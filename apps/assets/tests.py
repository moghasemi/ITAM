"""آزمون‌های موتور مقایسه اقلام، اسنپ‌شات و مولد QR."""
from __future__ import annotations

from django.test import TestCase

from apps.accounts.models import User
from apps.assets import qrgen
from apps.assets.models import (
    Asset,
    AssetCategory,
    ComponentType,
    HardwareSnapshot,
    SnapshotItem,
)
from apps.assets.services import compute_diff, create_snapshot, reference_snapshot
from apps.core.constants import (
    DIFF_ADDED,
    DIFF_CHANGED,
    DIFF_REMOVED,
    DIFF_REPLACED,
    DIFF_UNCHANGED,
)
from apps.org.models import Contract, Contractor


class _Item:
    """قلم ساختگی برای آزمون موتور مقایسه."""

    def __init__(self, pk, component_type, brand="", model_name="", serial_number="",
                 capacity="", quantity=1, slot="", condition="ok"):
        self.pk = pk
        self.component_type = component_type
        self.component_type_id = component_type.pk
        self.brand = brand
        self.model_name = model_name
        self.serial_number = serial_number
        self.capacity = capacity
        self.quantity = quantity
        self.slot = slot
        self.condition = condition

    def get_condition_display(self):
        return self.condition

    @property
    def display_label(self):
        return f"{self.component_type.name} {self.brand} {self.model_name}".strip()


class DiffEngineTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.cpu = ComponentType.objects.create(name="پردازنده", code="CPU", sort_order=10, is_key_item=True)
        cls.ram = ComponentType.objects.create(name="حافظه", code="RAM", sort_order=20, is_key_item=True)
        cls.ssd = ComponentType.objects.create(name="حافظه داخلی", code="SSD", sort_order=30, is_key_item=True)

    def test_unchanged_items(self):
        previous = [_Item(1, self.cpu, "Intel", "i5", "CPU-1", slot="سوکت")]
        current = [_Item(2, self.cpu, "Intel", "i5", "CPU-1", slot="سوکت")]
        result = compute_diff(previous, current)
        self.assertEqual(result["total_changes"], 0)
        self.assertEqual(result["counts"][DIFF_UNCHANGED], 1)

    def test_removed_item_is_alarm(self):
        previous = [
            _Item(1, self.cpu, "Intel", "i5", "CPU-1"),
            _Item(2, self.ram, "Kingston", "DDR4", "RAM-1", slot="اسلات ۱"),
        ]
        current = [_Item(3, self.cpu, "Intel", "i5", "CPU-1")]
        result = compute_diff(previous, current)
        self.assertEqual(result["removed"], 1)
        self.assertTrue(result["has_alarm"])
        self.assertEqual(result["counts"][DIFF_REMOVED], 1)

    def test_replaced_item(self):
        previous = [_Item(1, self.ssd, "Samsung", "870", "SSD-OLD", capacity="500GB", slot="SATA0")]
        current = [_Item(2, self.ssd, "WD", "SN570", "SSD-NEW", capacity="1TB", slot="SATA0")]
        result = compute_diff(previous, current)
        self.assertEqual(result["counts"][DIFF_REPLACED], 1)
        self.assertTrue(result["has_alarm"])

    def test_added_item(self):
        previous = [_Item(1, self.cpu, "Intel", "i5", "CPU-1")]
        current = [
            _Item(2, self.cpu, "Intel", "i5", "CPU-1"),
            _Item(3, self.ram, "Kingston", "DDR4", "RAM-9", slot="اسلات ۲"),
        ]
        result = compute_diff(previous, current)
        self.assertEqual(result["counts"][DIFF_ADDED], 1)
        self.assertEqual(result["removed"], 0)

    def test_changed_specs(self):
        previous = [_Item(1, self.ram, "Kingston", "DDR4", "RAM-1", capacity="4GB", slot="اسلات ۱")]
        current = [_Item(2, self.ram, "Kingston", "DDR4", "RAM-1", capacity="8GB", slot="اسلات ۱")]
        result = compute_diff(previous, current)
        self.assertEqual(result["counts"][DIFF_CHANGED], 1)
        self.assertTrue(any("ظرفیت" in change for change in result["rows"][0]["changes"]))

    def test_empty_previous(self):
        result = compute_diff([], [_Item(1, self.cpu, "Intel", "i5", "CPU-1")])
        self.assertEqual(result["counts"][DIFF_ADDED], 1)
        self.assertFalse(result["has_alarm"])


class SnapshotWorkflowTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.contractor = Contractor.objects.create(name="پیمانکار آزمون")
        cls.contract = Contract.objects.create(
            contractor=cls.contractor,
            number="T-1",
            title="قرارداد آزمون",
            start_date="2024-01-01",
            end_date="2025-01-01",
        )
        cls.category = AssetCategory.objects.create(
            name="کیس", code="PC", requires_component_tracking=True
        )
        cls.cpu = ComponentType.objects.create(name="پردازنده", code="CPU", is_key_item=True)
        cls.asset = Asset.objects.create(
            asset_tag="A-1", category=cls.category, contract=cls.contract, brand="DELL"
        )
        cls.technician = User.objects.create_user(
            username="tech", password="pass12345", role=User.ROLE_TECHNICIAN, contractor=cls.contractor
        )
        cls.it_expert = User.objects.create_user(
            username="expert", password="pass12345", role=User.ROLE_ADMIN_IT
        )

    def _make_snapshot(self, serial, user=None):
        user = user or self.technician
        snapshot = create_snapshot(self.asset, user)
        SnapshotItem.objects.create(
            snapshot=snapshot, component_type=self.cpu, brand="Intel", model_name="i5",
            serial_number=serial, slot="سوکت",
        )
        return snapshot

    def test_baseline_flow(self):
        snapshot = self._make_snapshot("CPU-1")
        self.assertTrue(snapshot.is_baseline)
        self.assertIsNone(snapshot.previous)
        self.assertEqual(snapshot.status, "draft")

        from apps.assets.services import approve_snapshot, submit_snapshot

        submit_snapshot(snapshot, self.technician)
        snapshot.refresh_from_db()
        self.assertEqual(snapshot.status, "pending")
        self.assertIsNotNone(snapshot.technician_confirmed_at)

        approve_snapshot(snapshot, self.it_expert)
        snapshot.refresh_from_db()
        self.asset.refresh_from_db()
        self.assertEqual(snapshot.status, "locked")
        self.assertIsNotNone(snapshot.locked_at)
        self.assertIsNotNone(snapshot.it_confirmed_at)
        self.assertEqual(self.asset.current_snapshot_id, snapshot.pk)
        self.assertIsNotNone(self.asset.baseline_locked_at)

    def test_second_snapshot_prefills_and_diffs(self):
        from apps.assets.services import approve_snapshot, submit_snapshot

        baseline = self._make_snapshot("CPU-1")
        submit_snapshot(baseline, self.technician)
        approve_snapshot(baseline, self.it_expert)

        review = create_snapshot(self.asset, self.technician)
        self.assertFalse(review.is_baseline)
        self.assertEqual(review.previous_id, baseline.pk)
        # اقلام از سند قبلی بارگذاری شده‌اند
        self.assertEqual(review.items.count(), 1)

        item = review.items.first()
        item.serial_number = "CPU-2"
        item.save()
        submit_snapshot(review, self.technician)
        review.refresh_from_db()
        self.assertEqual(review.diff_count, 1)
        self.assertEqual(review.diff_data["counts"][DIFF_REPLACED], 1)

    def test_reference_snapshot_points_to_locked(self):
        from apps.assets.services import approve_snapshot, submit_snapshot

        baseline = self._make_snapshot("CPU-1")
        submit_snapshot(baseline, self.technician)
        approve_snapshot(baseline, self.it_expert)
        self.assertEqual(reference_snapshot(self.asset).pk, baseline.pk)

    def test_technician_of_other_contractor_cannot_record(self):
        from django.core.exceptions import PermissionDenied

        other = User.objects.create_user(
            username="other", password="pass12345", role=User.ROLE_TECHNICIAN
        )
        with self.assertRaises(PermissionDenied):
            create_snapshot(self.asset, other)


class QrGeneratorTests(TestCase):
    """اعتبارسنجی مولد QR: چندجمله‌ای Reed-Solomon، ساختار و بازیابی داده."""

    KNOWN_GENERATOR_7 = [0, 87, 229, 146, 149, 238, 102, 21]
    KNOWN_GENERATOR_10 = [0, 251, 67, 46, 61, 118, 70, 64, 94, 32, 45]

    def test_reed_solomon_generator_matches_standard(self):
        for nsym, expected in ((7, self.KNOWN_GENERATOR_7), (10, self.KNOWN_GENERATOR_10)):
            generator = qrgen._rs_generator(nsym)
            exponents = [qrgen.GF_LOG[coefficient] if coefficient else 0 for coefficient in generator]
            self.assertEqual(exponents, expected, f"چندجمله‌ای مولد برای nsym={nsym} نادرست است")

    def test_gf_arithmetic(self):
        # α^8 = 0x1D با چندجمله‌ای مولد 0x11D
        self.assertEqual(qrgen.GF_EXP[8], 0x1D)
        self.assertEqual(qrgen._gf_mul(0, 123), 0)
        self.assertEqual(qrgen._gf_mul(1, 123), 123)

    def _decode(self, matrix):
        """بازیابی داده از ماتریس برای اطمینان از درستی جای‌گذاری و ماسک."""
        size = len(matrix)
        version = (size - 17) // 4

        bits = 0
        for i in range(6):
            bits |= matrix[i][8] << i
        bits |= matrix[7][8] << 6
        bits |= matrix[8][8] << 7
        bits |= matrix[8][7] << 8
        for i in range(9, 15):
            bits |= matrix[8][14 - i] << i
        bits ^= 0x5412
        payload = bits >> 10
        ecl_code = payload >> 3
        mask = payload & 7
        ecl = {value: key for key, value in qrgen.ECL_BITS.items()}[ecl_code]

        builder = qrgen._Builder(version)
        builder.draw_function_patterns()
        reserved = builder.function

        stream = []
        col = size - 1
        while col > 0:
            if col == 6:
                col -= 1
            upward = ((col + 1) & 2) == 0
            rows = range(size - 1, -1, -1) if upward else range(size)
            for row in rows:
                for c in (col, col - 1):
                    if reserved[row][c]:
                        continue
                    bit = matrix[row][c]
                    if qrgen._mask_bit(mask, row, c):
                        bit ^= 1
                    stream.append(bit)
            col -= 2

        ecc_per_block, groups = qrgen.BLOCK_TABLE[version][ecl]
        lengths = []
        for count, length in groups:
            lengths.extend([length] * count)
        total_data = sum(lengths)
        needed = (total_data + ecc_per_block * len(lengths)) * 8
        stream = stream[:needed]

        codewords = []
        for index in range(0, len(stream), 8):
            value = 0
            for bit in stream[index:index + 8]:
                value = (value << 1) | bit
            codewords.append(value)

        blocks = [[] for _ in lengths]
        cursor = 0
        max_length = max(lengths)
        for i in range(max_length):
            for index, length in enumerate(lengths):
                if i < length:
                    blocks[index].append(codewords[cursor])
                    cursor += 1
        data = [value for block in blocks for value in block]

        bit_string = "".join(f"{value:08b}" for value in data)
        mode = int(bit_string[:4], 2)
        count_bits = 8 if version <= 9 else 16
        length = int(bit_string[4:4 + count_bits], 2)
        start = 4 + count_bits
        raw = bit_string[start:start + length * 8]
        return mode, bytes(int(raw[i:i + 8], 2) for i in range(0, len(raw), 8))

    def test_round_trip(self):
        payloads = [
            "http://10.0.0.5:8000/assets/scan/2f6c1a5e-7b3d-4c9a-9f21-0a1b2c3d4e5f/",
            "A-10200001",
            "https://itam.local/a/1",
            "شماره اموال ۱۰۲۰۰۰۰۱",
        ]
        for payload in payloads:
            for ecc in ("L", "M", "Q", "H"):
                with self.subTest(payload=payload[:20], ecc=ecc):
                    matrix = qrgen.make_matrix(payload, ecc=ecc)
                    mode, decoded = self._decode(matrix)
                    self.assertEqual(mode, 0b0100)
                    self.assertEqual(decoded.decode("utf-8"), payload)

    def test_matrix_structure(self):
        matrix = qrgen.make_matrix("http://10.0.0.5:8000/a/1", ecc="M")
        size = len(matrix)
        self.assertEqual((size - 17) % 4, 0)
        # الگوهای راهنما در سه گوشه
        for row, col in ((0, 0), (0, size - 7), (size - 7, 0)):
            self.assertEqual(matrix[row][col], 1)
            self.assertEqual(matrix[row + 1][col + 1], 0)
            self.assertEqual(matrix[row + 3][col + 3], 1)
        # الگوی زمان‌بندی
        for index in range(8, size - 8):
            self.assertEqual(matrix[6][index], 1 if index % 2 == 0 else 0)
        # خانه تیره ثابت
        self.assertEqual(matrix[size - 8][8], 1)

    def test_version_selection(self):
        # ظرفیت نسخه ۱ با تصحیح خطای H برابر ۷ بایت است
        self.assertEqual(qrgen.choose_version(5, "H"), 1)
        self.assertEqual(qrgen.choose_version(8, "H"), 2)
        small = qrgen.make_matrix("x" * 10, ecc="L")
        large = qrgen.make_matrix("x" * 100, ecc="H")
        self.assertLess(len(small), len(large))

    def test_svg_output(self):
        svg = qrgen.svg("http://10.0.0.5:8000/a/1", module_size=4)
        self.assertTrue(svg.startswith("<svg"))
        self.assertIn("</svg>", svg)
        self.assertIn("<path", svg)

    def test_too_large_payload(self):
        with self.assertRaises(qrgen.QRCodeError):
            qrgen.make_matrix("x" * 5000, ecc="H")


class AssetModelTests(TestCase):
    def test_public_url_and_qr(self):
        from apps.core.models import SystemSetting

        setting = SystemSetting.load()
        setting.public_base_url = "http://10.0.0.5:8000"
        setting.save()

        category = AssetCategory.objects.create(name="کیس", requires_component_tracking=True)
        asset = Asset.objects.create(asset_tag="A-77", category=category)
        self.assertTrue(asset.public_url().startswith("http://10.0.0.5:8000/assets/scan/"))
        self.assertIn("<svg", asset.qr_svg())

    def test_next_version(self):
        category = AssetCategory.objects.create(name="کیس")
        asset = Asset.objects.create(asset_tag="A-88", category=category)
        self.assertEqual(HardwareSnapshot.next_version(asset), 1)
        HardwareSnapshot.objects.create(asset=asset, version=1)
        self.assertEqual(HardwareSnapshot.next_version(asset), 2)

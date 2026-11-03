"""تولید کد QR به‌صورت بومی (بدون وابستگی بیرونی).

پیاده‌سازی استاندارد ISO/IEC 18004 (Model 2) برای حالت بایت با سطوح
تصحیح خطای L/M/Q/H و نسخه‌های ۱ تا ۱۰ — کافی برای درج نشانی تجهیزات.
خروجی به‌صورت ماتریس یا تصویر SVG است (بدون نیاز به Pillow).
"""
from __future__ import annotations

__all__ = ["make_matrix", "svg", "svg_data_uri", "QRCodeError"]


class QRCodeError(ValueError):
    """داده برای تولید QR مناسب نیست."""


# ---------------------------------------------------------------------------
# میدان گالوا GF(256)
# ---------------------------------------------------------------------------
GF_EXP = [0] * 512
GF_LOG = [0] * 256
_x = 1
for _i in range(255):
    GF_EXP[_i] = _x
    GF_LOG[_x] = _i
    _x <<= 1
    if _x & 0x100:
        _x ^= 0x11D
for _i in range(255, 512):
    GF_EXP[_i] = GF_EXP[_i - 255]


def _gf_mul(a: int, b: int) -> int:
    if a == 0 or b == 0:
        return 0
    return GF_EXP[GF_LOG[a] + GF_LOG[b]]


def _poly_mul(a, b):
    result = [0] * (len(a) + len(b) - 1)
    for i, ca in enumerate(a):
        if not ca:
            continue
        for j, cb in enumerate(b):
            if cb:
                result[i + j] ^= _gf_mul(ca, cb)
    return result


def _rs_generator(nsym: int):
    generator = [1]
    for i in range(nsym):
        generator = _poly_mul(generator, [1, GF_EXP[i]])
    return generator


def _rs_encode(data, nsym: int):
    generator = _rs_generator(nsym)
    message = list(data) + [0] * nsym
    for i in range(len(data)):
        coef = message[i]
        if coef:
            for j in range(1, len(generator)):
                message[i + j] ^= _gf_mul(generator[j], coef)
    return message[len(data):]


# ---------------------------------------------------------------------------
# جدول‌های استاندارد QR
# ---------------------------------------------------------------------------
# برای هر نسخه: تعداد کل کدواژه‌ها
TOTAL_CODEWORDS = {
    1: 26, 2: 44, 3: 70, 4: 100, 5: 134,
    6: 172, 7: 196, 8: 242, 9: 292, 10: 346,
}

# برای هر نسخه و سطح تصحیح خطا: (کدواژه تصحیح خطا در هر بلوک، [(تعداد بلوک, کدواژه داده در بلوک), ...])
BLOCK_TABLE = {
    1: {
        "L": (7, [(1, 19)]), "M": (10, [(1, 16)]), "Q": (13, [(1, 13)]), "H": (17, [(1, 9)]),
    },
    2: {
        "L": (10, [(1, 34)]), "M": (16, [(1, 28)]), "Q": (22, [(1, 22)]), "H": (28, [(1, 16)]),
    },
    3: {
        "L": (15, [(1, 55)]), "M": (26, [(1, 44)]), "Q": (18, [(2, 17)]), "H": (22, [(2, 13)]),
    },
    4: {
        "L": (20, [(1, 80)]), "M": (18, [(2, 32)]), "Q": (26, [(2, 24)]), "H": (16, [(4, 9)]),
    },
    5: {
        "L": (26, [(1, 108)]), "M": (24, [(2, 43)]),
        "Q": (18, [(2, 15), (2, 16)]), "H": (22, [(2, 11), (2, 12)]),
    },
    6: {
        "L": (18, [(2, 68)]), "M": (16, [(4, 27)]), "Q": (24, [(4, 19)]), "H": (28, [(4, 15)]),
    },
    7: {
        "L": (20, [(2, 78)]), "M": (18, [(4, 31)]),
        "Q": (18, [(2, 14), (4, 15)]), "H": (26, [(4, 13), (1, 14)]),
    },
    8: {
        "L": (24, [(2, 97)]), "M": (22, [(2, 38), (2, 39)]),
        "Q": (22, [(4, 18), (2, 19)]), "H": (26, [(4, 14), (2, 15)]),
    },
    9: {
        "L": (30, [(2, 116)]), "M": (22, [(3, 36), (2, 37)]),
        "Q": (20, [(4, 16), (4, 17)]), "H": (24, [(4, 12), (4, 13)]),
    },
    10: {
        "L": (18, [(2, 68), (2, 69)]), "M": (26, [(4, 43), (1, 44)]),
        "Q": (24, [(6, 19), (2, 20)]), "H": (28, [(6, 15), (2, 16)]),
    },
}

# موقعیت الگوهای هم‌ترازی
ALIGNMENT_POSITIONS = {
    1: [], 2: [6, 18], 3: [6, 22], 4: [6, 26], 5: [6, 30],
    6: [6, 34], 7: [6, 22, 38], 8: [6, 24, 42], 9: [6, 26, 46], 10: [6, 28, 50],
}

# بیت‌های نشانگر سطح تصحیح خطا
ECL_BITS = {"L": 1, "M": 0, "Q": 3, "H": 2}
ECL_ORDER = ("L", "M", "Q", "H")


def _get_bit(value: int, index: int) -> int:
    return (value >> index) & 1


# ---------------------------------------------------------------------------
# ظرفیت و انتخاب نسخه
# ---------------------------------------------------------------------------
def data_capacity_bytes(version: int, ecl: str) -> int:
    """ظرفیت داده (بایت) برای نسخه و سطح خطای داده‌شده."""
    _, groups = BLOCK_TABLE[version][ecl]
    data_codewords = sum(count * length for count, length in groups)
    count_bits = 8 if version <= 9 else 16
    return (data_codewords * 8 - 4 - count_bits) // 8


def choose_version(data_length: int, ecl: str, min_version: int = 1) -> int:
    for version in range(max(1, min_version), 11):
        if data_capacity_bytes(version, ecl) >= data_length:
            return version
    raise QRCodeError(
        "حجم داده برای تولید QR بیش از حد بزرگ است (حداکثر نسخه ۱۰ پشتیبانی می‌شود)."
    )


# ---------------------------------------------------------------------------
# رمزگذاری داده
# ---------------------------------------------------------------------------
def _encode_data(payload: bytes, version: int, ecl: str):
    _, groups = BLOCK_TABLE[version][ecl]
    data_codewords = sum(count * length for count, length in groups)
    count_bits = 8 if version <= 9 else 16

    bits: list[int] = []

    def push(value: int, length: int):
        for i in range(length - 1, -1, -1):
            bits.append((value >> i) & 1)

    push(0b0100, 4)  # نشانگر حالت بایت
    push(len(payload), count_bits)
    for byte in payload:
        push(byte, 8)

    capacity_bits = data_codewords * 8
    # پایان‌دهنده
    for _ in range(min(4, capacity_bits - len(bits))):
        bits.append(0)
    # تکمیل تا مرز بایت
    while len(bits) % 8:
        bits.append(0)

    codewords = [int("".join(str(b) for b in bits[i:i + 8]), 2) for i in range(0, len(bits), 8)]
    # بایت‌های پرکننده
    pad = (0xEC, 0x11)
    index = 0
    while len(codewords) < data_codewords:
        codewords.append(pad[index % 2])
        index += 1

    # تقسیم به بلوک‌ها و افزودن کد تصحیح خطا
    ecc_per_block, groups = BLOCK_TABLE[version][ecl]
    blocks = []
    offset = 0
    for count, length in groups:
        for _ in range(count):
            blocks.append(codewords[offset:offset + length])
            offset += length
    ecc_blocks = [_rs_encode(block, ecc_per_block) for block in blocks]

    # درهم‌آمیزی
    result: list[int] = []
    max_data = max(len(block) for block in blocks)
    for i in range(max_data):
        for block in blocks:
            if i < len(block):
                result.append(block[i])
    for i in range(ecc_per_block):
        for block in ecc_blocks:
            result.append(block[i])
    return result


# ---------------------------------------------------------------------------
# ساخت ماتریس
# ---------------------------------------------------------------------------
class _Builder:
    def __init__(self, version: int):
        self.version = version
        self.size = version * 4 + 17
        self.modules = [[0] * self.size for _ in range(self.size)]
        self.function = [[False] * self.size for _ in range(self.size)]

    # -- توابع کمکی --------------------------------------------------------
    def set_function(self, row: int, col: int, dark: bool):
        self.modules[row][col] = 1 if dark else 0
        self.function[row][col] = True

    def draw_finder(self, row: int, col: int):
        for dr in range(-1, 8):
            for dc in range(-1, 8):
                r, c = row + dr, col + dc
                if not (0 <= r < self.size and 0 <= c < self.size):
                    continue
                inside = 0 <= dr <= 6 and 0 <= dc <= 6
                dark = inside and (dr in (0, 6) or dc in (0, 6) or (2 <= dr <= 4 and 2 <= dc <= 4))
                self.set_function(r, c, dark)

    def draw_alignment(self, row: int, col: int):
        for dr in range(-2, 3):
            for dc in range(-2, 3):
                dark = max(abs(dr), abs(dc)) != 1
                self.set_function(row + dr, col + dc, dark)

    def draw_function_patterns(self):
        size = self.size
        # الگوهای راهنما
        self.draw_finder(0, 0)
        self.draw_finder(size - 7, 0)
        self.draw_finder(0, size - 7)

        # الگوهای زمان‌بندی
        for i in range(8, size - 8):
            dark = i % 2 == 0
            self.set_function(6, i, dark)
            self.set_function(i, 6, dark)

        # الگوهای هم‌ترازی
        positions = ALIGNMENT_POSITIONS[self.version]
        for r in positions:
            for c in positions:
                if (r == 6 and c == 6) or (r == 6 and c == size - 7) or (r == size - 7 and c == 6):
                    continue
                self.draw_alignment(r, c)

        # خانه تیره ثابت
        self.set_function(size - 8, 8, True)

        # رزرو نواحی اطلاعات قالب
        for i in range(9):
            if not self.function[8][i]:
                self.set_function(8, i, False)
            if not self.function[i][8]:
                self.set_function(i, 8, False)
        for i in range(8):
            if not self.function[8][size - 1 - i]:
                self.set_function(8, size - 1 - i, False)
            if not self.function[size - 1 - i][8]:
                self.set_function(size - 1 - i, 8, False)

        # اطلاعات نسخه برای نسخه‌های ۷ و بالاتر
        if self.version >= 7:
            remainder = self.version
            for _ in range(12):
                remainder = (remainder << 1) ^ ((remainder >> 11) * 0x1F25)
            bits = (self.version << 12) | remainder
            for i in range(18):
                bit = _get_bit(bits, i)
                a = size - 11 + i % 3
                b = i // 3
                self.set_function(b, a, bool(bit))
                self.set_function(a, b, bool(bit))

    def draw_codewords(self, codewords):
        size = self.size
        bit_index = 0
        total_bits = len(codewords) * 8

        col = size - 1
        upward = True
        while col > 0:
            if col == 6:
                col -= 1
            upward = ((col + 1) & 2) == 0
            rows = range(size - 1, -1, -1) if upward else range(size)
            for row in rows:
                for c in (col, col - 1):
                    if self.function[row][c]:
                        continue
                    if bit_index < total_bits:
                        byte = codewords[bit_index >> 3]
                        self.modules[row][c] = _get_bit(byte, 7 - (bit_index & 7))
                        bit_index += 1
                    else:
                        self.modules[row][c] = 0
            col -= 2

    def draw_format_bits(self, ecl: str, mask: int):
        data = (ECL_BITS[ecl] << 3) | mask
        remainder = data
        for _ in range(10):
            remainder = (remainder << 1) ^ ((remainder >> 9) * 0x537)
        bits = ((data << 10) | remainder) ^ 0x5412
        size = self.size

        for i in range(0, 6):
            self.set_function(i, 8, bool(_get_bit(bits, i)))
        self.set_function(7, 8, bool(_get_bit(bits, 6)))
        self.set_function(8, 8, bool(_get_bit(bits, 7)))
        self.set_function(8, 7, bool(_get_bit(bits, 8)))
        for i in range(9, 15):
            self.set_function(8, 14 - i, bool(_get_bit(bits, i)))

        for i in range(0, 8):
            self.set_function(8, size - 1 - i, bool(_get_bit(bits, i)))
        for i in range(8, 15):
            self.set_function(size - 15 + i, 8, bool(_get_bit(bits, i)))
        self.set_function(size - 8, 8, True)

    def apply_mask(self, mask: int):
        for row in range(self.size):
            for col in range(self.size):
                if self.function[row][col]:
                    continue
                if _mask_bit(mask, row, col):
                    self.modules[row][col] ^= 1

    def copy(self):
        clone = _Builder.__new__(_Builder)
        clone.version = self.version
        clone.size = self.size
        clone.modules = [row[:] for row in self.modules]
        clone.function = [row[:] for row in self.function]
        return clone


def _mask_bit(mask: int, row: int, col: int) -> bool:
    if mask == 0:
        return (row + col) % 2 == 0
    if mask == 1:
        return row % 2 == 0
    if mask == 2:
        return col % 3 == 0
    if mask == 3:
        return (row + col) % 3 == 0
    if mask == 4:
        return (row // 2 + col // 3) % 2 == 0
    if mask == 5:
        return (row * col) % 2 + (row * col) % 3 == 0
    if mask == 6:
        return ((row * col) % 2 + (row * col) % 3) % 2 == 0
    if mask == 7:
        return ((row + col) % 2 + (row * col) % 3) % 2 == 0
    raise ValueError("شماره ماسک نامعتبر است")


def _penalty_score(modules) -> int:
    size = len(modules)
    score = 0

    # قاعده ۱: پنج ماژول همرنگ پشت‌سرهم
    for line_getter in (
        lambda i, j: modules[i][j],
        lambda i, j: modules[j][i],
    ):
        for i in range(size):
            run_color = line_getter(i, 0)
            run_length = 1
            for j in range(1, size):
                color = line_getter(i, j)
                if color == run_color:
                    run_length += 1
                else:
                    if run_length >= 5:
                        score += 3 + (run_length - 5)
                    run_color = color
                    run_length = 1
            if run_length >= 5:
                score += 3 + (run_length - 5)

    # قاعده ۲: بلوک‌های ۲×۲ همرنگ
    for row in range(size - 1):
        for col in range(size - 1):
            value = modules[row][col]
            if (
                value == modules[row][col + 1]
                and value == modules[row + 1][col]
                and value == modules[row + 1][col + 1]
            ):
                score += 3

    # قاعده ۳: الگوی شبیه راهنما
    pattern_a = [1, 0, 1, 1, 1, 0, 1, 0, 0, 0, 0]
    pattern_b = [0, 0, 0, 0, 1, 0, 1, 1, 1, 0, 1]
    for i in range(size):
        row = modules[i]
        col = [modules[j][i] for j in range(size)]
        for j in range(size - 10):
            if row[j:j + 11] == pattern_a or row[j:j + 11] == pattern_b:
                score += 40
            if col[j:j + 11] == pattern_a or col[j:j + 11] == pattern_b:
                score += 40

    # قاعده ۴: تعادل تیره و روشن
    dark = sum(sum(row) for row in modules)
    total = size * size
    percent = dark * 100 / total
    score += int(abs(percent - 50) / 5) * 10
    return score


def _build(payload: bytes, version: int, ecl: str):
    codewords = _encode_data(payload, version, ecl)
    best = None
    best_score = None
    for mask in range(8):
        builder = _Builder(version)
        builder.draw_function_patterns()
        builder.draw_codewords(codewords)
        builder.apply_mask(mask)
        builder.draw_format_bits(ecl, mask)
        score = _penalty_score(builder.modules)
        if best_score is None or score < best_score:
            best_score = score
            best = builder
    return best


# ---------------------------------------------------------------------------
# واسط عمومی
# ---------------------------------------------------------------------------
def make_matrix(content: str | bytes, ecc: str = "M", min_version: int = 1):
    """ماتریس دوبعدی QR (۱ = تیره) را برمی‌گرداند."""
    ecl = (ecc or "M").upper()
    if ecl not in ECL_BITS:
        raise QRCodeError("سطح تصحیح خطا باید یکی از L/M/Q/H باشد.")
    payload = content.encode("utf-8") if isinstance(content, str) else bytes(content)
    version = choose_version(len(payload), ecl, min_version=min_version)
    builder = _build(payload, version, ecl)
    return builder.modules


def svg(
    content: str | bytes,
    *,
    ecc: str = "M",
    module_size: int = 6,
    quiet_zone: int = 4,
    dark: str = "#000000",
    light: str = "#ffffff",
    title: str = "",
) -> str:
    """کد QR را به‌صورت تصویر برداری SVG برمی‌گرداند (مناسب چاپ برچسب)."""
    matrix = make_matrix(content, ecc)
    count = len(matrix)
    size = (count + 2 * quiet_zone) * module_size
    parts = []
    for row_index, row in enumerate(matrix):
        col = 0
        while col < count:
            if row[col]:
                start = col
                while col < count and row[col]:
                    col += 1
                run = col - start
                x = (start + quiet_zone) * module_size
                y = (row_index + quiet_zone) * module_size
                parts.append(
                    f"M{x} {y}h{run * module_size}v{module_size}h-{run * module_size}z"
                )
            else:
                col += 1
    description = f"<title>{_escape(title)}</title>" if title else ""
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{size}" height="{size}" '
        f'viewBox="0 0 {size} {size}" shape-rendering="crispEdges" role="img">'
        f"{description}"
        f'<rect width="{size}" height="{size}" fill="{light}"/>'
        f'<path d="{"".join(parts)}" fill="{dark}"/></svg>'
    )


def svg_data_uri(content: str | bytes, **kwargs) -> str:
    """کد QR به‌صورت data-uri برای درج مستقیم در HTML."""
    from urllib.parse import quote

    return "data:image/svg+xml;charset=utf-8," + quote(svg(content, **kwargs))


def _escape(text: str) -> str:
    return (
        str(text)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )

import io
import zipfile

from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import SimpleTestCase

from apps.core.validators import validate_document_file, validate_image_file


class UploadContentValidationTests(SimpleTestCase):
    def test_png_signature_is_accepted(self):
        png = SimpleUploadedFile(
            "proof.png",
            b"\x89PNG\r\n\x1a\n" + b"\x00" * 24,
            content_type="image/png",
        )
        validate_image_file(png)

    def test_pdf_disguised_as_png_is_rejected(self):
        fake_image = SimpleUploadedFile(
            "proof.png", b"%PDF-1.7 fake image", content_type="image/png"
        )
        with self.assertRaises(ValidationError):
            validate_image_file(fake_image)

    def test_executable_content_disguised_as_pdf_is_rejected(self):
        fake_pdf = SimpleUploadedFile(
            "report.pdf", b"MZ\x90\x00not a PDF", content_type="application/pdf"
        )
        with self.assertRaises(ValidationError):
            validate_document_file(fake_pdf)

    def test_pdf_signature_is_accepted(self):
        pdf = SimpleUploadedFile(
            "report.pdf", b"%PDF-1.7\n% minimal test file", content_type="application/pdf"
        )
        validate_document_file(pdf)

    def test_docx_requires_a_real_zip_package_with_document_member(self):
        stream = io.BytesIO()
        with zipfile.ZipFile(stream, "w") as archive:
            archive.writestr("word/document.xml", "<document/>")
        docx = SimpleUploadedFile("report.docx", stream.getvalue())
        validate_document_file(docx)

        invalid_docx = SimpleUploadedFile("bad.docx", b"PK\x03\x04not a zip")
        with self.assertRaises(ValidationError):
            validate_document_file(invalid_docx)

    def test_docx_with_excessive_archive_members_is_rejected(self):
        stream = io.BytesIO()
        with zipfile.ZipFile(stream, "w") as archive:
            archive.writestr("word/document.xml", "<document/>")
            for index in range(1000):
                archive.writestr(f"word/parts/{index}.xml", "<part/>")
        upload = SimpleUploadedFile("large-package.docx", stream.getvalue())
        with self.assertRaises(ValidationError):
            validate_document_file(upload)

    def test_unknown_attachment_extension_is_rejected(self):
        upload = SimpleUploadedFile("payload.exe", b"MZ\x90\x00")
        with self.assertRaises(ValidationError):
            validate_document_file(upload)

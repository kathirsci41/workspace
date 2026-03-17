"""Tests for StorageService (NAS file storage abstraction)."""
import os
import pytest
import tempfile
import asyncio

from app.services.storage_service import StorageService


# ── Helpers ──────────────────────────────────────────────────────────────

def run_async(coro):
    """Helper to run async functions in sync tests."""
    return asyncio.run(coro)


@pytest.fixture
def tmp_nas(tmp_path):
    """Create a temp directory to act as NAS base path."""
    return str(tmp_path)


@pytest.fixture
def svc(tmp_nas):
    return StorageService(nas_base_path=tmp_nas)


# ── generate_storage_path ────────────────────────────────────────────────

class TestGenerateStoragePath:
    def test_returns_tuple_of_two_strings(self, svc):
        rel, fname = svc.generate_storage_path("SKY-AB123", "PO-001", "CUSTOMER_PO", "invoice.pdf")
        assert isinstance(rel, str)
        assert isinstance(fname, str)

    def test_relative_path_contains_all_parts(self, svc):
        rel, _ = svc.generate_storage_path("SKY-AB123", "PO-001", "VENDOR_DC", "doc.pdf")
        assert "documents/SKY-AB123/PO-001/VENDOR_DC/" in rel

    def test_uuid_filename_contains_sanitized_original(self, svc):
        _, fname = svc.generate_storage_path("CUS-1", "PO-2", "POD", "My File (1).pdf")
        # original should be sanitized: spaces and parens become _
        assert "My_File__1_.pdf" in fname

    def test_uuid_prefix_is_8_chars(self, svc):
        _, fname = svc.generate_storage_path("CUS-1", "PO-2", "POD", "test.pdf")
        prefix = fname.split("_")[0]
        assert len(prefix) == 8

    def test_unique_filenames_each_call(self, svc):
        _, f1 = svc.generate_storage_path("C", "P", "T", "a.pdf")
        _, f2 = svc.generate_storage_path("C", "P", "T", "a.pdf")
        assert f1 != f2


# ── sanitize_filename ────────────────────────────────────────────────────

class TestSanitizeFilename:
    def test_leaves_safe_chars(self):
        assert StorageService.sanitize_filename("hello.pdf") == "hello.pdf"

    def test_replaces_spaces(self):
        assert StorageService.sanitize_filename("my file.pdf") == "my_file.pdf"

    def test_replaces_special_chars(self):
        result = StorageService.sanitize_filename("inv@ice#2024!.pdf")
        assert "@" not in result
        assert "#" not in result
        assert "!" not in result

    def test_preserves_hyphens(self):
        assert StorageService.sanitize_filename("a-b-c.pdf") == "a-b-c.pdf"

    def test_truncates_to_100_chars(self):
        long_name = "a" * 200 + ".pdf"
        result = StorageService.sanitize_filename(long_name)
        assert len(result) <= 100

    def test_empty_string(self):
        result = StorageService.sanitize_filename("")
        assert result == ""

    def test_unicode_chars_replaced(self):
        result = StorageService.sanitize_filename("日本語.pdf")
        # Non-word chars in ASCII sense get replaced
        assert ".pdf" in result


# ── calculate_checksum ───────────────────────────────────────────────────

class TestCalculateChecksum:
    def test_returns_hex_string(self):
        cs = StorageService.calculate_checksum(b"hello world")
        assert isinstance(cs, str)
        assert len(cs) == 64  # SHA-256 hex

    def test_deterministic(self):
        data = b"consistent data"
        assert StorageService.calculate_checksum(data) == StorageService.calculate_checksum(data)

    def test_different_data_different_checksum(self):
        cs1 = StorageService.calculate_checksum(b"aaa")
        cs2 = StorageService.calculate_checksum(b"bbb")
        assert cs1 != cs2

    def test_empty_bytes(self):
        cs = StorageService.calculate_checksum(b"")
        assert len(cs) == 64

    def test_known_sha256(self):
        import hashlib
        data = b"test"
        expected = hashlib.sha256(data).hexdigest()
        assert StorageService.calculate_checksum(data) == expected


# ── _validate_path ───────────────────────────────────────────────────────

class TestValidatePath:
    def test_normal_path_passes(self):
        StorageService._validate_path("documents/customer/file.pdf")

    def test_rejects_double_dot(self):
        with pytest.raises(ValueError, match="traversal"):
            StorageService._validate_path("../../etc/passwd")

    def test_rejects_embedded_double_dot(self):
        with pytest.raises(ValueError, match="traversal"):
            StorageService._validate_path("documents/../secret")

    def test_single_dot_ok(self):
        StorageService._validate_path("./documents/file.pdf")


# ── save_file / read_file / delete_file ──────────────────────────────────

class TestFileOperations:
    def test_save_and_read(self, svc, tmp_nas):
        data = b"PDF content here"
        rel = "test_dir/file.bin"
        run_async(svc.save_file(rel, data))
        result = run_async(svc.read_file(rel))
        assert result == data

    def test_save_creates_directories(self, svc, tmp_nas):
        rel = "deep/nested/dir/file.txt"
        run_async(svc.save_file(rel, b"data"))
        assert os.path.exists(os.path.join(tmp_nas, "deep", "nested", "dir", "file.txt"))

    def test_read_nonexistent_raises(self, svc):
        with pytest.raises(FileNotFoundError):
            run_async(svc.read_file("does/not/exist.pdf"))

    def test_delete_existing_file(self, svc, tmp_nas):
        rel = "to_delete/file.bin"
        run_async(svc.save_file(rel, b"data"))
        result = run_async(svc.delete_file(rel))
        assert result is True
        assert not os.path.exists(os.path.join(tmp_nas, rel))

    def test_delete_nonexistent_returns_false(self, svc):
        result = run_async(svc.delete_file("no/such/file.bin"))
        assert result is False

    def test_save_rejects_traversal(self, svc):
        with pytest.raises(ValueError, match="traversal"):
            run_async(svc.save_file("../../etc/passwd", b"evil"))

    def test_read_rejects_traversal(self, svc):
        with pytest.raises(ValueError, match="traversal"):
            run_async(svc.read_file("../../../secret"))

    def test_delete_rejects_traversal(self, svc):
        with pytest.raises(ValueError, match="traversal"):
            run_async(svc.delete_file("../../etc/passwd"))


# ── get_full_path ────────────────────────────────────────────────────────

class TestGetFullPath:
    def test_joins_base_and_relative(self, svc, tmp_nas):
        result = svc.get_full_path("docs/file.pdf")
        assert result == os.path.join(tmp_nas, "docs/file.pdf")

    def test_rejects_traversal(self, svc):
        with pytest.raises(ValueError, match="traversal"):
            svc.get_full_path("../../etc/passwd")

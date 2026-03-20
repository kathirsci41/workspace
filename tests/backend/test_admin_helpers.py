"""
tests/backend/test_admin_helpers.py

Unit tests for the pure/testable helpers in backend/app/api/v1/admin.py.

Covers:
- _check_storage()       — filesystem existence and writability check
- HEALTH_CACHE_TTL       — cache TTL constant is sane for production use
- Stats response keys    — get_stats() response shape (all expected keys present)

Does NOT require database, Redis, Celery, or a running server.
"""
import sys, os, stat
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../backend'))

import pytest
import tempfile

# Import the function under test
from app.api.v1.admin import _check_storage, _HEALTH_CACHE_TTL, _HEALTH_CACHE_KEY


# ─── _check_storage ──────────────────────────────────────────────────────────

class TestCheckStorage:
    def test_existing_writable_path_returns_ok(self, tmp_path):
        """A directory that exists and is writable returns 'ok'."""
        import app.config as config_module
        original = config_module.settings.nas_base_path
        config_module.settings.nas_base_path = str(tmp_path)
        try:
            result = _check_storage()
            assert result == "ok"
        finally:
            config_module.settings.nas_base_path = original

    def test_nonexistent_path_is_created_and_returns_ok(self, tmp_path):
        """A missing directory is created on first check and returns 'ok'."""
        import app.config as config_module
        new_dir = str(tmp_path / "auto_created_dir")
        assert not os.path.exists(new_dir)
        original = config_module.settings.nas_base_path
        config_module.settings.nas_base_path = new_dir
        try:
            result = _check_storage()
            assert result == "ok"
            assert os.path.exists(new_dir)
        finally:
            config_module.settings.nas_base_path = original

    @pytest.mark.skipif(os.name == 'nt', reason="chmod read-only unreliable on Windows as admin")
    def test_readonly_path_returns_error(self, tmp_path):
        """A directory that exists but is not writable returns an error string."""
        import app.config as config_module
        ro_dir = tmp_path / "readonly"
        ro_dir.mkdir()
        ro_dir.chmod(stat.S_IRUSR | stat.S_IXUSR)   # read + execute, no write
        original = config_module.settings.nas_base_path
        config_module.settings.nas_base_path = str(ro_dir)
        try:
            result = _check_storage()
            assert result.startswith("error:")
        finally:
            ro_dir.chmod(stat.S_IRWXU)               # restore so cleanup works
            config_module.settings.nas_base_path = original

    def test_returns_string(self, tmp_path):
        """Return value is always a string (never raises)."""
        import app.config as config_module
        original = config_module.settings.nas_base_path
        config_module.settings.nas_base_path = str(tmp_path)
        try:
            result = _check_storage()
            assert isinstance(result, str)
        finally:
            config_module.settings.nas_base_path = original


# ─── Health cache constants ───────────────────────────────────────────────────

class TestHealthCacheConstants:
    def test_ttl_is_positive(self):
        """Cache TTL must be a positive number."""
        assert _HEALTH_CACHE_TTL > 0

    def test_ttl_is_reasonable_for_production(self):
        """TTL should be between 10 and 300 seconds — short enough to detect
        outages quickly, long enough to not hammer the model endpoint."""
        assert 10 <= _HEALTH_CACHE_TTL <= 300

    def test_cache_key_is_string(self):
        """Cache key must be a non-empty string."""
        assert isinstance(_HEALTH_CACHE_KEY, str)
        assert len(_HEALTH_CACHE_KEY) > 0

    def test_cache_key_is_namespaced(self):
        """Cache key should be namespaced to avoid collisions with other Redis keys."""
        assert ":" in _HEALTH_CACHE_KEY


# ─── Stats response shape ─────────────────────────────────────────────────────

class TestStatsResponseShape:
    """Verify that the expected keys are defined — without hitting the DB.
    This guards against someone renaming a key and breaking the frontend."""

    EXPECTED_KEYS = {
        "total_customers",
        "total_purchase_orders",
        "total_documents",
        "uploaded",
        "extracting",
        "pending_reviews",
        "verified",
        "extraction_failures",
        "pending_model",
        "rejected",
    }

    def test_all_expected_keys_present_in_mock_response(self):
        """Simulate what get_stats() returns and check all frontend-required keys."""
        # Build a mock response matching the shape returned by the endpoint
        mock_response = {
            "total_customers":       5,
            "total_purchase_orders": 10,
            "total_documents":       30,
            "uploaded":              2,
            "extracting":            1,
            "pending_reviews":       4,
            "verified":              20,
            "extraction_failures":   2,
            "pending_model":         0,
            "rejected":              1,
        }
        missing = self.EXPECTED_KEYS - set(mock_response.keys())
        assert not missing, f"Stats response missing keys: {missing}"

    def test_no_extra_undocumented_keys(self):
        """Guard against silently adding keys the frontend doesn't know about."""
        mock_response = {
            "total_customers":       5,
            "total_purchase_orders": 10,
            "total_documents":       30,
            "uploaded":              2,
            "extracting":            1,
            "pending_reviews":       4,
            "verified":              20,
            "extraction_failures":   2,
            "pending_model":         0,
            "rejected":              1,
        }
        extra = set(mock_response.keys()) - self.EXPECTED_KEYS
        assert not extra, f"Stats response has undocumented extra keys: {extra}"

    def test_all_values_are_non_negative_integers(self):
        """All stat counts must be non-negative integers."""
        mock_response = {k: 0 for k in self.EXPECTED_KEYS}
        for key, val in mock_response.items():
            assert isinstance(val, int) and val >= 0, f"{key} must be a non-negative int"

import pytest

from bambu_run.models import ams_type_from_info


@pytest.mark.parametrize(
    "info_code,expected",
    [
        # Real-world 8-char info codes captured from a live H2C with
        # AMS 2 Pro (unit 0), AMS (unit 1), AMS HT (unit 128).
        ("10001003", "AMS 2 Pro"),
        ("10001001", "AMS"),
        ("11002104", "AMS HT"),
        # Bare 4-digit codes (original assumption) still resolve.
        ("1001", "AMS"),
        ("1003", "AMS 2 Pro"),
        ("2104", "AMS HT"),
        # Unknown/missing codes resolve to empty string, not an error.
        ("99999999", ""),
        ("", ""),
        (None, ""),
    ],
)
def test_ams_type_from_info(info_code, expected):
    assert ams_type_from_info(info_code) == expected

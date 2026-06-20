import pytest

from bambu_run.diagnostics import redact_diagnostics, build_diagnostics_report


def test_redacts_password_and_token_like_keys():
    data = {"BAMBU_PASSWORD": "hunter2", "access_token": "abc123", "ok": "fine"}

    redacted = redact_diagnostics(data)

    assert redacted["BAMBU_PASSWORD"] == "***REDACTED***"
    assert redacted["access_token"] == "***REDACTED***"
    assert redacted["ok"] == "fine"


def test_masks_known_identifier_keys_partially():
    data = {"dev_id": "31B8BP592601478", "tray_uuid": "EE37828FA8844DE1AB12"}

    redacted = redact_diagnostics(data)

    assert redacted["dev_id"] == "31B8...1478"
    assert redacted["tray_uuid"] == "EE37...AB12"


def test_short_identifier_values_fully_masked():
    data = {"dev_id": "short"}

    redacted = redact_diagnostics(data)

    assert redacted["dev_id"] == "***"


def test_recurses_into_nested_structures():
    data = {"devices": [{"dev_id": "31B8BP592601478", "name": "RNL-H2C"}]}

    redacted = redact_diagnostics(data)

    assert redacted["devices"][0]["dev_id"] == "31B8...1478"
    assert redacted["devices"][0]["name"] == "RNL-H2C"


def test_no_redact_passthrough_keeps_original_values():
    data = {"dev_id": "31B8BP592601478", "BAMBU_PASSWORD": "hunter2"}

    result = redact_diagnostics(data, redact=False)

    assert result == data


def test_build_diagnostics_report_structure():
    devices = [{"dev_id": "SERIAL-A", "name": "Printer A", "dev_product_name": "H2C"}]
    raw_payloads = {"SERIAL-A": {"device": {"extruder": {"info": []}}}}

    report = build_diagnostics_report(devices, raw_payloads)

    assert report["device_count"] == 1
    assert "generated_at" in report
    assert report["devices"][0]["device_info"]["dev_id"] == "SERIAL-A"
    assert report["devices"][0]["raw_mqtt_payload"] == {"device": {"extruder": {"info": []}}}


def test_build_diagnostics_report_handles_missing_payload():
    devices = [{"dev_id": "SERIAL-A", "name": "Printer A"}]

    report = build_diagnostics_report(devices, raw_payloads={})

    assert report["devices"][0]["raw_mqtt_payload"] is None
    assert report["devices"][0]["note"] == "No MQTT data received within the listen window."

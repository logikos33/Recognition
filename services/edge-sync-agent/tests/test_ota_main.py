"""Tests for app.ota.__main__'s OTA_SECONDARY_UNIT_NAMES env parsing:
unset -> default list, explicit empty -> opt-out, csv -> trimmed list."""

from app.ota.__main__ import _DEFAULT_SECONDARY_UNIT_NAMES, _parse_secondary_unit_names


def test_unset_env_uses_default_secondary_units():
    assert _parse_secondary_unit_names(None) == _DEFAULT_SECONDARY_UNIT_NAMES
    # edge-telemetry-collector is deliberately NOT part of the default: it's
    # a system unit (sudo-managed), not systemd --user, and runs from a
    # fixed path outside the OTA-managed `current` symlink — see the
    # OTA_SECONDARY_UNIT_NAMES docstring in app/ota/__main__.py.
    assert "edge-telemetry-collector" not in _DEFAULT_SECONDARY_UNIT_NAMES
    # edge-monitoring-collector IS in the default (runs from `current` like
    # the others) — a unit outside this list keeps running OLD code after
    # every release until someone restarts it over SSH (debt D-42).
    assert _DEFAULT_SECONDARY_UNIT_NAMES == (
        "edge-frame-collector",
        "edge-live-view",
        "edge-monitoring-collector",
    )


def test_explicit_empty_string_opts_out_of_all_secondary_units():
    assert _parse_secondary_unit_names("") == ()


def test_csv_is_split_and_trimmed():
    assert _parse_secondary_unit_names(" edge-frame-collector, edge-live-view ") == (
        "edge-frame-collector",
        "edge-live-view",
    )


def test_csv_drops_empty_entries_from_stray_commas():
    assert _parse_secondary_unit_names("edge-frame-collector,,edge-live-view,") == (
        "edge-frame-collector",
        "edge-live-view",
    )


def test_single_unit_override():
    assert _parse_secondary_unit_names("edge-frame-collector") == ("edge-frame-collector",)

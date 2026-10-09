"""Unit tests for the download manifest (http_get) and provenance.json (provenance). No network: the HTTP
call is replaced by a stub."""
import hashlib
import json

import pytest

from data_prep.historical import config, http_get, provenance


@pytest.fixture
def raw(tmp_path, monkeypatch):
    raw_dir = tmp_path / "raw"
    raw_dir.mkdir()
    monkeypatch.setattr(http_get, "RAW_DIR", raw_dir)
    monkeypatch.setattr(http_get, "MANIFEST", tmp_path / "raw_manifest.json")
    monkeypatch.setattr(config, "RAW_DIR", raw_dir)
    calls = []

    def fake_get(url, **kwargs):
        calls.append(url)
        return b"payload-" + str(len(calls)).encode(), {"http_status": 200, "content_type": "text/csv",
                                                        "last_modified": "Tue, 06 Oct 2026 13:23:31 GMT", "etag": "x"}
    monkeypatch.setattr(http_get, "get_bytes", fake_get)
    return raw_dir, calls


def test_download_records_url_time_size_and_checksum(raw):
    raw_dir, _ = raw
    dest = raw_dir / "bfe" / "a.csv"
    http_get.download("https://www.bfe-ogd.ch/a.csv", dest, force=False)
    entry = http_get.load_manifest()["bfe/a.csv"]
    assert entry["url"] == "https://www.bfe-ogd.ch/a.csv"
    assert entry["sha256"] == hashlib.sha256(b"payload-1").hexdigest() and entry["bytes"] == 9
    assert entry["retrieved_at_utc"] and entry["last_modified"] == "Tue, 06 Oct 2026 13:23:31 GMT"


def test_existing_matching_file_is_reused_without_a_request(raw):
    raw_dir, calls = raw
    dest = raw_dir / "a.csv"
    http_get.download("https://x/a.csv", dest, force=False)
    http_get.download("https://x/a.csv", dest, force=False)
    assert len(calls) == 1


def test_changed_file_raises(raw):
    raw_dir, _ = raw
    dest = raw_dir / "a.csv"
    http_get.download("https://x/a.csv", dest, force=False)
    dest.write_bytes(b"edited by hand")
    with pytest.raises(RuntimeError, match="changed since it was downloaded"):
        http_get.download("https://x/a.csv", dest, force=False)


def test_different_source_url_raises_until_forced(raw):
    raw_dir, calls = raw
    dest = raw_dir / "ogd17.csv"
    http_get.download("https://www.uvek-gis.admin.ch/ogd17.csv", dest, force=False)
    with pytest.raises(RuntimeError, match="was downloaded from"):
        http_get.download("https://www.bfe-ogd.ch/ogd17.csv", dest, force=False)
    http_get.download("https://www.bfe-ogd.ch/ogd17.csv", dest, force=True)
    assert http_get.load_manifest()["ogd17.csv"]["url"] == "https://www.bfe-ogd.ch/ogd17.csv" and len(calls) == 2


def test_file_from_before_the_manifest_gets_an_entry_with_unknown_time(raw):
    raw_dir, calls = raw
    dest = raw_dir / "old.json"
    dest.write_bytes(b"old")
    http_get.download("https://x/old.json", dest, force=False)
    entry = http_get.load_manifest()["old.json"]
    assert entry["retrieved_at_utc"] is None and "before the manifest" in entry["note"] and not calls


def test_entsoe_token_is_never_stored():
    url = "https://web-api.tp.entsoe.eu/api?documentType=A61&securityToken=abc123&in_Domain=10YCH-SWISSGRIDZ"
    clean = http_get.redact(url)
    assert "abc123" not in clean and "securityToken=REDACTED" in clean and "documentType=A61" in clean
    plain = "https://api.energy-charts.info/v2/price?bzn=IT-North&start=2025-10-01&end=2026-09-30"
    assert http_get.redact(plain) == plain


def test_provenance_lists_raw_checksums_marks_hand_copied_files_and_detects_edits(raw):
    raw_dir, _ = raw
    http_get.download("https://x/a.csv", raw_dir / "a.csv", force=False)
    (raw_dir / "entsoe_web").mkdir()
    (raw_dir / "entsoe_web" / "copy.txt").write_text("hand copy", encoding="utf-8")
    files = provenance.raw_files(http_get.load_manifest())
    assert files["a.csv"]["url"] == "https://x/a.csv"
    assert "not downloaded by download.py" in files["entsoe_web/copy.txt"]["source"]
    (raw_dir / "a.csv").write_bytes(b"tampered")
    with pytest.raises(RuntimeError, match="differs from its manifest checksum"):
        provenance.raw_files(http_get.load_manifest())


def test_provenance_settings_include_the_documented_assumptions():
    s = provenance.settings()
    assert s["ONSITE_SOLAR_SHARE"] == 0.5 and s["CAPACITY_HOURLY_RULE"] == "min"
    json.dumps(s)  # serialisable

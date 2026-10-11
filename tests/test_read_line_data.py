"""Unit tests for the transmission lines read by read_line_data (model/data_import_fcns.py).

A node pair must be one line: the model's Export variable is signed, so the same pair listed in
both directions would double its capacity. The function reads input/NTC/NTC_{import,export}_
<policy>_2050.csv relative to the working directory; the tests write small versions into a
temporary folder.
"""
import pytest

from model.data_import_fcns import read_line_data


def _read_lines(tmp_path, monkeypatch, import_rows, export_rows):
    ntc = tmp_path / "input" / "NTC"
    ntc.mkdir(parents=True)
    (ntc / "NTC_import_Test_2050.csv").write_text(
        "index,Import Capacity (MW)\n" + "".join(f"{line},{mw}\n" for line, mw in import_rows)
    )
    (ntc / "NTC_export_Test_2050.csv").write_text(
        "index,Export Capacity (MW)\n" + "".join(f"{line},{mw}\n" for line, mw in export_rows)
    )
    monkeypatch.chdir(tmp_path)
    return read_line_data(2050, ["AT00", "CH00"], ["t_1"], 1, "Test")


def test_line_listed_in_one_direction_in_both_files_is_one_line(tmp_path, monkeypatch):
    lines, map_line_node, export_limit, import_limit, _ = _read_lines(
        tmp_path, monkeypatch, [("AT00-CH00", 1200)], [("AT00-CH00", 900)]
    )
    assert lines == ["HVAC_AT00_CH00"]
    assert map_line_node["HVAC_AT00_CH00"] == {"start_node": "AT00", "end_node": "CH00"}
    assert export_limit["HVAC_AT00_CH00", "t_1"] == 900
    assert import_limit["HVAC_AT00_CH00", "t_1"] == 1200


def test_export_file_listing_the_reverse_of_an_import_line_raises(tmp_path, monkeypatch):
    with pytest.raises(ValueError, match="HVAC_CH00_AT00"):
        _read_lines(tmp_path, monkeypatch, [("AT00-CH00", 1200)], [("AT00-CH00", 900), ("CH00-AT00", 900)])


def test_import_file_listing_both_directions_raises(tmp_path, monkeypatch):
    with pytest.raises(ValueError, match="HVAC_CH00_AT00"):
        _read_lines(tmp_path, monkeypatch, [("AT00-CH00", 1200), ("CH00-AT00", 1200)], [("AT00-CH00", 900)])

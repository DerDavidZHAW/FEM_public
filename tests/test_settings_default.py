"""Unit test for scenarios/settings_default.py.

A key written twice in the dict literal silently keeps only its last value, so each default
setting must appear once. The file is parsed, not imported, because the dict cannot show the
repeated key after it is built.
"""
import ast
from pathlib import Path

SETTINGS_DEFAULT = Path(__file__).resolve().parents[1] / "scenarios" / "settings_default.py"


def test_every_default_setting_is_defined_once():
    tree = ast.parse(SETTINGS_DEFAULT.read_text())
    [defaults] = [
        node.value for node in tree.body
        if isinstance(node, ast.Assign) and [t.id for t in node.targets] == ["seetings_default_param"]
    ]
    keys = [key.value for key in defaults.keys]
    assert sorted({key for key in keys if keys.count(key) > 1}) == []

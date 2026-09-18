import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import ark_mobile_adb as m


def test_parse_devices():
    data = """List of devices attached
127.0.0.1:5555 device product:p3sxxx model:SM_G998B transport_id:2
emulator-5554 device product:p3sxxx model:SM_G998B transport_id:1
"""
    rows = m.parse_devices(data)
    assert len(rows) == 2
    assert rows[0]["serial"] == "127.0.0.1:5555"
    assert rows[0]["state"] == "device"
    assert rows[0]["model"] == "SM_G998B"


def test_parse_offline():
    rows = m.parse_devices("emulator-5554 offline")
    assert rows[0]["state"] == "offline"

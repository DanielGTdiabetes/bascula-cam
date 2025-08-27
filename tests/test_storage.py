from pathlib import Path
from bascula.services.storage import Storage

def test_storage_tmp(tmp_path: Path):
    s = Storage(str(tmp_path))
    s.append_measurement({"timestamp":"x","weight":1.0,"unit":"g","stable":True})
    out = s.load_json(s.measure_path, [])
    assert len(out) == 1

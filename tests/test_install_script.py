from __future__ import annotations

from pathlib import Path


def test_install_script_protects_optional_directories() -> None:
    script_path = Path(__file__).resolve().parents[1] / "scripts" / "install-2-app.sh"
    script_text = script_path.read_text(encoding="utf-8")

    required_excludes = {
        "--exclude 'data/***'",
        "--exclude 'local/***'",
        "--exclude 'models/***'",
    }

    found = False
    start = 0
    while True:
        idx = script_text.find("rsync -a --delete", start)
        if idx == -1:
            break

        end = script_text.find("\"${RUNTIME_ROOT}/\"", idx)
        if end != -1 and script_text.find("\"${REPO_ROOT}/\"", idx, end) != -1:
            block = script_text[idx:end]
            missing = sorted(ex for ex in required_excludes if ex not in block)
            assert not missing, f"Faltan exclusiones en rsync: {', '.join(missing)}"
            found = True

        start = idx + 1

    assert found, "No se encontró la sincronización principal hacia ${RUNTIME_ROOT}"

    assert "REPO_ROOT=\"${REPO_ROOT:-$(pwd)}\"" in script_text
    assert "RUNTIME_ROOT=\"/opt/bascula/current\"" in script_text
    assert "echo \"[inst] rsync protected: data local models\"" in script_text

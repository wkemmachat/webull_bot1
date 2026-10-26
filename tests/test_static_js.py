"""Every script of the web app must parse: one syntax error stops a whole page (the sign-in page in Oct 2026)."""
import re
import shutil
import subprocess
from pathlib import Path

import pytest

STATIC = Path(__file__).resolve().parent.parent / "app" / "static"
NODE = shutil.which("node")


def _check(code, tmp_path, name):
    f = tmp_path / name
    f.write_text(code)
    r = subprocess.run([NODE, "--check", str(f)], capture_output=True, text=True)
    assert r.returncode == 0, f"{name}: {r.stderr[:400]}"


@pytest.mark.skipif(not NODE, reason="node is not installed")
def test_js_files_parse(tmp_path):
    files = sorted((STATIC / "js").rglob("*.js"))
    assert files
    for f in files:
        _check(f.read_text(), tmp_path, f.name)


@pytest.mark.skipif(not NODE, reason="node is not installed")
def test_inline_scripts_parse(tmp_path):
    for page in ("index.html", "login.html"):
        for i, code in enumerate(re.findall(r"<script>(.*?)</script>", (STATIC / page).read_text(), re.S)):
            _check(code, tmp_path, f"{page}.{i}.js")

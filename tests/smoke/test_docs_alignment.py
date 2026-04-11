import subprocess
import sys


def test_docs_alignment_script_passes() -> None:
    result = subprocess.run(
        [sys.executable, "scripts/quality/check_docs_alignment.py"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr

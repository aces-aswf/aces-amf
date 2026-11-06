# SPDX-License-Identifier: Apache-2.0
"""Runs scripts/check_hash_sanity.py as part of the normal test suite.

The script itself is a standalone consumer of aces-amf-lib (no code added to the
library), scanning every .amf in the repo for hash-sanity problems that XSD validation
cannot catch — see the script's module docstring for the full rationale. This wrapper
just lets `uv run pytest` exercise it locally alongside everything else, instead of
requiring a separate invocation.
"""

from __future__ import annotations

import runpy
import sys
from pathlib import Path

import pytest

SCRIPT_PATH = Path(__file__).resolve().parents[3] / "scripts" / "check_hash_sanity.py"


def test_hash_sanity_across_repo(capsys):
    assert SCRIPT_PATH.is_file(), f"expected {SCRIPT_PATH} to exist"

    argv = sys.argv
    sys.argv = [str(SCRIPT_PATH)]
    try:
        with pytest.raises(SystemExit) as excinfo:
            runpy.run_path(str(SCRIPT_PATH), run_name="__main__")
    finally:
        sys.argv = argv

    output = capsys.readouterr().out
    assert excinfo.value.code == 0, f"hash sanity check failed:\n{output}"

# SPDX-License-Identifier: Apache-2.0
"""
Test fixtures shipped as package data.

Provides access to sample AMF files for use in tests across all packages.

Usage:
    from aswf.aces.amf_lib.fixtures import get_amf_examples_path

    examples_dir = get_amf_examples_path()
    example1 = examples_dir / "example1.amf"
"""

import importlib.resources
from importlib import resources
from pathlib import Path


_fixtures_dir = importlib.resources.files("aswf.aces.amf_lib") / "fixtures"


def get_amf_examples_path() -> Path:
    """Get the path to the bundled AMF example files directory.

    Returns a context-managed path that works whether the package is
    installed as a directory or a zip/wheel.

    Returns:
        Path to the amf-examples directory.
    """
    ref = _fixtures_dir / "amf-examples"
    # For packages installed on disk, joinpath returns a usable Path directly.
    # For zipped packages, as_file() is needed.
    if hasattr(ref, '__fspath__') or isinstance(ref, Path):
        return Path(ref)
    # Fallback for traversable resources
    with resources.as_file(ref) as p:
        return p


def list_amf_examples() -> list[str]:
    """List the available example AMF files.

    Returns:
        List of example filenames (e.g., ['example1.amf', 'exampleMinimum.amf', ...])
    """
    examples_dir = get_amf_examples_path()
    return sorted(f.name for f in examples_dir.iterdir() if f.suffix == ".amf")

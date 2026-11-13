# SPDX-License-Identifier: Apache-2.0
"""
Test fixtures shipped as package data.

Provides access to sample AMF files for use in tests across all packages.

Usage:
    from aswf.aces.amf_lib.fixtures import get_amf_examples_path

    examples_dir = get_amf_examples_path()
    example1 = examples_dir / "example1.amf"

Note on repo-root examples/: this directory (fixtures/amf-examples/) is the single
source of truth for the sample AMF/CLF content. setuptools' package-data globs can
only see files inside the package's own src/ tree, so this is also the only copy that
ships in the sdist/wheel and is reachable via get_amf_examples_path() by a pip-installed
consumer with no git checkout.

The repo-root examples/*.amf and examples/showLook.clf are symlinks into this
directory, not separate copies - they exist so humans browsing the repo, CI
(validate-xml.yml), and integration tests have a conventional examples/ path to point
at, without maintaining two copies that can silently drift out of sync (as they
previously did: both a stale systemVersion and a hex/base64 hash bug went unnoticed for
years because the two trees were never compared). Edit files here; examples/ follows
automatically. `uv build` dereferences the symlinks into normal files in the sdist and
wheel, so this has no effect on what ships.
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

#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Scan every ``.amf`` in this repository for hash-sanity problems that XSD validation
cannot catch, because ``<aces:hash>`` is a bare ``base64Binary`` with no length/pattern
constraint: a hex-encoded digest, or one otherwise too short or too long for its
declared algorithm, is lexically indistinguishable from valid base64. See
``aces-amf-lib``'s ``validation/hash_encoding.py`` for the underlying detector.

This is a standalone consumer of the published ``aces-amf-lib`` API — it adds no code
to any deployed package. It exists to catch the class of bug found in
``examples/example{2,3,4,5,6}.amf``: hashes attached to ``transformId``-only
transforms (meaningless — there is no file to hash), some of them hex-encoded, some of
them the wrong digest size for their declared algorithm, none of it caught by
``xmllint --schema`` or by ``FileHashValidator`` (which silently skips any transform
with no ``file``).

For every ``<aces:hash>`` found anywhere in the repo, checks:

  1. The value is correctly-sized base64 for its declared algorithm (sha256 -> 32
     bytes, sha1 -> 20 bytes, md5 -> 16 bytes). Rejects hex and any other wrong-size
     encoding, which XSD validation cannot.
  2. The hash's transform also has an ``<aces:file>`` — a hash with no file to verify
     against is meaningless.
  3. Where the file exists on disk (relative to the AMF), the hash matches it.

A small set of test fixtures deliberately violate one of these on purpose (documented
inline below in ``ALLOWLIST`` and ``EXPECTED_MISMATCH_DIRS``); those are reported as
informational, not failures.

Usage:
    uv run python scripts/check_hash_sanity.py [--root PATH]

Exit code is non-zero if any unclassified problem is found.
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
LIB_SRC = REPO_ROOT / "packages" / "aces-amf-lib" / "src"
if str(LIB_SRC) not in sys.path:
    sys.path.insert(0, str(LIB_SRC))

from aswf.aces.amf_lib.amf_helpers import load_amf  # noqa: E402
from aswf.aces.amf_lib.validation.core_validators.file_hashes import (  # noqa: E402
    HASH_ALGO_MAP,
    collect_transforms_with_hashes,
    compute_file_hash,
)
from aswf.aces.amf_lib.validation.hash_encoding import (  # noqa: E402
    ENCODING_HEX,
    ENCODING_UNKNOWN,
    digest_size_for,
)

# Directories to skip outright: virtualenvs, build output, VCS metadata.
SKIP_DIR_NAMES = {".git", "build", "__pycache__", ".venv", "sync"}

# Files with a known, deliberate reason to fail one of the three checks. Each entry
# documents *why* so the allowlist doesn't quietly grow without justification.
#
# tests/data/test_ASC_SOP_no_cdlworkingSpace.amf: two correctly-sized hex md5 hashes,
# attached to <aces:file> elements that don't physically exist in tests/data/. This
# fixture exists to test ASC SOP/SAT parsing, not hash verification or the hex/base64
# path; both the encoding and the missing backing file are intentional.
ALLOWLIST: dict[str, set[str]] = {
    "packages/aces-amf-lib/tests/data/test_ASC_SOP_no_cdlworkingSpace.amf": {
        "encoding",
        "missing_file",
    },
}

# Directories where an otherwise-correctly-formed hash may deliberately fail to match
# its file's actual content — these are HASH_MISMATCH fixtures, not encoding bugs.
EXPECTED_MISMATCH_DIRS = {
    "packages/aces-amf-lib/tests/Generated_Samples_AMF/invalid_AMFs",
}


@dataclass
class Problem:
    path: Path
    label: str
    kind: str  # "encoding" | "unattached" | "missing_file" | "mismatch"
    detail: str
    informational: bool = False


def relpath(p: Path) -> str:
    try:
        return str(p.relative_to(REPO_ROOT))
    except ValueError:
        return str(p)


def find_amf_files(root: Path) -> list[Path]:
    found = []
    for p in root.rglob("*.amf"):
        if any(part in SKIP_DIR_NAMES for part in p.relative_to(root).parts):
            continue
        found.append(p)
    return sorted(found)


def check_file(path: Path) -> list[Problem]:
    problems: list[Problem] = []
    rel = relpath(path)
    allowed = ALLOWLIST.get(rel, set())
    expect_mismatch = any(rel.startswith(d) for d in EXPECTED_MISMATCH_DIRS)

    try:
        amf_obj = load_amf(path, validate=False)
    except Exception as e:  # noqa: BLE001 - report and continue scanning other files
        # Some Generated_Samples_AMF/invalid_AMFs fixtures are deliberately malformed
        # to exercise *other* validators (missing systemVersion, duplicate elements,
        # etc.) and fail to load at all. That's out of scope for a hash-sanity check;
        # report it informationally rather than as a hash failure.
        problems.append(Problem(path, "(file)", "load_error", str(e), informational=True))
        return problems

    for label, transform in collect_transforms_with_hashes(amf_obj):
        hash_obj = transform.hash
        if hash_obj is None:
            continue

        digest_size = digest_size_for(hash_obj.algorithm)
        encoding = getattr(hash_obj, "_source_encoding", None)
        file_ref = getattr(transform, "file", None)

        # 1. Encoding / size sanity. `_normalize_hashes` already ran during load and
        #    tagged the source encoding; hex or wrong-size both surface as non-"base64".
        if digest_size is not None and encoding not in (None, "base64"):
            tag = "hex-encoded" if encoding == ENCODING_HEX else "wrong size for its algorithm"
            problem = Problem(
                path, label, "encoding", f"hash is {tag} (encoding={encoding})",
                informational="encoding" in allowed,
            )
            problems.append(problem)

        # 2. A hash with nothing to verify against is meaningless.
        if not file_ref:
            problems.append(
                Problem(
                    path, label, "unattached", "hash is present but transform has no <aces:file>",
                    informational="unattached" in allowed,
                )
            )
            continue

        # 3. If the file exists, the digest must match it.
        algo_name = HASH_ALGO_MAP.get(
            hash_obj.algorithm.value if hasattr(hash_obj.algorithm, "value") else str(hash_obj.algorithm)
        )
        if algo_name is None or encoding == ENCODING_UNKNOWN:
            continue  # unsupported algorithm or undecodable value; already flagged above

        resolved = path.parent / file_ref
        if not resolved.is_file():
            problems.append(
                Problem(
                    path, label, "missing_file", f"references {file_ref!r}, not found at {resolved}",
                    informational="missing_file" in allowed,
                )
            )
            continue

        actual = compute_file_hash(resolved, algo_name)
        if actual != hash_obj.value:
            problems.append(
                Problem(
                    path, label, "mismatch",
                    f"hash does not match {file_ref!r} (expected {hash_obj.value.hex()}, got {actual.hex()})",
                    informational=expect_mismatch,
                )
            )

    return problems


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=REPO_ROOT, help="Repo root to scan (default: this repo)")
    args = parser.parse_args()

    amf_files = find_amf_files(args.root)
    all_problems: list[Problem] = []
    for path in amf_files:
        all_problems.extend(check_file(path))

    failures = [p for p in all_problems if not p.informational]
    informational = [p for p in all_problems if p.informational]

    print(f"Scanned {len(amf_files)} .amf file(s) under {relpath(args.root)}.")

    if informational:
        print(f"\n{len(informational)} expected/allowlisted issue(s):")
        for p in informational:
            print(f"  [ok] {relpath(p.path)}: {p.label}: {p.detail}")

    if failures:
        print(f"\n{len(failures)} FAILURE(S):")
        for p in failures:
            print(f"  [FAIL] {relpath(p.path)}: {p.label}: {p.detail}")
        print()
        return 1

    print("\nNo hash-sanity problems found.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

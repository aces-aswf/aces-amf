# SPDX-License-Identifier: Apache-2.0
# Copyright Contributors to the ACES Project.
"""Version string resolution for ACES system version keys.

Short version strings resolve to the latest matching release:
- "v1.3" → "v1.3.1" (latest patch in v1.3.x)
- "v2.0" or "v2.0.0" → "v2.0.0+2026.01.15" (latest build of v2.0.0)
- "v1.0" → "v1.0.3" (latest patch in v1.0.x)

Exact keys (including build date suffix) pin to that specific release:
- "v2.0.0+2025.04.04" → "v2.0.0+2025.04.04" (exact match)
"""

from __future__ import annotations

import re

# Matches version strings like "v2.0.0+2025.04.04", "v1.3.1", "v1.0"
_VERSION_RE = re.compile(
    r"^v?(?P<major>\d+)\.(?P<minor>\d+)(?:\.(?P<patch>\d+))?(?:\+(?P<build>.+))?$"
)


def _parse_version(version: str) -> tuple[int, int, int, str] | None:
    """Parse a version string into (major, minor, patch, build) components.

    Returns None if the string doesn't match the expected format.
    Patch defaults to -1 for two-component versions like "v1.3".
    Build defaults to "" if no +suffix present.
    """
    m = _VERSION_RE.match(version)
    if not m:
        return None
    major = int(m.group("major"))
    minor = int(m.group("minor"))
    patch_str = m.group("patch")
    patch = int(patch_str) if patch_str is not None else -1
    build = m.group("build") or ""
    return (major, minor, patch, build)


def _sort_key(parsed: tuple[int, int, int, str]) -> tuple[int, int, int, str]:
    """Sort key for version tuples: higher patch first, then later build date."""
    return (parsed[0], parsed[1], parsed[2], parsed[3])


def resolve_version_key(requested: str, available_keys: list[str]) -> str | None:
    """Resolve a version string to the latest matching available key.

    Short versions resolve to the latest matching release. Exact keys
    (including build suffix) resolve to that specific release.

    Examples:
        "v1.3"              → "v1.3.1"           (latest v1.3.x patch)
        "v1.0"              → "v1.0.3"           (latest v1.0.x patch)
        "v2.0.0"            → "v2.0.0+2026.01.15" (latest v2.0.0 build)
        "v2.0.0+2025.04.04" → "v2.0.0+2025.04.04" (exact pin)

    Returns the matching key, or None if no match found.
    """
    # Normalize: ensure "v" prefix
    normalized = requested if requested.startswith("v") else f"v{requested}"

    # 1. Exact match (pins to a specific release, including build suffix)
    if normalized in available_keys:
        parsed = _parse_version(normalized)
        # If the key has a build suffix, it's an exact pin — return immediately
        if parsed and parsed[3]:
            return normalized
        # Otherwise fall through to find latest matching

    # 2. Parse the requested version
    parsed = _parse_version(normalized)
    if parsed is None:
        return None
    req_major, req_minor, req_patch, _req_build = parsed

    # 3. Find all matching candidates
    candidates: list[tuple[str, tuple[int, int, int, str]]] = []
    for key in available_keys:
        key_parsed = _parse_version(key)
        if key_parsed is None:
            continue

        k_major, k_minor, k_patch, _k_build = key_parsed

        if k_major != req_major or k_minor != req_minor:
            continue

        # If patch was specified, only match that patch
        if req_patch >= 0 and k_patch >= 0 and k_patch != req_patch:
            continue

        candidates.append((key, key_parsed))

    if not candidates:
        return None

    # 4. Return the latest: highest patch, then latest build date
    candidates.sort(key=lambda x: _sort_key(x[1]), reverse=True)
    return candidates[0][0]

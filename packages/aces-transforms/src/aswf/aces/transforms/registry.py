# SPDX-License-Identifier: Apache-2.0
# Copyright Contributors to the ACES Project.
"""
ACES Transform Registry.

Provides lookup and listing of known ACES transform URNs from a bundled
snapshot of the official ACES transforms registry.
"""

from __future__ import annotations

import importlib.resources
import json
import logging

from aswf.aces.common.types import TransformInfo

from ._version_resolver import resolve_version_key

logger = logging.getLogger(__name__)

_data_dir = importlib.resources.files("aswf.aces.transforms") / "data"


class ACESTransformRegistry:
    """Registry of official ACES transforms.

    Loads transform data from a bundled JSON snapshot of the official
    ACES transforms registry. Updates to the transform data require
    a new package release.
    """

    def __init__(self) -> None:
        self._data: dict | None = None
        # Flat index: transform_id → TransformInfo (first version loaded wins)
        self._index: dict[str, TransformInfo] = {}
        # Per-version index: version_key → {transform_id → TransformInfo}
        self._version_index: dict[str, dict[str, TransformInfo]] = {}
        # Previous equivalent ID → current canonical ID
        self._previous_id_map: dict[str, str] = {}

    def _ensure_loaded(self) -> None:
        if self._data is not None:
            return

        data_path = _data_dir / "aces_transforms.json"
        with importlib.resources.as_file(data_path) as path:
            with open(path) as f:
                self._data = json.load(f)

        self._build_index()

    def _build_index(self) -> None:
        for version_key, version_data in self._data.get("transformsData", {}).items():
            version_idx: dict[str, TransformInfo] = {}

            for t in version_data.get("transforms", []):
                tid = t["transformId"]
                info = TransformInfo(
                    transform_id=tid,
                    user_name=t.get("userName", ""),
                    transform_type=t.get("transformType", ""),
                    aces_version=version_key,
                    inverse_transform_id=t.get("inverseTransformId") or None,
                    previous_equivalent_ids=t.get("previousEquivalentTransformIds", []),
                )

                version_idx[tid] = info

                # Flat index: first version loaded wins
                if tid not in self._index:
                    self._index[tid] = info

                # Map previous equivalent IDs to current canonical ID
                for prev_id in info.previous_equivalent_ids:
                    if prev_id not in self._previous_id_map:
                        self._previous_id_map[prev_id] = tid

            self._version_index[version_key] = version_idx

    def _resolve_version(self, version: str) -> str | None:
        """Resolve a version string to an available version key."""
        return resolve_version_key(version, list(self._version_index.keys()))

    def _get_index(self, version: str | None) -> dict[str, TransformInfo]:
        """Return the appropriate index for the given version."""
        self._ensure_loaded()
        if version is None:
            return self._index
        resolved = self._resolve_version(version)
        if resolved is None:
            return {}
        return self._version_index.get(resolved, {})

    # -- Query methods --

    def is_valid_transform_id(self, transform_id: str, *, version: str | None = None) -> bool:
        """Check if a transform ID exists in the registry.

        Also checks previous equivalent transform IDs for backward compatibility.

        Args:
            transform_id: The transform URN to check.
            version: Optional ACES version to scope the query (e.g., "v2.0.0", "v1.3").
        """
        idx = self._get_index(version)
        if transform_id in idx:
            return True
        if version is None:
            return transform_id in self._previous_id_map
        # For version-scoped queries, check if any transform in this version
        # lists the ID as a previous equivalent
        for info in idx.values():
            if transform_id in info.previous_equivalent_ids:
                return True
        return False

    def get_transform_info(self, transform_id: str, *, version: str | None = None) -> dict | None:
        """Get information about a transform by ID.

        Returns a dict with transform metadata, or None if not found.
        Also resolves previous equivalent transform IDs.

        Args:
            transform_id: The transform URN to look up.
            version: Optional ACES version to scope the query.
        """
        idx = self._get_index(version)

        info = idx.get(transform_id)
        if info is None:
            # Check if it's a previous equivalent ID
            if version is None:
                current_id = self._previous_id_map.get(transform_id)
                if current_id:
                    info = self._index.get(current_id)
            else:
                for candidate in idx.values():
                    if transform_id in candidate.previous_equivalent_ids:
                        info = candidate
                        break

        if info is None:
            return None

        return info.to_dict()

    def list_transforms(self, *, category: str | None = None, version: str | None = None) -> list[dict]:
        """List all known transforms, optionally filtered.

        Args:
            category: Filter by transform type (e.g., 'CSC', 'Output', 'IDT').
            version: Optional ACES version to scope the query.
        """
        idx = self._get_index(version)
        results = list(idx.values())
        if category:
            results = [info for info in results if info.transform_type == category]
        return [info.to_dict() for info in results]

    def get_transform_categories(self, *, version: str | None = None) -> list[str]:
        """Get a sorted list of all transform categories/types.

        Args:
            version: Optional ACES version to scope the query.
        """
        idx = self._get_index(version)
        return sorted({info.transform_type for info in idx.values()})

    def are_transforms_inverses(self, id1: str, id2: str, *, version: str | None = None) -> bool:
        """Check if two transform IDs are declared inverses of each other.

        Args:
            id1: First transform URN.
            id2: Second transform URN.
            version: Optional ACES version to scope the query.
        """
        info1 = self.get_transform_info(id1, version=version)
        info2 = self.get_transform_info(id2, version=version)

        if not info1 or not info2:
            return False

        return (
            info1.get("inverse_transform_id") == info2.get("transform_id")
            or info2.get("inverse_transform_id") == info1.get("transform_id")
        )

    # -- Version methods --

    def list_versions(self) -> list[str]:
        """Return the list of available ACES version keys."""
        self._ensure_loaded()
        return list(self._version_index.keys())

    # -- Version equivalence methods --

    def get_equivalent_id(self, transform_id: str) -> str | None:
        """Resolve a transform ID to its canonical equivalent.

        If the ID is a legacy form of a newer transform, returns the
        canonical ID. If the ID is already canonical, returns it as-is.
        Returns None if not found in the registry.
        """
        self._ensure_loaded()
        canonical = self._previous_id_map.get(transform_id)
        if canonical is not None:
            return canonical
        if transform_id in self._index:
            return transform_id
        return None

    def get_equivalent_ids(self, transform_id: str) -> list[str]:
        """Get all equivalent IDs for a transform (legacy and current forms).

        Returns an empty list if the transform is not found or has no equivalents.
        """
        info = self.get_transform_info(transform_id)
        if info is None:
            return []
        return list(info.get("previous_equivalent_ids", []))

    # -- Properties --

    @property
    def transform_count(self) -> int:
        """Total number of unique transforms in the registry (across all versions)."""
        self._ensure_loaded()
        return len(self._index)

    @property
    def schema_version(self) -> str:
        """Schema version of the bundled transforms data."""
        self._ensure_loaded()
        return self._data.get("schemaVersion", "unknown")

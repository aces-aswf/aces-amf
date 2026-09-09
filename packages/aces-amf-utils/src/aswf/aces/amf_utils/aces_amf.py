# SPDX-License-Identifier: Apache-2.0
"""
High-level wrapper for ACES Metadata Files.

Provides a fluent API for loading, inspecting, mutating, and saving AMF files.

Usage:
    from aswf.aces.amf_utils import ACESAMF
    from aswf.aces.amf_lib import amf

    # Load and modify an existing AMF
    amf = ACESAMF.from_file("input.amf")
    amf.with_description("Updated Show").rev_up().write("output.amf")

    # Build a new AMF from scratch
    amf = (ACESAMF.new()
        .with_description("My Show - Ep 1")
        .with_author(amf.AuthorType(name="Jane Doe", email_address="jane@example.com"))
        .with_input_transform(amf.InputTransformType(
            transform_id="urn:ampas:aces:transformId:v1.5:IDT.ARRI.ARRI-LogC4.a1.v1",
            applied=False))
        .with_look_transform(amf.LookTransformType(file="grade.clf", applied=True))
        .with_output_transform(amf.OutputTransformType(
            transform_id="urn:ampas:aces:transformId:v1.5:RRTODT...",
            applied=False)))
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from typing import Self

from aswf.aces.amf_lib import (
    AcesMetadataFile,
    DEFAULT_HASH_ALGORITHM,
    amf,
    compute_file_hash,
    load_amf,
    load_amf_data,
    render_amf,
    save_amf,
)
from aswf.aces.amf_utils.factories import minimal_amf, prepare_for_write

from aswf.aces.amf_utils.builder import _AMFMutatorMixin


def _default_registry():
    """Return a default ACESTransformRegistry instance."""
    from aswf.aces.transforms import ACESTransformRegistry
    return ACESTransformRegistry()


class ACESAMF(_AMFMutatorMixin):
    """High-level wrapper around an ``AcesMetadataFile``.

    Inherits property access and fluent mutation methods from ``_AMFMutatorMixin``.
    Adds I/O, construction helpers, and derived read-only properties.
    """

    def __init__(self, amf_obj: AcesMetadataFile, registry=None):
        self._amf = amf_obj
        self._registry = registry

    @property
    def amf(self) -> AcesMetadataFile:
        """Direct model access for interop with lib functions."""
        return self._amf

    # ------------------------------------------------------------------
    # Construction / I/O
    # ------------------------------------------------------------------

    @classmethod
    def new(cls, aces_version: tuple[int, int, int] = (1, 3, 0), *, registry=None) -> ACESAMF:
        """Create a new minimal AMF.

        Args:
            aces_version: ACES system version tuple (major, minor, patch).
            registry: TransformRegistry for validation. Defaults to ACESTransformRegistry.
        """
        return cls(minimal_amf(aces_version=aces_version), registry=registry)

    @classmethod
    def from_file(cls, path: Path | str, *, validate: bool = True, registry=None) -> ACESAMF:
        """Load an AMF from a file path.

        Automatically upgrades v1 AMFs to v2.

        Args:
            path: Path to the AMF file.
            validate: Run semantic validation after loading.
            registry: TransformRegistry for validation. Defaults to ACESTransformRegistry.
        """
        effective_registry = registry or _default_registry()
        return cls(load_amf(path, validate=validate, transform_registry=effective_registry), registry=effective_registry)

    @classmethod
    def from_data(cls, data: bytes, *, validate: bool = True, registry=None) -> ACESAMF:
        """Load an AMF from raw bytes.

        Automatically upgrades v1 AMFs to v2.

        Args:
            data: Raw AMF XML bytes.
            validate: Run semantic validation after loading.
            registry: TransformRegistry for validation. Defaults to ACESTransformRegistry.
        """
        effective_registry = registry or _default_registry()
        return cls(load_amf_data(data, validate=validate, transform_registry=effective_registry), registry=effective_registry)

    def write(self, path: Path | str, *, validate: bool = True, registry=None) -> None:
        """Write the AMF to a file.

        Args:
            path: Destination file path.
            validate: Run semantic validation before writing.
            registry: TransformRegistry override for this write. Falls back to instance registry.
        """
        effective_registry = registry or self._registry or _default_registry()
        save_amf(self._amf, path, validate=validate, transform_registry=effective_registry)

    def dump(self, *, validate: bool = True, registry=None) -> str:
        """Serialize the AMF to an XML string.

        Args:
            validate: Run semantic validation before serializing.
            registry: TransformRegistry override for this call. Falls back to instance registry.
        """
        effective_registry = registry or self._registry or _default_registry()
        return render_amf(self._amf, validate=validate, transform_registry=effective_registry)

    def rev_up(self) -> Self:
        """Update modification timestamps and UUIDs.

        Should be called before writing after making changes.
        """
        prepare_for_write(self._amf)
        return self

    def compute_file_hashes(
        self,
        base_path: Path | str | None = None,
        algorithm: str = DEFAULT_HASH_ALGORITHM,
    ) -> dict[str, bytes]:
        """Compute and set file hashes on all transforms with file references.

        Walks all transforms in the active pipeline and sets ``hash.algorithm``
        and ``hash.value`` for each transform that has a ``file`` reference
        pointing to an existing file.

        Args:
            base_path: Base directory to resolve relative file paths against.
                Defaults to current working directory.
            algorithm: AMF hash algorithm URI. Defaults to SHA-256.

        Returns:
            Dict mapping file reference strings to their computed hash bytes.
            Only includes files that were successfully hashed.

        Raises:
            ValueError: If the algorithm URI is not supported.
        """
        from aswf.aces.amf_lib.validation import (
            HASH_ALGO_MAP,
            collect_transforms_with_hashes,
        )

        if algorithm not in HASH_ALGO_MAP:
            raise ValueError(f"Unsupported hash algorithm: {algorithm}")

        base = Path(base_path) if base_path is not None else Path.cwd()
        results: dict[str, bytes] = {}

        for _, transform in collect_transforms_with_hashes(self._amf):
            file_ref = getattr(transform, "file", None)
            if not file_ref:
                continue
            resolved = base / file_ref
            if not resolved.is_file():
                continue
            digest = compute_file_hash(resolved, HASH_ALGO_MAP[algorithm])
            transform.hash = amf.HashType(
                value=digest,
                algorithm=amf.HashAlgoType(algorithm),
            )
            results[file_ref] = digest

        return results

    # ------------------------------------------------------------------
    # Derived read-only properties (ACESAMF-specific)
    # ------------------------------------------------------------------

    @property
    def aces_version(self) -> tuple[int, int, int] | None:
        """ACES system version as a (major, minor, patch) tuple."""
        sv = self._amf.pipeline.pipeline_info.system_version
        if sv is None:
            return None
        try:
            return (int(sv.major_version), int(sv.minor_version), int(sv.patch_version))
        except (TypeError, ValueError):
            return None

    @property
    def aces_major_version(self) -> int | None:
        """Major version of the ACES system, or None if not set."""
        v = self.aces_version
        return v[0] if v is not None else None

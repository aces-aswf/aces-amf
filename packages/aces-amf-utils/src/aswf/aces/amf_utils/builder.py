# SPDX-License-Identifier: Apache-2.0
"""
Fluent builder for constructing AMF files.

Usage:
    from aswf.aces.amf_utils import AMFBuilder
    from aswf.aces.amf_lib import amf

    amf = (AMFBuilder()
        .with_description("My Show - Ep 1")
        .with_author(amf.AuthorType(name="Jane Doe", email_address="jane@example.com"))
        .with_input_transform(amf.InputTransformType(
            transform_id="urn:ampas:aces:transformId:v1.5:IDT.ARRI.ARRI-LogC4.a1.v1",
            applied=False))
        .with_look_transform(amf.LookTransformType(file="grade.clf", applied=True))
        .with_output_transform(amf.OutputTransformType(
            transform_id="urn:ampas:aces:transformId:v1.5:RRTODT.Academy.Rec709_100nits_dim.a1.0.3",
            applied=False))
        .build())
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Iterator

if TYPE_CHECKING:
    from typing import Self

from aswf.aces.amf_lib import AcesMetadataFile, amf, get_working_location_index
from aswf.aces.amf_utils.factories import minimal_amf


class _AMFMutatorMixin:
    """Shared property access and fluent mutation methods for AMFBuilder and ACESAMF.

    Provides:
    - **Properties** for Pythonic get/set of AMF fields using pre-built Pydantic types.
    - **``with_X()`` methods** that wrap property setters and return ``self`` for chaining.
    - **Look stack management** for ordered look transform manipulation.

    Subclasses must set ``self._amf`` (an ``AcesMetadataFile``) before use.
    """

    _amf: AcesMetadataFile

    # ------------------------------------------------------------------
    # Properties — get/set
    # ------------------------------------------------------------------

    @property
    def description(self) -> str | None:
        """Top-level AMF description."""
        return self._amf.amf_info.description

    @description.setter
    def description(self, value: str | None) -> None:
        self._amf.amf_info.description = value

    @property
    def pipeline_description(self) -> str | None:
        """Pipeline description."""
        pi = self._amf.pipeline.pipeline_info
        return pi.description if pi else None

    @pipeline_description.setter
    def pipeline_description(self, value: str | None) -> None:
        self._amf.pipeline.pipeline_info.description = value

    @property
    def input_transform(self) -> amf.InputTransformType | None:
        """The pipeline's input transform, or None."""
        return self._amf.pipeline.input_transform

    @input_transform.setter
    def input_transform(self, value: amf.InputTransformType | None) -> None:
        if value is not None:
            from aswf.aces.amf_utils.placement import validate_input_transform_placement

            validate_input_transform_placement(value)
        self._amf.pipeline.input_transform = value

    @property
    def output_transform(self) -> amf.OutputTransformType | None:
        """The pipeline's output transform, or None."""
        return self._amf.pipeline.output_transform

    @output_transform.setter
    def output_transform(self, value: amf.OutputTransformType | None) -> None:
        if value is not None:
            from aswf.aces.amf_utils.placement import validate_output_transform_placement

            validate_output_transform_placement(value)
        self._amf.pipeline.output_transform = value

    @property
    def clip_id(self) -> amf.ClipIdType | None:
        """Clip identification."""
        return self._amf.clip_id

    @clip_id.setter
    def clip_id(self, value: amf.ClipIdType | None) -> None:
        self._amf.clip_id = value

    @property
    def aces_system_version(self) -> amf.VersionType | None:
        """ACES system version."""
        return self._amf.pipeline.pipeline_info.system_version

    @aces_system_version.setter
    def aces_system_version(self, value: amf.VersionType | None) -> None:
        self._amf.pipeline.pipeline_info.system_version = value

    # ------------------------------------------------------------------
    # Properties — read-only
    # ------------------------------------------------------------------

    @property
    def clip_name(self) -> str | None:
        """Clip name, or None if no clipId is set."""
        return self._amf.clip_id.clip_name if self._amf.clip_id else None

    @property
    def amf_uuid(self) -> str:
        """Top-level AMF UUID."""
        return self._amf.amf_info.uuid

    @property
    def modification_date_time(self):
        """Last modification timestamp."""
        return self._amf.amf_info.date_time.modification_date_time

    @property
    def creation_date_time(self):
        """Creation timestamp."""
        return self._amf.amf_info.date_time.creation_date_time

    @property
    def authors(self) -> list[amf.AuthorType]:
        """List of AMF authors."""
        return self._amf.amf_info.author

    @property
    def has_working_location(self) -> bool:
        """Whether the pipeline has a working location marker."""
        return get_working_location_index(self._amf.pipeline) is not None

    # ------------------------------------------------------------------
    # Chainable with_X() wrappers
    # ------------------------------------------------------------------

    def with_description(self, text: str) -> Self:
        """Set the top-level AMF description."""
        self.description = text
        return self

    def with_pipeline_description(self, text: str) -> Self:
        """Set the pipeline description."""
        self.pipeline_description = text
        return self

    def with_input_transform(self, value: amf.InputTransformType) -> Self:
        """Set the input transform."""
        self.input_transform = value
        return self

    def with_output_transform(self, value: amf.OutputTransformType) -> Self:
        """Set the output transform."""
        self.output_transform = value
        return self

    def with_look_transform(self, value: amf.LookTransformType) -> Self:
        """Append a look transform to the pipeline."""
        from aswf.aces.amf_utils.placement import validate_look_transform_placement

        validate_look_transform_placement(value)
        self._amf.pipeline.working_location_or_look_transform.append(value)
        return self

    def with_working_location(self) -> Self:
        """Insert a working location delimiter.

        Looks added before this call are pre-working-location,
        looks added after are post-working-location.
        """
        self._amf.pipeline.working_location_or_look_transform.append(
            amf.WorkingLocationType()
        )
        return self

    def with_author(self, author: amf.AuthorType) -> Self:
        """Append an author."""
        self._amf.amf_info.author.append(author)
        return self

    def with_clip_id(self, value: amf.ClipIdType) -> Self:
        """Set clip identification."""
        self.clip_id = value
        return self

    def with_aces_system_version(self, value: amf.VersionType) -> Self:
        """Set the ACES system version."""
        self.aces_system_version = value
        return self

    # ------------------------------------------------------------------
    # Look stack management
    # ------------------------------------------------------------------

    def _look_positions(self) -> list[int]:
        """Return compound-list indices of all LookTransformType items."""
        return [
            i
            for i, item in enumerate(
                self._amf.pipeline.working_location_or_look_transform
            )
            if isinstance(item, amf.LookTransformType)
        ]

    def get_looks(self) -> list[amf.LookTransformType]:
        """Return all look transforms (excludes working location markers)."""
        return self._amf.pipeline.look_transforms

    def get_look(self, idx: int) -> amf.LookTransformType:
        """Return the look transform at logical index ``idx``.

        Supports negative indices.

        Args:
            idx: Logical look index.
        """
        return self.get_looks()[idx]

    def count_looks(self) -> int:
        """Return the number of look transforms."""
        return len(self.get_looks())

    def iter_looks(self) -> Iterator[tuple[int, amf.LookTransformType]]:
        """Yield ``(index, look)`` pairs for all look transforms."""
        return enumerate(self.get_looks())

    def insert_look(self, idx: int, lt: amf.LookTransformType) -> Self:
        """Insert a look transform at logical index ``idx``.

        Working location markers are preserved. If ``idx`` is beyond the
        current number of looks, the look is appended.

        Args:
            idx: Logical look index at which to insert.
            lt: The look transform to insert.
        """
        from aswf.aces.amf_utils.placement import validate_look_transform_placement

        validate_look_transform_placement(lt)
        compound = self._amf.pipeline.working_location_or_look_transform
        positions = self._look_positions()
        if idx >= len(positions):
            compound.append(lt)
        else:
            compound.insert(positions[idx], lt)
        return self

    def remove_look(self, idx: int) -> Self:
        """Remove the look transform at logical index ``idx``.

        Working location markers are preserved. Supports negative indices.

        Args:
            idx: Logical look index to remove.
        """
        compound = self._amf.pipeline.working_location_or_look_transform
        positions = self._look_positions()
        del compound[positions[idx]]
        return self

    def move_look(self, from_idx: int, to_idx: int) -> Self:
        """Move a look transform from one logical index to another.

        Indices are evaluated before the move (``to_idx`` is applied after
        the item at ``from_idx`` is removed).

        Args:
            from_idx: Source logical look index.
            to_idx: Destination logical look index.
        """
        lt = self.get_look(from_idx)
        self.remove_look(from_idx)
        self.insert_look(to_idx, lt)
        return self

    def clear_looks(self) -> Self:
        """Remove all look transforms, preserving working location markers."""
        self._amf.pipeline.working_location_or_look_transform = [
            item
            for item in self._amf.pipeline.working_location_or_look_transform
            if not isinstance(item, amf.LookTransformType)
        ]
        return self

    # ------------------------------------------------------------------
    # Pre/post working-location look split
    # ------------------------------------------------------------------

    def get_pre_working_looks(self) -> list[amf.LookTransformType]:
        """Look transforms before the working location marker.
        Returns empty list if no working location exists."""
        compound = self._amf.pipeline.working_location_or_look_transform
        wl_idx = get_working_location_index(self._amf.pipeline)
        if wl_idx is None:
            return []
        return [item for i, item in enumerate(compound)
                if i < wl_idx and isinstance(item, amf.LookTransformType)]

    def get_post_working_looks(self) -> list[amf.LookTransformType]:
        """Look transforms after the working location marker.
        Returns all looks if no working location exists."""
        compound = self._amf.pipeline.working_location_or_look_transform
        wl_idx = get_working_location_index(self._amf.pipeline)
        if wl_idx is None:
            return self.get_looks()
        return [item for i, item in enumerate(compound)
                if i > wl_idx and isinstance(item, amf.LookTransformType)]


class AMFBuilder(_AMFMutatorMixin):
    """Fluent builder for ACES Metadata Files.

    Each ``with_X()`` method returns ``self`` for chaining. Call ``.build()``
    to get the final ``AcesMetadataFile`` instance.
    """

    def __init__(self, aces_version: tuple[int, int, int] = (1, 3, 0)):
        self._amf = minimal_amf(aces_version=aces_version)

    def build(self) -> AcesMetadataFile:
        """Return the constructed AcesMetadataFile instance."""
        return self._amf

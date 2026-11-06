# aswf-aces-transforms

Python package for querying the official [ACES](https://acescentral.com/) transform registry. Provides lookup, validation, and version mapping of ACES transform IDs across all ACES system versions.

This package bundles a snapshot of the official ACES `transforms.json` from the [aces-aswf/aces](https://github.com/aces-aswf/aces) repository.

The bundled snapshot is minified and omits `transformUrl`, which the registry does
not use, to reduce package size. It includes the typo and transform ID fixes from
[`0c78fc5`](https://github.com/aces-aswf/aces/commit/0c78fc58267a25fde4510a76bd9d869d2e55c396).

## Installation

```bash
pip install aswf-aces-transforms
```

## Quick start

```python
from aswf.aces.transforms import ACESTransformRegistry

registry = ACESTransformRegistry()

# Look up a transform
info = registry.get_transform_info(
    "urn:ampas:aces:transformId:v2.0:CSC.Academy.ACES_to_ACEScc.a2.v1"
)
print(info["user_name"])  # "ACES2065-1 to ACEScc"

# List all Output transforms for ACES v2.0
outputs = registry.list_transforms(category="Output", version="v2.0")

# Validate a transform ID
registry.is_valid_transform_id(
    "urn:ampas:aces:transformId:v2.0:CSC.Academy.ACES_to_ACEScc.a2.v1"
)  # True
```

## Version-scoped queries

All query methods accept an optional `version` parameter to scope results to a specific ACES system version. Short version strings resolve to the latest matching release:

```python
# "v1.3" resolves to v1.3.1 (latest patch)
registry.list_transforms(version="v1.3")

# "v2.0.0" resolves to the latest build (e.g., v2.0.0+2025.04.04)
registry.list_transforms(version="v2.0.0")

# Exact pin with build suffix
registry.list_transforms(version="v2.0.0+2025.04.04")

# No version = search across all versions
registry.is_valid_transform_id(
    "urn:ampas:aces:transformId:v2.0:CSC.Arri.LogC4_to_ACES.a2.v1"
)
```

## Version migration

Resolve legacy transform IDs to their canonical equivalent:

```python
# Old v1.x ID -> canonical v2.0 equivalent
registry.get_equivalent_id("ACEScsc.ACES_to_ACEScc.a1.0.3")
# -> "urn:ampas:aces:transformId:v2.0:CSC.Academy.ACES_to_ACEScc.a2.v1"

# What are the equivalent IDs for this transform?
registry.get_equivalent_ids(
    "urn:ampas:aces:transformId:v2.0:CSC.Academy.ACES_to_ACEScc.a2.v1"
)
# -> ["urn:ampas:aces:transformId:v1.5:ACEScsc.Academy.ACES_to_ACEScc.a1.0.3", ...]
```

## API reference

### `ACESTransformRegistry`

| Method | Description |
|--------|-------------|
| `is_valid_transform_id(id, *, version=None)` | Check if a transform ID exists (includes previous equivalent IDs) |
| `get_transform_info(id, *, version=None)` | Get transform metadata as a dict, or `None` |
| `list_transforms(*, category=None, version=None)` | List transforms, optionally filtered by type and version |
| `get_transform_categories(*, version=None)` | Get sorted list of transform types (e.g., CSC, Output, IDT) |
| `are_transforms_inverses(id1, id2, *, version=None)` | Check if two transforms are declared inverses |
| `list_versions()` | List all available ACES version keys |
| `get_equivalent_id(id)` | Resolve a legacy ID to its canonical equivalent |
| `get_equivalent_ids(id)` | Get all equivalent IDs for a transform |
| `transform_count` | Total unique transforms across all versions |
| `schema_version` | Schema version of the bundled data |

### Transform info dict

`get_transform_info()` and `list_transforms()` return dicts with these keys:

```python
{
    "transform_id": "urn:ampas:aces:transformId:v2.0:CSC.Academy.ACES_to_ACEScc.a2.v1",
    "user_name": "ACES2065-1 to ACEScc",
    "transform_type": "CSC",
    "aces_version": "v2.0.0+2025.04.04",
    "inverse_transform_id": "urn:ampas:aces:transformId:v2.0:CSC.Academy.ACEScc_to_ACES.a2.v1",
    "previous_equivalent_ids": [
        "urn:ampas:aces:transformId:v1.5:ACEScsc.Academy.ACES_to_ACEScc.a1.0.3",
        "ACEScsc.ACES_to_ACEScc.a1.0.3",
    ],
}
```

## Updating the bundled registry

For an ACES release or a registry correction:

1. **Review the proposed registry changes**, including transform IDs, inverse
   references, and previous equivalent IDs.

2. **Update the bundled data file** at
   `src/aswf/aces/transforms/data/aces_transforms.json`, preserving its minified format
   and omission of `transformUrl`. Document the origin of any imported changes.

3. **Update affected AMF examples and fixtures** if any transform IDs changed, and
   add regression coverage for corrected lookup or equivalence behavior.

4. **Run the full test suite** from the repository root:
   ```bash
   .venv/bin/python -m pytest packages/*/tests
   ```

5. **For a package release**, bump the version in `pyproject.toml` and
   `src/aswf/aces/transforms/__init__.py`, then release to PyPI. Downstream consumers update with:
   ```bash
   pip install --upgrade aswf-aces-transforms
   ```

The registry reads the JSON data dynamically; registry corrections do not require
changes to the lookup implementation.

## ACES versions currently included

| Version | Transforms | Package Date |
|---------|-----------|--------------|
| v2.0.0 | 164 | 2025.04.04 |
| v1.3.1 | 993 | |
| v1.3 | 975 | |
| v1.2 | 970 | |
| v1.1 | 948 | |
| v1.0.3 | 930 | |
| v1.0.2 | 925 | |
| v1.0.1 | 922 | |
| v1.0 | 916 | |

## License

Apache-2.0. See [LICENSE](../../LICENSE) for details.

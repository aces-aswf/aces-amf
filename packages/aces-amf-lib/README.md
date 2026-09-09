# aswf-aces-amf-lib

Reference Python library for reading, writing, and validating ACES Metadata Files (AMF).

Provides type-safe Pydantic schema bindings, I/O helpers, and a pluggable validation system. For high-level builder and CLI tools, see [aswf-aces-amf-utils](../aces-amf-utils/).

This package currently supports AMF v2 schema only. ACES v1.x transform IDs embedded in AMF v2 documents remain supported, e.g. ACES 1.x pipelines in AMF v2.

## Installation

```bash
pip install aswf-aces-amf-lib
```

## Quick Start

```python
from aswf.aces.amf_lib import load_amf, save_amf, amf, validate_all

# Load an AMF v2 file without registry-backed validation
amf_doc = load_amf("example.amf", validate=False)
print(f"Description: {amf_doc.amf_info.description}")
print(f"Input: {amf_doc.pipeline.input_transform}")

# Modify directly via Pydantic models
amf_doc.amf_info.description = "Updated Show"
amf_doc.pipeline.input_transform = amf.InputTransformType(
    transform_id="urn:ampas:aces:transformId:v1.5:IDT.ARRI.ARRI-LogC4.a1.v1",
    applied=False,
)
save_amf(amf_doc, "output.amf", validate=False)

# Validate (schema + semantic checks)
from aswf.aces.transforms import ACESTransformRegistry

registry = ACESTransformRegistry()
messages = validate_all("output.amf", transform_registry=registry)
for msg in messages:
    print(f"[{msg.level.name}] {msg.message}")
```

## Features

- **Read/Write AMF files** -- Load, modify, and serialize AMF v2 documents
- **XSD schema validation** -- Validate against the bundled AMF v2 XML schema
- **Semantic validation** -- Date logic, UUID uniqueness, CDL value ranges, applied order, metadata completeness, file path security, transform ID verification
- **Pluggable validators** -- Register custom validators via the `aces_amf.validators` entry point
- **Type-safe Pydantic models** -- xsdata-generated Pydantic `BaseModel` bindings for AMF v2
- **Zero network calls** -- Everything works offline with bundled schemas

## I/O Functions

```python
from aswf.aces.amf_lib import load_amf, load_amf_data, save_amf, render_amf

# Load from file or bytes without registry-backed validation
amf_doc = load_amf("file.amf", validate=False)
amf_doc = load_amf_data(xml_bytes, validate=False)

# Save to file or serialize to string
save_amf(amf_doc, "output.amf", validate=False)
xml_string = render_amf(amf_doc, validate=False)
```

These I/O functions default to `validate=True`. When validation is enabled,
pass a registry implementation with `transform_registry=registry`. Pass
`validate=False` to skip explicit XSD and semantic validation. Parsing still
constructs the schema-derived AMF model, so input that cannot be represented by
that model raises `AMFSchemaError` regardless of the `validate` setting.

## Schema Bindings

The `amf` module provides Pydantic models generated from the ACES AMF v2 XSD schema:

```python
from aswf.aces.amf_lib import AcesMetadataFile, amf

# Root document
amf_doc = AcesMetadataFile(...)

# Key types
amf.InputTransformType       # input transform (transform_id, file, applied, ...)
amf.OutputTransformType      # output transform
amf.LookTransformType        # look transforms (file, CDL, transform_id, applied, ...)
amf.AuthorType               # author (name, email_address)
amf.ClipIdType               # clip identification (clip_name, file, uuid, sequence)
amf.VersionType              # system version (major, minor, patch)
amf.WorkingLocationType      # working location marker in compound list
amf.HashType                 # file hash (value, algorithm)
amf.DateTimeType             # creation and modification timestamps
amf.CdlWorkingSpaceType     # CDL working space transforms
amf.AscSop                   # ASC CDL slope/offset/power
amf.AscSat                   # ASC CDL saturation
```

### Compound Field: Working Location + Looks

The pipeline stores look transforms and working location markers in a single interleaved list:

```python
# The compound list preserves ordering between looks and the working location marker
pipeline.working_location_or_look_transform  # list[WorkingLocationType | LookTransformType]

# Convenience property for just the looks (filtered view)
pipeline.look_transforms  # list[LookTransformType]

# Find the working location marker index
from aswf.aces.amf_lib import get_working_location_index
idx = get_working_location_index(pipeline)  # int | None
```

## Validation

### Schema Validation

Validates AMF v2 XML against the bundled XSD schema:

```python
from aswf.aces.amf_lib import validate_schema
messages = validate_schema("file.amf")
```

### Semantic Validation

Runs pluggable validators that check logical correctness:

```python
from aswf.aces.amf_lib import validate_semantic
from aswf.aces.transforms import ACESTransformRegistry

registry = ACESTransformRegistry()
messages = validate_semantic("file.amf", transform_registry=registry)
```

Built-in semantic validators:

| Validator | Checks |
|-----------|--------|
| `temporal` | Creation <= modification, no future timestamps |
| `uuid` | UUIDs exist, URN format valid, no duplicates |
| `cdl` | Slope/offset/power/saturation ranges, identity detection |
| `metadata` | Description, authors, transform descriptions present |
| `applied_order` | Applied transforms follow correct logical order |
| `file_paths` | No path traversal, portable characters |
| `file_references` | Referenced transform and CDL files exist and are valid |
| `hash_encoding` | Hash values use valid, standard encoding |
| `working_space` | At most one working location, CDL transforms have working space |
| `transform_ids` | Transform ID URN format validation |
| `transform_placement` | Transform types appear in permitted pipeline positions |
| `file_hashes` | File hash integrity (SHA256, SHA1, MD5) |
| `transform_id_registry` | Transform IDs exist in provided registry |

### Combined Validation

```python
from aswf.aces.amf_lib import validate_all
from aswf.aces.transforms import ACESTransformRegistry

registry = ACESTransformRegistry()
messages = validate_all("file.amf", transform_registry=registry)
```

### Custom Validators

Register custom validators via the `aces_amf.validators` entry point in your package's `pyproject.toml`:

```toml
[project.entry-points."aces_amf.validators"]
my_validator = "my_package:MyValidator"
```

Validators implement the `AMFValidator` protocol:

```python
from aswf.aces.amf_lib import AMFValidator, AcesMetadataFile, ValidationContext, ValidationMessage

class MyValidator:
    name = "my_validator"

    def validate(self, amf: AcesMetadataFile, context: ValidationContext) -> list[ValidationMessage]:
        ...
```

## Utilities

```python
from aswf.aces.amf_lib import compute_file_hash, DEFAULT_HASH_ALGORITHM

# Compute file hash
digest = compute_file_hash("grade.clf", "sha256")
```

## License

Apache-2.0

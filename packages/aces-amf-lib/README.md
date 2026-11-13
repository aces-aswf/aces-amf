# aswf-aces-amf-lib

Reference Python library for reading, writing, and validating ACES Metadata Files (AMF).

Provides type-safe Pydantic schema bindings, I/O helpers, and a pluggable validation system.

For high-level builder and CLI tools, see [aswf-aces-amf-utils](https://pypi.org/project/aswf-aces-amf-utils/).

This package currently supports AMF v2.0 schema only. The AMF schema version is separate from the ACES system version of a given AMF, e.g. ACES v1.3 system version and transform IDs are supported in AMF v2.0.

## Installation

```bash
pip install aswf-aces-amf-lib
```

This installs the AMF models, I/O helpers, and bundled XSD schemas.

This package requires Python 3.10 or newer.

> **IMPORTANT:** This package includes **schema** validation against the XSD. This checks an AMF is formed correctly, but does not guarantee the transform IDs (URNs) exist in the official ACES transform registry.
>
>**Semantic** validation is also included (such as in `validate_all()` and with `validate=True`), which by default will also check transform IDs (URNs) exist in the ACES transform registry. To enable these checks, install `aswf-aces-transforms` and pass an `ACESTransformRegistry()` instance.
> ```bash
> pip install aswf-aces-amf-lib aswf-aces-transforms
> ```
> Reading and writing without semantic validation, and only XSD schema validation, does not require `aswf-aces-transforms`.
>
> See [Semantic Validation](#semantic-validation) section below.
>
> Alternatively, use [aswf-aces-amf-utils](https://pypi.org/project/aswf-aces-amf-utils/) which installs this library and the registry as dependencies.

## Quick Start

```python
from aswf.aces.amf_lib import load_amf, save_amf, amf, validate_all

# Load an AMF file without explicit validation
amf_doc = load_amf("example.amf", validate=False)
print(f"Description: {amf_doc.amf_info.description}")
print(f"Input: {amf_doc.pipeline.input_transform}")

# Modify directly via Pydantic models
amf_doc.amf_info.description = "Updated Show"
amf_doc.pipeline.input_transform = amf.InputTransformType(
    transform_id="urn:ampas:aces:transformId:v2.0:CSC.Arri.LogC4_to_ACES.a2.v1",
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

- **Read/Write AMF files** -- Load, modify, and serialize AMF documents
- **XSD schema validation** -- Validate against the bundled AMF XML schema
- **Semantic validation** -- Date logic, UUID uniqueness, CDL value ranges, applied order, metadata completeness, file path security, transform ID verification
- **Pluggable validators** -- Register custom validators via the `aces_amf.validators` entry point
- **Type-safe Pydantic models** -- xsdata-generated Pydantic `BaseModel` bindings for AMF
- **Offline operation** -- The AMF XSD schemas are bundled; the library makes no network calls. Transform ID validation uses a registry implementation supplied by the caller.

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

These I/O functions default to `validate=True`. The default semantic validators
include transform ID registry checks, so you must pass a registry implementation with
`transform_registry=registry` when validation is enabled. For example, install
`aswf-aces-transforms` and pass an `ACESTransformRegistry()` instance as the
`transform_registry` argument.
Pass `validate=False` to skip explicit validation. Even with `validate=False`, the file must be readable as an AMF document. Otherwise, parsing raises `AMFSchemaError`.

```python
# Load ACES transform registry
from aswf.aces.transforms import ACESTransformRegistry

# Set registry
registry = ACESTransformRegistry()

# Load AMF with registry-backed validation
amf_doc = load_amf(
    "file.amf",
    validate=True,
    transform_registry=registry,
)

save_amf(
    amf_doc,
    "output.amf",
    validate=True,
    transform_registry=registry,
)
```

## Schema Bindings

The `amf` module provides Pydantic models generated from the AMF XSD schema:

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

Validates AMF XML against the bundled XSD schema:

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
| `file_references` | Referenced transform and CDL files exist and are valid (requires `base_path`) |
| `hash_encoding` | Hash values use valid, standard encoding |
| `working_space` | At most one working location, CDL transforms have working space |
| `transform_ids` | Transform ID URN format validation |
| `transform_placement` | Transform types appear in permitted pipeline positions |
| `file_hashes` | File hash integrity (SHA256, SHA1, MD5; requires `base_path`) |
| `transform_id_registry` | Transform IDs exist in the provided registry (required unless this validator is excluded) |

File reference and hash validators resolve referenced files relative to
`base_path`. It defaults to `None`, in which case those checks are skipped.
Set it to the directory containing the referenced files when calling
`validate_semantic` or `validate_all`:

```python
from pathlib import Path
from aswf.aces.amf_lib import validate_all
from aswf.aces.transforms import ACESTransformRegistry

registry = ACESTransformRegistry()
messages = validate_all(
    "show.amf",
    base_path=Path("/path/to/files"),
    transform_registry=registry,
)
```

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
from aswf.aces.amf_lib import compute_file_hash

# The algorithm argument is a hashlib name, not an AMF algorithm URI.
digest = compute_file_hash("grade.clf", "sha256")
```

## License

Apache-2.0

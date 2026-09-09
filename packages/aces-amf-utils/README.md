# aswf-aces-amf-utils

CLI, builder, and utilities for creating, modifying, validating, and analyzing ACES Metadata Files (AMF).

This package currently supports AMF v2 schema only. ACES v1.x transform IDs embedded in AMF v2 documents remain supported, e.g. ACES 1.x pipelines in AMF v2.

## Installation

```bash
pip install aswf-aces-amf-utils
```

## Quick Start

```python
from aswf.aces.amf_lib import amf
from aswf.aces.amf_utils import ACESAMF, AMFBuilder, cdl_look_transform

# Load and inspect an existing AMF
aces_amf = ACESAMF.from_file("input.amf")
print(aces_amf.description)
print(aces_amf.input_transform)

# Build a new AMF from scratch
amf_doc = (AMFBuilder()
    .with_description("My Show - Ep 1")
    .with_author(amf.AuthorType(name="Jane Doe", email_address="jane@example.com"))
    .with_input_transform(amf.InputTransformType(
        transform_id="urn:ampas:aces:transformId:v1.5:IDT.ARRI.ARRI-LogC4.a1.v1",
        applied=False))
    .with_look_transform(cdl_look_transform(slope=(1.2, 1.0, 0.8), saturation=0.95))
    .with_output_transform(amf.OutputTransformType(
        transform_id="urn:ampas:aces:transformId:v1.5:ODT.Academy.Rec709_100nits_dim.a1.0.3",
        applied=False))
    .build())
```

## API Design

The API follows a property-based pattern with chainable builder wrappers:

- **Properties** for Pythonic get/set using pre-built Pydantic types from `aswf.aces.amf_lib.amf`
- **`with_X()` methods** that wrap property setters and return `self` for fluent chaining
- **Factory functions** for complex type construction (e.g., CDL look transforms)

```python
# Property access — direct get and set
aces_amf = ACESAMF.from_file("shot.amf")
it = aces_amf.input_transform                                  # get
aces_amf.input_transform = amf.InputTransformType(             # set
    transform_id="urn:...", applied=False)

# Builder chaining — via with_X() wrappers
aces_amf = (ACESAMF.new()
    .with_input_transform(amf.InputTransformType(transform_id="urn:...", applied=False))
    .with_look_transform(amf.LookTransformType(file="grade.clf", applied=True))
    .with_output_transform(amf.OutputTransformType(transform_id="urn:...", applied=False)))
```

## ACESAMF — High-Level Wrapper

`ACESAMF` wraps an `AcesMetadataFile` with convenient I/O and mutation methods.

### Construction

```python
# Create a new minimal AMF
amf = ACESAMF.new(aces_version=(1, 3, 0))

# Load an AMF v2 file
amf = ACESAMF.from_file("input.amf", validate=True)

# Load from raw bytes
amf = ACESAMF.from_data(xml_bytes, validate=True)
```

### I/O

```python
amf.write("output.amf", validate=True)   # write to file
xml = amf.dump(validate=True)             # serialize to XML string
amf.rev_up()                              # update timestamps and UUIDs before saving
```

### Properties (get/set)

All properties accept and return pre-built Pydantic types:

| Property | Type | Description |
|----------|------|-------------|
| `description` | `str \| None` | Top-level AMF description |
| `pipeline_description` | `str \| None` | Pipeline description |
| `input_transform` | `InputTransformType \| None` | Pipeline input transform |
| `output_transform` | `OutputTransformType \| None` | Pipeline output transform |
| `clip_id` | `ClipIdType \| None` | Clip identification |
| `aces_system_version` | `VersionType \| None` | ACES system version object |

### Read-Only Properties

| Property | Type | Description |
|----------|------|-------------|
| `clip_name` | `str \| None` | Extracted from clipId |
| `amf_uuid` | `str` | Top-level AMF UUID |
| `authors` | `list[AuthorType]` | Author list |
| `modification_date_time` | `XmlDateTime` | Last modified timestamp |
| `creation_date_time` | `XmlDateTime` | Creation timestamp |
| `has_working_location` | `bool` | Whether pipeline has a working location marker |
| `aces_version` | `tuple[int,int,int] \| None` | ACES version as tuple (ACESAMF only) |
| `aces_major_version` | `int \| None` | Major version number (ACESAMF only) |

### Chainable `with_X()` Methods

All return `self` for fluent chaining:

| Method | Accepts |
|--------|---------|
| `with_description(text)` | `str` |
| `with_pipeline_description(text)` | `str` |
| `with_input_transform(value)` | `InputTransformType` |
| `with_output_transform(value)` | `OutputTransformType` |
| `with_look_transform(value)` | `LookTransformType` |
| `with_working_location()` | _(no args — inserts delimiter)_ |
| `with_author(author)` | `AuthorType` |
| `with_clip_id(value)` | `ClipIdType` |
| `with_aces_system_version(value)` | `VersionType` |

## AMFBuilder — Fluent Construction

`AMFBuilder` provides the same properties and `with_X()` methods as `ACESAMF`, plus a `build()` method to extract the final `AcesMetadataFile`:

```python
from aswf.aces.amf_lib import amf, save_amf
from aswf.aces.amf_utils import AMFBuilder

amf = (AMFBuilder(aces_version=(2, 0, 0))
    .with_description("DI Grade")
    .with_author(amf.AuthorType(name="Colorist", email_address="color@studio.com"))
    .with_input_transform(amf.InputTransformType(
        transform_id="urn:ampas:aces:transformId:v1.5:IDT.ARRI.ARRI-LogC4.a1.v1",
        applied=False))
    .with_look_transform(amf.LookTransformType(
        file="grade.clf", description="Primary grade", applied=True))
    .with_working_location()
    .with_look_transform(amf.LookTransformType(
        file="trim.clf", description="Trim pass", applied=False))
    .with_output_transform(amf.OutputTransformType(
        transform_id="urn:ampas:aces:transformId:v1.5:ODT.Academy.Rec709_100nits_dim.a1.0.3",
        applied=False))
    .build())

save_amf(amf, "output.amf")
```

## Look Stack Management

Looks are stored in a compound list that can also contain working location markers. Management methods operate on logical look indices (excluding markers):

```python
amf = ACESAMF.from_file("input.amf")

# Read
looks = amf.get_looks()                    # list[LookTransformType]
look = amf.get_look(0)                     # by index (supports negative)
count = amf.count_looks()                  # int
for i, look in amf.iter_looks():           # (index, look) pairs
    print(f"{i}: {look.description}")

# Mutate
amf.insert_look(0, new_look)              # insert at logical index
amf.remove_look(1)                         # remove by logical index
amf.move_look(from_idx=0, to_idx=2)       # reorder
amf.clear_looks()                          # remove all (preserves working location)

# Working location splits
pre = amf.get_pre_working_looks()          # looks before working location
post = amf.get_post_working_looks()        # looks after working location
```

## Factory Functions

For complex type construction:

```python
from aswf.aces.amf_utils import cdl_look_transform, cdl_look_transform_to_dict

# Create a CDL look transform with ACEScct working space
lt = cdl_look_transform(
    slope=(1.2, 1.0, 0.8),
    offset=(0.01, 0.0, -0.01),
    power=(1.0, 1.0, 1.0),
    saturation=0.95,
)
lt.description = "Primary grade"
lt.applied = True

# Extract CDL values back to a dict
cdl_dict = cdl_look_transform_to_dict(lt)
# {"asc_sop": {"slope": [...], "offset": [...], "power": [...]}, "asc_sat": 0.95}
```

## Diff

Compare two AMF files or objects:

```python
from aswf.aces.amf_utils import diff_amf

result = diff_amf("a.amf", "b.amf", verbose=True)
if result.has_differences:
    print(result.summary())
    for d in result.differences:
        print(f"  {d.field}: {d.old_value} -> {d.new_value}")
```

## CLI

The `amf` command provides a full suite of tools:

```bash
# Validate AMF files
amf validate shot.amf
amf validate --schema-only shot.amf
amf validate --verbose *.amf

# Display AMF information
amf info shot.amf
amf info -v shot.amf              # verbose with transform details

# Create a new AMF
amf create output.amf -d "My Show" --author "Jane Doe" \
    --idt "urn:ampas:aces:transformId:v1.5:IDT.ARRI.ARRI-LogC4.a1.v1" \
    --odt "urn:ampas:aces:transformId:v1.5:ODT.Academy.Rec709_100nits_dim.a1.0.3"

# Add a CDL look transform
amf add-cdl shot.amf --slope 1.2 1.0 0.8 --saturation 0.95 -d "Primary grade"

# Compare two AMF files
amf diff a.amf b.amf --verbose

# Query the ACES transform registry
amf transforms list --category IDT
amf transforms info "urn:ampas:aces:transformId:v2.0:CSC.Academy.ACES_to_ACEScc.a2.v1"
amf transforms categories

# File hashes
amf compute-hashes shot.amf

# Template management
amf template list
amf template show <template-id>
amf template search "HDR"
```

## Key Types

All transform and metadata types come from `aswf.aces.amf_lib.amf`:

```python
from aswf.aces.amf_lib.amf import (
    InputTransformType,      # input_transform property type
    OutputTransformType,     # output_transform property type
    LookTransformType,       # look transforms and CDL
    AuthorType,              # author entries
    ClipIdType,              # clip identification
    VersionType,             # ACES system version
    WorkingLocationType,     # working location marker
)
```

## License

Apache-2.0

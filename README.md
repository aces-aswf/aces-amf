<!-- SPDX-License-Identifier: Apache-2.0 -->
<!-- Copyright Contributors to the ACES Project. -->

# ACES Metadata File (AMF)

[![License](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)
![AMF Schema and Example
Validation](https://github.com/aces-aswf/aces-amf/actions/workflows/validate-xml.yml/badge.svg)
![GitHub release (with
filter)](https://img.shields.io/github/v/release/aces-aswf/aces-amf) [![CLA
assistant](https://cla-assistant.io/readme/badge/aces-aswf/aces-amf)](https://cla-assistant.io/aces-aswf/aces-amf)

The ACES Metadata File (AMF) is an XML sidecar format for exchanging the
metadata required to reconstruct ACES viewing pipelines. It specifies the
transforms needed to configure an ACES pipeline for a set of related image
files.

This directory includes:

- The ACES Metadata File XML Schema:
  [acesMetadataFile.xsd](./schema/acesMetadataFile.xsd)

- Copies of dependent XML schemas

- [Example AMF files](./examples/)

For details on the AMF format and its use cases, see the [ACES
Documentation](https://docs.acescentral.com/amf/specification/).

## Python Packages

This repository includes a suite of Python packages for working with AMF files programmatically. The packages are organized as a [uv workspace](https://docs.astral.sh/uv/concepts/workspaces/) monorepo under `packages/`.

### Getting Started

```bash
# Install the high-level CLI and utilities (pulls in all dependencies)
pip install aswf-aces-amf-utils

# Or install individual packages
pip install aswf-aces-amf-lib   # core library only
pip install aswf-aces-transforms # transform registry only
```

### Package Overview

| Package | Description |
|---------|-------------|
| [**aswf-aces-amf-utils**](./packages/aces-amf-utils/) | CLI, builder, and utilities for creating, modifying, and analyzing AMF files |
| [**aswf-aces-amf-lib**](./packages/aces-amf-lib/) | Reference library for reading, writing, and validating AMF files |
| [**aswf-aces-transforms**](./packages/aces-transforms/) | ACES transform ID registry with offline lookup and version mapping |
| [**aswf-aces-common**](./packages/aces-common/) | Shared protocols and types |

### Dependency Graph

```
aswf-aces-common     (shared protocols, zero dependencies)
  |
  +-- aswf-aces-transforms (transform ID registry)
  |
  +-- aswf-aces-amf-lib (AMF I/O, schema bindings, validation)
        |
        +-- aswf-aces-amf-utils (CLI, builder, high-level API)
```

## Getting Started

### Load & Inspect an AMF

```python
from aswf.aces.amf_utils import ACESAMF

amf = ACESAMF.from_file("shot_001.amf", validate=False)
print(amf.description)
print(amf.aces_version)  # (2, 0, 0)

if amf.input_transform:
    print(amf.input_transform.transform_id)
for idx, look in amf.iter_looks():
    print(f"  Look {idx}: {look.description}")
if amf.output_transform:
    print(amf.output_transform.transform_id)
```

### Build a Complete AMF

Demonstrates all `.with_*` methods, including look transforms before and after a working location delimiter.

```python
from aswf.aces.amf_lib import amf
from aswf.aces.amf_utils import ACESAMF
from aswf.aces.amf_utils.factories import cdl_look_transform

# CDL grade with ACEScct working space
primary_grade = cdl_look_transform(
    slope=(1.1, 1.0, 0.9),
    offset=(0.01, 0.0, -0.01),
    saturation=0.95,
)
primary_grade.description = "Primary Grade"
primary_grade.applied = False
primary_grade.cdl_working_space = amf.CdlWorkingSpaceType(
    from_cdl_working_space=amf.WorkingSpaceTransformType(
        transform_id="urn:ampas:aces:transformId:v2.0:CSC.Academy.ACEScct_to_ACES.a2.v1",
    ),
    to_cdl_working_space=amf.WorkingSpaceTransformType(
        transform_id="urn:ampas:aces:transformId:v2.0:CSC.Academy.ACES_to_ACEScct.a2.v1",
    ),
)

# A file-based look (e.g. a show LUT)
show_look = amf.LookTransformType(
    file="show_lut.clf",
    description="Show LUT",
    applied=False,
)

amf = (
    ACESAMF.new(aces_version=(2, 0, 0))
    # Metadata
    .with_description("My Show - Ep 1")
    .with_pipeline_description("Camera to Rec.709 Display")
    .with_author(amf.AuthorType(name="Jane Doe", email_address="jane@example.com"))
    .with_clip_id(amf.ClipIdType(clip_name="A001C003", file="A001C003.ari"))
    # Input (camera to ACES)
    .with_input_transform(amf.InputTransformType(
        transform_id="urn:ampas:aces:transformId:v2.0:CSC.Arri.LogC4_to_ACES.a2.v1",
        description="ARRI LogC4 to ACES",
        applied=False,
    ))
    # Looks BEFORE working location (applied in ACES linear)
    .with_look_transform(primary_grade)
    # Working location delimiter
    .with_working_location()
    # Looks AFTER working location (applied in working color space)
    .with_look_transform(show_look)
    # Output (ACES to display)
    .with_output_transform(amf.OutputTransformType(
        transform_id="urn:ampas:aces:transformId:v2.0:Output.Academy.Rec709-D65_100nit_in_Rec709-D65_BT1886.a2.v1",
        description="Rec.709 100 nits",
        applied=False,
    ))
)

amf.write("output.amf", validate=False)
```

### Load, Modify, and Save

```python
from aswf.aces.amf_lib import amf
from aswf.aces.amf_utils import ACESAMF

aces_amf = ACESAMF.from_file("shot_001.amf", validate=False)
aces_amf.output_transform = amf.OutputTransformType(
    transform_id="urn:ampas:aces:transformId:v2.0:Output.Academy.P3-D65_1000nit_in_P3-D65_ST2084.a2.v1",
    description="P3 HDR 1000 nits",
    applied=False,
)
aces_amf.write("shot_001_hdr.amf", validate=False)
```

### Manage Look Transforms

Insert, remove, and reorder looks in an existing AMF.

```python
from aswf.aces.amf_utils import ACESAMF
from aswf.aces.amf_utils.factories import cdl_look_transform

amf = ACESAMF.from_file("shot_001.amf", validate=False)

# List existing looks
for idx, look in amf.iter_looks():
    print(f"  [{idx}] {look.description}")

# Add a new look at position 0
new_look = cdl_look_transform(slope=(1.2, 1.0, 0.8))
new_look.description = "Show LUT"
new_look.applied = False
amf.insert_look(0, new_look)

# Remove a look by index
amf.remove_look(2)

# Reorder: move look 0 to position 1
amf.move_look(0, 1)

amf.write("reordered.amf", validate=False)
```

### Validate an AMF

```python
from aswf.aces.amf_lib import validate_schema, validate_semantic, validate_all
from aswf.aces.transforms import ACESTransformRegistry

registry = ACESTransformRegistry()

# Schema validation only (XSD)
messages = validate_schema("shot_001.amf")

# Semantic validation (includes transform ID checks)
messages = validate_semantic("shot_001.amf", transform_registry=registry)

# Both at once
messages = validate_all("shot_001.amf", transform_registry=registry)

for m in messages:
    print(f"[{m.level.value}] {m.message}")
```

### Query the Transform Registry

Look up transforms, find equivalents, and check validity.

```python
from aswf.aces.transforms import ACESTransformRegistry

registry = ACESTransformRegistry()

# List available ACES versions
print(registry.list_versions())  # ['v2.0.0+2025.04.04', 'v1.3.1', ...]

# Find transforms by category
for t in registry.list_transforms(category="CSC", version="v2.0")[:5]:
    print(t["transform_id"], "-", t["user_name"])

# Validate a transform ID
registry.is_valid_transform_id(
    "urn:ampas:aces:transformId:v2.0:CSC.Arri.LogC4_to_ACES.a2.v1"
)  # True

# Resolve a legacy URN to its current equivalent
registry.get_equivalent_id(
    "urn:ampas:aces:transformId:v1.5:ACEScsc.Academy.ACES_to_ACEScct.a1.0.3"
)
# -> 'urn:ampas:aces:transformId:v2.0:CSC.Academy.ACES_to_ACEScct.a2.v1'
```

### Compare Two AMFs

```python
from aswf.aces.amf_utils import diff_amf

result = diff_amf("shot_001_v1.amf", "shot_001_v2.amf")
if result.has_differences:
    print(result.summary())
    for d in result.differences:
        print(f"  {d.field}: {d.old_value} -> {d.new_value}")
```

### Parse Transform URNs

```python
from aswf.aces.common import TransformURN

urn = TransformURN.parse(
    "urn:ampas:aces:transformId:v1.5:ACEScsc.Academy.ACES_to_ACEScct.a1.0.3"
)
print(urn.spec_version)    # v1.5
print(urn.transform_type)  # ACEScsc
print(urn.namespace)       # Academy
print(urn.name)            # ACES_to_ACEScct
print(urn.version_suffix)  # a1.0.3
print(urn.is_v1)           # True
```

### CLI Quick Reference

```bash
# Validate AMF files
amf validate shot_001.amf shot_002.amf

# Display AMF info
amf info shot_001.amf

# Create a new AMF
amf create output.amf -d "My Shot" \
  --idt "urn:ampas:aces:transformId:v2.0:CSC.Arri.LogC4_to_ACES.a2.v1" \
  --odt "urn:ampas:aces:transformId:v2.0:Output.Academy.Rec709-D65_100nit_in_Rec709-D65_BT1886.a2.v1"

# Add a CDL grade
amf add-cdl shot_001.amf --slope 1.1 1.0 0.9 --saturation 0.95 -o graded.amf

# Compare two AMFs
amf diff shot_001_v1.amf shot_001_v2.amf

# Query transforms
amf transforms list -c CSC -n 10
amf transforms info "urn:ampas:aces:transformId:v2.0:CSC.Arri.LogC4_to_ACES.a2.v1"

# Fix version-mismatched URNs
amf resolve-urns mixed.amf --auto -o fixed.amf
```

> **Lower-level access:** For direct Pydantic model access, `AMFBuilder(...).build()` returns a raw `AcesMetadataFile`, and `load_amf()` / `save_amf()` from `aswf.aces.amf_lib` provide I/O without the wrapper. See the [aswf-aces-amf-lib README](./packages/aces-amf-lib/) for details.

### Development Setup

```bash
# Clone and set up the workspace
git clone https://github.com/aces-aswf/aces-amf.git
cd aces-amf
uv sync

# Run all tests
uv run pytest
```

Requires Python >= 3.10.

## Contributing

ACES depends on community participation. Developers, manufacturers, and end
users are encouraged to contribute code, bug fixes, documentation, and other
technical artifacts.

All contributors must have a signed Contributor License Agreement (CLA) on file
to ensure that the project can freely use your contributions. 

See [CONTRIBUTING.md](./CONTRIBUTING.md) for more details.

## Governance

This repository is a submodule of the ACES project, which is governed by the
Academy Software Foundation.

For details about how the project operates, refer to the
[GOVERNANCE.md](https://github.com/aces-aswf/aces/blob/main/GOVERNANCE.md) file
found in the top-level ACES repository.

## Reporting Issues

To report a problem with AMF, please open an
[issue](https://github.com/aces-aswf/aces-amf/issues).

If the issue is sensitive in nature or a security related issue, please do not
report in the issue tracker. Instead refer to [SECURITY.md](SECURITY.md) for
more information about the project security policy.

## License

The ACES Project is licensed under the [Apache 2.0 license](./LICENSE).

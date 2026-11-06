# Binding Patches

These patch files are applied to the xsdata-generated Python bindings immediately after generation. Each patch is a standard unified diff and is applied with `patch -p0 --fuzz=2`.

Patches are applied in alphabetical order (see `_apply_patches` in `generate_bindings.sh`).

## Patches

### `compound_fields.patch`
**Target:** `amf/aces_metadata_file.py`

Replaces the two separate `working_location` and `look_transform` fields on `PipelineType` with a single compound field:

```python
working_location_or_look_transform: list[EmptyType | LookTransformType]
```

Also appends the `look_transforms` convenience property and `WorkingLocationType = EmptyType` alias.

**Why the compound field:** The AMF v2 XSD uses `xs:choice maxOccurs="unbounded"` to allow `workingLocation` and `lookTransform` elements to be freely interleaved. xsdata generates these as two separate lists, which destroys element ordering. The compound field (xsdata `"Elements"` type with `"choices"`) preserves the original interleaved document order, which is required for correct workingLocation positional semantics.

### `hash_value_encoding.patch`
**Target:** `amf/aces_metadata_file.py`

Adds a non-serialized `_source_encoding: str | None` `PrivateAttr` to `HashType`. At load time, `amf_helpers._normalize_hashes` records whether a `<hash>` value was read as `"base64"`, `"hex"`, or `"unknown"` (while normalizing `value` to the correct digest bytes). The `hash_encoding` validator reads this to warn on hex (non-standard per the AMF spec) and error on undecodable values. Being a `PrivateAttr`, it is never serialized back to XML.

**Why a patch:** the encoding flag must live on the generated `HashType`, so it has to survive binding regeneration.

### `init_exports.patch`
**Target:** `amf/__init__.py`

Adds `WorkingLocationType` to the module's imports and `__all__` so that consumers can import it from `aswf.aces.amf_lib.amf` directly.

---

## Regenerating Patches

If xsdata, the XSD schemas, or the manually-applied changes evolve, regenerate the patches:

```bash
# 1. Make your edits to the generated files under src/aswf/aces/amf_lib/amf/
# 2. Regenerate patch files from the current committed state
./generate_bindings.sh --gen-patches
# 3. Verify: wipe generated files and regenerate from scratch
rm -rf packages/aces-amf-lib/src/aswf/aces/amf_lib/amf
./generate_bindings.sh
uv run pytest packages/ -q
```

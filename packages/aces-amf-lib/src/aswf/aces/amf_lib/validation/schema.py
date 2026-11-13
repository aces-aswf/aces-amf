# SPDX-License-Identifier: Apache-2.0
"""
XSD schema validation for AMF files.
"""

import importlib.resources
from importlib import resources
from pathlib import Path

from lxml import etree

from .types import ValidationLevel, ValidationMessage, ValidationType

# Location of acesMetadataFile.xsd for each AMF version
_data_dir = importlib.resources.files("aswf.aces.amf_lib") / "data"
AMF_XSD_PATH_MAP = {
    "urn:ampas:aces:amf:v2.0": _data_dir / "amf-schema" / "v2",
}


def validate_schema(amf_path: Path | str) -> list[ValidationMessage]:
    """Validate an AMF file against its XSD schema.

    Args:
        amf_path: Path to the AMF file.

    Returns:
        List of validation messages. Empty list means valid.
    """
    amf_path = Path(amf_path)
    messages: list[ValidationMessage] = []

    # Parse the file to find the AMF version from the XML namespace
    try:
        with open(amf_path, "rb") as xml_file:
            tree = etree.parse(xml_file)
        amf_version_urn = tree.getroot().nsmap["aces"]
    except etree.XMLSyntaxError as e:
        messages.append(
            ValidationMessage(
                ValidationLevel.ERROR, ValidationType.SCHEMA_VIOLATION,
                f"Syntax error in AMF {amf_path}: {e}", amf_path,
            )
        )
        return messages
    except KeyError:
        messages.append(
            ValidationMessage(
                ValidationLevel.ERROR, ValidationType.SCHEMA_VIOLATION,
                f"Missing ACES namespace in AMF {amf_path}", amf_path,
            )
        )
        return messages

    # Find the XSD for the AMF version
    try:
        xsd_resource_path = AMF_XSD_PATH_MAP[amf_version_urn]
    except KeyError:
        messages.append(
            ValidationMessage(
                ValidationLevel.ERROR, ValidationType.SCHEMA_VIOLATION,
                f"Unsupported AMF version in AMF {amf_path}: {amf_version_urn}", amf_path,
            )
        )
        return messages

    # Validate the document against the schema
    try:
        with resources.as_file(xsd_resource_path) as xsd_dir:
            xsd_path = xsd_dir / "acesMetadataFile.xsd"
            xsd_doc = etree.parse(str(xsd_path))
            schema = etree.XMLSchema(xsd_doc)

        parser = etree.XMLParser(schema=schema)
        with open(amf_path, "rb") as xml_file:
            etree.parse(xml_file, parser)
    except etree.XMLSyntaxError as e:
        messages.append(
            ValidationMessage(
                ValidationLevel.ERROR, ValidationType.SCHEMA_VIOLATION,
                f"Syntax error in AMF {amf_path}: {e}", amf_path,
            )
        )
    except etree.XMLSchemaParseError as e:
        messages.append(
            ValidationMessage(
                ValidationLevel.ERROR, ValidationType.SCHEMA_VIOLATION,
                f"Schema error in AMF {amf_path}: {e}", amf_path,
            )
        )
    except Exception as e:
        messages.append(
            ValidationMessage(
                ValidationLevel.ERROR, ValidationType.SCHEMA_VIOLATION,
                f"Unexpected error in AMF {amf_path}: {e}", amf_path,
            )
        )

    return messages

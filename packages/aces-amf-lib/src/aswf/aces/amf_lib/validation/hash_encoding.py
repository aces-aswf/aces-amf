# SPDX-License-Identifier: Apache-2.0
"""Hash value encoding detection and normalization (base64 vs hex).

The AMF XSD types ``<hash>`` as ``base64Binary``, but some producers (e.g. DaVinci
Resolve) emit the digest as a hexadecimal string. A hash hex string is *also*
lexically valid base64 — hex chars are a subset of the base64 alphabet and hash hex
lengths (32/40/64) are multiples of 4 — so xsdata silently base64-decodes it into
wrong-length bytes. Given the algorithm's digest size we can unambiguously tell which
encoding was used (genuine base64 decodes to the digest size; a hex string mis-decodes
to exactly 1.5x) and recover the true digest.
"""

from __future__ import annotations

import base64
import binascii
import hashlib

from aswf.aces.amf_lib.validation.core_validators.file_hashes import HASH_ALGO_MAP

# Encoding tags recorded on HashType._source_encoding.
ENCODING_BASE64 = "base64"
ENCODING_HEX = "hex"
ENCODING_UNKNOWN = "unknown"


def algo_uri(algorithm) -> str | None:
    """Return the URI string for a HashAlgoType enum (or raw value)."""
    if algorithm is None:
        return None
    return algorithm.value if hasattr(algorithm, "value") else str(algorithm)


def digest_size_for(algorithm) -> int | None:
    """Expected digest size in bytes for a hash algorithm, or None if unsupported."""
    name = HASH_ALGO_MAP.get(algo_uri(algorithm))
    if name is None:
        return None
    return hashlib.new(name).digest_size


def classify_and_normalize(value: bytes, digest_size: int) -> tuple[bytes, str]:
    """Classify a parsed hash value's source encoding and normalize it to digest bytes.

    ``value`` is what xsdata produced by base64-decoding the ``<hash>`` text.

    Returns ``(normalized_bytes, encoding_tag)``:
      - genuine base64               -> (value, "base64")  # already correct digest bytes
      - hex (mis-decoded as base64)  -> (digest_bytes, "hex")
      - neither                      -> (value, "unknown")  # left as-is; caller flags invalid
    """
    if len(value) == digest_size:
        return value, ENCODING_BASE64

    # A digest's hex string is 2*digest_size chars, which base64-decodes to
    # 1.5*digest_size bytes; base64-re-encoding losslessly recovers the hex text.
    if len(value) == digest_size * 3 // 2:
        try:
            recovered = base64.b64encode(value).decode("ascii")
            hex_bytes = bytes.fromhex(recovered)
        except (binascii.Error, ValueError):
            return value, ENCODING_UNKNOWN
        if len(hex_bytes) == digest_size:
            return hex_bytes, ENCODING_HEX

    return value, ENCODING_UNKNOWN

"""ULID generation.

Scan ids need to be sortable by creation time, URL-safe, and generated without
coordination. ULID gives us all three in ~20 lines over the standard library, which is a
better trade than a dependency for this.

Layout: 48-bit millisecond timestamp + 80 bits of randomness, encoded with Crockford
base32 into 26 characters.
"""

from __future__ import annotations

import os
import time

_ALPHABET = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"  # Crockford base32: no I, L, O, U
_ENCODED_LENGTH = 26
_TIMESTAMP_BITS = 48
_RANDOM_BITS = 80


def new_ulid(now_ms: int | None = None) -> str:
    """Return a new ULID. ``now_ms`` is injectable so tests can assert ordering."""
    timestamp = time.time_ns() // 1_000_000 if now_ms is None else now_ms
    if not 0 <= timestamp < (1 << _TIMESTAMP_BITS):
        raise ValueError("timestamp out of ULID range")
    randomness = int.from_bytes(os.urandom(_RANDOM_BITS // 8), "big")
    return _encode((timestamp << _RANDOM_BITS) | randomness)


def is_ulid(value: str) -> bool:
    """Cheap shape check used to reject obviously invalid path parameters."""
    return len(value) == _ENCODED_LENGTH and all(char in _ALPHABET for char in value.upper())


def _encode(value: int) -> str:
    chars = [""] * _ENCODED_LENGTH
    for index in range(_ENCODED_LENGTH - 1, -1, -1):
        chars[index] = _ALPHABET[value & 0x1F]
        value >>= 5
    return "".join(chars)

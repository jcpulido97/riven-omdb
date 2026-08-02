"""Torrent utilities for infohash extraction and manipulation."""

import base64
import binascii
import re

from loguru import logger

# Pattern to match infohashes in magnet links (supports both 40-char hex and 32-char base32)
INFOHASH_PATTERN = re.compile(r"btih:([a-fA-F0-9]{40}|[a-zA-Z0-9]{32})", re.IGNORECASE)
HEX_INFOHASH_PATTERN = re.compile(r"(?<![a-fA-F0-9])([a-fA-F0-9]{40})(?![a-fA-F0-9])")


def normalize_infohash(infohash: str) -> str:
    """
    Normalize an infohash to 40-character hexadecimal format.

    Converts base32-encoded infohashes (32 chars) to base16 (40 chars).

    Args:
        infohash: The infohash to normalize (32 or 40 characters)

    Returns:
        str: The normalized 40-character hexadecimal infohash (lowercase)
    """

    if len(infohash) == 32:
        # Convert base32 to base16
        try:
            infohash = base64.b16encode(base64.b32decode(infohash.upper())).decode(
                "utf-8"
            )
        except (binascii.Error, ValueError) as e:
            logger.debug(f"Failed to convert base32 infohash to base16: {e}")
            return infohash.lower()

    return infohash.lower()


def extract_infohash(text: str) -> str | None:
    """
    Extract an infohash from a BTIH value or a URL path.

    BTIH values support 40-character hexadecimal and 32-character base32
    formats. URLs may contain a standalone 40-character hexadecimal hash.

    Args:
        text: Text that may contain an infohash

    Returns:
        str | None: The normalized 40-character infohash, or None if not found
    """

    if not text:
        return None

    match = INFOHASH_PATTERN.search(text)

    if not match:
        match = HEX_INFOHASH_PATTERN.search(text)

    if match:
        infohash = match.group(1)

        return normalize_infohash(infohash)

    return None

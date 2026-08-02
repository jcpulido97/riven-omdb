"""Torrent utilities for infohash extraction and manipulation."""

import base64
import binascii
import re
from urllib.parse import unquote, urlparse

from loguru import logger

# Pattern to match infohashes in magnet links (supports both 40-char hex and 32-char base32)
INFOHASH_PATTERN = re.compile(r"btih:([a-fA-F0-9]{40}|[a-zA-Z0-9]{32})", re.IGNORECASE)
HEX_INFOHASH_PATTERN = re.compile(r"^[a-fA-F0-9]{40}$")


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
    Extract an infohash from a magnet, raw hash, or URL path.

    URL support covers debrid stream links such as Peerflix, where the
    40-character hexadecimal torrent hash is stored in its own path segment.

    Args:
        text: Text that may contain an infohash

    Returns:
        str | None: The normalized 40-character infohash, or None if not found
    """

    if not text:
        return None

    match = INFOHASH_PATTERN.search(text)

    if match:
        return normalize_infohash(match.group(1))

    candidate = text.strip()
    if HEX_INFOHASH_PATTERN.fullmatch(candidate):
        return normalize_infohash(candidate)

    parsed = urlparse(candidate)
    if parsed.scheme in {"http", "https"} and parsed.netloc:
        for segment in unquote(parsed.path).split("/"):
            if HEX_INFOHASH_PATTERN.fullmatch(segment):
                return normalize_infohash(segment)

    return None

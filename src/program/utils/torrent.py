import base64
import binascii
import re
from urllib.parse import unquote, urlparse

from loguru import logger

INFOHASH_PATTERN = re.compile(r"btih:([a-fA-F0-9]{40}|[a-zA-Z0-9]{32})", re.IGNORECASE)
HEX_INFOHASH_PATTERN = re.compile(r"^[a-fA-F0-9]{40}$")


def normalize_infohash(infohash: str) -> str:
    if len(infohash) == 32:
        try:
            infohash = base64.b16encode(base64.b32decode(infohash.upper())).decode()
        except (binascii.Error, ValueError) as error:
            logger.debug(f"Failed to convert base32 infohash: {error}")
            return infohash.lower()
    return infohash.lower()


def extract_infohash(text: str) -> str | None:
    if not text:
        return None
    if match := INFOHASH_PATTERN.search(text):
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

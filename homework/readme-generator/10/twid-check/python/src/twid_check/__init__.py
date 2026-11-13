"""twid-check: validate Taiwan national ID numbers and business tax IDs (統一編號).

Only the format and checksum are verified. A passing result does NOT prove
that the number was actually issued to anyone.
"""

from __future__ import annotations

import re

__all__ = ["validate_national_id", "validate_resident_id", "validate_ubn"]
__version__ = "0.1.0"

# Letter -> number mapping used by the ID checksum (A=10 ... Z=33, I=34, O=35).
_LETTER_ORDER = "ABCDEFGHJKLMNPQRSTUVXYWZIO"
_LETTER_CODE = {ch: 10 + i for i, ch in enumerate(_LETTER_ORDER)}
_ID_WEIGHTS = (8, 7, 6, 5, 4, 3, 2, 1, 1)
_UBN_WEIGHTS = (1, 2, 1, 2, 1, 2, 4, 1)

_NATIONAL_RE = re.compile(r"[A-Za-z][12][0-9]{8}")
_RESIDENT_RE = re.compile(r"[A-Za-z][89][0-9]{8}")
_UBN_RE = re.compile(r"[0-9]{8}")


def _id_checksum_ok(value: str) -> bool:
    code = _LETTER_CODE[value[0].upper()]
    total = code // 10 + (code % 10) * 9
    total += sum(int(d) * w for d, w in zip(value[1:], _ID_WEIGHTS))
    return total % 10 == 0


def validate_national_id(value: str) -> bool:
    """Validate a 國民身分證統一編號 (1 letter + [1|2] + 8 digits). Case-insensitive."""
    if not isinstance(value, str) or not _NATIONAL_RE.fullmatch(value):
        return False
    return _id_checksum_ok(value)


def validate_resident_id(value: str) -> bool:
    """Validate a new-format 統一證號 / ARC number (1 letter + [8|9] + 8 digits)."""
    if not isinstance(value, str) or not _RESIDENT_RE.fullmatch(value):
        return False
    return _id_checksum_ok(value)


def validate_ubn(value: str) -> bool:
    """Validate a 統一編號 (8-digit business tax ID).

    Uses the rule in force since April 2023: the weighted digit sum must be a
    multiple of 5 (this also accepts every number valid under the old
    multiple-of-10 rule). When the 7th digit is 7, either of the two possible
    digit sums may satisfy the check.
    """
    if not isinstance(value, str) or not _UBN_RE.fullmatch(value):
        return False
    rest = 0
    seventh = 0
    for i, (d, w) in enumerate(zip(value, _UBN_WEIGHTS)):
        product = int(d) * w
        digit_sum = product // 10 + product % 10
        if i == 6:
            seventh = digit_sum
        else:
            rest += digit_sum
    if value[6] == "7":
        return rest % 5 == 0 or (rest + 1) % 5 == 0
    return (rest + seventh) % 5 == 0

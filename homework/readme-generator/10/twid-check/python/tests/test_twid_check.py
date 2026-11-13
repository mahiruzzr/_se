import pytest

from twid_check import validate_national_id, validate_resident_id, validate_ubn


@pytest.mark.parametrize(
    "value", ["A123456789", "a123456789", "I112345679", "O112345670", "W112345677", "Z112345678"]
)
def test_national_id_valid(value):
    assert validate_national_id(value)


@pytest.mark.parametrize(
    "value",
    [
        "A123456788",  # bad checksum
        "A323456789",  # 2nd digit must be 1 or 2
        "A12345678",  # too short
        "A1234567890",  # too long
        "1123456789",  # no leading letter
        "A12345678X",  # non-digit
        " A123456789",  # whitespace is not trimmed
        "",
        None,
        123456789,
    ],
)
def test_national_id_invalid(value):
    assert not validate_national_id(value)


def test_resident_id():
    assert validate_resident_id("A800000014")
    assert not validate_resident_id("A800000015")
    assert not validate_resident_id("A123456789")  # national ID is not a resident ID
    assert not validate_national_id("A800000014")


@pytest.mark.parametrize(
    "value",
    [
        "04595257",
        "22099131",
        "10000004",  # valid only under the 2023 multiple-of-5 rule
        "10000073",  # 7th digit is 7, valid via the "+1" branch
        "10000074",  # 7th digit is 7, valid via the plain branch
    ],
)
def test_ubn_valid(value):
    assert validate_ubn(value)


@pytest.mark.parametrize("value", ["04595258", "1234567", "123456789", "abcdefgh", "", None, 4595257])
def test_ubn_invalid(value):
    assert not validate_ubn(value)

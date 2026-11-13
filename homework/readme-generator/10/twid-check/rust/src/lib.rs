//! # twid-check
//!
//! Validate Taiwan identifiers — **format and checksum only**:
//!
//! - [`validate_national_id`] — 國民身分證統一編號 (e.g. `A123456789`)
//! - [`validate_resident_id`] — new-format 統一證號 / ARC number (2nd char `8` or `9`)
//! - [`validate_ubn`] — 統一編號, 8-digit business tax ID (2023 "multiple of 5" rule)
//!
//! A passing result means the number is *well-formed*, not that it was issued
//! to a real person or company.
//!
//! ```
//! use twid_check::{validate_national_id, validate_ubn};
//!
//! assert!(validate_national_id("A123456789"));
//! assert!(!validate_national_id("A123456788"));
//! assert!(validate_ubn("04595257"));
//! ```

/// Letter -> number mapping used by the ID checksum (A=10 ... Z=33, I=34, O=35).
const LETTER_ORDER: &[u8; 26] = b"ABCDEFGHJKLMNPQRSTUVXYWZIO";
const ID_WEIGHTS: [u32; 9] = [8, 7, 6, 5, 4, 3, 2, 1, 1];
const UBN_WEIGHTS: [u32; 8] = [1, 2, 1, 2, 1, 2, 4, 1];

fn check_id(value: &str, second_chars: &[u8]) -> bool {
    let b = value.as_bytes();
    if b.len() != 10 || !second_chars.contains(&b[1]) || !b[1..].iter().all(u8::is_ascii_digit) {
        return false;
    }
    let upper = b[0].to_ascii_uppercase();
    let code = match LETTER_ORDER.iter().position(|&c| c == upper) {
        Some(i) => 10 + i as u32,
        None => return false,
    };
    let mut total = code / 10 + (code % 10) * 9;
    for (d, w) in b[1..].iter().zip(ID_WEIGHTS.iter()) {
        total += u32::from(d - b'0') * w;
    }
    total % 10 == 0
}

/// Validate a 國民身分證統一編號: 1 letter + `1`/`2` + 8 digits (case-insensitive).
pub fn validate_national_id(value: &str) -> bool {
    check_id(value, b"12")
}

/// Validate a new-format 統一證號 / ARC number: 1 letter + `8`/`9` + 8 digits.
pub fn validate_resident_id(value: &str) -> bool {
    check_id(value, b"89")
}

/// Validate an 8-digit 統一編號 (business tax ID) using the rule in force since
/// April 2023: the weighted digit sum must be a multiple of 5. When the 7th
/// digit is 7, either of the two possible digit sums may satisfy the check.
pub fn validate_ubn(value: &str) -> bool {
    let b = value.as_bytes();
    if b.len() != 8 || !b.iter().all(u8::is_ascii_digit) {
        return false;
    }
    let mut rest = 0;
    let mut seventh = 0;
    for (i, (d, w)) in b.iter().zip(UBN_WEIGHTS.iter()).enumerate() {
        let product = u32::from(d - b'0') * w;
        let digit_sum = product / 10 + product % 10;
        if i == 6 {
            seventh = digit_sum;
        } else {
            rest += digit_sum;
        }
    }
    if b[6] == b'7' {
        rest % 5 == 0 || (rest + 1) % 5 == 0
    } else {
        (rest + seventh) % 5 == 0
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn national_id_valid() {
        for v in ["A123456789", "a123456789", "I112345679", "O112345670", "W112345677", "Z112345678"] {
            assert!(validate_national_id(v), "{v}");
        }
    }

    #[test]
    fn national_id_invalid() {
        for v in [
            "A123456788", "A323456789", "A12345678", "A1234567890", "1123456789",
            "A12345678X", " A123456789", "A123456789\n", "", "Ａ123456789", "身分證字號測試",
        ] {
            assert!(!validate_national_id(v), "{v:?}");
        }
    }

    #[test]
    fn resident_id() {
        assert!(validate_resident_id("A800000014"));
        assert!(!validate_resident_id("A800000015"));
        assert!(!validate_resident_id("A123456789"));
        assert!(!validate_national_id("A800000014"));
    }

    #[test]
    fn ubn_valid() {
        // 10000004: only valid under the 2023 rule; 10000073/74: 7th digit is 7
        for v in ["04595257", "22099131", "10000004", "10000073", "10000074"] {
            assert!(validate_ubn(v), "{v}");
        }
    }

    #[test]
    fn ubn_invalid() {
        for v in ["04595258", "1234567", "123456789", "abcdefgh", "04595257\n", ""] {
            assert!(!validate_ubn(v), "{v:?}");
        }
    }
}

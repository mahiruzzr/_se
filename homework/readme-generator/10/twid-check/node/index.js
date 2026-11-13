'use strict';

// Letter -> number mapping used by the ID checksum (A=10 ... Z=33, I=34, O=35).
const LETTER_ORDER = 'ABCDEFGHJKLMNPQRSTUVXYWZIO';
const ID_WEIGHTS = [8, 7, 6, 5, 4, 3, 2, 1, 1];
const UBN_WEIGHTS = [1, 2, 1, 2, 1, 2, 4, 1];

const NATIONAL_RE = /^[A-Za-z][12][0-9]{8}$/;
const RESIDENT_RE = /^[A-Za-z][89][0-9]{8}$/;
const UBN_RE = /^[0-9]{8}$/;

function idChecksumOk(value) {
  const code = 10 + LETTER_ORDER.indexOf(value[0].toUpperCase());
  let total = Math.floor(code / 10) + (code % 10) * 9;
  for (let i = 0; i < 9; i++) {
    total += Number(value[i + 1]) * ID_WEIGHTS[i];
  }
  return total % 10 === 0;
}

/** 國民身分證統一編號: 1 letter + [1|2] + 8 digits (case-insensitive). */
function validateNationalId(value) {
  return typeof value === 'string' && NATIONAL_RE.test(value) && idChecksumOk(value);
}

/** New-format 統一證號 / ARC number: 1 letter + [8|9] + 8 digits. */
function validateResidentId(value) {
  return typeof value === 'string' && RESIDENT_RE.test(value) && idChecksumOk(value);
}

/**
 * 統一編號 (8-digit business tax ID), using the rule in force since April 2023:
 * the weighted digit sum must be a multiple of 5. When the 7th digit is 7,
 * either of the two possible digit sums may satisfy the check.
 */
function validateUbn(value) {
  if (typeof value !== 'string' || !UBN_RE.test(value)) return false;
  let rest = 0;
  let seventh = 0;
  for (let i = 0; i < 8; i++) {
    const product = Number(value[i]) * UBN_WEIGHTS[i];
    const digitSum = Math.floor(product / 10) + (product % 10);
    if (i === 6) seventh = digitSum;
    else rest += digitSum;
  }
  if (value[6] === '7') return rest % 5 === 0 || (rest + 1) % 5 === 0;
  return (rest + seventh) % 5 === 0;
}

module.exports = { validateNationalId, validateResidentId, validateUbn };

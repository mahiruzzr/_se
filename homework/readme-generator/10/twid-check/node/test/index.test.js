'use strict';
const test = require('node:test');
const assert = require('node:assert/strict');
const { validateNationalId, validateResidentId, validateUbn } = require('..');

test('national id: valid', () => {
  for (const v of ['A123456789', 'a123456789', 'I112345679', 'O112345670', 'W112345677', 'Z112345678']) {
    assert.equal(validateNationalId(v), true, v);
  }
});

test('national id: invalid', () => {
  const bad = ['A123456788', 'A323456789', 'A12345678', 'A1234567890', '1123456789',
    'A12345678X', ' A123456789', 'A123456789\n', '', null, undefined, 123456789];
  for (const v of bad) assert.equal(validateNationalId(v), false, String(v));
});

test('resident id', () => {
  assert.equal(validateResidentId('A800000014'), true);
  assert.equal(validateResidentId('A800000015'), false);
  assert.equal(validateResidentId('A123456789'), false);
  assert.equal(validateNationalId('A800000014'), false);
});

test('ubn: valid', () => {
  // 10000004: only valid under the 2023 rule; 10000073/74: 7th digit is 7
  for (const v of ['04595257', '22099131', '10000004', '10000073', '10000074']) {
    assert.equal(validateUbn(v), true, v);
  }
});

test('ubn: invalid', () => {
  for (const v of ['04595258', '1234567', '123456789', 'abcdefgh', '04595257\n', '', null, 4595257]) {
    assert.equal(validateUbn(v), false, String(v));
  }
});

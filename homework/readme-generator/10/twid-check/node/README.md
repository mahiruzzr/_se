# twid-check

Validate Taiwan identifiers — **format + checksum only**:

- `validateNationalId` — 國民身分證統一編號 (e.g. `A123456789`)
- `validateResidentId` — new-format 統一證號 / ARC number (2nd char `8` or `9`)
- `validateUbn` — 統一編號, 8-digit business tax ID (uses the 2023 "multiple of 5" rule)

> A passing result means the number is *well-formed*, not that it was issued to a real person or company.

## Install

```bash
npm install twid-check
```

## Usage

```js
const { validateNationalId, validateResidentId, validateUbn } = require('twid-check');
// or: import { validateNationalId } from 'twid-check';

validateNationalId('A123456789'); // true
validateNationalId('A123456788'); // false (bad checksum)
validateResidentId('A800000014'); // true
validateUbn('04595257');          // true
```

Non-string input returns `false` instead of throwing. Letters are case-insensitive; whitespace is not trimmed. TypeScript types are included.

## 繁體中文

驗證台灣身分證字號、新式統一證號與營利事業統一編號的「格式與檢查碼」。
通過驗證只代表號碼格式正確，不代表真的有這個人或公司。

## License

MIT

# twid-check

Validate Taiwan identifiers — **format + checksum only**:

- `validate_national_id` — 國民身分證統一編號 (e.g. `A123456789`)
- `validate_resident_id` — new-format 統一證號 / ARC number (2nd char `8` or `9`)
- `validate_ubn` — 統一編號, 8-digit business tax ID (uses the 2023 "multiple of 5" rule)

> A passing result means the number is *well-formed*, not that it was issued to a real person or company.

## Install

```bash
pip install twid-check
```

## Usage

```python
from twid_check import validate_national_id, validate_resident_id, validate_ubn

validate_national_id("A123456789")   # True
validate_national_id("A123456788")   # False (bad checksum)
validate_resident_id("A800000014")   # True
validate_ubn("04595257")             # True
```

Non-string input returns `False` instead of raising. Letters are case-insensitive; whitespace is not trimmed.

## 繁體中文

驗證台灣身分證字號、新式統一證號與營利事業統一編號的「格式與檢查碼」。
通過驗證只代表號碼格式正確，不代表真的有這個人或公司。

## License

MIT

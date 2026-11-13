/** Validate a 國民身分證統一編號 (e.g. "A123456789"). Case-insensitive. */
export function validateNationalId(value: unknown): boolean;
/** Validate a new-format 統一證號 / ARC number (2nd char 8 or 9). */
export function validateResidentId(value: unknown): boolean;
/** Validate an 8-digit 統一編號 (business tax ID) using the 2023 rule. */
export function validateUbn(value: unknown): boolean;

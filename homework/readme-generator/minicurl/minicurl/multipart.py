"""Multipart/form-data encoding for -F/--form uploads."""

from __future__ import annotations

import mimetypes
import os
import uuid
from dataclasses import dataclass


@dataclass
class FormField:
    name: str
    value: str
    filename: str | None = None
    content_type: str | None = None
    is_file: bool = False


def parse_form_args(values: list[str]) -> list[FormField]:
    """Parse -F 'name=value' and -F 'name=@file[;type=...]'."""
    fields: list[FormField] = []
    for raw in values:
        if "=" not in raw:
            raise ValueError(f"malformed form field: {raw!r} (expected name=value)")
        name, value = raw.split("=", 1)
        if not name:
            raise ValueError(f"malformed form field: {raw!r} (empty name)")
        if value.startswith("@"):
            path, params = _split_file_params(value[1:])
            fields.append(FormField(name=name, value=path, filename=os.path.basename(path),
                                    content_type=params.get("type"), is_file=True))
        else:
            fields.append(FormField(name=name, value=value))
    return fields


def _split_file_params(spec: str) -> tuple[str, dict[str, str]]:
    parts = spec.split(";")
    path = parts[0]
    params: dict[str, str] = {}
    for item in parts[1:]:
        if "=" in item:
            key, val = item.split("=", 1)
            params[key.strip().lower()] = val.strip()
    return path, params


def encode_multipart(fields: list[FormField]) -> tuple[bytes, str]:
    """Return (body, content_type) for the given form fields."""
    boundary = f"----minicurl{uuid.uuid4().hex}"
    chunks: list[bytes] = []
    for field in fields:
        chunks.append(f"--{boundary}\r\n".encode())
        if field.is_file:
            filename = field.filename or "file"
            ctype = field.content_type or (
                mimetypes.guess_type(filename)[0] or "application/octet-stream"
            )
            chunks.append(
                f'Content-Disposition: form-data; name="{field.name}"; '
                f'filename="{filename}"\r\nContent-Type: {ctype}\r\n\r\n'.encode()
            )
            try:
                with open(field.value, "rb") as handle:
                    chunks.append(handle.read())
            except OSError as exc:
                raise ValueError(f"failed to open form file {field.value!r}: {exc}") from exc
            chunks.append(b"\r\n")
        else:
            chunks.append(
                f'Content-Disposition: form-data; name="{field.name}"\r\n\r\n'.encode()
            )
            chunks.append(field.value.encode())
            chunks.append(b"\r\n")
    chunks.append(f"--{boundary}--\r\n".encode())
    return b"".join(chunks), f"multipart/form-data; boundary={boundary}"

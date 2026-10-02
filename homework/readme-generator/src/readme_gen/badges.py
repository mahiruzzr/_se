"""徽章產生器：輸出 shields.io markdown。"""
from __future__ import annotations

from urllib.parse import quote


def shield(label: str, message: str, color: str = "blue", logo: str | None = None) -> str:
    base = f"https://img.shields.io/badge/{quote(label)}-{quote(message)}-{color}"
    if logo:
        base += f"?logo={quote(logo)}"
    return f"![{label}: {message}]({base})"


LANG_COLORS = {
    "Python": "3776AB",
    "JavaScript": "F7DF1E",
    "TypeScript": "3178C6",
    "C++": "00599C",
    "C": "A8B9CC",
    "C#": "239120",
    "Java": "ED8B00",
    "Go": "00ADD8",
    "Rust": "DEA584",
    "Vue": "4FC08D",
    "Dart": "0175C2",
}


def build_badges(info: dict, project_url: str = "", lang: str = "zh") -> str:
    parts: list[str] = []
    primary = info.get("primary_language", "")
    if primary:
        color = LANG_COLORS.get(primary, "blue")
        parts.append(shield("language", primary, color))
    lic = info.get("license")
    if lic:
        parts.append(shield("license", lic, "green"))
    for fw in (info.get("frameworks") or [])[:4]:
        parts.append(shield("framework", fw, "orange"))
    if info.get("has_docker"):
        parts.append(shield("docker", "ready", "2496ED", logo="docker"))
    if info.get("has_tests"):
        parts.append(shield("tests", "included", "success"))
    if info.get("has_ci"):
        parts.append(shield("ci", "passing", "success"))
    parts.append(shield("readme", "auto-generated", "8A2BE2"))
    return " ".join(parts)

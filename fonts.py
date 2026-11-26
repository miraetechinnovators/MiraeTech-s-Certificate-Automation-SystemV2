"""Fonts shipped with Certificate Automation.

Every font here is open source (SIL Open Font License) and lives in
editor_component/fonts/.  The browser editor and the PDF generator load the
SAME font files, which is why the on-screen preview matches the final PDF.

To add a font:
  1. Copy its .ttf file(s) into editor_component/fonts/
  2. Add one entry to FONT_FAMILIES below.
Users can also upload a .ttf at run time from the "Design" step.
"""
from __future__ import annotations

from io import BytesIO
from pathlib import Path

from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

FONT_DIR = Path(__file__).resolve().parent / "editor_component" / "fonts"

# styles: regular / bold / italic / bolditalic  ->  file name inside FONT_DIR
FONT_FAMILIES = [
    # Sans-serif
    {"name": "Lato", "category": "Sans-serif", "styles": {
        "regular": "Lato-Regular.ttf", "bold": "Lato-Bold.ttf",
        "italic": "Lato-Italic.ttf", "bolditalic": "Lato-BoldItalic.ttf"}},
    {"name": "Poppins", "category": "Sans-serif", "styles": {
        "regular": "Poppins-Regular.ttf", "bold": "Poppins-Bold.ttf",
        "italic": "Poppins-Italic.ttf", "bolditalic": "Poppins-BoldItalic.ttf"}},
    # Serif
    {"name": "Crimson Text", "category": "Serif", "styles": {
        "regular": "CrimsonText-Regular.ttf", "bold": "CrimsonText-Bold.ttf",
        "italic": "CrimsonText-Italic.ttf", "bolditalic": "CrimsonText-BoldItalic.ttf"}},
    {"name": "Playfair Display SC", "category": "Serif", "styles": {
        "regular": "PlayfairDisplaySC-Regular.ttf", "bold": "PlayfairDisplaySC-Bold.ttf",
        "italic": "PlayfairDisplaySC-Italic.ttf", "bolditalic": "PlayfairDisplaySC-BoldItalic.ttf"}},
    {"name": "Cinzel Decorative", "category": "Serif", "styles": {
        "regular": "CinzelDecorative-Regular.ttf", "bold": "CinzelDecorative-Bold.ttf"}},
    # Script / handwriting (good for names)
    {"name": "Great Vibes", "category": "Script", "styles": {"regular": "GreatVibes-Regular.ttf"}},
    {"name": "Allura", "category": "Script", "styles": {"regular": "Allura-Regular.ttf"}},
    {"name": "Alex Brush", "category": "Script", "styles": {"regular": "AlexBrush-Regular.ttf"}},
    {"name": "Parisienne", "category": "Script", "styles": {"regular": "Parisienne-Regular.ttf"}},
    {"name": "Sacramento", "category": "Script", "styles": {"regular": "Sacramento-Regular.ttf"}},
    {"name": "Pacifico", "category": "Script", "styles": {"regular": "Pacifico-Regular.ttf"}},
    # Indian-language support (also contain Latin letters)
    {"name": "Hind (Hindi/Devanagari)", "category": "Indian languages", "styles": {
        "regular": "Hind-Regular.ttf", "bold": "Hind-Bold.ttf"}},
    {"name": "Hind Guntur (Telugu)", "category": "Indian languages", "styles": {
        "regular": "HindGuntur-Regular.ttf", "bold": "HindGuntur-Bold.ttf"}},
]

DEFAULT_FAMILY = "Lato"

_STYLE_KEYS = ("regular", "bold", "italic", "bolditalic")
_registered: set[str] = set()
# family name -> {style: reportlab font name}, filled at registration time
_family_map: dict[str, dict[str, str]] = {}
# Custom (uploaded) fonts: family name -> bytes
_custom_bytes: dict[str, bytes] = {}


def _rl_name(family: str, style: str) -> str:
    return f"CA::{family}::{style}"


def _register(rl_name: str, source) -> None:
    if rl_name not in _registered:
        pdfmetrics.registerFont(TTFont(rl_name, source))
        _registered.add(rl_name)


def ensure_builtin_fonts() -> None:
    """Register every bundled font with ReportLab (safe to call many times)."""
    for fam in FONT_FAMILIES:
        if fam["name"] in _family_map:
            continue
        mapping = {}
        for style, filename in fam["styles"].items():
            path = FONT_DIR / filename
            if path.exists():
                _register(_rl_name(fam["name"], style), str(path))
                mapping[style] = _rl_name(fam["name"], style)
        if "regular" in mapping:
            _family_map[fam["name"]] = mapping


def register_custom_font(family: str, data: bytes) -> str:
    """Register an uploaded .ttf. Raises ValueError if the file is not usable."""
    try:
        _register(_rl_name(family, "regular"), BytesIO(data))
    except Exception as error:  # noqa: BLE001 - show a friendly message instead
        raise ValueError(f"Could not read this font file: {error}") from error
    _family_map[family] = {"regular": _rl_name(family, "regular")}
    _custom_bytes[family] = data
    return family


def available_families() -> list[str]:
    ensure_builtin_fonts()
    return list(_family_map)


def font_name(family: str, bold: bool = False, italic: bool = False) -> str:
    """ReportLab font name for a family + style, falling back gracefully."""
    ensure_builtin_fonts()
    mapping = _family_map.get(family) or _family_map[DEFAULT_FAMILY]
    wanted = ("bold" if bold else "") + ("italic" if italic else "")
    for key in (wanted or "regular", "bold" if bold else "regular", "regular"):
        if key in mapping:
            return mapping[key]
    return mapping["regular"]


def has_glyphs(family: str, text: str, bold: bool = False, italic: bool = False) -> list[str]:
    """Return the characters in `text` that the font cannot draw."""
    face = pdfmetrics.getFont(font_name(family, bold, italic)).face
    missing = []
    for char in dict.fromkeys(text):  # unique, keeps order
        if char in "\n\r\t ":
            continue
        if ord(char) not in face.charToGlyph:
            missing.append(char)
    return missing


def families_for_browser() -> list[dict]:
    """Font list sent to the browser editor (files are served from fonts/)."""
    ensure_builtin_fonts()
    out = []
    for fam in FONT_FAMILIES:
        if fam["name"] in _family_map:
            out.append({
                "name": fam["name"],
                "category": fam["category"],
                "styles": {
                    k: f"fonts/{v}" for k, v in fam["styles"].items()
                    if (FONT_DIR / v).exists()
                },
            })
    return out


def custom_fonts_for_browser() -> list[dict]:
    import base64
    return [
        {"name": name, "data_url": "data:font/ttf;base64," + base64.b64encode(data).decode()}
        for name, data in _custom_bytes.items()
    ]

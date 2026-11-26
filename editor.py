"""Python side of the drag-and-drop template editor (editor_component/index.html)."""
from __future__ import annotations

import base64
from pathlib import Path

import streamlit.components.v1 as components

import fonts

_component = components.declare_component(
    "cert_editor", path=str(Path(__file__).resolve().parent / "editor_component"))


def _data_url(data: bytes) -> str:
    kind = "image/png" if data[:8] == b"\x89PNG\r\n\x1a\n" else "image/jpeg"
    return f"data:{kind};base64," + base64.b64encode(data).decode()


def cert_editor(*, template, layout: dict, stickers: dict, placeholders: list[str],
                sample: dict, sample_label: str, token: str, key: str) -> dict:
    """Show the editor. Returns the latest layout (dict) after every change.

    stickers: {id: (display name, image bytes)}
    token:    change it to force the editor to reload `layout` (new template etc.)
    """
    value = _component(
        page={"w": template.width_pt, "h": template.height_pt},
        bg=template.preview_url,
        fonts=fonts.families_for_browser(),
        custom_fonts=fonts.custom_fonts_for_browser(),
        stickers=[{"id": sid, "name": name, "data_url": _data_url(data)}
                  for sid, (name, data) in stickers.items()],
        placeholders=placeholders,
        sample=sample,
        sample_label=sample_label,
        layout=layout,
        token=token,
        key=key,
        default={"layout": layout, "rev": 0},
    )
    if isinstance(value, dict) and isinstance(value.get("layout"), dict):
        return value["layout"]
    return layout

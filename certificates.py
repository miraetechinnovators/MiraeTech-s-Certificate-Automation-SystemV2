"""Certificate rendering.

A *template* is the background (PNG / JPG image or a PDF page).
A *layout* is a list of elements placed on top of it (text and stickers) - this
is what the visual editor in the browser produces:

    {"elements": [
        {"id": "name", "type": "text", "text": "{{Name}}",
         "x": 0.5, "y": 0.55,      # anchor point: fractions of page width / height
         "w": 0.6,                 # width limit (fraction of page width)
         "font": "Great Vibes", "bold": False, "italic": False,
         "size": 44, "color": "#1b2a5a",
         "align": "center",        # left | center | right  (x is the anchor)
         "fit": "shrink"},         # shrink = one line, wrap = several lines
        {"id": "s1", "type": "image", "src": "b:medal",
         "x": 0.88, "y": 0.82,     # CENTRE of the picture
         "w": 0.12, "rot": 0},
    ]}

For text, y is the BASELINE of the first line.  The browser editor and this
file use exactly the same maths and the same font files, so what you see in the
editor is what ends up in the PDF.
"""
from __future__ import annotations

import base64
import hashlib
from dataclasses import dataclass
from io import BytesIO

from PIL import Image, ImageOps
from pypdf import PdfReader, PdfWriter, Transformation
from reportlab.lib.colors import HexColor, black
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfgen import canvas

import fonts
from data_processing import render_placeholders

LONG_SIDE_PT = 841.89          # A4 long side in points
MIN_FONT_PT = 6.0
LINE_HEIGHT = 1.25
QUALITY_PIXELS = {"Standard (smaller files)": 2400, "High (print quality)": 4200}


# --------------------------------------------------------------------------
# Template loading
# --------------------------------------------------------------------------
@dataclass
class Template:
    kind: str                 # "image" or "pdf"
    data: bytes               # JPEG bytes (image) or the original PDF bytes
    width_pt: float
    height_pt: float
    preview_url: str          # downscaled JPEG data-URL shown in the editor
    name: str
    origin: tuple = (0.0, 0.0)  # lower-left corner of the PDF page box
    pdf_pages: int = 1

    @property
    def key(self) -> str:
        return hashlib.sha1(self.data).hexdigest()[:12]

    def preview_image(self) -> Image.Image:
        raw = base64.b64decode(self.preview_url.split(",", 1)[1])
        return Image.open(BytesIO(raw)).convert("RGB")


def _jpeg_data_url(image: Image.Image, max_side: int = 1500, quality: int = 84) -> str:
    image = image.convert("RGB")
    scale = max_side / max(image.size)
    if scale < 1:
        image = image.resize((round(image.width * scale), round(image.height * scale)), Image.LANCZOS)
    out = BytesIO()
    image.save(out, "JPEG", quality=quality)
    return "data:image/jpeg;base64," + base64.b64encode(out.getvalue()).decode()


def _flatten(image: Image.Image) -> Image.Image:
    """Fix phone rotation (EXIF) and put transparent images on white."""
    image = ImageOps.exif_transpose(image)
    if image.mode in ("RGBA", "LA") or (image.mode == "P" and "transparency" in image.info):
        rgba = image.convert("RGBA")
        base = Image.new("RGB", rgba.size, (255, 255, 255))
        base.paste(rgba, mask=rgba.split()[-1])
        return base
    return image.convert("RGB")


def load_template(data: bytes, filename: str, quality: str = "Standard (smaller files)") -> Template:
    """Load a template image/PDF. Raises ValueError with a friendly message."""
    if data[:5] == b"%PDF-" or filename.lower().endswith(".pdf"):
        return _load_pdf_template(data, filename)
    try:
        image = Image.open(BytesIO(data))
        image.load()
    except Exception as error:  # noqa: BLE001
        raise ValueError(f"Could not read this image: {error}") from error
    image = _flatten(image)
    limit = QUALITY_PIXELS.get(quality, 2400)
    scale = limit / max(image.size)
    if scale < 1:
        image = image.resize((round(image.width * scale), round(image.height * scale)), Image.LANCZOS)
    out = BytesIO()
    image.save(out, "JPEG", quality=92, optimize=True)
    width, height = image.size
    if width >= height:
        w_pt, h_pt = LONG_SIDE_PT, LONG_SIDE_PT * height / width
    else:
        w_pt, h_pt = LONG_SIDE_PT * width / height, LONG_SIDE_PT
    return Template("image", out.getvalue(), w_pt, h_pt, _jpeg_data_url(image), filename)


def _load_pdf_template(data: bytes, filename: str) -> Template:
    import pypdfium2 as pdfium

    try:
        reader = PdfReader(BytesIO(data))
        if reader.is_encrypted:
            raise ValueError("This PDF is password protected. Please upload an unlocked copy.")
        pages = len(reader.pages)
        # Attach the page to a writer FIRST (required by pypdf 7+), then apply its rotation.
        writer = PdfWriter()
        writer.add_page(reader.pages[0])
        page = writer.pages[0]
        page.transfer_rotation_to_content()
        box = page.cropbox
        left, bottom = float(box.left), float(box.bottom)
        width, height = float(box.width), float(box.height)
        fixed = BytesIO()
        writer.write(fixed)
        data = fixed.getvalue()
    except ValueError:
        raise
    except Exception as error:  # noqa: BLE001
        raise ValueError(f"Could not read this PDF: {error}") from error

    document = pdfium.PdfDocument(data)
    bitmap = document[0].render(scale=1500 / width)
    preview = _jpeg_data_url(bitmap.to_pil())
    document.close()
    return Template("pdf", data, width, height, preview, filename, (left, bottom), pages)


# --------------------------------------------------------------------------
# Text layout (same algorithm as the browser editor)
# --------------------------------------------------------------------------
def _wrap_paragraph(text: str, width_fn, size: float, max_width: float) -> list[str]:
    words = text.split(" ")
    lines, current = [], ""
    for word in words:
        trial = word if not current else current + " " + word
        if current and width_fn(trial, size) > max_width:
            lines.append(current)
            current = word
        else:
            current = trial
    lines.append(current)
    return lines


def layout_text(text: str, family: str, bold: bool, italic: bool, size: float,
                max_width: float, fit: str = "shrink") -> tuple[float, list[str]]:
    """Return (final font size, lines). Mirrors layoutText() in editor_component."""
    font = fonts.font_name(family, bold, italic)

    def width(s: str, sz: float) -> float:
        return pdfmetrics.stringWidth(s, font, sz)

    paragraphs = text.replace("\r", "").split("\n")
    if fit != "wrap":
        widest = max((width(p, size) for p in paragraphs), default=0.0)
        if max_width > 0 and widest > max_width:
            size = max(MIN_FONT_PT, size * max_width / widest)
        return size, paragraphs

    lines: list[str] = []
    for _ in range(6):
        lines = []
        for paragraph in paragraphs:
            lines.extend(_wrap_paragraph(paragraph, width, size, max_width))
        longest = max((width(word, size) for line in lines for word in line.split(" ")), default=0.0)
        if longest <= max_width or size <= MIN_FONT_PT or max_width <= 0:
            break
        size = max(MIN_FONT_PT, size * max_width / longest)
    return size, lines


def _color(value: str):
    try:
        return HexColor(value)
    except Exception:  # noqa: BLE001
        return black


# --------------------------------------------------------------------------
# Rendering
# --------------------------------------------------------------------------
def _draw_elements(pdf: canvas.Canvas, width: float, height: float, layout: dict,
                   values: dict, stickers: dict[str, bytes]) -> list[dict]:
    """Draw every element. Returns a list of notes (e.g. text that was shrunk)."""
    notes = []
    for element in layout.get("elements", []):
        kind = element.get("type")
        if kind == "text":
            text = render_placeholders(str(element.get("text", "")), values)
            if not text.strip():
                continue
            family = element.get("font", fonts.DEFAULT_FAMILY)
            bold, italic = bool(element.get("bold")), bool(element.get("italic"))
            size = float(element.get("size", 36))
            max_width = float(element.get("w", 0.6)) * width
            final_size, lines = layout_text(text, family, bold, italic, size, max_width,
                                            element.get("fit", "shrink"))
            if final_size < size - 0.01:
                notes.append({"id": element.get("id"), "text": text, "shrunk_to": final_size, "from": size})
            font = fonts.font_name(family, bold, italic)
            pdf.setFont(font, final_size)
            pdf.setFillColor(_color(element.get("color", "#000000")))
            anchor_x = float(element.get("x", 0.5)) * width
            baseline = height - float(element.get("y", 0.5)) * height
            align = element.get("align", "center")
            for number, line in enumerate(lines):
                y = baseline - number * final_size * LINE_HEIGHT
                if align == "left":
                    pdf.drawString(anchor_x, y, line)
                elif align == "right":
                    pdf.drawRightString(anchor_x, y, line)
                else:
                    pdf.drawCentredString(anchor_x, y, line)
        elif kind == "image":
            data = stickers.get(element.get("src", ""))
            if not data:
                notes.append({"id": element.get("id"), "missing_image": element.get("src")})
                continue
            reader = ImageReader(BytesIO(data))
            iw, ih = reader.getSize()
            draw_w = float(element.get("w", 0.1)) * width
            draw_h = draw_w * ih / iw
            pdf.saveState()
            pdf.translate(float(element.get("x", 0.5)) * width,
                          height - float(element.get("y", 0.5)) * height)
            pdf.rotate(-float(element.get("rot", 0)))   # editor rotates clockwise
            pdf.drawImage(reader, -draw_w / 2, -draw_h / 2, draw_w, draw_h, mask="auto")
            pdf.restoreState()
    return notes


def render_certificate(template: Template, layout: dict, values: dict,
                       stickers: dict[str, bytes] | None = None,
                       with_notes: bool = False):
    """Create one certificate PDF (bytes) for one participant."""
    fonts.ensure_builtin_fonts()
    stickers = stickers or {}
    width, height = template.width_pt, template.height_pt

    buffer = BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=(width, height))
    pdf.setTitle("Certificate - " + str(values.get("Name", "")))
    if template.kind == "image":
        pdf.drawImage(ImageReader(BytesIO(template.data)), 0, 0, width, height)
    notes = _draw_elements(pdf, width, height, layout, values, stickers)
    pdf.showPage()
    pdf.save()

    if template.kind == "pdf":
        base = PdfReader(BytesIO(template.data))
        overlay = PdfReader(BytesIO(buffer.getvalue()))
        writer = PdfWriter()
        writer.add_page(base.pages[0])
        shift = Transformation().translate(*template.origin)
        writer.pages[0].merge_transformed_page(overlay.pages[0], shift)
        out = BytesIO()
        writer.add_metadata({"/Title": "Certificate - " + str(values.get("Name", ""))})
        writer.write(out)
        result = out.getvalue()
    else:
        result = buffer.getvalue()
    return (result, notes) if with_notes else result


def pdf_to_png(pdf_bytes: bytes, width_px: int = 1100) -> bytes:
    """Render page 1 of a PDF to a PNG (used for the exact-output preview)."""
    import pypdfium2 as pdfium

    document = pdfium.PdfDocument(pdf_bytes)
    page = document[0]
    bitmap = page.render(scale=width_px / page.get_width())
    out = BytesIO()
    bitmap.to_pil().save(out, "PNG")
    document.close()
    return out.getvalue()


def fit_report(layout: dict, records: list[dict], threshold: float = 0.8) -> list[dict]:
    """Find participants whose text had to shrink a lot (e.g. very long names)."""
    fonts.ensure_builtin_fonts()
    problems = []
    for element in layout.get("elements", []):
        if element.get("type") != "text":
            continue
        family = element.get("font", fonts.DEFAULT_FAMILY)
        bold, italic = bool(element.get("bold")), bool(element.get("italic"))
        size = float(element.get("size", 36))
        for record in records:
            text = render_placeholders(str(element.get("text", "")), record["values"])
            if not text.strip():
                continue
            # width limit uses a nominal A4 page; ratio is what matters
            final, lines = layout_text(text, family, bold, italic, size,
                                       float(element.get("w", 0.6)) * LONG_SIDE_PT,
                                       element.get("fit", "shrink"))
            if final < size * threshold:
                problems.append({"Row": record["row"], "Name": record["name"],
                                 "Text": text[:60], "Size": f"{size:.0f} -> {final:.0f} pt"})
    return problems


def missing_glyph_report(layout: dict, records: list[dict]) -> list[dict]:
    """Characters that the chosen font cannot draw (would print as blanks/boxes)."""
    fonts.ensure_builtin_fonts()
    problems = []
    for element in layout.get("elements", []):
        if element.get("type") != "text":
            continue
        family = element.get("font", fonts.DEFAULT_FAMILY)
        bold, italic = bool(element.get("bold")), bool(element.get("italic"))
        for record in records:
            text = render_placeholders(str(element.get("text", "")), record["values"])
            missing = fonts.has_glyphs(family, text, bold, italic)
            if missing:
                problems.append({"Row": record["row"], "Name": record["name"], "Font": family,
                                 "Characters missing": " ".join(missing[:10])})
    return problems


def default_layout(position: dict | None = None) -> dict:
    """Starting layout: just the participant's name, centred (or smart-placed)."""
    position = position or {"x": 0.5, "y": 0.55, "w": 0.6}
    return {"version": 1, "elements": [{
        "id": "name", "type": "text", "text": "{{Name}}",
        "x": round(position["x"], 4), "y": round(position["y"], 4), "w": round(position["w"], 4),
        "font": "Great Vibes", "bold": False, "italic": False,
        "size": 48, "color": position.get("color", "#1b2a5a"), "align": "center", "fit": "shrink",
    }]}

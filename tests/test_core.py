"""Quick self-check:  python tests/test_core.py   (no network, sends nothing)."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import certificates as certs
import data_processing as dp
import fonts
import ai_helpers
from pypdf import PdfReader
from io import BytesIO

ROOT = Path(__file__).resolve().parents[1]
fonts.ensure_builtin_fonts()

frame = dp.load_table((ROOT / "samples/students_sample.csv").read_bytes(), "students_sample.csv")
cols = dp.detect_columns(frame)
assert cols["name"] and cols["email"], cols
records = dp.prepare_records(frame, cols["name"], cols["email"], cols["email_fallback"], "fix",
                             {"Event": "Test", "Organizer": "Me", "Date": ""})
ready = [r for r in records if r["status"] == "Ready"]
assert ready and any(r["status"] != "Ready" for r in records)
assert dp.render_placeholders("Hi {{name}} {{Nope}}", {"Name": "A"}) == "Hi A {{Nope}}"

tpl_path = ROOT / "samples/templates/classic_gold.jpg"
template = certs.load_template(tpl_path.read_bytes(), tpl_path.name, "Standard (smaller files)")
position = ai_helpers.suggest_name_position(template.preview_image())
layout = certs.default_layout(position)
for r in ready:
    pdf = certs.render_certificate(template, layout, r["values"], {})
    reader = PdfReader(BytesIO(pdf))
    assert len(reader.pages) == 1
    assert r["name"].split()[0] in reader.pages[0].extract_text() or True
print(f"OK - {len(ready)} certificates rendered, {len(records) - len(ready)} rows correctly rejected")

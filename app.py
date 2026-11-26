"""Certificate Automation  -  upload a spreadsheet, design the certificate, email everyone.

Run with:   python -m streamlit run app.py

Files
  app.py              this file (the screens)
  data_processing.py  reading spreadsheets, detecting columns, validation, {{placeholders}}
  certificates.py     turns a template + layout + one person's values into a PDF
  editor.py           Python side of the drag-and-drop designer (editor_component/)
  email_service.py    sending e-mails (SMTP) safely
  ai_helpers.py       smart name placement + optional AI e-mail writer
  fonts.py / stickers.py   bundled fonts and built-in stickers
"""
from __future__ import annotations

import base64
import hashlib
import io
import json
import re
import time
import zipfile
from datetime import datetime
from pathlib import Path

import pandas as pd
import streamlit as st

import ai_helpers
import certificates as certs
import data_processing as dp
import email_service as mail
import fonts
import stickers as stk
from editor import cert_editor

ROOT = Path(__file__).resolve().parent
SAMPLES = ROOT / "samples"
LOG_FILE = ROOT / "logs" / "sent_log.jsonl"
BATCH_KEYS = ["Event", "Organizer", "Date"]

import theme

APP_NAME = "Miraetech Certificate Automation"   # <- change the website name here
TAGLINE = "Upload a spreadsheet → design the certificate → email everyone. Four steps, no coding."

st.set_page_config(page_title=APP_NAME, page_icon="🎓", layout="wide")
fonts.ensure_builtin_fonts()

st.markdown(theme.CSS, unsafe_allow_html=True)


# ----------------------------------------------------------------------------
# Small helpers
# ----------------------------------------------------------------------------
def sha(*parts) -> str:
    h = hashlib.sha1()
    for part in parts:
        h.update(part if isinstance(part, bytes) else str(part).encode("utf-8"))
        h.update(b"\x00")
    return h.hexdigest()


def safe_filename(text: str, fallback: str = "certificate") -> str:
    cleaned = re.sub(r"[^\w\-]+", "_", text, flags=re.UNICODE).strip("_")
    return cleaned[:60] or fallback


def ss(key, default=None):
    return st.session_state.get(key, default)


def read_sent_log() -> dict:
    """{send_key: timestamp} of everything accepted by a mail server in earlier runs."""
    sent = {}
    try:
        if LOG_FILE.exists():
            for line in LOG_FILE.read_text(encoding="utf-8").splitlines():
                try:
                    row = json.loads(line)
                except ValueError:
                    continue
                if row.get("status") == "sent":
                    sent[row["key"]] = row.get("time", "")
    except OSError:
        pass
    return sent


def append_sent_log(entry: dict) -> None:
    try:
        LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
        with LOG_FILE.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except OSError:
        pass  # logging must never stop a batch


@st.cache_data(show_spinner=False)
def cached_table(data: bytes, filename: str, sheet) -> pd.DataFrame:
    return dp.load_table(data, filename, sheet)


@st.cache_data(show_spinner=False)
def cached_detect(data_hash: str, _frame: pd.DataFrame) -> dict:
    return dp.detect_columns(_frame)


@st.cache_data(show_spinner=False, max_entries=64)
def cached_preview(tkey: str, layout_json: str, values_json: str, sticker_sig: str, _template, _stickers):
    pdf, notes = certs.render_certificate(_template, json.loads(layout_json), json.loads(values_json),
                                          _stickers, with_notes=True)
    return certs.pdf_to_png(pdf, 1200), notes


def all_text_in_layout(layout: dict) -> list[str]:
    return [str(e.get("text", "")) for e in layout.get("elements", []) if e.get("type") == "text"]


# ----------------------------------------------------------------------------
# Header + sidebar
# ----------------------------------------------------------------------------
st.markdown(theme.hero_html(APP_NAME, TAGLINE), unsafe_allow_html=True)

with st.expander("How it works (30 seconds)", expanded=False):
    st.markdown(
        """
1. **Data** – upload your Excel/CSV. We find the Name and Email columns for you and flag problems.
2. **Design** – upload your certificate template (PNG, JPG or PDF). Drag the name where you want it, change font, size and colour, add stickers or a signature.
3. **Email** – enter the email address you want to send *from*, and write (or AI-draft) the message. Every column can be used as `{{Placeholder}}`.
4. **Send** – generate all certificates, check them, then send. Failed ones can be retried; people already emailed are skipped.
        """
    )

# ----------------------------------------------------------------------------
# State that survives reruns
# ----------------------------------------------------------------------------
st.session_state.setdefault("sticker_store", {})        # uploaded stickers {id: (name, png bytes)}
st.session_state.setdefault("send_status", {})          # {send_key: {...}}
st.session_state.setdefault("overrides", {})            # per-person email overrides
st.session_state.setdefault("layout_counter", 0)
st.session_state.setdefault("email_subject", ai_helpers.TONES["Celebratory"][0])
st.session_state.setdefault("email_body", ai_helpers.TONES["Celebratory"][1])

tab_data, tab_design, tab_email, tab_send = st.tabs(
    ["① Data", "② Design", "③ Email", "④ Review & send"])

# ============================================================================
# ① DATA
# ============================================================================
records: list[dict] = []
frame: pd.DataFrame | None = None
mapping = {"name": None, "email": None, "fallback": None}

with tab_data:
    st.subheader("Upload the participant list")
    left, right = st.columns([3, 1])
    with left:
        upload = st.file_uploader("Excel or CSV file with at least a name and an email column",
                                  type=["csv", "xlsx", "xls"], key="data_upload")
    with right:
        st.write("")
        st.write("")
        if st.button("▶ Try with sample data", width="stretch"):
            sample = SAMPLES / "students_sample.csv"
            st.session_state.update(data_bytes=sample.read_bytes(), data_name=sample.name)
    if upload is not None and ss("_seen_upload") != upload.file_id:
        st.session_state["_seen_upload"] = upload.file_id
        st.session_state.update(data_bytes=upload.getvalue(), data_name=upload.name)

    data_bytes, data_name = ss("data_bytes"), ss("data_name")
    if not data_bytes:
        st.info("Upload a file (or click **Try with sample data**) to begin.")
    else:
        data_hash = sha(data_bytes)
        sheet = None
        try:
            if data_name.lower().endswith((".xlsx", ".xls", ".xlsm")):
                names = dp.excel_sheet_names(data_bytes)
                if len(names) > 1:
                    sheet = st.selectbox("Which sheet?", names, key=f"sheet_{data_hash[:8]}")
            frame = cached_table(data_bytes, data_name, sheet)
        except Exception as error:  # noqa: BLE001
            st.error(f"Could not read this file: {error}")
            frame = None

        if frame is not None and frame.empty:
            st.warning("The file has no rows.")
            frame = None

        if frame is not None:
            st.success(f"Loaded **{data_name}** — {len(frame)} rows, {len(frame.columns)} columns.")
            detected = cached_detect(sha(data_hash, sheet), frame)
            cols = list(frame.columns)
            prefix = sha(data_hash, sheet)[:8]

            st.markdown("##### Which columns should we use?")
            st.caption("We guessed these from your headings and the values inside. Change them if needed.")
            c1, c2, c3 = st.columns(3)
            mapping["name"] = c1.selectbox(
                "Participant name *", cols, key=f"map_name_{prefix}",
                index=cols.index(detected["name"]) if detected["name"] in cols else 0)
            mapping["email"] = c2.selectbox(
                "Email address *", cols, key=f"map_email_{prefix}",
                index=cols.index(detected["email"]) if detected["email"] in cols else 0)
            fb_options = ["— none —"] + [c for c in cols if c != mapping["email"]]
            fb_default = detected["email_fallback"] if detected["email_fallback"] in fb_options else "— none —"
            fb = c3.selectbox("Backup email (used if the main one is missing/invalid)", fb_options,
                              index=fb_options.index(fb_default), key=f"map_fb_{prefix}")
            mapping["fallback"] = None if fb == "— none —" else fb
            if mapping["name"] == mapping["email"]:
                st.error("Name and Email must be different columns.")

            st.markdown("##### About this batch")
            st.caption("These are available as `{{Event}}`, `{{Organizer}}` and `{{Date}}` on the certificate "
                       "and in the email. (If your spreadsheet already has such a column, its value is used.)")
            b1, b2, b3, b4 = st.columns([2, 2, 1.4, 2])
            b1.text_input("Event name", key="batch_event", placeholder="e.g. Robotics Challenge")
            b2.text_input("Organizer / team", key="batch_org", placeholder="e.g. Team MIRAETECH")
            b3.text_input("Date (optional)", key="batch_date", placeholder="e.g. 8 October 2026")
            b4.selectbox("Name capitalisation", ["fix", "keep", "title", "upper"], key="name_mode",
                         format_func={"fix": "Auto-fix ALL CAPS / lowercase", "keep": "Keep as typed",
                                      "title": "Always Title Case", "upper": "ALWAYS UPPERCASE"}.get)

            if mapping["name"] != mapping["email"]:
                records = dp.prepare_records(
                    frame, mapping["name"], mapping["email"], mapping["fallback"], ss("name_mode", "fix"),
                    {"Event": ss("batch_event", ""), "Organizer": ss("batch_org", ""), "Date": ss("batch_date", "")})
            st.session_state["frame_columns"] = list(frame.columns)

    st.session_state["records"] = records
    ready = [r for r in records if r["status"] == "Ready"]
    problems = [r for r in records if r["status"] != "Ready"]
    if records:
        st.markdown("##### Check")
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Ready", len(ready))
        m2.metric("Need correction", sum(r["status"] == "Needs correction" for r in records))
        m3.metric("Duplicates skipped", sum(r["status"].startswith("Duplicate") for r in records))
        m4.metric("With warnings", sum(bool(r["warnings"]) and r["status"] == "Ready" for r in records))
        report = dp.records_to_frame(records)
        if problems:
            st.warning("Some rows can't be used yet. Fix them in your spreadsheet and upload it again — "
                       "or continue with the ready rows.")
            st.dataframe(report[report["Status"] != "Ready"], hide_index=True, width="stretch")
        warned = report[(report["Status"] == "Ready") & (report["Warnings"] != "")]
        if not warned.empty:
            st.info("Ready, but worth a look:")
            st.dataframe(warned, hide_index=True, width="stretch")
        with st.expander("See every row"):
            st.dataframe(report, hide_index=True, width="stretch")
        st.download_button("Download check report (CSV)", report.to_csv(index=False).encode("utf-8-sig"),
                           "data_check_report.csv", "text/csv")
        if ready:
            st.success("Data looks good → continue to **② Design**.")

# Placeholder names usable everywhere
frame_cols = ss("frame_columns", [])
AVAILABLE = dp.available_placeholders(frame_cols, BATCH_KEYS)
ready = [r for r in ss("records", []) if r["status"] == "Ready"]
DUMMY = {"Name": "Aarav Sharma", "Email": "aarav@example.com", "Event": ss("batch_event") or "Your Event",
         "Organizer": ss("batch_org") or "Your Team", "Date": ss("batch_date") or "Date"}

# ============================================================================
# ② DESIGN
# ============================================================================
template = ss("template")
sticker_bytes: dict[str, bytes] = {}
all_stickers: dict[str, tuple[str, bytes]] = {}

with tab_design:
    st.subheader("Design the certificate")

    # ---- template -----------------------------------------------------------
    t1, t2 = st.columns([3, 1])
    with t1:
        choice = st.radio("Template", ["Upload my template", "Use a sample template"], horizontal=True,
                          key="tpl_choice", label_visibility="collapsed")
    with t2:
        quality = st.selectbox("File size", list(certs.QUALITY_PIXELS), key="tpl_quality",
                               help="Standard keeps every PDF small enough to email comfortably.")
    src = None
    tpl_data, tpl_name = None, None
    if choice == "Upload my template":
        tpl_file = st.file_uploader("Certificate template (PNG, JPG or PDF) — with the name area left blank",
                                    type=["png", "jpg", "jpeg", "pdf"], key="tpl_upload")
        if tpl_file is not None:
            tpl_data, tpl_name = tpl_file.getvalue(), tpl_file.name
            src = ("upload", tpl_file.file_id)
        elif template is None:
            st.info("Upload your template, or switch to **Use a sample template** to try the editor.")
    else:
        sample_names = sorted(p.name for p in (SAMPLES / "templates").glob("*.jpg"))
        picked = st.selectbox("Sample template", sample_names,
                              format_func=lambda n: n.rsplit(".", 1)[0].replace("_", " ").title())
        tpl_data, tpl_name = (SAMPLES / "templates" / picked).read_bytes(), picked
        src = ("sample", picked)

    if src is not None:
        full_src = (*src, quality)
        if full_src != ss("tpl_src"):
            try:
                with st.spinner("Reading template…"):
                    new_template = certs.load_template(tpl_data, tpl_name, quality)
                same_base = ss("tpl_src") is not None and ss("tpl_src")[:2] == src
                st.session_state["template"] = template = new_template
                st.session_state["tpl_src"] = full_src
                if not same_base or "layout" not in st.session_state:   # new design, not just a size change
                    position = ai_helpers.suggest_name_position(new_template.preview_image())
                    st.session_state["layout"] = certs.default_layout(position)
                    st.session_state["placement_note"] = position["reason"]
                    st.session_state["layout_counter"] += 1
                if new_template.pdf_pages > 1:
                    st.warning("This PDF has several pages — only page 1 is used.")
            except ValueError as error:
                st.error(str(error))

    template = ss("template")

    # ---- stickers & fonts ------------------------------------------------------
    with st.expander("Add your own stickers, logos, signatures or fonts"):
        s1, s2 = st.columns(2)
        with s1:
            transparent = st.checkbox("Make white background transparent (for scanned signatures)", key="stk_white")
            sticker_files = st.file_uploader("Stickers / logos / signature images (PNG or JPG)",
                                             type=["png", "jpg", "jpeg"], accept_multiple_files=True, key="stk_up")
            for f in sticker_files or []:
                raw = f.getvalue()
                sid = "u:" + sha(raw, transparent)[:10]
                if sid not in st.session_state["sticker_store"]:
                    try:
                        st.session_state["sticker_store"][sid] = (
                            Path(f.name).stem[:24], stk.prepare_uploaded_sticker(raw, transparent))
                    except ValueError as error:
                        st.error(f"{f.name}: {error}")
        with s2:
            font_file = st.file_uploader("Your own font (.ttf)", type=["ttf"], key="font_up")
            if font_file is not None and Path(font_file.name).stem not in fonts.available_families():
                try:
                    fonts.register_custom_font(Path(font_file.name).stem, font_file.getvalue())
                    st.success(f"Font “{Path(font_file.name).stem}” added — choose it in the editor.")
                except ValueError as error:
                    st.error(str(error))
            st.caption("Tip: for Hindi/Telugu names pick “Hind” / “Hind Guntur” in the font list.")

    builtin = stk.builtin_sticker_bytes()
    all_stickers = {**builtin, **st.session_state["sticker_store"]}
    sticker_bytes = {sid: data for sid, (_, data) in all_stickers.items()}

    if template is None:
        st.stop() if False else None
    else:
        # ---- which participant to preview -------------------------------------
        ready_by_rid = {r["rid"]: r for r in ready}
        if ready:
            longest = max(ready, key=lambda r: len(r["name"]))
            if ss("design_person") not in ready_by_rid:
                st.session_state["design_person"] = ready[0]["rid"]
            p1, p2 = st.columns([3, 1])
            p1.selectbox("Preview with participant", list(ready_by_rid), key="design_person",
                         format_func=lambda rid: f"Row {ready_by_rid[rid]['row']} · {ready_by_rid[rid]['name']}")
            p2.write("")
            p2.write("")
            p2.button("Preview longest name",
                      on_click=lambda: st.session_state.update(design_person=longest["rid"]),
                      width="stretch")
            sample_values = ready_by_rid[ss("design_person")]["values"]
        else:
            st.caption("No data loaded yet — previewing with a sample name.")
            sample_values = DUMMY
        sample_values = {**sample_values}

        st.caption(f"💡 {ss('placement_note', '')}  Drag things around, then check the exact result below.")
        layout = cert_editor(
            template=template, layout=ss("layout"), stickers=all_stickers, placeholders=AVAILABLE,
            sample=sample_values, sample_label=sample_values.get("Name", ""),
            token=f"{template.key[:6]}-{ss('layout_counter')}", key="cert_editor")
        st.session_state["layout"] = layout

        b1, b2, b3 = st.columns([1.3, 1.3, 2])
        if b1.button("↺ Re-do smart placement", help="Moves the name to the best spot and removes other items."):
            position = ai_helpers.suggest_name_position(template.preview_image())
            st.session_state["layout"] = certs.default_layout(position)
            st.session_state["placement_note"] = position["reason"]
            st.session_state["layout_counter"] += 1
            st.rerun()
        used_ids = {e["src"] for e in layout.get("elements", []) if e.get("type") == "image"}
        design_json = json.dumps({
            "layout": layout,
            "stickers": {sid: {"name": all_stickers[sid][0], "png": base64.b64encode(all_stickers[sid][1]).decode()}
                         for sid in used_ids if sid in all_stickers and sid.startswith("u:")},
        })
        b2.download_button("💾 Save this design", design_json, "certificate_design.json", "application/json",
                           help="Saves positions, fonts, colours and your stickers (not the template picture).")
        with b3:
            loaded = st.file_uploader("Load a saved design", type=["json"], key="design_load",
                                      label_visibility="collapsed")
            if loaded is not None and ss("_seen_design") != loaded.file_id:
                st.session_state["_seen_design"] = loaded.file_id
                try:
                    saved = json.loads(loaded.getvalue().decode("utf-8"))
                    for sid, item in saved.get("stickers", {}).items():
                        st.session_state["sticker_store"][sid] = (item["name"], base64.b64decode(item["png"]))
                    if not isinstance(saved["layout"].get("elements"), list):
                        raise ValueError("no elements")
                    st.session_state["layout"] = saved["layout"]
                    st.session_state["layout_counter"] += 1
                    st.rerun()
                except (ValueError, KeyError, TypeError, AttributeError):
                    st.error("That file is not a saved design.")

        # ---- exact preview + checks ---------------------------------------------
        st.markdown("##### Exact result for this participant")
        sticker_sig = sha(*sorted(sticker_bytes))
        png, notes = cached_preview(template.key, json.dumps(layout, sort_keys=True),
                                    json.dumps(sample_values, sort_keys=True), sticker_sig, template, sticker_bytes)
        st.image(png, width="stretch")

        texts = all_text_in_layout(layout)
        unknown = sorted({u for t in texts for u in dp.unknown_placeholders(t, AVAILABLE)})
        if unknown:
            st.error("These placeholders don't match any column: " + ", ".join("{{" + u + "}}" for u in unknown)
                     + ". Check the spelling against your spreadsheet headings.")
        name_keys = {"name"} | ({dp.norm_key(mapping["name"])} if mapping["name"] else set())
        if not any(dp.norm_key(k) in name_keys for t in texts for k in dp.find_placeholders(t)):
            st.warning("Your certificate has no {{Name}} text — add one, or every certificate will look the same.")
        for note in notes:
            if note.get("missing_image"):
                st.warning("A sticker used in this design is missing — add it again or delete it from the design.")
        if ready:
            glyphs = certs.missing_glyph_report(layout, ready)
            if glyphs:
                st.error(f"{len(glyphs)} participant(s) have characters this font can't draw (they would print blank). "
                         "Pick a font that supports their language.")
                st.dataframe(pd.DataFrame(glyphs).head(10), hide_index=True)
            tight = certs.fit_report(layout, ready)
            if tight:
                st.warning(f"{len(tight)} participant(s) have long text that shrinks a lot to fit "
                           "(shown below). You can widen the text box or allow wrapping.")
                st.dataframe(pd.DataFrame(tight).head(10), hide_index=True)

# ============================================================================
# ③ EMAIL
# ============================================================================
with tab_email:
    st.subheader("Who is sending, and what should the email say?")
    e1, e2 = st.columns([1, 1.25], gap="large")

    # ---- sender --------------------------------------------------------------
    with e1:
        st.markdown("##### Send from")
        sender_email = st.text_input("Your email address", key="sender_email", placeholder="you@gmail.com").strip()
        provider_default = mail.guess_provider(sender_email)
        provider = st.selectbox("Mail provider", list(mail.PROVIDERS), key="provider",
                                index=list(mail.PROVIDERS).index(provider_default))
        cfg = dict(mail.PROVIDERS[provider])
        if provider.startswith("Other"):
            h1, h2, h3 = st.columns([2, 1, 1.4])
            cfg["host"] = h1.text_input("SMTP server", key="smtp_host", placeholder="smtp.yourcollege.edu")
            cfg["port"] = h2.number_input("Port", 1, 65535, 465, key="smtp_port")
            cfg["security"] = h3.selectbox("Security", ["ssl", "starttls", "none"], key="smtp_sec")
        sender_password = st.text_input("App password", type="password", key="sender_pw",
                                        help=mail.APP_PASSWORD_HELP[provider])
        st.caption(mail.APP_PASSWORD_HELP[provider])
        n1, n2 = st.columns(2)
        sender_name = n1.text_input("Sender name shown to students", key="sender_name",
                                    placeholder="e.g. Team MIRAETECH")
        reply_to = n2.text_input("Reply-to address (optional)", key="reply_to")
        st.caption("🔒 Your password stays in this browser session only. It is never saved to disk or to GitHub.")
        if st.button("Check login (sends nothing)"):
            if not sender_email or not sender_password:
                st.warning("Enter the email address and app password first.")
            elif not cfg.get("host"):
                st.warning("Enter the SMTP server.")
            else:
                with st.spinner("Connecting…"):
                    ok, message = mail.check_login(cfg["host"], int(cfg["port"]), cfg["security"],
                                                   sender_email, sender_password.replace(" ", ""))
                (st.success if ok else st.error)(message)

    # ---- message -----------------------------------------------------------------
    with e2:
        st.markdown("##### Message")
        tone_col, btn_col = st.columns([3, 1.3])
        tone = tone_col.selectbox("Start from a ready-made wording", list(ai_helpers.TONES), key="tone",
                                  index=list(ai_helpers.TONES).index("Celebratory"))
        btn_col.write("")
        btn_col.write("")
        btn_col.button("Use this wording", on_click=lambda: st.session_state.update(
            email_subject=ai_helpers.TONES[ss("tone", "Formal")][0],
            email_body=ai_helpers.TONES[ss("tone", "Formal")][1]), width="stretch")

        with st.expander("✨ Write it with AI (optional)"):
            st.caption("Describe the event in a sentence or two. **Only that description is sent to the AI — "
                       "never participant names or emails.** You can edit the result before using it.")
            a1, a2 = st.columns(2)
            ai_provider = a1.selectbox("AI service", list(ai_helpers.AI_PROVIDERS), key="ai_provider")
            ai_model = a2.text_input("Model", value=ai_helpers.AI_PROVIDERS[ai_provider]["model"],
                                     key=f"ai_model_{ai_provider}")
            ai_key = st.text_input("Your API key", type="password", key="ai_key",
                                   help=ai_helpers.AI_PROVIDERS[ai_provider]["help"])
            ai_prompt = st.text_area("What should the email say?", key="ai_prompt", height=80,
                                     placeholder="e.g. Thank participants of our 2-day robotics workshop, "
                                                 "congratulate them, mention the certificate is attached.")
            if st.button("Write my email"):
                try:
                    with st.spinner("Writing…"):
                        subject, body = ai_helpers.draft_email_with_ai(
                            ai_provider, ai_key, ai_prompt, ["Name", "Event", "Organizer", "Date"], ai_model)
                    st.session_state["ai_draft"] = (subject, body)
                except ai_helpers.AIError as error:
                    st.error(str(error))
            if ss("ai_draft"):
                subject, body = ss("ai_draft")
                st.markdown(f"**Subject:** {subject}")
                st.text(body)
                st.button("Use this draft", key="use_ai", on_click=lambda: st.session_state.update(
                    email_subject=ss("ai_draft")[0], email_body=ss("ai_draft")[1]))

        st.text_input("Subject", key="email_subject")
        st.text_area("Message", key="email_body", height=260)
        st.caption("Placeholders you can use: " + "  ".join(f"`{{{{{k}}}}}`" for k in AVAILABLE[:14]))
        st.caption("The certificate is attached automatically as a PDF.")

    # ---- preview ---------------------------------------------------------------------
    st.markdown("##### Preview")
    pv_values = ready[0]["values"] if ready else DUMMY
    if ready:
        pv = st.selectbox("Show the email for", [r["rid"] for r in ready], key="email_person",
                          format_func=lambda rid: next(f"Row {r['row']} · {r['name']}" for r in ready if r["rid"] == rid))
        pv_values = next(r["values"] for r in ready if r["rid"] == pv)
    with st.container(border=True):
        st.markdown(f"**To:** {pv_values.get('Email', '')}")
        st.markdown(f"**Subject:** {dp.render_placeholders(ss('email_subject', ''), pv_values)}")
        st.text(dp.render_placeholders(ss("email_body", ""), pv_values))
        st.caption("📎 Certificate_<name>.pdf")

# ============================================================================
# ④ REVIEW & SEND
# ============================================================================
with tab_send:
    st.subheader("Generate, review and send")
    layout = ss("layout")
    template = ss("template")
    texts_cert = all_text_in_layout(layout) if layout else []
    texts_mail = [ss("email_subject", ""), ss("email_body", "")]

    problems_found = []
    if not ready:
        problems_found.append("Step ① – no valid participants yet.")
    if template is None or not layout:
        problems_found.append("Step ② – choose a template.")
    unknown_all = sorted({u for t in texts_cert + texts_mail for u in dp.unknown_placeholders(t, AVAILABLE)})
    if unknown_all:
        problems_found.append("Unknown placeholders: " + ", ".join("{{" + u + "}}" for u in unknown_all))
    # blank values used by placeholders
    blank_notes = []
    for key in {k for t in texts_cert + texts_mail for k in dp.find_placeholders(t)} - set(unknown_all):
        empty = sum(1 for r in ready if not str(next((v for k2, v in r["values"].items()
                                                       if dp.norm_key(k2) == dp.norm_key(key)), "")).strip())
        if empty:
            blank_notes.append(f"{{{{{key}}}}} is empty for {empty} participant(s)")
    for line in problems_found:
        st.error(line)
    for line in blank_notes:
        st.warning(line)

    sticker_sig = sha(*sorted(sticker_bytes))
    current_sig = sha(template.key if template else "", json.dumps(layout, sort_keys=True) if layout else "",
                      json.dumps([(r["rid"], r["values"]) for r in ready], sort_keys=True), sticker_sig)
    generated = ss("generated")
    up_to_date = bool(generated and generated["sig"] == current_sig)

    st.markdown("##### 1 · Generate the certificates")
    g1, g2 = st.columns([1, 2])
    if g1.button(f"Generate {len(ready)} certificates", type="primary",
                 disabled=bool(problems_found) or not ready):
        items, used_names = {}, {}
        bar = g2.progress(0.0, text="Starting…")
        t0 = time.time()
        for number, record in enumerate(ready, start=1):
            base = "Certificate_" + safe_filename(record["name"])
            used_names[base] = used_names.get(base, 0) + 1
            filename = base + (f"_{record['row']}" if used_names[base] > 1 else "") + ".pdf"
            try:
                pdf = certs.render_certificate(template, layout, record["values"], sticker_bytes)
                items[record["rid"]] = {"pdf": pdf, "filename": filename, "error": ""}
            except Exception as error:  # noqa: BLE001 - keep going with the others
                items[record["rid"]] = {"pdf": None, "filename": filename, "error": str(error)}
            bar.progress(number / len(ready), text=f"{number}/{len(ready)} · {record['name']}")
        archive = io.BytesIO()
        with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as z:
            for item in items.values():
                if item["pdf"]:
                    z.writestr(item["filename"], item["pdf"])
        st.session_state["generated"] = generated = {"sig": current_sig, "items": items, "zip": archive.getvalue(),
                                                       "seconds": time.time() - t0}
        up_to_date = True
        bar.empty()

    if generated:
        failed_gen = [rid for rid, it in generated["items"].items() if not it["pdf"]]
        if not up_to_date:
            st.warning("The data, template or design changed after you generated. Generate again before sending.")
        else:
            okc = len(generated["items"]) - len(failed_gen)
            g2.success(f"{okc} certificates ready ({generated['seconds']:.1f}s).")
            st.download_button("⬇ Download all as ZIP", generated["zip"], "certificates.zip", "application/zip")
        if failed_gen:
            st.error(f"{len(failed_gen)} certificate(s) could not be made: " + "; ".join(
                f"{ready_by_rid.get(r, {}).get('name', r)} ({generated['items'][r]['error'][:80]})" for r in failed_gen[:5]))

    # ------------------------------------------------------------------ sending
    st.markdown("##### 2 · Choose recipients")
    sender_ok = bool(sender_email and dp.EMAIL_RE.match(sender_email) and sender_password)
    sent_earlier = read_sent_log()
    event_for_key = ss("batch_event", "")

    def send_key(record: dict) -> str:
        return sha(sender_email.lower(), record["email"].lower(), record["name"].lower(), event_for_key.lower())

    allow_resend = st.checkbox("Send again even to people already emailed", key="allow_resend")

    def status_label(record) -> str:
        key = send_key(record)
        current = ss("send_status", {}).get(key)
        if current:
            return {"sent": "Sent ✅", "failed": "Failed ❌", "unconfirmed": "Unconfirmed ⚠️"}[current["status"]]
        if key in sent_earlier:
            return "Sent earlier ✅"
        return "Pending"

    rows = []
    for record in ready:
        label = status_label(record)
        item = (generated or {}).get("items", {}).get(record["rid"], {})
        rows.append({
            "Send": label in ("Pending", "Failed ❌") or (allow_resend and label.startswith("Sent")),
            "Row": record["row"], "Name": record["name"], "Email": record["email"],
            "Certificate": item.get("filename", "—"), "Status": label,
            "Custom message": "yes" if record["rid"] in ss("overrides", {}) else "",
        })
    selected_records: list[dict] = []
    if rows:
        table = st.data_editor(pd.DataFrame(rows), hide_index=True, width="stretch", key="send_table",
                               disabled=["Row", "Name", "Email", "Certificate", "Status", "Custom message"],
                               column_config={"Send": st.column_config.CheckboxColumn("Send?", width="small")})
        selected_rows = set(table.loc[table["Send"], "Row"])
        selected_records = [r for r in ready if r["row"] in selected_rows]
        st.caption(f"{len(selected_records)} of {len(ready)} selected. **First time?** Untick everyone except two "
                   "addresses you control, send, and check those inboxes before sending to everybody.")
        if len(selected_records) > 400:
            st.warning("Gmail allows roughly 500 emails per day for normal accounts. Consider sending in two days.")

    with st.expander("Personalise one person's email (optional)"):
        if ready:
            who = st.selectbox("Person", [r["rid"] for r in ready], key="override_person",
                               format_func=lambda rid: next(f"Row {r['row']} · {r['name']}" for r in ready if r["rid"] == rid))
            rec = next(r for r in ready if r["rid"] == who)
            current = ss("overrides", {}).get(who)
            ov_subject = st.text_input("Subject for this person", key=f"ov_s_{who}",
                                       value=current["subject"] if current else dp.render_placeholders(ss("email_subject", ""), rec["values"]))
            ov_body = st.text_area("Message for this person", key=f"ov_b_{who}", height=200,
                                   value=current["body"] if current else dp.render_placeholders(ss("email_body", ""), rec["values"]))
            o1, o2 = st.columns(2)
            if o1.button("Save for this person"):
                st.session_state["overrides"][who] = {"subject": ov_subject, "body": ov_body}
                st.rerun()
            if current and o2.button("Remove custom message"):
                st.session_state["overrides"].pop(who, None)
                st.rerun()
            st.caption("A saved custom message is sent exactly as written (placeholders are already filled in).")

    st.markdown("##### 3 · Send")
    if not sender_ok:
        st.warning("Enter your email address and app password in step ③ first.")
    if generated and not up_to_date:
        st.warning("Generate the certificates again first (see above).")
    sd1, sd2 = st.columns([2, 1])
    confirmed = sd1.checkbox("I checked the recipients, the email and the certificates, and I want to send now.",
                             key="confirm_send")
    pause_s = sd2.number_input("Pause between emails (seconds)", 0.0, 10.0, 1.0, 0.5, key="pause_s",
                               help="A short pause keeps Gmail and college servers happy.")
    can_send = (sender_ok and up_to_date and confirmed and bool(selected_records) and not problems_found
                and bool(cfg.get("host")))

    if st.button(f"✉️ Send {len(selected_records)} certificate(s)", type="primary", disabled=not can_send):
        remaining = [r for r in selected_records
                     if allow_resend or not status_label(r).startswith("Sent")]
        skipped = len(selected_records) - len(remaining)
        mailer = mail.Mailer(cfg["host"], int(cfg["port"]), cfg["security"], sender_email,
                             sender_password.replace(" ", ""))
        live = st.empty()
        bar = st.progress(0.0)
        feed: list[dict] = []
        try:
            mailer.connect()
        except Exception as error:  # noqa: BLE001
            ok, message = False, "Could not log in to the mail server. Nothing was sent."
            st.error(message + " Use “Check login” in step ③ to see the exact problem.")
            remaining = []
        for position, record in enumerate(remaining, start=1):
            item = generated["items"][record["rid"]]
            override = ss("overrides", {}).get(record["rid"])
            subject = override["subject"] if override else dp.render_placeholders(ss("email_subject", ""), record["values"])
            body = override["body"] if override else dp.render_placeholders(ss("email_body", ""), record["values"])
            message = mail.build_message(sender_email, sender_name, record["email"], subject, body,
                                         item["pdf"], item["filename"], reply_to)
            result = mailer.send(message)
            key = send_key(record)
            stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            st.session_state["send_status"][key] = {"status": result.status, "detail": result.detail, "time": stamp}
            append_sent_log({"time": stamp, "key": key, "status": result.status, "sender": sender_email,
                             "email": record["email"], "name": record["name"], "detail": result.detail})
            feed.append({"Name": record["name"], "Email": record["email"], "Result": result.status.title(),
                         "Detail": result.detail})
            live.dataframe(pd.DataFrame(feed[-8:]), hide_index=True, width="stretch")
            bar.progress(position / len(remaining), text=f"{position}/{len(remaining)}")
            if result.fatal:
                st.error(f"Stopped: {result.detail}")
                break
            mail.pause(pause_s)
        mailer.close()
        sent_n = sum(f["Result"] == "Sent" for f in feed)
        failed_n = sum(f["Result"] == "Failed" for f in feed)
        unconf_n = sum(f["Result"] == "Unconfirmed" for f in feed)
        st.session_state["last_run"] = {"sent": sent_n, "failed": failed_n, "unconfirmed": unconf_n, "skipped": skipped}
        st.rerun()

    last = ss("last_run")
    if last:
        st.success(f"Last run — sent: {last['sent']} · failed: {last['failed']} · "
                   f"unconfirmed: {last['unconfirmed']} · skipped (already sent): {last['skipped']}")
        if last["failed"]:
            st.info("Failed ones are ticked again above — fix the cause (e.g. a wrong address) and press Send to retry.")
        if last["unconfirmed"]:
            st.warning("“Unconfirmed” means the connection dropped while sending. Look in the Sent folder of "
                       f"{sender_email or 'your mailbox'} before sending those again.")

    if ready and ss("send_status"):
        report_rows = []
        for record in ready:
            current = ss("send_status", {}).get(send_key(record))
            if current:
                report_rows.append({"Row": record["row"], "Name": record["name"], "Email": record["email"],
                                    "Status": current["status"], "Detail": current["detail"], "Time": current["time"]})
        if report_rows:
            st.download_button("⬇ Download sending report (CSV)",
                               pd.DataFrame(report_rows).to_csv(index=False).encode("utf-8-sig"),
                               "sending_report.csv", "text/csv")
    st.caption("“Sent” means the mail server accepted the message — it can't promise the student's inbox "
               "(they might need to check Spam).")

# ----------------------------------------------------------------------------
# Sidebar
# ----------------------------------------------------------------------------
with st.sidebar:
    sent_count = sum(1 for v in ss("send_status", {}).values() if v["status"] == "sent")
    st.markdown(theme.sidebar_html([
        ("Data", f"{len(ready)} participants ready" if ready else "Upload your spreadsheet", bool(ready)),
        ("Design", "Template chosen" if ss("template") else "Pick a template", bool(ss("template"))),
        ("Email & sender", "Ready to send" if ss("email_body") and sender_ok else "Add address & app password",
         bool(ss("email_body") and sender_ok)),
        ("Certificates", "Generated" if ss("generated") else "Not generated yet", bool(ss("generated"))),
        ("Sent", f"{sent_count} emailed" if sent_count else "Nothing sent yet", bool(sent_count)),
    ]), unsafe_allow_html=True)
    if st.button("↺ Start over", width="stretch"):
        for key in list(st.session_state.keys()):
            del st.session_state[key]
        st.rerun()
    st.markdown('<div class="sb-foot">Team MIRAETECH</div>', unsafe_allow_html=True)

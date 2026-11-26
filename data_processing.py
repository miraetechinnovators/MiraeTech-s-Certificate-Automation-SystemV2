"""Reading spreadsheets, detecting columns, validating records, placeholders.

Everything here is plain Python/pandas (no Streamlit), so it is easy to test
and easy to edit.
"""
from __future__ import annotations

import csv
import difflib
import re
from io import BytesIO, StringIO

import pandas as pd

EMAIL_RE = re.compile(r"^[^@\s,;<>()\[\]\"']+@[^@\s,;<>()\[\]\"']+\.[A-Za-z]{2,}$")
PLACEHOLDER_RE = re.compile(r"\{\{\s*([^{}]+?)\s*\}\}")

POPULAR_DOMAINS = [
    "gmail.com", "yahoo.com", "yahoo.in", "outlook.com", "hotmail.com",
    "live.com", "icloud.com", "rediffmail.com", "proton.me", "protonmail.com",
]


# --------------------------------------------------------------------------
# Reading files
# --------------------------------------------------------------------------
def _decode_csv(data: bytes) -> str:
    for encoding in ("utf-8-sig", "utf-16", "cp1252", "latin-1"):
        try:
            return data.decode(encoding)
        except (UnicodeDecodeError, UnicodeError):
            continue
    return data.decode("utf-8", errors="replace")


def excel_sheet_names(data: bytes) -> list[str]:
    return list(pd.ExcelFile(BytesIO(data)).sheet_names)


def load_table(data: bytes, filename: str, sheet: str | int | None = None) -> pd.DataFrame:
    """Read a CSV / Excel file into a DataFrame of cleaned strings."""
    name = filename.lower()
    if name.endswith((".xlsx", ".xlsm", ".xls")):
        frame = pd.read_excel(
            BytesIO(data), sheet_name=sheet if sheet is not None else 0,
            dtype=str, keep_default_na=False,
        )
    else:
        text = _decode_csv(data)
        try:
            delimiter = csv.Sniffer().sniff(text[:4096], delimiters=",;\t|").delimiter
        except csv.Error:
            delimiter = ","
        frame = pd.read_csv(StringIO(text), sep=delimiter, dtype=str, keep_default_na=False)

    frame.columns = [re.sub(r"\s+", " ", str(c)).strip() for c in frame.columns]
    for column in frame.columns:
        frame[column] = frame[column].astype(str).str.strip()
    # Drop completely empty rows and columns (very common in Excel exports).
    frame = frame.loc[frame.apply(lambda row: row.ne("").any(), axis=1)]
    keep = [c for c in frame.columns if frame[c].ne("").any() or not c.lower().startswith("unnamed")]
    frame = frame[keep]
    return frame.reset_index(drop=True)


# --------------------------------------------------------------------------
# Smart column detection
# --------------------------------------------------------------------------
def _norm_header(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", str(text).lower()).strip()


_NAME_EXACT = {
    "name", "full name", "student name", "participant name", "candidate name",
    "attendee name", "name of the participant", "name of participant",
    "name of the student", "winner name", "recipient name",
}
_NAME_BAD_WORDS = {
    "file", "user", "event", "team", "college", "school", "company", "father",
    "mother", "parent", "guardian", "course", "branch", "department",
    "project", "organisation", "organization", "institute", "university",
}


def _email_ratio(series: pd.Series) -> float:
    values = [v for v in series if v]
    if not values:
        return 0.0
    return sum(bool(EMAIL_RE.match(v)) for v in values) / len(values)


def _name_like_ratio(series: pd.Series) -> float:
    values = [v for v in series if v]
    if not values:
        return 0.0
    good = 0
    for value in values:
        words = value.split()
        if 1 <= len(words) <= 5 and re.fullmatch(r"[^\W\d_][\w .'\-]{0,60}", value):
            good += 1
    return good / len(values)


def detect_columns(frame: pd.DataFrame) -> dict:
    """Guess which columns hold the participant name and email address(es).

    Uses both the column heading AND the values inside the column, so it still
    works when the heading is unusual (e.g. "Candidate" or "Mail ID").
    """
    columns = list(frame.columns)

    total = max(1, len(frame))
    email_rank = {}
    email_candidates = []
    for col in columns:
        header = _norm_header(col)
        non_empty = [v for v in frame[col] if v]
        valid = sum(bool(EMAIL_RE.match(v)) for v in non_empty)
        looks_like_email = bool(non_empty) and valid / len(non_empty) >= 0.6
        if "mail" in header or looks_like_email:
            email_candidates.append(col)
            # best primary = the column that actually has the most valid addresses
            email_rank[col] = valid / total + (0.5 if "mail" in header else 0.0)
    email_candidates.sort(key=lambda c: (-round(email_rank[c], 3), columns.index(c)))

    name_scores = {}
    for col in columns:
        if col in email_candidates:
            continue
        header = _norm_header(col)
        words = set(header.split())
        score = 0.0
        if header in _NAME_EXACT:
            score += 3.0
        elif "name" in words and not (words & _NAME_BAD_WORDS):
            score += 2.0
        elif "name" in header and not (words & _NAME_BAD_WORDS):
            score += 1.5
        elif header in {"candidate", "participant", "student", "attendee", "winner", "recipient"}:
            score += 1.5
        if score or _name_like_ratio(frame[col]) > 0.9:
            # content bonus (names are short, alphabetic, 1-5 words)
            score += _name_like_ratio(frame[col])
        if re.search(r"\b(id|roll|number|no|phone|mobile|contact|date|year|class)\b", header):
            score -= 2.0
        name_scores[col] = score
    name_col = None
    if name_scores:
        best = max(name_scores, key=lambda c: (name_scores[c], -columns.index(c)))
        if name_scores[best] >= 1.0:
            name_col = best

    return {
        "name": name_col,
        "email": email_candidates[0] if email_candidates else None,
        "email_fallback": email_candidates[1] if len(email_candidates) > 1 else None,
        "email_candidates": email_candidates,
    }


# --------------------------------------------------------------------------
# Names, emails, placeholders
# --------------------------------------------------------------------------
def _title_token(token: str) -> str:
    if not token:
        return token
    if "." in token.strip(".") and len(token) <= 6:      # initials like "a.v."
        return token.upper()
    if re.fullmatch(r"[ivxIVX]{2,4}", token):             # II, III, IV
        return token.upper()
    pieces = re.split(r"([\-'’])", token)
    return "".join(p.capitalize() if p not in "-'’" else p for p in pieces)


def format_name(name: str, mode: str = "fix") -> str:
    """mode: 'keep' | 'fix' (fix ALL-CAPS / all-lowercase only) | 'title' | 'upper'"""
    name = re.sub(r"\s+", " ", str(name)).strip()
    if mode == "upper":
        return name.upper()
    letters = re.sub(r"[^A-Za-z]", "", name)
    needs_fix = bool(letters) and (letters.islower() or letters.isupper())
    if mode == "title" or (mode == "fix" and needs_fix):
        return " ".join(_title_token(t) for t in name.split(" "))
    return name


def norm_key(key: str) -> str:
    return re.sub(r"\s+", " ", str(key).strip()).casefold()


def find_placeholders(text: str) -> list[str]:
    return list(dict.fromkeys(m.group(1).strip() for m in PLACEHOLDER_RE.finditer(text or "")))


def unknown_placeholders(text: str, available) -> list[str]:
    known = {norm_key(k) for k in available}
    return [p for p in find_placeholders(text) if norm_key(p) not in known]


def render_placeholders(text: str, values: dict) -> str:
    """Replace {{Column}} with the participant's value (case-insensitive).
    Unknown placeholders are left visible so mistakes are easy to spot."""
    lookup = {norm_key(k): v for k, v in values.items()}

    def swap(match):
        key = norm_key(match.group(1))
        return str(lookup[key]) if key in lookup else match.group(0)

    return PLACEHOLDER_RE.sub(swap, text or "")


def email_typo_hint(email: str) -> str | None:
    """Return a suggestion like 'gmail.com' when the domain looks mistyped."""
    domain = email.rsplit("@", 1)[-1].lower()
    if domain in POPULAR_DOMAINS:
        return None
    close = difflib.get_close_matches(domain, POPULAR_DOMAINS, n=1, cutoff=0.84)
    return close[0] if close else None


# --------------------------------------------------------------------------
# Building and validating records
# --------------------------------------------------------------------------
def prepare_records(
    frame: pd.DataFrame,
    name_col: str,
    email_col: str,
    fallback_col: str | None = None,
    name_mode: str = "fix",
    batch_values: dict | None = None,
) -> list[dict]:
    """Turn the spreadsheet into validated records.

    Every record keeps its OWN values together (name, email, certificate
    values), so a certificate can never be attached to the wrong person.
    """
    batch_values = {k: v for k, v in (batch_values or {}).items()}
    records: list[dict] = []
    seen_pair: dict[tuple[str, str], int] = {}
    seen_email: dict[str, int] = {}

    for index, row in frame.iterrows():
        source_row = int(index) + 2          # row 1 is the heading row
        raw = {col: str(row[col]).strip() for col in frame.columns}
        issues: list[str] = []
        warnings: list[str] = []

        name = format_name(raw.get(name_col, ""), name_mode)
        if not name:
            issues.append("Missing name")

        primary = raw.get(email_col, "").strip()
        fallback = raw.get(fallback_col, "").strip() if fallback_col else ""
        email, email_source = "", ""
        if primary and EMAIL_RE.match(primary):
            email, email_source = primary, "main"
        elif fallback and EMAIL_RE.match(fallback):
            email, email_source = fallback, "fallback"
            warnings.append("Main email was missing/invalid - using the fallback email")
        elif not primary and not fallback:
            issues.append("Missing email")
        else:
            issues.append("Invalid email: " + (primary or fallback))

        if email:
            hint = email_typo_hint(email)
            if hint:
                warnings.append(f"Email domain looks like a typo (did you mean {hint}?)")

        pair = (email.casefold(), name.casefold())
        if email and name:
            if pair in seen_pair:
                issues.append(f"Duplicate of row {seen_pair[pair]}")
            else:
                seen_pair[pair] = source_row
                other = seen_email.get(email.casefold())
                if other:
                    warnings.append(f"Same email as row {other} but a different name")
            seen_email.setdefault(email.casefold(), source_row)

        # Values available to {{placeholders}} in the certificate and the email.
        values = dict(raw)
        lowered = {norm_key(k): k for k in values}
        for key, default in batch_values.items():
            existing = lowered.get(norm_key(key))
            if existing is None:
                values[key] = default
            elif not values[existing]:
                values[existing] = default
        values["Name"] = name
        values["Email"] = email

        status = "Ready"
        if issues:
            status = "Duplicate (skipped)" if issues[0].startswith("Duplicate") and len(issues) == 1 \
                else "Needs correction"

        records.append({
            "rid": f"r{source_row}",
            "row": source_row,
            "name": name,
            "email": email,
            "email_source": email_source,
            "values": values,
            "status": status,
            "issues": issues,
            "warnings": warnings,
        })
    return records


def records_to_frame(records: list[dict]) -> pd.DataFrame:
    return pd.DataFrame([
        {
            "Row": r["row"],
            "Name": r["name"],
            "Email": r["email"],
            "Status": r["status"],
            "Problems": "; ".join(r["issues"]),
            "Warnings": "; ".join(r["warnings"]),
        }
        for r in records
    ])


def available_placeholders(frame_columns, batch_keys) -> list[str]:
    """All keys usable as {{placeholders}} (Name/Email first)."""
    keys = ["Name", "Email"]
    for key in list(frame_columns) + list(batch_keys):
        if norm_key(key) not in {norm_key(k) for k in keys}:
            keys.append(key)
    return keys

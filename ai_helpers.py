"""Smart helpers.

1. suggest_name_position()  - looks at the template picture and finds the best
   spot for the participant's name (a blank line, or the biggest empty area).
   Pure image analysis, works offline.

2. draft_email_offline()    - ready-made email wording in different tones.

3. draft_email_with_ai()    - OPTIONAL. Uses Claude or Gemini (the organiser's
   own API key) to write the email from a one-line description.
   Only the event description you type is sent. No participant names or
   emails are ever sent to the AI service.
"""
from __future__ import annotations

import json
import re
import urllib.error
import urllib.request

import numpy as np
from PIL import Image, ImageFilter


# --------------------------------------------------------------------------
# 1. Smart name placement
# --------------------------------------------------------------------------
def _largest_empty_rectangle(empty: np.ndarray, height_cap: int = 6) -> tuple[int, int, int, int]:
    """Largest all-True rectangle in a boolean grid -> (row, col, height, width)."""
    rows, cols = empty.shape
    heights = np.zeros(cols, dtype=int)
    best = (0, 0, 0, 0)
    best_area = 0
    for r in range(rows):
        heights = np.where(empty[r], heights + 1, 0)
        stack: list[int] = []
        for c in range(cols + 1):
            h = heights[c] if c < cols else 0
            start = c
            while stack and heights[stack[-1]] >= h:
                idx = stack.pop()
                height = heights[idx]
                left = stack[-1] + 1 if stack else 0
                area = min(int(height), height_cap) * (c - left)
                if area > best_area:
                    best_area = area
                    best = (r - height + 1, left, int(height), int(c - left))
            stack.append(c)
    return best


def suggest_name_position(image: Image.Image) -> dict:
    """Return {"x","y","w","reason"} - anchor (x, baseline y) and width limit, all as
    fractions of the page, for a centred participant name."""
    gray_img = image.convert("L")
    width = 800
    height = max(1, round(gray_img.height * width / gray_img.width))
    gray_img = gray_img.resize((width, height), Image.LANCZOS)
    gray = np.asarray(gray_img, dtype=float)

    # --- A. look for a blank line ("____") where a name is meant to be written
    local_mean = np.asarray(gray_img.filter(ImageFilter.BoxBlur(10)), dtype=float)
    ink = gray < local_mean - 28
    best = None
    min_run = int(width * 0.16)
    for y in range(int(height * 0.28), int(height * 0.74)):
        row = ink[y]
        # longest run of True
        padded = np.concatenate(([0], row.astype(int), [0]))
        diff = np.diff(padded)
        starts, ends = np.where(diff == 1)[0], np.where(diff == -1)[0]
        if len(starts) == 0:
            continue
        lengths = ends - starts
        k = int(np.argmax(lengths))
        if lengths[k] < min_run:
            continue
        x0, x1 = int(starts[k]), int(ends[k])
        # a real writing line has empty space above it
        band = ink[max(0, y - int(height * 0.09)):max(1, y - 6), x0:x1]
        density = band.mean() if band.size else 1.0
        if density > 0.04:
            continue
        score = lengths[k] * (1 - density) - abs((x0 + x1) / 2 - width / 2) * 0.3
        if best is None or score > best[0]:
            best = (score, y, x0, x1)
    if best:
        _, y, x0, x1 = best
        line_width = (x1 - x0) / width
        return _finish({
            "x": ((x0 + x1) / 2) / width,
            "y": (y - 5) / height,
            "w": min(0.9, line_width * 1.05),
            "reason": "Found a blank line on the template - name placed just above it.",
        }, gray, width, height)

    # --- B. otherwise use the biggest empty area in the middle of the page
    cell = 16
    gh, gw = height // cell, width // cell
    grid = gray[:gh * cell, :gw * cell].reshape(gh, cell, gw, cell)
    flat = grid.std(axis=(1, 3)) < 9
    means = grid.mean(axis=(1, 3))
    # the page colour = the most common colour among flat cells (ignores coloured side bars)
    if flat.any():
        values, counts = np.unique((means[flat] // 12).astype(int), return_counts=True)
        background = float(values[int(np.argmax(counts))] * 12 + 6)
        flat = flat & (np.abs(means - background) < 24)
    lo, hi = int(gh * 0.25), int(gh * 0.80)
    r, c, h, w = _largest_empty_rectangle(flat[lo:hi], height_cap=max(2, int(gh * 0.16)))
    if h >= 2 and w >= gw * 0.25:
        center_x = (c + w / 2) / gw
        center_y = (lo + r + h / 2) / gh
        return _finish({
            "x": center_x, "y": min(0.9, center_y + 0.03), "w": min(0.9, w / gw * 0.95),
            "reason": "Placed in the largest empty area of the template.",
        }, gray, width, height)

    return _finish({"x": 0.5, "y": 0.55, "w": 0.6,
                    "reason": "Could not find an empty area - centred as a starting point."}, gray, width, height)


def _finish(result: dict, gray: np.ndarray, width: int, height: int) -> dict:
    """Plain floats (JSON-safe) + a text colour that is readable on this background."""
    x0 = int(max(0, (result["x"] - result["w"] / 2)) * width)
    x1 = int(min(1, (result["x"] + result["w"] / 2)) * width)
    y0 = int(max(0, result["y"] - 0.08) * height)
    y1 = int(min(1, result["y"] + 0.02) * height)
    patch = gray[y0:max(y1, y0 + 1), x0:max(x1, x0 + 1)]
    dark = bool(patch.size and patch.mean() < 110)
    out = {k: (float(v) if not isinstance(v, str) else v) for k, v in result.items()}
    out["color"] = "#f3e2a9" if dark else "#1b2a5a"
    return out


# --------------------------------------------------------------------------
# 2. Email wording without AI
# --------------------------------------------------------------------------
TONES = {
    "Formal": (
        "Your {{Event}} certificate",
        "Dear {{Name}},\n\n"
        "Thank you for your participation in {{Event}}. Please find your certificate "
        "attached to this email as a PDF.\n\n"
        "We appreciate your contribution and wish you every success in the future.\n\n"
        "Yours sincerely,\n{{Organizer}}",
    ),
    "Friendly": (
        "Congratulations, {{Name}}! Your {{Event}} certificate is here",
        "Hi {{Name}},\n\n"
        "Congratulations, and thank you for being part of {{Event}}! "
        "Your certificate is attached to this email (PDF).\n\n"
        "It was great having you with us - hope to see you at our next event.\n\n"
        "Cheers,\n{{Organizer}}",
    ),
    "Short & simple": (
        "Your certificate - {{Event}}",
        "Dear {{Name}},\n\nYour certificate for {{Event}} is attached.\n\nRegards,\n{{Organizer}}",
    ),
    "Celebratory": (
        "You did it, {{Name}}! Certificate for {{Event}}",
        "Dear {{Name}},\n\n"
        "Congratulations on your achievement at {{Event}}! "
        "We are delighted to present your personalised certificate, attached as a PDF.\n\n"
        "Your effort and enthusiasm made the event a success. Well done!\n\n"
        "Warm regards,\n{{Organizer}}",
    ),
}


def draft_email_offline(tone: str) -> tuple[str, str]:
    return TONES.get(tone, TONES["Formal"])


# --------------------------------------------------------------------------
# 3. Optional AI-written email
# --------------------------------------------------------------------------
AI_PROVIDERS = {
    "Claude (Anthropic)": {"model": "claude-sonnet-5-5", "help": "Key from console.anthropic.com"},
    "Gemini (Google AI Studio - free tier)": {"model": "gemini-2.5-flash", "help": "Free key from aistudio.google.com"},
}

_SYSTEM = (
    "You write short, polite emails that accompany a certificate attached as a PDF. "
    "Reply with ONLY a JSON object: {\"subject\": \"...\", \"body\": \"...\"}. "
    "Rules: plain text only (no markdown, no emoji); at most 140 words; the body must start "
    "with a greeting that uses {{Name}}; mention that the certificate is attached; "
    "you may use ONLY these placeholders exactly as written: {allowed}; "
    "do not invent dates, places, links, prizes or facts that the organiser did not state; "
    "end with a sign-off using {{Organizer}} when that placeholder is allowed."
)


class AIError(Exception):
    """Raised with a message that is safe to show to the organiser."""


def _http_json(url: str, payload: dict, headers: dict, timeout: int = 40) -> dict:
    request = urllib.request.Request(url, json.dumps(payload).encode(), headers=headers, method="POST")
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as error:
        detail = ""
        try:
            detail = error.read().decode("utf-8", "replace")[:300]
        except Exception:  # noqa: BLE001
            pass
        if error.code in (401, 403):
            raise AIError("The AI service rejected the API key. Check that it is correct.") from error
        if error.code == 404:
            raise AIError("The AI service does not know this model name. Change the model name and try again.") from error
        if error.code == 429:
            raise AIError("The AI service says you hit a usage limit. Wait a minute and try again.") from error
        raise AIError(f"The AI service returned an error ({error.code}). {detail}") from error
    except (urllib.error.URLError, TimeoutError, OSError) as error:
        raise AIError("Could not reach the AI service. Check your internet connection.") from error


def _parse_draft(text: str) -> tuple[str, str]:
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text, flags=re.I).strip()
    match = re.search(r"\{.*\}", text, flags=re.S)
    if not match:
        raise AIError("The AI reply was not in the expected format. Please try again.")
    try:
        data = json.loads(match.group(0))
        subject, body = str(data["subject"]).strip(), str(data["body"]).strip()
    except (ValueError, KeyError) as error:
        raise AIError("The AI reply was not in the expected format. Please try again.") from error
    if not subject or not body:
        raise AIError("The AI returned an empty email. Please try again.")
    return subject.replace("\n", " "), body


def draft_email_with_ai(provider: str, api_key: str, description: str, allowed: list[str],
                        model: str | None = None, base_url: str | None = None) -> tuple[str, str]:
    """Ask an AI model to draft (subject, body). `base_url` is only for testing."""
    if not api_key.strip():
        raise AIError("Enter an API key first.")
    if not description.strip():
        raise AIError("Describe the event or the message in one or two sentences first.")
    allowed_text = ", ".join("{{" + a + "}}" for a in allowed)
    system = _SYSTEM.replace("{allowed}", allowed_text)
    model = (model or AI_PROVIDERS[provider]["model"]).strip()

    if provider.startswith("Claude"):
        url = (base_url or "https://api.anthropic.com") + "/v1/messages"
        reply = _http_json(url, {
            "model": model, "max_tokens": 600, "system": system,
            "messages": [{"role": "user", "content": description.strip()}],
        }, {"x-api-key": api_key.strip(), "anthropic-version": "2023-06-01",
            "content-type": "application/json"})
        try:
            text = "".join(block.get("text", "") for block in reply["content"])
        except (KeyError, TypeError) as error:
            raise AIError("Unexpected reply from the AI service.") from error
    else:
        url = (base_url or "https://generativelanguage.googleapis.com") + \
            f"/v1beta/models/{model}:generateContent"
        reply = _http_json(url, {
            "systemInstruction": {"parts": [{"text": system}]},
            "contents": [{"role": "user", "parts": [{"text": description.strip()}]}],
            "generationConfig": {"temperature": 0.6, "maxOutputTokens": 700},
        }, {"x-goog-api-key": api_key.strip(), "content-type": "application/json"})
        try:
            text = "".join(p.get("text", "") for p in reply["candidates"][0]["content"]["parts"])
        except (KeyError, IndexError, TypeError) as error:
            raise AIError("Unexpected reply from the AI service.") from error

    subject, body = _parse_draft(text)
    return subject, body

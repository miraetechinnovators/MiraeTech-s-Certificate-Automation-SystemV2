"""Look & feel: Petronas-green liquid theme. Edit colours in :root below, or the app name in app.py (APP_NAME)."""

CSS = """
<style>
:root{
  --pg:#00A19B;          /* Petronas green  */
  --pg-dark:#007a76;
  --pg-deep:#06403f;
  --pg-light:#7fe3dc;
  --pg-mist:#e9faf8;
  --ink:#0a2f2e;
  --glass:rgba(255,255,255,.62);
  --glass-line:rgba(0,161,155,.22);
}
html, body, .stApp{ font-family:"Inter","Segoe UI",system-ui,sans-serif; color:var(--ink); }
.stApp{
  background:
    radial-gradient(1200px 700px at 8% -10%, #c9f5f0 0%, transparent 60%),
    radial-gradient(900px 600px at 105% 10%, #d6f7f2 0%, transparent 55%),
    linear-gradient(180deg,#f3fcfb 0%,#e7f7f5 100%);
}
header[data-testid="stHeader"]{ background:transparent; }
.block-container{ padding-top:1.4rem; max-width:1400px; position:relative; z-index:2; }

/* ---------- floating liquid blobs ---------- */
.liquid{ position:fixed; inset:0; z-index:0; pointer-events:none; overflow:hidden; }
.liquid i{ position:absolute; display:block; filter:blur(46px); opacity:.55;
  background:radial-gradient(circle at 30% 30%, var(--pg-light), var(--pg) 70%);
  animation:morph 18s ease-in-out infinite alternate, drift 26s ease-in-out infinite alternate; }
.liquid i:nth-child(1){ width:46vw; height:46vw; left:-12vw; top:-14vw; }
.liquid i:nth-child(2){ width:36vw; height:36vw; right:-10vw; top:18vh; animation-delay:-6s,-9s;
  background:radial-gradient(circle at 60% 40%, #5fd3cb, var(--pg-dark) 75%); opacity:.38; }
.liquid i:nth-child(3){ width:40vw; height:40vw; left:22vw; bottom:-22vw; animation-delay:-12s,-4s; opacity:.42; }
@keyframes morph{
  0%{ border-radius:42% 58% 63% 37% / 41% 44% 56% 59%; }
  50%{ border-radius:63% 37% 40% 60% / 55% 62% 38% 45%; }
  100%{ border-radius:38% 62% 55% 45% / 62% 38% 62% 38%; } }
@keyframes drift{ from{ transform:translate(0,0) rotate(0deg);} to{ transform:translate(5vw,4vh) rotate(40deg);} }

/* ---------- hero ---------- */
.hero{ position:relative; overflow:hidden; border-radius:28px; padding:30px 36px 64px; margin-bottom:14px;
  background:linear-gradient(120deg,var(--pg-deep),var(--pg-dark) 55%,var(--pg));
  box-shadow:0 18px 50px -18px rgba(0,100,96,.6); color:#fff; }
.hero h1{ margin:0; font-size:2.25rem; letter-spacing:-.02em; font-weight:800; color:#fff; padding:0; }
.hero h1 em{ font-style:normal; font-weight:300; opacity:.92; }
.hero h1, .hero h1 *{ color:#fff !important; }
.hero p{ margin:.35rem 0 0; opacity:.9; font-size:1.02rem; }
.hero .pill{ display:inline-block; margin-bottom:10px; padding:3px 12px; border-radius:99px; font-size:.74rem;
  letter-spacing:.08em; text-transform:uppercase; background:rgba(255,255,255,.16); border:1px solid rgba(255,255,255,.28); }
.hero svg{ position:absolute; left:0; bottom:-2px; width:200%; height:56px; animation:wave 14s linear infinite; }
.hero svg.w2{ animation-duration:22s; animation-direction:reverse; opacity:.5; bottom:4px; }
@keyframes wave{ from{ transform:translateX(0);} to{ transform:translateX(-50%);} }
.hero .bubble{ position:absolute; border-radius:50%; background:rgba(255,255,255,.10); animation:rise 9s ease-in infinite; }
.hero .bubble:nth-of-type(1){ width:46px;height:46px; right:12%; bottom:-50px; }
.hero .bubble:nth-of-type(2){ width:24px;height:24px; right:24%; bottom:-30px; animation-delay:-3s; }
.hero .bubble:nth-of-type(3){ width:70px;height:70px; right:5%;  bottom:-80px; animation-delay:-6s; }
@keyframes rise{ to{ transform:translateY(-190px); opacity:0; } }

/* ---------- glass panels ---------- */
div[data-testid="stTabs"]{ background:var(--glass); backdrop-filter:blur(14px) saturate(140%);
  border:1px solid var(--glass-line); border-radius:24px; padding:10px 22px 26px;
  box-shadow:0 14px 40px -22px rgba(0,90,86,.45); }
div[data-testid="stTabs"] [role="tablist"]{ gap:6px; border-bottom:none; }
div[data-testid="stTabs"] [data-testid="stTab"]{ border-radius:99px; padding:.5rem 1.15rem; font-weight:600;
  color:var(--pg-dark); background:transparent; transition:all .25s ease; }
div[data-testid="stTabs"] [data-testid="stTab"]:hover{ background:rgba(0,161,155,.12); }
div[data-testid="stTabs"] [data-testid="stTab"][aria-selected="true"]{
  background:linear-gradient(120deg,var(--pg),var(--pg-dark)); color:#fff; box-shadow:0 8px 20px -10px var(--pg-dark); }
div[data-testid="stTabs"] [data-baseweb="tab-highlight"], div[data-testid="stTabs"] [data-baseweb="tab-border"], div[data-testid="stTabs"] [role="tablist"]>div[aria-hidden]{ display:none; }
div[data-testid="stTab"][aria-selected="true"] *{ color:#fff !important; }

/* ---------- controls ---------- */
.stButton>button, .stDownloadButton>button{ border-radius:99px; border:1px solid var(--glass-line);
  background:rgba(255,255,255,.8); color:var(--pg-dark); font-weight:600; transition:all .25s ease; }
.stButton>button:hover, .stDownloadButton>button:hover{ border-color:var(--pg); color:var(--pg-dark);
  transform:translateY(-1px); box-shadow:0 10px 22px -12px var(--pg); background:#fff; }
.stButton>button[kind="primary"]{ color:#fff; border:none; background:linear-gradient(120deg,var(--pg),var(--pg-dark));
  background-size:160% 100%; box-shadow:0 12px 26px -12px var(--pg-dark); }
.stButton>button[kind="primary"]:hover{ background-position:100% 0; color:#fff; box-shadow:0 14px 30px -10px var(--pg-dark); }
.stButton>button:disabled{ opacity:.45; transform:none; box-shadow:none; }
div[data-baseweb="input"], div[data-baseweb="select"]>div, div[data-baseweb="textarea"]{ border-radius:14px !important; }
div[data-testid="stFileUploaderDropzone"]{ border-radius:20px; border:2px dashed var(--pg); background:rgba(0,161,155,.06); }
div[data-testid="stMetric"]{ background:rgba(255,255,255,.7); border:1px solid var(--glass-line); border-radius:18px; padding:12px 16px; }
div[data-testid="stExpander"]{ border-radius:18px; border:1px solid var(--glass-line); background:rgba(255,255,255,.55); }
div[data-testid="stAlert"]{ border-radius:16px; }
div[data-testid="stProgress"] div[role="progressbar"]>div{ background:linear-gradient(90deg,var(--pg-light),var(--pg)); }
iframe{ border-radius:18px; }
h2,h3,h4{ color:var(--pg-deep); letter-spacing:-.01em; }

/* ---------- sidebar ---------- */
section[data-testid="stSidebar"]{ background:linear-gradient(180deg,rgba(255,255,255,.72),rgba(214,247,242,.78));
  backdrop-filter:blur(16px) saturate(140%); border-right:1px solid var(--glass-line); }
section[data-testid="stSidebar"] > div{ background:transparent; }
.sb-brand{ display:flex; align-items:center; gap:10px; margin:4px 0 18px; }
.sb-logo{ width:38px; height:38px; border-radius:12px; display:grid; place-items:center; color:#fff; font-size:1.15rem;
  background:linear-gradient(135deg,var(--pg),var(--pg-deep)); box-shadow:0 8px 18px -8px var(--pg-dark); }
.sb-brand b{ display:block; line-height:1.1; color:var(--pg-deep); font-size:1rem; }
.sb-brand small{ color:var(--pg-dark); opacity:.75; font-size:.76rem; }
.sb-meter{ position:relative; height:12px; border-radius:99px; background:rgba(0,161,155,.16); overflow:hidden; margin:6px 0 4px; }
.sb-meter i{ position:absolute; inset:0 auto 0 0; border-radius:99px; transition:width .8s cubic-bezier(.4,.1,.2,1);
  background:linear-gradient(90deg,var(--pg-light),var(--pg),var(--pg-dark)); background-size:200% 100%; animation:flow 3s linear infinite; }
@keyframes flow{ to{ background-position:-200% 0; } }
.sb-pct{ font-size:.78rem; color:var(--pg-dark); font-weight:600; margin-bottom:16px; }
.sb-steps{ position:relative; margin:0; padding:0; list-style:none; }
.sb-steps li{ position:relative; display:flex; gap:12px; padding:0 0 18px 0; }
.sb-steps li:not(:last-child)::before{ content:""; position:absolute; left:13px; top:28px; bottom:2px; width:2px; background:rgba(0,161,155,.22); }
.sb-steps li.done:not(:last-child)::before{ background:var(--pg); }
.sb-dot{ flex:0 0 28px; height:28px; border-radius:50%; display:grid; place-items:center; font-size:.78rem; font-weight:700;
  background:#fff; border:2px solid rgba(0,161,155,.3); color:var(--pg-dark); }
.sb-steps li.done .sb-dot{ background:var(--pg); border-color:var(--pg); color:#fff; box-shadow:0 6px 14px -6px var(--pg-dark); }
.sb-steps li.now .sb-dot{ border-color:var(--pg); box-shadow:0 0 0 0 rgba(0,161,155,.5); animation:pulse 2s infinite; }
@keyframes pulse{ 70%{ box-shadow:0 0 0 9px rgba(0,161,155,0);} 100%{ box-shadow:0 0 0 0 rgba(0,161,155,0);} }
.sb-txt b{ display:block; color:var(--pg-deep); font-size:.93rem; line-height:1.25; }
.sb-txt span{ color:var(--pg-dark); opacity:.78; font-size:.8rem; }
.sb-steps li:not(.done):not(.now) .sb-txt b{ opacity:.55; }
.sb-foot{ margin-top:6px; color:var(--pg-dark); opacity:.7; font-size:.78rem; }

@media (prefers-reduced-motion:reduce){ .liquid i, .hero svg, .hero .bubble{ animation:none !important; } }
@media (max-width:700px){ .hero{ padding:22px 20px 56px; } .hero h1{ font-size:1.6rem; } }
</style>
"""

def hero_html(app_name: str, tagline: str) -> str:
    first, _, rest = app_name.partition(" ")
    wave = ('<svg viewBox="0 0 1200 56" preserveAspectRatio="none"><path fill="{c}" d="M0 28 C150 56 300 0 450 24 S750 56 900 24 '
            'S1050 4 1200 28 L1200 56 L0 56Z"/><path fill="{c}" d="M1200 28 C1350 56 1500 0 1650 24 S1950 56 2100 24 '
            'S2250 4 2400 28 L2400 56 L1200 56Z" transform="translate(-0 0)"/></svg>')
    return (
        '<div class="liquid"><i></i><i></i><i></i></div>'
        '<div class="hero"><span class="pill">Team MIRAETECH</span>'
        f'<h1>{first} <em>{rest}</em></h1><p>{tagline}</p>'
        '<div class="bubble"></div><div class="bubble"></div><div class="bubble"></div>'
        + wave.format(c="rgba(255,255,255,.35)").replace('<svg', '<svg class="w2"', 1)
        + wave.format(c="#eefaf8")
        + '</div>'
    )


def sidebar_html(steps: list[tuple[str, str, bool]]) -> str:
    """steps = [(title, detail, done), ...]  ->  brand header + liquid meter + vertical stepper."""
    done_n = sum(1 for _, _, d in steps if d)
    pct = round(100 * done_n / len(steps))
    first_open = next((i for i, (_, _, d) in enumerate(steps) if not d), -1)
    items = []
    for i, (title, detail, done) in enumerate(steps):
        cls = "done" if done else ("now" if i == first_open else "")
        mark = "✓" if done else str(i + 1)
        items.append(f'<li class="{cls}"><div class="sb-dot">{mark}</div>'
                     f'<div class="sb-txt"><b>{title}</b><span>{detail}</span></div></li>')
    return (
        '<div class="sb-brand"><div class="sb-logo">🎓</div><div><b>Miraetech</b><small>Certificate Automation</small></div></div>'
        f'<div class="sb-meter"><i style="width:{max(pct, 4)}%"></i></div><div class="sb-pct">{pct}% complete</div>'
        f'<ul class="sb-steps">{"".join(items)}</ul>'
    )

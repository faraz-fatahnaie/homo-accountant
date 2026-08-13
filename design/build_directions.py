#!/usr/bin/env python3
"""Generate the three design-direction mockups from _template.html.

Each direction injects: title/tagline, palette chips, embedded Vazirmatn fonts
(data URIs), light+dark design tokens, and identity-specific CSS overrides.
"""
from __future__ import annotations
import base64, pathlib, re, sys

ROOT = pathlib.Path(__file__).resolve().parent
TEMPLATE = (ROOT / "_template.html").read_text(encoding="utf-8")

FONTS = {  # weight -> filename
    400: "Vazirmatn-Regular.woff2",
    600: "Vazirmatn-SemiBold.woff2",
    700: "Vazirmatn-Bold.woff2",
}

def font_css() -> str:
    blocks = []
    for weight, fname in FONTS.items():
        data = base64.b64encode((ROOT.parent / ".fonts" / fname).read_bytes()).decode()
        blocks.append(
            f"@font-face{{font-family:'Vazirmatn';font-style:normal;font-weight:{weight};"
            f"font-display:swap;src:url(data:font/woff2;base64,{data}) format('woff2');}}"
        )
    return "\n".join(blocks)

def tokens(light: dict, dark: dict) -> str:
    def css(d: dict) -> str:
        return "".join(f"{k}:{v};" for k, v in d.items())
    return (
        ':root[data-theme="light"]{' + css(light) + "}\n"
        ':root[data-theme="dark"]{' + css(dark) + "}"
    )

DIRECTIONS = {}

# ----------------------------------------------------------------------------
# Direction 1 — Classic (trusted, ledger-inspired: pine green + paper + gold)
# ----------------------------------------------------------------------------
DIRECTIONS["classic"] = {
    "title": "جهت ۱ — کلاسیک و مورداعتماد",
    "tag": "حسابداری سنتی با ظرافت مدرن؛ سبز کاج، کرم کاغذی و خطوط دفترکل — برای تیمهایی که اعتماد و ثبات میخواهند.",
    "palette": ["#14604F", "#B08A3E", "#F5F3EC", "#FFFFFF", "#0F2E26"],
    "tokens": tokens(
        light={
            "--font":"'Vazirmatn','Segoe UI',Tahoma,'Noto Sans Arabic',sans-serif",
            "--bg":"#F5F3EC","--surface":"#FFFFFF","--surface-2":"#F0EDE4",
            "--text":"#22271F","--muted":"#5F665C",
            "--border":"#E1DDD0","--border-strong":"#C9C4B2",
            "--primary":"#14604F","--primary-strong":"#0D4A3C","--on-primary":"#FFFFFF","--primary-soft":"#E2EEE9",
            "--success":"#1F7A4F","--success-strong":"#155C3B","--success-soft":"#E4F2EA",
            "--warning":"#9A6B00","--warning-strong":"#7A5500","--warning-soft":"#FAF1DC",
            "--danger":"#A83B2C","--danger-strong":"#8A2E22","--danger-soft":"#F9E7E2",
            "--focus":"#14604F","--focus-soft":"rgba(20,96,79,.16)",
            "--chart-1":"#14604F","--chart-2":"#B08A3E","--chart-3":"#5C6B5E",
            "--chart-grid":"#E1DDD0","--chart-txt":"#7A8177",
            "--chart-1-soft":"#E2EEE9","--chart-2-soft":"#F4EBD7","--chart-3-soft":"#E7EAE4",
            "--r-sm":"3px","--r-md":"5px","--r-lg":"8px",
            "--fs-base":"13.5px","--fs-table":"12.5px","--lh":"1.65",
            "--sbw":"232px",
            "--sb-bg":"#0F2E26","--sb-text":"#E8EDE8","--sb-muted":"#9DB8AE","--sb-border":"#1B4237",
            "--sb-hover":"rgba(255,255,255,.06)","--sb-active":"rgba(255,255,255,.12)",
            "--sb-active-text":"#FFFFFF","--sb-active-icon":"#D8B36A",
            "--topbar-bg":"#F5F3EC","--row-hover":"#FAF9F4","--thead-bg":"#EFEDE3","--thead-text":"#3A4038",
        },
        dark={
            "--font":"'Vazirmatn','Segoe UI',Tahoma,'Noto Sans Arabic',sans-serif",
            "--bg":"#111613","--surface":"#181E1A","--surface-2":"#1F2722",
            "--text":"#E9EAE2","--muted":"#97A29A",
            "--border":"#2A342D","--border-strong":"#3A463E",
            "--primary":"#3E9B80","--primary-strong":"#57B294","--on-primary":"#0B221A","--primary-soft":"#1C3A30",
            "--success":"#4CAF7F","--success-strong":"#7FD6A8","--success-soft":"#1D3529",
            "--warning":"#D9A84B","--warning-strong":"#EFC87E","--warning-soft":"#3A2F18",
            "--danger":"#D97A63","--danger-strong":"#F0A08C","--danger-soft":"#3D2420",
            "--focus":"#57B294","--focus-soft":"rgba(87,178,148,.25)",
            "--chart-1":"#4CAF84","--chart-2":"#D0A44E","--chart-3":"#8FA396",
            "--chart-grid":"#2A342D","--chart-txt":"#97A29A",
            "--chart-1-soft":"#1D3529","--chart-2-soft":"#3A2F18","--chart-3-soft":"#26322B",
            "--r-sm":"3px","--r-md":"5px","--r-lg":"8px",
            "--fs-base":"13.5px","--fs-table":"12.5px","--lh":"1.65",
            "--sbw":"232px",
            "--sb-bg":"#0C201A","--sb-text":"#E4EAE5","--sb-muted":"#8FA99E","--sb-border":"#1C3A30",
            "--sb-hover":"rgba(255,255,255,.05)","--sb-active":"rgba(255,255,255,.10)",
            "--sb-active-text":"#FFFFFF","--sb-active-icon":"#D0A44E",
            "--topbar-bg":"#111613","--row-hover":"#1B221D","--thead-bg":"#1F2722","--thead-text":"#C9D2CB",
        },
    ),
    "extra_css": """
/* ---- Classic identity: ruled ledger paper, double rules, restrained ---- */
.nav-label{letter-spacing:.6px}
.brand-mark{border-radius:6px;border:1px solid rgba(255,255,255,.25);box-shadow:inset 0 0 0 2px var(--primary)}
table.data thead th{border-bottom:3px double var(--border-strong)}
table.data tbody tr td{border-bottom:1px solid var(--border)}
.card-head{background:var(--surface-2);border-bottom:1px solid var(--border-strong)}
.kpi{border-radius:var(--r-md);border-width:1px}
.kpi::before{content:"";position:absolute;inset-inline-start:0;top:14px;bottom:14px;width:3px;background:var(--primary);border-radius:0 2px 2px 0;opacity:.85}
.kpi-icon{border:1px solid var(--border);background:var(--surface)}
.btn-primary{border:1px solid var(--primary-strong);box-shadow:inset 0 -2px 0 rgba(0,0,0,.12)}
.btn-ghost{border:1px solid var(--border-strong);background:var(--surface)}
.search,.tb-period,.fselect,.input,.select,.textarea{border-radius:var(--r-sm)}
.nav-item.active{border-inline-start:3px solid var(--sb-active-icon)}
.user-chip{border:1px solid var(--sb-border)}
.badge{border:1px solid transparent}
.badge-success{border-color:#BBD8C6}.badge-warn{border-color:#E6D3A4}.badge-danger{border-color:#E8C0B6}.badge-info{border-color:#B9D3CC}.badge-muted{border-color:var(--border)}
.filters{border-radius:var(--r-md)}
.table-wrap{border-radius:var(--r-md)}
.lifecycle .step{border-radius:var(--r-sm)}
.prog{background:var(--border)}
.kpi-delta{border:1px solid var(--border)}
""",
}

# ----------------------------------------------------------------------------
# Direction 2 — Modern (airy SaaS: indigo, soft cards, generous whitespace)
# ----------------------------------------------------------------------------
DIRECTIONS["modern"] = {
    "title": "جهت ۲ — نوین و روشن",
    "tag": "فضای تنفس، کارتهای نرم و آبی آرام؛ سبک SaaS مدرن برای تیمهای کوچک و کاربران غیرحسابدار.",
    "palette": ["#2F5CC9", "#3E9E9D", "#F5F7FA", "#FFFFFF", "#182236"],
    "tokens": tokens(
        light={
            "--font":"'Vazirmatn','Segoe UI',Tahoma,'Noto Sans Arabic',sans-serif",
            "--bg":"#F5F7FA","--surface":"#FFFFFF","--surface-2":"#EEF2F7",
            "--text":"#182236","--muted":"#5C6B84",
            "--border":"#E3E9F2","--border-strong":"#C9D4E5",
            "--primary":"#2F5CC9","--primary-strong":"#224A9E","--on-primary":"#FFFFFF","--primary-soft":"#E9EFFC",
            "--success":"#167A5B","--success-strong":"#0F6248","--success-soft":"#E2F4EC",
            "--warning":"#B26A00","--warning-strong":"#8F5500","--warning-soft":"#FBF1DE",
            "--danger":"#C24032","--danger-strong":"#A23427","--danger-soft":"#FBEAE7",
            "--focus":"#2F5CC9","--focus-soft":"rgba(47,92,201,.18)",
            "--chart-1":"#2F5CC9","--chart-2":"#3E9E9D","--chart-3":"#8A6FE0",
            "--chart-grid":"#E3E9F2","--chart-txt":"#5C6B84",
            "--chart-1-soft":"#E9EFFC","--chart-2-soft":"#E1F4F3","--chart-3-soft":"#EFEAFB",
            "--r-sm":"8px","--r-md":"10px","--r-lg":"14px",
            "--fs-base":"14px","--fs-table":"13px","--lh":"1.7",
            "--sbw":"252px",
            "--sb-bg":"#FFFFFF","--sb-text":"#233047","--sb-muted":"#7A88A0","--sb-border":"#E3E9F2",
            "--sb-hover":"#F1F4F9","--sb-active":"#E9EFFC",
            "--sb-active-text":"#224A9E","--sb-active-icon":"#2F5CC9",
            "--topbar-bg":"#FFFFFF","--row-hover":"#F7F9FC","--thead-bg":"#F1F5FA","--thead-text":"#3D4C66",
        },
        dark={
            "--font":"'Vazirmatn','Segoe UI',Tahoma,'Noto Sans Arabic',sans-serif",
            "--bg":"#0C1220","--surface":"#111A2E","--surface-2":"#1A2540",
            "--text":"#E8EDF7","--muted":"#94A3C0",
            "--border":"#24304D","--border-strong":"#35436A",
            "--primary":"#7C9BFF","--primary-strong":"#9DB4FF","--on-primary":"#0B1430","--primary-soft":"#22315C",
            "--success":"#4FC08F","--success-strong":"#8ADFB9","--success-soft":"#173527",
            "--warning":"#E2A84C","--warning-strong":"#F4CB82","--warning-soft":"#372B14",
            "--danger":"#E07A6B","--danger-strong":"#F2A595","--danger-soft":"#3D2320",
            "--focus":"#7C9BFF","--focus-soft":"rgba(124,155,255,.28)",
            "--chart-1":"#7C9BFF","--chart-2":"#53B9B8","--chart-3":"#A992F2",
            "--chart-grid":"#24304D","--chart-txt":"#94A3C0",
            "--chart-1-soft":"#22315C","--chart-2-soft":"#163A3A","--chart-3-soft":"#2C2650",
            "--r-sm":"8px","--r-md":"10px","--r-lg":"14px",
            "--fs-base":"14px","--fs-table":"13px","--lh":"1.7",
            "--sbw":"252px",
            "--sb-bg":"#0F182C","--sb-text":"#E8EDF7","--sb-muted":"#8FA0C0","--sb-border":"#24304D",
            "--sb-hover":"rgba(255,255,255,.04)","--sb-active":"#22315C",
            "--sb-active-text":"#B7C8FF","--sb-active-icon":"#7C9BFF",
            "--topbar-bg":"#0C1220","--row-hover":"#131E36","--thead-bg":"#1A2540","--thead-text":"#B9C6E0",
        },
    ),
    "extra_css": """
/* ---- Modern identity: soft shadows, rounded, airy ---- */
.card,.kpi{box-shadow:0 1px 2px rgba(24,34,54,.04),0 8px 24px rgba(24,34,54,.05)}
[data-theme="dark"] .card,[data-theme="dark"] .kpi{box-shadow:0 1px 2px rgba(0,0,0,.2),0 10px 28px rgba(0,0,0,.25)}
.card-head{border-bottom:1px solid var(--border)}
.kpi-icon{border-radius:10px}
.btn-primary{box-shadow:0 4px 12px var(--focus-soft)}
.btn-primary:hover{box-shadow:0 5px 16px var(--focus-soft)}
.btn{border-radius:10px}
.search,.tb-period,.fselect,.input,.select,.textarea,.dropzone{border-radius:10px}
.nav-item{border-radius:9px}
.nav-item.active{border-inline-start:3px solid var(--primary)}
.brand-name{color:var(--text)}
.sidebar{border-inline-end:1px solid var(--sb-border)}
.topbar{box-shadow:0 1px 0 var(--border)}
.filters{border-radius:12px}
.table-wrap{border-radius:12px}
.badge{padding:3px 10px}
.lifecycle .step{border-radius:999px}
.prog{background:var(--border)}
.tfoot{border-top:1px solid var(--border-strong)}
.kpi-value{font-size:20px}
.page-title{font-size:20px}
""",
}

# ----------------------------------------------------------------------------
# Direction 3 — Dense (efficient power-user: slate + amber, high density)
# ----------------------------------------------------------------------------
DIRECTIONS["dense"] = {
    "title": "جهت ۳ — فشرده و کارآمد",
    "tag": "تراکم بالای اطلاعات برای حسابدار حرفهای؛ اسلیت آرام با کهربایی برای تمرکز، میانبرهای صفحهکلید.",
    "palette": ["#35507A", "#B45309", "#EDEFF2", "#FFFFFF", "#141A22"],
    "tokens": tokens(
        light={
            "--font":"'Vazirmatn','Segoe UI',Tahoma,'Noto Sans Arabic',sans-serif",
            "--bg":"#EDEFF2","--surface":"#FFFFFF","--surface-2":"#E9ECF0",
            "--text":"#1A232E","--muted":"#5A6572",
            "--border":"#D3D9E0","--border-strong":"#B4BDC9",
            "--primary":"#35507A","--primary-strong":"#293E60","--on-primary":"#FFFFFF","--primary-soft":"#E4EAF3",
            "--success":"#1E7A4F","--success-strong":"#155F3D","--success-soft":"#E1F1E8",
            "--warning":"#A85F00","--warning-strong":"#864D00","--warning-soft":"#F9EFDD",
            "--danger":"#B23A48","--danger-strong":"#8F2E3A","--danger-soft":"#F8E6E8",
            "--focus":"#B45309","--focus-soft":"rgba(180,83,9,.18)",
            "--chart-1":"#35507A","--chart-2":"#B45309","--chart-3":"#5B7C99",
            "--chart-grid":"#D3D9E0","--chart-txt":"#5A6572",
            "--chart-1-soft":"#E4EAF3","--chart-2-soft":"#F7EADA","--chart-3-soft":"#E5ECF1",
            "--r-sm":"3px","--r-md":"4px","--r-lg":"6px",
            "--fs-base":"12.5px","--fs-table":"12px","--lh":"1.55",
            "--sbw":"218px",
            "--sb-bg":"#141A22","--sb-text":"#DDE3EA","--sb-muted":"#7E8A98","--sb-border":"#222B36",
            "--sb-hover":"rgba(255,255,255,.05)","--sb-active":"#B45309",
            "--sb-active-text":"#FFFFFF","--sb-active-icon":"#FFC97E",
            "--topbar-bg":"#FFFFFF","--row-hover":"#F4F6F8","--thead-bg":"#E9ECF0","--thead-text":"#33404F",
        },
        dark={
            "--font":"'Vazirmatn','Segoe UI',Tahoma,'Noto Sans Arabic',sans-serif",
            "--bg":"#0B0F14","--surface":"#131922","--surface-2":"#1B2430",
            "--text":"#E5EBF1","--muted":"#8B98A8",
            "--border":"#26303C","--border-strong":"#38455A",
            "--primary":"#5F83B8","--primary-strong":"#7FA1D0","--on-primary":"#0C1420","--primary-soft":"#22314A",
            "--success":"#3FAE79","--success-strong":"#79D4A8","--success-soft":"#163229",
            "--warning":"#DE9E3E","--warning-strong":"#F0BF71","--warning-soft":"#372B15",
            "--danger":"#DA6B76","--danger-strong":"#F0959D","--danger-soft":"#3A2126",
            "--focus":"#DE9E3E","--focus-soft":"rgba(222,158,62,.25)",
            "--chart-1":"#5F83B8","--chart-2":"#DE9E3E","--chart-3":"#6F96B8",
            "--chart-grid":"#26303C","--chart-txt":"#8B98A8",
            "--chart-1-soft":"#22314A","--chart-2-soft":"#372B15","--chart-3-soft":"#1E2E3C",
            "--r-sm":"3px","--r-md":"4px","--r-lg":"6px",
            "--fs-base":"12.5px","--fs-table":"12px","--lh":"1.55",
            "--sbw":"218px",
            "--sb-bg":"#0D1117","--sb-text":"#DCE3EA","--sb-muted":"#7E8A98","--sb-border":"#1E2733",
            "--sb-hover":"rgba(255,255,255,.05)","--sb-active":"#B45309",
            "--sb-active-text":"#FFFFFF","--sb-active-icon":"#FFC97E",
            "--topbar-bg":"#0B0F14","--row-hover":"#171F2A","--thead-bg":"#1B2430","--thead-text":"#AEBBC9",
        },
    ),
    "extra_css": """
/* ---- Dense identity: compact, data-first, amber focus ---- */
.kpi{padding:10px 12px;gap:6px;border-radius:var(--r-sm)}
.kpi::before{content:"";position:absolute;top:0;inset-inline:0;height:3px;background:var(--primary)}
.kpi-value{font-size:16px}
.kpi-icon{width:26px;height:26px;border-radius:6px}
table.data thead th{padding:6px 10px;font-size:10.5px}
table.data td{padding:5px 10px}
.table-wrap{border-radius:var(--r-sm)}
.filters{padding:6px 8px;border-radius:var(--r-sm);gap:6px}
.fselect{padding:3px 8px;border-radius:var(--r-sm);font-size:11.5px}
.fselect select{font-size:12px}
.fdates input{padding:4px 8px;font-size:11.5px}
.toolbar{margin-bottom:8px}
.btn{padding:6px 11px;font-size:12.5px;border-radius:var(--r-sm)}
.btn-sm{padding:4px 8px;font-size:11.5px}
.icon-btn{width:30px;height:30px}
.search{padding:5px 10px;border-radius:var(--r-sm)}
.tb-period{padding:5px 10px;border-radius:var(--r-sm);font-size:12px}
.content{padding:12px 14px 40px}
.page-title{font-size:17px}
.card{margin-bottom:10px;border-radius:var(--r-sm)}
.card-head{padding:8px 12px;border-radius:var(--r-sm) var(--r-sm) 0 0}
.card-title{font-size:12.5px}
.card-body{padding:10px 12px}
.nav-item{padding:5px 8px;font-size:12.5px;border-radius:var(--r-sm)}
.nav-label{font-size:9.5px}
.sb-fy{font-size:10px}
.mini-item{padding:6px 0}
.mini-ic{width:24px;height:24px}
.mini-t{font-size:12px}
.mini-s{font-size:10.5px}
.tfoot{padding:7px 10px;font-size:11.5px}
.badge{padding:2px 7px;font-size:10.5px}
.chip-filter{font-size:11px}
.chip{padding:3px 9px;font-size:11px}
.seg button{padding:3px 9px;font-size:11.5px}
.lifecycle .step{padding:3px 8px;font-size:10.5px;border-radius:var(--r-sm)}
.prog-row{padding:6px 0}
.input,.select,.textarea{padding:6px 9px;font-size:12.5px}
.radio-card{padding:6px 9px;font-size:12px}
.entry{padding:6px 14px}
.data-table-alt th,.data-table-alt td{padding:4px 9px}
.dropzone{padding:12px;font-size:12px}
.kbd{display:inline-block}
table.data{min-width:860px}
""",
}

def build() -> None:
    font = font_css()
    for key, d in DIRECTIONS.items():
        html = TEMPLATE
        html = html.replace("%%DIRTITLE%%", d["title"])
        html = html.replace("%%DIRTAG%%", d["tag"])
        html = html.replace("%%PALETTE%%", "".join(f'<i style="background:{c}"></i>' for c in d["palette"]))
        html = html.replace("%%FONT_CSS%%", font)
        html = html.replace("%%TOKENS%%", d["tokens"])
        html = html.replace("%%EXTRA_CSS%%", d["extra_css"])
        leftovers = re.findall(r"%%[A-Z_]+%%", html)
        if leftovers:
            raise SystemExit(f"{key}: unresolved placeholders {leftovers}")
        out = ROOT / f"direction-{key}.html"
        out.write_text(html, encoding="utf-8")
        print(f"wrote {out.name}  ({out.stat().st_size/1024:.0f} KB)")

if __name__ == "__main__":
    build()

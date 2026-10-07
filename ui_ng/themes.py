"""Native NiceGUI design profiles for Rayar RAG."""

from __future__ import annotations

from nicegui import app, ui

THEMES = {
    "rayar": {
        "label": "Rayar", "dark": False,
        "bg": "#F7F3EA", "surface": "#FFFEFB", "surface2": "#F1ECE3",
        "ink": "#1A1A1A", "muted": "#6E655D",
        "primary": "#6B1A2A", "accent": "#B8924D", "border": "#D8D0C4",
        "input_bg": "#FFFEFB", "input_ink": "#1A1A1A", "input_label": "#655D56",
        "menu_bg": "#FFFEFB", "menu_ink": "#1A1A1A",
        "radius": "2px", "shadow": "0 12px 34px rgba(41,31,21,.06)",
        "heading_font": 'Georgia, "Times New Roman", serif',
        "body_font": 'Inter, ui-sans-serif, system-ui, -apple-system, sans-serif',
        "mono_font": 'ui-monospace, SFMono-Regular, Menlo, monospace',
        "density": "comfortable",
    },
    "executive": {
        "label": "Executive", "dark": False,
        "bg": "#F8FAFC", "surface": "#FFFFFF", "surface2": "#F1F5F9",
        "ink": "#111827", "muted": "#64748B",
        "primary": "#1F2937", "accent": "#2563EB", "border": "#E2E8F0",
        "input_bg": "#FFFFFF", "input_ink": "#111827", "input_label": "#64748B",
        "menu_bg": "#FFFFFF", "menu_ink": "#111827",
        "radius": "8px", "shadow": "0 8px 28px rgba(15,23,42,.06)",
        "heading_font": 'Inter, ui-sans-serif, system-ui, -apple-system, sans-serif',
        "body_font": 'Inter, ui-sans-serif, system-ui, -apple-system, sans-serif',
        "mono_font": 'ui-monospace, SFMono-Regular, Menlo, monospace',
        "density": "comfortable",
    },
    "slate": {
        "label": "Slate", "dark": True,
        "bg": "#0F172A", "surface": "#172033", "surface2": "#1E293B",
        "ink": "#F8FAFC", "muted": "#CBD5E1",
        "primary": "#93C5FD", "accent": "#60A5FA", "border": "#334155",
        "input_bg": "#111827", "input_ink": "#F8FAFC", "input_label": "#CBD5E1",
        "menu_bg": "#172033", "menu_ink": "#F8FAFC",
        "radius": "10px", "shadow": "0 18px 46px rgba(0,0,0,.28)",
        "heading_font": 'Inter, ui-sans-serif, system-ui, -apple-system, sans-serif',
        "body_font": 'Inter, ui-sans-serif, system-ui, -apple-system, sans-serif',
        "mono_font": 'ui-monospace, SFMono-Regular, Menlo, monospace',
        "density": "comfortable",
    },
    "midnight": {
        "label": "Midnight", "dark": True,
        "bg": "#080B12", "surface": "#101521", "surface2": "#161D2B",
        "ink": "#F7F8FA", "muted": "#B9C2D0",
        "primary": "#E0BD76", "accent": "#D4B373", "border": "#2A3444",
        "input_bg": "#0D121B", "input_ink": "#F7F8FA", "input_label": "#C6CEDA",
        "menu_bg": "#101521", "menu_ink": "#F7F8FA",
        "radius": "6px", "shadow": "0 20px 52px rgba(0,0,0,.36)",
        "heading_font": 'Georgia, "Times New Roman", serif',
        "body_font": 'Inter, ui-sans-serif, system-ui, -apple-system, sans-serif',
        "mono_font": 'ui-monospace, SFMono-Regular, Menlo, monospace',
        "density": "comfortable",
    },
    "terminal": {
        "label": "Terminal", "dark": True,
        "bg": "#09110D", "surface": "#0D1711", "surface2": "#132018",
        "ink": "#E7F7EA", "muted": "#A7C8AE",
        "primary": "#7BE495", "accent": "#B7F5C4", "border": "#24402D",
        "input_bg": "#07100B", "input_ink": "#F0FFF3", "input_label": "#B7D8BE",
        "menu_bg": "#0D1711", "menu_ink": "#F0FFF3",
        "radius": "0px", "shadow": "none",
        "heading_font": 'ui-monospace, SFMono-Regular, Menlo, monospace',
        "body_font": 'ui-monospace, SFMono-Regular, Menlo, monospace',
        "mono_font": 'ui-monospace, SFMono-Regular, Menlo, monospace',
        "density": "compact",
    },
}

CSS = r'''
:root {
  --rr-primary:#6B1A2A; --rr-accent:#B8924D; --rr-bg:#F7F3EA;
  --rr-panel:#FFFEFB; --rr-surface2:#F1ECE3; --rr-ink:#1A1A1A;
  --rr-muted:#6E655D; --rr-border:#D8D0C4; --rr-input-bg:#FFFEFB;
  --rr-input-ink:#1A1A1A; --rr-input-label:#655D56; --rr-menu-bg:#FFFEFB;
  --rr-menu-ink:#1A1A1A; --rr-radius:2px;
  --rr-shadow:0 12px 34px rgba(41,31,21,.06);
  --rr-heading-font:Georgia,"Times New Roman",serif;
  --rr-body-font:Inter,ui-sans-serif,system-ui,-apple-system,sans-serif;
  --rr-mono-font:ui-monospace,SFMono-Regular,Menlo,monospace;
}
body,.q-page,.q-layout,.nicegui-content{background:var(--rr-bg)!important;color:var(--rr-ink)!important;font-family:var(--rr-body-font)}
.nicegui-content{padding:0!important}.rr-shell{width:min(1440px,calc(100vw - 48px));margin:0 auto}
.rr-masthead{padding:24px 0 16px;border-bottom:1px solid var(--rr-border)}
.rr-brand{font-family:var(--rr-heading-font);color:var(--rr-primary);font-size:2rem;line-height:1;letter-spacing:-.02em}
.rr-subbrand,.rr-eyebrow,.rr-corpus,.rr-source-count,.rr-footer{font-family:var(--rr-mono-font)}
.rr-subbrand{margin-top:7px;font-size:.68rem;letter-spacing:.16em;text-transform:uppercase;color:var(--rr-muted)}
.rr-corpus{margin-top:14px;padding:10px 13px;border-left:2px solid var(--rr-accent);background:var(--rr-panel);font-size:.74rem;color:var(--rr-muted)}
.rr-corpus b{color:var(--rr-primary)}
.rr-main-grid{display:grid;grid-template-columns:minmax(0,2fr) minmax(310px,1fr);gap:34px;align-items:start;padding:28px 0 64px}
.rr-left{min-width:0}.rr-right{position:sticky;top:16px;min-width:0}
.rr-eyebrow{font-size:.67rem;letter-spacing:.16em;text-transform:uppercase;color:var(--rr-muted);margin-bottom:8px}
.rr-answer{font-size:1.02rem;line-height:1.7;max-width:900px}.rr-answer p{margin:0 0 .92rem}
.rr-cite-mark{display:inline-flex;align-items:center;justify-content:center;min-width:1.42rem;height:1.42rem;padding:0 .24rem;margin:0 .08rem;border:1px solid var(--rr-primary);color:var(--rr-primary);font-family:var(--rr-mono-font);font-size:.72em;line-height:1}
.rr-cite-mark+.rr-cite-mark{margin-left:.22em}
.rr-ledger{background:var(--rr-panel);border:1px solid var(--rr-border);box-shadow:var(--rr-shadow);border-radius:var(--rr-radius);padding:17px 18px 18px}
.rr-ledger-title{padding-bottom:10px;border-bottom:1px solid var(--rr-border);font-family:var(--rr-mono-font);font-size:.68rem;letter-spacing:.16em;text-transform:uppercase;color:var(--rr-muted)}
.rr-source-row{display:grid;grid-template-columns:28px minmax(0,1fr) auto;gap:10px;padding:12px 0;border-bottom:1px solid var(--rr-border);align-items:start}.rr-source-row:last-child{border-bottom:none}
.rr-source-n{width:24px;height:24px;display:inline-flex;align-items:center;justify-content:center;border:1px solid var(--rr-primary);color:var(--rr-primary);font-family:var(--rr-mono-font);font-size:.74rem}
.rr-source-name{overflow-wrap:anywhere;font-size:.88rem;line-height:1.35}.rr-source-count{margin-top:3px;color:var(--rr-muted);font-size:.67rem}
.rr-empty{padding:16px 0 3px;color:var(--rr-muted);font-size:.85rem;line-height:1.55}
.rr-open,.rr-result{margin-top:20px;padding-top:17px;border-top:1px solid var(--rr-border)}
.rr-excerpt{padding:11px 0 14px;border-bottom:1px solid var(--rr-border);white-space:pre-wrap;font-family:var(--rr-mono-font);font-size:.72rem;line-height:1.55;color:var(--rr-muted)}
.rr-status{min-height:34px;color:var(--rr-muted);font-family:var(--rr-mono-font);font-size:.73rem}
.rr-alert{border-left:3px solid var(--rr-accent);background:var(--rr-panel);padding:10px 13px;margin:10px 0 18px;font-size:.86rem}
.rr-nav{padding:12px 0;border-bottom:1px solid var(--rr-border)}
.rr-upload-panel{background:var(--rr-panel);border:1px solid var(--rr-border);border-radius:var(--rr-radius);padding:16px}
.rr-footer{font-size:.68rem;color:var(--rr-muted);border-top:1px solid var(--rr-border);margin-top:2.5rem;padding:12px 0 24px}
.q-field__control{background:var(--rr-input-bg)!important;color:var(--rr-input-ink)!important;border-radius:var(--rr-radius)!important}
.q-field__native,.q-field__input,.q-field__prefix,.q-field__suffix{color:var(--rr-input-ink)!important;caret-color:var(--rr-accent)!important}
.q-field__label,.q-field__marginal,.q-field__append,.q-field__prepend{color:var(--rr-input-label)!important}
.q-field--outlined .q-field__control:before{border-color:var(--rr-border)!important}.q-field--outlined.q-field--focused .q-field__control:after{border-color:var(--rr-accent)!important}
.q-menu,.q-card,.q-dialog__inner>div{background:var(--rr-menu-bg)!important;color:var(--rr-menu-ink)!important;border-color:var(--rr-border)!important}
.q-item,.q-item__label,.q-menu .q-item{color:var(--rr-menu-ink)!important}.q-item--active,.q-item:hover{background:var(--rr-surface2)!important;color:var(--rr-ink)!important}
.q-btn{border-radius:var(--rr-radius)!important}.q-btn.bg-primary{background:var(--rr-primary)!important;color:var(--rr-bg)!important}.q-btn.text-primary{color:var(--rr-primary)!important}
.q-expansion-item,.q-expansion-item__container,.q-expansion-item .q-item{color:var(--rr-ink)!important}.q-separator{background:var(--rr-border)!important}
::placeholder{color:var(--rr-muted)!important;opacity:.88}.rr-compact .rr-main-grid{gap:22px;padding-top:22px}.rr-compact .rr-source-row{padding:9px 0}.rr-compact .rr-answer{line-height:1.55;font-size:.94rem}
@media(max-width:880px){.rr-shell{width:min(100% - 28px,1440px)}.rr-main-grid{grid-template-columns:1fr;gap:24px}.rr-right{position:static}}
'''


def install_css() -> None:
    ui.add_css(CSS)


def apply(name: str, dark_mode) -> None:
    if name not in THEMES:
        name = "rayar"
    p = THEMES[name]
    app.storage.user["theme"] = name
    dark_mode.enable() if p["dark"] else dark_mode.disable()
    props = {
        "--rr-primary": p["primary"], "--rr-accent": p["accent"], "--rr-bg": p["bg"],
        "--rr-panel": p["surface"], "--rr-surface2": p["surface2"], "--rr-ink": p["ink"],
        "--rr-muted": p["muted"], "--rr-border": p["border"], "--rr-input-bg": p["input_bg"],
        "--rr-input-ink": p["input_ink"], "--rr-input-label": p["input_label"],
        "--rr-menu-bg": p["menu_bg"], "--rr-menu-ink": p["menu_ink"], "--rr-radius": p["radius"],
        "--rr-shadow": p["shadow"], "--rr-heading-font": p["heading_font"],
        "--rr-body-font": p["body_font"], "--rr-mono-font": p["mono_font"],
        "--q-primary": p["primary"], "--q-secondary": p["surface2"], "--q-accent": p["accent"],
        "--q-dark": p["surface"], "--q-dark-page": p["bg"],
    }
    assignments = ";".join(
        f"document.documentElement.style.setProperty({k!r},{v!r})" for k, v in props.items()
    )
    compact = "true" if p["density"] == "compact" else "false"
    ui.run_javascript(assignments + f";document.documentElement.classList.toggle('rr-compact',{compact})")

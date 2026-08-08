"""
branding.py — Styling for the elements Streamlit does not provide.

Colour, typography, radius and widget styling come from .streamlit/config.toml.
Streamlit derives border tones, widget states and light and dark variants from
those values.

What is left is small on purpose. An earlier version of this file ran to
twenty-five rules, set the height of Streamlit's own header to zero, and named
four different container selectors in the hope that one would match. The header
rule collapsed the toolbar that holds the rerun control, and the container
guesswork took three attempts and still did not work. This version follows the
pattern of a Streamlit application that has run on the same machine for months
without any of those faults: pad the container, colour the headings, style your
own classes, and leave Streamlit's chrome alone.
"""

import streamlit as st


def _option(name: str, fallback: str) -> str:
    """Read a Streamlit theme option, falling back if it is unset."""
    try:
        value = st.get_option(f"theme.{name}")
    except Exception:
        value = None
    return value if value else fallback


def resolved() -> dict:
    """Theme values resolved in Python, used as CSS fallbacks."""
    return {
        "primary": _option("primaryColor", "#6B1A2A"),
        "link": _option("linkColor", "#8A2436"),
        "panel": _option("secondaryBackgroundColor", "#FDFCF9"),
        "text": _option("textColor", "#1A1A1A"),
        "border": _option("borderColor", "#E1DDD5"),
    }


def css() -> str:
    """Styles for elements Streamlit does not provide."""
    t = resolved()

    return f"""
<style>
:root {{
  --rr-primary: var(--st-primary-color, {t['primary']});
  --rr-cite:    var(--st-link-color, {t['link']});
  --rr-panel:   var(--st-secondary-background-color, {t['panel']});
  --rr-ink:     var(--st-text-color, {t['text']});
  --rr-rule:    var(--st-border-color, {t['border']});
  --rr-mono:    var(--st-code-font, ui-monospace, monospace);
  --rr-radius:  var(--st-base-radius, 0);
}}

.main > div {{
  padding-top: 2rem;
}}

h1, h2, h3, h4 {{
  color: var(--rr-primary) !important;
  font-family: var(--st-heading-font, Georgia, 'Times New Roman', serif) !important;
  font-weight: 400 !important;
}}

/* a small label above a section */
.rr-eyebrow {{
  font-family: var(--rr-mono);
  font-size: .68rem;
  letter-spacing: .16em;
  text-transform: uppercase;
  color: var(--rr-ink);
  opacity: .55;
  margin: 0 0 .5rem 0;
}}

/* which collection is being searched */
.rr-corpus {{
  font-family: var(--rr-mono);
  font-size: .74rem;
  color: var(--rr-ink);
  opacity: .85;
  padding: .5rem .85rem;
  background: var(--rr-panel);
  border-left: 2px solid var(--rr-cite);
  border-radius: var(--rr-radius);
  margin: .35rem 0 1.35rem 0;
}}

.rr-corpus b {{ color: var(--rr-primary); font-weight: 600; }}

/* the source ledger, beside the answer */
.rr-ledger {{
  background: var(--rr-panel);
  border: 1px solid var(--rr-rule);
  border-radius: var(--rr-radius);
  padding: 1rem 1.05rem 1.15rem;
}}

.rr-ledger-title {{
  font-family: var(--rr-mono);
  font-size: .68rem;
  letter-spacing: .16em;
  text-transform: uppercase;
  color: var(--rr-ink);
  opacity: .55;
  padding-bottom: .6rem;
  border-bottom: 1px solid var(--rr-rule);
}}

.rr-source {{
  display: flex;
  gap: .7rem;
  align-items: baseline;
  padding: .7rem 0;
  border-bottom: 1px solid var(--rr-rule);
}}

.rr-source:last-child {{ border-bottom: none; padding-bottom: 0; }}

.rr-source-n {{
  font-family: var(--rr-mono);
  font-size: .78rem;
  color: var(--rr-cite);
  border: 1px solid var(--rr-cite);
  border-radius: var(--rr-radius);
  min-width: 1.4rem;
  height: 1.4rem;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  flex: 0 0 auto;
}}

.rr-source-name {{ font-size: .86rem; line-height: 1.3; word-break: break-word; }}

.rr-source-count {{
  font-family: var(--rr-mono);
  font-size: .68rem;
  opacity: .5;
  margin-top: .18rem;
}}

.rr-ledger-empty {{ font-size: .84rem; line-height: 1.5; opacity: .55; padding: .9rem 0 .2rem; }}

/* the answer, and the markers that tie it to the ledger */
.rr-answer {{ line-height: 1.65; }}
.rr-answer p {{ margin-bottom: .85rem; }}

/* Adjacent marks would otherwise sit flush and read as one number: three
   separate citations rendering as 134, which a reader takes for a figure. */
.rr-cite-mark + .rr-cite-mark {{
  margin-left: .22em;
}}

.rr-cite-mark {{
  font-family: var(--rr-mono);
  font-size: .74em;
  color: var(--rr-cite);
  border: 1px solid var(--rr-cite);
  border-radius: var(--rr-radius);
  padding: .04em .3em;
  margin: 0 .08em;
  white-space: nowrap;
}}

.rr-rule-under {{
  border-bottom: 1px solid var(--rr-rule);
  margin: -.4rem 0 1.4rem 0;
}}

/* Quiet, and at the bottom, because a person came here to read documents
   rather than to be told whose software they are reading them in. */
.rr-footer {{
  font-family: var(--rr-mono);
  font-size: .68rem;
  letter-spacing: .04em;
  color: var(--rr-ink);
  opacity: .4;
  border-top: 1px solid var(--rr-rule);
  margin-top: 3rem;
  padding-top: .7rem;
}}

.rr-footer a {{ color: inherit; text-decoration: none; }}
.rr-footer a:hover {{ opacity: .8; text-decoration: underline; }}
</style>
"""


def masthead(app_name: str, username: str | None = None,
             role: str | None = None) -> None:
    """The page header, rendered with Streamlit's own heading."""
    if username:
        left, right = st.columns([4, 1])
        with left:
            st.title(app_name)
        with right:
            st.caption(f"{username} · {role or 'user'}")
    else:
        st.title(app_name)
    st.markdown('<div class="rr-rule-under"></div>', unsafe_allow_html=True)


def footer() -> None:
    """Version and copyright, at the foot of the page."""
    from core.version import COPYRIGHT, PROJECT_URL, __version__

    st.markdown(
        f'<div class="rr-footer">Rayar RAG {__version__} &nbsp;·&nbsp; '
        f'{COPYRIGHT} &nbsp;·&nbsp; '
        f'<a href="{PROJECT_URL}" target="_blank">source</a></div>',
        unsafe_allow_html=True,
    )


def signin_mark(app_name: str) -> None:
    """The heading on the sign-in screen."""
    st.title(app_name)
    st.markdown('<div class="rr-eyebrow">Sign in</div>', unsafe_allow_html=True)


def top_gap() -> None:
    """Kept so existing call sites work. Spacing now comes from the stylesheet."""
    return

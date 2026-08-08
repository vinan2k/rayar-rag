"""
login.py — Sign-in screen.

Local username and password. A failed attempt costs a short delay rather than
a lockout, which slows scripted guessing without letting anyone lock a real
user out of their own machine.
"""

import time

import streamlit as st

from core import auth
from core.config import Config
from ui.branding import css, footer, signin_mark, top_gap

FAIL_DELAY_SECONDS = 0.6


def show(cfg: Config) -> None:
    """Render the sign-in screen. Sets session state and reruns on success."""
    st.markdown(css(), unsafe_allow_html=True)
    top_gap()

    signin_mark(cfg.get("app.name", "Rayar RAG"))

    with st.form("signin"):
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        submitted = st.form_submit_button("Sign in")

    if submitted:
        if not username or not password:
            st.error("Enter a username and password.")
        else:
            user = auth.verify(username, password)
            if user is None:
                time.sleep(FAIL_DELAY_SECONDS)
                st.error("That username and password do not match an account.")
            else:
                auth.touch_login(username)
                st.session_state["user"] = user
                st.rerun()



def sign_out() -> None:
    """Clear the session and return to the sign-in screen."""
    for key in list(st.session_state.keys()):
        if key == "user" or key.startswith(("ask::", "q::", "drill")):
            st.session_state.pop(key, None)
    st.rerun()

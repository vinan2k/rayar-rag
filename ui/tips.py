"""
tips.py — A hint at the moment it is useful, once.

Shown where the next step is not obvious and nowhere else. A tour on arrival
would be read by nobody: a person who has just signed in wants to do the thing
they came for, not be told what the thing is. So each hint appears at the point
it applies — after a first upload, after a first answer — and never again once
dismissed.

Dismissal is stored in the database rather than the session, because a hint
that returns after a restart is not a hint, it is a nag.
"""

import streamlit as st

from core import database

# Written here rather than at the call site so the whole set can be read at
# once, and so the wording stays consistent between them.
TIPS = {
    "first_upload": (
        "Those documents are indexed now. Switch to **Ask** to question them, "
        "or open one on the right to read a summary."
    ),
    "first_answer": (
        "The sources beside the answer are the documents it came from, and the "
        "numbers match the markers in the text. Open one to summarise it or "
        "question it on its own."
    ),
    "first_collection": (
        "A collection is a set of documents searched together. Keep separate "
        "subjects in separate collections and answers stay sharper."
    ),
}


def _key(name: str, user_id: int) -> str:
    return f"tip_seen::{user_id}::{name}"


def seen(name: str, user_id: int) -> bool:
    return bool(database.get_setting(_key(name, user_id), False))


def mark_seen(name: str, user_id: int) -> None:
    database.set_setting(_key(name, user_id), True)


def show(name: str, user: dict) -> None:
    """
    Render a hint if this person has not dismissed it.

    Silent when the hint is unknown, so a call site can be added before the
    wording is settled without breaking the page.
    """
    message = TIPS.get(name)
    if not message:
        return

    user_id = user.get("id")
    if user_id is None or seen(name, user_id):
        return

    box = st.container(border=True)
    with box:
        left, right = st.columns([6, 1])
        with left:
            st.markdown(message)
        with right:
            if st.button("Got it", key=f"tip_dismiss::{name}",
                         use_container_width=True):
                mark_seen(name, user_id)
                st.rerun()


def reset(user: dict) -> None:
    """Bring every hint back. For someone who wants to see them again."""
    user_id = user.get("id")
    if user_id is None:
        return
    for name in TIPS:
        database.delete_setting(_key(name, user_id))

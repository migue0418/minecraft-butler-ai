"""Tests TDD para la resolución del thread_id (memoria por usuario)."""


def test_session_id_takes_precedence():
    from app.features.butler.service import _resolve_thread_id

    assert _resolve_thread_id("player-123", 7) == "player-123"
    assert _resolve_thread_id("player-123", None) == "player-123"


def test_falls_back_to_user_when_no_session_id():
    from app.features.butler.service import _resolve_thread_id

    assert _resolve_thread_id(None, 7) == "user-7"
    assert _resolve_thread_id("", 7) == "user-7"


def test_falls_back_to_ephemeral_when_no_user_and_no_session():
    from app.features.butler.service import _resolve_thread_id

    tid = _resolve_thread_id(None, None)
    assert tid.startswith("ephemeral-")

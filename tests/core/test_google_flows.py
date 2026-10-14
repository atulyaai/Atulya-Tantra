import secrets
import sqlite3
import time
from contextlib import closing

from atulya.auth import AuthStore, SESSION_MAX_AGE
from atulya.google_auth import OAuthFlows, challenge
from atulya.logging_setup import redact


def test_app_handoff_requires_original_device_proof_and_is_single_use(project_temp_dir):
    flows = OAuthFlows(project_temp_dir)
    verifier = secrets.token_urlsafe(32)
    handoff = flows.handoff("account-one", challenge(verifier))
    assert flows.exchange(handoff, secrets.token_urlsafe(32)) is None
    assert flows.exchange(handoff, verifier) == "account-one"
    assert flows.exchange(handoff, verifier) is None


def test_expired_handoff_and_oauth_state_cannot_be_reused(project_temp_dir):
    flows = OAuthFlows(project_temp_dir)
    verifier = secrets.token_urlsafe(32)
    handoff = flows.handoff("account-one", challenge(verifier))
    state = flows.start({"connect_user": "account-one"})
    with closing(sqlite3.connect(flows.path)) as db, db:
        db.execute("UPDATE handoffs SET expires=?", (int(time.time()) - 1,))
    assert flows.exchange(handoff, verifier) is None
    assert flows.consume(state) == {"connect_user": "account-one"}
    assert flows.consume(state) is None


def test_expired_oauth_start_is_not_accepted(project_temp_dir):
    flows = OAuthFlows(project_temp_dir)
    state = flows.start({"connect_user": "account-one"})
    with closing(sqlite3.connect(flows.path)) as db, db:
        db.execute("UPDATE flows SET expires=?", (int(time.time()) - 1,))
    assert flows.consume(state) is None


def test_session_renewal_preserves_revocation_and_never_restores_expired_sessions(project_temp_dir):
    store = AuthStore(project_temp_dir)
    token = store.create_session()
    assert SESSION_MAX_AGE == 30 * 24 * 60 * 60
    assert store.renew_session(token)
    store.revoke_session(token)
    assert not store.renew_session(token)
    assert store.user_for_session(token) is None
    token = store.create_session()
    with closing(sqlite3.connect(store.path)) as db, db:
        db.execute("UPDATE sessions SET expires_at=?", (int(time.time()) - 1,))
    assert not store.renew_session(token)
    assert store.user_for_session(token) is None


def test_google_proofs_and_tokens_are_redacted_from_urls():
    for key in ("id_token", "refresh_token", "handoff", "verifier", "code"):
        assert "private-value" not in redact(f"https://example.test/?{key}=private-value&safe=yes")

import json

from atulya.agi_eval import judge, record
from atulya.goal_score import score
from atulya.recent_actions import recent_actions


def test_a_hand_written_pass_does_not_raise_agi(tmp_path):
    assert judge("KAPOK-19")
    assert not judge("KAPOK-19.")
    record(tmp_path, passed=True, answer="KAPOK-19", reason="exact match")
    report = score(tmp_path, {})
    assert report["agi"] == "0/3"


def test_recent_actions_include_every_channel(tmp_path):
    row = {"at": "2026-10-26T13:00:00+05:30", "channel": "telegram", "tool": "briefing_settings", "outcome": "ok"}
    (tmp_path / "audit.jsonl").write_text(json.dumps(row) + "\n", encoding="utf-8")
    text = recent_actions(tmp_path)
    assert "telegram" in text and "briefing_settings" in text

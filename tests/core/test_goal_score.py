import json

from atulya.evolution import capture_order
from atulya.goal_score import score


def test_scripted_features_do_not_raise_agi(tmp_path):
    report = score(tmp_path, {"ATULYA_TELEGRAM_BOT_TOKEN": "x"})
    assert report["agi"] == "0/3"
    names = {item["name"]: item["ok"] for item in report["checks"]}
    assert names["finds_issues"] is False
    assert names["proposes_fix"] is False
    assert names["applies_fix"] is False
    assert "weights_changed" not in names


def test_a_hand_written_probe_does_not_count(tmp_path):
    (tmp_path / "novel_tasks.jsonl").write_text(
        '{"novel": true, "passed": true}\n', encoding="utf-8")
    assert score(tmp_path, {})["agi"] == "0/3"


def test_an_approved_edit_is_the_apply_point(tmp_path):
    folder = tmp_path / "maintenance"
    folder.mkdir()
    (folder / "abc.json").write_text(json.dumps({"state": "applied", "path": "webui/assistant.js"}), encoding="utf-8")
    (tmp_path / "maintenance-last.json").write_text(json.dumps({"findings": [{"area": "webui"}]}), encoding="utf-8")
    names = {item["name"]: item["ok"] for item in score(tmp_path, {})["checks"]}
    assert names["finds_issues"] and names["proposes_fix"] and names["applies_fix"]


def test_dont_is_saved_and_a_one_off_stop_is_not(tmp_path):
    saved = capture_order(tmp_path, "admin", "Don't send the long weather report again")
    assert "weather" in saved
    assert capture_order(tmp_path, "admin", "stop the music") == ""

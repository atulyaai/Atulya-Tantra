from atulya.goal_score import score


def test_agi_stays_zero_without_a_novel_pass(tmp_path):
    report = score(tmp_path, {})
    assert report["agi"] == "0/3"
    assert "cannot raise it" in report["meaning"]


def test_a_novel_pass_is_the_only_agi_point(tmp_path):
    (tmp_path / "novel_tasks.jsonl").write_text(
        "{\"novel\": true, \"passed\": true, \"task\": \"unseen\"}\n", encoding="utf-8")
    report = score(tmp_path, {})
    assert report["agi"] == "1/3"
    names = {item["name"]: item["ok"] for item in report["checks"]}
    assert names["novel_tasks"] is True
    assert names["weights_changed"] is False

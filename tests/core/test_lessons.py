import json

from atulya.evolution import Lessons, learn_from_failures, lessons_for_prompt


def test_a_correction_is_repeated_on_the_next_prompt(tmp_path):
    store = Lessons(tmp_path)
    item = store.add("admin", "Never say you cannot change the news source.")
    prompt = lessons_for_prompt(tmp_path, "admin")
    assert item["id"] in prompt and "news source" in prompt
    assert store.add("admin", "Never say you cannot change the news source.")["id"] == item["id"]
    assert store.forget("admin", "news source") == 1
    assert lessons_for_prompt(tmp_path, "admin") == ""


def test_three_failures_become_one_rule(tmp_path):
    path = tmp_path / "audit.jsonl"
    row = {"user_id": "admin", "tool": "device_action", "outcome": "Device is offline"}
    path.write_text((json.dumps(row) + "\n") * 3, encoding="utf-8")
    learned = learn_from_failures(tmp_path)
    assert learned and "device_action" in learned[0]
    assert learn_from_failures(tmp_path) == []

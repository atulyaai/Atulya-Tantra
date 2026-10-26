from datetime import datetime, timezone

from atulya.maintenance import Maintenance

SINCE = datetime(2020, 1, 1, tzinfo=timezone.utc)
SKILL = "---\nname: demo\ndescription: Demo skill\n---\n\nbody\n"


def _shop(tmp_path):
    root = tmp_path / "root"
    skill = root / "tools" / "skills" / "demo"
    skill.mkdir(parents=True)
    (skill / "SKILL.md").write_text(SKILL, encoding="utf-8")
    data = tmp_path / "data"
    data.mkdir()
    (data / "autonomy.json").write_text('{"repairs": "apply_if_tests_pass"}', encoding="utf-8")
    return Maintenance(root, data, tmp_path / "models"), root


def test_web_ui_still_needs_approval(tmp_path):
    shop, root = _shop(tmp_path)
    web = root / "webui"
    web.mkdir()
    (web / "music.js").write_text("var x = 1;\n", encoding="utf-8")
    shop.propose("webui/music.js", "var x = 2;\n", "test")
    result = shop.auto_apply_since(SINCE, lambda: True)
    assert result["applied"] is False
    assert "approval" in result["reason"]
    assert (web / "music.js").read_text(encoding="utf-8") == "var x = 1;\n"


def test_a_failed_test_rolls_the_repair_back(tmp_path):
    shop, root = _shop(tmp_path)
    shop.propose("tools/skills/demo/SKILL.md", SKILL + "more\n", "note")
    result = shop.auto_apply_since(SINCE, lambda: False)
    assert result["applied"] is False
    assert "rolled back" in result["reason"]
    assert (root / "tools/skills/demo/SKILL.md").read_text(encoding="utf-8") == SKILL


def test_a_small_skill_edit_applies_when_tests_pass(tmp_path):
    shop, root = _shop(tmp_path)
    shop.propose("tools/skills/demo/SKILL.md", SKILL + "more\n", "note")
    result = shop.auto_apply_since(SINCE, lambda: True)
    assert result["applied"] is True
    assert (root / "tools/skills/demo/SKILL.md").read_text(encoding="utf-8").endswith("more\n")

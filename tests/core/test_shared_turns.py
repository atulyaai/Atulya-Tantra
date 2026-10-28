from atulya.history import ConversationHistory


def test_other_conversations_are_visible_as_data(tmp_path):
    history = ConversationHistory(tmp_path)
    history.append("telegram", "m1", "user", "stop the rain alert", user_id="admin")
    history.append("telegram", "m2", "assistant", "Stopped.", user_id="admin")
    history.append("webchat1", "m3", "user", "hello from the site", user_id="admin")
    note = history.recent_elsewhere("admin", "webchat1")
    assert "stop the rain alert" in note
    assert "hello from the site" not in note
    assert history.recent_elsewhere("admin", "telegram") == "user: hello from the site"

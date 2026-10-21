import pytest

from atulya.music import MusicStore, youtube_id


def test_music_queue_is_private_and_does_not_claim_playback(project_temp_dir):
    store = MusicStore(project_temp_dir)
    item = store.add("alice", "https://youtu.be/M7lc1UVf-VE", "Video")
    assert item["state"] == "queued"
    assert store.list("bob") == []
    assert not store.receipt("bob", item["id"], "playing")
    assert MusicStore(project_temp_dir).receipt("alice", item["id"], "playing")
    assert store.list("alice")[0]["state"] == "playing"


def test_music_rejects_unsafe_hosts_and_non_video_links():
    for url in ["javascript:alert(1)", "https://youtube.com.evil.com/watch?v=M7lc1UVf-VE", "https://www.youtube.com/results?search_query=music", "https://u:p@youtube.com/watch?v=M7lc1UVf-VE"]:
        with pytest.raises(ValueError):
            youtube_id(url)
    assert youtube_id("https://www.youtube.com/watch?v=M7lc1UVf-VE") == "M7lc1UVf-VE"

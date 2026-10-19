import pytest

from atulya.music import MusicStore, youtube_id
import sqlite3
import time
from contextlib import closing


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


def test_stale_playback_is_unconfirmed_and_cancelled_tracks_stay_cancelled(project_temp_dir):
    store = MusicStore(project_temp_dir)
    item = store.add("alice", "https://youtu.be/M7lc1UVf-VE")
    store.receipt("alice", item["id"], "playing")
    with closing(sqlite3.connect(store.path)) as db, db:
        db.execute("UPDATE tracks SET updated=?", (time.time() - 60,))
    assert store.list("alice")[0]["state"] == "unconfirmed"
    assert store.receipt("alice", item["id"], "playing")
    assert store.list("alice")[0]["state"] == "playing"
    assert store.receipt("alice", item["id"], "cancelled")
    assert not store.receipt("alice", item["id"], "ended")
    assert store.list("alice")[0]["state"] == "cancelled"

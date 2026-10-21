import asyncio
import json
import subprocess
from types import SimpleNamespace

import pytest

from atulya import music


def test_music_search_uses_metadata_only_and_filters_invalid_ids(monkeypatch):
    monkeypatch.setattr(music.importlib.util, "find_spec", lambda _: object())
    def run(command, **kwargs):
        assert "--skip-download" in command and "--ignore-config" in command
        assert kwargs["timeout"] == 25
        assert command[-1] == "ytsearch2:artist & song"
        return SimpleNamespace(returncode=0, stdout=json.dumps({"entries": [
            {"id": "M7lc1UVf-VE", "title": "Song", "channel": "Artist"},
            {"id": "invalid", "title": "Bad"}, None]}))
    monkeypatch.setattr(music.subprocess, "run", run)
    tracks = music.search_music("artist & song", 2)
    assert len(tracks) == 1
    assert tracks[0]["url"] == "https://www.youtube.com/watch?v=M7lc1UVf-VE"


def test_music_search_reports_missing_dependency_and_timeout(monkeypatch):
    monkeypatch.setattr(music.importlib.util, "find_spec", lambda _: None)
    with pytest.raises(ValueError, match="music extra"):
        music.search_music("Song")
    monkeypatch.setattr(music.importlib.util, "find_spec", lambda _: object())
    def timeout(*args, **kwargs):
        raise subprocess.TimeoutExpired("search", 25)
    monkeypatch.setattr(music.subprocess, "run", timeout)
    with pytest.raises(ValueError, match="timed out"):
        music.search_music("Song")


def test_song_name_queues_private_track_through_shared_toolbox(project_temp_dir, monkeypatch):
    from tools.plugins.toolkit import Toolbox, TOOLS
    from tools.plugins.registry import PluginContext
    monkeypatch.setenv("ATULYA_DATA_DIR", str(project_temp_dir))
    monkeypatch.setattr(music, "search_music", lambda *args: [{"url": "https://youtu.be/M7lc1UVf-VE", "title": "Matched song"}])
    toolbox = Toolbox(TOOLS, PluginContext("web", None, None, "alice"))
    result = asyncio.run(toolbox.call("queue_music", {"query": "Song"}))
    assert "Queued Matched song" in result
    assert "no phone playback is confirmed" in result
    assert music.MusicStore(project_temp_dir).list("alice")[0]["state"] == "queued"
    assert music.MusicStore(project_temp_dir).list("bob") == []

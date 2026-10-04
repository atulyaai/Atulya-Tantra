from atulya import kosh


def test_old_data_folder_is_moved_once_with_its_files(tmp_path):
    (tmp_path / "data" / "agent").mkdir(parents=True)
    (tmp_path / "data" / "agent" / "money.json").write_text('{"a": 1}')
    assert kosh.migrate(tmp_path) == "moved data to kosh"
    assert (tmp_path / "kosh" / "agent" / "money.json").read_text() == '{"a": 1}'
    assert not (tmp_path / "data").exists()
    assert kosh.migrate(tmp_path) == "nothing to do"


def test_existing_kosh_is_never_overwritten(tmp_path):
    (tmp_path / "data").mkdir()
    (tmp_path / "data" / "old.txt").write_text("old")
    (tmp_path / "kosh").mkdir()
    (tmp_path / "kosh" / "new.txt").write_text("new")
    assert kosh.migrate(tmp_path) == "nothing to do"
    assert (tmp_path / "kosh" / "new.txt").read_text() == "new" and (tmp_path / "data" / "old.txt").exists()


def test_no_data_folder_is_fine(tmp_path):
    assert kosh.migrate(tmp_path) == "nothing to do"

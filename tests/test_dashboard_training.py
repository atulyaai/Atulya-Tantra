import json


def test_dataset_index_exposes_trainable_files_only(tmp_path, monkeypatch):
    from drishti.dashboard import helpers

    datasets_dir = tmp_path / "datasets"
    datasets_dir.mkdir()
    (datasets_dir / "alpha.jsonl").write_text('{"instruction":"a","output":"b"}\n', encoding="utf-8")
    (datasets_dir / "identity.json").write_text("{}", encoding="utf-8")
    (datasets_dir / "tokenizer.json").write_text("{}", encoding="utf-8")

    monkeypatch.setattr(helpers, "DATASETS_DIR", datasets_dir)

    assert set(helpers._dataset_index()) == {"alpha.jsonl", "identity.json"}


def test_training_start_all_datasets_materializes_jsonl_bundle(tmp_path, monkeypatch):
    from drishti.dashboard.routes import train

    first = tmp_path / "first.jsonl"
    second = tmp_path / "second.jsonl"
    first.write_text(json.dumps({"instruction": "one", "output": "two"}) + "\n", encoding="utf-8")
    second.write_text(json.dumps({"instruction": "three", "output": "four"}) + "\n", encoding="utf-8")
    output_dir = tmp_path / "outputs"

    launched = {}

    class FakeProcess:
        pid = 4321

    def fake_popen(cmd, cwd, stdout, stderr):
        launched["cmd"] = cmd
        launched["cwd"] = cwd
        return FakeProcess()

    monkeypatch.setattr(train, "OUTPUTS_DIR", output_dir)
    monkeypatch.setattr(train, "PID_FILE", output_dir / "train.pid")
    monkeypatch.setattr(train, "LOG_FILE", output_dir / "training.log")
    monkeypatch.setattr(train, "_require_admin", lambda token: {"username": "admin", "role": "admin"})
    monkeypatch.setattr(train, "_pid_running", lambda pid: False)
    monkeypatch.setattr(train, "_python_executable", lambda: "python")
    monkeypatch.setattr(train, "_dataset_index", lambda: {"first.jsonl": first, "second.jsonl": second})
    monkeypatch.setattr(train.subprocess, "Popen", fake_popen)

    response = train.api_train_start({"data_id": "all", "config": "atulya_seed", "steps": 3}, _admin="token")

    data_arg = launched["cmd"][launched["cmd"].index("--data") + 1]
    bundle = output_dir / "dashboard_all_datasets.jsonl"
    rows = [json.loads(line) for line in bundle.read_text(encoding="utf-8").splitlines()]
    assert response["pid"] == 4321
    assert data_arg == str(bundle)
    assert rows == [
        {"instruction": "one", "output": "two"},
        {"instruction": "three", "output": "four"},
    ]

import ast
import importlib.util
import json
from pathlib import Path

import nbformat
import pytest

from pariksha import sims

ROOT = Path(__file__).resolve().parents[1]


def load(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / "prayog" / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture
def tm():
    return load("try_model")


@pytest.fixture
def cr():
    return load("connect_remote")


def test_recommendation_keeps_a_memory_margin(tm):
    assert tm.recommend(1.0) == "0.6b"            # tiny machine: smallest, never nothing
    assert tm.recommend(4.0) == "1.7b"
    assert tm.recommend(8.0) == "4b"
    assert tm.recommend(15.0) == "8b"
    assert tm.recommend(64.0) == "14b"
    for key in tm.MODELS:                          # whatever is recommended always fits in 75% of free memory
        assert tm.ram_needed(key) > tm.MODELS[key][2]


def test_model_table_matches_the_files_atulya_already_uses(tm):
    from atulya.mastishk import BRAIN_TIERS

    for tier, key in (("tiny", "0.6b"), ("balanced", "1.7b"), ("power", "4b")):
        assert tm.MODELS[key][:2] == (BRAIN_TIERS[tier]["repo"], BRAIN_TIERS[tier]["file"])


def test_answers_are_cleaned_and_tool_json_is_judged(tm):
    assert tm.clean_answer("<think>hmm\nmore</think>Hello there") == "Hello there"
    assert tm.is_tool_json('Sure: {"tool": "device_do", "arguments": {"device": "tv", "action": "power_off"}}')
    for bad in ("turn it off", '{"tool": "x"}', '{"tool": 5, "arguments": {}}', "{broken"):
        assert not tm.is_tool_json(bad)


def test_results_table_accumulates_rows(tm, tmp_path):
    result = {"load_s": 3.8, "avg_tok_per_s": 15.9, "runs": [
        {"label": "English", "first_s": 0.5, "ok": True}, {"label": "Tool call (JSON only)", "first_s": 0.7, "ok": True}]}
    out = tmp_path / "results.md"
    tm.append_results("1.7b", result, out)
    tm.append_results("4b", {**result, "avg_tok_per_s": 6.0}, out)
    lines = out.read_text().splitlines()
    assert lines[0].startswith("# Model results") and sum(row.startswith("| 1.7b") or row.startswith("| 4b") for row in lines) == 2
    assert "| 1.7b | 3.8 s | 15.9 | 0.6 s | yes |" in out.read_text()


def test_use_in_atulya_writes_the_env_file_only(tm, tmp_path, monkeypatch):
    monkeypatch.setenv("ATULYA_GGUF_PATH", "x")
    monkeypatch.delenv("ATULYA_GGUF_PATH")
    monkeypatch.setenv("ATULYA_LOCAL_MODEL_NAME", "x")
    monkeypatch.delenv("ATULYA_LOCAL_MODEL_NAME")
    model = tmp_path / "m.gguf"
    model.write_bytes(b"x")
    env = tmp_path / ".env"
    env.write_text("KEEP=1\n")
    tm.use_in_atulya("4b", model, env)
    text = env.read_text()
    assert "KEEP=1" in text and f"ATULYA_GGUF_PATH={model.resolve()}" in text and "ATULYA_LOCAL_MODEL_NAME=Qwen3-4B" in text


# ── connect_remote, against a real local OpenAI-style server ───────────────────────────────────────
def openai_sim(key="secret"):
    models = json.dumps({"data": [{"id": "qwen3-8b"}]})
    chat = json.dumps({"choices": [{"message": {"content": "ready"}}]})
    sim = sims.Sim({("GET", "/v1/models"): (200, models), ("POST", "/v1/chat/completions"): (200, chat)})
    return sim


def test_url_normalising_and_transport_rules(cr):
    assert cr.normalize_url("abc.trycloudflare.com") == "https://abc.trycloudflare.com/v1"
    assert cr.normalize_url("http://192.168.1.5:1234/") == "http://192.168.1.5:1234/v1"
    assert cr.normalize_url("https://x.io/v1/") == "https://x.io/v1"
    cr.check_transport("https://abc.trycloudflare.com/v1", "key")
    cr.check_transport("http://192.168.1.5:1234/v1", "key")           # your own network: fine
    cr.check_transport("http://localhost:8000/v1", "key")
    with pytest.raises(SystemExit, match="plain http"):
        cr.check_transport("http://8.8.8.8/v1", "key")                # a key must never cross the internet unencrypted
    cr.check_transport("http://8.8.8.8/v1", "")                       # no key, nothing to leak


def test_connect_detects_the_model_tests_it_and_saves_settings(cr, tmp_path, monkeypatch):
    for name in ("ATULYA_CUSTOM_URL", "ATULYA_CUSTOM_KEY", "ATULYA_CUSTOM_MODEL"):
        monkeypatch.setenv(name, "x")
        monkeypatch.delenv(name)
    env = tmp_path / ".env"
    env.write_text("KEEP=1\n")
    with openai_sim() as sim:
        info = cr.connect(f"http://127.0.0.1:{sim.port}", "secret", env_file=env)
    assert info["model"] == "qwen3-8b" and info["text"] == "ready" and info["url"].endswith("/v1")
    text = env.read_text()
    assert "KEEP=1" in text and "ATULYA_CUSTOM_MODEL=qwen3-8b" in text and "ATULYA_CUSTOM_KEY=secret" in text
    assert [r["path"] for r in sim.requests] == ["/v1/models", "/v1/chat/completions"]
    cr.remove(env)
    assert "ATULYA_CUSTOM" not in env.read_text() and "KEEP=1" in env.read_text()


def test_connect_failures_are_plain_and_save_nothing(cr, tmp_path):
    env = tmp_path / ".env"
    with sims.Sim({("GET", "/v1/models"): (401, "no")}) as sim:
        with pytest.raises(SystemExit, match="refused: 401. Check the key"):
            cr.connect(f"http://127.0.0.1:{sim.port}/v1", "bad", env_file=env)
    with pytest.raises(SystemExit, match="couldn't reach"):
        cr.connect("http://127.0.0.1:1/v1", "k", env_file=env)
    assert not env.exists()


def test_atulya_uses_the_remote_brain_through_its_own_provider(monkeypatch):
    """The same settings connect_remote writes are what the 'Your own' provider reads."""
    import asyncio

    from atulya.mastishk import OpenAICompatProvider
    from atulya.mastishk import BY_ID

    chat = json.dumps({"choices": [{"message": {"content": "hello from the big model"}}]})
    with sims.Sim({("POST", "/v1/chat/completions"): (200, chat)}) as sim:
        monkeypatch.setenv("ATULYA_CUSTOM_URL", f"http://127.0.0.1:{sim.port}/v1")
        monkeypatch.setenv("ATULYA_CUSTOM_KEY", "secret")
        monkeypatch.setenv("ATULYA_CUSTOM_MODEL", "qwen3-8b")
        provider = OpenAICompatProvider(BY_ID["custom"])
        assert provider.is_available()
        assert asyncio.run(provider.chat("hi")) == "hello from the big model"
    request = sim.requests[0]
    assert request["json"]["model"] == "qwen3-8b" and request["headers"]["Authorization"] == "Bearer secret"


# ── the Colab notebook ──────────────────────────────────────────────────────────────────────────────
NOTEBOOK = ROOT / "prayog" / "atulya_remote_brain.ipynb"


def test_notebook_is_valid_and_every_cell_parses():
    nb = nbformat.read(NOTEBOOK, as_version=4)
    nbformat.validate(nb)
    code = [c.source for c in nb.cells if c.cell_type == "code"]
    assert len(code) >= 7
    for src in code:
        keep = [ln for ln in src.splitlines() if not ln.lstrip().startswith(("%", "!", "# %%", "# CMAKE", "# %%bash"))]
        ast.parse("\n".join(ln for ln in keep if not ln.startswith("pip install")))


def test_notebook_protects_the_server_and_hardcodes_no_secret():
    src = "\n".join(c.source for c in nbformat.read(NOTEBOOK, as_version=4).cells if c.cell_type == "code")
    assert "--api_key" in src and "secrets.token_urlsafe" in src                   # a random key, always on
    assert "127.0.0.1" in src and "--host\", \"0.0.0.0" not in src                 # only the tunnel can reach it
    import re

    assert not re.search(r"sk-[A-Za-z0-9]{16,}|hf_[A-Za-z0-9]{20,}|[A-Za-z0-9_-]{40,}", src.replace("urlsafe", ""))   # no key-shaped strings
    assert "connect_remote.py" in src and "--n_gpu_layers" in src


def test_lean_request_drops_tool_text_for_plain_questions(monkeypatch):
    """A local CPU model reads ~1,800 fewer tokens when the question is not an action."""
    from atulya.mastishk import POLICY_MARK
    from atulya.mastishk import lean_request

    system = f"Persona text.\n\n{POLICY_MARK}\n- use tools\nAvailable tools:\n- web_search"
    tools = [{"type": "function"}]
    notes = "[Notes for this turn]\nCurrent local date and time: Monday, set the add send\n\n"

    monkeypatch.delenv("ATULYA_LOCAL_LEAN", raising=False)
    plain_system, plain_tools = lean_request(notes + "Why is the sky blue?", system, tools)
    assert plain_system == "Persona text." and plain_tools is None   # words in the notes do not count
    act_system, act_tools = lean_request(notes + "Play some jazz", system, tools)
    assert act_system == system and act_tools == tools
    monkeypatch.setenv("ATULYA_LOCAL_LEAN", "off")
    assert lean_request("Why is the sky blue?", system, tools) == (system, tools)

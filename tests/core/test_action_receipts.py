from tools.plugins.document_edits import create_document
from tools.plugins.toolkit import _restart_service


def finish_without_io(coroutine):
    # These guards must finish before any network, file or scheduling operation.
    try:
        coroutine.send(None)
    except StopIteration as result:
        return result.value
    finally:
        coroutine.close()
    raise AssertionError("Unavailable action unexpectedly attempted asynchronous work")


def test_document_creation_does_not_write_fake_formats(project_temp_dir, monkeypatch):
    monkeypatch.chdir(project_temp_dir)
    for kind in ("word", "excel", "pdf", "powerpoint"):
        result = finish_without_io(create_document(doc_type=kind, content="hello", title="../../escape"))
        assert result["success"] is False
        assert "unavailable" in result["error"]
        assert "filepath" not in result
    assert not list(project_temp_dir.iterdir())


def test_service_restart_does_not_claim_an_approval_or_execution():
    result = finish_without_io(_restart_service({"service": "atulya"}, None))
    assert "unavailable" in result
    assert "No approval was queued" in result
    assert "no service was changed" in result

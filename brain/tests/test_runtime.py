import tempfile
import unittest
from pathlib import Path

from atulya_runtime.config import Settings
from atulya_runtime.service import AtulyaService


class FakeProvider:
    name = "fake"

    def complete(self, messages):
        return f"Model reply to: {messages[-1]['content']}"


class AtulyaRuntimeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        root = Path(self.temp_dir.name)
        self.workspace = root / "workspace"
        self.workspace.mkdir()
        self.settings = Settings(
            data_dir=root / "data",
            workspace_dir=self.workspace,
            database_path=root / "data" / "atulya.sqlite3",
        )
        self.service = AtulyaService(self.settings)

    def tearDown(self) -> None:
        self.service.close()
        self.temp_dir.cleanup()

    def test_response_is_persisted_in_session(self) -> None:
        response = self.service.respond(session_id="session-1", user_id="user-1", message="Help me plan my day")
        self.assertTrue(response.trace_id.startswith("atl-"))
        history = self.service.store.recent_messages("session-1")
        self.assertEqual([turn["role"] for turn in history], ["user", "assistant"])

    def test_write_requires_explicit_approval(self) -> None:
        proposed = self.service.propose_action(
            session_id="session-1",
            user_id="user-1",
            action_type="write_file",
            payload={"path": "notes/today.txt", "content": "hello"},
        )
        self.assertEqual(proposed["status"], "pending_approval")
        self.assertFalse((self.workspace / "notes" / "today.txt").exists())

        result = self.service.approve_action(proposed["id"], user_id="user-1")
        self.assertEqual(result["status"], "completed")
        self.assertEqual((self.workspace / "notes" / "today.txt").read_text(), "hello")

    def test_paths_cannot_escape_workspace(self) -> None:
        proposed = self.service.propose_action(
            session_id="session-1",
            user_id="user-1",
            action_type="read_file",
            payload={"path": "../secret.txt"},
        )
        self.assertEqual(proposed["status"], "failed")
        self.assertIn("escapes", proposed["result"]["error"])

    def test_memory_is_user_scoped(self) -> None:
        self.service.remember(user_id="user-1", kind="preference", content="Prefer concise responses")
        self.assertEqual(len(self.service.store.list_memories("user-1")), 1)
        self.assertEqual(self.service.store.list_memories("user-2"), [])

    def test_configured_provider_can_only_return_text(self) -> None:
        service = AtulyaService(self.settings, provider=FakeProvider())
        try:
            response = service.respond(session_id="session-2", user_id="user-1", message="hello")
            self.assertEqual(response.model_source, "fake")
            self.assertEqual(response.content, "Model reply to: hello")
        finally:
            service.close()


if __name__ == "__main__":
    unittest.main()

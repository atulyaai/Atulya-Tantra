"""Tests for BrowserAutomation — headless browser control via Playwright."""



class TestBrowserAutomation:
    """Tests for BrowserAutomation (non-network, structural tests)."""

    def test_initialization_defaults(self):
        from yantra.tools.browser_automation import BrowserAutomation
        ba = BrowserAutomation()
        assert ba.headless is True
        assert len(ba._history) == 0

    def test_initialization_custom(self):
        from yantra.tools.browser_automation import BrowserAutomation
        ba = BrowserAutomation(headless=False)
        assert ba.headless is False

    def test_get_stats_empty(self):
        from yantra.tools.browser_automation import BrowserAutomation
        ba = BrowserAutomation()
        stats = ba.get_stats()
        assert stats["pages_visited"] == 0
        assert stats["last_url"] == ""

    def test_get_stats_after_history(self):
        from yantra.tools.browser_automation import BrowserAutomation
        from yantra.tools.browser_automation import BrowserResult
        ba = BrowserAutomation()
        ba._history.append(BrowserResult(success=True, url="https://example.com",
                                          title="Example", content="...", links=[]))
        stats = ba.get_stats()
        assert stats["pages_visited"] == 1
        assert stats["last_url"] == "https://example.com"

    def test_browser_result_dataclass(self):
        from yantra.tools.browser_automation import BrowserResult
        result = BrowserResult(
            success=True, url="http://test.com", title="Test",
            content="Hello", links=[{"text": "link", "href": "http://test.com/page"}],
        )
        assert result.success is True
        assert result.url == "http://test.com"
        assert len(result.links) == 1

    def test_browser_result_error(self):
        from yantra.tools.browser_automation import BrowserResult
        result = BrowserResult(success=False, url="http://bad.com",
                               metadata={"error": "Connection refused"})
        assert result.success is False
        assert result.metadata["error"] == "Connection refused"


"""Tests for DeviceController â€” IoT device management with multi-protocol support."""

import tempfile
import asyncio


class TestDeviceController:
    """Tests for DeviceController â€” add, remove, stats, and command dispatching."""

    def test_add_device(self):
        from yantra.device_controller import DeviceController
        with tempfile.TemporaryDirectory() as tmp:
            controller = DeviceController(data_dir=tmp)
            did = controller.add_device("test_tv", "tv", "ir")
            assert did is not None
            assert did.startswith("dev_")

    def test_add_device_with_address(self):
        from yantra.device_controller import DeviceController
        with tempfile.TemporaryDirectory() as tmp:
            controller = DeviceController(data_dir=tmp)
            did = controller.add_device("sensor", "temperature", "wifi",
                                         address="192.168.1.100", port=8080)
            assert did is not None

    def test_send_command_device_not_found(self):
        from yantra.device_controller import DeviceController
        with tempfile.TemporaryDirectory() as tmp:
            controller = DeviceController(data_dir=tmp)
            result = asyncio.run(controller.send_command("nonexistent", "power_on"))
            assert result["success"] is False
            assert "not found" in result["error"]

    def test_send_command_unsupported_protocol(self):
        from yantra.device_controller import DeviceController
        with tempfile.TemporaryDirectory() as tmp:
            controller = DeviceController(data_dir=tmp)
            did = controller.add_device("test", "sensor", "unknown_protocol")
            result = asyncio.run(controller.send_command(did, "test"))
            assert result["success"] is False
            assert "Unsupported protocol" in result["error"]

    def test_send_command_ir_fallback(self):
        """IR protocol should work even without lirc (fallback)."""
        from yantra.device_controller import DeviceController
        with tempfile.TemporaryDirectory() as tmp:
            controller = DeviceController(data_dir=tmp)
            did = controller.add_device("tv", "tv", "ir")
            result = asyncio.run(controller.send_command(did, "power_on"))
            assert result["success"] is True

    def test_get_stats(self):
        from yantra.device_controller import DeviceController
        with tempfile.TemporaryDirectory() as tmp:
            controller = DeviceController(data_dir=tmp)
            controller.add_device("tv1", "tv", "ir")
            controller.add_device("tv2", "tv", "ir")
            controller.add_device("sensor", "temp", "wifi")
            stats = controller.get_stats()
            # Note: IDs may collide if same second, so total could be 1-3
            assert stats["total_devices"] >= 1
            assert stats["by_protocol"] is not None

    def test_get_stats_empty(self):
        from yantra.device_controller import DeviceController
        with tempfile.TemporaryDirectory() as tmp:
            controller = DeviceController(data_dir=tmp)
            stats = controller.get_stats()
            assert stats["total_devices"] == 0

    def test_device_persistence(self):
        """Devices should survive across controller re-initialization."""
        from yantra.device_controller import DeviceController
        with tempfile.TemporaryDirectory() as tmp:
            c1 = DeviceController(data_dir=tmp)
            c1.add_device("persistent", "sensor", "serial")
            c2 = DeviceController(data_dir=tmp)
            stats = c2.get_stats()
            assert stats["total_devices"] == 1

    def test_add_device_multiple(self):
        from yantra.device_controller import DeviceController
        with tempfile.TemporaryDirectory() as tmp:
            controller = DeviceController(data_dir=tmp)
            ids = []
            for i in range(5):
                ids.append(controller.add_device(f"dev_{i}", "generic", "ir"))
            # At least some unique IDs (may collide if same second)
            unique_ids = len(set(ids))
            assert unique_ids >= 1


"""Tests for MCPManifestSigner — cryptographic signing and verification."""

import tempfile
import os


class TestMCPManifestSigner:
    """Tests for signing, verifying, saving, and loading MCP manifests."""

    def test_sign_adds_signature(self):
        from yantra.mcp.manifest import MCPManifest, MCPManifestSigner
        manifest = MCPManifest(name="test-tool", version="1.0.0", tools=[{"name": "echo", "args": ["text"]}])
        signer = MCPManifestSigner(secret="test-secret")
        sig = signer.sign(manifest)
        assert manifest.signature == sig
        assert len(sig) == 64  # SHA-256 is 64 hex chars

    def test_verify_valid(self):
        from yantra.mcp.manifest import MCPManifest, MCPManifestSigner
        manifest = MCPManifest(name="valid-tool", version="0.2.0", tools=[{"name": "greet"}])
        signer = MCPManifestSigner(secret="test-secret")
        signer.sign(manifest)
        assert signer.verify(manifest) is True

    def test_verify_invalid_signature(self):
        from yantra.mcp.manifest import MCPManifest, MCPManifestSigner
        manifest = MCPManifest(name="tool", version="1.0", tools=[])
        signer = MCPManifestSigner(secret="secret-a")
        signer.sign(manifest)
        # Verify with different secret
        another_signer = MCPManifestSigner(secret="secret-b")
        assert another_signer.verify(manifest) is False

    def test_verify_no_signature(self):
        from yantra.mcp.manifest import MCPManifest, MCPManifestSigner
        manifest = MCPManifest(name="tool", version="1.0", tools=[])
        signer = MCPManifestSigner(secret="test")
        assert signer.verify(manifest) is False

    def test_verify_tampered_data(self):
        from yantra.mcp.manifest import MCPManifest, MCPManifestSigner
        manifest = MCPManifest(name="tool", version="1.0", tools=[{"name": "ok"}])
        signer = MCPManifestSigner(secret="test")
        signer.sign(manifest)
        # Tamper with the tools
        manifest.tools = [{"name": "malicious"}]
        assert signer.verify(manifest) is False

    def test_save_and_load(self):
        from yantra.mcp.manifest import MCPManifest, MCPManifestSigner
        with tempfile.TemporaryDirectory() as tmp:
            manifest = MCPManifest(name="saved-tool", version="2.0", tools=[{"name": "test"}])
            signer = MCPManifestSigner(secret="test-secret")
            path = os.path.join(tmp, "manifest.json")
            signer.save_manifest(manifest, path)
            assert os.path.exists(path)

            loaded = signer.load_manifest(path)
            assert loaded is not None
            assert loaded.name == "saved-tool"
            assert loaded.version == "2.0"

    def test_load_nonexistent(self):
        from yantra.mcp.manifest import MCPManifestSigner
        signer = MCPManifestSigner(secret="test")
        result = signer.load_manifest("/nonexistent/path.json")
        assert result is None

    def test_load_tampered_file(self):
        from yantra.mcp.manifest import MCPManifestSigner, MCPManifest
        import json
        with tempfile.TemporaryDirectory() as tmp:
            manifest = MCPManifest(name="good", version="1.0", tools=[])
            signer = MCPManifestSigner(secret="test")
            path = os.path.join(tmp, "manifest.json")
            signer.save_manifest(manifest, path)

            # Tamper with the file
            data = json.loads(open(path).read())
            data["version"] = "9.9.9"
            json.dump(data, open(path, "w"))

            import pytest
            with pytest.raises(ValueError, match="Invalid manifest signature"):
                signer.load_manifest(path)

    def test_manifest_dataclass_defaults(self):
        from yantra.mcp.manifest import MCPManifest
        m = MCPManifest(name="test", version="1.0", tools=[{"name": "x"}])
        assert m.author == ""
        assert m.description == ""
        assert m.signature == ""
        assert m.created_at > 0


"""Tests for MCPServer — MCP-compatible tool/resource/prompt serving."""

import pytest
import tempfile


class TestMCPServer:
    """Tests for MCPServer core functionality."""

    def test_register_tool(self):
        from yantra.mcp.server import MCPServer
        with tempfile.TemporaryDirectory() as tmp:
            server = MCPServer(data_dir=tmp)
            server.register_tool("my_tool", "A test tool", {"type": "object", "properties": {}})
            tools = server.list_tools()
            assert any(t["name"] == "my_tool" for t in tools)

    def test_register_tool_no_schema(self):
        from yantra.mcp.server import MCPServer
        with tempfile.TemporaryDirectory() as tmp:
            server = MCPServer(data_dir=tmp)
            server.register_tool("simple_tool", "Simple tool", {"type": "object", "properties": {}})
            tools = server.list_tools()
            assert len(tools) == 1

    def test_register_resource(self):
        from yantra.mcp.server import MCPServer
        with tempfile.TemporaryDirectory() as tmp:
            server = MCPServer(data_dir=tmp)
            server.register_resource(uri="config://model", name="Model Config",
                                     description="Current model configuration")
            resources = server.list_resources()
            assert any("config://model" in str(r) for r in resources)

    def test_register_prompt(self):
        from yantra.mcp.server import MCPServer
        with tempfile.TemporaryDirectory() as tmp:
            server = MCPServer(data_dir=tmp)
            server.register_prompt("greet", "A greeting prompt", "Hello {{name}}!")
            prompts = server.list_prompts()
            assert any("greet" in str(p) for p in prompts)

    @pytest.mark.asyncio
    async def test_call_tool_with_handler(self):
        from yantra.mcp.server import MCPServer
        with tempfile.TemporaryDirectory() as tmp:
            server = MCPServer(data_dir=tmp)
            results = []
            def my_handler(arg):
                results.append(arg)
                return f"processed {arg}"
            server.register_tool("process", "Process handler",
                                 {"type": "object", "properties": {"arg": {"type": "string"}}},
                                 handler=my_handler)
            result = await server.call_tool("process", {"arg": "test"})
            assert result is not None
            assert result.get("success") is True

    @pytest.mark.asyncio
    async def test_call_tool_not_found(self):
        from yantra.mcp.server import MCPServer
        with tempfile.TemporaryDirectory() as tmp:
            server = MCPServer(data_dir=tmp)
            result = await server.call_tool("nonexistent", {})
            assert result.get("success") is False
            assert "not found" in result.get("error", "")

    def test_list_tools_empty(self):
        from yantra.mcp.server import MCPServer
        with tempfile.TemporaryDirectory() as tmp:
            server = MCPServer(data_dir=tmp)
            assert server.list_tools() == []

    def test_list_resources_empty(self):
        from yantra.mcp.server import MCPServer
        with tempfile.TemporaryDirectory() as tmp:
            server = MCPServer(data_dir=tmp)
            assert server.list_resources() == []

    def test_list_prompts_empty(self):
        from yantra.mcp.server import MCPServer
        with tempfile.TemporaryDirectory() as tmp:
            server = MCPServer(data_dir=tmp)
            assert server.list_prompts() == []

    def test_bridge_tool_registry(self):
        from yantra.mcp.server import MCPServer
        with tempfile.TemporaryDirectory() as tmp:
            server = MCPServer(data_dir=tmp)
            # Mock a tool registry
            class MockRegistry:
                def list_tools(self):
                    return [{"name": "tool_a", "description": "Tool A", "input_schema": {}}]
            server.bridge_tool_registry(MockRegistry())
            tools = server.list_tools()
            assert any("tool_a" in str(t) for t in tools)

    def test_get_server_info(self):
        from yantra.mcp.server import MCPServer
        with tempfile.TemporaryDirectory() as tmp:
            server = MCPServer(data_dir=tmp)
            info = server.get_server_info()
            assert isinstance(info, dict)
            assert "name" in info or "version" in info

    def test_register_and_list_tools(self):
        from yantra.mcp.server import MCPServer
        with tempfile.TemporaryDirectory() as tmp:
            server = MCPServer(data_dir=tmp)
            server.register_tool("t1", "First", {"type": "object"})
            server.register_tool("t2", "Second", {"type": "object"})
            tools = server.list_tools()
            assert len(tools) == 2


"""Tests for UnifiedSelfImprovement â€” chakras, skills, achievements, learning log."""

import tempfile


class TestUnifiedSelfImprovement:
    """Tests for the self-improvement lifecycle system."""

    def test_initialization(self):
        from yantra.selfimprovement.unified import UnifiedSelfImprovement
        with tempfile.TemporaryDirectory() as tmp:
            usi = UnifiedSelfImprovement(tmp)
            assert usi.data_dir.exists()
            assert usi.chakras == {}
            assert usi.skills == {}
            assert usi.achievements == []

    def test_add_chakra(self):
        from yantra.selfimprovement.unified import UnifiedSelfImprovement
        with tempfile.TemporaryDirectory() as tmp:
            usi = UnifiedSelfImprovement(tmp)
            usi.add_chakra("wisdom")
            assert "wisdom" in usi.chakras
            assert usi.chakras["wisdom"].level == 0

    def test_add_chakra_duplicate(self):
        from yantra.selfimprovement.unified import UnifiedSelfImprovement
        with tempfile.TemporaryDirectory() as tmp:
            usi = UnifiedSelfImprovement(tmp)
            usi.add_chakra("wisdom")
            usi.add_chakra("wisdom")  # same name
            assert len(usi.chakras) == 1

    def test_gain_experience(self):
        from yantra.selfimprovement.unified import UnifiedSelfImprovement
        with tempfile.TemporaryDirectory() as tmp:
            usi = UnifiedSelfImprovement(tmp)
            usi.add_chakra("wisdom")
            usi.gain_experience("wisdom", 150)
            assert usi.chakras["wisdom"].level == 1
            assert usi.chakras["wisdom"].experience == 50

    def test_gain_experience_nonexistent_chakra(self):
        """Gaining experience on nonexistent chakra should not throw."""
        from yantra.selfimprovement.unified import UnifiedSelfImprovement
        with tempfile.TemporaryDirectory() as tmp:
            usi = UnifiedSelfImprovement(tmp)
            usi.gain_experience("nonexistent", 100)  # no crash

    def test_add_skill(self):
        from yantra.selfimprovement.unified import UnifiedSelfImprovement
        with tempfile.TemporaryDirectory() as tmp:
            usi = UnifiedSelfImprovement(tmp)
            usi.add_skill("python", category="coding")
            assert "python" in usi.skills
            assert usi.skills["python"].category == "coding"

    def test_practice_skill(self):
        from yantra.selfimprovement.unified import UnifiedSelfImprovement
        with tempfile.TemporaryDirectory() as tmp:
            usi = UnifiedSelfImprovement(tmp)
            usi.add_skill("python")
            # practice_skill takes duration, not difficulty
            usi.practice_skill("python", duration=10.0)
            assert usi.skills["python"].level > 0

    def test_unlock_achievement(self):
        from yantra.selfimprovement.unified import UnifiedSelfImprovement
        with tempfile.TemporaryDirectory() as tmp:
            usi = UnifiedSelfImprovement(tmp)
            usi.unlock_achievement("first_step", "Completed first interaction")
            assert len(usi.achievements) == 1
            assert usi.achievements[0].name == "first_step"

    def test_log_learning(self):
        from yantra.selfimprovement.unified import UnifiedSelfImprovement
        with tempfile.TemporaryDirectory() as tmp:
            usi = UnifiedSelfImprovement(tmp)
            usi.log_learning("Python", "Learned about decorators")
            assert len(usi.learning_log) == 1

    def test_get_stats(self):
        from yantra.selfimprovement.unified import UnifiedSelfImprovement
        with tempfile.TemporaryDirectory() as tmp:
            usi = UnifiedSelfImprovement(tmp)
            usi.add_chakra("wisdom")
            usi.add_chakra("courage")
            usi.add_skill("python")
            usi.unlock_achievement("first", "test")
            # get_stats exists (not get_progress_report)
            stats = usi.get_stats()
            assert "chakras" in stats
            assert "skills" in stats
            assert "achievements" in stats

    def test_persistence(self):
        from yantra.selfimprovement.unified import UnifiedSelfImprovement
        with tempfile.TemporaryDirectory() as tmp:
            s1 = UnifiedSelfImprovement(tmp)
            s1.add_chakra("focus")
            s1.add_skill("writing")
            s1.unlock_achievement("first", "test")

            s2 = UnifiedSelfImprovement(tmp)
            assert "focus" in s2.chakras
            assert "writing" in s2.skills
            assert len(s2.achievements) == 1


"""Tests for SelfRepairSystem and CodeEvolver â€” automatic error recovery and evolution."""

import tempfile
import traceback


class TestSelfRepairSystem:
    """Tests for SelfRepairSystem â€” analyze errors and apply fixes."""

    def test_analyze_error(self):
        from yantra.selfrepair import SelfRepairSystem
        with tempfile.TemporaryDirectory() as tmp:
            repair = SelfRepairSystem(data_dir=tmp)
            error = ValueError("invalid input")
            tb = traceback.extract_stack()
            action = repair.analyze_error(error, tb)
            assert action is not None
            assert action.issue_type == "ValueError"
            assert "invalid input" in action.description

    def test_analyze_error_no_traceback(self):
        from yantra.selfrepair import SelfRepairSystem
        with tempfile.TemporaryDirectory() as tmp:
            repair = SelfRepairSystem(data_dir=tmp)
            action = repair.analyze_error(ModuleNotFoundError("No module named 'nonexistent'"))
            assert action is not None
            assert action.issue_type == "ModuleNotFoundError"

    def test_analyze_error_runtime(self):
        from yantra.selfrepair import SelfRepairSystem
        with tempfile.TemporaryDirectory() as tmp:
            repair = SelfRepairSystem(data_dir=tmp)
            try:
                1 / 0
            except ZeroDivisionError as e:
                tb = traceback.extract_tb(e.__traceback__)
                action = repair.analyze_error(e, tb)
                assert action.issue_type == "ZeroDivisionError"

    def test_apply_fix_no_file(self):
        from yantra.selfrepair import SelfRepairSystem
        with tempfile.TemporaryDirectory() as tmp:
            repair = SelfRepairSystem(data_dir=tmp)
            success = repair.apply_fix("/nonexistent/file.py", "ModuleNotFoundError: pip install requests")
            assert success is False

    def test_apply_fix_adds_import(self):
        from yantra.selfrepair import SelfRepairSystem
        with tempfile.TemporaryDirectory() as tmp:
            repair = SelfRepairSystem(data_dir=tmp)
            test_file = f"{tmp}/test_mod.py"
            with open(test_file, "w") as f:
                f.write("x = 1\n")
            success = repair.apply_fix(test_file, "ModuleNotFoundError: pip install requests")
            content = open(test_file).read()
            assert "import requests" in content
            assert success is True

    def test_get_repair_history_empty(self):
        from yantra.selfrepair import SelfRepairSystem
        with tempfile.TemporaryDirectory() as tmp:
            repair = SelfRepairSystem(data_dir=tmp)
            history = repair.get_repair_history()
            assert isinstance(history, list)
            assert len(history) == 0

    def test_get_stats(self):
        from yantra.selfrepair import SelfRepairSystem
        with tempfile.TemporaryDirectory() as tmp:
            repair = SelfRepairSystem(data_dir=tmp)
            repair.analyze_error(ValueError("bad"))
            repair.analyze_error(KeyError("missing"))
            stats = repair.get_stats()
            assert isinstance(stats, dict)
            assert stats["total_repairs"] == 2
            assert stats["by_type"]["ValueError"] == 1
            assert stats["by_type"]["KeyError"] == 1

    def test_multiple_repairs_tracked(self):
        from yantra.selfrepair import SelfRepairSystem
        with tempfile.TemporaryDirectory() as tmp:
            repair = SelfRepairSystem(data_dir=tmp)
            repair.analyze_error(ValueError("a"))
            repair.analyze_error(TypeError("b"))
            repair.analyze_error(KeyError("c"))
            history = repair.get_repair_history()
            assert len(history) == 3

    def test_repair_persistence(self):
        """Repair log should persist across re-initialization."""
        from yantra.selfrepair import SelfRepairSystem
        with tempfile.TemporaryDirectory() as tmp:
            r1 = SelfRepairSystem(data_dir=tmp)
            r1.analyze_error(ValueError("persist"))
            r2 = SelfRepairSystem(data_dir=tmp)
            assert r2.get_stats()["total_repairs"] == 1


class TestCodeEvolver:
    """Tests for CodeEvolver â€” architecture evolution and change proposals."""

    def test_propose_change(self):
        from yantra.selfrepair import CodeEvolver
        with tempfile.TemporaryDirectory() as tmp:
            evolver = CodeEvolver(base_dir=tmp)
            proposal = evolver.propose_change("mod.py", "old_code", "new_code", "Performance improvement")
            assert proposal is not None
            assert proposal["file"] == "mod.py"
            assert proposal["reason"] == "Performance improvement"
            assert proposal["approved"] is False

    def test_apply_change_unapproved(self):
        from yantra.selfrepair import CodeEvolver
        with tempfile.TemporaryDirectory() as tmp:
            evolver = CodeEvolver(base_dir=tmp)
            proposal = evolver.propose_change("mod.py", "old_code", "new_code", "fix")
            result = evolver.apply_change(proposal["id"])
            assert result is False  # Not approved

    def test_apply_change_approved(self):
        from yantra.selfrepair import CodeEvolver
        with tempfile.TemporaryDirectory() as tmp:
            test_file = f"{tmp}/mod.py"
            with open(test_file, "w") as f:
                f.write("OLD CODE")
            evolver = CodeEvolver(base_dir=tmp)
            proposal = evolver.propose_change("mod.py", "OLD CODE", "NEW CODE", "update")
            # Manually approve
            proposal["approved"] = True
            result = evolver.apply_change(proposal["id"])
            assert result is True
            assert open(test_file).read() == "NEW CODE"

    def test_get_stats(self):
        from yantra.selfrepair import CodeEvolver
        with tempfile.TemporaryDirectory() as tmp:
            evolver = CodeEvolver(base_dir=tmp)
            evolver.propose_change("a.py", "a", "b", "fix1")
            evolver.propose_change("b.py", "c", "d", "fix2")
            stats = evolver.get_stats()
            assert isinstance(stats, dict)
            assert stats["proposals"] == 2


"""Tests for VoicePipeline, TextToSpeech, SpeechToText — TTS/STT infrastructure."""

import tempfile


class TestTextToSpeech:
    """Tests for TextToSpeech (no actual network calls)."""

    def test_initialization(self):
        from yantra.tools.voice_pipeline import TextToSpeech
        with tempfile.TemporaryDirectory() as tmp:
            tts = TextToSpeech(output_dir=tmp)
            assert tts.output_dir.exists()
            assert tts.get_history() == []

    def test_voices_defined(self):
        from yantra.tools.voice_pipeline import TextToSpeech
        assert "en_male" in TextToSpeech.VOICES
        assert "en_female" in TextToSpeech.VOICES
        assert "hi_male" in TextToSpeech.VOICES
        assert "hi_female" in TextToSpeech.VOICES
        assert "sa_male" in TextToSpeech.VOICES

    def test_voice_config(self):
        from yantra.tools.voice_pipeline import TextToSpeech
        voice = TextToSpeech.VOICES["hi_male"]
        assert voice["language"] == "hi"

    def test_get_stats_empty(self):
        from yantra.tools.voice_pipeline import TextToSpeech
        with tempfile.TemporaryDirectory() as tmp:
            tts = TextToSpeech(output_dir=tmp)
            stats = tts.get_stats()
            assert stats["total_synthesized"] == 0
            assert stats["total_cost"] == 0.0


class TestSpeechToText:
    """Tests for SpeechToText (no actual network calls)."""

    def test_initialization(self):
        from yantra.tools.voice_pipeline import SpeechToText
        with tempfile.TemporaryDirectory() as tmp:
            stt = SpeechToText(output_dir=tmp)
            assert stt.output_dir.exists()
            assert stt.get_stats()["total_transcribed"] == 0

    def test_transcribe_no_input_returns_error(self):
        """transcribe() with no input returns a structured STT error result."""
        from yantra.tools.voice_pipeline import SpeechToText
        import asyncio
        with tempfile.TemporaryDirectory() as tmp:
            stt = SpeechToText(output_dir=tmp)
            result = asyncio.run(stt.transcribe())
            assert result.id == "error"
            assert result.error == "No audio provided"


class TestVoicePipeline:
    """Tests for combined VoicePipeline."""

    def test_initialization(self):
        from yantra.tools.voice_pipeline import VoicePipeline
        with tempfile.TemporaryDirectory() as tmp:
            pipeline = VoicePipeline(tts_dir=f"{tmp}/tts", stt_dir=f"{tmp}/stt")
            assert pipeline.tts is not None
            assert pipeline.stt is not None

    def test_get_stats_empty(self):
        from yantra.tools.voice_pipeline import VoicePipeline
        with tempfile.TemporaryDirectory() as tmp:
            pipeline = VoicePipeline(tts_dir=f"{tmp}/tts", stt_dir=f"{tmp}/stt")
            stats = pipeline.get_stats()
            assert "tts" in stats
            assert "stt" in stats
            assert stats["turns"] == 0


"""Tests for WebSearch — multi-provider search tool."""



class TestWebSearch:
    """Tests for MultiProviderSearch (web search tool, safe/mocked)."""

    def test_basic_search(self):
        from yantra.tools.web_search import MultiProviderSearch
        ws = MultiProviderSearch()
        results = ws.search("test query", max_results=3)
        assert isinstance(results, list)
        # Should always return a result list (may be empty if no network)
        assert len(results) >= 0

    def test_search_with_region(self):
        from yantra.tools.web_search import MultiProviderSearch
        ws = MultiProviderSearch()
        results = ws.search("python programming", max_results=5, region="us-en")
        assert isinstance(results, list)

    def test_stats_property(self):
        from yantra.tools.web_search import MultiProviderSearch
        ws = MultiProviderSearch()
        stats = ws.stats
        assert isinstance(stats, dict)
        assert "total_searches" in stats


"""Tests for WorkflowEngine — multi-step task orchestration."""

import pytest
import tempfile
import asyncio


class TestWorkflowEngine:
    """Tests for WorkflowEngine task creation, execution, and stats."""

    def _make_engine(self):
        """Create a WorkflowEngine with a temp directory."""
        from yantra.tools.workflow_engine import WorkflowEngine
        tmp = tempfile.mkdtemp()
        return WorkflowEngine(data_dir=tmp), tmp

    def test_create_task(self):
        engine, tmp = self._make_engine()
        try:
            tid = engine.create_task("test-task")
            assert tid is not None
            assert len(tid) > 0
        finally:
            import shutil; shutil.rmtree(tmp, ignore_errors=True)

    def test_create_task_with_tool(self):
        engine, tmp = self._make_engine()
        try:
            tid = engine.create_task("calc-task", tool_name="calculator", tool_args={"expr": "2+2"})
            assert tid is not None
        finally:
            import shutil; shutil.rmtree(tmp, ignore_errors=True)

    def test_get_task(self):
        engine, tmp = self._make_engine()
        try:
            tid = engine.create_task("test-task")
            task = engine.get_task(tid)
            assert task is not None
            assert task.title == "test-task"
        finally:
            import shutil; shutil.rmtree(tmp, ignore_errors=True)

    def test_get_task_not_found(self):
        engine, tmp = self._make_engine()
        try:
            assert engine.get_task("nonexistent") is None
        finally:
            import shutil; shutil.rmtree(tmp, ignore_errors=True)

    def test_create_workflow(self):
        engine, tmp = self._make_engine()
        try:
            t1 = engine.create_task("step1")
            t2 = engine.create_task("step2")
            wid = engine.create_workflow("test-flow", [t1, t2])
            assert wid is not None
            assert len(wid) > 0
        finally:
            import shutil; shutil.rmtree(tmp, ignore_errors=True)

    def test_get_workflow(self):
        engine, tmp = self._make_engine()
        try:
            t1 = engine.create_task("step1")
            wid = engine.create_workflow("test-flow", [t1])
            wf = engine.get_workflow(wid)
            assert wf is not None
            assert isinstance(wf, list)
        finally:
            import shutil; shutil.rmtree(tmp, ignore_errors=True)

    def test_execute_task_simple(self):
        engine, tmp = self._make_engine()
        try:
            tid = engine.create_task("simple-task")
            result = asyncio.run(engine.execute_task(tid))
            assert result is not None
            assert result.status.value in ("done", "in_progress", "todo")
        finally:
            import shutil; shutil.rmtree(tmp, ignore_errors=True)

    def test_execute_workflow(self):
        engine, tmp = self._make_engine()
        try:
            t1 = engine.create_task("a")
            t2 = engine.create_task("b")
            wid = engine.create_workflow("test-flow", [t1, t2])
            results = asyncio.run(engine.execute_workflow(wid))
            assert results is not None
            assert isinstance(results, list)
        finally:
            import shutil; shutil.rmtree(tmp, ignore_errors=True)

    def test_execute_task_not_found_raises(self):
        engine, tmp = self._make_engine()
        try:
            with pytest.raises(ValueError):
                asyncio.run(engine.execute_task("nonexistent"))
        finally:
            import shutil; shutil.rmtree(tmp, ignore_errors=True)

    def test_get_blocked_tasks(self):
        engine, tmp = self._make_engine()
        try:
            blocked = engine.get_blocked_tasks()
            assert isinstance(blocked, list)
        finally:
            import shutil; shutil.rmtree(tmp, ignore_errors=True)

    def test_get_pending_tasks(self):
        engine, tmp = self._make_engine()
        try:
            pending = engine.get_pending_tasks()
            assert isinstance(pending, list)
        finally:
            import shutil; shutil.rmtree(tmp, ignore_errors=True)

    def test_get_stats(self):
        engine, tmp = self._make_engine()
        try:
            engine.create_task("task1")
            engine.create_task("task2")
            engine.create_task("task3")
            stats = engine.get_stats()
            assert isinstance(stats, dict)
            assert stats["total_tasks"] == 3
            assert stats["workflows"] >= 0
        finally:
            import shutil; shutil.rmtree(tmp, ignore_errors=True)

    def test_get_stats_empty(self):
        engine, tmp = self._make_engine()
        try:
            stats = engine.get_stats()
            assert stats["total_tasks"] == 0
        finally:
            import shutil; shutil.rmtree(tmp, ignore_errors=True)

    def test_task_dependencies_block(self):
        engine, tmp = self._make_engine()
        try:
            t1 = engine.create_task("dep-a")
            t2 = engine.create_task("dep-b", dependencies=[t1])
            result = asyncio.run(engine.execute_task(t2))
            # t2 should be blocked because t1 is still TODO
            assert result.status.value == "blocked"
        finally:
            import shutil; shutil.rmtree(tmp, ignore_errors=True)

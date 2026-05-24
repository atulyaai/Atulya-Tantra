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

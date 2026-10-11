# Atulya MCP server

Atulya has an optional MCP server implemented with the official MIT-licensed Python SDK. The MCP runtime is pinned in `pyproject.toml` and the startup lock, and `tools/bootstrap.py` repairs it automatically if it is missing. The server runs over **stdio** when an MCP host launches `python -m atulya.cli mcp`; it does not open a network port.

## Registered capabilities

- `weather(city)`: current weather from the existing Open-Meteo information plugin.
- `news_headlines(limit)`: up to ten headlines from the existing BBC RSS information plugin.
- `get_time()` and `calculate(expression)`: local clock and safe calculator.
- One prompt per skill in `tools/skills/` (for example `daily_briefing(request)`), carrying that skill's instructions.

Plugins disabled in the WebUI (`data/plugin_settings.json`) are not exposed. The server exposes public information only. It does not expose private Atulya history, local files, code editing, shell commands, accounts, or MQTT. Tool failures return short safe messages; provider error details are not sent to the MCP client. Weather and news require network access when invoked.

## Setup and use

Normal Atulya startup/bootstrap installs the pinned MCP SDK along with the other locked dependencies. MCP stays dormant unless an MCP host launches the `mcp` subcommand. External MCP hosts typically need the project's Python interpreter, working directory, and arguments `-m atulya.cli mcp`; the host-specific connection file is not modified automatically by this project.

Example host entry (Claude Desktop `claude_desktop_config.json`; use your own paths):

```json
{"mcpServers": {"atulya": {"command": "C:/Users/you/Atulya-Tantra/.venv/Scripts/python.exe",
  "args": ["-m", "atulya.cli", "mcp"], "cwd": "C:/Users/you/Atulya-Tantra"}}}
```

The protocol tests use fake upstream providers and the SDK's in-memory client, plus a real stdio subprocess launched through the Atulya CLI. See the [integration roadmap](../../docs/TODO.md#open-source-plugins-mcp-and-skills-roadmap) for file, Git, calendar, email, MQTT, and other adapters that are not implemented yet.

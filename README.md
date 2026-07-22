# LM Studio Vision Bridge

[中文](README.zh-CN.md)

Give eyes to your text-only AI agent — bridge LM Studio local vision models to any agent via MCP protocol or CLI.

## What it does

Text-only LLMs can't process images. Vision-capable models (GPT-4o, Gemini) are either expensive or require sending data to the cloud.
LM Studio lets you run vision models locally, but only exposes an HTTP API — AI agents can't call it directly.

This project is a thin bridge in between:

```
You send an image → AI agent (text-only)
                    → this project's service
                    → LM Studio vision model (local)
                    → text description back to agent
```

Fully local. No data leaves your machine. Zero cost. Only Python stdlib required.

## Which one should I use

| Scenario | Recommended | Why |
|----------|-------------|-----|
| Reasonix / Claude Code / Cursor / any MCP agent | **MCP Server** (mcp-server.py) | Standard MCP protocol, configure once |
| Just want a quick CLI command | **CLI script** (lms-vision.py) | One command, no config |
| Windows users (recommended) | **MCP HTTP Server** (mcp-http-server.py) | HTTP transport, bypasses Windows stdio pipe issues |

---

## Path A: MCP Server (Universal)

### Prerequisites

- LM Studio running with a vision model loaded, API server on (port 1234)
- Python 3.8+

```bash
git clone https://github.com/FuchaZ/lm-studio-vision-bridge.git
cd lm-studio-vision-bridge
```

No `pip install` needed. Just configure your MCP client.

### Configuration

**Reasonix**
```toml
[[plugins]]
name    = "vision"
command = "python"
args    = ["D:\\path\\to\\lm-studio-vision-bridge\\mcp-server.py"]
```

**Claude Code**
```json
{
  "mcpServers": {
    "lm-studio-vision": {
      "command": "python",
      "args": ["/path/to/lm-studio-vision-bridge/mcp-server.py"]
    }
  }
}
```

**OpenCode / Cursor / Windsurf**
```
Name: lm-studio-vision
Type: command
Command: python /path/to/lm-studio-vision-bridge/mcp-server.py
```

**VS Code** — Add to `%APPDATA%\Code\User\mcp.json`:
```json
{
  "servers": {
    "lm-studio-vision": {
      "type": "stdio",
      "command": "python",
      "args": ["D:\\path\\to\\lm-studio-vision-bridge\\mcp-server.py"]
    }
  }
}
```

**Continue.dev**
```json
{
  "experimental": {
    "mcpServers": {
      "lm-studio-vision": {
        "command": "python",
        "args": ["/path/to/lm-studio-vision-bridge/mcp-server.py"]
      }
    }
  }
}
```

After configuration, just tell your agent: "Take a look at this image."

### Windows users

mcp-server.py handles GBK encoding and uses a 120s timeout — ready to use out of the box.
If stdio pipe mode is unstable, try the HTTP server instead (see below).

### Tool

| Parameter | Description |
|-----------|-------------|
| `image_path` | Path to the image file (absolute path recommended) |
| `prompt` | What you want the model to extract |

If the model returns reasoning, the result includes both `--- reasoning ---` and `--- answer ---` sections.

---

## Path B: CLI Script (Quick)

No MCP setup needed? One command to read an image:

```bash
python lms-vision.py image.jpg
python lms-vision.py image.jpg "Describe the text in this image"
```

Auto-detects LM Studio address and model.

### Environment variables

| Variable | Default | Description |
|----------|---------|-------------|
| `VISION_MODEL` | auto-pick first | Specify model name |
| `LM_STUDIO_PORT` | `1234` | LM Studio API port |
| `MODEL_BASE_URL` | auto-detect | Full LM Studio URL, e.g. `http://192.168.1.5:1234` |
| `REQUEST_TIMEOUT` | `120` | Request timeout (seconds) |

---

## Path C: MCP HTTP Server (Windows recommended)

If stdio pipe mode is unstable (common on Windows), use the Python HTTP version:

```bash
python mcp-http-server.py
```

Listens on `http://127.0.0.1:3456`. Configure your MCP client to connect in HTTP mode.

**Auto-detects LM Studio at startup** — no manual address config needed.

Supports the same env vars (`VISION_MODEL`, `LM_STUDIO_PORT`, `MODEL_BASE_URL`), plus:

| Variable | Default | Description |
|----------|---------|-------------|
| `MCP_PORT` | `3456` | HTTP server listening port |

> Legacy `mcp-http-server.cjs` (Node.js) is kept but Python version is recommended.

---

## Auto-detection

LM Studio's IP can change — DHCP renewal, WiFi switch, VPN toggle.
All services auto-probe `127.0.0.1:1234`, `localhost:1234`, and every NIC IP on your machine at startup.

Manual probe:
```powershell
.\scripts\find-lm-studio.ps1
```

## Project structure

```
lm-studio-vision-bridge/
├── lms-vision.py           # CLI script (one-shot image reading)
├── mcp-server.py           # MCP server (stdio transport)
├── mcp-http-server.py      # MCP HTTP server (Windows recommended)
├── mcp-http-server.cjs     # Legacy Node.js HTTP server
├── _bridge.py              # Shared core logic
├── SKILL.md                # Reasonix skill definition
├── README.md               # This file
├── README.zh-CN.md         # Chinese version
└── scripts/
    └── find-lm-studio.ps1  # LM Studio address probe
```

## Why not make it more complex

It does one thing: image to text. No cache, no queue, no multi-model router. If your use case genuinely needs those, add them later — not now.

## License

MIT

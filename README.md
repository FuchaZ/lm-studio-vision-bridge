# LM Studio Vision Bridge

[中文](README.zh-CN.md)

An MCP server that bridges locally-hosted LM Studio vision models to any text-only AI agent — DeepSeek, Claude Code, OpenCode, Cursor, etc.

## What it does

Text-only LLMs (DeepSeek, Claude Sonnet, etc.) can't process images. Vision-capable models (GPT-4o, Gemini) are either expensive or require sending data to the cloud.

LM Studio lets you run vision models locally (minicpm-v, qwen-vl, llava, etc.), but only exposes an HTTP API — AI agents can't call it directly.

This project is a thin MCP server in between:

```
You send an image → AI agent (text-only)
                    → this MCP server
                    → LM Studio vision model (local)
                    → text description back to agent
```

Fully local. No data leaves your machine. Zero cost. No dependencies.

## Highlights

- **Single .py file** — zero external dependencies, only Python stdlib
- **Auto-detects LM Studio** — handles IP changes (DHCP, WiFi switch, VPN) automatically
- **Standard MCP protocol** — works with any MCP-compatible client, not tied to a specific tool

## Quick start

### Prerequisites

LM Studio running with a vision model loaded, API server enabled (port 1234). Python 3.8+.

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

**OpenCode**
```json
{
  "mcp": {
    "lm-studio-vision": {
      "type": "local",
      "command": ["python", "/path/to/lm-studio-vision-bridge/mcp-server.py"],
      "enabled": true
    }
  }
}
```

**Cursor / Windsurf** — In MCP settings:
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

After configuration, just tell your agent: "Take a look at this image: D:\screenshot.png"

## Tool

Single entry point: `read_image_with_model`

| Parameter | Description |
|-----------|-------------|
| `image_path` | Path to the image file (absolute path recommended) |
| `prompt` | What you want the model to extract, e.g. "Describe this image" |

## Why auto-detection

LM Studio's IP can change — DHCP lease renewal, WiFi network switch, VPN toggle. This server automatically probes `127.0.0.1:1234`, `localhost:1234`, and every NIC IP on your machine at startup.

You can also run the probe script manually:
```powershell
.\scripts\find-lm-studio.ps1
```

## Environment variables

Usually not needed. Override if necessary:

- `VISION_MODEL` — default auto-picks the first model in LM Studio
- `LM_STUDIO_PORT` — default `1234`

## Project structure

```
lm-studio-vision-bridge/
├── SKILL.md                # Reasonix skill definition
├── mcp-server.py           # The MCP server (the only file that matters)
├── README.md               # This file
├── README.zh-CN.md         # Chinese version
└── scripts/
    └── find-lm-studio.ps1  # LM Studio address probe
```

## Why not make it more complex

It does one thing: image to text. No cache, no queue, no multi-model router. If your use case genuinely needs those, add them later — not now.

## License

MIT

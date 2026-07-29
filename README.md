# LM Studio Vision Bridge

[中文](README.zh-CN.md)

Give eyes to your text-only AI agent — bridge LM Studio local vision models to any agent via MCP protocol or CLI.

## Quick Start: 5 minutes

### 1️⃣ Install LM Studio
Download from [lmstudio.ai/download](https://lmstudio.ai/download) and install.

### 2️⃣ Download a vision model

**Recommended model: [MiniCPM-V-4.6-Thinking](https://huggingface.co/openbmb/MiniCPM-V-4.6-Thinking-abliterated-MAX)**

Search `minicpm-v` in LM Studio's model search, or download GGUF files from Hugging Face and drag them into the left panel.

GGUF quantization options:

| Model | File size | VRAM | Recommended GPU |
|-------|-----------|------|-----------------|
| MiniCPM-V-4.6-Thinking **Q8_0** | ~10GB | ~8GB VRAM | RTX 4060 / 3060 12GB+ |
| MiniCPM-V-4.6-Thinking **Q4_K_M** | ~5GB | ~5GB VRAM | 6GB+ VRAM |

> **Reference config**: i7-13700H + RTX 4060 (8GB) + 32GB RAM runs Q8_0 smoothly at ~120 token/s

Other vision models (qwen-vl, llava, etc.) also work as long as LM Studio can load them.

### 3️⃣ Load the model and start the API
1. Select your model in LM Studio's left panel
2. Click "Load Model" to load it into VRAM
3. Click "Developer" panel on the left
4. Under "Local Inference Server", click "Start Server"
5. Confirm the port is 1234 (default)

### 4️⃣ Verify the service
```bash
curl http://127.0.0.1:1234/v1/models
```
You should see your model listed.

### 5️⃣ Connect this project
```bash
git clone https://github.com/FuchaZ/lm-studio-vision-bridge.git
cd lm-studio-vision-bridge

# CLI mode: read an image directly
python lms-vision.py image.jpg

# MCP HTTP mode: start the server (Windows recommended)
python mcp-http-server.py
```

Then check "Which one should I use" below to pick your preferred setup.

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
| `VISION_MODEL` | 不设置（使用当前加载的模型）| 指定模型名，覆盖默认行为 |
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

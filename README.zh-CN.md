# LM Studio Vision Bridge

[English](README.md)

把本地 LM Studio 跑的视觉模型挂载成 AI agent 的眼睛——让 DeepSeek、Claude Code、Reasonix 等纯文本 agent 也能识别图片。

## 它解决什么问题

纯文本模型推理能力强但没有视觉。能看图的模型要么贵，要么数据得上云。
LM Studio 可以在本地跑视觉模型（minicpm-v、qwen-vl、llava 等），但它只暴露 HTTP API，agent 无法直接调用。

这个项目在中间搭了一层薄桥：

```
你发送图片 → AI agent（纯文本）
             → 本项目的服务
             → LM Studio 视觉模型（本地）
             → 文字描述返回给 agent
```

全本地运行，图片不离开你的电脑，零成本，零外部依赖，只依赖 Python 标准库。

## 我该选哪个

| 场景 | 推荐方式 | 说明 |
|------|----------|------|
| 使用 Reasonix / Claude Code / Cursor 等支持 MCP 的 agent | **MCP Server**（mcp-server.py） | 标准 MCP 协议，配置一次就能让 agent 自动调 |
| 只想在命令行里快速看图 | **CLI 脚本**（lms-vision.py） | 一句命令出结果，无需配置 |
| Windows 用户（推荐）| **MCP HTTP Server**（mcp-http-server.py） | HTTP 传输，彻底绕开 Windows stdio 管道问题 |

---

## 路径 A：MCP Server（通用集成）

### 前置条件

- LM Studio 正在运行，已加载视觉模型，API 服务已启用（端口 1234）
- Python 3.8+

```bash
git clone https://github.com/FuchaZ/lm-studio-vision-bridge.git
cd lm-studio-vision-bridge
```

无需 `pip install`，直接配置 MCP 客户端。

### 配置方式

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

**VS Code** — 写入 `%APPDATA%\Code\User\mcp.json`：
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

配置完成后，对 agent 说一句「看一下这张图」即可。

### Windows 用户注意

mcp-server.py 已处理 GBK 编码问题和较长的推理超时（120s），开箱即用。
如果 stdio 管道模式不稳定，可以换用 HTTP 版（见下方）。

### 工具

| 参数 | 说明 |
|------|------|
| `image_path` | 图片路径（建议绝对路径） |
| `prompt` | 提示词，告诉模型要看什么 |

如果模型返回了推理过程（reasoning），结果会包含 `--- 推理过程 ---` 和 `--- 最终回答 ---` 两部分。

---

## 路径 B：CLI 脚本（快速调用）

不想配 MCP？一句命令直接看图：

```bash
python lms-vision.py 图片路径.jpg
python lms-vision.py 图片路径.jpg "描述这张图里的文字内容"
```

自动探测 LM Studio 地址和模型，出结果就走。

### 环境变量

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `VISION_MODEL` | 不设置（使用当前加载的模型）| 指定模型名，覆盖默认行为 |
| `LM_STUDIO_PORT` | `1234` | LM Studio API 端口 |
| `MODEL_BASE_URL` | 自动探测 | 指定 LM Studio 完整地址，如 `http://192.168.1.5:1234` |
| `REQUEST_TIMEOUT` | `120` | 请求超时（秒） |

---

## 路径 C：MCP HTTP Server（Windows 推荐）

如果 stdio 管道模式不稳定（Windows 常见问题），使用 HTTP 版：

```bash
python mcp-http-server.py
```

启动后监听 `http://127.0.0.1:3456`。在 MCP 客户端中配置为 HTTP 模式连接此地址。

**启动时自动探测 LM Studio**，无需手动配置地址。

支持的环境变量：`VISION_MODEL`、`LM_STUDIO_PORT`、`MODEL_BASE_URL`（同上），额外支持 `MCP_PORT`（默认 3456）。

> 旧版 `mcp-http-server.cjs`（Node.js）仍保留，但推荐使用 Python 版。

**环境变量：**

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `MCP_PORT` | `3456` | HTTP 服务监听端口 |

---

## 地址自动探测

LM Studio 的 IP 有时会变化——DHCP 续约、WiFi 切换、VPN 等都可能导致地址改变。

本项目的所有服务启动时都会自动扫描 `127.0.0.1:1234`、`localhost:1234` 以及本机所有网卡 IP 的 `:1234` 端口，找到可用的地址即用。

也可以手动探测：
```powershell
.\scripts\find-lm-studio.ps1
```

## 项目结构

```
lm-studio-vision-bridge/
├── lms-vision.py           # CLI 脚本（一句话调 LM Studio）
├── mcp-server.py           # MCP 服务器（stdio 传输）
├── mcp-http-server.py      # MCP HTTP 服务器（Windows 推荐，绕开管道问题）
├── mcp-http-server.cjs     # 旧版 Node.js HTTP 服务器（保留备选）
├── _bridge.py              # 共享核心逻辑
├── SKILL.md                # Reasonix skill 定义
├── README.md               # 英文文档
├── README.zh-CN.md         # 中文文档
└── scripts/
    └── find-lm-studio.ps1  # LM Studio 地址探测脚本
```

## 为什么不做复杂

只做一件事：图片转文字。不需要缓存、不需要并发队列、不需要多模型路由。如果需要，到时再加。

## License

MIT

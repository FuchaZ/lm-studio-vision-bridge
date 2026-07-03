# LM Studio Vision Bridge

**给纯文本 AI agent 装上眼睛。** 通过本地 LM Studio 运行视觉模型，为 DeepSeek、Claude Code、OpenCode 等无多模态能力的 agent 提供图片识别能力。

## 背景

大语言模型的视觉能力（多模态）和推理能力往往是分离的：

- DeepSeek、Claude Sonnet 等 **推理强但无视觉**
- GPT-4o、Gemini 等 **有视觉但成本高、有审查、数据需上传云端**

LM Studio 让你可以在本地跑视觉模型（minicpm-v、qwen-vl、llava 等），但这些模型只能通过 HTTP API 调用，无法直接接入 AI agent 的工作流。

**LM Studio Vision Bridge** 是一个极轻量的 MCP（Model Context Protocol）服务器，它在中间搭一座桥：

```
你发图 → AI Agent (纯文本)
              ↓ (调用 MCP 工具)
    lm-studio-vision-bridge
              ↓ (HTTP API)
    LM Studio 视觉模型（本地）
              ↓ (文字描述)
    AI Agent 获得视觉能力
```

这样你的纯文本 agent 就能「看见」了——而且图片不出本地，零成本，零延迟。

## 核心特点

- 🪶 **极轻量** —— 一个 `.py` 文件，无任何外部依赖（只用 Python 标准库）
- 🏠 **纯本地** —— 不调用任何云端 API，图片不离开你的电脑
- 🔍 **自动探测** —— LM Studio 地址变了（DHCP、WiFi 切换）也不用改配置
- 🔌 **通用 MCP 协议** —— 支持所有 MCP 兼容的 AI agent
- 📦 **Reasonix Skill** —— 可直接在 Reasonix 技能市场安装使用

## 快速开始

### 前置条件

1. [LM Studio](https://lmstudio.ai/) 已安装
2. LM Studio 中加载了一个视觉模型（minicpm-v / qwen-vl / llava 等）
3. LM Studio 的 API 服务已开启（Settings → Local Inference Server → 启用，默认端口 1234）
4. Python 3.8+

### 安装

```bash
git clone https://github.com/<你的用户名>/lm-studio-vision-bridge.git
cd lm-studio-vision-bridge
```

无需 `pip install`，零依赖！

### 注册 MCP 服务器

#### Reasonix

```toml
# config.toml
[[plugins]]
name    = "vision"
command = "python"
args    = ["D:\\path\\to\\lm-studio-vision-bridge\\mcp-server.py"]
```

#### Claude Code

```json
// ~/.claude/.mcp.json
{
  "mcpServers": {
    "lm-studio-vision": {
      "command": "python",
      "args": ["/path/to/lm-studio-vision-bridge/mcp-server.py"]
    }
  }
}
```

#### OpenCode

```jsonc
// opencode.jsonc
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

#### Cursor / Windsurf

在 Cursor 的 MCP 配置中添加：
```
Name: lm-studio-vision
Type: command
Command: python /path/to/lm-studio-vision-bridge/mcp-server.py
```

#### VS Code (Copilot Agent)

```json
// %APPDATA%\Code\User\mcp.json
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

#### Continue.dev

```json
// ~/.continue/config.json
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

### 使用

配置完成后，直接对你的 AI agent 说类似：

> 打开这张图：`D:\screenshot.png`，告诉我里面有什么

Agent 会自动调用 `read_image_with_model` 工具，通过 LM Studio 识别后返回文字描述。

## 工具

### read_image_with_model

| 参数 | 必填 | 说明 |
|------|------|------|
| `image_path` | ✅ | 图片文件路径（支持绝对/相对路径） |
| `prompt` | ✅ | 提示词，告诉视觉模型要看什么 |

**示例：**
```
read_image_with_model(image_path="chart.png", prompt="描述这张图表的趋势和数据")
```

## 自动地址探测

LM Studio 的 IP 可能因 DHCP、WiFi 切换、VPN 等原因变化。本服务器启动时自动扫描：

```
127.0.0.1:1234 → localhost:1234 → 每个网卡 IP:1234
```

找到即用，找不到返回明确错误信息。

你也可以单独运行探测脚本：
```powershell
.\scripts\find-lm-studio.ps1
# → Found: http://192.168.1.5:1234
```

## 环境变量

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `VISION_MODEL` | 自动选择 LM Studio 中第一个模型 | 指定模型名，如 `minicpm-v-4.6` |
| `LM_STUDIO_PORT` | `1234` | LM Studio API 端口 |

## 项目结构

```
lm-studio-vision-bridge/
├── SKILL.md                # Reasonix Skill 定义（ponytail 风格）
├── mcp-server.py           # MCP 服务器（核心，仅此一个文件）
├── README.md               # 本文件
└── scripts/
    └── find-lm-studio.ps1  # LM Studio 地址自动探测脚本
```

## 设计哲学

本项目遵循 **ponytail** 原则（极简、务实）：

- **YAGNI**：只做图片→文字，不做缓存、队列、多模型路由
- **标准库优先**：`mcp-server.py` 只用 Python 标准库，零 `pip install`
- **删除优于添加**：没有配置文件、数据库、初始化脚本
- **最小可行**：一个文件包圆 MCP 协议 + LM Studio 调用 + 地址探测

**什么时候需要加东西？** 当你的视觉模型请求频繁到需要并发控制，或者你要支持多个视觉模型轮询时再加——不是现在。

## 与其他方案对比

| | LM Studio Vision Bridge | vision-tool | lmstudio-mcp |
|---|---|---|---|
| 纯本地运行 | ✅ | ❌ 需要云端 API | ✅ |
| 零外部依赖 | ✅ | ❌ 需要 pillow | ❌ 需要 requests+mcp |
| 自动地址探测 | ✅ | ❌ | ❌ |
| Reasonix Skill | ✅ | ❌ | ❌ |
| 多 agent 支持 | ✅ MCP 标准 | ✅ MCP 标准 | ✅ MCP 标准 |
| 文件数量 | 1 个核心文件 | 21 个文件 | 含 Docker 等多文件 |

## License

MIT

# LM Studio Vision Bridge

[English](README.md)

把本地 LM Studio 跑的视觉模型挂载成 MCP 服务，让 DeepSeek、Claude Code 这类纯文本 agent 也能识别图片。

## 它解决什么问题

纯文本模型（DeepSeek、Claude Sonnet 等）推理能力强但没有视觉能力。能看图的模型（GPT-4o、Gemini）要么收费，要么数据得经过云端。

LM Studio 可以在本地跑视觉模型（minicpm-v、qwen-vl、llava 等），但它只暴露了 HTTP API，AI agent 无法直接调用。

这个项目在中间搭了一层薄的 MCP 服务：

```
你发送图片 → AI agent（纯文本）
             → 本 MCP 服务
             → LM Studio 视觉模型（本地）
             → 文字描述返回给 agent
```

全本地运行，图片不离开你的电脑，零成本，零外部依赖。

## 特点

- **单文件**，只依赖 Python 标准库，无需 `pip install`
- **自动探测 LM Studio 地址**，IP 变化（DHCP 续约、WiFi 切换、VPN 变动）无需手动改配置
- **标准 MCP 协议**，不绑定特定工具，任何 MCP 兼容客户端都能接入

## 快速开始

### 前置条件

LM Studio 正在运行，已加载视觉模型，API 服务已启用（端口 1234）。Python 3.8 以上。

```bash
git clone https://github.com/FuchaZ/lm-studio-vision-bridge.git
cd lm-studio-vision-bridge
```

无需安装依赖，直接配置 MCP 客户端即可。

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

**Cursor / Windsurf** — 在 MCP 设置中添加：
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

配置完成后，对 agent 说一句「看一下这张图 D:\screenshot.png 里有什么」即可。

## 工具

只有一个入口：`read_image_with_model`

| 参数 | 说明 |
|------|------|
| `image_path` | 图片路径（建议使用绝对路径） |
| `prompt` | 提示词，告诉模型要看什么，如"描述这张图" |

## 地址自动探测

LM Studio 的 IP 有时会变化——DHCP 租约续期、WiFi 切换、VPN 开启等都可能导致地址改变。

本服务启动时自动扫描 `127.0.0.1:1234`、`localhost:1234` 以及本机所有网卡 IP 的 `:1234` 端口，找到可用的地址即用。

也可以手动运行探测脚本：
```powershell
.\scripts\find-lm-studio.ps1
```

## 环境变量

通常不需要设置。如需覆盖默认行为：

- `VISION_MODEL` — 默认自动选择 LM Studio 中的第一个模型，可指定具体模型名
- `LM_STUDIO_PORT` — 默认 `1234`

## 项目结构

```
lm-studio-vision-bridge/
├── SKILL.md                # Reasonix skill 定义
├── mcp-server.py           # MCP 服务器（核心文件）
├── README.md               # 英文文档
├── README.zh-CN.md         # 中文文档
└── scripts/
    └── find-lm-studio.ps1  # LM Studio 地址探测脚本
```

## 为什么不做复杂

这个项目只做一件事情：图片转文字。不需要缓存、不需要并发队列、不需要多模型路由。如果后续使用中确实需要这些功能，到时再加不迟。

## License

MIT

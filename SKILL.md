---
name: lm-studio-vision-bridge
description: 通过本地 LM Studio 视觉模型为 Reasonix 及其他 AI agent 提供图片识别能力。零依赖、自动探测地址、纯本地运行。
argument-hint: "[setup|status]"
license: MIT
---

# LM Studio Vision Bridge

纯文本模型（DeepSeek、Claude Sonnet 等）不认识图片。这个 skill 在本地搭一座桥：

```
发图 → Reasonix MCP → mcp-server.py → LM Studio 视觉模型 → 文字描述 → 你
```

不需要 GPU 云、不需要付费 API，只要你的电脑能跑 LM Studio。

## 背景

大语言模型的视觉和推理能力往往是分离的——DeepSeek 推理强但无视觉，GPT-4o 有视觉但成本高。
本项目让你用 LM Studio 在本地跑视觉模型（minicpm-v、qwen-vl、llava 等），通过标准 MCP 协议
给任意纯文本 AI agent 装上眼睛。图片不出本地，零成本零审查。

## 工具

| 工具 | 参数 | 说明 |
|------|------|------|
| `read_image_with_model` | `image_path`, `prompt` | 读取图片并返回文字描述 |

## 安装

### 前置条件

1. LM Studio 已安装，已加载一个视觉模型（minicpm-v / qwen-vl / llava 等）
2. LM Studio 的 API 服务已开启（Settings → Local Inference Server → 启用，端口 1234）
3. Python 3.8+（mcp-server.py 只用标准库，无需 pip install）

### Reasonix 配置

```toml
# config.toml
[[plugins]]
name    = "vision"
command = "python"
args    = ["D:\\path\\to\\lm-studio-vision-bridge\\mcp-server.py"]
```

### 其他 MCP 兼容 agent

当前目录下的 `mcp-server.py` 是一个标准 MCP 服务器，可直接接入：

- **Claude Code** → 写入 `~/.claude/.mcp.json`
- **OpenCode** → 写入 `opencode.jsonc`
- **Cursor / Windsurf** → MCP 设置中添加
- **VS Code (Copilot Agent)** → 写入 `mcp.json`
- **Continue.dev** → 写入 `~/.continue/config.json`

详情见 README.md 中对应章节。

## 自动探测

LM Studio 的 IP 可能因 DHCP、WiFi 切换等原因变化。mcp-server.py 启动时自动扫描：

```
127.0.0.1:1234 → localhost:1234 → 每个网卡 IP:1234
```

找到即用，找不到返回明确错误。也可独立运行探测脚本：

```powershell
.\scripts\find-lm-studio.ps1
# → Found: http://192.168.1.5:1234
```

## 环境变量

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `VISION_MODEL` | 自动选择第一个模型 | 指定模型名 |
| `LM_STUDIO_PORT` | `1234` | LM Studio API 端口 |

## 错误处理

| 症状 | 原因 | 处理 |
|------|------|------|
| "LM Studio not found" | 未运行或地址变了 | 检查 LM Studio API 是否启用 |
| "File not found" | 图片路径不对 | 用绝对路径 |
| 空响应 | 模型不支持该格式 | 转 PNG/JPG |
| 连续失败 2-3 次 | 地址可能变了 | 自动重试 + 重新探测 |

## 与其他方案对比

| | 本项目 | vision-tool | lmstudio-mcp |
|---|---|---|---|
| 纯本地 | ✅ | ❌ 需云端 API | ✅ |
| 零依赖 | ✅ | ❌ 需 pillow | ❌ 需 requests+mcp |
| 地址探测 | ✅ | ❌ | ❌ |
| Reasonix 支持 | ✅ | ❌ | ❌ |

## 设计哲学（Ponytail）

只做一件事——图片→文字。核心只有一个文件 `mcp-server.py`，纯标准库，零依赖。
不加缓存、队列、多模型路由——当视觉请求频繁到需要并发控制时再加，不是现在。

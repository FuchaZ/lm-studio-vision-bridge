---
name: lm-studio-vision-bridge
description: 通过本地 LM Studio 视觉模型为 Reasonix 及其他 AI agent 提供图片识别能力。零依赖、自动探测地址、纯本地运行。
license: MIT
---

# LM Studio Vision Bridge

给纯文本模型接上本地视觉能力。通过 LM Studio 跑视觉模型，走标准 MCP 协议给任何 AI agent 看图。

## 背景

纯文本模型（DeepSeek、Claude Sonnet 等）推理能力强但没视觉。有视觉的模型要么贵要么得上云。
这个东西让你用 LM Studio 在本地跑视觉模型，图片不离开你的电脑，agent 也能「看见」。

## 工具

只有一个入口：

`read_image_with_model(image_path, prompt)` — 给一张图，返回文字描述

## 安装

- LM Studio 跑着，加载了视觉模型，API 开着（端口 1234）
- Python 3.8+

### Reasonix 配置

```toml
[[plugins]]
name    = "vision"
command = "python"
args    = ["D:\\path\\to\\lm-studio-vision-bridge\\mcp-server.py"]
```

### 其他 agent

mcp-server.py 是标准 MCP 服务，Claude Code、OpenCode、Cursor、VS Code、Continue.dev 都能接。
具体配置见同目录下的 README.md。

## 地址自动探测

LM Studio 的 IP 可能会变。服务启动时会自动扫 `127.0.0.1:1234`、`localhost:1234`、各网卡 IP:1234，找到就用。

## 环境变量

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `VISION_MODEL` | 自动选第一个模型 | 指定模型名 |
| `LM_STUDIO_PORT` | `1234` | LM Studio API 端口 |

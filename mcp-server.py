#!/usr/bin/env python3
"""
MCP Server (stdio) — LM Studio Vision Bridge

标准 MCP 协议，通过 stdin/stdout 的 JSON-RPC 2.0 与 AI agent 通信。
核心逻辑由 _bridge.py 提供。

配置示例（Reasonix）：
    [[plugins]]
    name    = "vision"
    command = "python"
    args    = ["D:\\path\\to\\mcp-server.py"]
"""

import json
import re
import sys

from _bridge import (
    TOOL_DEFINITION,
    DEFAULT_PROMPT,
    call_tool,
    find_model,
    scan_lm_studio,
)

_lm_base = None
_model = None


# ── MCP stdio 传输 ────────────────────────────────────


def _read():
    """从 stdin 读取一条 MCP 消息（Content-Length 帧格式）。"""
    length = None
    while True:
        line = sys.stdin.buffer.readline()
        if not line:
            return None
        line = line.strip()
        if not line:
            break
        m = re.match(rb"Content-Length:\s*(\d+)", line, re.IGNORECASE)
        if m:
            length = int(m.group(1))
    if length is None:
        return None
    raw = sys.stdin.buffer.read(length)
    return json.loads(raw.decode("utf-8")) if len(raw) == length else None


def _send(msg):
    raw = json.dumps(msg, ensure_ascii=False).encode("utf-8")
    sys.stdout.buffer.write(f"Content-Length: {len(raw)}\r\n\r\n".encode() + raw)
    sys.stdout.buffer.flush()


# ── 请求处理 ──────────────────────────────────────────


def _handle_tool_call(params):
    global _lm_base, _model

    name = params.get("name")
    args = params.get("arguments", {})

    if name != "read_image_with_model":
        return {"error": {"code": -32601, "message": f"Unknown tool: {name}"}}

    # 初始化 LM Studio 连接
    if not _lm_base:
        _lm_base = scan_lm_studio()
    if not _lm_base:
        return {
            "isError": True,
            "content": [
                {
                    "type": "text",
                    "text": (
                        "LM Studio not found. "
                        "Please ensure LM Studio is running with API server enabled "
                        "(Settings → Local Inference Server)."
                    ),
                }
            ],
        }

    if not _model:
        _model = find_model(_lm_base)
    if not _model:
        return {
            "isError": True,
            "content": [
                {"type": "text", "text": "No vision model loaded in LM Studio."}
            ],
        }

    image_path = args.get("image_path", "")
    prompt = args.get("prompt", DEFAULT_PROMPT)

    if not image_path:
        return {
            "isError": True,
            "content": [{"type": "text", "text": "Missing required argument: image_path"}],
        }

    return call_tool(_lm_base, _model, image_path, prompt)


# ── 主循环 ────────────────────────────────────────────


def main():
    # Windows GBK 修复
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8")

    # Dispatch 表
    handlers = {
        "initialize": lambda id, p: _send(
            {
                "jsonrpc": "2.0",
                "id": id,
                "result": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {"tools": {}},
                    "serverInfo": {
                        "name": "lm-studio-vision-bridge",
                        "version": "2.0.0",
                    },
                },
            }
        ),
        "tools/list": lambda id, p: _send(
            {
                "jsonrpc": "2.0",
                "id": id,
                "result": {"tools": [TOOL_DEFINITION]},
            }
        ),
        "tools/call": lambda id, p: _send(
            {"jsonrpc": "2.0", "id": id, "result": _handle_tool_call(p)}
        ),
        "ping": lambda id, p: _send(
            {"jsonrpc": "2.0", "id": id, "result": {}}
        ),
    }

    while True:
        msg = _read()
        if msg is None:
            break
        method = msg.get("method", "")
        mid = msg.get("id")
        if method == "notifications/initialized":
            continue
        handler = handlers.get(method)
        if handler:
            handler(mid, msg.get("params", {}))
        else:
            _send(
                {
                    "jsonrpc": "2.0",
                    "id": mid,
                    "error": {
                        "code": -32601,
                        "message": f"Unknown method: {method}",
                    },
                }
            )


if __name__ == "__main__":
    main()

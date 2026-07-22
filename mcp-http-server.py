#!/usr/bin/env python3
"""
MCP HTTP Server — LM Studio Vision Bridge

通过 HTTP 传输的 MCP 服务器，绕过 Windows stdio 管道问题。
核心逻辑由 _bridge.py 提供。

启动：
    python mcp-http-server.py

然后在 MCP 客户端中配置为 HTTP 模式，连接 http://127.0.0.1:3456
"""

import json
import os
import sys
from http.server import HTTPServer, BaseHTTPRequestHandler
from threading import Thread

from _bridge import (
    TOOL_DEFINITION,
    DEFAULT_PROMPT,
    call_tool,
    find_model,
    scan_lm_studio,
)

MCP_PORT = int(os.environ.get("MCP_PORT", "3456"))

_lm_base = None
_model = None


class MCPHandler(BaseHTTPRequestHandler):
    """处理 MCP 协议的 HTTP POST 请求。"""

    # 禁用父类的日志（我们自己处理）
    def log_message(self, format, *args):
        pass

    def _send_json(self, code, data):
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(data, ensure_ascii=False).encode("utf-8"))

    def do_GET(self):
        self._send_json(200, {
            "jsonrpc": "2.0",
            "result": {
                "serverInfo": {"name": "lm-studio-vision-bridge-http", "version": "2.0.0"},
                "instructions": "Send POST with JSON-RPC 2.0 payload.",
            },
        })

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length)

        try:
            msg = json.loads(body.decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError) as e:
            self._send_json(400, {
                "jsonrpc": "2.0",
                "error": {"code": -32700, "message": f"Parse error: {e}"},
            })
            return

        method = msg.get("method", "")
        mid = msg.get("id")
        params = msg.get("params", {})

        # Notification — no response
        if method == "notifications/initialized":
            self._send_json(200, {"jsonrpc": "2.0"})
            return

        result = self._dispatch(method, mid, params)
        self._send_json(200, result)

    def _dispatch(self, method, mid, params):
        if method == "ping":
            return {"jsonrpc": "2.0", "id": mid, "result": {}}

        if method == "initialize":
            return {
                "jsonrpc": "2.0",
                "id": mid,
                "result": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {"tools": {}},
                    "serverInfo": {
                        "name": "lm-studio-vision-bridge-http",
                        "version": "2.0.0",
                    },
                },
            }

        if method == "tools/list":
            return {
                "jsonrpc": "2.0",
                "id": mid,
                "result": {"tools": [TOOL_DEFINITION]},
            }

        if method == "tools/call":
            result = self._handle_call(params)
            return {"jsonrpc": "2.0", "id": mid, "result": result}

        return {
            "jsonrpc": "2.0",
            "id": mid,
            "error": {"code": -32601, "message": f"Unknown method: {method}"},
        }

    def _handle_call(self, params):
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
                "content": [
                    {"type": "text", "text": "Missing required argument: image_path"}
                ],
            }

        return call_tool(_lm_base, _model, image_path, prompt)


def main():
    # Windows GBK 修复
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8")

    # 启动时预探测 LM Studio
    global _lm_base, _model
    print("[INFO] 正在探测 LM Studio...", file=sys.stderr)
    _lm_base = scan_lm_studio()
    if _lm_base:
        _model = find_model(_lm_base)
        print(f"[INFO] 已连接: {_lm_base}  模型: {_model}", file=sys.stderr)
    else:
        print("[WARN] 未找到 LM Studio，将在首次请求时重试", file=sys.stderr)

    server = HTTPServer(("127.0.0.1", MCP_PORT), MCPHandler)
    print(f"[INFO] MCP HTTP Server 启动: http://127.0.0.1:{MCP_PORT}", file=sys.stderr)
    print("[INFO] 在 MCP 客户端中配置为 HTTP 模式连接此地址", file=sys.stderr)
    sys.stderr.flush()

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n[INFO] 关闭服务器", file=sys.stderr)
        server.server_close()


if __name__ == "__main__":
    main()

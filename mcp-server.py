#!/usr/bin/env python3
"""MCP server: LM Studio Vision Bridge.

A lightweight MCP (Model Context Protocol) server that bridges Reasonix
to locally-hosted LM Studio vision models.

Protocol: JSON-RPC 2.0 over stdio (Content-Length framing).
Tool: read_image_with_model(image_path, prompt) → text description.
"""

import base64
import json
import os
import re
import socket
import struct
import subprocess
import sys
import time
import urllib.error
import urllib.request

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

LM_STUDIO_DEFAULT_PORT = 1234
REQUEST_TIMEOUT = 60  # seconds; vision models can be slow
MAX_RETRIES = 2

# ---------------------------------------------------------------------------
# LM Studio auto-detection
# ---------------------------------------------------------------------------


def _get_local_ips():
    """Return all non-loopback IPv4 addresses for this machine."""
    ips = set()
    try:
        hostname = socket.gethostname()
        for addr in socket.getaddrinfo(hostname, None):
            ip = addr[4][0]
            if not ip.startswith("127.") and "." in ip:
                ips.add(ip)
    except Exception:
        pass
    return sorted(ips)


def find_lm_studio(port=LM_STUDIO_DEFAULT_PORT, timeout=2):
    """Probe common addresses for an LM Studio API server.

    Returns the base URL (e.g. 'http://192.168.1.5:1234') or None.
    """
    candidates = ["http://127.0.0.1", "http://localhost"]
    candidates += [f"http://{ip}" for ip in _get_local_ips()]

    # Deduplicate while preserving order
    seen = set()
    unique = []
    for c in candidates:
        if c not in seen:
            seen.add(c)
            unique.append(c)

    for base in unique:
        url = f"{base}:{port}/v1/models"
        try:
            req = urllib.request.Request(url)
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                if resp.status == 200:
                    return f"{base}:{port}"
        except Exception:
            continue
    return None


# ---------------------------------------------------------------------------
# LM Studio API call
# ---------------------------------------------------------------------------


def _lm_studio_chat_completion(base_url, model, image_path, prompt):
    """Send an image + prompt to LM Studio and return the text response."""
    with open(image_path, "rb") as f:
        b64 = base64.b64encode(f.read()).decode()

    payload = json.dumps({
        "model": model,
        "max_tokens": 4096,
        "temperature": 0.01,
        "messages": [{
            "role": "user",
            "content": [
                {
                    "type": "image_url",
                    "image_url": {"url": f"data:image/png;base64,{b64}"},
                },
                {"type": "text", "text": prompt},
            ],
        }],
    }).encode()

    url = f"{base_url}/v1/chat/completions"
    req = urllib.request.Request(
        url,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT) as resp:
            body = json.loads(resp.read())
    except urllib.error.HTTPError as e:
        return {"error": f"LM Studio returned HTTP {e.code}: {e.read().decode(errors='replace')}"}
    except urllib.error.URLError as e:
        return {"error": f"Cannot reach LM Studio at {base_url}: {e.reason}"}
    except json.JSONDecodeError as e:
        return {"error": f"LM Studio returned invalid JSON: {e}"}

    content = ""
    try:
        content = body["choices"][0]["message"]["content"]
    except (KeyError, IndexError):
        content = json.dumps(body, ensure_ascii=False)

    return {"description": content.strip() or "(empty response)"}


# ---------------------------------------------------------------------------
# MCP protocol over stdio
# ---------------------------------------------------------------------------

# We use the standard MCP stdio transport:
#   Content-Length: <N>\r\n\r\n<JSON payload of N bytes>
#
# JSON-RPC 2.0 methods we handle:
#   initialize                  → capabilities
#   notifications/initialized   → no-op (notification, no response)
#   tools/list                  → tool definitions
#   tools/call                  → execute a tool


def _read_stdio_message():
    """Read one MCP message from stdin using Content-Length framing."""
    # Read headers
    length = None
    while True:
        line = sys.stdin.buffer.readline()
        if not line:
            return None  # EOF
        line = line.strip()
        if not line:
            break  # end of headers
        m = re.match(rb"Content-Length:\s*(\d+)", line, re.IGNORECASE)
        if m:
            length = int(m.group(1))

    if length is None:
        return None

    raw = sys.stdin.buffer.read(length)
    if len(raw) != length:
        return None

    return json.loads(raw.decode("utf-8"))


def _send_stdio_message(msg):
    """Send one MCP message to stdout using Content-Length framing."""
    data = json.dumps(msg, ensure_ascii=False)
    raw = data.encode("utf-8")
    header = f"Content-Length: {len(raw)}\r\n\r\n".encode()
    sys.stdout.buffer.write(header + raw)
    sys.stdout.buffer.flush()


# ---------------------------------------------------------------------------
# Tool implementation
# ---------------------------------------------------------------------------


def _handle_tools_list():
    return {
        "tools": [
            {
                "name": "read_image_with_model",
                "description": "Read an image file using a local LM Studio vision model and return a text description",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "image_path": {
                            "type": "string",
                            "description": "Absolute or relative path to the image file",
                        },
                        "prompt": {
                            "type": "string",
                            "description": "Instruction for the vision model describing what to extract from the image",
                        },
                    },
                    "required": ["image_path", "prompt"],
                },
            }
        ]
    }


def _handle_tool_call(params):
    tool_name = params.get("name")
    args = params.get("arguments", {})

    if tool_name != "read_image_with_model":
        return {"error": {"code": -32601, "message": f"Unknown tool: {tool_name}"}}

    image_path = args.get("image_path", "")
    prompt = args.get("prompt", "Describe this image in detail.")

    if not image_path:
        return {"error": {"code": -32000, "message": "Missing required argument: image_path"}}

    # Resolve relative paths
    if not os.path.isabs(image_path):
        # Try relative to cwd
        cand = os.path.join(os.getcwd(), image_path)
        if os.path.exists(cand):
            image_path = cand

    if not os.path.exists(image_path):
        return {
            "isError": True,
            "content": [{"type": "text", "text": f"File not found: {image_path}"}],
        }

    # Detect LM Studio
    lm_base = find_lm_studio()
    if not lm_base:
        return {
            "isError": True,
            "content": [
                {
                    "type": "text",
                    "text": (
                        "LM Studio not found. "
                        "Please ensure LM Studio is running with API server enabled "
                        "(Settings → Local Inference Server → Start)."
                    ),
                }
            ],
        }

    # Determine model - try environment variable first, then query LM Studio
    model = os.environ.get("VISION_MODEL", "")
    if not model:
        try:
            req = urllib.request.Request(f"{lm_base}/v1/models")
            with urllib.request.urlopen(req, timeout=5) as resp:
                models = json.loads(resp.read()).get("data", [])
            if models:
                model = models[0]["id"]
        except Exception:
            pass

    if not model:
        return {
            "isError": True,
            "content": [{"type": "text", "text": "No vision model found in LM Studio. Load a vision model first."}],
        }

    # Call LM Studio (with retries)
    last_error = None
    for attempt in range(1 + MAX_RETRIES):
        result = _lm_studio_chat_completion(lm_base, model, image_path, prompt)
        if "error" not in result:
            return {
                "content": [{"type": "text", "text": result["description"]}],
            }
        last_error = result["error"]
        if attempt < MAX_RETRIES:
            time.sleep(1)

    return {
        "isError": True,
        "content": [{"type": "text", "text": f"Vision model call failed after retries: {last_error}"}],
    }


# ---------------------------------------------------------------------------
# Main loop
# ---------------------------------------------------------------------------


def main():
    # Write startup info to stderr (MCP uses stdout for protocol)
    sys.stderr.write(
        "LM Studio Vision Bridge MCP server started.\n"
        f"Python {sys.version}\n"
    )
    sys.stderr.flush()

    while True:
        msg = _read_stdio_message()
        if msg is None:
            break  # EOF

        method = msg.get("method", "")
        msg_id = msg.get("id")
        params = msg.get("params", {})

        # Notifications have no id
        if method == "notifications/initialized":
            continue

        if method == "initialize":
            _send_stdio_message({
                "jsonrpc": "2.0",
                "id": msg_id,
                "result": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {
                        "tools": {},
                    },
                    "serverInfo": {
                        "name": "lm-studio-vision-bridge",
                        "version": "1.0.0",
                    },
                },
            })
        elif method == "tools/list":
            _send_stdio_message({
                "jsonrpc": "2.0",
                "id": msg_id,
                "result": _handle_tools_list(),
            })
        elif method == "tools/call":
            result = _handle_tool_call(params)
            _send_stdio_message({
                "jsonrpc": "2.0",
                "id": msg_id,
                "result": result,
            })
        elif method == "ping":
            _send_stdio_message({
                "jsonrpc": "2.0",
                "id": msg_id,
                "result": {},
            })
        else:
            _send_stdio_message({
                "jsonrpc": "2.0",
                "id": msg_id,
                "error": {"code": -32601, "message": f"Method not found: {method}"},
            })


if __name__ == "__main__":
    main()

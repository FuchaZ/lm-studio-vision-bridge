"""
_bridge.py — LM Studio Vision Bridge 共享核心逻辑

被 mcp-server.py（stdio）和 mcp-http-server.py（HTTP）共用。
零外部依赖，仅 Python 标准库。
"""

import base64
import json
import mimetypes
import os
import socket
import time
import urllib.error
import urllib.request

LM_STUDIO_PORT = int(os.environ.get("LM_STUDIO_PORT", "1234"))
MAX_TOKENS = int(os.environ.get("MAX_TOKENS", "8192"))
TIMEOUT = int(os.environ.get("REQUEST_TIMEOUT", "120"))

DEFAULT_PROMPT = (
    "请详细描述这张图片的内容，包括所有文字、图表、界面元素等。用中文回答。"
)

TOOL_DEFINITION = {
    "name": "read_image_with_model",
    "description": "Read an image file using a local LM Studio vision model and return a text description",
    "inputSchema": {
        "type": "object",
        "properties": {
            "image_path": {
                "type": "string",
                "description": "Path to the image file (absolute path recommended)",
            },
            "prompt": {
                "type": "string",
                "description": "Instruction for the vision model, e.g. 'Describe this image in detail'",
            },
        },
        "required": ["image_path", "prompt"],
    },
}


# ── LM Studio 地址探测 ────────────────────────────────


def scan_lm_studio() -> str | None:
    """扫描本地网络，找到 LM Studio API 地址。返回 base URL 或 None。"""
    env_url = os.environ.get("MODEL_BASE_URL", "").strip()
    if env_url:
        test_url = f"{env_url.rstrip('/')}/v1/models"
        try:
            req = urllib.request.Request(test_url)
            with urllib.request.urlopen(req, timeout=2) as r:
                if r.status == 200:
                    return env_url.rstrip("/")
        except Exception:
            pass

    seen = set()
    for raw in ["http://127.0.0.1", "http://localhost"]:
        seen.add(raw)
    try:
        hostname, _, ips = socket.gethostbyname_ex(socket.gethostname())
        for ip in ips:
            if not ip.startswith("127.") and "." in ip:
                seen.add(f"http://{ip}")
    except Exception:
        pass

    for base in seen:
        url = f"{base}:{LM_STUDIO_PORT}/v1/models"
        try:
            req = urllib.request.Request(url)
            with urllib.request.urlopen(req, timeout=2) as r:
                if r.status == 200:
                    return f"{base}:{LM_STUDIO_PORT}"
        except Exception:
            continue
    return None


# ── 模型查询 ──────────────────────────────────────────


def find_model() -> str | None:
    """只读环境变量 VISION_MODEL，返回模型名或 None。不自动查 LM Studio 列表。"""
    model = os.environ.get("VISION_MODEL", "").strip()
    return model if model else None


# ── LM Studio API 调用 ────────────────────────────────


def describe_image(
    base_url: str, model: str | None, image_path: str, prompt: str
) -> dict | str:
    """发送图片+提示词到 LM Studio。

    model 为 None 或空时不传 model 字段，LM Studio 会用当前加载的模型。
    成功返回 {"text": str, "reasoning": str|None}
    失败返回错误字符串（以 "LM Studio" 或 "Cannot" 或 "Invalid" 开头）。
    """
    with open(image_path, "rb") as f:
        b64 = base64.b64encode(f.read()).decode()
    mime_type, _ = mimetypes.guess_type(image_path)
    if not mime_type:
        mime_type = "image/png"  # fallback

    body = {
        "max_tokens": MAX_TOKENS,
        "temperature": 0.01,
        "messages": [
            {
                "role": "user",
                "content": [
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:{mime_type};base64,{b64}"},
                    },
                    {"type": "text", "text": prompt},
                ],
            }
        ],
    }
    # 只在明确指定了模型时才传 model 字段
    if model:
        body["model"] = model

    payload = json.dumps(body).encode()

    req = urllib.request.Request(
        f"{base_url}/v1/chat/completions",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        body = json.loads(urllib.request.urlopen(req, timeout=TIMEOUT).read())
    except urllib.error.HTTPError as e:
        return f"LM Studio HTTP {e.code}: {e.read().decode(errors='replace')}"
    except urllib.error.URLError as e:
        return f"Cannot reach LM Studio: {e.reason}"
    except json.JSONDecodeError as e:
        return f"Invalid LM Studio response: {e}"

    try:
        msg = body["choices"][0]["message"]
        text = (msg.get("content") or "").strip() or "(empty)"
        reasoning = (msg.get("reasoning_content") or "").strip() or None
        return {"text": text, "reasoning": reasoning}
    except (KeyError, IndexError):
        return {"text": json.dumps(body, ensure_ascii=False), "reasoning": None}


# ── 工具调用逻辑（被两个 server 共享）────────────────


def call_tool(lm_base: str, model: str | None, image_path: str, prompt: str) -> dict:
    """执行 read_image_with_model 调用，返回 MCP 兼容的 result dict。"""
    # 确认文件存在
    if not os.path.isabs(image_path):
        alt = os.path.join(os.getcwd(), image_path)
        if os.path.exists(alt):
            image_path = alt
    if not os.path.exists(image_path):
        return {
            "isError": True,
            "content": [{"type": "text", "text": f"File not found: {image_path}"}],
        }

    # 调 LM Studio（重试 3 次）
    result = None
    for i in range(3):
        result = describe_image(lm_base, model, image_path, prompt)
        if isinstance(result, dict):
            break
        if i < 2:
            time.sleep(1)

    if not isinstance(result, dict):
        return {
            "isError": True,
            "content": [{"type": "text", "text": str(result or "Unknown error")}],
        }

    content_parts = []
    if result.get("reasoning"):
        content_parts.append(
            {"type": "text", "text": f"--- 推理过程 ---\n{result['reasoning']}"}
        )
    content_parts.append({"type": "text", "text": result["text"]})
    return {"content": content_parts}

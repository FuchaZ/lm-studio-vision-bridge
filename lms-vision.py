#!/usr/bin/env python3
"""
LM Studio Vision Bridge — CLI 快捷调用脚本
用法: python lms-vision.py <图片路径> [提示词]

零依赖（仅 Python 标准库），自动探测 LM Studio 地址和模型。
"""

import base64
import json
import os
import re
import socket
import sys
import urllib.error
import urllib.request

DEFAULT_PORT = int(os.environ.get("LM_STUDIO_PORT", "1234"))
REQUEST_TIMEOUT = int(os.environ.get("REQUEST_TIMEOUT", "120"))
MAX_TOKENS = int(os.environ.get("MAX_TOKENS", "4096"))
MODEL = os.environ.get("VISION_MODEL", "")  # 可选，不设则自动探测

DEFAULT_PROMPT = (
    "请详细描述这张图片的内容，包括所有文字、图表、界面元素等。用中文回答。"
)


# ── LM Studio 地址自动探测 ─────────────────────────────


def _scan_lm_studio():
    """探测 LM Studio API 地址，返回 base URL 或 None。"""
    seen = set()

    # 优先使用环境变量
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

    # 本地回环地址
    for raw in ["http://127.0.0.1", "http://localhost"]:
        seen.add(raw)

    # 本机所有非回环 IPv4 地址
    try:
        hostname, _, ips = socket.gethostbyname_ex(socket.gethostname())
        for ip in ips:
            if not ip.startswith("127.") and "." in ip:
                seen.add(f"http://{ip}")
    except Exception:
        pass

    for base in seen:
        url = f"{base}:{DEFAULT_PORT}/v1/models"
        try:
            req = urllib.request.Request(url)
            with urllib.request.urlopen(req, timeout=2) as r:
                if r.status == 200:
                    return f"{base}:{DEFAULT_PORT}"
        except Exception:
            continue
    return None


# ── LM Studio API 调用 ─────────────────────────────────


def encode_image(path: str) -> str:
    with open(path, "rb") as f:
        return base64.b64encode(f.read()).decode()


def ask_lms(base_url: str, model: str, image_b64: str, prompt: str):
    """发送图片到 LM Studio 完成请求，返回 {content, reasoning, usage} 或 None。"""
    payload = {
        "model": model,
        "max_tokens": MAX_TOKENS,
        "temperature": 0.01,
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:image/png;base64,{image_b64}"},
                    },
                ],
            }
        ],
    }

    req = urllib.request.Request(
        f"{base_url}/v1/chat/completions",
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
    )

    try:
        with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT) as resp:
            result = json.loads(resp.read())
            content = result["choices"][0]["message"]["content"]
            reasoning = result["choices"][0]["message"].get("reasoning_content", "")
            usage = result.get("usage", {})
            return {
                "content": content.strip(),
                "reasoning": reasoning.strip() if reasoning else None,
                "usage": usage,
            }
    except urllib.error.HTTPError as e:
        print(f"[ERROR] HTTP {e.code}: {e.read().decode()}", file=sys.stderr)
        return None
    except urllib.error.URLError as e:
        print(f"[ERROR] 连接失败: {e.reason}", file=sys.stderr)
        return None
    except Exception as e:
        print(f"[ERROR] {e}", file=sys.stderr)
        return None


def _find_model(base_url: str) -> str | None:
    """从 LM Studio 查询第一个可用模型。"""
    try:
        req = urllib.request.Request(f"{base_url}/v1/models")
        data = json.loads(
            urllib.request.urlopen(req, timeout=5).read()
        ).get("data", [])
        if data:
            return data[0]["id"]
    except Exception:
        pass
    return None


# ── 主入口 ──────────────────────────────────────────────


def main():
    # Windows GBK 编码修复
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")

    if len(sys.argv) < 2:
        print("用法: python lms-vision.py <图片路径> [提示词]", file=sys.stderr)
        sys.exit(1)

    img_path = sys.argv[1]
    prompt = sys.argv[2] if len(sys.argv) > 2 else DEFAULT_PROMPT

    if not os.path.isfile(img_path):
        print(f"[ERROR] 文件不存在: {img_path}", file=sys.stderr)
        sys.exit(1)

    # 1. 探测 LM Studio
    base_url = _scan_lm_studio()
    if not base_url:
        print(
            "[ERROR] 找不到 LM Studio。请确保 LM Studio 正在运行，"
            "且已启用 API 服务（Settings → Local Inference Server → 端口 1234）。",
            file=sys.stderr,
        )
        sys.exit(1)

    # 2. 确定模型名
    model = MODEL or _find_model(base_url)
    if not model:
        print(
            "[ERROR] 无法确定视觉模型。请在 LM Studio 中加载一个视觉模型，"
            "或设置环境变量 VISION_MODEL。",
            file=sys.stderr,
        )
        sys.exit(1)

    print(f"[INFO] 已连接到 {base_url}，模型: {model}", file=sys.stderr)

    # 3. 编码图片
    try:
        b64 = encode_image(img_path)
    except Exception as e:
        print(f"[ERROR] 读取图片失败: {e}", file=sys.stderr)
        sys.exit(1)

    print(f"[INFO] 图片已读取 ({len(b64)} bytes)，发送请求...", file=sys.stderr)

    # 4. 发送请求（失败重试一次）
    result = ask_lms(base_url, model, b64, prompt)
    if result is None:
        print("[INFO] 重试中...", file=sys.stderr)
        result = ask_lms(base_url, model, b64, prompt)

    if result is None:
        print(
            "[ERROR] 连续两次请求失败，请检查 LM Studio 是否正常运行",
            file=sys.stderr,
        )
        sys.exit(1)

    # 5. 输出结果
    if result["reasoning"]:
        print("--- 推理过程 ---")
        print(result["reasoning"])
        print("--- 最终回答 ---")
    print(result["content"])

    usage = result["usage"]
    if usage:
        print(
            f"[USAGE] prompt={usage.get('prompt_tokens','?')} "
            f"completion={usage.get('completion_tokens','?')} "
            f"total={usage.get('total_tokens','?')}",
            file=sys.stderr,
        )


if __name__ == "__main__":
    main()

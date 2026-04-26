import json
from typing import List, Dict, Optional
from urllib.parse import urlparse


def parse_append_args(raw: str):
    """
    解析 /append 命令参数
    支持:
    - markdown <content>
    - md <content>
    - html <content>
    - auto <content>
    - 直接内容（parse_mode=None，跟随规则）
    """
    text = (raw or "").strip()
    if not text:
        return None, ""

    lowered = text.lower()
    for prefix, mode in (("markdown ", "Markdown"), ("md ", "Markdown"), ("html ", "HTML"), ("auto ", None)):
        if lowered.startswith(prefix):
            return mode, text[len(prefix):].strip()

    return None, text


def parse_buttons_input(text: str) -> List[List[Dict[str, str]]]:
    """
    解析 /buttons 文本，返回二维按钮列表。

    语法：
    - 每行表示一行按钮
    - 同一行中用 && 分隔多个按钮
    - 每个按钮格式：按钮文本 - https://example.com

    例子：
    官方网站 - https://example.com && 立即加入 - https://t.me/abc
    文档 - https://docs.example.com
    """
    rows: List[List[Dict[str, str]]] = []
    if not text or not text.strip():
        return rows

    for raw_line in text.strip().splitlines():
        line = raw_line.strip()
        if not line:
            continue

        row: List[Dict[str, str]] = []
        for part in line.split("&&"):
            item = part.strip()
            if not item:
                continue

            if " - " not in item:
                raise ValueError(f"按钮格式错误: {item}（应为 '文本 - 链接'）")

            btn_text, url = item.split(" - ", 1)
            btn_text = btn_text.strip()
            url = url.strip()

            if not btn_text:
                raise ValueError("按钮文本不能为空")
            if not _is_valid_url(url):
                raise ValueError(f"无效链接: {url}")

            row.append({"text": btn_text, "url": url})

        if row:
            rows.append(row)

    return rows


def serialize_button_rows(rows: List[List[Dict[str, str]]]) -> str:
    return json.dumps(rows, ensure_ascii=False)


def deserialize_button_rows(raw: Optional[str]) -> List[List[Dict[str, str]]]:
    if not raw:
        return []
    try:
        data = json.loads(raw)
        if isinstance(data, list):
            return data
    except Exception:
        pass
    return []


def _is_valid_url(url: str) -> bool:
    parsed = urlparse(url)
    return parsed.scheme in {"http", "https", "tg"} and bool(parsed.netloc or parsed.path)

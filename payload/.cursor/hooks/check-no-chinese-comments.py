#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Detect Simplified-Chinese comments in agent source edits.

Japanese Kanji shares the CJK Unicode block, so we do NOT flag all Han
characters. We look for Simplified-Chinese comment markers that almost never
appear in this project's Japanese/English comments.

afterFileEdit: scan edits, stash warning if needed, try additional_context.
postToolUse: drain stashed warning into additional_context (reliable delivery).
"""

from __future__ import print_function

import json
import os
import re
import sys
import tempfile

SOURCE_EXT = (".java", ".vue", ".ts", ".tsx", ".js", ".jsx")

# Phrases / particles typical of Simplified Chinese AI comments.
# Avoid JP lookalikes that are also Japanese (e.g. 更新, 判断, 成功).
ZH_MARKERS = re.compile(
    r"(字符串|避免|混淆|未选择|数值|进行|实现|处理|添加|删除|修改|"
    r"检查|是否|需要|可以|应该|不要|不能|没有|已经|如果|但是|因为|所以|"
    r"使用|获取|返回|设置|创建|查询|临时|当前|默认|后端|前端|表单|"
    r"按钮|弹窗|对话框|接口|列表|文件|数据|根据|通过|对应|相关|"
    r"的|了|吗|吧|呢|这|那|什么|怎么|咱们|您们|将数值|与未)"
)

LINE_COMMENT = re.compile(r"(^|[^:])//(.*)$")
BLOCK_COMMENT_START = re.compile(r"/\*")
BLOCK_COMMENT_END = re.compile(r"\*/")
HTML_COMMENT = re.compile(r"<!--([\s\S]*?)-->")


def pending_path(conversation_id):
    base = os.path.join(tempfile.gettempdir(), "{{name}}-cursor-hooks")
    try:
        os.makedirs(base, exist_ok=True)
    except OSError:
        pass
    safe = re.sub(r"[^A-Za-z0-9._-]", "_", conversation_id or "unknown")
    return os.path.join(base, "zh-comment-%s.txt" % safe)


def is_source_path(path):
    if not path:
        return False
    lower = path.replace("\\", "/").lower()
    if "/locale/" in lower or "/i18n/" in lower:
        return False
    if "/docs/" in lower or lower.endswith(".md"):
        return False
    return lower.endswith(SOURCE_EXT)


def extract_comment_snippets(text):
    """Yield comment text snippets from source (best-effort, line oriented)."""
    if not text:
        return

    for m in HTML_COMMENT.finditer(text):
        yield m.group(1)

    in_block = False
    for line in text.splitlines():
        if in_block:
            end = BLOCK_COMMENT_END.search(line)
            if end:
                yield line[: end.start()]
                in_block = False
                line = line[end.end() :]
            else:
                yield line
                continue

        start = BLOCK_COMMENT_START.search(line)
        if start and "*/" not in line[start.end() :]:
            yield line[start.end() :]
            in_block = True
            continue
        if start and "*/" in line[start.end() :]:
            end = line.find("*/", start.end())
            yield line[start.end() : end]
            line = line[end + 2 :]

        m = LINE_COMMENT.search(line)
        if m:
            yield m.group(2)


def find_zh_in_text(text):
    hits = []
    for snippet in extract_comment_snippets(text):
        if not snippet or not ZH_MARKERS.search(snippet):
            continue
        cleaned = " ".join(snippet.strip().split())
        if cleaned and cleaned not in hits:
            hits.append(cleaned[:160])
    return hits


def stash_warning(conversation_id, message):
    path = pending_path(conversation_id)
    try:
        with open(path, "w", encoding="utf-8") as f:
            f.write(message)
    except OSError as e:
        print("stash failed: %s" % e, file=sys.stderr)


def drain_warning(conversation_id):
    path = pending_path(conversation_id)
    if not os.path.isfile(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            msg = f.read().strip()
        os.remove(path)
        return msg or None
    except OSError:
        return None


def handle_after_file_edit(payload):
    file_path = payload.get("file_path") or ""
    if not is_source_path(file_path):
        return {}

    edits = payload.get("edits") or []
    all_hits = []
    for edit in edits:
        new_string = edit.get("new_string") or ""
        for h in find_zh_in_text(new_string):
            if h not in all_hits:
                all_hits.append(h)

    # Full-file fallback when edits omit context (Write whole file, etc.)
    if not all_hits and os.path.isfile(file_path):
        try:
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                all_hits = find_zh_in_text(f.read())
        except OSError:
            pass

    if not all_hits:
        return {}

    rel = file_path
    roots = payload.get("workspace_roots") or []
    for root in roots:
        if file_path.startswith(root.rstrip("/") + "/"):
            rel = file_path[len(root.rstrip("/")) + 1 :]
            break

    samples = "; ".join(all_hits[:5])
    message = (
        "BLOCKER: Simplified-Chinese comment detected in source (comments must be "
        "Japanese or English per project-core / AGENTS.md). Fix immediately: rewrite "
        "those comments to Japanese (preferred) or English.\n"
        "file: %s\n"
        "samples: %s" % (rel, samples)
    )
    print(message, file=sys.stderr)

    cid = (
        payload.get("conversation_id")
        or payload.get("session_id")
        or "unknown"
    )
    stash_warning(cid, message)

    # Prefer additional_context when Cursor consumes afterFileEdit output.
    return {"additional_context": message}


def handle_post_tool_use(payload):
    cid = (
        payload.get("conversation_id")
        or payload.get("session_id")
        or "unknown"
    )
    msg = drain_warning(cid)
    if not msg:
        return {}
    return {"additional_context": msg}


def main():
    try:
        raw = sys.stdin.read()
        payload = json.loads(raw) if raw.strip() else {}
    except Exception as e:
        print("invalid hook stdin: %s" % e, file=sys.stderr)
        print("{}")
        return 0

    event = (payload.get("hook_event_name") or "").strip()
    out = {}
    if event == "afterFileEdit" or (not event and "edits" in payload):
        out = handle_after_file_edit(payload)
    elif event == "postToolUse":
        out = handle_post_tool_use(payload)
    else:
        out = handle_post_tool_use(payload)

    sys.stdout.write(json.dumps(out, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())

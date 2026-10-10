#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""CI 校验：插件结构、JSON 合法性、SKILL.md frontmatter、Python 语法、密钥泄漏。

在本地和 GitHub Actions 里跑同一份，避免"本地过了 CI 挂"。
用法：python3 scripts/ci_check.py
"""
import json
import py_compile
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
errors: list[str] = []


def fail(msg: str) -> None:
    errors.append(msg)


# 1. 所有 JSON 必须能解析
for p in sorted(ROOT.rglob("*.json")):
    if ".git" in p.parts:
        continue
    try:
        json.loads(p.read_text(encoding="utf-8"))
    except Exception as e:
        fail(f"{p.relative_to(ROOT)}：JSON 解析失败 —— {e}")

# 2. plugin.json 必填字段 + 与 marketplace 里的条目名必须一致
plugin = ROOT / ".claude-plugin" / "plugin.json"
market = ROOT / ".claude-plugin" / "marketplace.json"
if not plugin.is_file():
    fail(".claude-plugin/plugin.json 缺失")
if not market.is_file():
    fail(".claude-plugin/marketplace.json 缺失")

if plugin.is_file() and market.is_file():
    pj = json.loads(plugin.read_text(encoding="utf-8"))
    mk = json.loads(market.read_text(encoding="utf-8"))
    for field in ("name", "version", "description"):
        if not pj.get(field):
            fail(f"plugin.json 缺 {field}")
    entries = mk.get("plugins") or []
    if not entries:
        fail("marketplace.json 的 plugins 为空")
    else:
        if entries[0].get("name") != pj.get("name"):
            fail(f"名字不一致：plugin.json={pj.get('name')!r} vs marketplace={entries[0].get('name')!r}"
                 "（官方要求两者相同）")
    if pj.get("homepage") and not str(pj["homepage"]).startswith("http"):
        fail("plugin.json 的 homepage 必须是 URL")

# 3. 每个 SKILL.md 必须有 frontmatter 的 name 与 description
for sk in sorted((ROOT / "skills").glob("*/SKILL.md")):
    text = sk.read_text(encoding="utf-8")
    rel = sk.relative_to(ROOT)
    if not text.startswith("---"):
        fail(f"{rel}：frontmatter 必须从第一行的 --- 开始")
        continue
    fm = text.split("---", 2)[1] if text.count("---") >= 2 else ""
    for field in ("name:", "description:"):
        if field not in fm:
            fail(f"{rel}：frontmatter 缺 {field}")

# 4. Python 必须能编译（用 compile()，不落盘——py_compile 会写 .pyc，
#    用 /dev/null 当 cfile 在 Windows 上还会造出一个 F:\dev 目录）
for p in sorted(ROOT.rglob("*.py")):
    if ".git" in p.parts:
        continue
    try:
        compile(p.read_text(encoding="utf-8"), str(p), "exec")
    except SyntaxError as e:
        fail(f"{p.relative_to(ROOT)}：语法错误 —— 第 {e.lineno} 行 {e.msg}")

# 5. 不许有密钥
PATTERNS = [
    (re.compile(r"sk-or-v1-[A-Za-z0-9]{16,}"), "OpenRouter key"),
    (re.compile(r"ghp_[A-Za-z0-9]{20,}"), "GitHub PAT"),
    (re.compile(r"sk-[A-Za-z0-9]{32,}"), "OpenAI-style key"),
    (re.compile(r"AKIA[0-9A-Z]{16}"), "AWS access key"),
    (re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"), "私钥"),
]
SKIP_SUFFIX = {".png", ".jpg", ".jpeg", ".gif", ".zip", ".mp3", ".mp4"}
for p in sorted(ROOT.rglob("*")):
    if not p.is_file() or ".git" in p.parts or p.suffix.lower() in SKIP_SUFFIX:
        continue
    if p.name == Path(__file__).name:
        continue
    try:
        text = p.read_text(encoding="utf-8")
    except (UnicodeDecodeError, OSError):
        continue
    for rx, label in PATTERNS:
        m = rx.search(text)
        if m:
            fail(f"{p.relative_to(ROOT)}：疑似泄漏 {label}（{m.group(0)[:12]}…）")


if errors:
    print("CI 校验未通过：\n")
    for e in errors:
        print("  ✗", e)
    sys.exit(1)

print("CI 校验通过：JSON / 插件结构 / frontmatter / Python 语法 / 密钥扫描 全部 OK")

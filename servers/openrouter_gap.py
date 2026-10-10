#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""OpenRouter gap-modality MCP server (zero-dependency, stdio JSON-RPC).

Scope: the two modalities that OpenRouter exposes but that mainstream OpenRouter MCP servers do
NOT cover — **embeddings** and **decisions**. It deliberately ships nothing else; chat, image,
video, speech, transcription and rerank are better served by
https://github.com/stabgan/openrouter-mcp-multimodal , and duplicating its tools here would only
make it unclear which one to call.

Tools:
    or_embed        POST /api/v1/embeddings
    or_decide       POST /api/alpha/decisions   (returns probabilities, not text)
    or_list_models  GET  /api/v1/models?output_modalities=<modality>

Gotchas baked in (all observed against the live API):
  * `decisions` lives under `/api/alpha/`, NOT `/api/v1/` — the OpenAPI `servers` block only
    declares `/api/v1`, and `/api/v1/alpha/decisions` 404s.
  * Listing models needs `?output_modalities=<modality>`; without it you get text models only.
    The official modality names are `transcription` (not speech-to-text) and `decisions`.
  * `usage.cost` in the response is the authoritative dollar cost.
  * stdout carries JSON-RPC only; all logging goes to stderr.

Credential: `OPENROUTER_API_KEY` (the plugin prompts for it), or a `OpenRouter=` line in
`~/.claude/token.txt`.
"""
import io
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

if hasattr(sys.stdout, "buffer"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", newline="\n")
if hasattr(sys.stderr, "buffer"):
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8")

API = "https://openrouter.ai/api/v1"
API_ROOT = "https://openrouter.ai/api"          # decisions lives here, not under /v1
TOKEN_FILE = Path.home() / ".claude" / "token.txt"
PROTOCOL = "2025-06-18"


def log(*a):
    print(*a, file=sys.stderr, flush=True)


def get_key():
    k = os.environ.get("OPENROUTER_API_KEY", "").strip()
    if k:
        return k
    if TOKEN_FILE.exists():
        for line in TOKEN_FILE.read_text(encoding="utf-8", errors="ignore").splitlines():
            if line.strip().startswith("OpenRouter="):
                return line.split("=", 1)[1].strip()
    raise RuntimeError("no OpenRouter key: set OPENROUTER_API_KEY, or add an 'OpenRouter=' line "
                       "to ~/.claude/token.txt")


def call(path, payload, timeout=120, base=API):
    req = urllib.request.Request(
        base + path, data=json.dumps(payload).encode(),
        headers={"Authorization": "Bearer " + get_key(), "Content-Type": "application/json"})
    try:
        return json.loads(urllib.request.urlopen(req, timeout=timeout).read())
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"HTTP {e.code}: {e.read().decode(errors='ignore')[:400]}")


def get(path, timeout=60):
    req = urllib.request.Request(API + path, headers={"Authorization": "Bearer " + get_key()})
    try:
        return json.loads(urllib.request.urlopen(req, timeout=timeout).read())
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"HTTP {e.code}: {e.read().decode(errors='ignore')[:400]}")


TOOLS = [
    {
        "name": "or_embed",
        "description": "Embed text (POST /api/v1/embeddings). Returns the count and dimension rather "
                       "than the full vectors. Default model openai/text-embedding-3-small; pass "
                       "`model` to override. Use for semantic search / RAG.",
        "inputSchema": {"type": "object", "properties": {
            "texts": {"type": "array", "items": {"type": "string"}},
            "model": {"type": "string"}}, "required": ["texts"]},
    },
    {
        "name": "or_decide",
        "description": "Ask a decision model for probabilities instead of text "
                       "(POST /api/alpha/decisions — an OpenRouter alpha modality, 19 models such as "
                       "typesafe/jev-1.13 and upstage/solar-decide-flash). `questions` maps a name to "
                       "{type, instructions, criteria}; type is one of: noul (yes/no, "
                       "criteria={true,false}), choice (pick one, criteria={option: hint}), "
                       "score (ordered rubric, criteria=[lowest..highest]). `state` is the material "
                       "being judged (string / object / array).",
        "inputSchema": {"type": "object", "properties": {
            "model": {"type": "string"},
            "questions": {"type": "object"},
            "state": {}}, "required": ["questions"]},
    },
    {
        "name": "or_list_models",
        "description": "List OpenRouter models by modality — mainly to find embeddings / decisions "
                       "candidates. modality: embeddings / decisions / text / image / video / speech "
                       "/ transcription / audio / rerank / all. "
                       "NOTE: the price this returns is unreliable (the API often omits a "
                       "modality's pricing), so never read 'free' off it.",
        "inputSchema": {"type": "object", "properties": {
            "modality": {"type": "string"},
            "limit": {"type": "integer"}}, "required": ["modality"]},
    },
]

DEFAULT_EMBED = "openai/text-embedding-3-small"
DEFAULT_DECIDE = "typesafe/jev-1.13"


def run_tool(name, a):
    if name == "or_embed":
        r = call("/embeddings", {"model": a.get("model") or DEFAULT_EMBED, "input": a["texts"]})
        data = r.get("data") or []
        dims = len(data[0]["embedding"]) if data else 0
        head = data[0]["embedding"][:8] if dims else []
        return f"OK {len(data)} vectors, dimension {dims}; first 8 of vector 0: {head}"

    if name == "or_decide":
        body = {"model": a.get("model") or DEFAULT_DECIDE, "questions": a["questions"]}
        if "state" in a:
            body["state"] = a["state"]
        r = call("/alpha/decisions", body, base=API_ROOT)
        cost = (r.get("usage") or {}).get("cost")
        return (f"cost_usd={cost}\n" if cost is not None else "") + \
            json.dumps(r.get("answers", r), ensure_ascii=False, indent=1)[:2000]

    if name == "or_list_models":
        d = get(f"/models?output_modalities={a.get('modality')}")
        rows = [m.get("id") for m in d.get("data", [])][: int(a.get("limit") or 60)]
        return f"{len(d.get('data', []))} models (showing {len(rows)}):\n" + "\n".join("   " + r for r in rows)

    raise RuntimeError(f"unknown tool {name}")


def main():
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
        except Exception:
            continue
        mid = msg.get("id")
        method = msg.get("method")
        params = msg.get("params") or {}

        if method == "initialize":
            resp = {"jsonrpc": "2.0", "id": mid, "result": {
                "protocolVersion": PROTOCOL,
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "openrouter-gap", "version": "0.1.0",
                               "title": "OpenRouter gap modalities (embeddings / decisions)"}}}
        elif method in ("notifications/initialized", "notifications/cancelled"):
            continue
        elif method == "tools/list":
            resp = {"jsonrpc": "2.0", "id": mid, "result": {"tools": TOOLS}}
        elif method == "tools/call":
            try:
                out = run_tool(params.get("name"), params.get("arguments") or {})
                resp = {"jsonrpc": "2.0", "id": mid,
                        "result": {"content": [{"type": "text", "text": str(out)}], "isError": False}}
            except Exception as e:
                resp = {"jsonrpc": "2.0", "id": mid,
                        "result": {"content": [{"type": "text", "text": f"ERROR {type(e).__name__}: {e}"}],
                                   "isError": True}}
        elif method == "ping":
            resp = {"jsonrpc": "2.0", "id": mid, "result": {}}
        else:
            if mid is None:
                continue
            resp = {"jsonrpc": "2.0", "id": mid,
                    "error": {"code": -32601, "message": f"Method not found: {method}"}}

        sys.stdout.write(json.dumps(resp, ensure_ascii=False) + "\n")
        sys.stdout.flush()


if __name__ == "__main__":
    main()

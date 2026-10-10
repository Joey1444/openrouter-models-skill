#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""List OpenRouter models by modality, with real prices and true-free detection.

Why this exists: OpenRouter's own model browser makes you hunt through the website, and the
`search_models` tool in most OpenRouter MCP servers can only filter on vision/audio/video — there is
no price or "free" filter anywhere.

Usage:
    python list_models.py                 # overview: model count and free count per modality
    python list_models.py image           # one modality, free first, with prices
    python list_models.py image --free    # only the truly free ones
    python list_models.py --json image    # machine-readable

"Truly free" is decided as follows (all three rules were derived from real API responses — do not
simplify them):
  * free only if EVERY pricing field is 0
  * reading only prompt/completion marks paid models as free; the real charge is usually in
    image_output / image_token
  * a non-text modality whose pricing contains only prompt/completion tells you nothing about that
    modality's price -> report "unknown", never "free"

The endpoint /api/v1/models is public: no API key required.
"""
import argparse
import io
import json
import sys
import urllib.request

if hasattr(sys.stdout, "buffer"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", newline="\n")

API = "https://openrouter.ai/api/v1/models"
MODALITIES = ["text", "image", "video", "speech", "transcription",
              "embeddings", "rerank", "decisions"]
GENERIC = {"prompt", "completion"}          # text-shaped fields; cannot price other modalities


def fetch_all():
    with urllib.request.urlopen(API + "?output_modalities=all", timeout=90) as r:
        return json.load(r)["data"]


def classify(pricing: dict, modality: str, model_id: str = ""):
    """Return (price, state) where state is free / paid / unknown.

    Order matters:
      1. an id ending in `:free` is an official free variant -> free
         (its pricing is {prompt:0, completion:0}, indistinguishable from an unpriced video model,
         so the suffix is the only reliable signal)
      2. every field 0 -> free, BUT for a non-text modality whose pricing holds only
         prompt/completion that means "price not exposed", not "free"
      3. a positive value -> paid (smallest positive wins); only negative values (e.g. -1 for
         unlimited) -> unknown
    """
    if model_id.endswith(":free"):
        return 0.0, "free"
    if not pricing:
        return None, "unknown"
    keys = set(pricing.keys())
    vals = []
    for v in pricing.values():
        try:
            vals.append(float(v))
        except (TypeError, ValueError):
            pass
    if not vals:
        return None, "unknown"
    if all(v == 0 for v in vals):
        if modality != "text" and keys <= GENERIC:
            return None, "unknown"
        return 0.0, "free"
    pos = [v for v in vals if v > 0]        # negative values usually mean "unlimited"
    if pos:
        return min(pos), "paid"
    return None, "unknown"


def group(models):
    out = {m: [] for m in MODALITIES}
    for mdl in models:
        arch = mdl.get("architecture") or {}
        outs = arch.get("output_modalities") or []
        for mod in outs:
            if mod in out and mod != "text":
                out[mod].append(mdl)
        # Match the numbers OpenRouter's own site reports for Text (every model emitting text).
        if "text" in outs:
            out["text"].append(mdl)
    return out


def rows_for(models, modality):
    rows = []
    for m in models:
        price, state = classify(m.get("pricing") or {}, modality, m["id"])
        rows.append({"id": m["id"], "state": state, "price": price,
                     "name": (m.get("name") or "")[:40]})
    order = {"free": 0, "paid": 1, "unknown": 2}
    rows.sort(key=lambda r: (order[r["state"]], r["price"] if r["price"] is not None else 9e9, r["id"]))
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("modality", nargs="?", choices=MODALITIES)
    ap.add_argument("--free", action="store_true")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()

    try:
        groups = group(fetch_all())
    except Exception as e:
        print(f"fetch failed: {type(e).__name__}: {e}")
        return 1

    if not a.modality:
        if a.json:
            print(json.dumps({k: {"total": len(v),
                                  "free": sum(1 for m in v if classify(m.get('pricing') or {}, k, m['id'])[1] == 'free')}
                              for k, v in groups.items()}, ensure_ascii=False))
            return 0
        print("OpenRouter models (free = truly free)\n")
        for mod in MODALITIES:
            r = rows_for(groups[mod], mod)
            nf = sum(1 for x in r if x["state"] == "free")
            print(f"  {mod:<14} {len(r):>3} models, {nf} free")
        print("\nDetails: /openrouter-models:models <modality> [--free]    e.g. image --free")
        return 0

    rows = rows_for(groups[a.modality], a.modality)
    if a.free:
        rows = [r for r in rows if r["state"] == "free"]
    if a.json:
        print(json.dumps(rows, ensure_ascii=False))
        return 0

    if not rows:
        print(f"{a.modality}: no matching models")
        return 0
    print(f"{a.modality}: {len(rows)} models" + (" (free only)" if a.free else "") + "\n")
    for r in rows[:60]:
        if r["state"] == "free":
            tag = "FREE"
        elif r["state"] == "unknown":
            tag = "? price n/a"
        else:
            tag = f"${r['price']:.6g}"
        print(f"  {tag:<12} {r['id']}")
    if len(rows) > 60:
        print(f"  ... {len(rows) - 60} more (use --json for the full list)")
    return 0


if __name__ == "__main__":
    sys.exit(main())

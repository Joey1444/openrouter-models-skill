# openrouter-models

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

A Claude Code plugin that answers one question fast: **which OpenRouter model should I use, and
which ones are actually free?**

It adds:

| Component | What it does |
|---|---|
| `/openrouter-models:models` | Lists OpenRouter models per modality with **real prices** and **true-free** detection |
| `or_embed` | Embeddings (`/api/v1/embeddings`) |
| `or_decide` | Decision models that return **probabilities, not text** (`/api/alpha/decisions`) |
| `or_list_models` | Raw model listing by modality |

## Why this exists

Two gaps, both found the hard way:

1. **No price or free filter anywhere.** OpenRouter's own model browser makes you hunt through the
   website, and the `search_models` tool in popular OpenRouter MCP servers can only filter on
   vision / audio / video.
2. **Embeddings and decisions are missing.** Mainstream OpenRouter MCP servers cover chat, image,
   video, speech, transcription and rerank — but not these two modalities.

## Install

Two ways — pick one.

**skills.sh** (the open agent skills directory):

```bash
npx skills add Joey1444/openrouter-models-skill
```

**Claude Code plugin** (also adds the `or_embed` / `or_decide` MCP tools):

```bash
claude plugin marketplace add Joey1444/openrouter-models-skill
claude plugin install openrouter-models@openrouter-models
```

Then, in a session:

```
/openrouter-models:models                 # overview of every modality
/openrouter-models:models image --free    # which image models are truly free
/openrouter-models:models speech          # all speech models, cheapest first
```

**The `/models` command needs no API key** — it reads OpenRouter's public models endpoint.
Claude Code prompts you for an OpenRouter API key when you enable the plugin, and only the
`or_embed` / `or_decide` tools use it. You can skip it: leave the field blank and everything except
those two tools still works.

Requires **Python 3** (standard library only, no `pip install`).

## What "truly free" means

The obvious check — "is `prompt` 0?" — is wrong. Real charges hide in `image_output` and
`image_token`, so a model can look free and still bill you. This plugin marks a model free only when:

- its id ends in `:free`, **or**
- **every** pricing field is `0`

And it refuses to guess: a modality whose pricing isn't exposed by the API (true for **all** video
models) is reported as `? price n/a`, never as free.

```
  FREE         inclusionai/ming-image-0.1-design
  FREE         fish-audio/s2.1-pro-free:free
  $4.3e-06     elevenlabs/eleven-v4
  ? price n/a  google/veo-3.1
```

Free models also expire — the default free TTS model that most OpenRouter guides recommend now
404s. Validate before relying on one.

## Relation to other projects

This plugin **complements**
[stabgan/openrouter-mcp-multimodal](https://github.com/stabgan/openrouter-mcp-multimodal)
(Apache-2.0), an excellent MCP server that covers chat, vision, audio, video and rerank for
OpenRouter. If you want those modalities, use it — it is far more complete than anything here.

What this plugin adds is deliberately narrow: the two modalities that project does not implement
(`embeddings`, `decisions`), plus a price-aware model picker. No code was copied from it, so this
plugin is an independent implementation under its own MIT license; the acknowledgement is given
because the gap is defined by that project.

## Layout

```
.claude-plugin/
├── marketplace.json      # catalog: this repo publishes one plugin
└── plugin.json           # manifest + MCP server + userConfig prompt for the API key
skills/models/
├── SKILL.md              # the /openrouter-models:models command
└── list_models.py        # price / free detection
servers/
└── openrouter_gap.py     # MCP server: or_embed, or_decide, or_list_models
```

## 中文速览

**装**：

```bash
claude plugin marketplace add Joey1444/openrouter-models-skill
claude plugin install openrouter-models@openrouter-models
```

**用**：`/openrouter-models:models image --free` —— 查每个模态有哪些模型、**哪些是真免费**、各自什么价。
命令走 OpenRouter 公开接口，**不需要 key**；只有 embeddings / decisions 两个工具需要。

**判据**：id 带 `:free` 或 pricing **全部字段**为 0 才算免费。只看 `prompt`/`completion` 会把收费模型
误判成免费——真实计费常在 `image_output`/`image_token`。视频类定价压根不在接口里，一律标「未知」，不冒充免费。

## License

MIT — see [LICENSE](LICENSE).

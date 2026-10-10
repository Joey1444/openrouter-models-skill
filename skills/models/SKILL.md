---
name: models
description: List OpenRouter models per modality with real prices and true-free detection. Use when the user asks which models are free, wants to pick a model for image / video / speech / embedding / rerank / decision work, or asks what OpenRouter offers.
argument-hint: "[text|image|video|speech|transcription|embeddings|rerank|decisions] [--free]"
allowed-tools: Bash(python ${CLAUDE_SKILL_DIR}/list_models.py:*)
---

## Live inventory (fetched when this command runs)

!`python ${CLAUDE_SKILL_DIR}/list_models.py`

## How to use

- **No modality given** → explain the overview above, then ask which modality they want.
- **A modality is given** (`$ARGUMENTS`) → run the same script with the argument and report only the
  highlights (the free ones, then the cheapest few). Do not paste 60 rows:

  ```
  python ${CLAUDE_SKILL_DIR}/list_models.py $ARGUMENTS
  ```

  Examples: `/openrouter-models:models image --free` · `/openrouter-models:models speech` · `/openrouter-models:models --json video`

## Rules of thumb (don't guess these)

- 🆓 **truly free** = the id ends in `:free`, or **every** pricing field is 0.
  ⚠️ Reading only `prompt` / `completion` marks paid models as free — the real charge is usually in
  `image_output` / `image_token`.
- ❔ **price unknown** = that modality's pricing is not in the API (true for **all** video models).
  Treat it as paid and check openrouter.ai.
- **Free models expire** (the default free TTS model advertised by most OpenRouter guides now 404s).
  Validate with `validate_model` or just try it before relying on it.

## Data source

`https://openrouter.ai/api/v1/models` — public, **no API key needed**.

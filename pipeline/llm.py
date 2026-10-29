"""
One entry point for every creative LLM call in both flows.

  ANTHROPIC_API_KEY set  → Claude via the Anthropic SDK (default claude-opus-5-5),
                           adaptive thinking, schema-constrained JSON output, and
                           the server-side refusal fallback.
  otherwise              → Vercel AI Gateway (free-tier models), JSON parsed
                           from the reply text.

generate_json() always returns a plain dict plus which model produced it.
"""

from __future__ import annotations

import json
import time

from .config import CLAUDE_EFFORT, CLAUDE_MODEL, ENV


class LLMError(RuntimeError):
    pass


# USD per million tokens (input, output); used to report what each video cost on the Claude bill.
_PRICES = {"opus": (4.0, 20.0), "sonnet": (3.0, 15.0), "haiku": (1.0, 5.0), "fable": (10.0, 50.0)}
USAGE = {"inputTokens": 0, "outputTokens": 0, "claudeUsd": 0.0}


def _track(model: str, usage) -> None:
    price = next((v for k, v in _PRICES.items() if k in model), _PRICES["opus"])
    i, o = usage.input_tokens or 0, usage.output_tokens or 0
    USAGE["inputTokens"] += i
    USAGE["outputTokens"] += o
    USAGE["claudeUsd"] = round(USAGE["claudeUsd"] + i / 1e6 * price[0] + o / 1e6 * price[1], 4)


def claude_available() -> bool:
    return bool(ENV.get("ANTHROPIC_API_KEY"))


def _strip_to_json(text: str) -> str:
    t = text.strip()
    if t.startswith("```"):
        t = t.split("```", 2)[1] if t.count("```") >= 2 else t.strip("`")
        if t.lstrip().lower().startswith("json"):
            t = t.lstrip()[4:]
    start, end = t.find("{"), t.rfind("}")
    return t[start:end + 1].strip() if start != -1 and end != -1 else t.strip()


def _claude(system: str, prompt: str, schema: dict | None, max_tokens: int, effort: str) -> dict:
    import anthropic

    client = anthropic.Anthropic(api_key=ENV["ANTHROPIC_API_KEY"], max_retries=3, timeout=600)
    output_config: dict = {"effort": effort}
    if schema:
        output_config["format"] = {"type": "json_schema", "schema": schema}
    try:
        # Streaming keeps long, thinking-heavy generations clear of HTTP timeouts.
        with client.beta.messages.stream(
            model=CLAUDE_MODEL,
            max_tokens=max_tokens,
            system=system,
            messages=[{"role": "user", "content": prompt}],
            output_config=output_config,
            betas=["server-side-fallback-2026-07-01"],
            fallbacks="default",
        ) as stream:
            msg = stream.get_final_message()
    except anthropic.AuthenticationError as e:
        raise LLMError("ANTHROPIC_API_KEY was rejected — check the key in the dashboard.") from e
    except anthropic.PermissionDeniedError as e:
        raise LLMError(f"Claude key lacks permission for {CLAUDE_MODEL}: {e.message}") from e
    except anthropic.NotFoundError as e:
        raise LLMError(f"Unknown Claude model '{CLAUDE_MODEL}'.") from e
    except anthropic.RateLimitError as e:
        raise LLMError("Claude rate limit or spend limit reached — try again later.") from e
    except anthropic.APIStatusError as e:
        raise LLMError(f"Claude API error {e.status_code}: {e.message}") from e
    except anthropic.APIConnectionError as e:
        raise LLMError("Could not reach the Claude API.") from e

    if msg.stop_reason == "refusal":
        raise LLMError("Claude declined this request (refusal).")
    if msg.stop_reason == "max_tokens":
        raise LLMError("Claude ran out of output tokens before finishing the JSON.")
    text = next((b.text for b in msg.content if b.type == "text"), "")
    usage = msg.usage
    _track(msg.model, usage)
    print(f"  [llm] {msg.model} · in {usage.input_tokens} / out {usage.output_tokens} tokens · run total ${USAGE['claudeUsd']:.3f}")
    try:
        return json.loads(text if schema else _strip_to_json(text))
    except json.JSONDecodeError as e:
        raise LLMError(f"Claude returned invalid JSON: {e}") from e


def _gateway(system: str, prompt: str, schema: dict | None, max_tokens: int, model: str) -> dict:
    from openai import OpenAI

    key = ENV.get("AI_GATEWAY_API_KEY") or ENV.get("OPENAI_API_KEY")
    if not key:
        raise LLMError("No LLM key: set ANTHROPIC_API_KEY (Claude) or AI_GATEWAY_API_KEY.")
    client = OpenAI(api_key=key, base_url=ENV.get("LLM_BASE_URL", "https://ai-gateway.vercel.sh/v1"))
    if schema:
        prompt += ("\n\nReply with ONE JSON object that matches this JSON Schema exactly "
                   "(every property present, no extra keys, no markdown):\n"
                   + json.dumps(schema, ensure_ascii=False))
    last: Exception | None = None
    for attempt in range(5):
        try:
            resp = client.chat.completions.create(
                model=model, max_tokens=max_tokens,
                messages=[{"role": "system", "content": system}, {"role": "user", "content": prompt}],
            )
            text = resp.choices[0].message.content or ""
            print(f"  [llm] gateway {model}")
            return json.loads(_strip_to_json(text))
        except json.JSONDecodeError as e:
            last = e
        except Exception as e:  # noqa: BLE001 — free-tier gateway is rate-limited
            last = e
            if "429" in str(e) or "rate" in str(e).lower():
                time.sleep(15 * (attempt + 1))
                continue
            raise LLMError(f"AI Gateway error: {e}") from e
    raise LLMError(f"AI Gateway failed after retries: {last}")


def generate_json(system: str, prompt: str, *, schema: dict | None = None, max_tokens: int = 16000,
                  effort: str | None = None, gateway_model: str | None = None) -> dict:
    if claude_available():
        return _claude(system, prompt, schema, max_tokens, effort or CLAUDE_EFFORT)
    return _gateway(system, prompt, schema, min(max_tokens, 8000),
                    gateway_model or ENV.get("LLM_MODEL") or "google/gemini-2.5-flash-lite")


def provider_label() -> str:
    return CLAUDE_MODEL if claude_available() else "AI Gateway (free tier)"


VISION_MODEL = ENV.get("STORY_VISION_MODEL") or "claude-haiku-5-5"


def look(image_jpeg: bytes, prompt: str, schema: dict) -> dict | None:
    """Ask a small Claude model about one image (schema-constrained JSON). None when Claude isn't
    configured or the call fails — callers decide whether that means "skip the image"."""
    if not claude_available():
        return None
    import base64

    import anthropic

    client = anthropic.Anthropic(api_key=ENV["ANTHROPIC_API_KEY"], max_retries=3, timeout=120)
    try:
        msg = client.messages.create(
            model=VISION_MODEL, max_tokens=1500,
            messages=[{"role": "user", "content": [
                {"type": "image", "source": {"type": "base64", "media_type": "image/jpeg",
                                             "data": base64.b64encode(image_jpeg).decode()}},
                {"type": "text", "text": prompt},
            ]}],
            output_config={"format": {"type": "json_schema", "schema": schema}},
        )
    except anthropic.APIError as e:
        print(f"  [vision] {e.__class__.__name__}")
        return None
    _track(msg.model, msg.usage)
    text = next((b.text for b in msg.content if b.type == "text"), "")
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        print(f"  [vision] unreadable reply (stop: {msg.stop_reason}): {text[:120]!r}")
        return None

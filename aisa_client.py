"""Instrumented client for the AIsa LLM gateway.

Wraps the OpenAI-compatible /chat/completions endpoint and logs every
call (latency, token usage, cost) to a local SQLite DB via db.py.

Design decision: if a model's price isn't in pricing.json (or is marked
verified: false), cost is logged as cost_status="unknown_price" with
cost_usd=None, instead of guessing. Silently estimating a wrong cost is
worse than admitting the cost is unknown.
"""
import json
import os
import time
from pathlib import Path

import requests
from dotenv import load_dotenv

import db

load_dotenv()

BASE_URL = os.environ.get("AISA_BASE_URL", "https://api.aisa.one/v1")
API_KEY = os.environ.get("AISA_API_KEY")

PRICING_PATH = Path(__file__).parent / "pricing.json"
_pricing_cache = None


def _load_pricing() -> dict:
    global _pricing_cache
    if _pricing_cache is None:
        with open(PRICING_PATH, encoding="utf-8") as f:
            _pricing_cache = json.load(f)
    return _pricing_cache


def get_model_price(model: str) -> dict | None:
    """Returns {"input": float, "output": float} per 1M tokens, only if
    both values are known and verified. Otherwise returns None."""
    pricing = _load_pricing()
    entry = pricing["models"].get(model)
    if not entry or not entry.get("verified"):
        return None
    if entry.get("input") is None or entry.get("output") is None:
        return None
    return {"input": entry["input"], "output": entry["output"]}


def estimate_cost_usd(model: str, prompt_tokens: int, completion_tokens: int) -> tuple[float | None, str]:
    """Returns (cost_usd or None, cost_status)."""
    price = get_model_price(model)
    if price is None:
        return None, "unknown_price"
    cost = (prompt_tokens / 1_000_000) * price["input"] + (completion_tokens / 1_000_000) * price["output"]
    return cost, "known"


def chat_completion(model: str, messages: list[dict], run_tag: str | None = None, **kwargs) -> dict:
    """Calls POST /chat/completions, logs the call, returns the parsed JSON response.

    Raises requests.HTTPError on non-2xx (after logging the failed call).
    """
    if not API_KEY:
        raise RuntimeError("AISA_API_KEY not set — copy .env.example to .env and fill it in.")

    payload = {"model": model, "messages": messages, **kwargs}
    headers = {"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"}

    start = time.perf_counter()
    try:
        resp = requests.post(f"{BASE_URL}/chat/completions", headers=headers, json=payload, timeout=120)
        latency_ms = (time.perf_counter() - start) * 1000
        resp.raise_for_status()
        data = resp.json()
    except requests.RequestException as e:
        latency_ms = (time.perf_counter() - start) * 1000
        db.log_call(
            model=model, provider=None, endpoint="chat.completions",
            prompt_tokens=None, completion_tokens=None, total_tokens=None,
            latency_ms=latency_ms, cost_usd=None, cost_status="error",
            status="error", error_message=str(e), run_tag=run_tag,
        )
        raise

    usage = data.get("usage", {})
    prompt_tokens = usage.get("prompt_tokens")
    completion_tokens = usage.get("completion_tokens")
    total_tokens = usage.get("total_tokens")

    cost_usd, cost_status = (None, "unknown_price")
    if prompt_tokens is not None and completion_tokens is not None:
        cost_usd, cost_status = estimate_cost_usd(model, prompt_tokens, completion_tokens)

    db.log_call(
        model=model, provider=data.get("owned_by"), endpoint="chat.completions",
        prompt_tokens=prompt_tokens, completion_tokens=completion_tokens, total_tokens=total_tokens,
        latency_ms=latency_ms, cost_usd=cost_usd, cost_status=cost_status,
        status="ok", error_message=None, run_tag=run_tag,
    )
    return data

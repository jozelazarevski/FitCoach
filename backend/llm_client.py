"""
Backend LLM client — unified interface for Ollama and Anthropic Claude.
Used by recipe suggestion and generation endpoints.
"""

import json
import os

try:
    import anthropic
except ImportError:
    anthropic = None

try:
    import requests as _requests
except ImportError:
    _requests = None

from config import ANTHROPIC_API_KEY, OLLAMA_BASE_URL, OLLAMA_MODEL


def _get_provider_config():
    """Get the best available LLM provider config from DB or env."""
    from backend.api.admin import get_active_api_key

    # Try Ollama first (free, local)
    ollama_data = get_active_api_key('ollama')
    if ollama_data and _requests:
        url = ollama_data.get('api_key', '') or OLLAMA_BASE_URL
        model = ollama_data.get('model', '') or OLLAMA_MODEL
        # Quick check if Ollama is reachable
        try:
            r = _requests.get(f"{url}/api/tags", timeout=2)
            if r.ok:
                return {'provider': 'ollama', 'url': url, 'model': model}
        except Exception:
            pass

    # Check env-based Ollama
    if _requests and OLLAMA_BASE_URL:
        try:
            r = _requests.get(f"{OLLAMA_BASE_URL}/api/tags", timeout=2)
            if r.ok:
                return {'provider': 'ollama', 'url': OLLAMA_BASE_URL, 'model': OLLAMA_MODEL}
        except Exception:
            pass

    # Try Anthropic from DB
    anthropic_data = get_active_api_key('anthropic')
    if anthropic_data and anthropic:
        return {
            'provider': 'anthropic',
            'api_key': anthropic_data['api_key'],
            'model': anthropic_data.get('model', '') or 'claude-haiku-4-5-20251001'
        }

    # Try Anthropic from env
    if ANTHROPIC_API_KEY and anthropic:
        return {
            'provider': 'anthropic',
            'api_key': ANTHROPIC_API_KEY,
            'model': 'claude-haiku-4-5-20251001'
        }

    return None


def call_llm(prompt, max_tokens=4000):
    """Call the best available LLM and return the text response.

    Returns the raw text response from the LLM.
    Raises RuntimeError if no LLM provider is available.
    """
    config = _get_provider_config()
    if not config:
        raise RuntimeError("No LLM provider configured. Add an API key via admin panel or set OLLAMA_BASE_URL / ANTHROPIC_API_KEY.")

    if config['provider'] == 'ollama':
        return _call_ollama(config['url'], config['model'], prompt, max_tokens)
    else:
        return _call_anthropic(config['api_key'], config['model'], prompt, max_tokens)


def _call_ollama(base_url, model, prompt, max_tokens):
    """Call Ollama API with fallback between /api/chat and /api/generate."""
    # Try /api/chat first (newer Ollama)
    resp = _requests.post(
        f"{base_url}/api/chat",
        json={
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "stream": False,
            "options": {"num_predict": max_tokens, "temperature": 0.7}
        },
        timeout=300
    )
    if resp.status_code == 404:
        # Older Ollama — try /api/generate
        resp = _requests.post(
            f"{base_url}/api/generate",
            json={
                "model": model,
                "prompt": prompt,
                "stream": False,
                "options": {"num_predict": max_tokens, "temperature": 0.7}
            },
            timeout=300
        )
        resp.raise_for_status()
        return resp.json().get("response", "")
    resp.raise_for_status()
    return resp.json().get("message", {}).get("content", "")


def _call_anthropic(api_key, model, prompt, max_tokens):
    """Call Anthropic Claude API."""
    client = anthropic.Anthropic(api_key=api_key)
    response = client.messages.create(
        model=model,
        max_tokens=max_tokens,
        messages=[{"role": "user", "content": prompt}]
    )
    return response.content[0].text


def call_llm_json(prompt, max_tokens=4000):
    """Call LLM and parse JSON from the response.

    Returns parsed JSON (dict or list).
    Raises ValueError if JSON cannot be parsed.
    """
    text = call_llm(prompt, max_tokens)
    # Clean markdown fences
    text = text.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1] if "\n" in text else text[3:]
        text = text.rsplit("```", 1)[0]
    text = text.strip()

    # Try to find JSON object or array
    for start_char, end_char in [('[', ']'), ('{', '}')]:
        if start_char in text:
            start = text.find(start_char)
            end = text.rfind(end_char)
            if start != -1 and end != -1 and end > start:
                try:
                    return json.loads(text[start:end + 1])
                except json.JSONDecodeError:
                    continue

    # Last resort: try full text
    return json.loads(text)

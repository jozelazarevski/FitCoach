"""Tests for backend.llm_client — JSON parsing from LLM responses."""

import json
from unittest.mock import patch

from backend.llm_client import call_llm_json


def _mock_call_llm(text):
    """Return a patcher that makes call_llm return *text*."""
    return patch("backend.llm_client.call_llm", return_value=text)


def test_call_llm_json_clean():
    """Clean JSON string should be parsed correctly."""
    payload = {"name": "Chicken Bowl", "calories": 400}
    with _mock_call_llm(json.dumps(payload)):
        result = call_llm_json("test prompt")
    assert result == payload


def test_call_llm_json_strips_markdown_fences():
    """JSON wrapped in markdown code fences should be extracted."""
    payload = {"name": "Rice Bowl", "calories": 350}
    raw = f"```json\n{json.dumps(payload)}\n```"
    with _mock_call_llm(raw):
        result = call_llm_json("test prompt")
    assert result == payload


def test_call_llm_json_extracts_from_surrounding_text():
    """JSON embedded in surrounding prose should be extracted."""
    payload = [{"name": "Salad", "calories": 200}]
    raw = f"Here is the result:\n{json.dumps(payload)}\nHope that helps!"
    with _mock_call_llm(raw):
        result = call_llm_json("test prompt")
    assert result == payload


def test_call_llm_json_object_in_text():
    """A JSON object embedded in text should be found."""
    payload = {"suggestion": "eat more protein"}
    raw = f"Sure! {json.dumps(payload)} Let me know if you need more."
    with _mock_call_llm(raw):
        result = call_llm_json("test prompt")
    assert result == payload

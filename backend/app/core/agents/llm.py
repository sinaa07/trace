"""Pluggable LLM providers for investigation agents.

Default path is local/heuristic so no paid API is required.
Optional OpenAI-compatible endpoint (Ollama/vLLM) or Anthropic/OpenAI.
"""

from __future__ import annotations

import json
import re
from typing import Any, Protocol

import httpx

from app.core.config import settings
from app.schemas.investigation import HypothesisFindingCreate


class LLMProvider(Protocol):
    def complete_json(
        self,
        *,
        system: str,
        user: str,
        schema_hint: str | None = None,
    ) -> dict[str, Any]:
        ...


class HeuristicLLM:
    """No-network synthesizer used when LLM_PROVIDER=heuristic (default)."""

    def complete_json(
        self,
        *,
        system: str,
        user: str,
        schema_hint: str | None = None,
    ) -> dict[str, Any]:
        # Orchestrator never relies on this for the default path;
        # HeuristicAgent synthesizes findings directly. Keep a stub for interface.
        return {
            "hypothesis": "Insufficient model configuration for generative synthesis.",
            "reasoning": "Heuristic provider does not generate free-form JSON; use domain synthesizer.",
            "supporting_evidence": [],
            "contradicting_evidence": [],
            "relevant_events": [],
            "missing_evidence": [],
            "assumptions": ["LLM_PROVIDER=heuristic"],
            "reasoning_summary": "Heuristic mode active.",
            "confidence": 0.0,
            "uncertainty": "No generative model configured.",
        }


class OpenAICompatibleLLM:
    """OpenAI chat-completions compatible (Ollama, vLLM, OpenAI)."""

    def __init__(
        self,
        *,
        base_url: str | None = None,
        api_key: str | None = None,
        model: str | None = None,
        timeout: float = 60.0,
    ) -> None:
        self.base_url = (base_url or settings.llm_base_url).rstrip("/")
        self.api_key = api_key if api_key is not None else settings.llm_api_key
        self.model = model or settings.llm_model
        self.timeout = timeout

    def complete_json(
        self,
        *,
        system: str,
        user: str,
        schema_hint: str | None = None,
    ) -> dict[str, Any]:
        messages = [
            {"role": "system", "content": system},
            {
                "role": "user",
                "content": user
                + (
                    f"\n\nReturn ONLY valid JSON matching: {schema_hint}"
                    if schema_hint
                    else "\n\nReturn ONLY valid JSON."
                ),
            },
        ]
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": 0.1,
        }
        url = f"{self.base_url}/chat/completions"
        with httpx.Client(timeout=self.timeout) as client:
            response = client.post(url, headers=headers, json=payload)
            response.raise_for_status()
            data = response.json()
        content = data["choices"][0]["message"]["content"]
        return _parse_json_object(content)


class AnthropicLLM:
    """Optional Anthropic Messages API (paid; not default)."""

    def __init__(
        self,
        *,
        api_key: str | None = None,
        model: str | None = None,
        timeout: float = 60.0,
    ) -> None:
        self.api_key = api_key or settings.llm_api_key
        self.model = model or settings.llm_model or "claude-sonnet-4-20250514"
        self.timeout = timeout

    def complete_json(
        self,
        *,
        system: str,
        user: str,
        schema_hint: str | None = None,
    ) -> dict[str, Any]:
        if not self.api_key:
            raise RuntimeError("ANTHROPIC / LLM_API_KEY required for anthropic provider")
        body = {
            "model": self.model,
            "max_tokens": 2048,
            "system": system,
            "messages": [
                {
                    "role": "user",
                    "content": user
                    + (
                        f"\n\nReturn ONLY valid JSON matching: {schema_hint}"
                        if schema_hint
                        else "\n\nReturn ONLY valid JSON."
                    ),
                }
            ],
        }
        headers = {
            "content-type": "application/json",
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
        }
        with httpx.Client(timeout=self.timeout) as client:
            response = client.post(
                "https://api.anthropic.com/v1/messages",
                headers=headers,
                json=body,
            )
            response.raise_for_status()
            data = response.json()
        content = "".join(
            block.get("text", "")
            for block in data.get("content", [])
            if block.get("type") == "text"
        )
        return _parse_json_object(content)


def get_llm_provider(name: str | None = None) -> LLMProvider:
    provider = (name or settings.llm_provider or "heuristic").strip().lower()
    if provider in {"heuristic", "none", "local-heuristic"}:
        return HeuristicLLM()
    if provider in {"openai", "openai_compatible", "ollama", "vllm"}:
        return OpenAICompatibleLLM()
    if provider in {"anthropic", "claude"}:
        return AnthropicLLM()
    raise ValueError(f"Unknown LLM_PROVIDER: {provider}")


def finding_from_llm_dict(
    data: dict[str, Any],
    *,
    domain: str,
    domain_features: dict[str, Any] | None = None,
) -> HypothesisFindingCreate:
    return HypothesisFindingCreate(
        domain=domain,
        hypothesis=str(data.get("hypothesis") or "").strip() or "Unspecified hypothesis",
        reasoning=str(data.get("reasoning") or data.get("reasoning_summary") or ""),
        supporting_evidence=_as_str_list(data.get("supporting_evidence")),
        contradicting_evidence=_as_str_list(data.get("contradicting_evidence")),
        relevant_events=_as_str_list(data.get("relevant_events")),
        missing_evidence=_as_str_list(data.get("missing_evidence")),
        assumptions=_as_str_list(data.get("assumptions")),
        reasoning_summary=str(data.get("reasoning_summary") or "")[:2000],
        confidence=_clamp_float(data.get("confidence"), 0.0),
        uncertainty=(str(data["uncertainty"]) if data.get("uncertainty") is not None else None),
        domain_features=domain_features,
    )


def _as_str_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(v) for v in value]
    return [str(value)]


def _clamp_float(value: Any, default: float) -> float:
    try:
        return max(0.0, min(float(value), 1.0))
    except (TypeError, ValueError):
        return default


def _parse_json_object(text: str) -> dict[str, Any]:
    text = text.strip()
    try:
        parsed = json.loads(text)
        if isinstance(parsed, dict):
            return parsed
    except json.JSONDecodeError:
        pass
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if match:
        parsed = json.loads(match.group(0))
        if isinstance(parsed, dict):
            return parsed
    raise ValueError("LLM response did not contain a JSON object")

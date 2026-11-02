"""Model providers behind one interface (workstream 6).

The rest of OpenDPO asks a provider for one thing: given instructions, the material and a
JSON Schema, return an object that fits the schema. Which provider runs is a setting, so the
platform is not tied to one AI vendor:

- anthropic: Claude through the Anthropic API. Needs ANTHROPIC_API_KEY. The answer comes back
  as the input of a single tool, submit_draft, whose input schema is the draft format. The tool
  is offered with tool_choice "auto" and the prompt says to call it: current models think before
  answering, and Sonnet 5.5 and Opus 5.5 refuse a forced tool call with a 400 error. A reply
  that does not call the tool raises NoToolCall, which the drafter treats as a fixable mistake.
- fixture: replays a saved draft. No key, no cost and the same answer every time, so CI and a
  recording-day backup never depend on a live call. Every revision it writes is labelled as
  coming from the fixture.

Settings (environment): OPENDPO_AGENT_PROVIDER (anthropic or fixture; default anthropic when a
key is set, otherwise fixture), OPENDPO_AGENT_MODEL (default claude-sonnet-5-5),
OPENDPO_AGENT_FIXTURE (path of the saved draft).
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol

import httpx

DEFAULT_MODEL = "claude-sonnet-5-5"
DEFAULT_FIXTURE = Path(__file__).resolve().parents[2] / "tests" / "fixtures" / "harbor_draft.json"
ANTHROPIC_URL = "https://api.anthropic.com/v1/messages"


class ProviderError(RuntimeError):
    pass


class NoToolCall(ProviderError):
    """The model answered without calling submit_draft. Carries the reply so the drafter can ask
    again in the same conversation."""

    def __init__(self, reply: "Reply"):
        super().__init__("the model answered without calling submit_draft")
        self.reply = reply


@dataclass
class Reply:
    output: dict[str, Any]
    provider: str
    model: str
    usage: dict[str, Any] = field(default_factory=dict)
    # The assistant turn exactly as returned (thinking blocks included), and the id of its
    # submit_draft call, so a repair round can send it back unchanged as the API requires.
    content: list[dict[str, Any]] = field(default_factory=list)
    tool_use_id: str | None = None


class Provider(Protocol):
    name: str
    model: str

    def complete(self, system: str, messages: list[dict[str, Any]], schema: dict[str, Any],
                 max_tokens: int = 32000) -> Reply: ...


class AnthropicProvider:
    name = "anthropic"

    def __init__(self, model: str | None = None, api_key: str | None = None, timeout: float = 600):
        self.model = model or os.environ.get("OPENDPO_AGENT_MODEL") or DEFAULT_MODEL
        self.api_key = api_key or os.environ.get("ANTHROPIC_API_KEY")
        self.timeout = timeout
        if not self.api_key:
            raise ProviderError("ANTHROPIC_API_KEY is not set")

    def complete(self, system: str, messages: list[dict[str, Any]], schema: dict[str, Any],
                 max_tokens: int = 32000) -> Reply:
        # max_tokens covers the model's thinking as well as the draft, hence the headroom.
        body = {
            "model": self.model, "max_tokens": max_tokens, "system": system, "messages": messages,
            "tools": [{"name": "submit_draft", "description": "Submit the assessment draft.",
                       "input_schema": schema}],
            "tool_choice": {"type": "auto"},
        }
        try:
            r = httpx.post(ANTHROPIC_URL, json=body, timeout=self.timeout, headers={
                "x-api-key": self.api_key, "anthropic-version": "2023-06-01", "content-type": "application/json"})
        except httpx.HTTPError as exc:
            raise ProviderError(f"the model could not be reached: {exc}") from exc
        if r.status_code != 200:
            raise ProviderError(f"the model returned HTTP {r.status_code}: {r.text[:500]}")
        data = r.json()
        if data.get("stop_reason") == "max_tokens":
            raise ProviderError("the draft was cut off at the token limit")
        content = data.get("content", [])
        block = next((b for b in content if b.get("type") == "tool_use" and b.get("name") == "submit_draft"), None)
        reply = Reply(block["input"] if block else {}, self.name, data.get("model", self.model),
                      data.get("usage", {}), content, block.get("id") if block else None)
        if block is None:
            raise NoToolCall(reply)
        return reply


class FixtureProvider:
    name = "fixture"

    def __init__(self, path: Path | str | None = None):
        self.path = Path(path or os.environ.get("OPENDPO_AGENT_FIXTURE") or DEFAULT_FIXTURE)
        self.model = f"fixture:{self.path.name}"

    def complete(self, system: str, messages: list[dict[str, Any]], schema: dict[str, Any],
                 max_tokens: int = 32000) -> Reply:
        try:
            saved = json.loads(self.path.read_text(encoding="utf-8"))
        except OSError as exc:
            raise ProviderError(f"the saved draft {self.path} could not be read") from exc
        return Reply(saved["draft"], self.name, self.model, {"note": saved.get("note", "")})


def from_settings(model: str | None = None) -> Provider:
    choice = os.environ.get("OPENDPO_AGENT_PROVIDER") or ("anthropic" if os.environ.get("ANTHROPIC_API_KEY")
                                                          else "fixture")
    if choice == "anthropic":
        return AnthropicProvider(model=model)
    if choice == "fixture":
        return FixtureProvider()
    raise ProviderError(f"unknown OPENDPO_AGENT_PROVIDER {choice!r}; use anthropic or fixture")

"""Model gateway. Connected mode runs real Google ADK agents on an NVIDIA-hosted OpenAI-compatible endpoint via
LiteLLM; sample mode uses explicitly labelled scripted roles. Outputs are always validated by Pydantic schemas;
a model can never authorize an action — it only proposes typed data that deterministic code checks.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Callable, Protocol

from pydantic import BaseModel, ValidationError

from greenops.config import Settings

SCRIPTED_MODEL_ID = "scripted-sample-v1"


class ModelError(Exception):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


class BudgetExceeded(ModelError):
    def __init__(self, message: str):
        super().__init__("BUDGET_EXCEEDED", message)


@dataclass
class RoleResult:
    output: BaseModel
    model_id: str
    input_tokens: int | None
    output_tokens: int | None
    model_requests: int
    tool_calls: int
    duration_ms: int
    corrective_attempts: int = 0
    tool_log: list[dict] = field(default_factory=list)


@dataclass
class Budget:
    """Per-run call/cost guard. `reserve` is called before every model request (retries included)."""
    max_calls: int
    max_cost_usd: Any  # Decimal
    conservative_cost_per_call: Any  # Decimal
    used_calls: int = 0

    def reserve(self) -> None:
        if self.used_calls + 1 > self.max_calls:
            raise BudgetExceeded(f"model call budget {self.max_calls} exhausted")
        if (self.used_calls + 1) * self.conservative_cost_per_call > self.max_cost_usd:
            raise BudgetExceeded("conservative spend reservation would exceed the run cap")
        self.used_calls += 1


class ModelGateway(Protocol):
    model_id: str

    def run(self, role: str, instruction: str, payload: dict, output_model: type[BaseModel], *,
            tools: list[Callable] | None = None, budget: Budget | None = None,
            before_tool: Callable | None = None, timeout_s: float = 45.0) -> RoleResult: ...


def _strip_fence(text: str) -> str:
    t = text.strip()
    if t.startswith("```"):
        t = t.split("\n", 1)[1] if "\n" in t else ""
        t = t.rsplit("```", 1)[0]
    return t.strip()


_LITELLM_WARM = False


def _warm_litellm() -> None:
    """LiteLLM lazily imports ~3,000 provider/type modules (≈30 s of Pydantic schema building) inside the first
    acompletion, which counted against the role timeout and failed the first real investigation (25 Oct). One
    offline mock completion per process pays that cost outside any timed call; it sends no request."""
    global _LITELLM_WARM
    if _LITELLM_WARM:
        return
    import litellm
    asyncio.run(litellm.acompletion(model="openai/warmup", messages=[{"role": "user", "content": "warmup"}],
                                    mock_response="{}", api_key="unused", api_base="http://127.0.0.1:9"))
    _LITELLM_WARM = True


class AdkGateway:
    """Real ADK LlmAgent per role call; one bounded corrective re-request for schema violations."""

    def __init__(self, settings: Settings):
        if not settings.model_configured:
            raise ModelError("DEPENDENCY_UNAVAILABLE", "MODEL_ID/MODEL_API_KEY not configured")
        os.environ.setdefault("LITELLM_LOG", "ERROR")
        logging.getLogger("LiteLLM").setLevel(logging.ERROR)
        _warm_litellm()
        from google.adk.models._capabilities import LlmCapabilities
        from google.adk.models.lite_llm import LiteLlm  # imported lazily: no network at import time

        class NimLiteLlm(LiteLlm):
            """LiteLlm claims output_schema_and_tools, so ADK sent tools together with a json_schema response_format.
            NVIDIA's guided JSON decoding then forbids tool calls and the model answered without any lookup (NIM-01,
            25 Oct). Declaring it unsupported makes ADK use its set_model_response tool for the typed final answer."""

            @property
            def capabilities(self) -> LlmCapabilities:
                return LlmCapabilities(**super().capabilities.model_dump() | {"output_schema_and_tools": False})

        self.model_id = settings.model_id
        self.structured = os.environ.get("MODEL_STRUCTURED_OUTPUT", "json_schema")
        # Generation ceiling so the conservative per-request reservation bounds actual spend (audit A08).
        # Nemotron reasoning tokens count against max_tokens and truncated typed JSON in a real call (25 Oct), so
        # reasoning is off unless MODEL_REASONING=on; deterministic checks, not model reasoning, decide outcomes.
        reasoning = os.environ.get("MODEL_REASONING", "off") == "on"
        self._llm = NimLiteLlm(model=f"openai/{settings.model_id}", api_base=settings.model_base_url,
                            api_key=settings.model_api_key, temperature=0, max_tokens=int(os.environ.get("MODEL_MAX_OUTPUT_TOKENS", "1024")),
                            extra_body={"chat_template_kwargs": {"enable_thinking": reasoning}})

    def run(self, role, instruction, payload, output_model, *, tools=None, budget=None, before_tool=None, timeout_s=None):
        # Per-turn ceiling; 45 s was too tight for a 120B hosted model writing a typed report plus one correction.
        timeout_s = timeout_s or float(os.environ.get("MODEL_ROLE_TIMEOUT_S", "90"))
        # One fresh-session retry for a transient provider failure (a single >90 s or HTTP 500 response failed whole
        # investigations on 25 and 26 Oct). Role calls are read-only proposals; every request still reserves budget.
        for attempt in (1, 2):
            try:
                return asyncio.run(self._run(role, instruction, payload, output_model, tools or [], budget, before_tool, timeout_s))
            except ModelError as e:
                if e.code != "DEPENDENCY_UNAVAILABLE" or attempt == 2:
                    raise
                logging.getLogger(__name__).warning("%s: transient provider failure, retrying once: %s", role, e)

    async def _run(self, role, instruction, payload, output_model, tools, budget, before_tool, timeout_s):
        from google.adk.agents import LlmAgent
        from google.adk.runners import InMemoryRunner
        from google.genai import types

        def before_model(callback_context, llm_request):
            if budget:
                budget.reserve()
            return None

        schema_text = json.dumps(output_model.model_json_schema())
        instr = instruction + ("\n\nReturn ONLY a JSON object matching this JSON schema:\n" + schema_text
                               if self.structured == "prompt" else "")
        agent = LlmAgent(name=role, model=self._llm, instruction=instr, tools=tools,
                         output_schema=output_model if self.structured == "json_schema" else None,
                         before_model_callback=before_model, before_tool_callback=before_tool)
        runner = InMemoryRunner(agent=agent, app_name="greenops")
        session = await runner.session_service.create_session(app_name="greenops", user_id="greenops-worker")
        started = time.perf_counter()
        totals = {"in": 0, "out": 0, "usage_missing": False, "requests": 0, "tools": 0}
        tool_log: list[dict] = []

        async def turn(text: str) -> str:
            final = ""
            msg = types.Content(role="user", parts=[types.Part(text=text)])
            async for ev in runner.run_async(user_id="greenops-worker", session_id=session.id, new_message=msg):
                if ev.usage_metadata is not None:
                    totals["requests"] += 1
                    totals["in"] += ev.usage_metadata.prompt_token_count or 0
                    totals["out"] += ev.usage_metadata.candidates_token_count or 0
                for p in (ev.content.parts if ev.content and ev.content.parts else []):
                    if p.function_call and p.function_call.name == "set_model_response":
                        continue  # ADK's typed-final-answer tool, not a data tool call
                    if p.function_call:
                        totals["tools"] += 1
                        tool_log.append({"tool": p.function_call.name, "args": dict(p.function_call.args or {})})
                    elif p.text and ev.is_final_response() and not getattr(p, "thought", False):
                        final += p.text
            return final

        corrective = 0
        try:
            text = await asyncio.wait_for(turn(json.dumps(payload, default=str)), timeout_s)
            try:
                out = output_model.model_validate_json(_strip_fence(text))
            except ValidationError as e:
                corrective = 1  # exactly one bounded corrective attempt; no free-form JSON repair
                text = await asyncio.wait_for(turn(
                    "Your previous reply did not match the required schema: " + str(e.errors()[:5])[:800]
                    + ". Reply again with ONLY the corrected JSON object."), timeout_s)
                out = output_model.model_validate_json(_strip_fence(text))
        except ValidationError as e:
            raise ModelError("MODEL_OUTPUT_INVALID", f"{role}: schema violation after corrective attempt: {e.error_count()} errors")
        except asyncio.TimeoutError:
            raise ModelError("DEPENDENCY_UNAVAILABLE", f"{role}: model call exceeded {timeout_s}s")
        except BudgetExceeded:
            raise
        except ModelError:
            raise
        except Exception as e:  # provider/transport errors: bounded, typed, no secrets
            raise ModelError("DEPENDENCY_UNAVAILABLE", f"{role}: model provider error {type(e).__name__}")
        return RoleResult(out, self.model_id, totals["in"] if totals["requests"] else None,
                          totals["out"] if totals["requests"] else None, totals["requests"], totals["tools"],
                          int((time.perf_counter() - started) * 1000), corrective, tool_log)


class ScriptedGateway:
    """Sample/test mode only: deterministic role functions. Never presented as model evidence."""

    model_id = SCRIPTED_MODEL_ID

    def __init__(self, scripts: dict[str, Callable[[dict, list[Callable] | None], dict]]):
        self.scripts = scripts

    def run(self, role, instruction, payload, output_model, *, tools=None, budget=None, before_tool=None, timeout_s=45.0):
        if budget:
            budget.reserve()
        started = time.perf_counter()
        out = output_model.model_validate(self.scripts[role](payload, tools))
        return RoleResult(out, self.model_id, None, None, 1, 0, int((time.perf_counter() - started) * 1000))


def new_call_id() -> str:
    return str(uuid.uuid4())

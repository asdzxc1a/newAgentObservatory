from __future__ import annotations

import asyncio
import os
import time
import uuid
from typing import Any, Literal

from agents import Agent, Runner
from mcp.server import MCPServer
from mcp.server.transport_security import TransportSecuritySettings

try:
    from agents.extensions.experimental.hosted_multi_agent import (
        OpenAIHostedMultiAgentModel,
    )
except Exception:  # The experimental surface may move between SDK releases.
    OpenAIHostedMultiAgentModel = None  # type: ignore[assignment,misc]


SERVER_VERSION = "0.1.0"
DEFAULT_MODEL = os.getenv("OPENAI_MODEL", "gpt-5.6-sol")
ENABLE_HOSTED = os.getenv("ENABLE_HOSTED_MULTI_AGENT", "1").lower() not in {
    "0",
    "false",
    "no",
}
MAX_ALLOWED_SUBAGENTS = int(os.getenv("MAX_SUBAGENTS", "8"))

mcp = MCPServer(
    "ChatGPT Native Subagent Primitive",
    version=SERVER_VERSION,
    instructions=(
        "This server gives ChatGPT explicit delegation primitives. Use `delegate` for one "
        "specialist and `swarm` for multiple independent specialists followed by synthesis. "
        "Prefer `swarm` when independent perspectives, research branches, review passes, or "
        "parallel decomposition will materially improve the result."
    ),
)


def _require_api_key() -> None:
    if not os.getenv("OPENAI_API_KEY"):
        raise RuntimeError(
            "OPENAI_API_KEY is not set on the MCP server. Add it as a secret environment "
            "variable on the host, then retry."
        )


def _normalize_hostname(value: str) -> str:
    host = value.strip()
    for prefix in ("https://", "http://"):
        if host.startswith(prefix):
            host = host[len(prefix) :]
    return host.split("/", 1)[0].strip()


def _transport_security() -> TransportSecuritySettings:
    """Build a narrow Host/Origin allowlist for local and hosted deployments.

    Render injects RENDER_EXTERNAL_HOSTNAME at runtime. Other hosts can set
    MCP_PUBLIC_HOST to one hostname or a comma-separated list. This keeps DNS
    rebinding protection enabled by default instead of broadly disabling it.
    """
    configured: list[str] = []
    for source in (os.getenv("RENDER_EXTERNAL_HOSTNAME", ""), os.getenv("MCP_PUBLIC_HOST", "")):
        configured.extend(_normalize_hostname(item) for item in source.split(",") if item.strip())
    hosts = list(dict.fromkeys(host for host in configured if host))

    if not hosts:
        return TransportSecuritySettings(
            enable_dns_rebinding_protection=True,
            allowed_hosts=["127.0.0.1:*", "localhost:*", "[::1]:*"],
            allowed_origins=[
                "http://127.0.0.1:*",
                "http://localhost:*",
                "http://[::1]:*",
            ],
        )

    allowed_hosts: list[str] = []
    allowed_origins: list[str] = []
    for host in hosts:
        allowed_hosts.extend([host, f"{host}:*"])
        allowed_origins.extend([f"https://{host}", f"https://{host}:*"])

    return TransportSecuritySettings(
        enable_dns_rebinding_protection=True,
        allowed_hosts=list(dict.fromkeys(allowed_hosts)),
        allowed_origins=list(dict.fromkeys(allowed_origins)),
    )


def _clean_roles(roles: list[str] | None) -> list[str]:
    cleaned = [r.strip() for r in (roles or []) if r and r.strip()]
    if not cleaned:
        cleaned = ["researcher", "skeptic", "implementation specialist"]
    return list(dict.fromkeys(cleaned))[:MAX_ALLOWED_SUBAGENTS]


async def _run_one_specialist(
    *,
    role: str,
    task: str,
    context: str,
    model: str,
    semaphore: asyncio.Semaphore,
) -> dict[str, str]:
    instructions = (
        f"You are the {role} subagent in a larger coordinated run. Work independently. "
        "Focus only on your specialty, surface concrete evidence/reasoning, identify uncertainty, "
        "and return a compact result that another agent can synthesize. Do not pretend you ran "
        "tools you do not actually have."
    )
    prompt = task if not context else f"TASK:\n{task}\n\nSHARED CONTEXT:\n{context}"
    agent = Agent(name=role[:80], instructions=instructions, model=model)
    async with semaphore:
        result = await Runner.run(agent, prompt)
    return {"role": role, "output": str(result.final_output)}


async def _run_local_swarm(
    *,
    task: str,
    roles: list[str],
    context: str,
    model: str,
    max_concurrency: int,
) -> tuple[str, list[dict[str, str]]]:
    semaphore = asyncio.Semaphore(max_concurrency)
    specialist_results = await asyncio.gather(
        *[
            _run_one_specialist(
                role=role,
                task=task,
                context=context,
                model=model,
                semaphore=semaphore,
            )
            for role in roles
        ]
    )

    evidence = "\n\n".join(
        f"## {item['role']}\n{item['output']}" for item in specialist_results
    )
    synthesizer = Agent(
        name="subagent-synthesizer",
        model=model,
        instructions=(
            "You are the parent agent synthesizing independent subagent outputs. Resolve conflicts, "
            "preserve important caveats, avoid majority-vote reasoning, and produce one coherent "
            "answer that directly addresses the original task."
        ),
    )
    synth_prompt = f"ORIGINAL TASK:\n{task}\n\nSUBAGENT OUTPUTS:\n{evidence}"
    if context:
        synth_prompt += f"\n\nSHARED CONTEXT:\n{context}"
    result = await Runner.run(synthesizer, synth_prompt)
    return str(result.final_output), specialist_results


async def _run_hosted_swarm(
    *,
    task: str,
    roles: list[str],
    context: str,
    model: str,
    max_concurrency: int,
) -> str:
    if OpenAIHostedMultiAgentModel is None:
        raise RuntimeError(
            "The installed openai-agents package does not expose the experimental hosted "
            "multi-agent model. Upgrade openai-agents or use mode='local'."
        )

    hosted_model = OpenAIHostedMultiAgentModel(
        model=model,
        config={"max_concurrent_subagents": max_concurrency},
    )
    role_text = ", ".join(roles)
    instructions = (
        "You are the root coordinator. Create and coordinate server-hosted subagents to solve the "
        "task. Delegate independent branches concurrently when possible. Ensure the requested "
        f"perspectives are covered: {role_text}. Have subagents challenge each other where useful, "
        "then synthesize one final answer. Do not expose internal orchestration chatter unless it is "
        "material to the result."
    )
    prompt = task if not context else f"TASK:\n{task}\n\nSHARED CONTEXT:\n{context}"
    root = Agent(name="hosted-subagent-root", instructions=instructions, model=hosted_model)
    try:
        result = await Runner.run(root, prompt)
        return str(result.final_output)
    finally:
        await hosted_model.close()


@mcp.tool()
async def primitive_info() -> dict[str, Any]:
    """Describe the subagent primitive, runtime mode, limits, and required configuration."""
    return {
        "name": "chatgpt-native-subagent-primitive",
        "version": SERVER_VERSION,
        "default_model": DEFAULT_MODEL,
        "openai_api_key_configured": bool(os.getenv("OPENAI_API_KEY")),
        "hosted_multi_agent_enabled": ENABLE_HOSTED,
        "hosted_multi_agent_import_available": OpenAIHostedMultiAgentModel is not None,
        "max_subagents": MAX_ALLOWED_SUBAGENTS,
        "tools": {
            "delegate": "Run one specialist subagent and return its result.",
            "swarm": (
                "Run multiple specialists and synthesize them. In auto mode it prefers OpenAI's "
                "experimental server-hosted multi-agent primitive and falls back to explicit "
                "parallel Agents SDK runs."
            ),
        },
    }


@mcp.tool()
async def delegate(
    task: str,
    role: str = "specialist",
    context: str = "",
    model: str = DEFAULT_MODEL,
) -> dict[str, Any]:
    """Delegate one bounded task to a specialist subagent and return the specialist's output."""
    _require_api_key()
    run_id = str(uuid.uuid4())
    started = time.perf_counter()
    result = await _run_one_specialist(
        role=role.strip() or "specialist",
        task=task,
        context=context,
        model=model,
        semaphore=asyncio.Semaphore(1),
    )
    return {
        "run_id": run_id,
        "mode": "single-agent-delegation",
        "model": model,
        "role": result["role"],
        "output": result["output"],
        "elapsed_seconds": round(time.perf_counter() - started, 3),
    }


@mcp.tool()
async def swarm(
    task: str,
    roles: list[str] | None = None,
    context: str = "",
    mode: Literal["auto", "hosted", "local"] = "auto",
    model: str = DEFAULT_MODEL,
    max_concurrency: int = 3,
) -> dict[str, Any]:
    """Run a coordinated subagent swarm and synthesize a single final answer.

    `mode='hosted'` uses OpenAI's experimental Responses hosted multi-agent primitive.
    `mode='local'` runs explicit Agents SDK specialists in parallel and then synthesizes them.
    `mode='auto'` prefers hosted and falls back to local if hosted is unavailable or errors.
    """
    _require_api_key()
    run_id = str(uuid.uuid4())
    started = time.perf_counter()
    normalized_roles = _clean_roles(roles)
    concurrency = max(1, min(int(max_concurrency), len(normalized_roles), MAX_ALLOWED_SUBAGENTS))

    hosted_error: str | None = None
    if mode == "hosted" and not ENABLE_HOSTED:
        raise RuntimeError("Hosted multi-agent mode is disabled by ENABLE_HOSTED_MULTI_AGENT=0.")

    if mode in {"auto", "hosted"} and ENABLE_HOSTED:
        try:
            output = await _run_hosted_swarm(
                task=task,
                roles=normalized_roles,
                context=context,
                model=model,
                max_concurrency=concurrency,
            )
            return {
                "run_id": run_id,
                "mode": "openai-hosted-multi-agent",
                "model": model,
                "roles_requested": normalized_roles,
                "max_concurrency": concurrency,
                "output": output,
                "elapsed_seconds": round(time.perf_counter() - started, 3),
            }
        except Exception as exc:
            hosted_error = f"{type(exc).__name__}: {exc}"
            if mode == "hosted":
                raise

    output, specialist_results = await _run_local_swarm(
        task=task,
        roles=normalized_roles,
        context=context,
        model=model,
        max_concurrency=concurrency,
    )
    response: dict[str, Any] = {
        "run_id": run_id,
        "mode": "parallel-agents-sdk-fallback",
        "model": model,
        "roles": normalized_roles,
        "max_concurrency": concurrency,
        "subagents": specialist_results,
        "output": output,
        "elapsed_seconds": round(time.perf_counter() - started, 3),
    }
    if hosted_error:
        response["hosted_fallback_reason"] = hosted_error
    return response


if __name__ == "__main__":
    port = int(os.getenv("PORT", "8000"))
    mcp.run(
        transport="streamable-http",
        host="0.0.0.0",
        port=port,
        streamable_http_path="/mcp",
        transport_security=_transport_security(),
    )

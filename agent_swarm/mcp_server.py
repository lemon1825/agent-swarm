"""Agent Swarm MCP Server — expose Agent Swarm as an MCP tool.

Connects Agent Swarm to Claude Desktop, Claude Code, Cursor, and any MCP-compatible client.

Usage:
    python -m agent_swarm.mcp_server

MCP Config (add to claude_desktop_config.json or mcp_config.json):
    {
        "mcpServers": {
            "agent-swarm": {
                "command": "python",
                "args": ["-m", "agent_swarm.mcp_server"],
                "env": {
                    "OPENAI_API_KEY": "sk-xxx"
                }
            }
        }
    }

Tools exposed:
    - swarm_run: Execute a multi-agent workflow
    - swarm_playbook: Run a built-in playbook
    - swarm_ontology: Query ontology terms and capabilities
    - swarm_skills: List active skills and fitness scores
    - swarm_status: Engine status and configuration
"""
import asyncio
import json
import sys
import os

# MCP protocol over stdio — zero-dep implementation
# Compatible with MCP spec without requiring the mcp package


class MCPServer:
    """Minimal MCP server over stdio. No external dependencies."""

    def __init__(self):
        self.tools = {}
        self._id_counter = 0

    def tool(self, name: str, description: str, input_schema: dict):
        """Register a tool."""
        def decorator(fn):
            self.tools[name] = {
                "function": fn,
                "description": description,
                "inputSchema": input_schema,
            }
            return fn
        return decorator

    async def handle_message(self, msg: dict) -> dict:
        method = msg.get("method", "")
        msg_id = msg.get("id")
        params = msg.get("params", {})

        if method == "initialize":
            return self._response(msg_id, {
                "protocolVersion": "2024-11-05",
                "capabilities": {"tools": {"listChanged": False}},
                "serverInfo": {"name": "agent-swarm", "version": "1.0.0"},
            })

        elif method == "tools/list":
            tools_list = []
            for name, tool in self.tools.items():
                tools_list.append({
                    "name": name,
                    "description": tool["description"],
                    "inputSchema": tool["inputSchema"],
                })
            return self._response(msg_id, {"tools": tools_list})

        elif method == "tools/call":
            tool_name = params.get("name", "")
            arguments = params.get("arguments", {})

            if tool_name not in self.tools:
                return self._error(msg_id, -32601, f"Unknown tool: {tool_name}")

            try:
                fn = self.tools[tool_name]["function"]
                result = await fn(arguments) if asyncio.iscoroutinefunction(fn) else fn(arguments)
                return self._response(msg_id, {
                    "content": [{"type": "text", "text": json.dumps(result, ensure_ascii=False, default=str)}],
                })
            except Exception as e:
                return self._response(msg_id, {
                    "content": [{"type": "text", "text": f"Error: {str(e)}"}],
                    "isError": True,
                })

        elif method == "notifications/initialized":
            return None  # No response needed for notifications

        else:
            return self._error(msg_id, -32601, f"Unknown method: {method}")

    def _response(self, msg_id, result):
        return {"jsonrpc": "2.0", "id": msg_id, "result": result}

    def _error(self, msg_id, code, message):
        return {"jsonrpc": "2.0", "id": msg_id, "error": {"code": code, "message": message}}

    async def run_stdio(self):
        """Run MCP server over stdin/stdout."""
        import sys
        reader = asyncio.StreamReader()
        protocol = asyncio.StreamReaderProtocol(reader)
        await asyncio.get_event_loop().connect_read_pipe(lambda: protocol, sys.stdin.buffer)

        w_transport, w_protocol = await asyncio.get_event_loop().connect_write_pipe(
            asyncio.streams.FlowControlMixin, sys.stdout.buffer)
        writer = asyncio.StreamWriter(w_transport, w_protocol, reader, asyncio.get_event_loop())

        while True:
            try:
                header = await reader.readline()
                if not header:
                    break
                header_str = header.decode().strip()
                if header_str.startswith("Content-Length:"):
                    content_length = int(header_str.split(":")[1].strip())
                    await reader.readline()  # empty line
                    body = await reader.readexactly(content_length)
                    msg = json.loads(body.decode())

                    response = await self.handle_message(msg)
                    if response:
                        response_bytes = json.dumps(response).encode()
                        out = f"Content-Length: {len(response_bytes)}\r\n\r\n".encode() + response_bytes
                        writer.write(out)
                        await writer.drain()
            except (asyncio.IncompleteReadError, ConnectionResetError):
                break
            except Exception as e:
                sys.stderr.write(f"MCP Error: {e}\n")
                sys.stderr.flush()


# ── Agent Swarm Tools ─────────────────────────────────────

server = MCPServer()

# Import engine
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from agent_swarm import (
    Swarm, SubTask, SkillBank, SkillGenetics, Skill,
    OntologyRegistry, CORE_ONTOLOGY, BUILTIN_PLAYBOOKS, SkillManifest,
)

# Shared state
_bank = SkillBank()
_genetics = SkillGenetics(_bank)

# Live visualization: lazy init — only connects when server actually runs
from agent_swarm.events import EventBus, HttpEventBridge
_event_bus = None
_http_bridge = None

def _get_event_bus():
    """Lazy-create event bus + HTTP bridge on first use."""
    global _event_bus, _http_bridge
    if _event_bus is None:
        _event_bus = EventBus()
        bridge_url = os.environ.get("AGENT_SWARM_BRIDGE_URL", "http://localhost:8000/events/push")
        _http_bridge = HttpEventBridge(bridge_url)
        _event_bus.on_all(_http_bridge.send)
    return _event_bus

# Default LLM — uses OpenAI if available, else echo
async def _get_llm():
    api_key = os.environ.get("OPENAI_API_KEY")
    if api_key:
        from openai import AsyncOpenAI
        client = AsyncOpenAI()
        async def llm(prompt, tools=None):
            r = await client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": prompt}],
                max_tokens=1000,
            )
            return r.choices[0].message.content
        return llm

    anthropic_key = os.environ.get("ANTHROPIC_API_KEY")
    if anthropic_key:
        from anthropic import AsyncAnthropic
        client = AsyncAnthropic()
        async def llm(prompt, tools=None):
            r = await client.messages.create(
                model="claude-haiku-4-5-20251001",
                max_tokens=1000,
                messages=[{"role": "user", "content": prompt}],
            )
            return r.content[0].text
        return llm

    # Fallback: echo
    async def llm(prompt, tools=None):
        return f"[No LLM configured] Received: {prompt[:200]}"
    return llm


@server.tool(
    name="swarm_run",
    description="Execute a multi-agent workflow. Agents run in parallel where possible.",
    input_schema={
        "type": "object",
        "properties": {
            "goal": {"type": "string", "description": "What you want the agents to accomplish"},
            "tasks": {
                "type": "array",
                "description": "List of tasks. Each task has id, description, role, and optional dependencies.",
                "items": {
                    "type": "object",
                    "properties": {
                        "id": {"type": "string"},
                        "description": {"type": "string"},
                        "role": {"type": "string"},
                        "dependencies": {"type": "array", "items": {"type": "string"}},
                    },
                    "required": ["id", "description", "role"],
                },
            },
        },
        "required": ["goal", "tasks"],
    },
)
async def swarm_run(args):
    llm = await _get_llm()
    swarm = Swarm(
        llm=llm,
        skill_bank=_bank,
        genetics=_genetics,
        ontology=OntologyRegistry([CORE_ONTOLOGY]),
        event_bus=_get_event_bus(),
    )
    tasks = [SubTask(
        id=t["id"], description=t["description"], role=t["role"],
        dependencies=t.get("dependencies", [])
    ) for t in args["tasks"]]

    result = await swarm.run(args["goal"], tasks=tasks)
    meta = result["metadata"]

    return {
        "final_output": result["final_output"],
        "succeeded": meta["succeeded"],
        "failed": meta["failed"],
        "total_tasks": meta["total_tasks"],
        "execution_time_s": meta["execution_time_s"],
        "task_results": {
            tid: {"role": tr.role, "success": tr.success, "output": str(tr.output)[:500]}
            for tid, tr in result["results"].items()
        },
    }


@server.tool(
    name="swarm_playbook",
    description="Run a built-in playbook: research, code_review, discover, strategy, write_prd, plan_launch, north_star, swarm_feature, swarm_bugfix, swarm_research",
    input_schema={
        "type": "object",
        "properties": {
            "goal": {"type": "string", "description": "What you want to accomplish"},
            "playbook": {"type": "string", "description": "Playbook name",
                         "enum": ["research", "code_review", "discover", "strategy",
                                  "write_prd", "plan_launch", "north_star",
                                  "swarm_feature", "swarm_bugfix", "swarm_research"]},
        },
        "required": ["goal", "playbook"],
    },
)
async def swarm_playbook(args):
    llm = await _get_llm()
    swarm = Swarm(llm=llm, skill_bank=_bank, genetics=_genetics, event_bus=_get_event_bus())
    result = await swarm.run(args["goal"], playbook=args["playbook"])
    meta = result["metadata"]
    return {
        "final_output": result["final_output"],
        "succeeded": meta["succeeded"],
        "total_tasks": meta["total_tasks"],
        "next_steps": meta.get("next_steps", []),
        "playbook_used": args["playbook"],
    }


@server.tool(
    name="swarm_ontology",
    description="Query the ontology: list terms, check capabilities, get role recommendations",
    input_schema={
        "type": "object",
        "properties": {
            "action": {"type": "string", "enum": ["list_terms", "recommend_role", "recommend_playbook", "check_capabilities"],
                       "description": "What to query"},
            "query": {"type": "string", "description": "Task description or goal text"},
        },
        "required": ["action"],
    },
)
async def swarm_ontology(args):
    reg = OntologyRegistry([CORE_ONTOLOGY])
    action = args["action"]
    query = args.get("query", "")

    if action == "list_terms":
        return {"terms": [{"id": t.id, "label": t.label, "kind": t.kind}
                          for t in reg._terms.values()]}

    elif action == "recommend_role":
        role = reg.recommend_role(query)
        return {"query": query, "recommended_role": role}

    elif action == "recommend_playbook":
        scored = reg.recommend_playbook(query, BUILTIN_PLAYBOOKS)
        return {"query": query, "recommendations": scored[:3]}

    elif action == "check_capabilities":
        term = reg.resolve_by_label(query)
        if not term:
            return {"query": query, "error": "Term not found"}
        caps = reg.task_requires(term.id)
        produces = reg.task_produces(term.id)
        return {"term": term.label, "requires": sorted(caps), "produces": sorted(produces)}

    return {"error": f"Unknown action: {action}"}


@server.tool(
    name="swarm_skills",
    description="List active skills with fitness scores, or view genetics effectiveness",
    input_schema={
        "type": "object",
        "properties": {
            "action": {"type": "string", "enum": ["list", "effectiveness"],
                       "description": "list = show all skills, effectiveness = genetics report"},
        },
        "required": ["action"],
    },
)
async def swarm_skills(args):
    if args["action"] == "list":
        skills = _bank._all()
        return {"skills": [
            {"name": s.name, "state": s.state.value if hasattr(s.state, 'value') else str(s.state),
             "fitness": s.fitness, "hit_count": s.hit_count, "helped": s.helped_count}
            for s in skills
        ], "total": len(skills)}

    elif args["action"] == "effectiveness":
        report = _genetics.effectiveness_report()
        return report

    return {"error": "Unknown action"}


@server.tool(
    name="swarm_status",
    description="Get Agent Swarm engine status and configuration",
    input_schema={"type": "object", "properties": {}},
)
async def swarm_status(args):
    has_openai = bool(os.environ.get("OPENAI_API_KEY"))
    has_anthropic = bool(os.environ.get("ANTHROPIC_API_KEY"))
    return {
        "version": "1.0.0",
        "skills_count": len(_bank._all()),
        "genetics_generation": _genetics.generation,
        "ontology_terms": len(OntologyRegistry([CORE_ONTOLOGY])._terms),
        "playbooks": list(BUILTIN_PLAYBOOKS.keys()),
        "llm_available": has_openai or has_anthropic,
        "llm_provider": "openai" if has_openai else ("anthropic" if has_anthropic else "none"),
    }


# ── MCP Setup Guide ──────────────────────────────────────

MCP_SETUP_GUIDE = """
# Agent Swarm MCP Setup

## Claude Desktop

Add to ~/Library/Application Support/Claude/claude_desktop_config.json:

{
    "mcpServers": {
        "agent-swarm": {
            "command": "python",
            "args": ["-m", "agent_swarm.mcp_server"],
            "env": {
                "OPENAI_API_KEY": "sk-your-key-here"
            }
        }
    }
}

## Claude Code

Add to your MCP config:

{
    "mcpServers": {
        "agent-swarm": {
            "command": "python",
            "args": ["-m", "agent_swarm.mcp_server"]
        }
    }
}

## Available Tools

- swarm_run: Execute multi-agent workflow with parallel tasks
- swarm_playbook: Run built-in playbook (research, code_review, etc.)
- swarm_ontology: Query ontology terms and get recommendations
- swarm_skills: View skills and genetics effectiveness
- swarm_status: Engine status and configuration

## Example Usage (in Claude)

"Use swarm_run to research AI trends with 3 agents: a researcher to find data,
an analyst to compare findings, and a writer to produce a summary."
"""


if __name__ == "__main__":
    if "--help" in sys.argv or "-h" in sys.argv:
        print(MCP_SETUP_GUIDE)
        sys.exit(0)

    if "--setup" in sys.argv:
        print(MCP_SETUP_GUIDE)
        sys.exit(0)

    # Run MCP server
    asyncio.run(server.run_stdio())

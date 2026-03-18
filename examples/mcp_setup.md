# Agent Swarm MCP Setup Guide

## What is MCP?

MCP (Model Context Protocol) lets AI tools like Claude Desktop and Claude Code call external tools. Agent Swarm's MCP server exposes the engine as 5 tools that any MCP-compatible client can use.

## Setup

### Claude Desktop (macOS)

1. Install Agent Swarm:
```bash
pip install agent-swarm-core
```

2. Edit `~/Library/Application Support/Claude/claude_desktop_config.json`:
```json
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
```

3. Restart Claude Desktop. You'll see "agent-swarm" in the tools list.

### Claude Code

```bash
# In your project directory
claude mcp add agent-swarm python -m agent_swarm.mcp_server
```

### Cursor / Windsurf / Other MCP Clients

Add to your MCP configuration:
```json
{
    "mcpServers": {
        "agent-swarm": {
            "command": "python",
            "args": ["-m", "agent_swarm.mcp_server"]
        }
    }
}
```

## Available Tools

| Tool | Description |
|---|---|
| `swarm_run` | Execute multi-agent workflow with parallel tasks, roles, and dependencies |
| `swarm_playbook` | Run built-in playbook (research, code_review, discover, strategy, write_prd, plan_launch, north_star) |
| `swarm_ontology` | Query ontology: list terms, recommend roles, check capabilities |
| `swarm_skills` | View active skills with fitness scores, or check genetics effectiveness |
| `swarm_status` | Engine version, skill count, available LLM |

## Example Prompts (in Claude)

**Research workflow:**
> "Use swarm_run to research AI agent trends. Create 3 tasks: a researcher to find top 5 frameworks, an analyst to compare them, and a writer to produce a recommendation."

**Playbook:**
> "Use swarm_playbook with the 'strategy' playbook to define positioning for an AI startup."

**Ontology query:**
> "Use swarm_ontology to recommend the best role for 'analyze customer churn data'."

**Check skills:**
> "Use swarm_skills to show the effectiveness report for genetics."

## LLM Configuration

Set one of these environment variables:
- `OPENAI_API_KEY` — uses GPT-4o-mini
- `ANTHROPIC_API_KEY` — uses Claude Haiku

If neither is set, the engine runs in echo mode (returns input without LLM processing).

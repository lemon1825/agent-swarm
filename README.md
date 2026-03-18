# Agent Swarm

**A lightweight, test-first agent workflow engine for research, review, and approval-heavy operations.**

Zero dependencies. 252 tests. Skills that evolve.

```python
from agent_swarm import Swarm, SubTask

result = await Swarm(llm=my_llm).run("Analyze competitors", tasks=[
    SubTask(id="research", description="Find top 5 competitors", role="Researcher"),
    SubTask(id="compare", description="Compare strengths", role="Analyst", dependencies=["research"]),
    SubTask(id="report", description="Write recommendation", role="Writer", dependencies=["compare"]),
])
```

```bash
pip install agent-swarm-core
```

---

## What problems does this solve?

**"I need agents that run in parallel, wait for approval, stay within budget, and get better over time."**

Agent Swarm is built for workflows where:
- Multiple agents research, analyze, and write **in parallel**
- Some tasks need **human approval** before continuing
- You need **budget caps** so LLM costs don't spiral
- Outputs must pass **schema validation** before delivery
- The engine **learns from every run** and gets better over time

### Real use cases

| Use case | What Agent Swarm does |
|---|---|
| **Competitor analysis** | 3 agents research in parallel → analyst compares → writer produces report → reviewer approves |
| **Code review pipeline** | Scanner finds issues → reviewer prioritizes → writer produces fix suggestions → lead approves |
| **Product discovery** | Researcher explores market → analyst identifies opportunities → strategist writes brief → PM approves |
| **Content production** | Researcher gathers sources → writer drafts → editor reviews → publisher approves final version |
| **Compliance review** | Analyst checks policy → reviewer verifies → approver signs off → report generated |

---

## Get started in 3 minutes

### 1. Install

```bash
pip install agent-swarm-core
```

No ChromaDB, no Neo4j, no torch, no LangChain. Just Python.

### 2. Connect your LLM

```python
# OpenAI
from openai import AsyncOpenAI
client = AsyncOpenAI()
async def llm(prompt, tools=None):
    r = await client.chat.completions.create(
        model="gpt-4o-mini", messages=[{"role":"user","content":prompt}], max_tokens=1000)
    return r.choices[0].message.content

# Claude
from anthropic import AsyncAnthropic
client = AsyncAnthropic()
async def llm(prompt, tools=None):
    r = await client.messages.create(
        model="claude-sonnet-4-20250514", max_tokens=1000,
        messages=[{"role":"user","content":prompt}])
    return r.content[0].text

# Any local model (Ollama, vLLM, llama.cpp)
async def llm(prompt, tools=None):
    return your_model.generate(prompt)
```

### 3. Run a workflow

```python
from agent_swarm import Swarm, SubTask

result = await Swarm(llm=llm).run(
    "Research AI agent market and recommend strategy",
    tasks=[
        SubTask(id="research", description="Find top 5 AI agent frameworks",
                role="Researcher"),
        SubTask(id="compare", description="Compare strengths and weaknesses",
                role="Analyst", dependencies=["research"]),
        SubTask(id="recommend", description="Write startup recommendation",
                role="Writer", dependencies=["compare"]),
    ]
)

print(result["final_output"])
```

### 4. Add approval gates

```python
async def slack_approval(task_id, description, role):
    # Post to Slack, wait for thumbs up
    return await ask_slack_channel(f"Approve '{description}' by {role}?")

result = await Swarm(llm=llm, approval_callback=slack_approval).run(
    "Produce quarterly report",
    tasks=[
        SubTask(id="draft", description="Write Q1 report draft", role="Writer"),
        SubTask(id="review", description="Review for accuracy", role="Reviewer",
                dependencies=["draft"]),
        SubTask(id="publish", description="Finalize and publish", role="Publisher",
                dependencies=["review"]),
    ]
)
# "review" and "publish" will wait for Slack approval before executing
```

### 5. Watch skills evolve

```python
from agent_swarm import Swarm, SkillGenetics, SkillBank

bank = SkillBank()
genetics = SkillGenetics(bank)
swarm = Swarm(llm=llm, skill_bank=bank, genetics=genetics)

# Run 10 times — the engine extracts skills from successes and failures
for i in range(10):
    result = await swarm.run("Research AI trends")

# Check if genetics is working
report = genetics.effectiveness_report()
print(f"Verdict: {report['verdict']}")  # "effective" / "emerging" / "inconclusive"
print(f"Fitness delta: {report['fitness']['delta']:+.3f}")
```

---

## Why not LangGraph / CrewAI / AutoGen?

| | Agent Swarm | LangGraph | CrewAI | AutoGen |
|---|---|---|---|---|
| Dependencies | **0** | 10+ | 10+ | 10+ |
| Install size | **< 1 MB** | ~500 MB | ~300 MB | ~200 MB |
| Lines of code | **2,457** | ~50,000+ | ~30,000+ | ~40,000+ |
| Skill evolution | **Crossover, adversarial, tournament** | No | No | No |
| Ontology routing | **SKOS-style, 3-mode gate** | No | No | No |
| Embed in your product | **Copy the folder** | Requires full stack | Requires full stack | Requires full stack |
| Human approval gates | **Built-in** | Manual | Limited | Manual |

**Use Agent Swarm when** you want a lightweight orchestrator embedded inside your product — not a platform.

**Use something else when** you need 300+ integrations (LangGraph), visual no-code building (CrewAI Studio), or enterprise distributed runtime (LangGraph Cloud).

---

## Skill Packs

Install domain-specific skills and ontology terms with one command.

```bash
# See available packs
python -m agent_swarm --packs

# Install a pack
python -m agent_swarm --add research-pack
python -m agent_swarm --add review-pack
python -m agent_swarm --add pm-pack

# View pack details
python -m agent_swarm --pack-info pm-pack

# Run with a pack
python -m agent_swarm --with-pack pm-pack "Define product strategy"
```

| Pack | Skills | What it adds |
|---|---|---|
| `research-pack` | 4 | Source verification, quantitative extraction, competitive landscape, synthesis |
| `review-pack` | 4 | Security scan, code quality, compliance check, fix suggestions |
| `pm-pack` | 5 | Market discovery, positioning, PRD writing, launch planning, north star |

Each pack includes skills + ontology terms + competency questions. Packs extend the core engine without changing it.

```python
from agent_swarm import Swarm, PackManager, OntologyRegistry, CORE_ONTOLOGY, SkillGenetics

pm = PackManager()
pm.install("research-pack")
bank, bundles = pm.apply()

swarm = Swarm(
    llm=my_llm,
    skill_bank=bank,
    genetics=SkillGenetics(bank),
    ontology=OntologyRegistry([CORE_ONTOLOGY] + bundles),
)
result = await swarm.run("Research AI market trends")
```

---

## MCP Integration

Connect Agent Swarm to Claude Desktop, Claude Code, Cursor, and any MCP-compatible tool.

```bash
python -m agent_swarm.mcp_server          # Start MCP server
python -m agent_swarm.mcp_server --setup  # Show setup guide
```

**Claude Desktop** — add to `claude_desktop_config.json`:
```json
{
    "mcpServers": {
        "agent-swarm": {
            "command": "python",
            "args": ["-m", "agent_swarm.mcp_server"],
            "env": {"OPENAI_API_KEY": "sk-your-key"}
        }
    }
}
```

**5 MCP tools:** `swarm_run` (execute workflow), `swarm_playbook` (run playbook), `swarm_ontology` (query terms), `swarm_skills` (view skills), `swarm_status` (engine info).

See [MCP Setup Guide](examples/mcp_setup.md) for full configuration.

---

## Features

### Parallel DAG Execution
Tasks run in topological waves. Maximum concurrency within each wave.

### Human Approval Gates
Any task can require approval. Rejected work stops cleanly. Audit trail included.

### Budget Control
Set `max_cost_per_run`. The engine tracks spending and blocks when exceeded.

### Skill Genetics
Skills mutate, crossover, face adversarial testing, compete in tournaments. Full lineage tracking.

### Ontology Routing
SKOS-style vocabulary controls what agents can do. 3 modes: SOFT (log), WARN (count), STRICT (block).

### Production Error Handling
7-class error classification. Rate limits → retry with jitter. Token exceeded → immediate fail. Auth errors → immediate fail.

### 7 Built-in Playbooks
`research`, `code_review`, `discover`, `strategy`, `write_prd`, `plan_launch`, `north_star`

### Schema Validation
Nested schemas, $ref composition, 5 domain presets, structured ValidationError objects.

### CLI
```bash
python -m agent_swarm "Research AI trends"
python -m agent_swarm --playbook discover "Explore new ideas"
python -m agent_swarm --playbooks
python -m agent_swarm --ontology
```

---

## Scenario Examples

See `examples/` for runnable scripts:

| Example | What it shows |
|---|---|
| `04_competitor_analysis.py` | 5-agent parallel research → analysis → report with budget cap |
| `05_approval_workflow.py` | 4-step content pipeline with human approval at review and publish |
| `06_code_review_pipeline.py` | Code scan → prioritize → fix suggestions → lead approval |
| `07_pack_pm_workflow.py` | PM discovery → positioning → PRD → launch with pm-pack |
| `with_openai.py` | Real OpenAI GPT-4 connection |
| `with_claude.py` | Real Anthropic Claude connection |
| `mcp_setup.md` | MCP setup for Claude Desktop, Claude Code, Cursor |

---

## Architecture

```
agent_swarm/
  core.py          817   ← Swarm engine, DAG executor, planner
  ontology.py      382   ← SKOS registry, 3-mode gate, recommendations
  genetics.py      330   ← Crossover, adversarial, tournament, fitness, lineage
  skills.py        312   ← SkillBank, 6-gate promotion, replay benchmark
  validation.py    217   ← Schema, $ref, 5 domain presets
  __main__.py       88   ← CLI
  models.py         86   ← Ticket, Budget, Org, Handoff
  metrics.py        83   ← Histogram (p50/p95/p99), Tracer
  playbooks.py      80   ← 7 playbooks with next_steps
  __init__.py       44
  session.py        18
```

2,457 lines. Zero dependencies. Python 3.10+.

---

## Testing

```bash
pytest tests/ -q                    # 129 tests
pytest tests/ -q -m ontology        # ontology tests
pytest tests/ -q -m genetics        # genetics tests
pytest tests/ -q -m core            # core engine tests
pytest tests/ -q -m policy          # policy tests
python test_agent_swarm.py           # 123 integration tests
```

---

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md).

---

## Agent Swarm Pro

For teams that need dashboards, persistent storage, approval UI, eval framework, and hosted execution — [learn more](https://agent-swarm.dev/pro).

The core engine is MIT-licensed and always will be.

## License

MIT

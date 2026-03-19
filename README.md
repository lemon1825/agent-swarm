<p align="center">
  <img src="https://img.shields.io/badge/dependencies-0-brightgreen?style=flat-square" alt="Zero Dependencies">
  <img src="https://img.shields.io/badge/size-%3C1MB-blue?style=flat-square" alt="Size">
  <img src="https://img.shields.io/badge/python-3.10%2B-blue?style=flat-square&logo=python&logoColor=white" alt="Python">
  <img src="https://img.shields.io/badge/license-MIT-green?style=flat-square" alt="MIT License">
  <img src="https://img.shields.io/badge/tests-121%20passed-success?style=flat-square" alt="Tests">
  <img src="https://img.shields.io/badge/LOC-9.1K-informational?style=flat-square" alt="Lines of Code">
</p>

<h1 align="center">Agent Swarm</h1>

<p align="center">
  <strong>The embeddable agent engine that learns.</strong><br>
  Zero-dependency AI agent orchestration with parallel DAG execution,<br>
  skill genetics, ontology routing, and human approval gates.
</p>

<p align="center">
  <a href="#get-started-in-3-minutes">Quick Start</a> &bull;
  <a href="#why-agent-swarm">Why Agent Swarm</a> &bull;
  <a href="#features">Features</a> &bull;
  <a href="#skill-packs">Skill Packs</a> &bull;
  <a href="#mcp-integration">MCP</a> &bull;
  <a href="#architecture">Architecture</a>
</p>

---

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
| **Competitor analysis** | 3 agents research in parallel -> analyst compares -> writer produces report -> reviewer approves |
| **Code review pipeline** | Scanner finds issues -> reviewer prioritizes -> writer produces fix suggestions -> lead approves |
| **Product discovery** | Researcher explores market -> analyst identifies opportunities -> strategist writes brief -> PM approves |
| **Content production** | Researcher gathers sources -> writer drafts -> editor reviews -> publisher approves final version |
| **Compliance review** | Analyst checks policy -> reviewer verifies -> approver signs off -> report generated |

---

## Why Agent Swarm?

<table>
<tr>
<td width="50%">

### vs. LangGraph / CrewAI / AutoGen

| | Agent Swarm | Others |
|---|:---:|:---:|
| **Dependencies** | **0** | 10+ |
| **Install size** | **< 1 MB** | 200-500 MB |
| **Lines of code** | **9.1K** | 30-50K+ |
| **Skill evolution** | **Yes** | No |
| **Ontology routing** | **Yes** | No |
| **Budget control** | **Built-in** | Manual |
| **Embed in product** | **Copy folder** | Full stack |

</td>
<td width="50%">

### When to use what

**Use Agent Swarm when** you want a lightweight orchestrator embedded inside your product — not a platform.

**Use something else when** you need 300+ integrations (LangGraph), visual no-code building (CrewAI Studio), or enterprise distributed runtime (LangGraph Cloud).

</td>
</tr>
</table>

---

## Get started in 3 minutes

### 1. Install

```bash
pip install agent-swarm-core
```

No ChromaDB, no Neo4j, no torch, no LangChain. Just Python.

### 2. Connect your LLM

<details>
<summary><strong>OpenAI</strong></summary>

```python
from openai import AsyncOpenAI
client = AsyncOpenAI()

async def llm(prompt, tools=None):
    r = await client.chat.completions.create(
        model="gpt-4o-mini", messages=[{"role":"user","content":prompt}], max_tokens=1000)
    return r.choices[0].message.content
```
</details>

<details>
<summary><strong>Claude (Anthropic)</strong></summary>

```python
from anthropic import AsyncAnthropic
client = AsyncAnthropic()

async def llm(prompt, tools=None):
    r = await client.messages.create(
        model="claude-sonnet-4-20250514", max_tokens=1000,
        messages=[{"role":"user","content":prompt}])
    return r.content[0].text
```
</details>

<details>
<summary><strong>Local models (Ollama, vLLM, llama.cpp)</strong></summary>

```python
async def llm(prompt, tools=None):
    return your_model.generate(prompt)
```
</details>

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
    return await ask_slack_channel(f"Approve '{description}' by {role}?")

result = await Swarm(llm=llm, approval_callback=slack_approval).run(
    "Produce quarterly report",
    tasks=[
        SubTask(id="draft", description="Write Q1 report draft", role="Writer"),
        SubTask(id="review", description="Review for accuracy", role="Reviewer",
                dependencies=["draft"], requires_approval=True),
        SubTask(id="publish", description="Finalize and publish", role="Publisher",
                dependencies=["review"], requires_approval=True),
    ]
)
```

### 5. Watch skills evolve

```python
from agent_swarm import Swarm, SkillGenetics, SkillBank

bank = SkillBank()
genetics = SkillGenetics(bank)
swarm = Swarm(llm=llm, skill_bank=bank, genetics=genetics)

# Run 10 times -- the engine extracts skills from successes and failures
for i in range(10):
    result = await swarm.run("Research AI trends")

report = genetics.effectiveness_report()
print(f"Verdict: {report['verdict']}")       # "effective" / "emerging"
print(f"Fitness delta: {report['fitness']['delta']:+.3f}")
```

---

## Features

<table>
<tr>
<td width="33%">

### Parallel DAG Execution
Tasks run in topological waves with maximum concurrency. Attention Residuals pattern enables selective context access across waves.

### Human Approval Gates
Any task can require approval. Rejected work stops cleanly. Full audit trail.

### Budget Control
Set `max_cost_per_run`. The engine tracks real token usage and blocks when exceeded.

</td>
<td width="33%">

### Skill Genetics
Skills mutate, crossover, face adversarial testing, compete in tournaments. Full lineage tracking across generations.

### Ontology Routing
SKOS-style vocabulary controls agent capabilities. 3 modes: SOFT (log), WARN (count), STRICT (block).

### Schema Validation
Nested JSON schemas, `$ref` composition, cross-field rules, 5 domain presets, structured error objects.

</td>
<td width="33%">

### Security Hardened
SSRF protection, command blocklist, path traversal prevention, HMAC webhook auth, prompt injection defense.

### 7 Built-in Playbooks
`research`, `code_review`, `discover`, `strategy`, `write_prd`, `plan_launch`, `north_star`

### MCP + CLI
Connect to Claude Desktop, Cursor, or any MCP client. Full CLI for quick runs.

</td>
</tr>
</table>

---

## Skill Packs

Install domain-specific skills and ontology terms with one command.

```bash
python -m agent_swarm --packs                              # List packs
python -m agent_swarm --add research-pack                  # Install
python -m agent_swarm --with-pack pm-pack "Define strategy"  # Run with pack
```

| Pack | Skills | What it adds |
|---|---|---|
| `research-pack` | 4 | Source verification, quantitative extraction, competitive landscape, synthesis |
| `review-pack` | 4 | Security scan, code quality, compliance check, fix suggestions |
| `pm-pack` | 5 | Market discovery, positioning, PRD writing, launch planning, north star |

<details>
<summary><strong>Programmatic usage</strong></summary>

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
</details>

---

## MCP Integration

Connect Agent Swarm to Claude Desktop, Claude Code, Cursor, and any MCP-compatible tool.

```bash
python -m agent_swarm.mcp_server          # Start MCP server
python -m agent_swarm.mcp_server --setup  # Show setup guide
```

<details>
<summary><strong>Claude Desktop config</strong></summary>

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
</details>

**5 MCP tools:** `swarm_run` | `swarm_playbook` | `swarm_ontology` | `swarm_skills` | `swarm_status`

---

## Architecture

```
                    CLI (__main__.py)     MCP Server (mcp_server.py)
                           |                       |
                    +------+-----------------------+------+
                    |          Swarm Orchestrator          |
                    |            (core.py)                 |
                    +--+--------+--------+--------+-------+
                       |        |        |        |
              +--------+   +---+---+  +-+------+ +--------+
              | Skills |   |Ontology|  |Genetics| |Run     |
              | Bank   |   |Registry|  |Engine  | |Machine |
              +--------+   +-------+  +--------+ +--------+
                       |        |        |        |
                    +--+--------+--------+--------+-------+
                    |        Infrastructure Layer          |
                    | Cache | Memory | Tracing | Durable   |
                    +-------------------------------------+
```

<details>
<summary><strong>Full module breakdown (35 modules, 9.1K LOC)</strong></summary>

| Module | Lines | Purpose |
|---|---:|---|
| `core.py` | 1,163 | Swarm engine, DAG executor, Attention Residuals |
| `run_machine.py` | 525 | State machine runner, proof bundles |
| `mcp_server.py` | 439 | MCP protocol server (zero deps) |
| `ontology.py` | 416 | SKOS registry, 3-mode gate |
| `skills.py` | 371 | SkillBank, 6-gate promotion |
| `tools.py` | 360 | 6 built-in tools, security hardened |
| `genetics.py` | 330 | Crossover, adversarial, tournament |
| `tracing.py` | 296 | Distributed execution tracing |
| `tracker.py` | 295 | Webhook triggers, HMAC auth |
| `validation.py` | 217 | Schema, `$ref`, cross-field rules |
| `...` | | 25 more modules |

</details>

---

## Testing

```bash
pytest tests/ -q          # 121 tests (4 known failures in run_machine)
```

---

## Examples

See `examples/` for runnable scripts:

| Example | What it shows |
|---|---|
| `04_competitor_analysis.py` | 5-agent parallel research with budget cap |
| `05_approval_workflow.py` | Content pipeline with human approval |
| `06_code_review_pipeline.py` | Code scan -> prioritize -> fix suggestions |
| `07_pack_pm_workflow.py` | PM discovery -> PRD -> launch with pm-pack |
| `with_openai.py` | Real OpenAI GPT-4 connection |
| `with_claude.py` | Real Anthropic Claude connection |

---

## Agent Swarm Pro

For teams that need dashboards, persistent storage, approval UI, eval framework, and hosted execution.

The core engine is MIT-licensed and always will be.

---

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md).

## License

MIT

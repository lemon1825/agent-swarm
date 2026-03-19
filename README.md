# Agent Swarm

**A lightweight, test-first agent workflow engine for research, review, and approval-heavy operations.**

Zero dependencies. Security-hardened. Skills that evolve.

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
| Lines of code | **8,691** | ~50,000+ | ~30,000+ | ~40,000+ |
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

### Security Hardening
- **Command Injection 방지**: `shell=True` 제거, `shlex.split()` 기반 안전한 프로세스 실행
- **Path Traversal 방지**: workspace 파일 접근 시 `os.path.realpath` 검증으로 디렉터리 탈출 차단
- **Webhook 서버 로컬 바인딩**: tracker webhook이 `127.0.0.1`에만 바인딩 (외부 노출 방지)

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
  core.py          971   ← Swarm engine, DAG executor, planner
  run_machine.py   569   ← State machine runner (재귀→while 루프)
  mcp_server.py    438   ← MCP protocol server
  ontology.py      382   ← SKOS registry, 3-mode gate, recommendations
  migrate.py       352   ← Schema migration engine
  pro_client.py    350   ← Pro API client
  genetics.py      334   ← Crossover, adversarial, tournament, fitness, lineage, generation property
  context_diversity.py 329 ← Context diversity scoring
  skills.py        312   ← SkillBank, 6-gate promotion, replay benchmark
  tools.py         311   ← Tool registry (shlex.split 기반 안전한 실행)
  tracing.py       296   ← Distributed tracing
  skill_eval.py    281   ← Skill evaluation (속성명/enum 수정 완료)
  tracker.py       279   ← Webhook tracker (127.0.0.1 바인딩)
  vllm_presets.py  268   ← vLLM preset configurations
  __main__.py      246   ← CLI
  memory.py        232   ← Agent memory
  result_export.py 229   ← Result export (JSON, CSV)
  supervisor.py    220   ← Supervisor agent
  packs.py         218   ← Skill pack manager
  validation.py    217   ← Schema, $ref, 5 domain presets
  llm_connectors.py 213  ← LLM connectors (get_running_loop 전환)
  progress.py      206   ← Progress reporting
  events.py        192   ← Event system (ThreadPoolExecutor)
  workspace.py     189   ← Workspace (path traversal 방지)
  streaming.py     171   ← SSE streaming
  auto_tools.py    165   ← Auto-tool binding (변수 초기화 수정)
  durable.py       139   ← Durable execution
  playbooks.py     111   ← 7 playbooks with next_steps
  cache.py         110   ← Response cache
  router.py        107   ← Task router
  models.py         87   ← Ticket, Budget, Org, Handoff
  metrics.py        83   ← Histogram (p50/p95/p99), Tracer
  __init__.py       66
  session.py        18
```

8,691 lines. Zero dependencies. Python 3.10+.

---

## Testing

```bash
pytest tests/ -q                    # pytest tests
pytest tests/ -q -m ontology        # ontology tests
pytest tests/ -q -m genetics        # genetics tests
pytest tests/ -q -m core            # core engine tests
pytest tests/ -q -m policy          # policy tests
python test_agent_swarm.py           # smoke test
```

---

## Recent Changes

### Security Hardening
- `shell=True` 제거 → `shlex.split()` 사용 (Command Injection 방지)
- workspace path traversal 방지 (`os.path.realpath` 검증)
- tracker.py webhook 서버 `127.0.0.1` 바인딩 (외부 접근 차단)

### Code Quality
- events.py: `ThreadPoolExecutor` 도입으로 blocking I/O 안전 처리
- llm_connectors.py: deprecated `asyncio.get_event_loop()` → `get_running_loop()` 전환
- genetics.py: `generation` property 추가, lineage 추적 강화
- 데드코드 제거 및 미사용 import 정리

### Bug Fixes
- skill_eval.py: 속성명 및 enum 값 수정
- migrate.py: 속성명 수정
- auto_tools.py: 변수 초기화 누락 수정
- run_machine.py: 재귀 호출 → `while` 루프 전환 (RecursionError 방지)

---

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md).

---

## Agent Swarm Pro

For teams that need dashboards, persistent storage, approval UI, eval framework, and hosted execution — [learn more](https://agent-swarm.dev/pro).

The core engine is MIT-licensed and always will be.

## License

MIT

# Release Checklist

Run **every item** before each release. No exceptions.

## 1. Import
```bash
python3 -c "import agent_swarm; print(agent_swarm.__version__)"
```
- [ ] No ImportError, version matches pyproject.toml

## 2. Tests
```bash
python3 -m pytest tests/ -q
python3 test_agent_swarm.py
python3 scripts/check_harness.py
```
- [ ] pytest 129+ passed, 0 failed
- [ ] integration 123/123 passed
- [ ] harness PASS

## 3. Examples
```bash
python3 examples/01_basic.py
python3 examples/04_competitor_analysis.py
python3 examples/05_approval_workflow.py
```
- [ ] All exit 0

## 4. CLI
```bash
python3 -m agent_swarm --version    # 1.0.0
python3 -m agent_swarm --playbooks  # 10 playbooks
python3 -m agent_swarm --packs      # 3 packs
python3 -m agent_swarm --ontology   # 12 terms
```

## 5. Core → Pro Integration
```bash
pip install -e .
python3 -c "from agent_swarm_pro import PersistentStore, validate_license"
```

## 6. Symphony Pipeline
```bash
python3 -c "
import asyncio,tempfile,shutil
from agent_swarm import Swarm,RunMachine,TrackerAdapter,Supervisor,SupervisorConfig
async def llm(p,t=None): return 'ok'
async def main():
    tmp=tempfile.mkdtemp();m=RunMachine(persist_dir=tmp);t=TrackerAdapter(m)
    rid=t.handle_webhook({'goal':'check'});s=Supervisor(SupervisorConfig(max_concurrent=1))
    await s.execute_one(rid,Swarm(llm=llm),m);print(m.get(rid).state.value);shutil.rmtree(tmp)
asyncio.run(main())"
```
- [ ] Prints "completed"

## 7. README Accuracy
- [ ] Test count matches actual
- [ ] No broken commands

## 8. Package Metadata
- [ ] pyproject.toml version == __version__
- [ ] name = "agent-swarm-core"

## 9. Clean Build
```bash
python3 -m build && ls dist/
```

## 10. Final
- [ ] Git tag matches version
- [ ] All above checked

---

**One-liner:**
```bash
python3 -c "import agent_swarm;print(agent_swarm.__version__)" && python3 -m pytest tests/ -q --tb=no && python3 test_agent_swarm.py 2>&1|tail -1 && python3 scripts/check_harness.py 2>&1|tail -1 && python3 examples/01_basic.py>/dev/null && echo "RELEASE READY"
```

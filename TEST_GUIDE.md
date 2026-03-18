# Agent Swarm 사용자 테스트 시나리오

각 테스트를 순서대로 실행하세요.
"예상 결과"와 다르면 문제가 있는 것입니다.

---

## 준비

```bash
unzip agent-swarm-1.0.0.zip
unzip agent-swarm-pro-1.0.0.zip
cd agent-swarm
pip install -e .
python -m agent_swarm --version
```

예상:
```
agent-swarm 1.0.0
```

---

# Part A: Free 사용자 (로컬, 코드로 실행)

---

## A-1. 첫 실행

```bash
python examples/01_basic.py
```

예상:
```
=== Output ===
[Researcher] Found 3 key competitors: AlphaAI...
[Analyst] AlphaAI leads in enterprise...
[Writer] Executive Summary: The AI market has 3 main players...

=== Stats ===
Tasks: 3/3 succeeded
Time: 0.001s
Waves: 3
```

확인:
- [ ] 3/3 succeeded
- [ ] 에러 없음

---

## A-2. 직접 코드 작성

`test_manual.py` 파일 만들기:

```python
import asyncio
from agent_swarm import Swarm, SubTask

async def my_llm(prompt, tools=None):
    if "조사" in prompt or "Research" in prompt:
        return "한국 AI 시장은 2026년 기준 약 3조원 규모입니다."
    if "분석" in prompt or "Analy" in prompt:
        return "주요 플레이어: 네이버, 카카오, SK텔레콤"
    if "보고서" in prompt or "Write" in prompt:
        return "결론: B2B SaaS 영역에 기회가 있습니다."
    return "처리 완료"

async def main():
    result = await Swarm(llm=my_llm).run(
        goal="한국 AI 시장 분석",
        tasks=[
            SubTask(id="조사", description="시장 규모 조사", role="Researcher"),
            SubTask(id="분석", description="플레이어 분석", role="Analyst", dependencies=["조사"]),
            SubTask(id="보고서", description="보고서 작성", role="Writer", dependencies=["분석"]),
        ]
    )
    for task_id, r in result["results"].items():
        print(f"[{task_id}] {'성공' if r.success else '실패'}: {r.output}")
    print(f"\n{result['metadata']['succeeded']}/{result['metadata']['total_tasks']} 성공")

asyncio.run(main())
```

```bash
python test_manual.py
```

예상:
```
[조사] 성공: 한국 AI 시장은 2026년 기준 약 3조원 규모입니다.
[분석] 성공: 주요 플레이어: 네이버, 카카오, SK텔레콤
[보고서] 성공: 결론: B2B SaaS 영역에 기회가 있습니다.

3/3 성공
```

확인:
- [ ] 3/3 성공
- [ ] 한글 깨지지 않음
- [ ] 순서: 조사 → 분석 → 보고서

---

## A-3. 병렬 실행 확인

`test_parallel.py` 파일:

```python
import asyncio, time
from agent_swarm import Swarm, SubTask

async def slow_llm(prompt, tools=None):
    await asyncio.sleep(0.5)
    return "완료"

async def main():
    start = time.time()
    result = await Swarm(llm=slow_llm).run(
        goal="병렬 테스트",
        tasks=[
            SubTask(id="a", description="A팀", role="Researcher"),
            SubTask(id="b", description="B팀", role="Researcher"),
            SubTask(id="c", description="C팀", role="Researcher"),
            SubTask(id="report", description="종합", role="Writer",
                    dependencies=["a", "b", "c"]),
        ]
    )
    elapsed = time.time() - start
    meta = result["metadata"]
    print(f"{meta['succeeded']}/{meta['total_tasks']} 성공")
    print(f"웨이브: {meta['waves']}")
    print(f"시간: {elapsed:.1f}초")
    print("✓ 병렬 확인" if elapsed < 1.5 else "✗ 병렬 안 됨")

asyncio.run(main())
```

```bash
python test_parallel.py
```

예상:
```
4/4 성공
웨이브: 2
시간: 1.0초
✓ 병렬 확인
```

확인:
- [ ] 웨이브 2 (a,b,c 동시 → report)
- [ ] 시간 1.5초 미만 (순차면 2초+)

---

## A-4. 실패 복구

`test_retry.py` 파일:

```python
import asyncio
from agent_swarm import Swarm, SubTask, AgentConfig

call_count = 0

async def flaky_llm(prompt, tools=None):
    global call_count
    call_count += 1
    if call_count <= 2:
        raise Exception("Rate limit exceeded (429)")
    return "3번째 시도에서 성공"

async def main():
    result = await Swarm(
        llm=flaky_llm,
        configs={"default": AgentConfig(timeout=30, retries=5)}
    ).run("test", tasks=[SubTask(id="t", description="불안정 API", role="Worker")])

    r = result["results"]["t"]
    print(f"성공: {r.success}")
    print(f"시도: {r.attempts}회")
    print(f"결과: {r.output}")

asyncio.run(main())
```

```bash
python test_retry.py
```

예상:
```
성공: True
시도: 3회
결과: 3번째 시도에서 성공
```

확인:
- [ ] 2번 실패 후 3번째 성공
- [ ] 엔진이 크래시하지 않음

---

## A-5. 메모리

`test_memory.py` 파일:

```python
from agent_swarm import MemoryStore
import tempfile, shutil

tmp = tempfile.mkdtemp()
mem = MemoryStore(tmp)

mem.add("long", "FastAPI PostgreSQL architecture", tags=["backend"])
mem.add("entity", "Naver: Korean AI market leader", entity="Naver")
mem.add("context", "Check JWT expiry before refresh", skill="Auth")

# 키워드 검색
results = mem.search("backend architecture")
print(f"검색: {len(results)}개")
for r in results:
    print(f"  [{r.type}] {r.content}")

# 엔티티 검색
naver = mem.get_entity("Naver")
print(f"엔티티: {len(naver)}개")

# 통계
s = mem.stats()
print(f"전체: {s['total']}개, 엔티티: {s['entities']}개")

shutil.rmtree(tmp)
```

```bash
python test_memory.py
```

예상:
```
검색: 1개
  [long] FastAPI PostgreSQL architecture
엔티티: 1개
전체: 3개, 엔티티: 1개
```

확인:
- [ ] 검색 결과 나옴
- [ ] 엔티티 검색 동작

---

## A-6. 도구

`test_tools.py` 파일:

```python
from agent_swarm.tools import json_parse, file_read, file_write
import tempfile, os

# JSON 파싱
print(json_parse(data='{"user":{"name":"Alice","age":30}}', query="user.name"))
print(json_parse(data='{"items":["a","b","c"]}', query="items.1"))

# 파일 쓰기/읽기
tmp = os.path.join(tempfile.mkdtemp(), "test.txt")
file_write(path=tmp, content="Agent Swarm test file")
print(file_read(path=tmp))
os.unlink(tmp)
```

```bash
python test_tools.py
```

예상:
```
Alice
b
Agent Swarm test file
```

---

## A-7. Export (Pro 전환 준비)

```bash
python -m agent_swarm export --output my_workspace.json
```

예상:
```
Exported to: my_workspace.json
Workspace Bundle v1.0.0
  Skills: 0
  Memories: ...

Next steps:
  1. Go to agentswarm.dev
  2. Upgrade to Pro ($49/mo)
  3. Click 'Import Workspace'
  4. Upload my_workspace.json
```

확인:
- [ ] JSON 파일 생성됨
- [ ] Next steps 안내 나옴

파일 확인 후 삭제:
```bash
python -m json.tool my_workspace.json | head -5
rm my_workspace.json
```

---

## A-8. 자동 테스트 431개

```bash
python -m pytest tests/ -q
python test_agent_swarm.py
python test_scenario_free.py
python test_scenario_pro.py
python test_scenario_failures.py
```

예상:
```
129 passed
TOTAL: 123/123 passed, 0 failed
Passed: 54/54  Verdict: ALL PASSED ✓
Passed: 58/58  Verdict: ALL PASSED ✓
Passed: 67/67  Verdict: ALL PASSED ✓
```

확인:
- [ ] 5개 전부 0 failed

---

# Part B: Pro 사용자 (서버 + 대시보드)

---

## B-1. Pro 서버 시작

```bash
cd ../agent-swarm-pro
pip install fastapi uvicorn
pip install -e ../agent-swarm/
pip install -e .
python -m agent_swarm_pro.hosted
```

예상:
```
Agent Swarm Hosted MVP starting on port 8000
Dashboard: http://localhost:8000
API docs:  http://localhost:8000/docs
```

확인:
- [ ] 에러 없이 시작
- [ ] 브라우저에서 http://localhost:8000 열림
- [ ] http://localhost:8000/docs 에서 Swagger 보임

서버는 켜 둔 채로 새 터미널을 엽니다.

---

## B-2. API 키 발급

새 터미널에서:

```bash
curl -s -X POST "http://localhost:8000/api/keys?user_id=mytest&plan=pro" | python -m json.tool
```

예상:
```json
{
    "api_key": "ask_xxxxxxxxxxxx...",
    "user_id": "mytest",
    "plan": "pro",
    "note": "Save this key — it won't be shown again."
}
```

**api_key 값을 복사하세요.** 아래에서 계속 사용합니다.

확인:
- [ ] ask_로 시작하는 키 발급됨

---

## B-3. 대시보드 사용

1. 브라우저에서 http://localhost:8000 열기
2. API key 입력 팝업에 B-2에서 받은 키 붙여넣기
3. "Analyze AI market trends" 입력
4. "Submit Run" 클릭

확인:
- [ ] 대시보드 UI가 보임
- [ ] Run이 제출됨
- [ ] 상태가 queued → completed로 변함

---

## B-4. REST API 사용

api_key를 바꿔서 실행하세요:

```bash
# Run 제출
curl -s -X POST http://localhost:8000/api/runs \
  -H "Authorization: Bearer 여기에_키" \
  -H "Content-Type: application/json" \
  -d '{"goal":"Analyze competitor pricing"}' | python -m json.tool

# Run 목록
curl -s -H "Authorization: Bearer 여기에_키" \
  http://localhost:8000/api/runs | python -m json.tool

# 빌링 확인
curl -s -H "Authorization: Bearer 여기에_키" \
  http://localhost:8000/api/billing | python -m json.tool

# 서버 상태
curl -s http://localhost:8000/api/health | python -m json.tool
```

확인:
- [ ] Run 제출 시 run_id 반환
- [ ] Run 목록에 제출한 것 보임
- [ ] Billing에 plan: pro 표시

---

## B-5. Proof Bundle 확인

B-4에서 받은 run_id로:

```bash
curl -s -H "Authorization: Bearer 여기에_키" \
  http://localhost:8000/api/runs/여기에_run_id/proof | python -m json.tool
```

예상: tasks_completed, tokens, cost, trigger, state_history 포함된 JSON

확인:
- [ ] proof 데이터가 나옴
- [ ] state_history에 상태 전환 기록 있음

---

# Part C: Pro SDK (로컬 코드에서 서버 호출)

서버가 켜져 있는 상태에서 실행합니다.

---

## C-1. SDK 기본 사용

`test_sdk.py` 파일 (api_key를 바꾸세요):

```python
from agent_swarm.pro_client import ProClient

client = ProClient(
    api_key="여기에_B2에서_받은_키",
    server="http://localhost:8000"
)

# 서버 상태
print("1. Health:")
print(f"   {client.health()}")

# 빌링
print("\n2. Billing:")
b = client.billing()
print(f"   Plan: {b['plan']}, Runs: {b['runs_this_month']}/{b['limits']['runs_per_month']}")

# Run 제출
print("\n3. Submit run:")
run = client.submit("Analyze AI agent framework market")
print(f"   Run ID: {run['run_id']}")
print(f"   State: {run['state']}")

# 완료 대기
print("\n4. Waiting for completion...")
import time; time.sleep(2)
result = client.get_run(run["run_id"])
print(f"   State: {result['state']}")

# Proof
print("\n5. Proof bundle:")
proof = client.proof(run["run_id"])
print(f"   Tasks completed: {len(proof.get('tasks_completed', []))}")
print(f"   Trigger: {proof.get('trigger')}")
```

```bash
cd ../agent-swarm
python test_sdk.py
```

예상:
```
1. Health:
   {'status': 'ok', 'version': '1.0.0', ...}

2. Billing:
   Plan: pro, Runs: 0/500

3. Submit run:
   Run ID: run_xxxxxxxx
   State: queued

4. Waiting for completion...
   State: completed

5. Proof bundle:
   Tasks completed: 1
   Trigger: api
```

확인:
- [ ] 서버 연결 됨
- [ ] Run 제출 + 완료
- [ ] Proof 확인 가능

---

## C-2. SDK 전체 기능

`test_sdk_full.py` 파일 (api_key를 바꾸세요):

```python
from agent_swarm.pro_client import ProClient, ProClientError
import json, tempfile, os

client = ProClient(
    api_key="여기에_B2에서_받은_키",
    server="http://localhost:8000"
)

# 1. Run 제출 + 대기
print("1. Run 제출:")
run = client.submit("Research top 3 AI frameworks", priority=2)
print(f"   {run['run_id']}")

import time; time.sleep(2)

# 2. 상태 확인
print("\n2. 상태:")
r = client.get_run(run["run_id"])
print(f"   {r['state']}")

# 3. Run 목록
print("\n3. 내 Run 목록:")
runs = client.list_runs()
print(f"   {len(runs)}개")

# 4. Proof
print("\n4. Proof:")
proof = client.proof(run["run_id"])
print(f"   Tasks: {len(proof.get('tasks_completed',[]))} completed")

# 5. Approvals
print("\n5. 대기 중 승인:")
approvals = client.pending_approvals()
print(f"   {len(approvals)}개")

# 6. Plans
print("\n6. 가격표:")
plans = client.plans()
for name, info in plans["plans"].items():
    print(f"   {name}: ${info['price']}/mo, {info['runs_per_month']} runs")

# 7. Import
print("\n7. Workspace import:")
ws = {"version":"1.0.0","exported_at":0,"source":"local",
      "skills":[],"skill_genetics":[],"custom_ontology_terms":[],
      "memories":[{"id":"m1","type":"long","content":"SDK test memory",
                  "tags":["test"],"entity":"","skill":"","run_id":0,
                  "timestamp":0,"access_count":0,"relevance_score":0}],
      "recent_runs":[],"settings":{},"installed_packs":[],
      "total_runs":0,"total_tokens":0,"total_skills_evolved":0}
tmp = os.path.join(tempfile.mkdtemp(), "ws.json")
with open(tmp, "w") as f: json.dump(ws, f)
result = client.import_workspace(tmp)
print(f"   {result['message']}")
os.unlink(tmp)

# 8. Webhook
print("\n8. Webhook으로 Run 생성:")
wh = client.send_webhook({"goal": "Webhook test from SDK"})
print(f"   Status: {wh['status']}, Run: {wh.get('run_id')}")

# 9. Keys
print("\n9. 내 API 키:")
keys = client.list_keys()
print(f"   {len(keys)}개")

# 10. 잘못된 키 테스트
print("\n10. 잘못된 키:")
bad = ProClient(api_key="ask_wrong_key", server="http://localhost:8000")
try:
    bad.billing()
    print("   ERROR: 통과하면 안 됨")
except ProClientError as e:
    print(f"   정상 차단: {e}")

print("\n✅ SDK 전체 기능 확인 완료")
```

```bash
python test_sdk_full.py
```

예상:
```
1. Run 제출:
   run_xxxxxxxx
2. 상태:
   completed
3. 내 Run 목록:
   2개
4. Proof:
   Tasks: 1 completed
5. 대기 중 승인:
   0개
6. 가격표:
   free: $0/mo, 50 runs
   pro: $49/mo, 500 runs
   team: $249/mo, 5000 runs
   enterprise: $-1/mo, -1 runs
7. Workspace import:
   Imported 0 skills, 1 memories, 0 runs
8. Webhook으로 Run 생성:
   Status: triggered, Run: run_xxxxxxxx
9. 내 API 키:
   1개
10. 잘못된 키:
   정상 차단: [401] Unauthorized — Invalid or missing API key

✅ SDK 전체 기능 확인 완료
```

확인:
- [ ] 10개 전부 예상대로 동작
- [ ] 잘못된 키 정상 차단

---

## C-3. Free에서 Pro 전환 시뮬레이션

`test_migration.py` 파일 (api_key를 바꾸세요):

```python
from agent_swarm import Swarm, SubTask, MemoryStore, WorkspaceExporter
from agent_swarm.pro_client import ProClient, ProClientError
import asyncio, tempfile, shutil, json, os

# === Phase 1: 로컬에서 Free 사용 ===
print("=== Phase 1: 로컬 Free 사용 ===")

# 메모리 축적
tmp = tempfile.mkdtemp()
mem = MemoryStore(os.path.join(tmp, "memory"))
mem.add("long", "Project uses FastAPI backend", tags=["architecture"])
mem.add("entity", "CompanyX is an AI startup", entity="CompanyX")
mem.add("context", "Always check token expiry before refresh", skill="Auth")
print(f"메모리 {len(mem.all())}개 축적")

# 로컬 run
async def local_llm(p, t=None): return "Local analysis done"
result = asyncio.run(Swarm(llm=local_llm).run("test", tasks=[
    SubTask(id="t1", description="Local task", role="Worker")
]))
print(f"로컬 run: {result['metadata']['succeeded']}/{result['metadata']['total_tasks']} 성공")

# === Phase 2: Export ===
print("\n=== Phase 2: Export ===")
exporter = WorkspaceExporter(data_dir=tmp)
export_path = os.path.join(tmp, "my_workspace.json")
bundle = exporter.export(export_path)
print(f"Export: {os.path.getsize(export_path)} bytes")
print(f"  Memories: {len(bundle.memories)}개")

# === Phase 3: Pro 서버에 Import ===
print("\n=== Phase 3: Pro Import ===")
client = ProClient(
    api_key="여기에_B2에서_받은_키",
    server="http://localhost:8000"
)

# Import
result = client.import_workspace(export_path)
print(f"Import: {result['message']}")

# Workspace 확인
ws = client.workspace_status()
print(f"서버 데이터: {ws['has_data']}")

# === Phase 4: Pro에서 실행 ===
print("\n=== Phase 4: Pro 서버에서 Run ===")
run = client.submit("Continue analysis with imported data")
import time; time.sleep(2)
r = client.get_run(run["run_id"])
print(f"Run: {r['state']}")

proof = client.proof(run["run_id"])
print(f"Proof: {len(proof.get('tasks_completed',[]))} tasks")

shutil.rmtree(tmp)
print("\n✅ Free → Pro 전환 완료")
```

```bash
python test_migration.py
```

예상:
```
=== Phase 1: 로컬 Free 사용 ===
메모리 3개 축적
로컬 run: 1/1 성공

=== Phase 2: Export ===
Export: xxxx bytes
  Memories: 3개

=== Phase 3: Pro Import ===
Import: Imported 0 skills, 3 memories, 0 runs
서버 데이터: True

=== Phase 4: Pro 서버에서 Run ===
Run: completed
Proof: 1 tasks

✅ Free → Pro 전환 완료
```

확인:
- [ ] 로컬 데이터 축적됨
- [ ] Export 파일 생성
- [ ] 서버에 Import 성공
- [ ] Pro 서버에서 Run 성공

---

## C-4. OpenAI 연결 (선택 — API 키 필요)

```bash
pip install openai
export OPENAI_API_KEY=sk-your-key-here
```

`test_openai.py` 파일:

```python
import asyncio
from openai import AsyncOpenAI
from agent_swarm import Swarm, SubTask

client = AsyncOpenAI()

async def llm(prompt, tools=None):
    r = await client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role":"user","content":prompt}],
        max_tokens=500)
    usage = {"prompt_tokens": r.usage.prompt_tokens,
             "completion_tokens": r.usage.completion_tokens,
             "total_tokens": r.usage.total_tokens}
    return (r.choices[0].message.content, usage)

async def main():
    result = await Swarm(llm=llm).run(
        "2026년 AI 에이전트 프레임워크를 분석하세요",
        tasks=[
            SubTask(id="research", description="주요 프레임워크 3개 조사", role="Researcher"),
            SubTask(id="compare", description="장단점 비교", role="Analyst", dependencies=["research"]),
            SubTask(id="recommend", description="추천 작성", role="Writer", dependencies=["compare"]),
        ])
    for tid, r in result["results"].items():
        print(f"\n[{tid}]")
        print(r.output[:300] if r.output else r.error)
    meta = result["metadata"]
    print(f"\n{meta['succeeded']}/{meta['total_tasks']} 성공, 토큰: {meta['total_tokens']}")

asyncio.run(main())
```

```bash
python test_openai.py
```

확인:
- [ ] 실제 GPT 응답 나옴
- [ ] 토큰 수 표시됨

---

# 결과 체크리스트

| # | 테스트 | 방식 | API키 | 결과 |
|---|---|---|---|---|
| A-1 | 첫 실행 | 코드 | 불필요 | |
| A-2 | 직접 코드 | 코드 | 불필요 | |
| A-3 | 병렬 실행 | 코드 | 불필요 | |
| A-4 | 실패 복구 | 코드 | 불필요 | |
| A-5 | 메모리 | 코드 | 불필요 | |
| A-6 | 도구 | 코드 | 불필요 | |
| A-7 | Export | CLI | 불필요 | |
| A-8 | 자동 431개 | 코드 | 불필요 | |
| B-1 | Pro 서버 | 서버 | 불필요 | |
| B-2 | API 키 발급 | curl | 불필요 | |
| B-3 | 대시보드 | 브라우저 | Pro 키 | |
| B-4 | REST API | curl | Pro 키 | |
| B-5 | Proof Bundle | curl | Pro 키 | |
| C-1 | SDK 기본 | 코드 | Pro 키 | |
| C-2 | SDK 전체 | 코드 | Pro 키 | |
| C-3 | Free→Pro 전환 | 코드 | Pro 키 | |
| C-4 | OpenAI 연결 | 코드 | OpenAI 키 | |

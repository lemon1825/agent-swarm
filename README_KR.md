# Agent Swarm

**리서치, 리뷰, 승인 워크플로를 위한 경량 멀티에이전트 엔진**

외부 의존성 0개. 모듈 34개. export 159개. 테스트 252개. 스킬이 스스로 진화합니다.

```python
from agent_swarm import Swarm, SubTask, openai

result = await Swarm(llm=openai()).run("경쟁사 분석", tasks=[
    SubTask(id="조사", description="상위 5개 경쟁사 조사", role="Researcher"),
    SubTask(id="비교", description="강점 비교 분석", role="Analyst", dependencies=["조사"]),
    SubTask(id="보고서", description="추천 보고서 작성", role="Writer", dependencies=["비교"]),
])
```

```bash
pip install agent-swarm-core
```

---

## 1분 만에 시작하기

```bash
pip install agent-swarm-core openai
export OPENAI_API_KEY=sk-xxx
```

```python
from agent_swarm import Swarm, SubTask, openai, save_result

result = await Swarm(llm=openai()).run("AI 시장 분석", tasks=[
    SubTask(id="r", description="조사", role="Researcher"),
    SubTask(id="a", description="분석", role="Analyst", dependencies=["r"]),
    SubTask(id="w", description="보고서", role="Writer", dependencies=["a"]),
])

save_result(result, "report.html")  # HTML 보고서 저장
```

---

## LLM 연결 (5개 커넥터)

```python
from agent_swarm import Swarm, openai, claude, ollama, vllm, litellm

# 클라우드 API
Swarm(llm=openai())                    # GPT-4o-mini (기본)
Swarm(llm=openai("gpt-4o"))            # 모델 지정
Swarm(llm=claude())                     # Claude Sonnet
Swarm(llm=claude("claude-opus-4-6"))    # Claude Opus

# 로컬 모델 — API 키 불필요
Swarm(llm=ollama("llama3"))             # Ollama (개인 PC, CPU OK)
Swarm(llm=vllm("meta-llama/Llama-3.1-8B-Instruct"))  # vLLM (GPU 서버)

# 100+ 프로바이더
Swarm(llm=litellm("gpt-4o-mini"))

# vLLM 최적 프리셋
from agent_swarm import vllm_optimized, list_presets
Swarm(llm=vllm_optimized("meta-llama/Llama-3.1-8B-Instruct"))

# 내 GPU에 맞는 모델 찾기
models = list_presets(max_gpu_gb=24)  # 24GB 이하 모델
```

| 커넥터 | API 키 | GPU | 비용 | 용도 |
|---|---|---|---|---|
| `openai()` | 필요 | 불필요 | 종량제 | 빠른 테스트 |
| `claude()` | 필요 | 불필요 | 종량제 | 고품질 분석 |
| `ollama()` | 불필요 | CPU OK | $0 | 개인 개발 |
| `vllm()` | 불필요 | GPU 필요 | $0 | 프로덕션 |
| `litellm()` | 프로바이더별 | 불필요 | 프로바이더별 | 멀티 프로바이더 |

---

## 도구 자동 호출

```python
from agent_swarm import Swarm, openai, auto_tools

# 에이전트가 필요하면 자동으로 web_search, json_parse 등 호출
swarm = Swarm(llm=auto_tools(openai()))
result = await swarm.run("Cursor의 최신 가격 정책 조사")
```

---

## 결과 저장

```python
from agent_swarm import save_result

save_result(result, "report.md")     # Markdown
save_result(result, "report.html")   # 스타일링된 HTML
save_result(result, "report.json")   # JSON
```

---

## 레시피 — 즉시 사용 가능한 봇 5개

```bash
export OPENAI_API_KEY=sk-xxx

python recipes/competitor_analysis.py "Cursor"          # 경쟁사 분석
python recipes/code_review.py src/auth.py               # 코드 리뷰
python recipes/research.py "AI 에이전트 시장"             # 리서치
python recipes/content_writer.py "AI의 미래"             # 콘텐츠 제작
python recipes/bug_analysis.py "NullPointerException"   # 버그 분석
```

API 키 없이도 데모 모드로 실행됩니다.

---

## 스킬 효과 측정

SkillsBench 논문(Li et al., 2026) 기반. 스킬이 실제로 도움이 되는지 A/B 테스트합니다.

```python
from agent_swarm import SkillEvaluator

evaluator = SkillEvaluator(swarm)
report = await evaluator.evaluate(goal, tasks, runs=5)
print(report.summary())
# → MarketResearch: +17pp ✓ (유지)
# → DataAnalysis:   -8pp ✗ (비활성화 권장)
```

---

## 컨텍스트 다양성 점수

XSA 논문(Zhai, 2026) 기반. 에이전트가 자기 출력만 반복하는지 측정합니다.

```python
from agent_swarm import diversity_report

report = diversity_report(result)
# → [analyst] diversity=0.82, self_ref=15% → Good
# → [writer]  diversity=0.31, self_ref=72% → High self-reference
```

---

## 주요 기능

- **병렬 DAG 실행**: 의존성 없는 태스크 자동 병렬
- **승인 게이트**: 사람이 중간에 승인/거절
- **예산 통제**: LLM 비용 상한
- **스킬 유전학**: 스킬이 교차/적대적 테스트/토너먼트으로 진화
- **온톨로지 라우팅**: SKOS 3-mode 게이트 (soft/warn/strict)
- **프로덕션 에러 처리**: 7-class 분류 + 자동 재시도/truncation
- **메모리 4종**: short/long/entity/context
- **빌트인 도구 6개**: web_search, http_fetch, file_read/write, shell_exec, json_parse
- **플레이북 10개**: research, code_review, discover, strategy 등
- **스킬 팩 3개**: research-pack, review-pack, pm-pack
- **체크포인트/재개**: 프로세스 죽어도 이어서 실행
- **Pro SDK**: 로컬에서 Pro 서버 기능 호출

---

## Free → Pro 전환

```bash
python -m agent_swarm export --output my_workspace.json
# → agentswarm.dev에서 Pro 결제 → Import → 끊김 없이 이어서 사용
```

---

## 테스트

```bash
python examples/01_basic.py         # 30초 즉시 확인
python -m pytest tests/ -q          # 129 unit tests
python test_agent_swarm.py          # 123 integration tests
```

---

## 라이센스

MIT — 영원히 무료

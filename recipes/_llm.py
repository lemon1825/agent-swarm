"""Shared LLM connector for recipes.

Auto-detects available API key and connects to the right LLM.
Falls back to mock if no key is set.

Usage:
    from _llm import get_llm, print_cost

    llm, model_name = get_llm()
    # ... use llm with Swarm ...
    print_cost(result)
"""
import os
import sys

def get_llm():
    """Returns (llm_function, model_name).

    Priority:
      1. OPENAI_API_KEY → gpt-4o-mini
      2. ANTHROPIC_API_KEY → claude-sonnet
      3. No key → mock (demo mode)
    """
    if os.environ.get("OPENAI_API_KEY"):
        return _openai_llm(), "gpt-4o-mini"
    elif os.environ.get("ANTHROPIC_API_KEY"):
        return _claude_llm(), "claude-sonnet-4-20250514"
    else:
        print("⚠ API 키 없음 — 데모 모드로 실행 (실제 LLM 연결은 OPENAI_API_KEY 설정)")
        print()
        return _mock_llm(), "mock"


def _openai_llm():
    from openai import AsyncOpenAI
    client = AsyncOpenAI()

    async def llm(prompt, tools=None):
        r = await client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=2000,
            temperature=0.3,
        )
        usage = {
            "prompt_tokens": r.usage.prompt_tokens,
            "completion_tokens": r.usage.completion_tokens,
            "total_tokens": r.usage.total_tokens,
        }
        return (r.choices[0].message.content, usage)

    return llm


def _claude_llm():
    from anthropic import AsyncAnthropic
    client = AsyncAnthropic()

    async def llm(prompt, tools=None):
        r = await client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=2000,
            messages=[{"role": "user", "content": prompt}],
        )
        usage = {
            "prompt_tokens": r.usage.input_tokens,
            "completion_tokens": r.usage.output_tokens,
            "total_tokens": r.usage.input_tokens + r.usage.output_tokens,
        }
        return (r.content[0].text, usage)

    return llm


def _mock_llm():
    """Produces realistic-looking output for demo purposes."""
    async def llm(prompt, tools=None):
        p = prompt.lower()

        # Competitor analysis
        if "경쟁사" in p or "competitor" in p or "find" in p and "market" in p:
            return "[데모] 주요 경쟁사 3곳 발견: A사 (시장 점유율 35%, 매출 $50M), B사 (급성장, YoY 200%), C사 (니치 시장 강자, 기술력 우위). A사는 엔터프라이즈에 강하나 개발자 경험이 약함."
        if "비교" in p or "compare" in p or "강점" in p or "weakness" in p or "swot" in p:
            return "[데모] SWOT 분석:\n- A사: 강점(브랜드, 자금력), 약점(느린 혁신)\n- B사: 강점(성장률, UX), 약점(수익성)\n- C사: 강점(기술력, 정확도), 약점(스케일)\n\n기회: 개발자 중심 시장이 비어있음. 위협: 빅테크 진입 가능성."
        if "전략" in p or "strategy" in p or "recommend" in p or "추천" in p:
            return "[데모] 추천 전략:\n1. 개발자 경험을 핵심 차별점으로 설정\n2. B2B SaaS 시장 진입 (A사가 약한 영역)\n3. 오픈소스 커뮤니티로 초기 사용자 확보\n4. 6개월 내 PMF 검증, 12개월 내 시리즈 A 목표\n\n예상 TAM: $2.1B, 목표 시장 점유율: 5% (3년)"

        # Code review
        if "보안" in p or "security" in p or "vulnerab" in p:
            return "[데모] 보안 점검 결과:\n- SQL Injection 위험: line 42 (user input이 직접 쿼리에 삽입됨)\n- XSS 취약점: line 87 (사용자 입력이 escape 없이 렌더링)\n- 하드코딩된 시크릿: line 15 (API_KEY가 코드에 포함)\n심각도: HIGH (즉시 수정 필요)"
        if "품질" in p or "quality" in p or "코드" in p and "리뷰" in p:
            return "[데모] 코드 품질:\n- 복잡도: 함수 3개가 cyclomatic complexity > 15 (리팩토링 권장)\n- 중복: 인증 로직이 3곳에 반복 (유틸 함수로 추출)\n- 네이밍: 변수명 x, tmp, data → 의미 있는 이름으로 변경\n- 테스트 커버리지: 추정 40% (목표 80%)"
        if "개선" in p or "improve" in p or "수정" in p or "fix" in p:
            return "[데모] 수정 제안:\n1. SQL Injection → parameterized query 사용\n2. XSS → DOMPurify로 sanitize\n3. 시크릿 → 환경변수로 이동\n4. 복잡한 함수 → 단일 책임 원칙으로 분리\n\n우선순위: 보안(즉시) > 중복 제거(이번 주) > 네이밍(다음 스프린트)"

        # Research
        if "조사" in p or "research" in p or "찾" in p or "탐색" in p:
            return "[데모] 조사 결과:\n- 2026년 시장 규모: $4.2B (전년 대비 38% 성장)\n- 핵심 트렌드: 멀티에이전트 시스템, 자율 코딩, RAG 고도화\n- 주요 논문: 'Scaling Agents' (Stanford, 2025), 'Agent Benchmarks' (Google, 2026)\n- 업계 동향: 90%의 기업이 AI 에이전트 도입 검토 중"
        if "검증" in p or "verify" in p or "fact" in p:
            return "[데모] 검증 결과:\n- 시장 규모 $4.2B: Gartner 보고서와 일치 (신뢰도 HIGH)\n- 38% 성장률: McKinsey 추정치 35-42%와 일치\n- 90% 기업 도입: 출처 불명확 (신뢰도 LOW, 실제로는 45-60% 추정)\n\n수정 권고: '90% 기업 도입 검토' → '약 50%의 기업이 파일럿 진행 중'으로 수정"
        if "종합" in p or "synthe" in p or "보고서" in p or "report" in p or "write" in p:
            return "[데모] 종합 보고서:\n\n## 핵심 요약\nAI 에이전트 시장은 2026년 $4.2B 규모로, 연 38% 성장 중입니다.\n\n## 주요 발견\n1. 멀티에이전트 아키텍처가 단일 에이전트를 대체하는 추세\n2. 개발자 경험(DX)이 프레임워크 선택의 핵심 기준\n3. 오픈소스 프로젝트가 상용 솔루션보다 빠르게 혁신\n\n## 권고\n경량 오픈소스 엔진으로 시작, 엔터프라이즈 기능은 유료화"

        # Content
        if "초안" in p or "draft" in p:
            return "[데모] 초안:\n\n# AI 에이전트가 바꾸는 소프트웨어 개발의 미래\n\n2026년, 개발자는 더 이상 혼자 코딩하지 않습니다. AI 에이전트가 리서치, 코드 리뷰, 테스트를 동시에 수행하며, 개발자는 아키텍처와 의사결정에 집중합니다.\n\n이 글에서는 멀티에이전트 시스템이 실제로 어떻게 작동하는지, 그리고 2026년에 주목할 3가지 트렌드를 소개합니다."
        if "편집" in p or "edit" in p or "review" in p and "content" in p:
            return "[데모] 편집 결과:\n- 도입부: '2026년' → 구체적 데이터 추가 (시장 규모 $4.2B)\n- 2단락: 수동태 → 능동태로 변경 (가독성 향상)\n- 결론: CTA 추가 ('지금 시작하세요' 섹션)\n- 전체: 읽기 수준 검증 완료 (중학생 이해 가능)"

        # Bug analysis
        if "원인" in p or "cause" in p or "분석" in p and ("버그" in p or "에러" in p or "error" in p):
            return "[데모] 원인 분석:\n- Root cause: NullPointerException at AuthService.java:142\n- refresh_token이 만료된 상태에서 갱신 시도 시 null 체크 누락\n- 영향 범위: 로그인 후 24시간 경과한 모든 사용자\n- 재현 조건: 1) 로그인 2) 24시간 대기 3) API 호출"
        if "재현" in p or "reproduce" in p:
            return "[데모] 재현 단계:\n1. 테스트 계정으로 로그인\n2. refresh_token의 expiry를 과거로 수동 설정\n3. GET /api/profile 호출\n4. 500 Internal Server Error 확인\n\n재현율: 100%"
        if "수정안" in p or "patch" in p or "solution" in p:
            return "[데모] 수정안:\n```java\n// Before (line 142)\nString newToken = refreshService.refresh(token);\n\n// After\nif (token == null || token.isExpired()) {\n    throw new AuthException(\"Token expired, re-login required\");\n}\nString newToken = refreshService.refresh(token);\n```\n\n테스트: 기존 142개 + 신규 3개 = 145개 통과"

        return f"[데모] 처리 완료: {prompt[:80]}..."

    return llm


def print_cost(result):
    """Print token usage and estimated cost."""
    meta = result["metadata"]
    tokens = meta.get("total_tokens", 0)
    # GPT-4o-mini pricing: ~$0.15/1M input, ~$0.60/1M output
    cost = tokens * 0.0000003
    print(f"\n{'─'*50}")
    print(f"토큰: {tokens:,}  |  예상 비용: ${cost:.4f}")
    print(f"태스크: {meta['succeeded']}/{meta['total_tasks']} 성공  |  시간: {meta['execution_time_s']:.1f}초")
    print(f"{'─'*50}")


def save_result(result, filename):
    """Save final output to markdown file."""
    output = result.get("final_output", "")
    if not output:
        outputs = []
        for tid, r in result["results"].items():
            if r.success:
                outputs.append(f"## {tid}\n\n{r.output}")
        output = "\n\n---\n\n".join(outputs)

    with open(filename, "w") as f:
        f.write(output)
    print(f"📄 결과 저장: {filename}")

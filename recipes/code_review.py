"""코드 리뷰 봇

파일 경로를 입력하면 보안 점검 → 품질 분석 → 개선안을 생성합니다.

사용법:
    export OPENAI_API_KEY=sk-xxx
    python recipes/code_review.py my_code.py
    python recipes/code_review.py src/auth/login.py

API 키 없이도 데모 모드로 실행됩니다.
"""
import asyncio
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.dirname(__file__))

from agent_swarm import Swarm, SubTask, AgentConfig
from _llm import get_llm, print_cost, save_result


async def main(filepath: str):
    llm, model = get_llm()

    # 파일 읽기
    code = ""
    if os.path.isfile(filepath):
        with open(filepath) as f:
            code = f.read()
        print(f"🔍 코드 리뷰: {filepath} ({len(code)} chars)")
    else:
        code = f"# (파일 없음 — '{filepath}' 기반 데모 리뷰)"
        print(f"🔍 코드 리뷰: {filepath} (데모)")

    print(f"   모델: {model}")
    print()

    swarm = Swarm(
        llm=llm,
        configs={"default": AgentConfig(timeout=60, retries=3)},
    )

    result = await swarm.run(
        goal=f"다음 코드를 리뷰하세요:\n\n```\n{code[:3000]}\n```",
        tasks=[
            SubTask(
                id="security_scan",
                description="코드의 보안 취약점을 점검하세요. SQL Injection, XSS, 하드코딩된 시크릿, 인증 우회 등을 확인하고 심각도(HIGH/MEDIUM/LOW)를 표시하세요.",
                role="Researcher",
            ),
            SubTask(
                id="quality_review",
                description="코드 품질을 평가하세요. 복잡도, 중복, 네이밍, 에러 처리, 테스트 커버리지를 확인하세요.",
                role="Researcher",
            ),
            SubTask(
                id="improvement_plan",
                description="보안 점검과 품질 평가 결과를 종합하여, 우선순위가 높은 순서대로 구체적인 수정 제안을 작성하세요. 가능하면 수정된 코드 예시를 포함하세요.",
                role="Writer",
                dependencies=["security_scan", "quality_review"],
            ),
        ],
    )

    labels = {"security_scan": "🔒 보안 점검", "quality_review": "📏 품질 분석", "improvement_plan": "🛠 개선안"}
    for tid, r in result["results"].items():
        print(f"\n{labels.get(tid, tid)}")
        print("─" * 50)
        print(r.output if r.success else f"❌ 실패: {r.error}")

    print_cost(result)
    basename = os.path.splitext(os.path.basename(filepath))[0]
    save_result(result, f"code_review_{basename}.md")


if __name__ == "__main__":
    filepath = sys.argv[1] if len(sys.argv) > 1 else "example.py"
    asyncio.run(main(filepath))

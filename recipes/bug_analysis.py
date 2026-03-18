"""버그 분석 봇

에러 메시지나 로그를 입력하면 원인 분석 → 재현 방법 → 수정안을 생성합니다.

사용법:
    export OPENAI_API_KEY=sk-xxx
    python recipes/bug_analysis.py "NullPointerException at AuthService.java:142"
    python recipes/bug_analysis.py "TypeError: Cannot read property 'map' of undefined"

API 키 없이도 데모 모드로 실행됩니다.
"""
import asyncio
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.dirname(__file__))

from agent_swarm import Swarm, SubTask, AgentConfig
from _llm import get_llm, print_cost, save_result


async def main(error: str):
    llm, model = get_llm()
    print(f"🐛 버그 분석: {error[:80]}")
    print(f"   모델: {model}")
    print()

    swarm = Swarm(
        llm=llm,
        configs={"default": AgentConfig(timeout=60, retries=3)},
    )

    result = await swarm.run(
        goal=f"다음 에러를 분석하고 수정안을 제시하세요:\n\n{error}",
        tasks=[
            SubTask(
                id="root_cause",
                description=f"다음 에러의 근본 원인(Root Cause)을 분석하세요:\n{error}\n\n가능한 원인을 우선순위별로 나열하고, 영향 범위를 파악하세요.",
                role="Researcher",
            ),
            SubTask(
                id="reproduce",
                description="원인 분석을 바탕으로 이 버그를 재현하는 단계별 방법을 작성하세요. 필요한 환경, 선행 조건, 정확한 재현 스텝을 포함하세요.",
                role="Analyst",
                dependencies=["root_cause"],
            ),
            SubTask(
                id="fix_proposal",
                description="근본 원인과 재현 방법을 바탕으로 수정안을 제시하세요. 수정 코드 예시, 테스트 케이스, 배포 시 주의사항을 포함하세요. 재발 방지 대책도 제안하세요.",
                role="Writer",
                dependencies=["root_cause", "reproduce"],
            ),
        ],
    )

    labels = {"root_cause": "🔎 원인 분석", "reproduce": "🔄 재현 방법", "fix_proposal": "🛠 수정안"}
    for tid, r in result["results"].items():
        print(f"\n{labels.get(tid, tid)}")
        print("─" * 50)
        print(r.output if r.success else f"❌ 실패: {r.error}")

    print_cost(result)
    safe_name = error.replace(" ", "_").replace("/", "_").replace(":", "")[:30]
    save_result(result, f"bug_analysis_{safe_name}.md")


if __name__ == "__main__":
    error = sys.argv[1] if len(sys.argv) > 1 else "NullPointerException at AuthService.java:142 — refresh token expired"
    asyncio.run(main(error))

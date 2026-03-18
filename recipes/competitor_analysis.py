"""경쟁사 분석 봇

회사명을 입력하면 경쟁사 조사 → SWOT 비교 → 전략 보고서를 생성합니다.

사용법:
    export OPENAI_API_KEY=sk-xxx
    python recipes/competitor_analysis.py "Cursor"
    python recipes/competitor_analysis.py "네이버"

API 키 없이도 데모 모드로 실행됩니다.
"""
import asyncio
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.dirname(__file__))

from agent_swarm import Swarm, SubTask, AgentConfig
from _llm import get_llm, print_cost, save_result


async def main(company: str):
    llm, model = get_llm()
    print(f"🔍 경쟁사 분석: {company}")
    print(f"   모델: {model}")
    print()

    swarm = Swarm(
        llm=llm,
        configs={"default": AgentConfig(timeout=60, retries=3)},
    )

    result = await swarm.run(
        goal=f"{company}의 경쟁 환경을 분석하고 전략을 추천하세요",
        tasks=[
            SubTask(
                id="find_competitors",
                description=f"{company}의 직접 경쟁사 3-5개를 찾고, 각각의 시장 점유율, 매출 규모, 핵심 강점을 정리하세요.",
                role="Researcher",
            ),
            SubTask(
                id="swot_analysis",
                description=f"경쟁사 조사 결과를 바탕으로 {company}와 경쟁사들의 SWOT(강점/약점/기회/위협) 비교 분석을 수행하세요.",
                role="Analyst",
                dependencies=["find_competitors"],
            ),
            SubTask(
                id="strategy_report",
                description=f"SWOT 분석을 바탕으로 {company}의 경쟁 전략을 추천하세요. 단기(3개월), 중기(6개월), 장기(1년) 액션 플랜을 포함하세요.",
                role="Writer",
                dependencies=["swot_analysis"],
            ),
        ],
    )

    # 결과 출력
    for tid, r in result["results"].items():
        label = {"find_competitors": "🔎 경쟁사 조사", "swot_analysis": "📊 SWOT 분석", "strategy_report": "📋 전략 보고서"}
        print(f"\n{label.get(tid, tid)}")
        print("─" * 50)
        print(r.output if r.success else f"❌ 실패: {r.error}")

    print_cost(result)
    save_result(result, f"competitor_analysis_{company.replace(' ', '_')}.md")


if __name__ == "__main__":
    company = sys.argv[1] if len(sys.argv) > 1 else "Agent Swarm"
    asyncio.run(main(company))

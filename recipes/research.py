"""리서치 봇

주제를 입력하면 조사 → 팩트 검증 → 종합 보고서를 생성합니다.

사용법:
    export OPENAI_API_KEY=sk-xxx
    python recipes/research.py "2026년 AI 에이전트 시장"
    python recipes/research.py "한국 SaaS 시장 현황"

API 키 없이도 데모 모드로 실행됩니다.
"""
import asyncio
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.dirname(__file__))

from agent_swarm import Swarm, SubTask, AgentConfig
from _llm import get_llm, print_cost, save_result


async def main(topic: str):
    llm, model = get_llm()
    print(f"🔬 리서치: {topic}")
    print(f"   모델: {model}")
    print()

    swarm = Swarm(
        llm=llm,
        configs={"default": AgentConfig(timeout=60, retries=3)},
    )

    result = await swarm.run(
        goal=f"'{topic}'에 대해 깊이 있는 리서치를 수행하세요",
        tasks=[
            SubTask(
                id="broad_research",
                description=f"'{topic}'에 대해 폭넓게 조사하세요. 시장 규모, 주요 플레이어, 최신 트렌드, 핵심 데이터를 수집하세요. 가능하면 출처를 명시하세요.",
                role="Researcher",
            ),
            SubTask(
                id="deep_dive",
                description=f"'{topic}'의 기술적/비즈니스적 심층 분석을 수행하세요. 일반적으로 알려지지 않은 인사이트, 숨은 트렌드, 반론을 포함하세요.",
                role="Researcher",
            ),
            SubTask(
                id="fact_check",
                description="앞선 조사 결과의 핵심 주장과 데이터를 검증하세요. 각 주장의 신뢰도(HIGH/MEDIUM/LOW)를 표시하고, 부정확한 부분은 수정 권고하세요.",
                role="Analyst",
                dependencies=["broad_research", "deep_dive"],
            ),
            SubTask(
                id="final_report",
                description=f"모든 조사와 검증 결과를 종합하여 '{topic}'에 대한 최종 보고서를 작성하세요. 핵심 요약, 주요 발견, 데이터, 권고사항을 포함하세요. 마크다운 형식으로 작성하세요.",
                role="Writer",
                dependencies=["fact_check"],
            ),
        ],
    )

    labels = {"broad_research": "🌐 폭넓은 조사", "deep_dive": "🔬 심층 분석", "fact_check": "✅ 팩트 검증", "final_report": "📋 최종 보고서"}
    for tid, r in result["results"].items():
        print(f"\n{labels.get(tid, tid)}")
        print("─" * 50)
        print(r.output if r.success else f"❌ 실패: {r.error}")

    print_cost(result)
    safe_name = topic.replace(" ", "_").replace("/", "_")[:30]
    save_result(result, f"research_{safe_name}.md")


if __name__ == "__main__":
    topic = sys.argv[1] if len(sys.argv) > 1 else "AI 에이전트 프레임워크 시장 2026"
    asyncio.run(main(topic))

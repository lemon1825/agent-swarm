"""콘텐츠 제작 봇

주제를 입력하면 리서치 → 초안 → 편집 → 최종본을 생성합니다.

사용법:
    export OPENAI_API_KEY=sk-xxx
    python recipes/content_writer.py "AI가 바꾸는 소프트웨어 개발"
    python recipes/content_writer.py "스타트업을 위한 멀티에이전트 가이드"

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
    print(f"✍️  콘텐츠 제작: {topic}")
    print(f"   모델: {model}")
    print()

    swarm = Swarm(
        llm=llm,
        configs={"default": AgentConfig(timeout=60, retries=3)},
    )

    result = await swarm.run(
        goal=f"'{topic}' 주제로 블로그 포스트를 작성하세요",
        tasks=[
            SubTask(
                id="research",
                description=f"'{topic}'에 대한 핵심 정보, 최신 데이터, 인용할 만한 사례를 조사하세요. 독자의 관심을 끌 수 있는 흥미로운 사실을 찾으세요.",
                role="Researcher",
            ),
            SubTask(
                id="outline",
                description=f"조사 결과를 바탕으로 블로그 포스트의 구조를 설계하세요. 제목, 서론, 본론 3-5개 섹션, 결론, CTA를 포함하세요.",
                role="Analyst",
                dependencies=["research"],
            ),
            SubTask(
                id="draft",
                description="설계된 구조에 따라 블로그 포스트 초안을 작성하세요. 1500-2000자 분량. 전문적이면서 읽기 쉬운 톤으로 작성하세요. 마크다운 형식으로 작성하세요.",
                role="Writer",
                dependencies=["outline"],
            ),
            SubTask(
                id="edit",
                description="초안을 편집하세요. 문법, 흐름, 톤, 정확성을 검토하고, 도입부를 더 강렬하게, 결론에 CTA를 추가하세요. 최종 발행 가능한 상태로 만드세요.",
                role="Analyst",
                dependencies=["draft"],
            ),
        ],
    )

    labels = {"research": "🔍 리서치", "outline": "📝 구조 설계", "draft": "✏️ 초안", "edit": "📰 최종본"}
    for tid, r in result["results"].items():
        print(f"\n{labels.get(tid, tid)}")
        print("─" * 50)
        print(r.output if r.success else f"❌ 실패: {r.error}")

    print_cost(result)
    safe_name = topic.replace(" ", "_").replace("/", "_")[:30]
    save_result(result, f"content_{safe_name}.md")


if __name__ == "__main__":
    topic = sys.argv[1] if len(sys.argv) > 1 else "AI 에이전트가 바꾸는 소프트웨어 개발의 미래"
    asyncio.run(main(topic))

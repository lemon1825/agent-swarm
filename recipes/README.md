# 레시피 — 즉시 사용 가능한 봇

API 키 하나면 바로 실행됩니다.

```bash
export OPENAI_API_KEY=sk-xxx
```

## 경쟁사 분석

```bash
python recipes/competitor_analysis.py "Cursor"
```

회사명 → 경쟁사 조사 → SWOT 비교 → 전략 보고서 (markdown 저장)

## 코드 리뷰

```bash
python recipes/code_review.py src/auth/login.py
```

파일 경로 → 보안 점검 → 품질 분석 → 개선안 (markdown 저장)

## 리서치

```bash
python recipes/research.py "2026년 AI 에이전트 시장"
```

주제 → 폭넓은 조사 + 심층 분석 → 팩트 검증 → 종합 보고서 (markdown 저장)

## 콘텐츠 제작

```bash
python recipes/content_writer.py "AI가 바꾸는 소프트웨어 개발"
```

주제 → 리서치 → 구조 설계 → 초안 → 편집 → 최종본 (markdown 저장)

## 버그 분석

```bash
python recipes/bug_analysis.py "NullPointerException at AuthService.java:142"
```

에러 → 원인 분석 → 재현 방법 → 수정안 + 코드 예시 (markdown 저장)

---

## API 키 없이 실행

키 없이도 데모 모드로 구조를 확인할 수 있습니다:

```bash
python recipes/competitor_analysis.py "TestCompany"
```

`⚠ API 키 없음 — 데모 모드로 실행` 메시지와 함께 샘플 결과가 나옵니다.

## 지원 LLM

| 환경변수 | 모델 |
|---|---|
| `OPENAI_API_KEY` | gpt-4o-mini |
| `ANTHROPIC_API_KEY` | claude-sonnet |
| 없음 | 데모 모드 |

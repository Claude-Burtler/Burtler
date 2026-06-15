# CLAUDE.md

Behavioral guidelines to reduce common LLM coding mistakes. Merge with project-specific instructions as needed.

**Tradeoff:** These guidelines bias toward caution over speed. For trivial tasks, use judgment.

## 1. Think Before Coding

**Don't assume. Don't hide confusion. Surface tradeoffs.**

Before implementing:
- State your assumptions explicitly. If uncertain, ask.
- If multiple interpretations exist, present them - don't pick silently.
- If a simpler approach exists, say so. Push back when warranted.
- If something is unclear, stop. Name what's confusing. Ask.

## 2. Simplicity First

**Minimum code that solves the problem. Nothing speculative.**

- No features beyond what was asked.
- No abstractions for single-use code.
- No "flexibility" or "configurability" that wasn't requested.
- No error handling for impossible scenarios.
- If you write 200 lines and it could be 50, rewrite it.

Ask yourself: "Would a senior engineer say this is overcomplicated?" If yes, simplify.

## 3. Surgical Changes

**Touch only what you must. Clean up only your own mess.**

When editing existing code:
- Don't "improve" adjacent code, comments, or formatting.
- Don't refactor things that aren't broken.
- Match existing style, even if you'd do it differently.
- If you notice unrelated dead code, mention it - don't delete it.

When your changes create orphans:
- Remove imports/variables/functions that YOUR changes made unused.
- Don't remove pre-existing dead code unless asked.

The test: Every changed line should trace directly to the user's request.

## 4. Goal-Driven Execution

**Define success criteria. Loop until verified.**

Transform tasks into verifiable goals:
- "Add validation" → "Write tests for invalid inputs, then make them pass"
- "Fix the bug" → "Write a test that reproduces it, then make it pass"
- "Refactor X" → "Ensure tests pass before and after"

For multi-step tasks, state a brief plan:
```
1. [Step] → verify: [check]
2. [Step] → verify: [check]
3. [Step] → verify: [check]
```

Strong success criteria let you loop independently. Weak criteria ("make it work") require constant clarification.

## 5. 코드 구조 원칙

**기능 중심 설계. 확장성과 가독성을 기본값으로.**

### 기능 분리
- 관련 기능은 같은 모듈/폴더로 묶어라. 기능별 디렉토리 구조를 유지해라.
  - 예: `routers/`, `models/`, `services/`, `utils/`
- 하나의 파일·클래스·함수는 하나의 책임만 진다.
- 여러 곳에서 쓰이는 로직은 공통 모듈로 분리해라.

### Pydantic 모델 (Python)
- 요청/응답 스키마, 설정값, 함수 간 데이터 전달에는 반드시 Pydantic `BaseModel`을 사용해라.
- 함수 경계를 넘어 raw `dict`를 전달하지 마라.

### 확장성
- 공통 동작은 기반 클래스(base class)로 추출해라.
- 새 기능 추가가 기존 코드 수정 없이 가능한 구조를 목표로 해라 (Open/Closed).
- 구체 구현보다 추상(abstract class, protocol)에 의존해라.

### 가독성
- 변수명·함수명만 봐도 의도를 알 수 있어야 한다.
- "왜(why)"가 자명하지 않은 로직에만 짧은 주석을 달아라. "무엇(what)"은 코드로 표현해라.
- 한 화면을 넘는 함수는 분리를 고려해라.

---

**These guidelines are working if:** fewer unnecessary changes in diffs, fewer rewrites due to overcomplication, and clarifying questions come before implementation rather than after mistakes.
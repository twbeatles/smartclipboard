# SmartClipboard Contextual Action Palette
## Agent-Ready Implementation Specification

> Repository: `twbeatles/smartclipboard`
>
> 목표: 기존 SmartClipboard의 클립보드 히스토리/자동 처리 기능을 유지하면서, 사용자가 선택한 클립보드 항목에 대해 상황별 작업을 빠르게 실행할 수 있는 **Contextual Action Palette**를 추가한다.
>
> 이 문서는 Codex / Claude Code / Gemini CLI 등에 그대로 전달 가능한 구현 지시서다.
>
> **구현 상태 (2026-08-14):** MVP가 `smartclipboard_core/action_palette` + `smartclipboard_app/features/action_palette`에 반영됨.
> writeback은 §20 확정 정책(`mark_internal_copy` + 같은 행 merge)이다. 감사 후속은 `PROJECT_AUDIT.md` 섹션 7.

---

# 1. 제품 목표

현재 SmartClipboard는 텍스트·이미지·URL·파일 등을 저장하고 검색하며, 정규식 기반 자동 액션과 URL 제목 조회, 전화번호 포맷팅 등을 제공한다.

이번 기능은 다음 한 문장으로 정의한다.

> **복사한 내용을 저장하는 앱에서, 복사한 내용으로 바로 일을 처리하는 앱으로 확장한다.**

핵심 사용자 흐름:

```text
클립보드 항목 선택
    ↓
Alt + A 또는 우클릭 → 작업 실행
    ↓
현재 콘텐츠에 적용 가능한 작업만 제안
    ↓
검색 / 방향키 / Enter
    ↓
결과 복사 또는 Preview
```

목표 UX 시간:

```text
항목 선택 → 원하는 결과 획득
3초 이내 / 3회 이하 주요 키 입력
```

---

# 2. 현재 저장소 구조에서 반드시 지킬 사항

구현 전에 현재 `main`을 다시 확인한다.

현재 확인된 구조상:

```text
smartclipboard_core/
    actions.py            # clipboard automation compatibility facade
    automation/
        fetch_title.py
        formatters.py
        manager.py
    database.py
    worker.py

smartclipboard_app/
    ... UI / application code
```

`smartclipboard_core/actions.py`는 기존 공개 import 경로를 보존하는 **compatibility facade** 역할을 한다.

따라서:

- 새 Action Palette 구현을 `smartclipboard_core/actions.py`에 몰아넣지 않는다.
- 기존 `ClipboardActionManager`를 대체하지 않는다.
- `format_phone`, `format_email`, `transform_text`, `fetch_title_logic` 등 기존 helper는 재사용한다.
- 기존 public import contract를 깨지 않는다.
- UI는 `smartclipboard_app`의 현재 패턴을 따른다.
- core에는 GUI-independent 로직만 둔다.

권장:

```text
smartclipboard_core/
    action_palette/
        __init__.py
        models.py
        context.py
        registry.py
        executor.py
        builtins/
            text.py
            phone.py
            url.py
            developer.py
            search.py

smartclipboard_app/
    features/
        action_palette/
            dialog.py
            preview.py
            integration.py
```

실제 프로젝트 구조가 달라졌다면 현재 코드 관례를 우선한다.

---

# 3. 기존 자동 액션과 새 기능의 역할 분리

기존:

```text
Clipboard change
 → copy rule
 → normalize/replace
 → ClipboardActionManager
 → DB 저장
```

새 기능:

```text
이미 저장된 item 또는 현재 선택 item
 → ActionContext
 → applicable actions
 → 사용자 명시적 선택
 → ActionExecutor
 → result
```

원칙:

```text
기존 ClipboardActionManager = 자동 처리
새 Action Palette          = 수동 처리
```

새 Palette를 위해 기존 자동화 파이프라인을 재설계하지 않는다.

---

# 4. MVP 범위

반드시 포함:

1. ActionContext
2. ActionResult
3. Action 정의 계약
4. ActionRegistry
5. applicability 판단
6. Action executor
7. Action Palette UI
8. 검색
9. keyboard navigation
10. 메인 history 선택 항목에서 실행
11. 우클릭 진입점
12. 최소 15개 built-in action
13. 결과 preview
14. action error isolation
15. 기존 formatter/title-fetch 재사용
16. core unit tests
17. 최소 UI smoke
18. pyright/test/build 검증
19. README 업데이트

---

# 5. 명시적 비범위

이번 PR에서 하지 않는다.

- LLM API
- OpenAI/Claude/Gemini
- Python plugin dynamic import
- shell / PowerShell 실행
- 파일 삭제/이동
- 임의 HTTP POST
- 클라우드 sync
- 사용자 스크립트 실행기
- batch workflow builder
- OCR
- browser extension
- semantic classification

에이전트가 "확장성"을 이유로 위 기능의 framework까지 미리 만들지 않는다.

---

# 6. ActionContext

예시:

```python
from dataclasses import dataclass, field
from typing import Any, Mapping

@dataclass(frozen=True)
class ActionContext:
    item_id: int | str | None
    raw_text: str
    normalized_text: str
    content_type: str

    url: str | None = None
    domain: str | None = None
    file_paths: tuple[str, ...] = ()

    is_multiline: bool = False
    is_valid_json: bool = False
    is_sensitive: bool = False

    metadata: Mapping[str, Any] = field(default_factory=dict)
```

`content_type` 예:

```text
text
url
phone
email
json
code
color
file
files
image
unknown
```

분류 규칙을 새로 중복 구현하지 않는다.

현재 앱에 text analysis/type inference가 있으면 adapter로 재사용한다.

추가 heuristic만 새 helper에 둔다.

---

# 7. Sensitive content 처리

기존 앱에는 보안 보관함이 있으므로 새 Palette가 민감 정보 UX를 악화시키면 안 된다.

다음 조건을 확인한다.

- vault item인지
- password/API key로 분류되는 item인지
- privacy mode 상태인지

정책:

```text
민감 item:
- Google Search 기본 추천 금지
- URL title fetch 기본 추천 금지
- QR은 허용 가능하나 명시적 실행
- local transform은 허용
- 외부 네트워크 action에는 경고
```

MVP에서 정확한 sensitive classifier가 없다면:

```text
vault item → sensitive
```

만이라도 적용한다.

절대 clipboard 내용을 자동으로 네트워크에 전송하지 않는다.

---

# 8. Action 계약

권장:

```python
@dataclass(frozen=True)
class ActionResult:
    kind: str              # "text" | "url" | "qr" | "info"
    value: str
    title: str | None = None
    preview: bool = False
    copy_to_clipboard: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)


class ClipboardPaletteAction(Protocol):
    id: str
    title: str
    category: str
    description: str
    priority: int
    network_required: bool

    def is_applicable(self, context: ActionContext) -> bool:
        ...

    def execute(self, context: ActionContext) -> ActionResult:
        ...
```

과도한 추상 클래스 계층 금지.

---

# 9. Registry

```python
class ActionRegistry:
    def register(self, action) -> None:
        ...

    def get_applicable(
        self,
        context: ActionContext,
        query: str = "",
    ) -> list:
        ...
```

정렬:

1. content-specific action
2. `priority`
3. recent/frequent usage
4. title

첫 버전은 usage 없이 deterministic priority만 사용해도 된다.

---

# 10. Action Executor

Executor 책임:

- exception isolation
- network action 여부 체크
- sensitive context guard
- 실행 시간 측정(optional)
- result normalization
- usage 기록(optional)

개별 action 실패 시:

```text
toast:
"JSON 정리에 실패했습니다."
```

앱 전체 예외로 전파하지 않는다.

---

# 11. UI 진입점

필수 2개:

### A. 단축키

```text
Alt + A
```

현재 앱 내 단축키 충돌 확인 후 사용.

충돌 시 대체:

```text
Ctrl + Alt + A
```

단축키를 하드코딩하기 전에 기존 shortcut registry/settings 구조를 확인한다.

### B. Context menu

history item 우클릭:

```text
작업 실행...
```

선택 item이 없으면 disabled.

---

# 12. Palette UI

예:

```text
┌ 작업 실행 ───────────────────────── Esc ┐
│                                         │
│ https://github.com/twbeatles/...        │
│ URL · github.com                        │
│                                         │
│ 🔍 작업 검색                            │
│                                         │
│ 추천                                    │
│ > Markdown 링크 만들기                  │
│   페이지 열기                           │
│   도메인 복사                           │
│   QR 코드                               │
│                                         │
│ 텍스트                                  │
│   한 줄로 만들기                        │
└─────────────────────────────────────────┘
```

요구사항:

- 폭 약 540~620px
- theme token 사용
- list scrolling
- Up/Down
- Enter
- Esc
- 검색 field autofocus
- 검색 결과 없음 empty state
- action description tooltip 또는 secondary text
- icon은 optional

---

# 13. Built-in Actions

## Text

### `text.trim`
앞뒤 whitespace 제거.

### `text.collapse_spaces`
연속 horizontal whitespace를 하나로.
newline 유지.

### `text.single_line`
newline → single space.

### `text.remove_blank_lines`
빈 줄 제거.

### `text.dedupe_lines`
순서 유지 + 동일 줄 중복 제거.

### `text.sort_lines`
case-insensitive 또는 현재 locale-independent sort.
동작을 테스트로 고정한다.

### `text.lowercase`

### `text.uppercase`

### `text.normalize_newlines`
CRLF/CR/LF 정규화.

---

# 14. Phone Actions

반드시 기존 `format_phone` 재사용.

### `phone.format_kr`

예:

```text
01012345678 → 010-1234-5678
021234567   → 02-1234-5678
```

### `phone.digits_only`

```text
010-1234-5678 → 01012345678
```

---

# 15. URL Actions

### `url.open`
Qt의 기존 external-open 방식 사용.

### `url.copy_domain`

```text
https://github.com/a/b?x=1
→ github.com
```

### `url.markdown_link`

title metadata가 있으면:

```markdown
[SmartClipboard](https://...)
```

없으면 domain 사용.

### `url.fetch_title`

기존 `fetch_title_logic` / worker 패턴 재사용.

**중요:** UI thread에서 blocking HTTP를 실행하지 않는다.

현재 worker abstraction이 있으면 반드시 사용한다.

### `url.qr`

기존 qrcode dependency와 UI가 있으면 재사용.

---

# 16. Developer Actions

### `dev.json_pretty`

```python
json.dumps(obj, ensure_ascii=False, indent=2)
```

### `dev.json_minify`

compact separators.

### `dev.url_encode`

### `dev.url_decode`

### `dev.json_escape_string`

### `dev.base64_encode`

MVP optional.

### `dev.base64_decode`

UTF-8로 안전하게 decode 가능한 경우만 applicable.

binary output 금지.

---

# 17. Search Action

### `search.google`

사용자가 명시적으로 실행해야 한다.

- query max 500자
- sensitive context에서는 추천 우선순위 낮추거나 숨김
- default browser open

---

# 18. Preview 정책

즉시 복사:

- trim
- phone formatting
- domain
- lowercase/uppercase

Preview 권장:

- JSON pretty
- multiline transform
- 300자 이상
- QR
- 원본 대비 변화량이 큰 결과

Preview UI:

```text
[원본] | [결과]

[복사] [닫기]
```

diff view는 MVP에서 불필요.

---

# 19. 비동기 작업

다음은 UI thread에서 실행 금지:

- URL title fetch
- 향후 network action
- 큰 QR render(optional)

현재 `smartclipboard_core/worker.py` 또는 application worker pattern을 조사하여 재사용한다.

새 thread framework를 만들지 않는다.

---

# 20. Clipboard write 정책

Action 결과를 clipboard로 복사하면 watcher가 다시 감지할 수 있다.

구현 확정 정책 (2026-08-14):

> Palette 변환 결과는 `mark_internal_copy()` 후 clipboard에 쓰고,
> 선택 history 행에 `replace_text_item_or_merge()`로 writeback 한다.
> 자동 `ClipboardActionManager`를 다시 타지 않는다.

초기 초안은 “새 history row 저장”을 기본으로 적었으나, 앱의 기존 `setText` 계약과
상세 패널 변환 UX에 맞춰 같은 행 갱신으로 고정했다.

새 suppression subsystem은 만들지 않는다.

---

# 21. Action usage statistics

MVP 후반 선택 기능.

저장 예:

```json
{
  "text.single_line": {
    "count": 12,
    "last_used": "..."
  }
}
```

새 DB migration보다 기존 prefs/settings 저장소를 우선.

추천 순서에 반영 가능.

이 기능 때문에 MVP가 지연되면 생략.

---

# 22. 성능 기준

Palette open:

```text
로컬 action 계산 < 50ms 목표
```

다음 작업은 open 시 수행 금지:

- HTTP
- DNS
- filesystem scan
- DB full scan

context 생성은 선택 item 한 건만 사용.

---

# 23. 에러/Edge Cases

반드시 처리:

- 빈 text
- whitespace-only
- 100k+ characters
- malformed URL
- invalid JSON
- JSON primitive (`1`, `"x"`)
- 전화번호처럼 보이나 invalid
- emoji
- Hangul
- surrogate/unicode
- clipboard item deleted during palette open
- network title timeout
- no selected item
- image-only item
- file-only item

지원하지 않는 type이면:

```text
이 항목에 사용할 수 있는 작업이 없습니다.
```

---

# 24. 테스트

## Pure transforms

- trim
- whitespace collapse
- newline
- dedupe
- sort
- phone
- URL domain
- markdown
- JSON pretty/minify
- encode/decode

## Applicability

```text
URL → URL actions
phone → phone actions
JSON → JSON actions
plain text → general text actions
invalid JSON → JSON actions 미노출
vault/sensitive → network action recommendation 제한
```

## Error isolation

action이 예외를 던져도 executor가 safe result/error를 반환.

## UI smoke

가능한 범위:

- dialog opens
- search filters
- arrow selection
- Enter
- Escape

---

# 25. Packaging 검증

SmartClipboard는 Windows EXE 배포가 있으므로:

- PyInstaller hidden import가 필요한지 확인
- 새 package가 자동 포함되는지 확인
- qrcode/optional imports 회귀 확인
- static assets 추가 시 spec 반영

`smartclipboard.spec` 변경은 필요한 경우에만 한다.

---

# 26. 단계별 구현

## Phase 1
Core models + context + registry + text actions + tests.

## Phase 2
Palette UI + history integration + shortcut + context menu.

## Phase 3
Phone / URL / JSON / search / QR.

## Phase 4
Preview + sensitive guard + polish + docs.

각 Phase는 실행 가능한 상태로 끝낸다.

stub만 쌓지 않는다.

---

# 27. Definition of Done

- [ ] 기존 clipboard automation 회귀 없음
- [ ] `ClipboardActionManager` public contract 유지
- [ ] Alt+A 또는 승인된 대체 shortcut
- [ ] context menu 진입
- [ ] 15개 이상 action
- [ ] content-specific recommendation
- [ ] network action UI-thread blocking 없음
- [ ] sensitive content 외부 action guard
- [ ] Preview
- [ ] error isolation
- [ ] core tests
- [ ] UI smoke
- [ ] pyright 통과
- [ ] 전체 pytest 통과
- [ ] EXE packaging smoke
- [ ] README 업데이트
- [ ] 5개 theme에서 UI 확인

---

# 28. 구현하지 말아야 할 실수

- 기존 `actions.py` facade에 모든 새 클래스를 넣기
- 자동 ActionManager와 Palette action을 동일 lifecycle로 합치기
- UI에서 HTTP 동기 호출
- 사용자 동의 없이 clipboard text를 외부 전송
- 대규모 DB migration
- plugin framework 선행 구현
- 기존 tests 약화/삭제
- unrelated UI refactor
- 단축키를 기존 registry 확인 없이 추가

---

# 29. 에이전트 실행 프롬프트

```text
Repository: twbeatles/smartclipboard

현재 main 브랜치와 README, claude.md, PROJECT_ANALYSIS.md, smartclipboard_core,
smartclipboard_app, tests, smartclipboard.spec를 먼저 확인하고,
기존 구조를 유지한 채 Contextual Action Palette를 구현해라.

핵심 제품 목표:
사용자가 history item을 선택하고 Alt+A 또는 컨텍스트 메뉴 "작업 실행..."을 통해
현재 콘텐츠에 적용 가능한 수동 작업을 검색/선택/실행할 수 있게 한다.

매우 중요:
- smartclipboard_core/actions.py는 현재 compatibility facade다.
- 기존 ClipboardActionManager와 format_phone/format_email/transform_text/
  fetch_title_logic 공개 contract를 깨지 않는다.
- 새 Palette는 자동 clipboard processing과 분리한다.
- 기존 formatter와 URL title fetch 로직을 재사용한다.
- network title fetch는 UI thread에서 동기 실행하지 않는다.
- 현재 worker abstraction을 조사해 재사용한다.
- vault/sensitive item은 외부 network action을 자동 추천하거나 실행하지 않는다.
- shell, 파일 삭제, 사용자 script, LLM API는 구현하지 않는다.

필수:
ActionContext, ActionResult, ActionRegistry, executor, applicability,
Palette UI, search, Up/Down/Enter/Esc, history integration,
context menu, shortcut, preview, built-in actions, tests.

built-in 최소:
trim
collapse spaces
single line
remove blank lines
dedupe lines
sort lines
normalize newlines
lowercase
uppercase
Korean phone format (기존 formatter reuse)
digits only
URL open
domain copy
Markdown link
URL title fetch (기존 logic reuse, async)
QR
JSON pretty
JSON minify
URL encode
URL decode
JSON string escape
Google search

구현 위치는 현재 코드 구조를 우선하되 core action logic과 Qt UI는 분리한다.
가능하면 smartclipboard_core/action_palette + smartclipboard_app의 feature UI 구조를 사용한다.

테스트:
- pure transforms
- applicability
- invalid input
- sensitive guard
- executor exception isolation
- 최소 UI smoke
- 전체 기존 tests

완료 검증:
pytest
pyright
repo가 제공하는 기타 check
PyInstaller packaging smoke

테스트 assertion을 약화하거나 기존 기능을 삭제하지 않는다.
unrelated refactor 금지.
README와 단축키 문서를 실제 구현 상태로 업데이트한다.

마지막 보고:
1. 변경 파일
2. 핵심 설계
3. 재사용한 기존 모듈
4. 테스트 결과
5. packaging 결과
6. 남은 제한사항
```

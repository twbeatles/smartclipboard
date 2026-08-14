# Project Audit

감사 범위: Contextual Action Palette (2026-08 추가분)  
근거: `README.md`, `Claude.md`, CodeGraph 호출 경로, 해당 소스 본문  
작성일: 2026-08-14  
감사 시점에는 코드 수정을 하지 않음. **권고안은 같은 날 구현에 반영됨** — 섹션 7 참고.

---

## 1. Executive Summary

Action Palette는 기존 자동 액션(`ClipboardActionManager`)과 분리된 수동 실행 경로로 잘 나뉘어 있다. 코어 변환·applicability·예외 isolation은 테스트가 있고, `fetch_title` HTTP는 기존 `fetch_title_logic`의 SSRF 가드를 재사용한다.

다만 **클립보드 쓰기 정책이 프로젝트 계약과 충돌**하고, **제목 조회의 수명주기/중복 실행 가드가 자동 경로보다 약하다**. 민감 정보 가드는 태그/메모 부분 문자열에만 의존해, 비밀번호·토큰이 본문에만 있는 항목은 Google 검색이 그대로 노출된다.

전체 위험도: **Medium-High**. 즉시 장애를 낼 Critical은 드물지만, 종료 중 콜백·대용량 QR·비밀 텍스트 외부 검색은 실제 사용에서 터질 수 있다.

핵심 문제 3개:

1. Palette `setText`가 `mark_internal_copy`를 쓰지 않아, 변환 결과가 다시 자동 액션 파이프라인을 탄다.
2. `start_fetch_title`는 shutdown 가드·캐시·inflight dedupe·사전 URL 검증이 없다.
3. `is_sensitive`가 본문/보관함 출처를 보지 않아 네트워크 액션 가드가 쉽게 비어 있다.

---

## 2. Project Understanding

### 제품

SmartClipboard Pro는 Windows PyQt6 클립보드 매니저다. 히스토리 저장·검색·자동화 규칙·보안 보관함·내보내기/가져오기가 본래 기능이고, 이번 추가는 **선택 항목으로 일을 처리하는 수동 Palette**다.

### 아키텍처 규칙 (`Claude.md`)

- 신규 로직은 `smartclipboard_core/` 또는 `smartclipboard_app/features/`에 둔다.
- `legacy_main.py`는 marshal payload 로더이며, UI 변경은 `legacy_main_src.py` + payload 재생성.
- `clipboard.setText()` 경로는 `mark_internal_copy()`를 먼저 호출한다.
- `fetch_title`은 첫 URL만, 로컬/사설 차단, Worker + 전용 thread pool.
- `smartclipboard_core/actions.py` facade와 `ClipboardActionManager` public contract는 유지.

### 추가 기능 실행 흐름 (CodeGraph)

```text
선택 item
  → Alt+A / 우클릭 "작업 실행..."
  → MainWindow.open_action_palette
  → ActionPaletteController.open_palette
  → open_palette_impl
       → context_from_item(db) → build_context
       → ActionPaletteDialog (적용 가능 목록)
       → ActionExecutor.execute
       → preview 또는 apply_result
            ├─ fetch_title → Worker(fetch_title_logic) → _handle_title_result
            ├─ url/google  → webbrowser.open
            └─ text 복사   → clipboard.setText (internal flag 없음)
                 → on_clipboard_change_impl
                 → process_text_clipboard_impl
                 → ClipboardActionManager.process
```

자동 파이프라인과 Palette는 클래스를 공유하지 않는다. 교차점은 **클립보드 쓰기**와 **같은 `fetch_title_logic` / thread pool**뿐이다.

---

## 3. High-Risk Issues

### H1. Palette 복사가 프로젝트 클립보드 계약을 깨고 자동 액션을 재실행한다

* 위치: `smartclipboard_app/features/action_palette/services.py` `apply_result`
* 문제: `copy_to_clipboard`일 때 `clipboard.setText(result.value)`만 호출하고 `mark_internal_copy`를 쓰지 않는다.
* 영향: 변환 결과가 새 history로 들어가며, 켜져 있는 copy rule / `format_phone` / `fetch_title` 자동 규칙이 한 번 더 돈다. 제목 조회·치환이 중복되고, 사용자가 “이 항목을 고쳐서 복사”했다고 생각한 결과가 다른 row로  entangle된다. `Claude.md`의 “모든 `setText`는 internal flag” 규칙과도 어긋난다.
* 근거:
  - `apply_result` 69–72행: `setText`만 수행.
  - `on_clipboard_change_impl` 20–22행: `is_internal_copy`가 아니면 debounce 후 `process_clipboard`.
  - `process_text_clipboard_impl` 108–110행: `add_item` 후 `_process_actions`.
* 권장 수정 방향: 정책을 문서와 코드에서 하나로 고정한다. (A) Palette도 `mark_internal_copy` + 선택 row writeback(자동 액션과 동일 merge 규칙), 또는 (B) 새 history가 맞다면 `Claude.md`를 개정하고, 자동 `process_actions`가 Palette 결과에서 재실행되지 않도록 출처 플래그를 둔다. 둘을 섞지 말 것.
* 우선순위: **High**

### H2. 제목 조회 Worker가 종료/DB close 이후에도 UI·DB를 건드린다

* 위치: `services.py` `start_fetch_title`, `_handle_title_result`  
  대비: `ClipboardActionManager.shutdown` / `_is_shutting_down`
* 문제: Palette Worker 콜백은 shutdown 가드가 없다. `quit_app_impl`은 `action_manager.shutdown()`과 `db.close()`를 하지만, 이미 돌고 있는 Palette Worker의 `result` 시그널은 막지 않는다. 콜백은 `db.get_content` / `update_url_title` / toast / 모달 Preview를 연다.
* 영향: 종료 직후 SQLite 사용, 파괴된 위젯 toast, 종료 중 모달 다이얼로그. Qt/스레드에서 간헐 크래시 가능.
* 근거:
  - `start_fetch_title` 81–92행: `Worker` + `result.connect(_handle_title_result)`, inflight 추적 없음.
  - `_handle_title_result` 99–116행: `db`/`window` 유효성·shutdown 플래그 없음.
  - `quit_app_impl` 151–162행: automation shutdown + `db.close()`만 수행. Palette 전용 취소 없음.
  - `ClipboardActionManager._handle_title_result`는 `_is_shutting_down`과 `_db_is_available()`를 본다.
* 권장 수정 방향: 자동 경로와 같은 가드를 넣거나, Palette fetch를 `action_manager.fetch_url_title_async`에 위임한다. 종료 시 Worker disconnect + 무시 플래그.
* 우선순위: **High**

### H3. 민감 가드가 본문·보관함 출처를 보지 않는다

* 위치: `smartclipboard_core/action_palette/context.py` `_is_sensitive`, `build_context`  
  `registry.get_applicable` / `ActionExecutor.execute`
* 문제: `is_sensitive`는 `tags`/`note`에 `password|secret|api_key|token|비밀번호` 부분 문자열이 있을 때만 True다. 클립보드 본문이 API 키여도 태그가 없으면 `search.google`이 적용된다. 보관함 복사는 `mark_internal_copy`라 history에 안 들어오므로, 명세의 “vault item → sensitive”는 Palette에서 거의 작동하지 않는다.
* 영향: 사용자가 복사한 비밀을 명시적으로 Google에 보낼 수 있다. 반대로 메모에 `token`이 들어가면 정상 URL 제목 조회까지 막힌다(부분 일치).
* 근거:
  - `_is_sensitive` 39–43행: tags/note only, `in` 부분 문자열.
  - `search.google` `network_required=True`, `url.fetch_title`만 숨김.
  - `url.open` / `url.qr`은 `network_required=False`라 민감해도 남는다.
* 권장 수정 방향: 본문 heuristic(PEM, `sk-`, `AKIA`, 긴 hex/base64)을 값싸게 추가하고, Google은 민감 시 숨김을 유지. `token`은 단어 경계로 좁힌다. `url.open`은 민감 URL에서 확인 또는 비추천.
* 우선순위: **High**

### H4. QR 생성에 크기 제한·예외 처리가 없다

* 위치: `builtins/url.py` `_qr` / `_has_text`  
  `features/action_palette/qr.py` `render_qr_pixmap`  
  `preview.py` Preview UI
* 문제: 비어 있지 않은 텍스트면 QR이 뜬다. 1MB 히스토리 텍스트도 대상이다. `render_qr_pixmap`은 try/except가 없고, Preview는 렌더 실패 시 예외가 다이얼로그 생성으로 전파될 수 있다.
* 영향: UI 정지, 메모리 급증, Preview 크래시.
* 근거:
  - `_has_text`: image/file만 제외.
  - `render_qr_pixmap`: `qr.add_data(text); qr.make(fit=True)` 후 PIL 변환, 가드 없음.
  - 기존 `MainWindow.generate_qr`는 try/except + 메시지 박스가 있다.
* 권장 수정 방향: 길이 상한(예: 1–2KB) 후 미적용. `render_qr_pixmap`에서 예외를 잡고 Preview는 안내 문구.
* 우선순위: **High**

### H5. Palette `fetch_title`는 자동 경로의 사전검증·캐시·dedupe를 건너뛴다

* 위치: `services.start_fetch_title` vs `ClipboardActionManager.fetch_url_title_async`
* 문제: 자동 경로는 `validate_title_fetch_url` 선행, 256/24h 캐시, URL당 inflight 합치기를 한다. Palette는 매번 Worker를 띄운다. `_action_palette_title_worker`를 덮어써서 이전 작업은 계속 돌고 콜백만 둘 다 온다.
* 영향: 같은 URL 중복 HTTP, 사설 URL도 워커가 뜬 뒤에야 실패, 연속 실행 시 Preview가 두 번.
* 근거:
  - `start_fetch_title` 76–92행: precheck/cache/pending map 없음, worker 핸들 덮어쓰기.
  - `ClipboardActionManager.fetch_url_title_async` 125–167행: HAS_WEB, validate, cache, `_pending_by_url`.
  - `fetch_title_logic` 내부 검증은 있으므로 SSRF 자체는 워커 안에서 막힌다.
* 권장 수정 방향: `action_manager.fetch_url_title_async`를 재사용하거나, 동일 precheck/cache/pending을 Palette에 이식. 연속 실행 시 이전 시그널 disconnect.
* 우선순위: **Medium**

### H6. 제목 저장 후 목록/상세가 갱신되지 않는다

* 위치: `_handle_title_result`
* 문제: `update_url_title` 후 `load_data()` / `on_selection_changed()`가 없다. Preview만 띄운다.
* 영향: 히스토리의 URL 제목 컬럼/상세가 다음 새로고침까지 비어 보인다. 자동 경로는 `action_completed` → UI 갱신 흐름이 있다.
* 근거: `_handle_title_result` 108–116행은 DB 갱신 + Preview. `load_data` 호출 없음.
* 권장 수정 방향: 성공 시 `window.load_data()` 또는 해당 row만 갱신. 창이 숨김이면 `is_data_dirty = True`.
* 우선순위: **Medium**

### H7. `url.open`이 텍스트 속 첫 URL을 확인 없이 연다

* 위치: `builtins/url.py` `_open`, `_has_url`  
  `services.apply_result` `webbrowser.open`
* 문제: `extract_first_url`이 잡힌 http(s)면 적용된다. 본문이 “메모 + URL”이어도 첫 URL을 연다. `network_required=False`라 민감 가드도 우회한다. scheme은 http/https로 제한되므로 `javascript:`/`file:`은 `extract_first_url`에 안 걸린다.
* 영향: 의도하지 않은 사이트 오픈. 피싱 URL이 클립보드에 있으면 한 번의 Enter로 방문.
* 근거: `_open` 24–31행, `apply_result` 65–67행, `extract_first_url`은 `https?://`만.
* 권장 수정 방향: 헤더에 열 URL을 명시. 본문≠URL이면 확인. 민감이면 숨기거나 경고.
* 우선순위: **Medium**

### H8. 종료 중 Preview 모달이 다시 뜰 수 있다

* 위치: `_handle_title_result` → `show_preview` → `ActionPreviewDialog.exec`
* 문제: 비동기 완료 시점에 모달 Preview를 연다. 앱 종료·창 숨김과 겹치면 종료가 막히거나 부모 없는 다이얼로그가 뜬다.
* 영향: 종료 지연, 포커스 이상.
* 근거: `_handle_title_result` 113–116행이 동기 `exec()`.
* 권장 수정 방향: 창이 visible/active일 때만 Preview. 아니면 toast + 제목만 저장.
* 우선순위: **Medium**

### H9. Preview에서 QR “복사”는 이미지가 아니라 원문 텍스트다

* 위치: `integration.show_preview_impl` 55–66행
* 문제: QR 결과를 복사하면 `kind`를 `text`로 바꿔 `result.value`(원문)를 클립보드에 넣는다.
* 영향: 사용자는 QR 이미지를 복사했다고 오해할 수 있다.
* 근거: `kind="text" if result.kind == "qr" else result.kind`.
* 권장 수정 방향: QR은 복사 비활성, 또는 `QImage`를 클립보드에. 버튼을 “원문 복사”로 표기.
* 우선순위: **Medium**

### H10. README / Claude.md와 구현 불일치

* 위치: `README.md`, `Claude.md`, 구현
* 문제:
  1. README가 Palette를 “클립보드 액션 자동화” 아래에 두어 자동 규칙과 섞여 보인다.
  2. README 앱 내 단축키에 `Ctrl+G` 구글 검색이 남아 있으나, 현재 `init_shortcuts`에는 Escape/Ctrl+F/Ctrl+P/Delete/Shift+Delete/Return/Ctrl+C/Alt+A만 있다. (`Ctrl+G`는 이번 기능 이전부터 문서만 남아 있는 것으로 보임.)
  3. `Claude.md`는 모든 `setText`에 `mark_internal_copy`를 요구하는데 Palette는 의도적으로 위반한다.
* 영향: 기여자/사용자가 잘못된 계약을 따른다. 다음 수정이 다시 어긋날 수 있다.
* 근거: README 34–42, 193–204행; `init_shortcuts` 1043–1085행; `Claude.md` 32행 vs `apply_result` 69–72행.
* 권장 수정 방향: Palette를 수동 기능으로 분리 서술. `Ctrl+G` 삭제 또는 구현. 클립보드 정책을 한쪽으로 문서화.
* 우선순위: **Medium**

### H11. 통합 테스트가 실제 실행 경로를 거의 안 탄다

* 위치: `tests/test_action_palette_core.py`, `tests/test_action_palette_ui.py`
* 문제: 순수 변환·다이얼로그 위젯·메뉴 라벨은 있다. `open_palette_impl`, `start_fetch_title`, shutdown 중 콜백, Palette 복사 후 `process_actions` 재진입, QR 예외, 사설 URL fetch는 없다. CodeGraph도 이들 심볼에 covering tests 없음을 표시한다.
* 영향: H1–H8 회귀가 CI를 통과한 채로 남을 수 있다.
* 근거: CodeGraph blast radius — `open_palette_impl`, `start_fetch_title`, `show_preview_impl` “no covering tests”.
* 권장 수정 방향: 섹션 6 테스트 목록.
* 우선순위: **Medium**

### H12. `json.loads`가 Palette 오픈 시 전체 본문에 대해 실행된다

* 위치: `context.py` `_looks_like_json` / `build_context`
* 문제: 오픈마다 `json.loads(text.strip())`. 저장 한도는 1MB라 상한은 있지만, 깊게 중첩된 JSON은 CPU를 쓸 수 있다. 오픈 목표 50ms와 충돌할 수 있다.
* 영향: 큰 JSON 항목에서 Palette가 늦게 뜬다. (추정: 일반적인 1MB pretty JSON은 보통 괜찮음.)
* 근거: `build_context` 100행. 열린 직후 HTTP/FS는 하지 않음(좋음).
* 권장 수정 방향: 길이 상한(예: 256KB) 초과 시 JSON 판정 skip. 필요하면 타임박스.
* 우선순위: **Low**

### H13. `_history_fields`가 DB 커넥션을 직접 조회한다

* 위치: `services._history_fields`
* 문제: public `ClipboardDB` API가 아니라 `db.conn` + raw SQL. mixin 추가 없이 surface를 우회한다. 스키마/락 관례 변경 시 Palette만 깨질 수 있다.
* 영향: 유지보수 취약. 기능 버그 가능성은 낮음(파라미터 바인딩은 사용).
* 근거: 18–35행. `Claude.md`는 public surface 안정을 요구.
* 권장 수정 방향: 기존 metadata helper를 쓰거나, 읽기 전용 getter를 DB API에 추가하고 baseline을 갱신.
* 우선순위: **Low**

---

## 4. Potential Functional Gaps

확실하지 않은 항목은 **추정**으로 표시한다.

| 항목 | 상태 | 설명 |
|------|------|------|
| 미니 창에서 Palette | 명세 비범위 | 미니 창 선택 항목에서는 `Alt+A`가 메인 창 단축키라 동작하지 않음. |
| usage 통계로 추천 정렬 | 명세 optional, 미구현 | 항상 priority+title. |
| 민감 본문 classifier | 부분 구현 | 태그/메모만. 본문 비밀은 Google 가능. |
| FILE/IMAGE 액션 | 명세대로 빈 상태 | 경로 복사·탐색기 열기는 없음. **추정:** 사용자가 기대할 수 있음. |
| `url.fetch_title` UX | 부분 | 사전 차단 사유(사설망)를 사용자에게 거의 안 보여 줌. |
| Palette 결과와 선택 row 동기화 | 의도적 분기 | 상세 패널 변환은 internal copy, Palette는 새 history. 두 UX가 다름. |
| 5 테마 육안 확인 | 미검증 | 토큰은 쓰지만 테마별 스크린 확인은 테스트에 없음. **추정:** light에서 contrast 이슈 가능. |
| `Ctrl+G` | 문서만 존재 | Palette Google과 별개. 단축키는 없음. |
| payload/EXE | payload는 재생성됨 | `smartclipboard.spec`은 `collect_submodules(features)`로 포함 가능. 수동 EXE smoke는 이 감사에서 실행하지 않음. **추정:** hidden import는 문제 없을 가능성 큼. |
| 검색 500자 | 구현됨 | core `search.py`는 500자, 메뉴 `build_google_search_url`은 무제한. Palette만 제한. |
| 다중 선택 | 미구현 | 첫 선택만. 병합 후 변환은 기존 메뉴에만 있음. |

---

## 5. Recommended Fix Plan

### 1단계 — 즉시 (동작·안전)

1. 클립보드 정책 확정 후 `apply_result`와 `Claude.md`를 맞춘다. 자동 액션 재진입을 막거나, 새 history를 명시하고 자동화 skip 플래그를 둔다. (H1)
2. Palette fetch 콜백에 shutdown/DB 유효성 가드를 넣고, `quit_app_impl`에서 disconnect한다. (H2, H8)
3. QR 길이 제한 + `render_qr_pixmap` try/except. (H4)
4. 민감 본문이 Google 검색에 안 나가게 최소 heuristic을 넣는다. (H3)

### 2단계 — 안정성

1. `fetch_url_title_async` 재사용 또는 cache/dedupe/precheck 이식. (H5)
2. 제목 저장 후 `load_data` / dirty 플래그. (H6)
3. `url.open` 확인 또는 민감 시 숨김. (H7)
4. QR 복사 라벨/동작을 분명히. (H9)
5. README에서 Palette를 수동 기능으로 분리, `Ctrl+G` 정리, 클립보드 정책 한 줄 명시. (H10)

### 3단계 — 구조

1. `_history_fields`를 DB public read로 승격. (H13)
2. 메뉴/코어 `build_google_search_url` 단일화.
3. JSON 판정 비용 상한. (H12)
4. 통합 테스트로 H1/H2/H4/H5를 고정. (H11, 섹션 6)

---

## 6. Test Recommendations

기존 `test_action_palette_core` / `_ui`는 변환·위젯 smoke로는 충분하다. 아래는 빠진 실행 경로다.

1. **Palette 복사 → 자동 액션**  
   가짜 clipboard + `is_internal_copy` + `process_text_clipboard_impl`.  
   현재 구현이면 새 history/`process_actions` 호출을 assert. 정책 변경 후면 호출되지 않음을 assert.

2. **fetch_title shutdown**  
   Worker 콜백을 직접 호출하되 `db.conn is None` / `_is_shutting_down` 상황에서 toast/Preview/`update_url_title`이 없음을 검증.

3. **inflight 중복**  
   `start_fetch_title` 두 번 → HTTP/Worker가 1회이거나 이전 시그널이 disconnect되는지.

4. **사설 URL**  
   `http://127.0.0.1/` fetch가 요청 없이 실패하고, 사용자 메시지가 남는지. (`fetch_title_logic` 단위는 `test_core`에 있음. Palette 진입 테스트가 없음.)

5. **민감**  
   본문만 있는 `sk-...` / `AKIA...` 에서 `search.google` 미노출. 태그 `documentation`에 `token` 부분일치가 과도하게 숨기지 않는지.

6. **QR**  
   10KB+ 텍스트는 미적용 또는 예외 없이 실패 메시지.

7. **제목 저장 후 UI**  
   `update_url_title` 이후 `load_data` 또는 dirty 플래그.

8. **url.open**  
   `webbrowser.open`에 넘기는 값이 `extract_first_url` 결과와 같고, `javascript:`/`file:`이 목록에 없는 것.

9. **회귀 문서**  
   README/설정 단축키 탭/`APP_LOCAL_SHORTCUTS`에 `Alt+A`가 있고 `Ctrl+G`가 구현과 일치하는지 문자열 계약 테스트.

이 목록을 구현하기 전에는 코드를 바꾸지 않는 것이 이 감사의 범위다.

---

## 7. Remediation status (2026-08-14)

감사 직후 옵션 A로 반영했다. 아래는 구현 후 상태이며, 위 섹션 1–6은 감사 당시 스냅샷으로 남긴다.

| ID | 조치 | 상태 |
|----|------|------|
| H1 | `apply_result`가 `mark_internal_copy()` 후 `setText()`, 선택 행은 `replace_text_item_or_merge()` | 반영 |
| H2 | `shutdown_palette_workers()` + fetch 콜백 shutdown/DB 가드. `quit_app_impl`에서 호출 | 반영 |
| H3 | 태그 단어 경계 + 본문 heuristic(PEM/`sk-`/`AKIA`/JWT). 민감 시 Google/제목 조회 숨김 | 반영 |
| H4 | QR 2048자 상한, `render_qr_pixmap` try/except | 반영 |
| H5 | `validate_title_fetch_url` 선행, manager cache, inflight disconnect | 반영 |
| H6 | 제목 저장 후 `load_data()` | 반영 |
| H7 | 민감 시 `url.open` 숨김, 혼합 텍스트는 확인 | 반영 |
| H10 | README에서 Palette를 수동 기능으로 분리, `Ctrl+G` 제거, `Alt+A` 명시 | 반영 |
| H11–H13 | `get_item_annotations` public read, Google URL 500자 단일화, JSON 256KB 상한, 통합 테스트 | 반영 |

문서 정합:

- 앱 내 단축키는 `Alt+A`(작업 실행). `Ctrl+G`는 구현에 없으며 현행 README/`PROJECT_ANALYSIS`에서 제거.
- 패키징은 기존 `collect_submodules` 범위. `smartclipboard.spec` 추가 hidden import 없음.
- 비공식 명세: `smartclipboard_action_palette_agent_spec.md` §20 writeback 정책.
- Spec Kit `specs/` 디렉터리는 아직 없음. `.specify/` + 루트 명세로 관리.

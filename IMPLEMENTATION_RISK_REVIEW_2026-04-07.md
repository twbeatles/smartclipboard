# SmartClipboard 구현 리스크 점검 메모

작성일: 2026-04-07
업데이트: 2026-04-08

## 처리 결과 요약

- 본 문서에 기록된 주요 리스크 1~7은 2026-04-08 기준으로 코드와 테스트에 반영 완료.
- 관련 구현은 `legacy_main_src.py`, `smartclipboard_core/`, `smartclipboard_app/ui/`, `tests/`에 반영됨.
- 문서/빌드/테스트 정합성도 함께 갱신했으며, Windows 테스트 temp 경로는 repo-local `.tmp-unittest/`로 통일.

## 항목별 조치 현황

### 1. 토스트 호출 인자 불일치 / 클립보드 모니터 재연결 누락

- `ToastNotification.show_toast()`가 `detail` 인자를 지원하도록 확장.
- `on_action_completed()`는 `clipboard.dataChanged` disconnect/connect를 `try/finally`로 보장.
- 토스트 자체가 실패해도 목록 갱신과 재연결이 계속 진행되도록 예외 분리.

### 2. `Ctrl+Shift+Z` paste-last semantics 불일치

- hotkey 경로가 표시 순서가 아닌 실제 최근 복사 항목(`timestamp DESC`, `id DESC`)을 선택하도록 수정.
- 사용자 문서 표현도 "가장 최근 복사 항목" 기준으로 수정.

### 3. 내림차순 사용자 정렬 시 pinned-first 깨짐

- pinned / unpinned 그룹을 먼저 분리하고 각 그룹 내부만 정렬하도록 변경.

### 4. 컬렉션 삭제 후 휴지통 복원 시 orphan `collection_id`

- 컬렉션 삭제 시 `history`뿐 아니라 `deleted_history`도 `collection_id = NULL` 처리.
- 복원 시 존재하지 않는 컬렉션 참조는 `NULL`로 강등.
- 컬렉션 할당/이동 시 invalid `collection_id` 방어 추가.

### 5. 보안 보관함 비밀번호 변경 직후 복사 버튼 실패

- copy 버튼은 생성 시점 암호문을 캡처하지 않고 `vid` 기준으로 최신 vault row를 다시 조회.
- 비밀번호 변경 성공 후 `load_items()` 재호출.

### 6. 종료/복원 타이밍의 URL 제목 worker late result

- `ClipboardActionManager.shutdown()` 추가.
- 종료/복원 전에 action signal disconnect + threadpool 정리.
- 종료 이후 late result는 닫힌 DB에 반영하지 않도록 가드.

### 7. import-time 로깅 설정의 handler 생성 부작용

- root logger에 handler가 없을 때만 `logging.basicConfig()`를 호출하도록 변경.

## 문서 / 빌드 / 테스트 동기화

- 수정 문서:
  - `README.md`
  - `claude.md`
  - `.gemini/GEMINI.md`
  - `PROJECT_ANALYSIS.md`
  - `legacy/README (modular).md`
  - `legacy/README (legacy).md`
- 빌드 문서:
  - `smartclipboard.spec` 상단 메모의 회귀 테스트 목록 갱신
- git ignore:
  - `.tmp-unittest/` 추가

## 검증 기준

- `tests/test_core.py`
- `tests/test_ui_dialogs_widgets.py`
- `tests/test_legacy_ui_contracts.py`
- `tests/test_public_surfaces.py`
- `tests/test_migration_collections.py`

## 잔여 메모

- repo-wide `pyright` 노이즈 정책은 기존과 동일하며, 로컬 게이트는 계속 `scripts/preflight_local.py`.
- payload 기반 런타임 구조는 유지되므로 `legacy_main_src.py` 변경 시 payload 재생성이 계속 필요.

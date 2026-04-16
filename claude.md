# SmartClipboard Pro - Claude 작업 가이드

## 1. 현재 아키텍처 요약

- 실행 진입점: `클립모드 매니저.py`
- 부트스트랩: `smartclipboard_app/bootstrap.py`
- 코어 비즈니스 로직: `smartclipboard_core/`
- 정적 분석 범위: 루트 `pyrightconfig.json` (현행 유지보수 대상 기준)
- 레거시 런타임:
  - `smartclipboard_app/legacy_main.py`는 **marshal payload 로더**
  - 실제 본문은 `smartclipboard_app/legacy_main_payload.marshal`
  - payload 동기화 메타데이터는 `smartclipboard_app/legacy_main_payload.manifest.json`

## 2. 작업 우선순위

1. 새 기능/수정은 가능한 한 `smartclipboard_core/` 또는 `smartclipboard_app/ui/`에 반영
2. 파사드 호환성(`클립모드 매니저.py` export) 유지
3. 빌드 시 payload 누락 방지 (`smartclipboard.spec` datas)

## 3. 변경 시 주의사항

- `legacy_main_payload.marshal`은 텍스트 diff/리뷰가 어려운 바이너리 payload이며, `legacy_main_payload.manifest.json`과 세트로 관리합니다.
- `legacy_main.py`를 소스 본문 파일로 가정하고 리팩토링하면 안 됩니다.
- `legacy_main.py`는 payload 로딩 실패 시 `legacy_main_src.py`로 자동 폴백하며, `LEGACY_IMPL_ACTIVE`/`LEGACY_IMPL_FALLBACK_REASON`로 활성 구현과 폴백 사유를 확인할 수 있습니다.
- `pyright`/Pylance 진단은 기본적으로 `legacy/클립모드 매니저 (legacy).py`와 `smartclipboard_app/legacy_main_src.py`를 제외한 현행 코드 기준으로 맞춥니다.
- UI/DB 기능 변경을 EXE에 반영하려면 `scripts/build_legacy_payload.py`로 `legacy_main_payload.marshal`과 manifest를 함께 재생성한 뒤 빌드해야 합니다.
- `fetch_title` 액션은 텍스트 전체가 아니라 첫 URL만 추출해 제목 요청하도록 유지합니다.
- `fetch_title`은 로컬/사설/메타데이터 주소를 기본 차단하고, HTML 응답만 제한 크기로 읽는 정책을 유지합니다.
- 동일 비이미지 재복사는 기존 history row를 갱신하는 정책이며, 메타데이터(tags/note/bookmark/collection/pin/use_count)를 유지해야 합니다.
- 동일 `FILE` path 집합 재복사도 기존 history row를 갱신하는 정책이며, `content`는 newline-joined absolute paths, `file_path`는 첫 경로로 유지합니다.
- 직접 `clipboard.setText()`를 호출하는 경로는 `smartclipboard_app.ui.clipboard_guard.mark_internal_copy()`를 통해 내부 복사 플래그를 먼저 세팅합니다.
- 파일 clipboard 복원 경로는 `smartclipboard_app.ui.clipboard_guard.restore_file_clipboard()`를 사용하고, 일부 파일만 남아 있으면 부분 복원, 모두 없으면 clipboard를 건드리지 않습니다.
- `FILE` 항목은 복원 직전뿐 아니라 목록/상세/미니 창에서도 stale/missing 경로 수를 먼저 보여주는 UX를 유지합니다.
- JSON 마이그레이션 포맷(`include_metadata=True`)은 `items` 외에 top-level `collections` 메타데이터(legacy_id/name/icon/color)를 포함하며, import 시 컬렉션 ID remap을 수행합니다.
- JSON 마이그레이션 문구는 히스토리 메타데이터 + 컬렉션 범위만 의미하며, 스니펫/규칙/핫키/보안 보관함 상태까지 포함하는 것으로 확장하지 않습니다.
- JSON export/import는 `IMAGE` 항목의 `image_data_b64` round-trip을 지원하고, CSV/Markdown은 이미지 BLOB 대신 플레이스홀더만 기록합니다.
- JSON export/import는 `FILE` 항목의 `file_paths`/`file_path`/newline content round-trip을 지원하고, CSV import는 `IMAGE` 플레이스홀더 row를 복원하지 않습니다.
- import는 호환성보다 정합성을 우선하며, JSON import에서 remap 불가 `collection_id`는 `NULL`, 비표준 timestamp는 앱 표준 시각으로 정규화하거나 import 시각으로 대체합니다.
- 현재 timestamp 정규화는 timezone-aware ISO 입력의 원본 wall-clock을 보존하는 정책입니다.
- `format_phone`은 `02`, 일반 지역번호, `0505`, `15xx/16xx/18xx` 대표번호까지 지원하는 쪽으로 유지합니다.
- `copy_rules`의 `custom_replace`는 빈 replacement를 허용하며, 빈 문자열은 “삭제 치환”으로 해석합니다.
- 스니펫 `shortcut`은 app-local 단축키이며 기본 앱 단축키·글로벌 핫키·다른 스니펫과 충돌하면 저장되지 않아야 합니다.
- 전체 기록 삭제는 영구 삭제가 아니라 고정 제외 후 휴지통 이동 정책을 유지합니다.
- 보안 보관함은 마스터 비밀번호 변경과 복호화 클립보드 30초 자동 삭제 흐름을 포함하며, `unlock()` 실패 시 `fernet/is_unlocked` 상태가 반드시 함께 초기화되어야 합니다.
- 보안 보관함은 `vault_salt`와 `vault_verification`이 모두 있어야 정상 구성으로 간주하고, 손상 시 잠금 화면 Reset 복구 경로를 유지합니다.
- `Ctrl+Shift+Z` paste-last는 pinned 정렬과 무관하게 가장 최근 복사된 항목(`timestamp DESC`, tie-break `id DESC`)을 사용해야 합니다.
- UI 사용자 정렬은 오름/내림차순과 무관하게 pinned-first 정책을 유지해야 합니다.
- 컬렉션 삭제는 `history`뿐 아니라 `deleted_history`의 `collection_id`도 정리해야 하고, 복원 시 존재하지 않는 컬렉션 참조는 `NULL`로 떨어져야 합니다.
- 보안 보관함 복사 버튼은 비밀번호 변경 직후에도 최신 DB row를 다시 조회해 복호화해야 합니다.
- Windows 테스트 임시 경로는 시스템 temp 대신 repo-local `.tmp-unittest/`를 사용합니다.
- 핫키 저장 경로는 등록 실패 시 이전 글로벌 핫키 상태로 롤백되어야 합니다.
- `smartclipboard.spec`는 `smartclipboard_core`, `smartclipboard_core.automation`, `smartclipboard_app.features`, `smartclipboard_app.ui.mainwindow_parts` 하위 모듈을 hidden import로 자동 수집하도록 유지하고, payload에서 직접 참조하는 `smartclipboard_app.ui.dialogs.collections`도 명시적으로 포함합니다.
- 2026-04-13 기준 `smartclipboard.spec` 추가 자산은 payload manifest(`legacy_main_payload.manifest.json`) 1건이며, 현재 spec에 반영되어 있습니다.
- 구조 검증 스크립트:
  - `scripts/refactor_symbol_inventory.py`
  - `scripts/refactor_signal_snapshot.py`
  - payload 반영 동기화 검증: `tests/test_payload_sync.py`
  - 현재 로더 구조에서는 로더 기반 결과와 소스 본문 기준 결과가 다를 수 있으므로 `legacy_main_src.py` 기준으로 확인합니다.

## 3.1 2026-04-12 Stable Contract

- `ExportImportManager` public API는 계속 `int`를 반환하고, 세부 요약은 `last_import_report` / `last_export_report`에서 읽습니다.
- JSON/CSV import는 항상 pre-import backup을 만든 뒤 파일 단위 단일 트랜잭션으로 반영하며, 실패 시 전체 rollback 됩니다.
- `search_items()`는 FTS-first 정책을 유지하고 FTS 0건일 때만 LIKE 보완 검색을 수행합니다. `_last_search_fallback`은 실제 FTS 오류일 때만 UI 경고용으로 사용합니다.
- `ClipboardActionManager.fetch_title`은 URL dedupe/cache와 전용 `QThreadPool(maxThreadCount=4)` 위에서 동작하며, stale URL 결과는 현재 row URL을 다시 확인한 뒤에만 저장합니다.
- `ClipboardActionManager`의 동기 텍스트 액션(`format_phone`/`format_email`/`transform`)은 순차적으로 working text를 갱신해야 하며, `fetch_title`은 그 최종 텍스트를 기준으로 URL을 다시 추출해야 합니다.
- 텍스트 치환 액션 결과는 UI 토스트만 띄우고 끝내지 말고, 같은 history row와 실제 clipboard에도 다시 기록해 저장 상태와 실제 clipboard를 맞춰야 합니다.
- `FILE` duplicate detection은 `history.file_signature` lookup을 사용하므로 path canonicalization 규칙을 깨면 안 됩니다.
- 보안 보관함 복호화 텍스트는 armed clipboard state로 추적되며 30초 조건부 clear와 종료 시 즉시 clear를 모두 유지합니다.
- `mini_window_enabled` 변경 후 hotkey 재등록이 실패하면 그 설정만 rollback 하고 실제 `_last_hotkey_error`를 사용자 경고로 노출합니다.
- `smartclipboard.spec`은 이번 안정화에서도 추가 hidden import/datas 증설 없이 유지 가능합니다.
- 검색 query가 있을 때는 DB/FTS relevance 순서를 기본으로 유지하고, 사용자가 명시적으로 헤더 정렬을 바꿨을 때만 client-side sort override를 적용합니다.
- JSON import가 컬렉션을 추가했다면 `load_data()` 전에 `refresh_collection_filter_options()`를 먼저 호출해야 상단 필터가 즉시 최신 상태를 반영합니다.
- 빈 검색 결과/빈 히스토리 경로에서도 `update_status_bar(0)`이 호출되어 이전 카운트가 남지 않아야 합니다.

## 4. 필수 검증

```powershell
python scripts/preflight_local.py
pyright <touched-files>
```

optional runtime dependency까지 CI와 같은 강도로 확인하려면 `python scripts/preflight_local.py --strict-optional-deps`를 추가 실행합니다.

- 현재 repo-wide `pyright`는 `smartclipboard_core/db_parts/*.py` mixin attribute-access 노이즈가 남아 있으므로, 최소 게이트는 `preflight_local.py`이고 `pyright`는 변경 파일 기준으로 병행합니다.

또는 단계별 실행:

```powershell
pyright <touched-files>
python scripts/build_legacy_payload.py --src smartclipboard_app/legacy_main_src.py --out smartclipboard_app/legacy_main_payload.marshal --smoke-import
python -m py_compile "클립모드 매니저.py" "smartclipboard_app/bootstrap.py" "smartclipboard_app/legacy_main.py" "smartclipboard_app/legacy_main_src.py" "smartclipboard_core/database.py" "smartclipboard_core/actions.py" "smartclipboard_core/worker.py"
python -m unittest discover -s tests -v
```

권장 회귀 포인트:
- `tests/test_core.py` (코어 DB/액션 회귀)
- `tests/test_ui_dialogs_widgets.py` (정렬/보관함/핫키 UI 회귀)
- `tests/test_payload_sync.py` (payload 런타임 시그니처/URL 액션)
- `tests/test_migration_collections.py` (JSON 마이그레이션 컬렉션 메타/ID remap)
- `tests/test_legacy_ui_contracts.py` (레거시 UI 계약: 토스트 호출/선택모드/가시성 가드)
- `tests/test_signal_snapshot.py` (MainWindow 분할 구조 시그널 스냅샷)
- `tests/test_legacy_loader.py` (payload 실패 시 src 폴백/활성 구현 상수)
- `tests/test_public_surfaces.py` (공개 API/시그니처 회귀)

## 5. 빌드

```powershell
python scripts/build_legacy_payload.py --src smartclipboard_app/legacy_main_src.py --out smartclipboard_app/legacy_main_payload.marshal --smoke-import
pyinstaller --clean smartclipboard.spec
```

빌드 결과:

- `dist/SmartClipboard.exe`
- payload/runtime sync: `smartclipboard_app/legacy_main_payload.marshal` + `smartclipboard_app/legacy_main_payload.manifest.json`

## 6. 소스 복원 필요성

장기적으로 구조 분할 리팩토링을 지속하려면 `legacy_main.py` 원본 소스 복원이 필요합니다.  
복원 전에는 로더/payload 호환성을 깨지 않는 변경만 수행합니다.

## 7. CI 검증 (GitHub Actions)

- 워크플로우: `.github/workflows/ci.yml`
- 실행 환경: `windows-latest`
- Python 매트릭스: `3.10`, `3.11`, `3.12`, `3.13`
- 단계:
  - `scripts/build_legacy_payload.py --smoke-import`
  - `scripts/preflight_local.py --skip-payload-build --strict-optional-deps`

## 8. MainWindow 분할 리팩토링 작업 규칙 (2026-03-07)

- `legacy_main_src.MainWindow` 메서드 시그니처는 외부 계약으로 간주하고 유지합니다.
- 실제 구현은 `smartclipboard_app/features/` 도메인 패키지와 controller 계층으로 이동하고, `smartclipboard_app/ui/mainwindow_parts/`는 shim으로 유지합니다.
- `eventFilter` helper에서는 module-level `super()`를 사용하지 않고, 원본 클래스의 fallback 이벤트 필터를 주입받아 호출합니다.
- `scripts/refactor_signal_snapshot.py` 스냅샷은 `legacy_main_src.py` + shim 파일 + feature 구현 파일을 모두 포함해야 합니다.
- 수동 `py_compile` 검증 시 helper/shim뿐 아니라 `features/**/*.py`, `db_parts/**/*.py`, `automation/**/*.py`까지 함께 포함해야 하며, 기본적으로는 `python scripts/preflight_local.py` 실행을 우선합니다.

## 9. Refactor Notes (2026-03-12)

- `smartclipboard_core/database.py` has been split into mixins under `smartclipboard_core/db_parts/`.
- `smartclipboard_core/db_parts/`는 flat facade + subpackage 구조(`search/`, `automation/`, `catalog/`, `retention/`)로 유지합니다.
- `smartclipboard_core/actions.py`는 facade이고 실제 구현은 `smartclipboard_core/automation/`에 있습니다.
- `smartclipboard_app/ui/mainwindow_parts/`는 shim이며 실제 구현은 `smartclipboard_app/features/` 아래에 있습니다.
- Keep `MainWindow` and `ClipboardDB` public signatures stable.
- `scripts/preflight_local.py` now compiles `smartclipboard_core/db_parts/**/*.py`, `smartclipboard_core/automation/**/*.py`, `smartclipboard_app/features/**/*.py` as part of local guard checks.
- Added API surface regression check:
  - `tests/test_public_surfaces.py`
  - `tests/baseline/clipboarddb_public_methods.txt`

# SmartClipboard Pro - Gemini 작업 가이드

## 프로젝트 현황

- 엔트리: `클립모드 매니저.py`
- 앱 부트스트랩: `smartclipboard_app/bootstrap.py`
- 코어 모듈: `smartclipboard_core/`
- 정적 분석 범위: 루트 `pyrightconfig.json`
- 레거시 런타임:
  - `smartclipboard_app/legacy_main.py`는 로더
  - `smartclipboard_app/legacy_main_payload.marshal`을 실행해 기존 동작을 복원
  - `smartclipboard_app/legacy_main_payload.manifest.json`으로 Python/source 동기화를 검증

## 작업 원칙

1. 신규 수정은 `smartclipboard_core/`와 `smartclipboard_app/features/` 우선, `smartclipboard_app/ui/`는 호환 shim/조립 레이어로 취급
2. `클립모드 매니저.py`의 외부 호환 API(export) 유지
3. 빌드 산출물이 payload와 payload manifest를 함께 포함하도록 `smartclipboard.spec` 유지

## 주의

- `legacy_main_payload.marshal`은 바이너리 payload입니다.
- `legacy_main_payload.manifest.json`은 payload와 세트로 관리하는 런타임 동기화 메타데이터입니다.
- `legacy_main.py`에 기존 대형 소스가 있다고 가정하고 라인 단위 리팩토링하면 안 됩니다.
- `pyright`/Pylance 기준선은 현행 유지보수 코드에 맞춰 관리하며, 레거시 보관본과 `legacy_main_src.py`는 기본 분석 범위에서 제외합니다.
- 구조 인벤토리/시그널 스냅샷은 로더 구조 특성상 소스 본문 검증과 의미가 달라질 수 있습니다.
- payload 반영 누락 방지를 위해 `tests/test_payload_sync.py`를 포함한 로컬 preflight를 우선 실행합니다.
- `fetch_title` 액션은 텍스트 전체가 아니라 첫 URL만 추출해 제목 요청하도록 유지합니다.
- `fetch_title`은 로컬/사설/메타데이터 주소를 기본 차단하고, HTML 응답만 제한 크기로 읽는 정책을 유지합니다.
- 동일 비이미지 재복사는 기존 history row를 갱신하는 정책이며 메타데이터를 유지해야 합니다.
- 직접 `clipboard.setText()`를 호출하는 경로는 `smartclipboard_app.ui.clipboard_guard.mark_internal_copy()`를 통해 내부 복사 플래그를 먼저 세팅합니다.
- JSON 마이그레이션(`include_metadata=True`)에는 top-level `collections` 메타데이터가 포함되며 import 시 컬렉션 ID remap이 수행됩니다.
- JSON 마이그레이션 범위는 히스토리 메타데이터 + 컬렉션까지만 의미하며, 스니펫/규칙/핫키/보안 보관함 상태까지 포함하는 것으로 확장하지 않습니다.
- JSON export/import는 `IMAGE` 항목의 `image_data_b64` round-trip을 지원하고, CSV/Markdown은 이미지 BLOB를 제외합니다.
- timezone-aware ISO timestamp는 원본 wall-clock 기준 앱 표준 시각 문자열로 정규화합니다.
- `format_phone`은 `02`, 일반 지역번호, `0505`, `15xx/16xx/18xx` 대표번호까지 처리하는 기준을 유지합니다.
- `copy_rules`의 `custom_replace`는 빈 replacement를 허용하고, 이 경우 삭제 치환으로 취급합니다.
- `FILE` 항목은 목록/상세/미니 창에서 stale/missing 경로 수를 먼저 보여주는 UX를 유지합니다.
- 보안 보관함은 `vault_salt`와 `vault_verification`이 모두 있어야 정상 구성으로 간주하며, 손상 상태는 잠금 화면 Reset 경로로 복구합니다.
- `Ctrl+Shift+Z` paste-last는 pinned 정렬과 무관하게 가장 최근 복사된 항목을 사용해야 합니다.
- 사용자 정렬은 오름/내림차순과 무관하게 pinned-first 정책을 유지해야 합니다.
- 컬렉션 삭제는 휴지통 row의 `collection_id`도 같이 정리하고, 복원 시 없는 컬렉션 참조는 `NULL`로 복원해야 합니다.
- 보안 보관함 복사 버튼은 비밀번호 변경 직후에도 최신 DB row를 다시 읽어 복호화해야 합니다.
- Windows 테스트 임시 경로는 repo-local `.tmp-unittest/`를 사용합니다.
- `smartclipboard.spec`는 `smartclipboard_core`, `smartclipboard_core.automation`, `smartclipboard_app.features`, `smartclipboard_app.ui.mainwindow_parts` 하위 모듈을 hidden import로 자동 수집하도록 유지합니다.
- 2026-04-13 기준 spec 추가 자산은 `legacy_main_payload.manifest.json` 1건이며, 현재 spec에 반영되어 있습니다.

## 검증 커맨드

```powershell
python scripts/preflight_local.py
pyright <touched-files>
```

- 현재 repo-wide `pyright`는 `smartclipboard_core/db_parts/*.py` mixin attribute-access 노이즈가 남아 있으므로, 최소 게이트는 `preflight_local.py`이고 `pyright`는 변경 파일 기준으로 병행합니다.

또는 단계별 실행:

```powershell
pyright <touched-files>
python scripts/build_legacy_payload.py --src smartclipboard_app/legacy_main_src.py --out smartclipboard_app/legacy_main_payload.marshal --smoke-import
python -m py_compile "클립모드 매니저.py" "smartclipboard_app/bootstrap.py" "smartclipboard_app/legacy_main.py" "smartclipboard_app/legacy_main_src.py" "smartclipboard_core/database.py" "smartclipboard_core/actions.py" "smartclipboard_core/worker.py"
python -m unittest discover -s tests -v
```

권장 회귀 테스트:
- `tests/test_core.py`
- `tests/test_ui_dialogs_widgets.py`
- `tests/test_payload_sync.py`
- `tests/test_legacy_loader.py`
- `tests/test_migration_collections.py`
- `tests/test_legacy_ui_contracts.py`
- `tests/test_signal_snapshot.py`
- `tests/test_public_surfaces.py`

## 빌드

```powershell
python scripts/build_legacy_payload.py --src smartclipboard_app/legacy_main_src.py --out smartclipboard_app/legacy_main_payload.marshal --smoke-import
pyinstaller --clean smartclipboard.spec
```

결과:

- `dist/SmartClipboard.exe`

## 향후 리팩토링 전제

본격적인 코드 분할 리팩토링(클래스/메서드 단위 이동)을 재개하려면 `legacy_main.py` 원본 소스 복원이 선행되어야 합니다.

## Refactor Sync (2026-03-12)

- `smartclipboard_core/database.py` is now split into `smartclipboard_core/db_parts/*.py` facades plus subpackages under `search/`, `automation/`, `catalog/`, `retention/`.
- `smartclipboard_core/actions.py` is a public facade and the implementation lives in `smartclipboard_core/automation/`.
- `smartclipboard_app/ui/mainwindow_parts/` is a compatibility shim layer, while actual MainWindow feature logic now lives in `smartclipboard_app/features/`.
- `scripts/preflight_local.py` compiles `db_parts/**/*.py`, `automation/**/*.py`, `features/**/*.py`, `ui/**/*.py` recursively.
- Added API surface regression checks:
  - `tests/test_public_surfaces.py`
  - `tests/baseline/clipboarddb_public_methods.txt`
- `smartclipboard.spec` explicitly collects `smartclipboard_core.db_parts`, `smartclipboard_core.automation`, `smartclipboard_app.features`, `smartclipboard_app.ui.mainwindow_parts` submodules.

## 2026-04-15 Structure Refactor Notes

- `legacy_main_src.MainWindow` keeps its public method surface but now delegates to feature controllers for clipboard, history/table, tray_hotkey, lifecycle, settings, and shell_ui.
- `smartclipboard_app/features/shared/state.py` binds `WindowState`, `WindowServices`, `WindowWidgets` so feature controllers do not depend on the raw Qt window indiscriminately.
- `tests/test_signal_snapshot.py` and `scripts/refactor_signal_snapshot.py` now scan both shim files and feature implementation files to preserve the legacy signal contract while the implementation is split.

## 2026-04-12 Stabilization Notes

- `ExportImportManager` public API still returns `int`, and detailed results live in `last_import_report` / `last_export_report`.
- JSON/CSV import now always creates a pre-import backup and applies each file inside one DB transaction, so partial writes do not survive failures.
- `search_items()` remains FTS-first and only uses LIKE as a zero-hit supplement or true FTS-error fallback. UI warning state should only represent real FTS errors.
- `ClipboardActionManager.fetch_title` uses URL-level in-flight dedupe, an in-memory title cache, and a dedicated `QThreadPool(maxThreadCount=4)`. Late results must re-check the current row URL before saving.
- Synchronous text actions (`format_phone`, `format_email`, `transform`) must update the working text sequentially, and `fetch_title` must resolve its URL from the post-transform final text.
- Replace-text action results must be written back to both the same history row and the live clipboard so stored state and clipboard contents do not diverge.
- `FILE` duplicate detection now depends on `history.file_signature`; keep path canonicalization rules aligned across insert/update/restore code paths.
- Vault clipboard plaintext is tracked only in-process via an armed state and must be conditionally cleared after 30 seconds and again on shutdown if still present.
- `mini_window_enabled` save failures should roll back only that setting and surface `_last_hotkey_error` to the user.
- For CI-equivalent dependency verification, run `python scripts/preflight_local.py --strict-optional-deps`.
- Search queries should preserve DB/FTS relevance order by default, and only apply a client-side sort when the user has explicitly overridden the header sort.
- If JSON import creates collections, refresh `refresh_collection_filter_options()` before reloading the table so the top filter stays in sync.
- Empty search/empty-history paths should still call `update_status_bar(0)` so stale item counts are cleared.

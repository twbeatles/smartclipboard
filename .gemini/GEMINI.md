# SmartClipboard Pro - Gemini 작업 가이드

## 프로젝트 현황

- 엔트리: `클립모드 매니저.py`
- 앱 부트스트랩: `smartclipboard_app/bootstrap.py`
- 코어 모듈: `smartclipboard_core/`
- 정적 분석 범위: 루트 `pyrightconfig.json`
- 레거시 런타임:
  - `smartclipboard_app/legacy_main.py`는 로더
  - `smartclipboard_app/legacy_main_payload.marshal`을 실행해 기존 동작을 복원

## 작업 원칙

1. 신규 수정은 `smartclipboard_core/`와 `smartclipboard_app/ui/` 우선
2. `클립모드 매니저.py`의 외부 호환 API(export) 유지
3. 빌드 산출물이 payload를 포함하도록 `smartclipboard.spec` 유지

## 주의

- `legacy_main_payload.marshal`은 바이너리 payload입니다.
- `legacy_main.py`에 기존 대형 소스가 있다고 가정하고 라인 단위 리팩토링하면 안 됩니다.
- `pyright`/Pylance 기준선은 현행 유지보수 코드에 맞춰 관리하며, 레거시 보관본과 `legacy_main_src.py`는 기본 분석 범위에서 제외합니다.
- 구조 인벤토리/시그널 스냅샷은 로더 구조 특성상 소스 본문 검증과 의미가 달라질 수 있습니다.
- payload 반영 누락 방지를 위해 `tests/test_payload_sync.py`를 포함한 로컬 preflight를 우선 실행합니다.
- `fetch_title` 액션은 텍스트 전체가 아니라 첫 URL만 추출해 제목 요청하도록 유지합니다.
- 동일 비이미지 재복사는 기존 history row를 갱신하는 정책이며 메타데이터를 유지해야 합니다.
- 직접 `clipboard.setText()`를 호출하는 경로는 `smartclipboard_app.ui.clipboard_guard.mark_internal_copy()`를 통해 내부 복사 플래그를 먼저 세팅합니다.
- JSON 마이그레이션(`include_metadata=True`)에는 top-level `collections` 메타데이터가 포함되며 import 시 컬렉션 ID remap이 수행됩니다.
- JSON export/import는 `IMAGE` 항목의 `image_data_b64` round-trip을 지원하고, CSV/Markdown은 이미지 BLOB를 제외합니다.
- `Ctrl+Shift+Z` paste-last는 pinned 정렬과 무관하게 가장 최근 복사된 항목을 사용해야 합니다.
- 사용자 정렬은 오름/내림차순과 무관하게 pinned-first 정책을 유지해야 합니다.
- 컬렉션 삭제는 휴지통 row의 `collection_id`도 같이 정리하고, 복원 시 없는 컬렉션 참조는 `NULL`로 복원해야 합니다.
- 보안 보관함 복사 버튼은 비밀번호 변경 직후에도 최신 DB row를 다시 읽어 복호화해야 합니다.
- Windows 테스트 임시 경로는 repo-local `.tmp-unittest/`를 사용합니다.
- `smartclipboard.spec`는 `smartclipboard_core`, `smartclipboard_app.ui.mainwindow_parts` 하위 모듈을 hidden import로 자동 수집하도록 유지합니다.

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

- `smartclipboard_core/database.py` is now split into `smartclipboard_core/db_parts/*.py` mixins.
- `smartclipboard_app/ui/mainwindow_parts/` now includes:
  - `theme_style_sections.py`
  - `ui_init_sections.py`, `ui_dragdrop_ops.py`
  - `tray_hotkey_ops.py`, `status_lifecycle_ops.py`, `clipboard_runtime_ops.py`
- `scripts/preflight_local.py` compiles `db_parts/*.py` and `mainwindow_parts/*.py`.
- Added API surface regression checks:
  - `tests/test_public_surfaces.py`
  - `tests/baseline/clipboarddb_public_methods.txt`
- `smartclipboard.spec` explicitly collects `smartclipboard_core.db_parts` submodules.

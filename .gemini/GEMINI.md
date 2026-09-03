# SmartClipboard Pro - Gemini 작업 가이드

## 프로젝트 현황

- 엔트리: `클립모드 매니저.py`
- 앱 부트스트랩: `smartclipboard_app/bootstrap.py`
- 코어 모듈: `smartclipboard_core/` (`automation/`, `action_palette/`, `db_parts/`)
- 네이티브 코어: `native/` (Rust + Tauri 2 + React 19 + TypeScript + Tailwind CSS)
- 정적 분석 범위: 루트 `pyrightconfig.json`
- 레거시 런타임:
  - `smartclipboard_app/legacy_main.py`는 로더
  - `smartclipboard_app/legacy_main_payload.marshal`을 실행해 기존 동작을 복원
  - `smartclipboard_app/legacy_main_payload.manifest.json`으로 Python/source와 payload size/SHA-256 동기화를 검증

## 작업 원칙

1. 신규 수정은 `smartclipboard_core/`와 `smartclipboard_app/features/` 우선, `smartclipboard_app/ui/`는 호환 shim/조립 레이어로 취급
2. 네이티브 관련 수정은 `native/` 하위 모듈(`src-tauri/src/` 및 `src/`)에 반영하며 기존 DB 바이너리 호환성 100% 유지
3. `클립모드 매니저.py`의 외부 호환 API(export) 유지
4. 빌드 산출물이 payload와 payload manifest를 함께 포함하도록 `smartclipboard.spec` 유지

## 주의

- `legacy_main_payload.marshal`은 바이너리 payload입니다.
- `legacy_main_payload.manifest.json`은 payload와 세트로 관리하는 런타임 동기화 메타데이터입니다.
- `legacy_main.py`에 기존 대형 소스가 있다고 가정하고 라인 단위 리팩토링하면 안 됩니다.
- `pyright`/Pylance 기준선은 현행 유지보수 코드 repo-wide 0 errors에 맞춰 관리하며, 레거시 보관본과 `legacy_main_src.py`는 기본 분석 범위에서 제외합니다.
- 구조 인벤토리/시그널 스냅샷은 로더 구조 특성상 소스 본문 검증과 의미가 달라질 수 있습니다.
- payload 반영 누락 방지를 위해 `tests/test_payload_sync.py`를 포함한 로컬 preflight를 우선 실행합니다.
- `fetch_title` 액션은 텍스트 전체가 아니라 첫 URL만 추출해 제목 요청하도록 유지합니다.
- `fetch_title`은 로컬/사설/메타데이터 주소를 기본 차단하고, HTML 응답만 제한 크기로 읽으며, URL title cache는 256개/24시간 TTL 제한을 유지합니다.
- 동일 비이미지 재복사는 기존 history row를 갱신하는 정책이며 메타데이터를 유지해야 합니다.
- 직접 `clipboard.setText()`를 호출하는 경로는 `smartclipboard_app.ui.clipboard_guard.mark_internal_copy()`를 통해 내부 복사 플래그를 먼저 세팅합니다.
- Action Palette 텍스트 결과도 동일하게 `mark_internal_copy()` 후 `setText()`하며, 변환 텍스트는 선택 history 행에 `replace_text_item_or_merge()`로 writeback 합니다. 자동 `ClipboardActionManager`를 다시 타지 않습니다.
- Palette `fetch_title`는 기존 `validate_title_fetch_url` 사전검증·title cache·inflight 합치기·종료 시 disconnect를 유지합니다.
- JSON 마이그레이션(`include_metadata=True`)에는 top-level `collections` 메타데이터가 포함되며 import 시 컬렉션 ID remap이 수행됩니다.
- JSON 마이그레이션 범위는 히스토리 메타데이터 + 컬렉션까지만 의미하며, 스니펫/규칙/핫키/보안 보관함 상태까지 포함하는 것으로 확장하지 않습니다.
- JSON export/import는 `IMAGE` 항목의 `image_data_b64` round-trip을 지원하고, CSV/Markdown은 이미지 BLOB를 제외합니다.
- CSV import는 export된 고정 상태와 사용 횟수를 복원하되, CSV에 pin order가 없으므로 pinned 항목은 기존 pinned 목록 뒤에 import 순서대로 붙입니다.
- JSON import는 top-level `items` list를 필수로 검증하고 metadata 타입/범위를 정규화합니다.
- timezone-aware ISO timestamp는 원본 wall-clock 기준 앱 표준 시각 문자열로 정규화합니다.
- `format_phone`은 `02`, 일반 지역번호, `0505`, `15xx/16xx/18xx` 대표번호까지 처리하는 기준을 유지합니다.
- `copy_rules`의 `custom_replace`는 빈 replacement를 허용하고, 이 경우 삭제 치환으로 취급합니다.
- `FILE` 항목은 목록/상세/미니 창에서 stale/missing 경로 수를 먼저 보여주는 UX를 유지합니다.
- 보안 보관함은 `vault_salt`와 `vault_verification`이 모두 있어야 정상 구성으로 간주하며, 손상 상태는 잠금 화면 Reset 경로로 복구합니다.
- `max_history` 감소와 자동 cleanup은 고정되지 않은 오래된 항목을 휴지통 없이 영구 삭제하는 정책이므로 UI/문서 경고를 유지합니다.
- `Ctrl+Shift+Z` paste-last는 pinned 정렬과 무관하게 가장 최근 복사된 항목을 사용해야 합니다.
- 사용자 정렬은 오름/내림차순과 무관하게 pinned-first 정책을 유지해야 합니다.
- 컬렉션 삭제는 휴지통 row의 `collection_id`도 같이 정리하고, 복원 시 없는 컬렉션 참조는 `NULL`로 복원해야 합니다.
- 보안 보관함 복사 버튼은 비밀번호 변경 직후에도 최신 DB row를 다시 읽어 복호화해야 합니다.
- Windows 테스트 임시 경로는 repo-local `.tmp-unittest/`를 사용합니다.
- `smartclipboard.spec`는 `smartclipboard_core`, `smartclipboard_core.automation`, `smartclipboard_app.features`, `smartclipboard_app.ui.mainwindow_parts` 하위 모듈을 hidden import로 자동 수집하도록 유지합니다.
- 2026-05-11 기준 privacy debounce, `deleted_history.url_title`, action writeback merge, restore full/minimal 검증, 핫키 실패 알림, 설정 write/read-back, 텍스트 1MB 제한은 기존 `collect_submodules` 규칙 안에 있으며 spec 추가 자산은 없습니다.
- 2026-06-10 SOLID 분할 이후에도 새 모듈은 `smartclipboard_app.features`와 `smartclipboard_core.db_parts` 하위에 있으므로 spec 추가 hidden import/datas는 필요 없습니다.
- 2026-08-14 Contextual Action Palette는 `smartclipboard_core.action_palette`와 `smartclipboard_app.features.action_palette`에 있으며 기존 `collect_submodules` 범위로 포함됩니다. spec 추가 hidden import/datas는 없습니다.
- `MainWindow.__init__` orchestration은 `smartclipboard_app/features/shell/window_bootstrap.py`, dialog launcher는 `features/dialogs/`, history interaction은 `features/history/interactions.py`, QSS section builders는 `features/settings/styles/`, import/export helper는 `features/import_export/services.py`에 둡니다.
- `smartclipboard_core/db_parts/history_ops.py`는 facade이고 실제 history 구현은 `smartclipboard_core/db_parts/history/` 하위 책임별 모듈에 있습니다.
- `.codegraph/`는 로컬 분석 인덱스이며 `.gitignore` 제외 대상입니다.
- 텍스트 clipboard는 기본 1MB 초과 시 저장하지 않고 status/toast로 사용자에게 알립니다. 이미지 5MB 제한은 유지합니다.
- DB 복원은 full 검증을 우선하고, legacy/minimal 백업은 기능 데이터 누락 가능성을 경고한 뒤에만 진행합니다. replace 전후 target DB의 `-wal`, `-shm` sidecar를 정리합니다.
- JSON migration export/import는 `url_title`을 포함하며, CSV/Markdown export 정책은 기존 범위를 유지합니다.

## 검증 커맨드

### Python 에디션 검증

```powershell
python scripts/preflight_local.py --with-pyright
```

- `pyright`는 루트 `pyrightconfig.json` 기준 repo-wide 0 errors를 유지합니다.

또는 단계별 실행:

```powershell
pyright
python scripts/build_legacy_payload.py --src smartclipboard_app/legacy_main_src.py --out smartclipboard_app/legacy_main_payload.marshal --smoke-import
python -m py_compile "클립모드 매니저.py" "smartclipboard_app/bootstrap.py" "smartclipboard_app/legacy_main.py" "smartclipboard_app/legacy_main_src.py" "smartclipboard_core/database.py" "smartclipboard_core/actions.py" "smartclipboard_core/worker.py"
python -m unittest discover -s tests -v
```

### Rust + Tauri 2 네이티브 에디션 검증

```powershell
# 1. Rust 단위/패리티/통합 테스트 (30건)
cargo test --manifest-path native/src-tauri/Cargo.toml

# 2. Rust Clippy 린터 점검 (0 warnings)
cargo clippy --manifest-path native/src-tauri/Cargo.toml

# 3. 프론트엔드 TypeScript & Vite 번들 검증
cd native
npm run build
```

## 빌드

### Python 에디션 (PyInstaller)

```powershell
python scripts/build_legacy_payload.py --src smartclipboard_app/legacy_main_src.py --out smartclipboard_app/legacy_main_payload.marshal --smoke-import
pyinstaller --clean smartclipboard.spec
```

결과: `dist/SmartClipboard.exe`

### Native 에디션 (Tauri 2)

```powershell
cd native
npm run tauri build
```

결과: `native/src-tauri/target/release/smartclipboard-native.exe` 및 설치 프로그램

## 2026-09-03 Rust + Tauri 2 Native Architecture Notes

- `native/`에 완전한 Rust 코어 및 Tauri 2 + React 19 UI 셸이 구현되었습니다.
- 기존 SQLite WAL `clipboard_history_v6.db` 스키마와 100% 무변경 상호운용됩니다.
- Windows 네이티브 `WM_CLIPBOARDUPDATE` 이벤트 리스너를 사용하여 폴링 없는 초저지연 클립보드 감시가 수행됩니다.
- PBKDF2-HMAC-SHA256 (480,000 iter) 및 Fernet (AES-128-CBC + HMAC-SHA256) 암호화 레이어는 Python cryptography와 100% 크로스 복호화/암호화 호환성을 가집니다.
- `docs/NATIVE_PARITY_MATRIX.md`에서 100% 완료된 기능 동등성 매트릭스를 확인할 수 있습니다.

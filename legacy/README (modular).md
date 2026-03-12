# SmartClipboard Pro v10.6

Windows용 PyQt6 기반 클립보드 매니저입니다.

> ⚠️ 이 문서는 모듈화 전환 당시의 보관 문서입니다. 최신 기준은 루트 `README.md`와 `pyrightconfig.json`입니다.

## 현재 상태

- 엔트리 파일: `클립모드 매니저.py` (호환 파사드)
- 앱 부트스트랩: `smartclipboard_app/bootstrap.py`
- 코어 로직: `smartclipboard_core/`
- 정적 분석 범위: 루트 `pyrightconfig.json` (현행 유지보수 대상 기준)
- 레거시 런타임: `smartclipboard_app/legacy_main.py`
  - 현재 `legacy_main.py`는 소스 본문이 아니라 `legacy_main_payload.marshal`을 로드/실행하는 호환 로더입니다.
  - payload 파일: `smartclipboard_app/legacy_main_payload.marshal`

## 주요 기능

- 클립보드 히스토리 저장/검색
- 고정, 북마크, 태그, 컬렉션
- 상단 컬렉션 필터(전체/미분류/개별 컬렉션)
- 보안 보관함(AES)
- 클립보드 액션 자동화
- 스니펫/휴지통/미니 윈도우
- JSON/CSV/Markdown 내보내기
- JSON 마이그레이션 모드(메타데이터 + 컬렉션 정의/ID 매핑 정보 포함) 내보내기/가져오기

## 프로젝트 구조

```text
smartclipboard-main/
├── 클립모드 매니저.py
├── smartclipboard.spec
├── smartclipboard_app/
│   ├── bootstrap.py
│   ├── legacy_main.py                  # marshal loader
│   ├── legacy_main_payload.marshal     # legacy runtime payload
│   ├── managers/
│   └── ui/
├── smartclipboard_core/
│   ├── database.py
│   ├── actions.py
│   └── worker.py
└── tests/
```

## 실행

```powershell
pip install -r requirements.txt
python "클립모드 매니저.py"
```

## 테스트

```powershell
python scripts/preflight_local.py
```

정적 분석은 별도 실행:

```powershell
pyright
```

또는 단계별 실행:

```powershell
pyright
python scripts/build_legacy_payload.py --src smartclipboard_app/legacy_main_src.py --out smartclipboard_app/legacy_main_payload.marshal --smoke-import
python -m py_compile "클립모드 매니저.py" "smartclipboard_app/bootstrap.py" "smartclipboard_app/legacy_main.py" "smartclipboard_app/legacy_main_src.py" "smartclipboard_core/database.py" "smartclipboard_core/actions.py" "smartclipboard_core/worker.py"
python -m unittest discover -s tests -v
```

권장 회귀 테스트:
- `tests/test_payload_sync.py`
- `tests/test_migration_collections.py`
- `tests/test_legacy_ui_contracts.py`
- `tests/test_signal_snapshot.py`

## 빌드

```powershell
pyinstaller --clean smartclipboard.spec
```

결과물:

- `dist/SmartClipboard.exe`

`smartclipboard.spec`는 `smartclipboard_app/legacy_main_payload.marshal`을 `datas`로 포함하며, `smartclipboard_core`와 `smartclipboard_app.ui.mainwindow_parts` 하위 모듈을 hidden import로 자동 수집합니다.

## 중요 참고

- 현재 `legacy_main`이 marshal payload 로더이므로, `smartclipboard_app/legacy_main.py` 소스만으로는 클래스/시그널 구조를 직접 추적하기 어렵습니다.
- `pyright`/Pylance는 현행 유지보수 코드만 기본 분석 대상으로 보며, `smartclipboard_app/legacy_main_src.py`와 `legacy/` 보관본은 제외됩니다.
- 구조 리팩토링을 재개하려면 신뢰 가능한 원본 `legacy_main.py` 소스 복원이 선행되어야 합니다.
- 2026-03 정합성 패치로 fetch_title 액션의 첫 URL 추출 경로, 복합 필터 검색 경로, 휴지통 다중선택, minimized 시작 안정성, JSON 컬렉션 remap이 보강되었습니다.

## 문서 정합성 기준 (2026-03-07)

- 상세 변경 이력은 루트 `README.md`를 기준으로 관리합니다.
- 개발 가이드는 `claude.md`, `.gemini/GEMINI.md`와 동일한 테스트/빌드 기준을 따릅니다.

## Refactor Sync (2026-03-12)

- MainWindow helper modules have expanded under `smartclipboard_app/ui/mainwindow_parts/`.
- DB layer is split to `smartclipboard_core/db_parts/` with `database.py` as composition entrypoint.
- Local guard now compiles both helper folders via `scripts/preflight_local.py`.
- Added API surface tests: `tests/test_public_surfaces.py` and `tests/baseline/clipboarddb_public_methods.txt`.
- Packaging guard: `smartclipboard.spec` now explicitly includes `smartclipboard_core.db_parts` collection.

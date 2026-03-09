# SmartClipboard Pro - Claude 작업 가이드

## 1. 현재 아키텍처 요약

- 실행 진입점: `클립모드 매니저.py`
- 부트스트랩: `smartclipboard_app/bootstrap.py`
- 코어 비즈니스 로직: `smartclipboard_core/`
- 정적 분석 범위: 루트 `pyrightconfig.json` (현행 유지보수 대상 기준)
- 레거시 런타임:
  - `smartclipboard_app/legacy_main.py`는 **marshal payload 로더**
  - 실제 본문은 `smartclipboard_app/legacy_main_payload.marshal`

## 2. 작업 우선순위

1. 새 기능/수정은 가능한 한 `smartclipboard_core/` 또는 `smartclipboard_app/ui/`에 반영
2. 파사드 호환성(`클립모드 매니저.py` export) 유지
3. 빌드 시 payload 누락 방지 (`smartclipboard.spec` datas)

## 3. 변경 시 주의사항

- `legacy_main_payload.marshal`은 텍스트 diff/리뷰가 어려운 바이너리 payload입니다.
- `legacy_main.py`를 소스 본문 파일로 가정하고 리팩토링하면 안 됩니다.
- `pyright`/Pylance 진단은 기본적으로 `legacy/클립모드 매니저 (legacy).py`와 `smartclipboard_app/legacy_main_src.py`를 제외한 현행 코드 기준으로 맞춥니다.
- UI/DB 기능 변경을 EXE에 반영하려면 `scripts/build_legacy_payload.py`로 `legacy_main_payload.marshal`을 재생성한 뒤 빌드해야 합니다.
- `fetch_title` 액션은 텍스트 전체가 아니라 첫 URL만 추출해 제목 요청하도록 유지합니다.
- JSON 마이그레이션 포맷(`include_metadata=True`)은 `items` 외에 top-level `collections` 메타데이터(legacy_id/name/icon/color)를 포함하며, import 시 컬렉션 ID remap을 수행합니다.
- `smartclipboard.spec`는 `smartclipboard_core`, `smartclipboard_app.ui.mainwindow_parts` 하위 모듈을 hidden import로 자동 수집하도록 유지합니다.
- 구조 검증 스크립트:
  - `scripts/refactor_symbol_inventory.py`
  - `scripts/refactor_signal_snapshot.py`
  - payload 반영 동기화 검증: `tests/test_payload_sync.py`
  - 현재 로더 구조에서는 로더 기반 결과와 소스 본문 기준 결과가 다를 수 있으므로 `legacy_main_src.py` 기준으로 확인합니다.

## 4. 필수 검증

```powershell
pyright
python scripts/preflight_local.py
```

또는 단계별 실행:

```powershell
pyright
python scripts/build_legacy_payload.py --src smartclipboard_app/legacy_main_src.py --out smartclipboard_app/legacy_main_payload.marshal --smoke-import
python -m py_compile "클립모드 매니저.py" "smartclipboard_app/bootstrap.py" "smartclipboard_app/legacy_main.py" "smartclipboard_app/legacy_main_src.py" "smartclipboard_core/database.py" "smartclipboard_core/actions.py" "smartclipboard_core/worker.py"
python -m unittest discover -s tests -v
```

권장 회귀 포인트:
- `tests/test_payload_sync.py` (payload 런타임 시그니처/URL 액션)
- `tests/test_migration_collections.py` (JSON 마이그레이션 컬렉션 메타/ID remap)
- `tests/test_legacy_ui_contracts.py` (레거시 UI 계약: 토스트 호출/선택모드/가시성 가드)
- `tests/test_signal_snapshot.py` (MainWindow 분할 구조 시그널 스냅샷)

## 5. 빌드

```powershell
pyinstaller --clean smartclipboard.spec
```

빌드 결과:

- `dist/SmartClipboard.exe`

## 6. 소스 복원 필요성

장기적으로 구조 분할 리팩토링을 지속하려면 `legacy_main.py` 원본 소스 복원이 필요합니다.  
복원 전에는 로더/payload 호환성을 깨지 않는 변경만 수행합니다.

## 7. MainWindow 분할 리팩토링 작업 규칙 (2026-03-07)

- `legacy_main_src.MainWindow` 메서드 시그니처는 외부 계약으로 간주하고 유지합니다.
- 본문 분할은 `smartclipboard_app/ui/mainwindow_parts/` helper 함수로 수행합니다.
- `eventFilter` helper에서는 module-level `super()`를 사용하지 않고, 원본 클래스의 fallback 이벤트 필터를 주입받아 호출합니다.
- `scripts/refactor_signal_snapshot.py` 스냅샷은 `legacy_main_src.py` + `mainwindow_parts/*.py`를 모두 포함해야 합니다.
- 수동 `py_compile` 검증 시 helper 모듈도 함께 포함해야 하며, 기본적으로는 `python scripts/preflight_local.py` 실행을 우선합니다.

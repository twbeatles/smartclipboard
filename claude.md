# SmartClipboard Pro - Claude 작업 가이드

## 1. 현재 아키텍처 요약

- 실행 진입점: `클립모드 매니저.py`
- 부트스트랩: `smartclipboard_app/bootstrap.py`
- 코어 비즈니스 로직: `smartclipboard_core/`
- 레거시 런타임:
  - `smartclipboard_app/legacy_main.py`는 **marshal payload 로더**
  - 실제 본문은 `smartclipboard_app/legacy_main_payload.marshal`
  - 개발/테스트(비-frozen) 환경에서 payload가 없으면 `legacy_main_src.py`로 자동 폴백

## 2. 작업 우선순위

1. 새 기능/수정은 가능한 한 `smartclipboard_core/` 또는 `smartclipboard_app/ui/`에 반영
2. 파사드 호환성(`클립모드 매니저.py` export) 유지
3. 빌드 시 payload 누락 방지 (`smartclipboard.spec` datas)

## 3. 변경 시 주의사항

- `legacy_main_payload.marshal`은 텍스트 diff/리뷰가 어려운 바이너리 payload입니다.
- `legacy_main.py`를 소스 본문 파일로 가정하고 리팩토링하면 안 됩니다.
- UI/DB 기능 변경을 EXE에 반영하려면 `scripts/build_legacy_payload.py`로 `legacy_main_payload.marshal`을 재생성한 뒤 빌드해야 합니다.
- 비-frozen 소스 실행/테스트는 payload가 없어도 동작할 수 있으나, EXE 빌드/배포 검증에서는 payload 존재를 반드시 확인해야 합니다.
- 구조 검증 스크립트:
  - `scripts/refactor_symbol_inventory.py`
  - `scripts/refactor_signal_snapshot.py`
  - 현재 로더 구조에서는 결과가 소스 본문 기준 검증과 다를 수 있습니다.

## 4. 필수 검증

```powershell
python -m py_compile "클립모드 매니저.py" "smartclipboard_app/bootstrap.py" "smartclipboard_app/legacy_main.py" "smartclipboard_core/database.py" "smartclipboard_core/actions.py" "smartclipboard_core/worker.py"
python -m unittest discover -s tests -v
```

## 5. 빌드

```powershell
pyinstaller smartclipboard.spec
```

빌드 결과:

- `dist/SmartClipboard.exe`

## 6. 소스 복원 필요성

장기적으로 구조 분할 리팩토링을 지속하려면 `legacy_main.py` 원본 소스 복원이 필요합니다.  
복원 전에는 로더/payload 호환성을 깨지 않는 변경만 수행합니다.

## 7. 최신 안정성 반영 메모 (2026-02-19)

- `smartclipboard_core/database.py`
  - `search_items()` 필터 일관성 개선: 빈 쿼리에서도 `tag/type/bookmark/collection/limit` 동시 적용
  - FTS/LIKE 공통 필터 규칙 정렬
- `smartclipboard_app/legacy_main_src.py`
  - `col:<name>` 미존재 컬렉션은 명시적으로 0건 반환
- `smartclipboard_core/backup_zip.py`
  - ZIP import 단일 트랜잭션 처리(실패 시 전체 롤백, partial commit 방지)
- 테스트 보강:
  - `tests/test_core.py`, `tests/test_backup_zip.py`, `tests/test_symbol_inventory.py`

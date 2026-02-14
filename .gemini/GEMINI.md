# SmartClipboard Pro - Gemini 작업 가이드

## 프로젝트 현황

- 엔트리: `클립모드 매니저.py`
- 앱 부트스트랩: `smartclipboard_app/bootstrap.py`
- 코어 모듈: `smartclipboard_core/`
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
- 구조 인벤토리/시그널 스냅샷은 로더 구조 특성상 소스 본문 검증과 의미가 달라질 수 있습니다.

## 검증 커맨드

```powershell
python -m py_compile "클립모드 매니저.py" "smartclipboard_app/bootstrap.py" "smartclipboard_app/legacy_main.py" "smartclipboard_core/database.py" "smartclipboard_core/actions.py" "smartclipboard_core/worker.py"
python -m unittest discover -s tests -v
```

## 빌드

```powershell
pyinstaller smartclipboard.spec
```

결과:

- `dist/SmartClipboard.exe`

## 향후 리팩토링 전제

본격적인 코드 분할 리팩토링(클래스/메서드 단위 이동)을 재개하려면 `legacy_main.py` 원본 소스 복원이 선행되어야 합니다.

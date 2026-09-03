# 📋 SmartClipboard Pro (Python Legacy Edition)

> 이 디렉터리는 SmartClipboard Pro의 기존 Python/PyQt6 구현체 보관소입니다.  
> 2026-09-03 네이티브 전환(Rust + Tauri 2)에 따라 루트 디렉터리가 네이티브 에디션으로 승격되었으며, Python 구현체는 참조 및 백업 목적으로 이곳에 온전히 보존되어 있습니다.

---

## 디렉터리 구성

- `smartclipboard_app/`: PyQt6 UI 및 애플리케이션 기능 모듈
- `smartclipboard_core/`: SQLite DB 및 자동화/액션 코어
- `tests/`: 파이썬 회귀 테스트 스위트 (230건)
- `scripts/`: 로컬 사전 점검(`preflight_local.py`) 및 레거시 빌드 스크립트
- `requirements.txt`: 파이썬 의존성 정의
- `smartclipboard.spec`: PyInstaller 빌드 명세서
- `클립모드 매니저.py`: 파이썬 진입점 스크립트

---

## 실행 및 테스트 방법

```powershell
# 가상환경 진입 및 의존성 설치
pip install -r legacy/python/requirements.txt

# 파이썬 앱 실행
python "legacy/python/클립모드 매니저.py"

# 회귀 테스트 실행
python -m pytest legacy/python/tests
```

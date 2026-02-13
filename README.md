# SmartClipboard Pro v10.6

Windows용 PyQt6 기반 클립보드 매니저입니다.

## 현재 상태

- 엔트리 파일: `클립모드 매니저.py` (호환 파사드)
- 앱 부트스트랩: `smartclipboard_app/bootstrap.py`
- 코어 로직: `smartclipboard_core/`
- 레거시 런타임: `smartclipboard_app/legacy_main.py`
  - 현재 `legacy_main.py`는 소스 본문이 아니라 `legacy_main_payload.marshal`을 로드/실행하는 호환 로더입니다.
  - payload 파일: `smartclipboard_app/legacy_main_payload.marshal`

## 주요 기능

- 클립보드 히스토리 저장/검색
- 고정, 북마크, 태그, 컬렉션
- 보안 보관함(AES)
- 클립보드 액션 자동화
- 스니펫/휴지통/미니 윈도우
- JSON/CSV/Markdown 내보내기

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
python -m py_compile "클립모드 매니저.py" "smartclipboard_app/bootstrap.py" "smartclipboard_app/legacy_main.py" "smartclipboard_core/database.py" "smartclipboard_core/actions.py" "smartclipboard_core/worker.py"
python -m unittest discover -s tests -v
```

## 빌드

```powershell
pyinstaller smartclipboard.spec
```

결과물:

- `dist/SmartClipboard.exe`

`smartclipboard.spec`는 `smartclipboard_app/legacy_main_payload.marshal`을 `datas`로 포함하도록 설정되어 있습니다.

## 중요 참고

- 현재 `legacy_main`이 marshal payload 로더이므로, `smartclipboard_app/legacy_main.py` 소스만으로는 클래스/시그널 구조를 직접 추적하기 어렵습니다.
- 구조 리팩토링을 재개하려면 신뢰 가능한 원본 `legacy_main.py` 소스 복원이 선행되어야 합니다.

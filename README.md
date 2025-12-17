# 📋 SmartClipboard Pro v6.1

**고급 클립보드 매니저** - PyQt6 기반 Windows 클립보드 히스토리 관리 도구

![Python](https://img.shields.io/badge/Python-3.8+-blue?logo=python)
![PyQt6](https://img.shields.io/badge/PyQt6-6.0+-green?logo=qt)
![Platform](https://img.shields.io/badge/Platform-Windows-lightgrey?logo=windows)

---

## ✨ 주요 기능

### 📋 클립보드 관리
- **자동 히스토리 저장** - 텍스트, 이미지 자동 캡처
- **스마트 분류** - 텍스트, 링크, 코드, 색상, 이미지 자동 분류
- **고정 기능** - 중요한 항목 상단 고정
- **검색 & 필터** - 빠른 검색 및 유형별 필터링
- **사용 횟수 추적** - 자주 사용하는 항목 확인

### 🏷️ 태그 시스템 (NEW)
- **커스텀 태그** - 항목에 태그 추가/편집
- **빠른 태그** - 업무, 개인, 중요 등 원클릭 태그
- **우클릭 → 🏷️ 태그 편집**

### 🔗 다중 선택 & 병합 (NEW)
- **Ctrl/Shift+클릭**으로 여러 항목 선택
- **병합 기능** - 구분자(줄바꿈/콤마/공백/탭) 선택
- **우클릭 → 🔗 N개 병합**

### 📝 스니펫 관리
- **템플릿 저장** - 자주 쓰는 텍스트 저장
- **템플릿 변수** - `{{date}}`, `{{time}}`, `{{random:N}}` 지원
- **편집 → 📝 스니펫 관리...**

### 📊 히스토리 대시보드 (NEW)
- **통계 보기** - 총 항목, 고정, 오늘 복사 개수
- **유형별 분포** - 텍스트/링크/이미지 비율
- **Top 5** - 자주 복사한 항목
- **보기 → 📊 히스토리 통계...**

### ⚙️ 복사 규칙 자동화 (NEW)
- **자동 변환** - 패턴 매칭 후 자동 변환
- **동작** - trim, lowercase, uppercase, remove_newlines
- **설정 → ⚙️ 복사 규칙 관리...**

### 🎨 테마 시스템
- **다크 모드** - 기본 다크 테마
- **라이트 모드** - 밝은 테마
- **오션 모드** - 개발자 친화적 테마

### 🔧 편의 기능
- **QR 코드 생성** - 텍스트를 QR 코드로 변환
- **구글 검색** - 선택 텍스트 바로 검색
- **서식 정리** - 줄바꿈 정규화, JSON 포맷팅 (NEW)
- **텍스트 변환** - 대/소문자, 공백 제거
- **이미지 저장** - 클립보드 이미지 PNG 저장
- **히스토리 내보내기** - TXT 파일로 백업

---

## ⌨️ 키보드 단축키

| 단축키 | 기능 |
|--------|------|
| `Ctrl+Shift+V` | 창 표시/숨기기 (글로벌) |
| `Ctrl+C` | 선택 항목 복사 |
| `Enter` | 복사 후 붙여넣기 |
| `Delete` | 선택 항목 삭제 |
| `Ctrl+P` | 고정/해제 토글 |
| `Ctrl+F` | 검색창 포커스 |
| `Ctrl/Shift+클릭` | 다중 선택 |
| `Escape` | 창 숨기기 |
| `Ctrl+Q` | 프로그램 종료 |

---

## 🚀 설치 방법

### 요구 사항
- Python 3.8+
- Windows OS

### 의존성 설치
```bash
pip install PyQt6 keyboard qrcode[pil]
```

### 실행
```bash
python "클립모드 매니저.py"
```

### EXE 빌드
```bash
pip install pyinstaller
pyinstaller smartclipboard.spec
```

---

## 📁 파일 구조

```
smartclipboard/
├── 클립모드 매니저.py      # 메인 프로그램
├── smartclipboard.spec     # PyInstaller 빌드 설정
├── clipboard_history_v6.db # SQLite 데이터베이스 (자동 생성)
├── clipboard_manager.log   # 로그 파일 (자동 생성)
└── README.md
```

---

## 🔄 v6.1 변경사항

### 새 기능
- 🏷️ 태그 시스템 - 항목에 커스텀 태그 추가
- 🔗 다중 선택 & 병합 - 여러 항목 결합
- ✨ 템플릿 변수 - `{{date}}`, `{{time}}`, `{{random:N}}` 등
- 📊 히스토리 대시보드 - 통계 및 분석
- ⚙️ 복사 규칙 자동화 - 패턴 기반 자동 변환
- 📋 서식 정리 - 줄바꿈 정규화, JSON 포맷팅

### 개선사항
- DB 스키마 확장 (tags, copy_rules)
- 컨텍스트 메뉴 확장
- 다중 선택 지원 (ExtendedSelection)

---

## ⚙️ 설정

### 시작 시 자동 실행
설정 → 🚀 시작 시 자동 실행

### 테마 변경
보기 → 🎨 테마 → 원하는 테마 선택

### 항상 위 고정
보기 → 📌 항상 위 고정

---

## 📜 라이선스

MIT License

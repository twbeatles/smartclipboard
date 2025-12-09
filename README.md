# 📋 SmartClipboard Pro v6.0

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

### 🎨 테마 시스템
- **다크 모드** - 기본 다크 테마
- **라이트 모드** - 밝은 테마
- **오션 모드** - 개발자 친화적 테마

### 🔧 편의 기능
- **QR 코드 생성** - 텍스트를 QR 코드로 변환
- **구글 검색** - 선택 텍스트 바로 검색
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

---

## 📁 파일 구조

```
smartclipboard/
├── 클립모드 매니저.py   # 메인 프로그램
├── clipboard_history_v6.db  # SQLite 데이터베이스 (자동 생성)
├── clipboard_manager.log    # 로그 파일 (자동 생성)
└── README.md
```

---

## ⚙️ 설정

### 시작 시 자동 실행
메뉴 → 설정 → 🚀 시작 시 자동 실행

### 테마 변경
메뉴 → 보기 → 🎨 테마 → 원하는 테마 선택

### 항상 위 고정
메뉴 → 보기 → 📌 항상 위 고정

---

## 🔄 v6.0 변경사항

### 새 기능
- 3가지 테마 지원 (다크/라이트/오션)
- 키보드 단축키 시스템
- 설정 다이얼로그
- 사용 횟수 추적
- 상태바 통계 표시
- 확장된 색상 분석 (HEX, RGB, HSL)
- 스니펫 기능 (DB 준비 완료)

### 개선사항
- 로깅 시스템 추가
- 스레드 안전성 강화 (DB Lock)
- HotkeyListener 버그 수정
- 예외 처리 개선
- UI/UX 전면 개선

---

## 📜 라이선스

MIT License

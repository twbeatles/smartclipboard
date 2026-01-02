# 📋 SmartClipboard Pro v8.0

> 강력한 Windows 클립보드 매니저 - PyQt6 기반

![Version](https://img.shields.io/badge/version-8.0-blue)
![Python](https://img.shields.io/badge/python-3.10+-green)
![Platform](https://img.shields.io/badge/platform-Windows-lightgrey)

## ✨ 주요 기능

### 📝 클립보드 관리
- **자동 히스토리 저장**: 텍스트, 이미지, 링크 자동 기록
- **스마트 분류**: TEXT, LINK, IMAGE, CODE, COLOR, FILE 타입 자동 감지
- **검색 및 필터링**: 빠른 검색, 태그 및 유형별 필터
- **항목 고정**: 중요 항목 상단 고정, 드래그로 순서 변경

### � v8.0 신규: 보안 보관함
- AES-256 암호화로 민감 정보 보호
- 마스터 비밀번호 설정
- 5분 비활성 시 자동 잠금

### ⚡ v8.0 신규: 클립보드 자동화
- 정규식 기반 패턴 매칭
- URL 복사 시 제목 자동 가져오기
- 전화번호/이메일 자동 포맷팅

### 📋 v8.0 신규: 플로팅 미니 창
- `Alt+V`로 빠른 접근
- 최근 10개 항목 표시
- 더블클릭으로 즉시 붙여넣기

### 🎨 UI/UX
- **5가지 테마**: 다크, 라이트, 오션, 퍼플, 미드나잇
- **그라데이션 버튼**: 모던 디자인
- **토스트 알림**: 슬라이드 애니메이션

### 🛠 기타 기능
- 스니펫 관리 (템플릿 변수 지원)
- 복사 규칙 자동화
- QR 코드 생성
- JSON/CSV/Markdown 내보내기
- 시스템 트레이 지원
- 글로벌 핫키 (`Ctrl+Shift+V`)

---

## 🚀 설치 및 실행

### 요구 사항
```
Python 3.10+
Windows 10/11
```

### 패키지 설치
```bash
pip install PyQt6 keyboard qrcode pillow cryptography requests beautifulsoup4
```

### 실행
```bash
python "클립모드 매니저.py"
```

### PyInstaller 빌드
```bash
pyinstaller smartclipboard.spec
```

---

## ⌨️ 단축키

| 단축키 | 기능 |
|--------|------|
| `Ctrl+Shift+V` | 메인 창 열기 (글로벌) |
| `Alt+V` | 미니 창 열기 (글로벌) |
| `Ctrl+Shift+Z` | 마지막 항목 붙여넣기 |
| `Ctrl+C` | 선택 항목 복사 |
| `Enter` | 복사 후 붙여넣기 |
| `Delete` | 선택 항목 삭제 |
| `Ctrl+P` | 고정/해제 |
| `Ctrl+F` | 검색 포커스 |
| `Escape` | 창 숨기기 |

---

## � 파일 구조

```
smartclipboard-main/
├── 클립모드 매니저.py     # 메인 애플리케이션
├── smartclipboard.spec    # PyInstaller 빌드 설정
├── README.md              # 문서
├── clipboard_history_v6.db  # SQLite 데이터베이스
└── clipboard_manager.log    # 로그 파일
```

---

## 🔧 설정

### 테마 변경
메뉴: **보기 > 🎨 테마**

### 핫키 설정
메뉴: **설정 > ⌨️ 핫키 설정**

### 보안 보관함
메뉴: **설정 > 🔒 보안 보관함**

### 액션 자동화
메뉴: **설정 > ⚡ 액션 자동화**

---

## 📜 라이선스

MIT License

---

## 🆕 버전 히스토리

### v8.0 (2026-01-02)
- 🔐 암호화 보안 보관함
- ⚡ 클립보드 액션 자동화
- 📋 플로팅 미니 창 (`Alt+V`)
- 🎨 2개 신규 테마 (퍼플, 미드나잇)
- 📤 JSON/CSV/Markdown 내보내기
- 🔧 코드 리팩토링 및 버그 수정

### v7.2
- 토스트 알림 시스템
- 복사 규칙 기능
- QR 코드 생성

### v6.3
- 초기 PyQt6 버전
- 기본 클립보드 관리 기능

# 📋 SmartClipboard Pro v9.0

> 고급 클립보드 매니저 - PyQt6 기반의 현대적이고 강력한 클립보드 관리 도구

![Version](https://img.shields.io/badge/version-9.0-blue)
![Python](https://img.shields.io/badge/python-3.10+-green)
![Platform](https://img.shields.io/badge/platform-Windows-lightgrey)
![License](https://img.shields.io/badge/license-MIT-orange)

---

## ✨ 주요 기능

### 📋 클립보드 히스토리
- 텍스트, 이미지, 링크, 코드, 색상 자동 분류 및 저장
- 최대 500개 항목 저장 (설정 가능)
- 📌 중요 항목 고정 기능
- 🏷️ 태그 시스템으로 항목 정리

### 🔒 보안 보관함 (v8.0+)
- AES-256 암호화로 민감한 데이터 안전 보관
- 마스터 비밀번호 기반 잠금
- 자동 잠금 타이머

### ⚡ 클립보드 액션 자동화 (v8.0+)
- 패턴 매칭 기반 자동 처리
- URL 제목 자동 가져오기
- 알림 액션 지원

### 📤 고급 내보내기/가져오기 (v8.0+)
- JSON, CSV, Markdown 형식 지원
- 백업/복원 기능

### 🎨 UI/UX (v9.0)
- **글래스모피즘** 디자인
- 5가지 테마: 다크, 라이트, 오션, 퍼플, 미드나잇
- 현대적인 애니메이션 효과
- 플로팅 미니 창

### ⌨️ 글로벌 핫키
- `Ctrl+Shift+V`: 메인 창 표시
- `Alt+V`: 미니 창 토글
- `Ctrl+Shift+Z`: 마지막 항목 즉시 붙여넣기

---

## 🖥️ 시스템 요구사항

- **OS**: Windows 10/11
- **Python**: 3.10 이상
- **메모리**: 50MB 이상
- **디스크**: 100MB 이상

---

## 📦 설치

### 방법 1: 실행 파일 (권장)
1. [Releases](https://github.com/your-repo/smartclipboard/releases)에서 최신 버전 다운로드
2. `SmartClipboard.exe` 실행

### 방법 2: 소스에서 실행
```powershell
# 저장소 클론
git clone https://github.com/your-repo/smartclipboard.git
cd smartclipboard

# 의존성 설치
pip install -r requirements.txt

# 실행
python "클립모드 매니저.py"
```

---

## 📄 의존성

### 필수
```
PyQt6>=6.4.0
keyboard>=0.13.5
```

### 선택적 (기능 확장)
```
cryptography>=41.0.0    # 보안 보관함 암호화
requests>=2.28.0        # URL 제목 가져오기
beautifulsoup4>=4.11.0  # HTML 파싱
qrcode[pil]>=7.3        # QR 코드 생성
Pillow>=9.0.0           # 이미지 처리
```

---

## 🔨 빌드 (PyInstaller)

### 빌드 명령어
```powershell
# 경량화 빌드 (권장)
pyinstaller SmartClipboard.spec

# 또는 직접 명령어
pyinstaller --onefile --windowed --name SmartClipboard "클립모드 매니저.py"
```

### 빌드 파일 위치
- 실행 파일: `dist/SmartClipboard.exe`

---

## 📁 파일 구조

```
smartclipboard-main/
├── 클립모드 매니저.py     # 메인 애플리케이션
├── SmartClipboard.spec    # PyInstaller 빌드 설정
├── README.md              # 이 문서
├── requirements.txt       # Python 의존성
├── clipboard_history_v6.db # SQLite 데이터베이스 (자동 생성)
└── clipboard_manager.log  # 로그 파일 (자동 생성)
```

---

## ⌨️ 단축키

| 단축키 | 기능 |
|--------|------|
| `Ctrl+Shift+V` | 메인 창 표시/숨기기 (글로벌) |
| `Alt+V` | 미니 창 토글 (글로벌) |
| `Ctrl+Shift+Z` | 마지막 항목 붙여넣기 (글로벌) |
| `Ctrl+F` | 검색창 포커스 |
| `Ctrl+C` | 선택 항목 복사 |
| `Ctrl+P` | 고정/해제 토글 |
| `Enter` | 복사 후 붙여넣기 |
| `Delete` | 선택 항목 삭제 |
| `Escape` | 창 숨기기 |

---

## 🎨 테마

| 테마 | 설명 |
|------|------|
| 🌙 다크 모드 | 눈의 피로를 줄여주는 어두운 테마 |
| ☀️ 라이트 모드 | 밝고 깔끔한 테마 |
| 🌊 오션 모드 | 시원한 블루 톤 |
| 💜 퍼플 모드 | 우아한 보라색 테마 |
| 🌌 미드나잇 | 깊은 밤하늘 느낌 |

---

## 📝 v9.0 변경사항

### 🎨 UI/UX 전면 개편
- **글래스모피즘** 디자인 도입
- 모든 컴포넌트에 현대적 스타일 적용
- 검색창/테이블/버튼 둥근 모서리 강화
- 슬림 스크롤바 (8px)
- 테이블 헤더 그라데이션
- 호버 효과 개선

### 🔧 코드 품질 개선
- QBuffer 임포트 누락 수정
- 중복 단축키 등록 제거
- bare except를 명시적 Exception으로 변경
- 클립보드 액션 자동화 실제 동작 연결
- 설정에서 로깅 레벨 변경 가능

---

## 🐛 알려진 이슈

- 일부 애플리케이션에서 `keyboard` 라이브러리 충돌 가능
- 고해상도 모니터에서 스케일링 조정 필요할 수 있음

---

## 📜 라이선스

MIT License - 자유롭게 사용, 수정, 배포 가능

---

## 🙏 기여

버그 리포트, 기능 제안, PR 환영합니다!

---

<div align="center">
  <b>Made with ❤️ by MySmartTools</b><br>
  <sub>© 2025-2026</sub>
</div>

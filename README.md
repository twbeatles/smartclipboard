# 📋 SmartClipboard Pro v10.0

> 고급 클립보드 매니저 - PyQt6 기반의 현대적이고 강력한 클립보드 관리 도구

![Version](https://img.shields.io/badge/version-10.0-blue)
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
- ⭐ 북마크 기능

### 🔒 보안 보관함
- AES-256 암호화로 민감한 데이터 안전 보관
- 마스터 비밀번호 기반 잠금
- 5분 자동 잠금 타이머

### ⚡ 클립보드 액션 자동화
- 패턴 매칭 기반 자동 처리
- URL 제목 자동 가져오기
- 알림 액션 지원

### 📤 고급 내보내기/가져오기
- JSON, CSV, Markdown 형식 지원
- 백업/복원 기능

### 🎨 UI/UX
- **글래스모피즘** 디자인
- 5가지 테마: 다크, 라이트, 오션, 퍼플, 미드나잇
- 현대적인 애니메이션 효과
- 플로팅 미니 창
- 상세 툴팁 및 단축키 안내

### ⌨️ 글로벌 핫키
| 단축키 | 기능 |
|--------|------|
| `Ctrl+Shift+V` | 메인 창 표시 |
| `Alt+V` | 미니 창 토글 |
| `Ctrl+Shift+Z` | 마지막 항목 즉시 붙여넣기 |

---

## 🖥️ 시스템 요구사항

- **OS**: Windows 10/11
- **Python**: 3.10 이상 (소스 실행 시)
- **메모리**: 50MB 이상
- **디스크**: 100MB 이상

---

## 📦 설치

### 방법 1: 실행 파일 (권장)
1. [Releases](https://github.com/your-repo/smartclipboard/releases)에서 최신 버전 다운로드
2. `SmartClipboard.exe` 실행

### 방법 2: 소스에서 실행
```powershell
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

## 🔨 빌드

### PyInstaller 빌드
```powershell
pyinstaller smartclipboard.spec
```

### 빌드 결과물
- `dist/SmartClipboard.exe` (단일 실행 파일, ~45MB)

---

## ⌨️ 앱 내 단축키

| 단축키 | 기능 |
|--------|------|
| `Ctrl+F` | 검색창 포커스 |
| `Ctrl+C` | 선택 항목 복사 |
| `Ctrl+P` | 고정/해제 토글 |
| `Ctrl+G` | 구글 검색 |
| `Ctrl+L` | 링크 열기 |
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

## 📝 v10.0 변경사항

### ⚡ 성능 최적화
- **정규식 사전 컴파일**: 클립보드 분석용 정규식을 전역 상수로 컴파일하여 CPU 사용량 감소
- **코드 인디케이터 상수화**: `CODE_INDICATORS`를 `frozenset`으로 변환하여 O(1) 조회
- **복사 규칙 캐싱**: DB I/O 최소화, 규칙 변경 시에만 리로드
- **이미지 중복 체크**: MD5 해시 기반 중복 감지로 DB 공간 절약

### 🔧 코드 품질 개선
- **analyze_text()**: 사전 컴파일된 정규식 사용
- **apply_copy_rules()**: 캐시 메커니즘 도입
- **cleanup 최적화**: 매번이 아닌 N회마다 실행

### 🎨 v9.1 기능 유지
- 로그 파일 로테이션 (최대 1MB, 백업 3개)
- 디버그 모드 토글
- 리소스 정리 강화
- 상태바 오늘 복사 횟수 표시
- 버튼 애니메이션 클릭 효과

---

## 📜 라이선스

MIT License - 자유롭게 사용, 수정, 배포 가능

---

<div align="center">
  <b>Made with ❤️ by MySmartTools</b><br>
  <sub>© 2025-2026</sub>
</div>

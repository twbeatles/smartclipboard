# 📋 SmartClipboard Pro v10.1

> 고급 클립보드 매니저 - PyQt6 기반의 현대적이고 강력한 클립보드 관리 도구

![Version](https://img.shields.io/badge/version-10.1-blue)
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

### 🎨 UI/UX
- **글래스모피즘** 디자인
- 5가지 테마: 다크, 라이트, 오션, 퍼플, 미드나잇
- **v10.1**: 향상된 마이크로 인터랙션 (호버/포커스 효과)
- 온보딩 가이드가 포함된 빈 상태 UI

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

---

## 📦 설치

### 방법 1: 실행 파일 (권장)
[Releases](https://github.com/your-repo/smartclipboard/releases)에서 `SmartClipboard.exe` 다운로드

### 방법 2: 소스에서 실행
```powershell
pip install -r requirements.txt
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

```powershell
pyinstaller smartclipboard.spec
```

결과물: `dist/SmartClipboard.exe` (~40MB, UPX 압축 적용 시)

---

## ⌨️ 앱 내 단축키

| 단축키 | 기능 |
|--------|------|
| `Ctrl+F` | 검색창 포커스 |
| `Ctrl+C` | 선택 항목 복사 |
| `Ctrl+P` | 고정/해제 토글 |
| `Ctrl+G` | 구글 검색 |
| `Enter` | 복사 후 붙여넣기 |
| `Delete` | 선택 항목 삭제 |
| `Escape` | 창 숨기기 |

---

## 📝 v10.1 변경사항

### ⚡ 성능 최적화
- `load_data()` UI 일괄 렌더링 (`setUpdatesEnabled`)
- `hashlib` 모듈 레벨 import 이동
- `TYPE_ICONS` 상수 추출로 루프 내 딕셔너리 생성 제거
- DB 인덱스 추가 (pinned, type, timestamp, bookmark)

### 🎨 UI/UX 개선
- 버튼 호버/포커스 효과 강화 (2px 테두리, 포커스 링)
- 테이블 행 호버 시 좌측 프라이머리 컬러 보더
- 선택 항목 폰트 굵기 강조
- 빈 상태에서 단축키 가이드 포함 온보딩 UI

### 🔧 코드 품질
- `SecureVaultManager.unlock()` 예외 처리 세분화
- `UI_TEXTS` 상수 추가 (다국어 지원 대비)

---

## 📜 라이선스

MIT License

---

<div align="center">
  <b>Made with ❤️ by MySmartTools</b><br>
  <sub>© 2025-2026</sub>
</div>

# 📋 SmartClipboard Pro v10.2

> 고급 클립보드 매니저 - PyQt6 기반의 현대적이고 강력한 클립보드 관리 도구

![Version](https://img.shields.io/badge/version-10.2-blue)
![Python](https://img.shields.io/badge/python-3.10+-green)
![Platform](https://img.shields.io/badge/platform-Windows-lightgrey)
![License](https://img.shields.io/badge/license-MIT-orange)

---

## ✨ 주요 기능

### 📋 클립보드 히스토리
- 텍스트, 이미지, 링크, 코드, 색상 자동 분류 및 저장
- 최대 500개 항목 저장 (설정 가능)
- 📌 중요 항목 고정 및 드래그 정렬 기능
- 🏷️ 태그 시스템으로 항목 정리
- ⭐ 북마크 기능으로 즐겨찾기 관리
- 📁 컬렉션 기능으로 항목 그룹화
- 📝 항목별 메모 첨부 기능

### 🔒 보안 보관함
- AES-256 암호화로 민감한 데이터 안전 보관
- 마스터 비밀번호 기반 잠금
- **v10.2**: 비밀번호 강도 검증 (8자 이상, 대/소문자+숫자+특수문자)
- 5분 자동 잠금 타이머

### ⚡ 클립보드 액션 자동화
- 패턴 매칭 기반 자동 처리
- **v10.2**: URL 제목 가져오기 개선 (타임아웃/에러 처리 강화)
- 전화번호 자동 포맷팅
- 이메일 정규화
- 텍스트 변환 (대소문자, 트림 등)
- **v10.2**: 정규식 패턴 유효성 검증

### 🗑️ 휴지통 기능
- 삭제 항목 7일간 보관 후 자동 영구 삭제
- **v10.2**: 휴지통 다이얼로그 다중 선택 지원
- 원클릭 복원 및 영구 삭제
- 실행 취소 가능한 안전한 삭제

### 📄 텍스트 스니펫
- 자주 사용하는 텍스트 템플릿 저장
- **v10.2**: 스니펫 수정 기능 추가
- 카테고리별 정리
- 단축키 할당 가능

### 📤 내보내기/가져오기
- JSON, CSV, Markdown 포맷 지원
- 날짜 및 타입 필터링
- 백업 및 마이그레이션 용이

### 🎨 UI/UX
- **글래스모피즘** 디자인
- 5가지 테마: 🌙 다크, ☀️ 라이트, 🌊 오션, 💜 퍼플, 🌌 미드나잇
- **v10.1**: 향상된 마이크로 인터랙션 (호버/포커스 효과)
- 온보딩 가이드가 포함된 빈 상태 UI
- 플로팅 토스트 알림 (슬라이드 애니메이션)
- 미니 창 모드 지원

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

## 📝 v10.2 변경사항

### 🔐 보안 강화
- 마스터 비밀번호 강도 검증 추가 (8자 이상, 대/소문자+숫자+특수문자 필수)
- URL 제목 가져오기 타임아웃 설정 (기본 5초)
- 액션 패턴 정규식 유효성 검증

### 🗑️ 휴지통 개선
- 휴지통 다이얼로그 다중 선택 지원
- 선택 항목 일괄 복원/삭제 기능
- 빈 휴지통 경고 메시지 개선

### 📄 스니펫 편집
- 스니펫 수정 다이얼로그 추가
- 더블클릭으로 스니펫 편집 가능
- 편집 시 카테고리 변경 지원

### 🔧 핫키 안정성
- 핫키 등록/해제 에러 핸들링 강화
- 앱 종료 시 안전한 핫키 해제
- 충돌 핫키 감지 및 경고

### ⏱️ 클린업 타이머
- 만료된 임시 항목 자동 정리 (1분 주기)
- 휴지통 만료 항목 자동 삭제 (1분 주기)
- `QTimer` 기반 리소스 정리

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

## 📁 프로젝트 구조

```
smartclipboard-main/
├── 클립모드 매니저.py    # 메인 애플리케이션 (5,400+ lines)
├── requirements.txt      # Python 의존성
├── smartclipboard.spec   # PyInstaller 빌드 설정
├── README.md             # 문서
└── clipboard_history_v6.db  # SQLite 데이터베이스 (자동 생성)
```

---

## 🗄️ 데이터베이스 구조

| 테이블 | 용도 |
|--------|------|
| `history` | 클립보드 히스토리 저장 |
| `snippets` | 텍스트 스니펫 저장 |
| `settings` | 앱 설정 (테마, 핫키 등) |
| `copy_rules` | 복사 규칙 |
| `secure_vault` | 암호화된 보안 항목 |
| `clipboard_actions` | 자동화 액션 규칙 |
| `collections` | 컬렉션 정보 |
| `deleted_history` | 휴지통 (7일 보관) |

---

## 🎯 사용 팁

1. **빠른 접근**: `Ctrl+Shift+V`로 언제든 히스토리 확인
2. **미니 모드**: `Alt+V`로 작은 창에서 빠르게 항목 선택
3. **고정 항목**: 자주 쓰는 텍스트는 📌 고정하여 상단에 유지
4. **태그 활용**: 관련 항목끼리 태그로 분류
5. **보안 보관함**: 비밀번호, API 키 등 민감 정보는 암호화 보관
6. **스니펫**: 자주 사용하는 이메일 서명, 템플릿 등은 스니펫으로 저장

---

## ⚠️ 알려진 제한사항

- Windows 전용 (macOS/Linux 미지원)
- 일부 애플리케이션에서 글로벌 핫키 충돌 가능
- 이미지 히스토리는 크기에 따라 DB 용량 증가

---

## 🤝 기여

버그 리포트, 기능 제안, PR 환영합니다!

---

## 📜 라이선스

MIT License

---

<div align="center">
  <b>Made with ❤️ by MySmartTools</b><br>
  <sub>© 2025-2026</sub>
</div>

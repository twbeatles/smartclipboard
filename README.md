# 📋 SmartClipboard Pro

> Windows용 고급 클립보드 매니저 — 복사한 모든 것을 저장하고, 검색하고, 활용하세요.  
> **Python/PyQt6 클래식 에디션**과 초경량 **Rust + Tauri 2 네이티브 에디션**을 모두 지원합니다.

![Version](https://img.shields.io/badge/version-10.7-blue)
![Rust](https://img.shields.io/badge/rust-1.85+-orange)
![Tauri](https://img.shields.io/badge/tauri-2.0+-blueviolet)
![React](https://img.shields.io/badge/react-19-61dafb)
![Python](https://img.shields.io/badge/python-3.10+-green)
![Platform](https://img.shields.io/badge/platform-Windows-lightgrey)
![License](https://img.shields.io/badge/license-MIT-orange)

---

## 🦀 Rust + Tauri 2 네이티브 에디션 (Native Edition)

SmartClipboard Pro는 기존 Python 구현의 모든 데이터와 기능을 100% 보존하면서 메모리 사용량과 반응 속도를 극대화한 **Rust + Tauri 2 네이티브 코어**를 탑재하고 있습니다.

- **OS 네이티브 이벤트 리스너**: `WM_CLIPBOARDUPDATE` 기반으로 폴링 없이 즉각 반응하며 유휴 시 CPU 0% 유지
- **100% DB 바이너리 호환**: 기존 SQLite WAL DB(`clipboard_history_v6.db`)와 FTS5 전문 검색 트리거, PBKDF2 (480,000 iter) + Fernet 보안 보관함 데이터 무변경 완벽 연동
- **초경량 모던 UI**: React 19 + TypeScript Strict + Tailwind CSS 5종 테마(다크, 라이트, 오션, 퍼플, 미드나잇) 및 플로팅 미니 윈도우
- **기능 동등성 검증**: 총 30건의 Rust 네이티브 테스트와 230건의 Python 크로스 회귀 테스트 100% 통과 ([NATIVE_PARITY_MATRIX.md](docs/NATIVE_PARITY_MATRIX.md))

### 네이티브 에디션 빌드 및 실행

```powershell
# 프론트엔드 의존성 설치 및 빌드
cd native
npm install
npm run build

# Tauri 네이티브 테스트 실행
cargo test --manifest-path src-tauri/Cargo.toml

# 네이티브 개발 모드 실행
npm run tauri dev

# 릴리즈 실행 파일 빌드
npm run tauri build
```

---

## 주요 기능

### 📋 클립보드 히스토리

- 텍스트, 이미지, 링크, 코드, 색상, 파일/폴더를 자동 분류하여 저장
- 최대 500개 항목 보관 (설정에서 조정 가능)
- 중복 항목은 자동 병합 — 태그·메모·북마크 등 메타데이터 유지
- 📌 고정 기능으로 중요한 항목을 상단에 유지, 드래그앤드롭으로 순서 변경

### 🔍 검색 및 정리

- 빠른 전문 검색(FTS5)으로 히스토리를 즉시 조회
- 🏷️ **태그** — 관련 항목끼리 태그로 분류
- ⭐ **북마크** — 즐겨찾기 표시
- 📁 **컬렉션** — 항목을 그룹으로 묶어 프로젝트별 관리
- 📝 **메모** — 항목별 메모 첨부
- 상단 필터로 전체 / 미분류 / 특정 컬렉션 빠르게 전환

### 🔒 보안 보관함

- PBKDF2-HMAC-SHA256 + Fernet 방식으로 민감한 정보를 암호화 보관
- 마스터 비밀번호 기반 잠금 (8자 이상, 숫자+특수문자 필수)
- 5분 비활성 시 자동 잠금 (메모리 키 즉시 zeroize 파기)
- 마스터 비밀번호 변경 시 저장된 항목 전체 원자적 재암호화
- 복호화 후 클립보드에 복사된 텍스트는 30초 뒤 자동 삭제

### ⚡ 클립보드 액션 자동화

정규식 패턴 기반으로 복사된 내용을 자동으로 처리합니다.

| 액션 | 설명 |
|------|------|
| URL 제목 가져오기 | 복사한 링크의 페이지 제목을 자동 조회 |
| 전화번호 포맷팅 | 02, 지역번호, 0505, 1588 계열 대표번호 자동 정리 |
| 이메일 정규화 | 소문자 변환, 앞뒤 공백 제거 |
| 텍스트 변환 | 대소문자 변환, 공백 제거 등 |
| 토스트 알림 | 특정 패턴 감지 시 알림 표시 |

### ⚡ 작업 실행 (Action Palette)

히스토리에서 항목을 고른 뒤 `Alt+A` 또는 우클릭 **작업 실행...**으로, 지금 내용에 맞는 작업만 검색하고 실행합니다.

- 자동 액션 규칙과 분리된 **수동** 경로
- 변환 결과는 같은 항목과 클립보드에 반영되며, 자동 규칙을 다시 타지 않음
- Base64 인코딩/디코딩, SHA-256 해시, JSON 포맷팅, 글자 수 통계 등 즉시 실행

### 📄 텍스트 스니펫

- 이메일 서명, 답변 템플릿 등 자주 쓰는 텍스트를 저장해두고 즉시 붙여넣기
- 카테고리별 정리, 더블클릭으로 즉시 복사
- 앱 내부 단축키 지정 가능

### 📤 내보내기 / 가져오기

- **내보내기**: JSON, CSV, Markdown
- **가져오기**: JSON, CSV
- JSON은 이미지·파일 경로 포함 완전한 라운드트립 지원
- 날짜 범위 및 항목 타입 필터 적용 가능

### 🗑️ 휴지통

- 삭제한 항목을 7일간 보관 후 자동 영구 삭제
- 원클릭 복원 및 영구 삭제, 다중 선택 일괄 처리 지원
- 전체 기록 삭제 시 고정 항목을 제외하고 휴지통으로 이동

### 🚀 자동 업데이트 (GitHub Releases)

- Ed25519 디지털 서명과 SHA-256 해시 검증 기반의 안전한 자동 업데이트
- 앱 기동 시 백그라운드 확인 및 `도움말 > 🚀 업데이트 확인...`을 통한 원클릭 설치
- 업데이트 적용 시 이전 버전 자동 백업 및 문제 발생 시 안전한 자동 롤백 지원

### 🎨 UI/UX

- 글래스모피즘 디자인
- 5가지 테마: 🌙 다크 · ☀️ 라이트 · 🌊 오션 · 💜 퍼플 · 🌌 미드나잇
- 플로팅 미니 창(`Alt+V`)으로 언제든 빠르게 접근
- 시스템 트레이 상주, 슬라이드 토스트 알림
- 통계 대시보드

---

## 🖥️ 시스템 요구사항

| 항목 | 요구사항 |
|------|---------|
| OS | Windows 10 / 11 |
| 메모리 | 50MB 이상 |
| Native 실행 | WebView2 런타임 (Windows 10/11 기본 내장) |
| Python (소스 실행 시) | 3.10 이상 |

---

## 📦 설치 및 실행

### 방법 1: 실행 파일 (권장)

[Releases](https://github.com/twbeatles/smartclipboard/releases)에서 `SmartClipboard.exe`를 다운로드하여 실행하세요.
별도 설치 없이 바로 사용할 수 있습니다.

### 방법 2: Native 에디션 실행

```powershell
cd native
npm install
npm run tauri dev
```

### 방법 3: Python 클래식 소스 실행

```powershell
pip install -r requirements.txt
python "클립모드 매니저.py"
```

---

## ⌨️ 단축키

### 글로벌 핫키 (앱이 백그라운드에 있어도 동작)

| 단축키 | 기능 |
|--------|------|
| `Ctrl+Shift+V` | 메인 창 표시 |
| `Alt+V` | 미니 창 토글 |
| `Ctrl+Shift+Z` | 가장 최근 복사 항목 즉시 붙여넣기 |

### 앱 내 단축키

| 단축키 | 기능 |
|--------|------|
| `Ctrl+F` | 검색창 포커스 |
| `Ctrl+C` | 선택 항목 복사 |
| `Ctrl+P` | 고정/해제 토글 |
| `Alt+A` | 선택 항목 작업 실행 |
| `Enter` | 복사 후 붙여넣기 |
| `Delete` | 선택 항목 삭제 |
| `Escape` | 창 숨기기 |

---

## ⚠️ 알려진 제한사항

- Windows 전용 (macOS / Linux 미지원)
- 일부 앱에서 글로벌 핫키 충돌 발생 가능
- 이미지 히스토리는 최신 20개만 유지 (DB 용량 관리)
- 스니펫 단축키는 앱이 활성화된 상태에서만 동작

---

## 🤝 기여

버그 리포트, 기능 제안, PR 환영합니다!
상세 마이그레이션 기술 문서는 [SMARTCLIPBOARD_RUST_TAURI_MIGRATION_PLAN.md](SMARTCLIPBOARD_RUST_TAURI_MIGRATION_PLAN.md)와 [docs/NATIVE_PARITY_MATRIX.md](docs/NATIVE_PARITY_MATRIX.md)를 참조하세요.

---

## 📜 라이선스

MIT License

---

<div align="center">
  <b>Made with ❤️ by MySmartTools</b><br>
  <sub>© 2025-2026</sub>
</div>

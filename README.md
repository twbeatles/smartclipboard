# 📋 SmartClipboard Pro v10.6

> 고급 클립보드 매니저 - PyQt6 기반의 현대적이고 강력한 클립보드 관리 도구

![Version](https://img.shields.io/badge/version-10.6-blue)
![Python](https://img.shields.io/badge/python-3.10+-green)
![Platform](https://img.shields.io/badge/platform-Windows-lightgrey)
![License](https://img.shields.io/badge/license-MIT-orange)

---

## ✨ 주요 기능

### 📋 클립보드 히스토리
- 텍스트, 이미지, 링크, 코드, 색상, 파일/폴더 자동 분류 및 저장
- 최대 500개 항목 저장 (설정 가능)
- 📌 중요 항목 고정 및 드래그 정렬 기능
- 🏷️ 태그 시스템으로 항목 정리
- ⭐ 북마크 기능으로 즐겨찾기 관리
- 📁 컬렉션 기능으로 항목 그룹화
- 📝 항목별 메모 첨부 기능
- 파일 복사는 다중 선택을 하나의 `FILE` 항목으로 저장하고, paste-last/미니 창/선택 붙여넣기에서 로컬 file URL 클립보드를 복원

### 🔒 보안 보관함
- PBKDF2-HMAC-SHA256 + Fernet 기반 암호화로 민감한 데이터 안전 보관
- 마스터 비밀번호 기반 잠금
- **v10.2**: 비밀번호 강도 검증 (8자 이상, 숫자+특수문자)
- 5분 자동 잠금 타이머
- 마스터 비밀번호 변경 시 기존 보관 항목 전체 재암호화
- 복호화 후 클립보드로 복사한 텍스트는 30초 뒤 자동 삭제
- 설정 손상 시 잠금 화면에서 `Reset 보관함`으로 복구 가능

### ⚡ 클립보드 액션 자동화
- 패턴 매칭 기반 자동 처리
- **v10.2**: URL 제목 가져오기 개선 (타임아웃/에러 처리 강화)
- `fetch_title`은 첫 URL만 추출하며 로컬/사설/메타데이터 주소는 보안상 차단
- 전화번호 자동 포맷팅 (`02`, 일반 지역번호, `0505`, `1588/1661/1800`류 대표번호 포함)
- 이메일 정규화
- 텍스트 변환 (대소문자, 트림 등)
- **v10.2**: 정규식 패턴 유효성 검증

### 🗑️ 휴지통 기능
- 삭제 항목 7일간 보관 후 자동 영구 삭제
- **v10.2**: 휴지통 다이얼로그 다중 선택 지원
- 원클릭 복원 및 영구 삭제
- 실행 취소 가능한 안전한 삭제
- 전체 기록 삭제도 고정 항목을 제외하고 휴지통 이동으로 처리

### 📄 텍스트 스니펫
- 자주 사용하는 텍스트 템플릿 저장
- **v10.2**: 스니펫 수정 기능 추가
- 카테고리별 정리
- 더블클릭/버튼으로 즉시 복사
- 앱 내부 전용 단축키(`shortcut`) 등록 및 실행 지원
- 기본 단축키/글로벌 핫키/다른 스니펫과의 충돌 검증

### 📤 내보내기/가져오기
- JSON, CSV, Markdown 내보내기 / JSON, CSV 가져오기 지원
- 날짜 및 타입 필터링
- JSON은 `IMAGE` 항목을 `image_data_b64`로 보존하며, CSV/Markdown은 이미지 플레이스홀더만 기록
- `FILE` 항목은 바이너리 대신 경로 목록만 내보내며, JSON은 `file_paths`/`file_path`, CSV/Markdown은 newline 경로 목록을 사용
- JSON 마이그레이션 모드 (히스토리 항목의 태그/메모/북마크 + 컬렉션 정의/ID 매핑 정보 포함, 스니펫/규칙/핫키/보안 보관함 제외)
- JSON import는 ISO-8601/tz timestamp를 원본 시각 기준 앱 표준 시각 문자열로 정규화하고, 완전 불량 timestamp는 import 시각으로 대체
- CSV import는 이미지 플레이스홀더 row를 복원하지 않으며, JSON import는 remap 실패/누락된 `collection_id`를 `NULL`로 정리
- `FILE` 항목은 복원 전에 목록/상세/미니 창에서 누락 경로(stale) 여부를 미리 표시
- 백업 및 마이그레이션 용이

### 🎨 UI/UX
- **글래스모피즘** 디자인
- 5가지 테마: 🌙 다크, ☀️ 라이트, 🌊 오션, 💜 퍼플, 🌌 미드나잇
- **v10.1**: 향상된 마이크로 인터랙션 (호버/포커스 효과)
- 온보딩 가이드가 포함된 빈 상태 UI
- 플로팅 토스트 알림 (슬라이드 애니메이션)
- 미니 창 모드 지원
- 상단 컬렉션 필터(전체/미분류/개별 컬렉션)

### ⌨️ 글로벌 핫키
| 단축키 | 기능 |
|--------|------|
| `Ctrl+Shift+V` | 메인 창 표시 |
| `Alt+V` | 미니 창 토글 |
| `Ctrl+Shift+Z` | 가장 최근 복사 항목 즉시 붙여넣기 |

---

## 🖥️ 시스템 요구사항

- **OS**: Windows 10/11
- **Python**: 3.10-3.14 (소스 실행/로컬 빌드 검증 기준)
- **메모리**: 50MB 이상

---

## 📦 설치

### 방법 1: 실행 파일 (권장)
[Releases](https://github.com/twbeatles/smartclipboard/releases)에서 `SmartClipboard.exe` 다운로드

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
python scripts/preflight_local.py
pyinstaller --clean smartclipboard.spec
```

결과물: `dist/SmartClipboard.exe` (기본 spec 기준 UPX 비활성)

payload와 manifest만 다시 생성해야 할 때는:

```powershell
python scripts/build_legacy_payload.py --src smartclipboard_app/legacy_main_src.py --out smartclipboard_app/legacy_main_payload.marshal --smoke-import
```

위 명령은 `legacy_main_payload.marshal`과 함께 `legacy_main_payload.manifest.json`도 갱신합니다.

## ✅ 로컬 프리플라이트

```powershell
python scripts/preflight_local.py
```

`preflight_local.py`는 payload 재생성, payload smoke import, `py_compile`, `unittest`(`test_payload_sync` 포함)을 순차 실행합니다.
현재 핵심 회귀 범위에는 `test_core`, `test_ui_dialogs_widgets`, `test_payload_sync`, `test_legacy_loader`, `test_migration_collections`, `test_legacy_ui_contracts`, `test_signal_snapshot`, `test_public_surfaces`가 포함됩니다.
`pyright`는 별도 단계이며 루트 `pyrightconfig.json` 기준으로 현행 유지보수 대상만 분석합니다.
현재 repo-wide `pyright`에는 `smartclipboard_core/db_parts/*.py` mixin attribute typing 노이즈가 남아 있으므로, 로컬 게이트는 `preflight_local.py`이고 `pyright`는 변경 파일 기준 보조 검증으로 사용합니다.
Windows 로컬 테스트는 시스템 temp 권한 이슈를 피하기 위해 repo 루트의 `.tmp-unittest/` 하위 임시 디렉터리를 사용합니다.

필요 시 payload 재생성 단계를 건너뛰려면:

```powershell
python scripts/preflight_local.py --skip-payload-build
```

optional dependency까지 CI와 같은 강도로 확인하려면 위 strict 커맨드를 사용합니다. 기본 `preflight_local.py`는 `cryptography`, `requests`, `bs4`, `qrcode`, `PIL` 누락을 경고만 출력하고 계속 진행하지만, strict 모드와 CI는 실패로 처리합니다.

```powershell
python scripts/preflight_local.py --skip-payload-build --strict-optional-deps
```

## 🤖 CI (GitHub Actions)

- 워크플로우 파일: `.github/workflows/ci.yml`
- 실행 환경: `windows-latest`
- Python 매트릭스: `3.10`, `3.11`, `3.12`, `3.13`
- 각 매트릭스에서 다음을 수행합니다.
  - payload 빌드 + smoke import
  - `python scripts/preflight_local.py --skip-payload-build --strict-optional-deps`

## 🔎 정적 분석 (Pylance/Pyright)

```powershell
pyright
```

- 루트 `pyrightconfig.json`이 공식 분석 범위를 정의합니다.
- 기본 범위에는 현행 유지보수 대상(`클립모드 매니저.py`, `smartclipboard_app/`, `smartclipboard_core/`, `tests/`)만 포함됩니다.
- 레거시 보관본 `legacy/클립모드 매니저 (legacy).py`와 소스 스냅샷 `smartclipboard_app/legacy_main_src.py`는 호환성 참조용이므로 기본 분석에서 제외됩니다.

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

## 📝 v10.5 변경사항

### 🚀 비동기 시스템 (Async)
- **URL 제목 가져오기 비동기화**: 네트워크 요청 시 UI 프리징 현상 완전 해결
- `Worker` 클래스 및 스레드풀 도입 (Background Processing)
- 즉각적인 클립보드 반응성 및 처리 상태 시각화 (Fetching...)

### 🛡️ 데이터 안전성 & 최적화
- **자동 DB 백업**: 매일 1회 `backups/` 폴더에 DB 자동 백업 (최근 7일 보관)
- **클립보드 모니터 리셋**: 트레이 메뉴 > 고급 > 모니터 재시작 기능 (체인 끊김 해결)
- **이미지 히스토리 제한**: 이미지 항목은 최신 20개만 유지하여 DB 용량 최적화

### 🎨 UI 개선
- **가독성 향상**: UI 기본 폰트를 **'맑은 고딕(Malgun Gothic)'**으로 변경
- 텍스트 미리보기 영역 폰트 가독성 개선

---

## 📝 v10.6 변경사항

### 🔧 드래그앤드롭 수정
- **고정 항목 순서 변경**: 드래그 시 데이터 손실 버그 수정
- `DragDropMode` 변경으로 Qt 자동 행 삭제 방지
- `eventFilter` 재설계 (DragEnter/DragMove/Drop 분리 처리)

### 🛡️ DB 안정성 강화
- `toggle_pin`: 새 고정 항목 `pin_order` 자동 초기화
- `soft_delete`, `restore_item`: rollback 추가
- `add_snippet`, `update_snippet`, `delete_snippet`: rollback/return 추가
- `set_setting`: rollback 추가
- `update_url_title`: URL 제목 캐시 저장 메서드 추가
- 삭제/복원 시 휴지통 메타데이터(tags/note/bookmark/collection/pin/use_count) 보존
- 고정 항목 순서 갱신을 트랜잭션 일괄 처리로 변경(`update_pin_orders`)

### 📁 Collections API 구현
- `add_collection()`: 컬렉션 생성
- `get_collections()`: 목록 조회
- `update_collection()`: 수정
- `delete_collection()`: 삭제 (항목 연결 해제)
- `assign_to_collection()`: 항목 할당/해제
- `get_items_by_collection()`: 컬렉션별 조회
- 메인 상단 상시 필터로 `전체/미분류/컬렉션` 즉시 조회 지원

### ⌨️ 핫키/백업 동작 보강
- 핫키 설정 저장 즉시 `register_hotkeys()` 재등록 (재시작 불필요)
- 자동 백업을 "앱 시작 1회"에서 "실질적 일 1회"로 보강 (1시간 주기 날짜 변경 감시)

### 🛠️ 2026-03-25 구현 반영
- `cleanup()`이 `timestamp ASC, id ASC` 기준으로 가장 오래된 항목부터 정리되도록 수정
- 전체 기록 삭제가 영구 삭제가 아니라 고정 제외 후 휴지통 이동으로 동작
- JSON 재-import 시 컬렉션 이름을 정규화해 기존 컬렉션을 재사용하고 중복 생성을 방지
- CSV/Markdown 내보내기도 JSON과 동일한 날짜·타입 필터를 적용하고 이미지 항목은 플레이스홀더로 기록
- 스니펫 `shortcut` UI와 앱 내부 단축키 실행 경로를 연결
- 복사 규칙/클립보드 액션 다이얼로그에 생성·수정·삭제·우선순위 이동을 모두 반영
- 컬렉션 관리 다이얼로그를 추가하고 이름 중복/빈 값 검증을 적용
- 보안 보관함 마스터 비밀번호 변경과 복호화 클립보드 30초 자동 삭제를 추가
- 핫키 저장 실패 시 이전 글로벌 핫키 상태로 롤백되도록 보강

### 🛠️ 2026-03 정합성 패치
- `fetch_title` 액션 경로가 텍스트 전체가 아닌 **첫 URL만 추출**해 제목 요청하도록 보강
- 빈 검색(`q == ""`)에서도 태그/북마크/컬렉션/미분류 **복합 필터를 동시 적용**하도록 검색 경로 통합
- `TrashDialog` 다중 선택(`ExtendedSelection`)을 명시해 문서와 실제 동작 정합성 확보
- 미니 창 더블클릭 복사 시 `is_internal_copy`를 설정해 자기 재수집 루프 방지
- `update_always_on_top()`에서 창 가시성 보존 가드 적용 (`--minimized` 시작 안정성 개선)
- JSON 마이그레이션에 `collections` 메타데이터를 포함하고 import 시 컬렉션 ID remap 지원

### 🛠️ 2026-03-19 구현 안정화 패치
- `add_snippet()`의 런타임 `datetime` 누락을 수정해 신규 스니펫 저장 경로 복구
- 동일 비이미지 텍스트를 다시 복사하면 기존 row의 메타데이터(tags/note/bookmark/collection/pin/use_count)를 유지한 채 `timestamp/content/type`만 갱신
- 일반 히스토리/북마크/컬렉션/미분류/빈 검색 fallback의 unpinned 정렬을 `timestamp DESC, id DESC`로 통일
- 보안 보관함 복사, 스니펫 사용, URL 복사 경로에서 `smartclipboard_app.ui.clipboard_guard.mark_internal_copy()`를 통해 내부 복사 플래그를 먼저 세팅
- JSON export/import가 `IMAGE` 항목을 `image_data_b64`로 round-trip
- pinned drag-drop helper의 `Qt` 참조 누락을 수정

### 🛠️ 2026-04-08 구현 리스크 보강
- 토스트 호출을 `detail`/`duration`/`toast_type` 키워드 기준으로 정리하고, URL 제목 처리 중 예외가 나도 `clipboard.dataChanged`가 반드시 재연결되도록 보강
- `Ctrl+Shift+Z`가 표시 순서가 아닌 실제 최근 복사 항목(`timestamp DESC`, `id DESC`)을 붙여넣도록 정합성 수정
- 테이블 사용자 정렬이 내림차순이어도 pinned-first 정책이 깨지지 않도록 pinned/unpinned 그룹을 분리 정렬
- 컬렉션 삭제 시 `deleted_history.collection_id`도 `NULL`로 정리하고, 복원 시 삭제된 컬렉션 참조는 자동으로 `NULL` 복원
- 보안 보관함은 마스터 비밀번호 변경 직후 열린 다이얼로그에서도 최신 암호문을 다시 조회해 복사 버튼이 계속 동작하도록 수정
- 종료/복원 시 비동기 URL 제목 worker 결과가 닫힌 DB로 들어오지 않도록 `ClipboardActionManager.shutdown()` 경로를 추가

### 🛠️ 2026-04-10 안정화 + 파일 Clipboard 지원
- `FILE` 타입을 추가해 로컬 파일/폴더 복사를 다중 경로 하나의 히스토리 항목으로 저장
- `history.file_path`를 FILE 첫 경로 저장용으로 활성화하고, 동일 path 집합 재복사 시 기존 metadata를 유지한 채 row를 갱신
- paste-last/미니 창/선택 붙여넣기/더블클릭 복원 경로가 `QMimeData + file URL` 클립보드를 다시 구성하도록 보강
- 일부 파일만 남아 있으면 남은 경로만 복원하고, 모두 사라졌으면 경고만 표시하고 clipboard/paste는 건드리지 않음
- JSON export/import는 `FILE`의 `file_paths`/`file_path`/newline content를 모두 지원하고, CSV/Markdown은 경로 목록만 기록
- CSV import는 `IMAGE` 플레이스홀더 row를 건너뛰고, JSON import는 ISO timestamp를 원본 시각 기준 앱 표준 시각으로 정규화하며 고아 `collection_id`를 `NULL`로 정리
- 보안 보관함 `unlock()` 실패 시 `fernet/is_unlocked` 상태를 원자적으로 초기화해 잘못된 재시도 후 반쯤 열린 상태가 남지 않도록 수정

### 🛠️ 2026-04-11 기능 리뷰 후속 반영
- `fetch_title`은 URL 후행 문장부호를 제거하고, 로컬/사설/메타데이터 주소와 비 HTML 응답을 제목 조회 대상에서 제외
- 전화번호 자동 포맷 범위를 `02`, 일반 지역번호, `0505`, `15xx/16xx/18xx` 대표번호까지 확장
- 보안 보관함은 salt/verification 설정을 함께 저장하고, 손상 상태에서는 잠금 화면 `Reset 보관함`으로 설정값과 저장 항목을 초기화 복구
- 복사 규칙의 `custom_replace`는 빈 문자열 치환을 허용해 “삭제 치환”에 사용할 수 있도록 완화
- `FILE` 항목은 목록/상세/미니 창에서 누락 파일 수를 미리 보여 주어 붙여넣기 전에 stale 상태를 확인 가능
- JSON 마이그레이션 문구를 실제 범위(히스토리 메타데이터 + 컬렉션) 기준으로 정리하고, 관련 회귀 테스트를 추가

---

## 📝 v10.3 변경사항

### 🔲 미니 창 개선
- 미니 클립보드 창 **On/Off 옵션** 추가 (설정 > 일반 > 미니 창)
- 비활성화 시 `Alt+V` 단축키 등록 해제
- 설정 변경 시 재시작 없이 즉시 적용

### 🔒 보안 강화
- Google 검색 URL 인코딩 추가 (특수문자 처리)
- Import 시 타입 유효성 검증 (잘못된 타입 자동 복구)

### ⚡ 성능 개선
- 클립보드 감지 디바운스 개선 (빠른 연속 복사 시 중복 호출 방지)
- `export_json` 날짜 필터링 기능 구현 (`date_from` 파라미터)

### 🛠️ 코드 품질
- `TYPE_ICONS` 상수 통일 (3개 위치에서 중복 제거)
- `empty_trash()` rollback 추가 (DB 일관성 보장)

---

## 📝 v10.2 변경사항

### 🔐 보안 강화
- 마스터 비밀번호 강도 검증 추가 (8자 이상, 숫자+특수문자 필수)
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
- 만료된 임시 항목 자동 정리 (1시간 주기)
- 휴지통 만료 항목 자동 삭제 (1시간 주기)
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

```text
smartclipboard/
├── 클립모드 매니저.py                # 외부 호환 파사드
├── pyrightconfig.json               # Pylance/pyright 분석 범위
├── requirements.txt                 # Python 의존성
├── smartclipboard.spec              # PyInstaller 빌드 설정
├── smartclipboard_app/
│   ├── bootstrap.py
│   ├── legacy_main.py               # legacy payload loader
│   ├── legacy_payload.py            # payload manifest/hash helper
│   ├── legacy_main_payload.marshal  # 런타임 payload
│   ├── legacy_main_payload.manifest.json  # Python/source sync manifest
│   ├── managers/
│   └── ui/
│       ├── clipboard_guard.py       # internal copy flag helper
│       └── mainwindow_parts/        # MainWindow helper 분리 모듈
├── smartclipboard_core/
│   ├── actions.py
│   ├── database.py
│   └── worker.py
├── tests/
└── legacy/                          # 참조용 레거시 보관본
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

## 🧩 개발자/리팩토링 노트

- `smartclipboard_app/legacy_main.py`는 레거시 런타임을 로드하는 하이브리드 모듈입니다.
- 기본값(권장): payload 모드 (`smartclipboard_app/legacy_main_payload.marshal`) (env: 미설정 또는 `SMARTCLIPBOARD_LEGACY_IMPL=payload`)
- payload는 `legacy_main_payload.manifest.json`으로 현재 Python minor/source hash를 검증합니다.
- payload 로딩 실패(파일 누락/파싱 실패/manifest 불일치/실행 실패) 시 `legacy_main_src.py`로 자동 폴백하며, `LEGACY_IMPL_ACTIVE`/`LEGACY_IMPL_FALLBACK_REASON` 상수로 상태를 확인할 수 있습니다.
- 소스 모드(정적 분석/클래스/시그널 추적용): env `SMARTCLIPBOARD_LEGACY_IMPL=src`
- 복원된 원본 소스: `smartclipboard_app/legacy_main_src.py` (원본: `legacy/클립모드 매니저 (legacy).py`)
- Pylance/pyright는 루트 `pyrightconfig.json`을 기준으로 현행 유지보수 코드만 검사합니다.
- 직접 `clipboard.setText()`를 호출하는 경로는 `smartclipboard_app.ui.clipboard_guard.mark_internal_copy()`를 먼저 거쳐 자기 재수집 루프를 피합니다.
- JSON export/import는 `IMAGE` 항목용 `image_data_b64` round-trip을 지원하고, CSV/Markdown은 이미지 BLOB를 의도적으로 제외합니다.
- `FILE` 항목은 경로 목록 중심으로 동작하며, JSON은 `file_paths`/`file_path`, CSV/Markdown은 newline path content를 사용합니다.
- `FILE` 항목은 복원 시점뿐 아니라 목록/상세/미니 창에서 누락 경로 수를 먼저 보여주며, 일부만 남아 있으면 부분 복원 정책을 유지합니다.
- import 무결성 정책상 CSV 이미지 플레이스홀더는 복원하지 않고, JSON에서 매핑 불가 `collection_id`는 `NULL`, 비표준 timestamp는 정규화 또는 import 시각으로 대체합니다.
- `fetch_title`은 첫 URL만 대상으로 하며, 로컬/사설/메타데이터 주소 차단과 HTML 응답 제한을 기본 정책으로 유지합니다.
- 보안 보관함은 `vault_salt`와 `vault_verification`이 함께 있어야 정상 구성으로 간주하며, 손상 상태는 Reset 복구 흐름을 통해 정리합니다.
- 기존 모듈러 레이아웃 README는 `legacy/README (modular).md`에 보관되어 있습니다.

---

## ⚠️ 알려진 제한사항

- Windows 전용 (macOS/Linux 미지원)
- 일부 애플리케이션에서 글로벌 핫키 충돌 가능
- 이미지 히스토리는 크기에 따라 DB 용량 증가
- 스니펫 단축키는 앱이 활성화된 상태에서만 동작하는 앱 내부 단축키로 제한

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

---

## 2026-04-12 Stabilization Notes

- `ExportImportManager` 공개 메서드는 계속 `int`를 반환하고, 상세 결과는 `last_import_report` / `last_export_report`에 기록됩니다.
- JSON/CSV import는 시작 전에 `backups/pre_import_YYYYMMDD_HHMMSS.db` 백업을 만들고 파일 단위 단일 트랜잭션으로 반영되어, 중간 실패 시 전체 rollback 됩니다.
- `search_items()`는 FTS-first 정책을 유지하면서 FTS 0건일 때만 LIKE 보완 검색을 수행합니다. `_last_search_fallback`은 실제 FTS 오류일 때만 UI 경고용으로 켜집니다.
- `ClipboardActionManager`는 전용 `QThreadPool(maxThreadCount=4)`과 URL 기준 in-flight dedupe/cache를 사용하고, 늦게 도착한 title 결과는 현재 row의 첫 URL이 여전히 같은 경우에만 저장합니다.
- `history.file_signature` 컬럼과 인덱스를 사용해 `FILE` 중복 판별을 전체 row 순회 대신 canonicalized path signature lookup으로 처리합니다.
- 보안 보관함 복호화 텍스트는 프로세스 내 armed clipboard state로 추적되며, 30초 조건부 clear와 앱 종료 시 즉시 clear를 모두 수행합니다.
- 설정 저장 시 `mini_window_enabled` 변경으로 핫키 재등록이 실패하면 그 설정만 되돌리고 실제 `_last_hotkey_error`를 경고로 노출합니다.
- `smartclipboard.spec`은 이번 안정화 기준으로 payload manifest(`legacy_main_payload.manifest.json`)까지 포함하도록 정리되어 있으며, 별도 추가 hidden import 증설은 필요하지 않습니다.

## MainWindow 분할 구조 (2026-03-07)

- `smartclipboard_app/legacy_main_src.py`의 `MainWindow` 공개 메서드 시그니처는 유지됩니다.
- 실제 대형 메서드 본문은 `smartclipboard_app/ui/mainwindow_parts/`로 위임되었습니다.
  - `theme_ops.py`: `apply_theme`
  - `ui_ops.py`: `init_ui`, `eventFilter`, `_handle_drop_event`
  - `menu_ops.py`: `init_menu`, `show_context_menu`
  - `table_ops.py`: `load_data`, `_get_display_items`, `_show_empty_state`, `_populate_table`, `on_selection_changed`
- 시그널 스냅샷 검증(`scripts/refactor_signal_snapshot.py`, `tests/test_signal_snapshot.py`)은 `legacy_main_src.py`와 `mainwindow_parts/*.py`를 함께 스캔합니다.
- 로컬 사전검증(`scripts/preflight_local.py`)의 `py_compile` 단계에 `mainwindow_parts/*.py`가 포함됩니다.

## 문서 정합성 기준 (2026-04-13)

- 실행/빌드/검증 기준 문서는 루트 `README.md`이며, `claude.md`, `.gemini/GEMINI.md`, `legacy/README (modular).md`는 동일 기준을 따릅니다.
- 권장 회귀 테스트 기준은 `test_core`, `test_ui_dialogs_widgets`, `test_payload_sync`, `test_legacy_loader`, `test_migration_collections`, `test_legacy_ui_contracts`, `test_signal_snapshot`, `test_public_surfaces`입니다.
- PyInstaller 기준(`smartclipboard.spec`)은 payload 데이터(`legacy_main_payload.marshal`)와 payload manifest(`legacy_main_payload.manifest.json`)를 함께 포함하고, `smartclipboard_core`, `smartclipboard_app.ui.mainwindow_parts` 하위 모듈을 hidden import로 자동 수집하며, payload에서 직접 참조하는 대화상자 모듈(`smartclipboard_app.ui.dialogs.collections` 포함)을 명시적으로 유지합니다.
- 2026-04-13 기준 추가 패키징 자산은 payload manifest 1건이며, 현재 spec에 반영되어 있습니다.

## Refactor Layout (2026-03-12)

- `smartclipboard_core/database.py` is now a composition entrypoint.
- Database implementation is split under `smartclipboard_core/db_parts/`:
  - `schema_search.py`
  - `history_ops.py`
  - `rules_snippets_actions.py`
  - `tags_collections.py`
  - `vault_trash.py`
- MainWindow helper logic in `smartclipboard_app/ui/mainwindow_parts/` is expanded:
  - `theme_style_sections.py` (theme QSS builder split)
  - `ui_init_sections.py`, `ui_dragdrop_ops.py` (`ui_ops.py` wrappers)
  - `tray_hotkey_ops.py`, `status_lifecycle_ops.py`, `clipboard_runtime_ops.py`
- `scripts/preflight_local.py` now compiles both `mainwindow_parts/*.py` and `db_parts/*.py`.
- Added surface-guard test: `tests/test_public_surfaces.py` and baseline `tests/baseline/clipboarddb_public_methods.txt`.

# SmartClipboard Pro — 프로젝트 구조 분석

> **기준일:** 2026-03-21
> **버전:** v10.6
> **목적:** 신규 기능 추가를 위한 코드베이스 심층 분석

---

## 목차

1. [프로젝트 개요](#1-프로젝트-개요)
2. [전체 디렉터리 구조](#2-전체-디렉터리-구조)
3. [런타임 아키텍처](#3-런타임-아키텍처)
4. [레이어별 모듈 분석](#4-레이어별-모듈-분석)
   - [4.1 진입점 / 부트스트랩](#41-진입점--부트스트랩)
   - [4.2 Core 레이어](#42-core-레이어)
   - [4.3 UI 레이어](#43-ui-레이어)
   - [4.4 Manager 레이어](#44-manager-레이어)
5. [데이터베이스 스키마](#5-데이터베이스-스키마)
6. [클립보드 액션 시스템](#6-클립보드-액션-시스템)
7. [현재 구현된 기능 목록](#7-현재-구현된-기능-목록)
8.1 [2026-03-25 구현 동기화 메모](#81-2026-03-25-구현-동기화-메모)
8. [기능 추가 가이드](#8-기능-추가-가이드)
9. [주요 클래스 관계도](#9-주요-클래스-관계도)
10. [알려진 제한사항 및 미구현 항목](#10-알려진-제한사항-및-미구현-항목)
11. [검증 및 빌드 절차](#11-검증-및-빌드-절차)

---

## 1. 프로젝트 개요

SmartClipboard Pro는 **PyQt6** 기반 Windows 전용 클립보드 관리 데스크톱 앱이다.
텍스트·이미지·링크·코드·색상 코드를 자동 분류하여 SQLite DB에 영구 저장하고,
태그·컬렉션·북마크·암호화 보관함·자동화 액션 등 고급 기능을 제공한다.

| 항목 | 값 |
|------|-----|
| 진입점 | `클립모드 매니저.py` |
| UI 프레임워크 | PyQt6 ≥ 6.4.0 |
| 데이터 저장 | SQLite 3 (WAL 모드) |
| 빌드 산출물 | `dist/SmartClipboard.exe` (~40MB) |
| 대상 OS | Windows 10/11 |
| Python 지원 | 3.10 / 3.11 / 3.12 / 3.13 |

---

## 2. 전체 디렉터리 구조

```
smartclipboard/
│
├── 클립모드 매니저.py              ← 외부 호환 파사드 (진입점)
├── pyrightconfig.json             ← 정적 분석 범위 정의
├── requirements.txt               ← Python 의존성
├── smartclipboard.spec            ← PyInstaller 빌드 설정
│
├── smartclipboard_app/
│   ├── bootstrap.py               ← QApplication 초기화, 예외 훅
│   ├── legacy_main.py             ← 하이브리드 payload 로더
│   ├── legacy_main_src.py         ← 복원된 소스 스냅샷 (1,741줄)
│   ├── legacy_main_payload.marshal ← 바이너리 런타임 payload
│   │
│   ├── managers/
│   │   ├── export_import.py       ← JSON/CSV/MD 내보내기·가져오기
│   │   └── secure_vault.py        ← PBKDF2+Fernet 암호화 관리자
│   │
│   └── ui/
│       ├── main_window.py         ← MainWindow 컴포지터
│       ├── clipboard_guard.py     ← 내부 복사 플래그 헬퍼
│       │
│       ├── controllers/           ← 얇은 위임 레이어 (4개)
│       │   ├── clipboard_controller.py
│       │   ├── table_controller.py
│       │   ├── tray_hotkey_controller.py
│       │   └── lifecycle_controller.py
│       │
│       ├── dialogs/               ← 모달 다이얼로그 (12종)
│       │   ├── settings.py
│       │   ├── secure_vault.py
│       │   ├── clipboard_actions.py
│       │   ├── copy_rules.py
│       │   ├── export_dialog.py
│       │   ├── import_dialog.py
│       │   ├── trash_dialog.py
│       │   ├── hotkeys.py
│       │   ├── snippets.py
│       │   ├── tags.py
│       │   ├── statistics.py
│       │   └── collections.py
│       │
│       ├── widgets/               ← 커스텀 위젯
│       │   ├── floating_mini_window.py  ← 플로팅 미니 창
│       │   └── toast.py                ← 토스트 알림
│       │
│       └── mainwindow_parts/     ← MainWindow 대형 메서드 분할 (11개)
│           ├── theme_ops.py
│           ├── theme_style_sections.py  ← QSS 스타일시트 생성 (464줄)
│           ├── ui_init_sections.py      ← 위젯 생성·레이아웃 (301줄)
│           ├── ui_ops.py
│           ├── ui_dragdrop_ops.py       ← 고정 항목 드래그앤드롭 (124줄)
│           ├── menu_ops.py              ← 컨텍스트·트레이 메뉴 (278줄)
│           ├── table_ops.py             ← 히스토리 테이블 표시·필터 (255줄)
│           ├── tray_hotkey_ops.py       ← 핫키 등록·트레이 (147줄)
│           ├── status_lifecycle_ops.py  ← 상태바, 볼트 타임아웃 (130줄)
│           └── clipboard_runtime_ops.py ← 클립보드 모니터링·처리 (155줄)
│
├── smartclipboard_core/
│   ├── database.py                ← ClipboardDB 컴포지터 (mixin 조합)
│   ├── actions.py                 ← ClipboardActionManager
│   ├── worker.py                  ← 비동기 Worker + WorkerSignals
│   │
│   └── db_parts/                 ← DB mixin 모듈 (6개)
│       ├── shared.py              ← 공통 상수
│       ├── schema_search.py       ← 스키마 생성 + FTS5 검색 (406줄)
│       ├── history_ops.py         ← 히스토리 CRUD (467줄)
│       ├── rules_snippets_actions.py ← 규칙·스니펫·액션 (198줄)
│       ├── tags_collections.py    ← 태그·컬렉션 (227줄)
│       └── vault_trash.py         ← 보안 보관함·휴지통 (151줄)
│
├── tests/
│   ├── test_payload_sync.py       ← payload/src 시그니처 동기화
│   ├── test_legacy_loader.py      ← payload 폴백 동작
│   ├── test_migration_collections.py ← JSON 마이그레이션·컬렉션 remap
│   ├── test_signal_snapshot.py    ← 시그널 연결 스냅샷
│   ├── test_public_surfaces.py    ← ClipboardDB 공개 API 회귀
│   ├── test_legacy_ui_contracts.py
│   ├── test_ui_dialogs_widgets.py
│   ├── test_core.py
│   ├── test_symbol_inventory.py
│   └── baseline/
│       ├── clipboarddb_public_methods.txt   ← 71개 공개 메서드 기준선
│       ├── mainwindow_signal_connects.txt
│       └── symbol_inventory_v10_6.json      ← 심볼 인벤토리 (39KB)
│
├── scripts/
│   ├── build_legacy_payload.py    ← legacy_main_src.py → .marshal 직렬화
│   ├── preflight_local.py         ← 로컬 사전검증 (payload+compile+test)
│   ├── refactor_symbol_inventory.py
│   └── refactor_signal_snapshot.py
│
├── .github/workflows/ci.yml       ← GitHub Actions CI
│
└── legacy/                        ← 참조용 레거시 보관본
    ├── 클립모드 매니저 (legacy).py
    ├── README (legacy).md
    └── README (modular).md
```

---

## 3. 런타임 아키텍처

### 3.1 하이브리드 로더 패턴

```
클립모드 매니저.py  (파사드)
    │
    └─► smartclipboard_app.bootstrap.run()
            │
            └─► MainWindow  (ui/main_window.py — 컴포지터)
                    │
                    └─► LegacyMainWindow  ←── 로더 선택
                                │
                    ┌───────────┴──────────────┐
                    │                          │
            [payload 모드]              [src 모드 / 폴백]
     legacy_main_payload.marshal      legacy_main_src.py
        (기본·배포용)                  (개발·분석·폴백용)
```

**모드 선택 (`SMARTCLIPBOARD_LEGACY_IMPL` 환경변수):**

| 값 | 설명 |
|----|------|
| 미설정 / `payload` | 바이너리 marshal 로드 (기본) |
| `src` | `legacy_main_src.py` 직접 로드 |
| 자동 폴백 | payload 파싱 실패 시 src로 전환 |

상태 확인: `LEGACY_IMPL_ACTIVE`, `LEGACY_IMPL_FALLBACK_REASON` 상수.

### 3.2 컨트롤러 위임 구조

```
MainWindow
├── ClipboardController    ← 클립보드 모니터링·텍스트/이미지 처리
├── TableController        ← 히스토리 테이블 표시·선택
├── TrayHotkeyController   ← 시스템 트레이·글로벌 핫키
└── LifecycleController    ← 볼트 타임아웃·정리·앱 종료
```

---

## 4. 레이어별 모듈 분석

### 4.1 진입점 / 부트스트랩

#### `클립모드 매니저.py`
- 외부 호환 파사드. `smartclipboard_app.bootstrap.run()` 호출.
- MainWindow, ClipboardDB 등 핵심 클래스를 re-export.
- **수정 시 주의:** 이 파일의 공개 export 목록은 외부 계약으로 유지해야 한다.

#### `smartclipboard_app/bootstrap.py`
- `QApplication` 생성 (High-DPI, 기본 폰트: Malgun Gothic)
- 전역 예외 훅 등록
- `--minimized` 플래그 지원
- 이전 디버그 오류 로그 정리

---

### 4.2 Core 레이어

#### `smartclipboard_core/database.py` — `ClipboardDB`

5개 mixin의 다중 상속 컴포지터:

```python
class ClipboardDB(
    SchemaSearchMixin,         # 스키마·FTS5 검색
    HistoryOpsMixin,           # 히스토리 CRUD
    RulesSnippetsActionsMixin, # 규칙·스니펫·액션
    TagsCollectionsMixin,      # 태그·컬렉션
    VaultTrashMixin,           # 보안 보관함·휴지통
):
```

**연결 설정:**
- SQLite WAL 모드, `synchronous=NORMAL`
- `threading.RLock()` — 재진입 가능 스레드 안전

**71개 공개 메서드** (기준선: `tests/baseline/clipboarddb_public_methods.txt`)

#### `smartclipboard_core/db_parts/`

| 파일 | 핵심 책임 | 주요 메서드 |
|------|-----------|-------------|
| `schema_search.py` | 테이블 생성, FTS5, 통합 검색 | `create_tables()`, `search_items()` |
| `history_ops.py` | 히스토리 CRUD, 핀 관리 | `add_item()`, `get_items()`, `toggle_pin()`, `update_pin_orders()` |
| `rules_snippets_actions.py` | 스니펫, 규칙, 액션 | `add_snippet()`, `add_clipboard_action()`, `get_copy_rules()` |
| `tags_collections.py` | 태그, 컬렉션 | `set_item_tags()`, `add_collection()`, `assign_to_collection()` |
| `vault_trash.py` | 암호화 보관함, 휴지통 | `add_vault_item()`, `soft_delete()`, `restore_item()`, `empty_trash()` |

**중복 방지 정책 (`add_item`):**
- 동일 비이미지 텍스트 재복사 시: 기존 row의 tags/note/bookmark/collection/pin/use_count **유지**, timestamp/content/type만 갱신.

#### `smartclipboard_core/actions.py` — `ClipboardActionManager`

정규식 기반 자동화 엔진. 지원 액션:

| 액션 | 설명 |
|------|------|
| `fetch_title` | 첫 번째 URL 추출 → 비동기 웹 페이지 제목 가져오기 |
| `format_phone` | 전화번호 자동 포맷팅 (010-xxxx-xxxx, 02-xxx-xxxx) |
| `format_email` | 이메일 정규화 (소문자, 공백 제거) |
| `notify` | 토스트 알림 표시 |
| `transform` | 텍스트 변환 (trim/upper/lower) |

**`fetch_title` 규칙:** 텍스트 전체가 아닌 **첫 URL만** 추출해서 제목 요청.

#### `smartclipboard_core/worker.py` — `Worker` / `WorkerSignals`

```python
class WorkerSignals(QObject):
    finished = pyqtSignal()
    error = pyqtSignal(tuple)
    result = pyqtSignal(object)

class Worker(QRunnable):
    # QThreadPool에 제출되는 비동기 태스크
```

---

### 4.3 UI 레이어

#### `smartclipboard_app/ui/main_window.py` — `MainWindow`

`LegacyMainWindow`를 상속하고 4개 컨트롤러를 붙이는 컴포지터 클래스.
**메서드 시그니처는 외부 계약 — 변경 금지.**

#### `smartclipboard_app/legacy_main_src.py` — `LegacyMainWindow` (1,741줄)

핵심 PyQt6 창. 대형 메서드는 `mainwindow_parts/` 헬퍼로 위임.

**주요 시그널:**
- `clipboard_changed`
- `action_completed`
- `search_text_changed`
- `item_selection_changed`

**글로벌 핫키:**

| 단축키 | 기능 |
|--------|------|
| `Ctrl+Shift+V` | 메인 창 표시 |
| `Alt+V` | 미니 창 토글 |
| `Ctrl+Shift+Z` | 마지막 항목 즉시 붙여넣기 |

**앱 내 단축키:**

| 단축키 | 기능 |
|--------|------|
| `Ctrl+F` | 검색창 포커스 |
| `Ctrl+C` | 선택 항목 복사 |
| `Ctrl+P` | 고정/해제 토글 |
| `Ctrl+G` | 구글 검색 |
| `Enter` | 복사 후 붙여넣기 |
| `Delete` | 항목 삭제 |
| `Escape` | 창 숨기기 |

#### `mainwindow_parts/` 헬퍼 모듈 요약

| 모듈 | 위임받은 책임 |
|------|--------------|
| `theme_ops.py` | `apply_theme()` — 5개 테마 전환 |
| `theme_style_sections.py` | QSS 스타일시트 생성 (464줄) |
| `ui_init_sections.py` | 위젯 생성·레이아웃 초기화 (301줄) |
| `ui_ops.py` | `eventFilter`, 키보드 단축키 |
| `ui_dragdrop_ops.py` | 고정 항목 드래그앤드롭 재정렬 |
| `menu_ops.py` | 우클릭 컨텍스트 메뉴, 트레이 메뉴 |
| `table_ops.py` | 히스토리 테이블 렌더링·필터링 |
| `tray_hotkey_ops.py` | `keyboard` 라이브러리 핫키 등록 |
| `status_lifecycle_ops.py` | 상태바, 볼트 자동잠금 타이머 |
| `clipboard_runtime_ops.py` | `QClipboard` 변경 감지·처리 |

#### 다이얼로그 목록 (`smartclipboard_app/ui/dialogs/`)

| 파일 | 기능 |
|------|------|
| `settings.py` | 테마·핫키·히스토리 한도 설정 |
| `secure_vault.py` | 마스터 비밀번호, 보관함 항목 관리 |
| `clipboard_actions.py` | 자동화 액션 규칙 생성·편집 |
| `copy_rules.py` | 레거시 텍스트 변환 규칙 |
| `export_dialog.py` | JSON/CSV/MD 내보내기 (공통 날짜·타입 필터) |
| `import_dialog.py` | JSON/CSV 가져오기 |
| `trash_dialog.py` | 휴지통 복원·영구 삭제 (다중 선택) |
| `hotkeys.py` | 글로벌 핫키 구성·검증·저장 실패 롤백 |
| `snippets.py` | 스니펫 생성·편집·관리자·app-local shortcut |
| `tags.py` | 태그 편집 |
| `statistics.py` | 히스토리 통계 대시보드 |
| `collections.py` | 컬렉션 생성·편집·삭제·관리 |

#### 위젯 (`smartclipboard_app/ui/widgets/`)

- **`floating_mini_window.py`** — 컴팩트 플로팅 클립보드 뷰어 (Alt+V)
- **`toast.py`** — 슬라이드 애니메이션 임시 알림
- **`clipboard_guard.py`** — `mark_internal_copy()` 내부 복사 플래그 (자기 재수집 루프 방지)

---

### 4.4 Manager 레이어

#### `smartclipboard_app/managers/export_import.py` — `ExportImportManager`

| 형식 | 기능 |
|------|------|
| JSON (내보내기) | 메타데이터 포함 (`include_metadata=True`): tags/note/bookmark/collections/use_count |
| JSON (가져오기) | 컬렉션 ID remap, IMAGE는 `image_data_b64` round-trip |
| CSV | 날짜·타입 필터 공통 적용, IMAGE는 플레이스홀더 행으로 기록 |
| Markdown | 날짜·타입 필터 공통 적용, IMAGE는 설명용 플레이스홀더만 기록 |

**JSON 마이그레이션 포맷** — `items` 외에 top-level `collections` 메타데이터(legacy_id/name/icon/color) 포함.

#### `smartclipboard_app/managers/secure_vault.py` — `SecureVaultManager`

- **KDF:** PBKDF2-HMAC-SHA256 (480,000 iterations)
- **암호화:** Fernet (대칭)
- **Salt:** 16바이트 랜덤, base64 저장
- **자동 잠금:** 5분 비활성 타임아웃
- **검증:** 암호화된 "VAULT_VERIFIED" 토큰
- **비밀번호 변경:** 기존 보관 항목 전체 재암호화 후 salt/verification 갱신
- **클립보드 보호:** 복호화 복사 텍스트 30초 후 조건부 자동 삭제

---

## 5. 데이터베이스 스키마

### `history` 테이블 (핵심)

| 컬럼 | 타입 | 설명 |
|------|------|------|
| `id` | INTEGER PK | 자동 증가 |
| `content` | TEXT | 텍스트 내용 |
| `image_data` | BLOB | 이미지 데이터 (최신 20개 유지) |
| `type` | TEXT | `TEXT` / `LINK` / `IMAGE` / `CODE` / `COLOR` |
| `timestamp` | TEXT | ISO 형식 생성 시각 |
| `pinned` | INTEGER | 고정 여부 (1=고정) |
| `pin_order` | INTEGER | 고정 항목 정렬 순서 |
| `use_count` | INTEGER | 붙여넣기 횟수 |
| `tags` | TEXT | 쉼표 구분 태그 목록 |
| `note` | TEXT | 사용자 메모 |
| `bookmark` | INTEGER | 북마크 여부 |
| `collection_id` | INTEGER | FK → collections |
| `url_title` | TEXT | 웹 페이지 제목 캐시 |
| `expires_at` | TEXT | 임시 항목 만료 시각 |

### 전체 테이블 목록

| 테이블 | 역할 |
|--------|------|
| `history` | 클립보드 히스토리 |
| `snippets` | 텍스트 템플릿 (category, shortcut, created_at) |
| `settings` | 앱 설정 (key/value) |
| `copy_rules` | 레거시 텍스트 변환 규칙 |
| `secure_vault` | 암호화된 민감 데이터 |
| `clipboard_actions` | 자동화 규칙 (pattern/action_type/priority/enabled) |
| `collections` | 컬렉션 (name/icon/color) |
| `deleted_history` | 소프트 삭제된 항목 (7일 보관) |
| `history_fts` | FTS5 전문 검색 인덱스 (온디맨드 생성) |

### 검색 전략

1. **FTS5** — 토큰화 검색, BM25 관련성 순위 (가능 시)
2. **LIKE 폴백** — FTS5 미지원 환경
3. **복합 필터** — query + type + tag + collection_id + bookmark + uncategorized 동시 적용

---

## 6. 클립보드 액션 시스템

### 처리 흐름

```
클립보드 변경 감지 (QClipboard)
    │
    ▼
clipboard_guard 확인 (내부 복사 여부)
    │
    ▼
content_type 분류 (TEXT/LINK/IMAGE/CODE/COLOR)
    │
    ▼
ClipboardDB.add_item() — 중복 처리
    │
    ▼
ClipboardActionManager.process(text, item_id)
    │
    ├─► 패턴 매칭 (컴파일된 정규식)
    │
    ├─► fetch_title  → Worker(QRunnable) → 비동기 HTTP 요청
    │                                    → update_url_title() 콜백
    │
    ├─► format_phone → 즉시 변환
    ├─► format_email → 즉시 변환
    ├─► notify      → toast.show()
    └─► transform   → 즉시 변환
```

### 내부 복사 루프 방지

```python
# 직접 clipboard.setText() 전 반드시 호출
from smartclipboard_app.ui.clipboard_guard import mark_internal_copy
mark_internal_copy()
clipboard.setText(text)
```

---

## 7. 현재 구현된 기능 목록

### 클립보드 히스토리
- [x] 텍스트/이미지/링크/코드/색상 자동 분류 저장
- [x] 최대 500개 항목 (설정 가능)
- [x] 중복 항목 자동 병합 (메타데이터 유지)
- [x] 고정(Pin) 기능 + 드래그앤드롭 순서 변경
- [x] 태그 시스템
- [x] 북마크
- [x] 컬렉션 (그룹화)
- [x] 항목별 메모
- [x] 소프트 삭제 → 휴지통 (7일 보관)
- [x] 자동 DB 백업 (일 1회, 최근 7일)
- [x] 이미지 히스토리 최신 20개 제한

### 검색
- [x] FTS5 전문 검색 (LIKE 폴백)
- [x] 타입 필터
- [x] 태그 필터
- [x] 북마크 필터
- [x] 컬렉션 필터
- [x] 미분류 필터

### 보안
- [x] PBKDF2-HMAC-SHA256 + Fernet 암호화 보관함
- [x] 마스터 비밀번호 (8자+숫자+특수문자)
- [x] 5분 자동 잠금
- [x] 마스터 비밀번호 변경 + 전체 보관 항목 재암호화
- [x] 복호화 클립보드 30초 자동 삭제

### 자동화
- [x] URL 제목 자동 가져오기 (비동기)
- [x] 전화번호 자동 포맷팅
- [x] 이메일 정규화
- [x] 텍스트 변환 (대소문자/트림)
- [x] 패턴 기반 토스트 알림
- [x] 액션/규칙 생성·수정·삭제·우선순위 이동 UI

### UI/UX
- [x] 5가지 테마 (다크/라이트/오션/퍼플/미드나잇)
- [x] 글래스모피즘 디자인
- [x] 플로팅 미니 창 (Alt+V)
- [x] 시스템 트레이 최소화
- [x] 글로벌 핫키 (Ctrl+Shift+V / Alt+V / Ctrl+Shift+Z)
- [x] 핫키 저장 실패 시 이전 상태 롤백
- [x] 컬렉션 관리 다이얼로그
- [x] 앱 내부 스니펫 단축키
- [x] 토스트 알림 (슬라이드 애니메이션)
- [x] 드래그앤드롭 파일 지원

### 데이터 관리
- [x] JSON/CSV/Markdown 내보내기
- [x] JSON/CSV 가져오기
- [x] 이미지 base64 round-trip (JSON)
- [x] 컬렉션 메타데이터 마이그레이션
- [x] JSON/CSV/Markdown 공통 날짜·타입 필터
- [x] 전체 기록 삭제 시 휴지통 이동

### 기타
- [x] 텍스트 스니펫 (카테고리별 저장)
- [x] 통계 다이얼로그
- [x] 레거시 복사 규칙 (copy_rules)
- [x] QR 코드 생성 (선택적 의존성)

---

## 8.1 2026-03-25 구현 동기화 메모

- `history_ops.cleanup()`은 이제 `timestamp ASC, id ASC` 순으로 가장 오래된 항목부터 정리한다.
- `clear_all_history()` 경로는 영구 삭제 대신 `soft_delete_unpinned()`를 사용해 휴지통 정책과 일치한다.
- JSON 재-import는 컬렉션 이름을 정규화해서 기존 컬렉션을 재사용하며, 중복 이름의 컬렉션을 새로 만들지 않는다.
- `copy_rules` / `clipboard_actions`는 `priority` 컬럼을 실제 UI 순서와 동기화한다.
- `ExportImportManager`는 JSON/CSV/Markdown에 동일한 날짜·타입 필터를 적용하고, CSV/Markdown의 IMAGE는 플레이스홀더만 기록한다.
- `SecureVaultManager`는 마스터 비밀번호 변경과 클립보드 30초 자동 정리 흐름을 지원한다.
- `smartclipboard.spec`는 payload 경로에서 누락되지 않도록 `smartclipboard_app.ui.dialogs.collections`를 hidden import에 포함한다.

---

## 8. 기능 추가 가이드

### 8.1 새 DB 기능 추가

1. 적절한 mixin 파일(`db_parts/*.py`)에 메서드 추가
2. `ClipboardDB`는 자동으로 상속 — 별도 등록 불필요
3. `tests/baseline/clipboarddb_public_methods.txt` 업데이트
4. `test_public_surfaces.py` 재실행으로 API 회귀 확인

### 8.2 새 클립보드 액션 추가

`smartclipboard_core/actions.py`의 `process()` 메서드에 액션 타입 추가:
```python
elif action_type == "my_new_action":
    result = self._handle_my_new_action(text, params)
```

### 8.3 새 다이얼로그 추가

1. `smartclipboard_app/ui/dialogs/` 에 새 파일 생성
2. `legacy_main_src.py`의 메뉴/버튼 핸들러에서 호출
3. `smartclipboard.spec`의 hidden imports 목록에 모듈 추가
4. payload 재빌드: `python scripts/build_legacy_payload.py ...`

### 8.4 UI 위젯/섹션 추가

- 신규 위젯: `smartclipboard_app/ui/widgets/` 에 작성
- MainWindow 레이아웃 변경: `mainwindow_parts/ui_init_sections.py` 수정
- 스타일: `mainwindow_parts/theme_style_sections.py` 에 QSS 추가

### 8.5 새 설정값 추가

`ClipboardDB`의 `get_setting()` / `set_setting()` 활용:
```python
db.set_setting("my_feature_enabled", "1")
value = db.get_setting("my_feature_enabled", default="0")
```

### 8.6 변경 후 필수 검증

```powershell
# 정적 분석 (변경 파일 기준)
pyright smartclipboard_core/actions.py smartclipboard_app/ui/dialogs/new_dialog.py

# payload 재빌드 (legacy_main_src.py 변경 시 반드시)
python scripts/build_legacy_payload.py --src smartclipboard_app/legacy_main_src.py --out smartclipboard_app/legacy_main_payload.marshal --smoke-import

# 전체 사전검증
python scripts/preflight_local.py
```

---

## 9. 주요 클래스 관계도

```
QApplication (bootstrap.py)
    └── MainWindow (ui/main_window.py)
            │ 상속
            └── LegacyMainWindow (legacy_main_src.py)
                    │ 사용
                    ├── ClipboardDB (smartclipboard_core/database.py)
                    │       ├── SchemaSearchMixin
                    │       ├── HistoryOpsMixin
                    │       ├── RulesSnippetsActionsMixin
                    │       ├── TagsCollectionsMixin
                    │       └── VaultTrashMixin
                    │
                    ├── ClipboardActionManager (smartclipboard_core/actions.py)
                    │       └── Worker (smartclipboard_core/worker.py)
                    │
                    ├── SecureVaultManager (managers/secure_vault.py)
                    ├── ExportImportManager (managers/export_import.py)
                    │
                    ├── [mainwindow_parts/*.py 헬퍼 함수들]
                    │
                    ├── 다이얼로그들 (ui/dialogs/*.py)
                    └── 위젯들 (ui/widgets/*.py)
```

---

## 10. 알려진 제한사항 및 미구현 항목

| 항목 | 상태 | 비고 |
|------|------|------|
| macOS/Linux 지원 | 미지원 | Windows 전용 (`keyboard` 라이브러리) |
| 스니펫 `shortcut` 단축키 | 지원됨 | 앱 활성 상태에서만 동작하는 app-local 단축키 |
| 일부 앱에서 글로벌 핫키 충돌 | 알려진 제한 | `keyboard` 라이브러리 한계 |
| repo-wide pyright 노이즈 | `db_parts/*.py` mixin | 변경 파일 기준으로만 실행 |
| `legacy_main.py` 소스 복원 | 장기 목표 | 현재는 payload+src 하이브리드 |

---

## 11. 검증 및 빌드 절차

### 로컬 사전검증 (권장)

```powershell
python scripts/preflight_local.py
```

내부 동작:
1. payload 재생성 + smoke import
2. `py_compile` (전체 대상 모듈)
3. `unittest discover`

### 단계별 실행

```powershell
# 1. 정적 분석 (변경 파일 기준)
pyright <touched-files>

# 2. payload 재빌드
python scripts/build_legacy_payload.py \
    --src smartclipboard_app/legacy_main_src.py \
    --out smartclipboard_app/legacy_main_payload.marshal \
    --smoke-import

# 3. 컴파일 검증
python -m py_compile "클립모드 매니저.py" "smartclipboard_app/bootstrap.py" ...

# 4. 테스트
python -m unittest discover -s tests -v
```

### 핵심 회귀 테스트

| 테스트 | 검증 대상 |
|--------|-----------|
| `test_payload_sync.py` | payload/src 시그니처 동기화 |
| `test_legacy_loader.py` | payload 폴백 동작 |
| `test_migration_collections.py` | JSON 마이그레이션·컬렉션 remap |
| `test_legacy_ui_contracts.py` | 토스트·선택모드·가시성 가드 |
| `test_signal_snapshot.py` | MainWindow 시그널 스냅샷 |
| `test_public_surfaces.py` | ClipboardDB 공개 API 회귀 |

### 빌드

```powershell
python scripts/build_legacy_payload.py \
    --src smartclipboard_app/legacy_main_src.py \
    --out smartclipboard_app/legacy_main_payload.marshal \
    --smoke-import
pyinstaller --clean smartclipboard.spec
# → dist/SmartClipboard.exe
```

### CI (GitHub Actions)

- 파일: `.github/workflows/ci.yml`
- 환경: `windows-latest`
- 매트릭스: Python 3.10 / 3.11 / 3.12 / 3.13

---

*이 문서는 2026-03-21 기준 v10.6 코드베이스를 분석하여 작성되었습니다.*
*코드 변경 시 해당 섹션을 업데이트해 주세요.*

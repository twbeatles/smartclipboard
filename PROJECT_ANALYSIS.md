# SmartClipboard Pro — 프로젝트 구조 분석

> **기준일:** 2026-06-10
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
텍스트·이미지·링크·코드·색상·파일/폴더를 자동 분류하여 SQLite DB에 영구 저장하고,
태그·컬렉션·북마크·암호화 보관함·자동화 액션 등 고급 기능을 제공한다.

| 항목 | 값 |
|------|-----|
| 진입점 | `클립모드 매니저.py` |
| UI 프레임워크 | PyQt6 ≥ 6.4.0 |
| 데이터 저장 | SQLite 3 (WAL 모드) |
| 빌드 산출물 | `dist/SmartClipboard.exe` (`smartclipboard.spec`는 `upx=True`를 요청하지만 실제 빌드 출력은 로컬 UPX 도구 가용성에 따라 달라질 수 있음) |
| 대상 OS | Windows 10/11 |
| Python 지원 | 3.10 / 3.11 / 3.12 / 3.13 / 3.14 |

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
│   ├── legacy_main.pyi            ← payload 로더 공개 export 타입 보강
│   ├── legacy_payload.py          ← payload manifest/hash 유틸
│   ├── legacy_main_src.py         ← 복원된 호환 소스 스냅샷 (1,570줄)
│   ├── legacy_main_payload.marshal ← 바이너리 런타임 payload
│   ├── legacy_main_payload.manifest.json ← Python/source sync manifest
│   │
│   ├── managers/
│   │   ├── export_import.py       ← JSON/CSV/MD 내보내기·가져오기
│   │   └── secure_vault.py        ← PBKDF2+Fernet 암호화 관리자
│   │
│   ├── features/                  ← 도메인별 실제 구현
│   │   ├── clipboard/             ← clipboard runtime pipeline/controller
│   │   ├── dialogs/               ← MainWindow dialog launcher
│   │   ├── history/               ← table/menu/view/interaction
│   │   ├── import_export/         ← manager 구현 + helper services
│   │   ├── settings/styles/       ← QSS section builders
│   │   ├── shell/window_bootstrap.py ← MainWindow 초기화 orchestration
│   │   ├── shell_ui/              ← layout/drag-drop/view
│   │   ├── tray_hotkey/           ← tray/global hotkey
│   │   └── vault/                 ← secure vault service
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
│       └── mainwindow_parts/     ← MainWindow legacy shim (11개)
│           ├── theme_ops.py
│           ├── theme_style_sections.py  ← QSS facade
│           ├── ui_init_sections.py      ← UI init facade
│           ├── ui_ops.py
│           ├── ui_dragdrop_ops.py       ← 고정 항목 드래그앤드롭 (124줄)
│           ├── menu_ops.py              ← 메뉴 shim
│           ├── table_ops.py             ← 테이블 shim
│           ├── tray_hotkey_ops.py       ← 핫키/트레이 shim
│           ├── status_lifecycle_ops.py  ← lifecycle shim
│           └── clipboard_runtime_ops.py ← clipboard runtime shim
│
├── smartclipboard_core/
│   ├── database.py                ← ClipboardDB 컴포지터 (mixin 조합)
│   ├── app_paths.py               ← source/frozen app data directory resolver
│   ├── actions.py                 ← ClipboardActionManager
│   ├── file_paths.py              ← FILE 경로 정규화/설명/중복 시그니처 헬퍼
│   ├── worker.py                  ← 비동기 Worker + WorkerSignals
│   │
│   └── db_parts/                 ← DB mixin facade + subpackages
│       ├── shared.py              ← 공통 상수/app path resolver 연결
│       ├── typing_helpers.py      ← DB mixin 정적 분석 보강
│       ├── schema_search.py       ← schema/search facade
│       ├── history_ops.py         ← history facade
│       ├── history/               ← write/query/metadata/delete/maintenance
│       ├── rules_snippets_actions.py ← 규칙·스니펫·액션 facade
│       ├── tags_collections.py    ← 태그·컬렉션 facade
│       └── vault_trash.py         ← 보안 보관함·휴지통 facade
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
| 자동 폴백 | payload 파싱 실패, manifest 불일치, 실행 실패 시 src로 전환 |

상태 확인: `LEGACY_IMPL_ACTIVE`, `LEGACY_IMPL_FALLBACK_REASON` 상수.

### 3.2 컨트롤러 위임 구조

```
MainWindow
├── ClipboardController    ← 클립보드 모니터링·텍스트/이미지 처리
├── TableController        ← 히스토리 테이블 표시·선택
├── TrayHotkeyController   ← 시스템 트레이·글로벌 핫키
├── LifecycleController    ← 볼트 타임아웃·정리·앱 종료
├── SettingsController     ← 설정 helper facade
└── ShellUiController      ← layout/drag-drop/view orchestration
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
| `history_ops.py` | history facade | `HistoryOpsMixin` |
| `history/write.py` | insert/update/duplicate merge | `add_item()`, `replace_text_item_or_merge()` |
| `history/queries.py` | history read models | `get_items()`, `get_content()`, `get_top_items()` |
| `history/metadata.py` | pin/bookmark/note metadata | `toggle_pin()`, `update_pin_orders()`, `set_item_metadata()` |
| `history/deletion.py` | hard/soft delete entry points | `delete_item()`, `clear_all()`, `soft_delete_unpinned()` |
| `history/maintenance.py` | cleanup/backup/temp/close | `cleanup()`, `backup_db()`, `cleanup_expired_items()` |
| `rules_snippets_actions.py` | 스니펫, 규칙, 액션 | `add_snippet()`, `add_clipboard_action()`, `get_copy_rules()` |
| `tags_collections.py` | 태그, 컬렉션 | `set_item_tags()`, `add_collection()`, `assign_to_collection()` |
| `vault_trash.py` | 암호화 보관함, 휴지통 | `add_vault_item()`, `soft_delete()`, `restore_item()`, `empty_trash()` |

**중복 방지 정책 (`add_item`):**
- 동일 비이미지 텍스트 재복사 시: 기존 row의 tags/note/bookmark/collection/pin/use_count **유지**, timestamp/content/type만 갱신.
- 동일 `FILE` path 집합 재복사 시: 기존 row의 metadata를 유지하고 `content/file_path/timestamp`만 갱신.

#### `smartclipboard_core/actions.py` — `ClipboardActionManager`

정규식 기반 자동화 엔진. 지원 액션:

| 액션 | 설명 |
|------|------|
| `fetch_title` | 첫 번째 URL 추출 → 비동기 웹 페이지 제목 가져오기 |
| `format_phone` | 전화번호 자동 포맷팅 (`02`, 일반 지역번호, `0505`, `15xx/16xx/18xx`) |
| `format_email` | 이메일 정규화 (소문자, 공백 제거) |
| `notify` | 토스트 알림 표시 |
| `transform` | 텍스트 변환 (trim/upper/lower) |

**액션 체인 규칙:**
- `format_phone` / `format_email` / `transform`은 `replace_text` 결과를 반환하고 working text를 즉시 갱신한다.
- `fetch_title`은 동기 치환이 끝난 뒤 최종 텍스트에서 **첫 URL만** 다시 추출해서 제목 요청한다.
- 텍스트 치환이 발생하면 같은 history row와 clipboard도 함께 갱신해 UI/DB/clipboard 정합성을 유지한다.

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

`LegacyMainWindow`를 상속하고 feature controller를 붙이는 컴포지터 클래스.
**메서드 시그니처는 외부 계약 — 변경 금지.**

#### `smartclipboard_app/legacy_main_src.py` — `LegacyMainWindow` (1,570줄)

핵심 PyQt6 창 호환 소스. public method signature는 유지하고, 초기화/dialog/history/clipboard/table/lifecycle 로직은 feature/helper 모듈로 위임.

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
| `Ctrl+Shift+Z` | 가장 최근 복사 항목 즉시 붙여넣기 |

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
| `theme_style_sections.py` | QSS facade (`features/settings/styles/` 재수출) |
| `ui_init_sections.py` | UI init facade (`features/shell_ui/sections.py` 재수출) |
| `ui_ops.py` | `eventFilter`, 키보드 단축키 |
| `ui_dragdrop_ops.py` | 고정 항목 드래그앤드롭 재정렬 |
| `menu_ops.py` | history menu facade |
| `table_ops.py` | history table/view facade |
| `tray_hotkey_ops.py` | tray/hotkey facade |
| `status_lifecycle_ops.py` | shell lifecycle facade |
| `clipboard_runtime_ops.py` | clipboard runtime facade |

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
- **`clipboard_guard.py`** — `mark_internal_copy()` 및 file URL clipboard 복원 헬퍼 (`restore_file_clipboard`)

---

### 4.4 Manager 레이어

#### `smartclipboard_app/managers/export_import.py` — `ExportImportManager`

| 형식 | 기능 |
|------|------|
| JSON (내보내기) | 메타데이터 포함 (`include_metadata=True`): tags/note/bookmark/collections/use_count |
| JSON (가져오기) | `items` list 검증, 컬렉션 ID remap, metadata 타입/범위 정규화, IMAGE는 `image_data_b64` round-trip, FILE은 `file_paths/file_path/content`를 모두 수용 |
| CSV | 날짜·타입 필터 공통 적용, IMAGE는 플레이스홀더 행으로 기록하고 import 시 skip, FILE은 newline path 목록, pinned/use_count round-trip |
| Markdown | 날짜·타입 필터 공통 적용, IMAGE는 설명용 플레이스홀더만 기록, FILE은 fenced text 경로 목록 |

**JSON 마이그레이션 포맷** — `items` 외에 top-level `collections` 메타데이터(legacy_id/name/icon/color) 포함.
**무결성 정책** — ISO-8601/tz timestamp는 **원본 wall-clock 기준** 앱 표준 시각 문자열로 정규화하고, 완전 불량 timestamp는 import 시각으로 대체한다. remap 실패, 누락, 불량 `collection_id`는 `NULL`로 정리하고, CSV pinned 항목은 기존 pinned 목록 뒤에 import 순서대로 붙인다.

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
2. **LIKE 폴백** — FTS5 미지원 환경 또는 FTS 0건 보완
3. **복합 필터** — query + type + tag + collection_id + bookmark + uncategorized 동시 적용
4. **UI 정렬 규칙** — query가 있을 때는 relevance 순서를 기본 유지하고, 사용자가 헤더 정렬을 명시적으로 바꾼 경우에만 client-side sort override 적용

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
- [x] 손상된 보관함 설정 Reset 복구

### 자동화
- [x] URL 제목 자동 가져오기 (비동기)
- [x] 로컬/사설 URL 차단 기반 제목 가져오기 하드닝
- [x] 전화번호 자동 포맷팅 (`02`/일반 지역번호/`0505`/대표번호)
- [x] 이메일 정규화
- [x] 텍스트 변환 (대소문자/트림)
- [x] 패턴 기반 토스트 알림
- [x] 액션/규칙 생성·수정·삭제·우선순위 이동 UI
- [x] 빈 문자열 허용 `custom_replace` 삭제 치환

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
- [x] FILE 누락 경로 사전 표시(stale preview)

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
- `smartclipboard.spec`는 payload 경로에서 누락되지 않도록 `smartclipboard_app.ui.dialogs.collections`를 hidden import에 포함하고, `legacy_main_payload.manifest.json`을 payload와 함께 데이터 자산으로 포함한다.

## 8.2 2026-04-08 구현 리스크 보강 메모

- `ToastNotification.show_toast()` 호출은 `detail`/`duration`/`toast_type` 키워드 기준으로 정리되었고, URL 제목 처리 중 토스트 실패가 나도 클립보드 시그널 재연결은 보장된다.
- `paste_last_item_slot_impl()`는 pinned 정렬 결과가 아니라 실제 최근 복사 항목(`timestamp DESC`, `id DESC`)을 기준으로 붙여넣는다.
- `table_ops.get_display_items_impl()`의 사용자 정렬은 pinned/unpinned를 분리한 뒤 각 그룹 내부만 정렬해 내림차순에서도 pinned-first를 유지한다.
- `delete_collection()`은 `deleted_history.collection_id`도 함께 `NULL` 처리하고, `restore_item()`은 존재하지 않는 컬렉션 참조를 `NULL`로 복원한다.
- `SecureVaultDialog.copy_item()`은 버튼 생성 시점의 암호문을 신뢰하지 않고 최신 보관 row를 다시 읽는다.
- `ClipboardActionManager.shutdown()`은 종료 시 threadpool 완료를 기다리고, late result는 닫힌 DB에 반영하지 않는다.
- Windows 테스트는 시스템 temp ACL 이슈를 피하려고 repo-local `.tmp-unittest/` 경로를 사용한다.

## 8.3 2026-04-10 FILE Clipboard + import 정합성 메모

- `FILE` 타입이 추가되어 로컬 파일/폴더 복사를 다중 경로 하나의 history row로 저장한다.
- `smartclipboard_core.file_paths`는 local path 정규화, duplicate signature, preview label 생성의 단일 기준점이다.
- `clipboard_runtime_ops.process_clipboard_impl()`는 `image -> local file urls -> text` 순서로 수집하며, Windows 파일 복사 시 `hasUrls()`를 `hasText()`보다 우선한다.
- `history.file_path`는 FILE 첫 경로를 저장하고, `content`는 newline-joined absolute paths를 유지한다.
- paste-last, 선택 붙여넣기, 미니 창 더블클릭은 `restore_file_clipboard()`를 통해 `QMimeData + file URL` 클립보드를 재구성한다.
- 일부 파일만 남아 있으면 남은 경로만 복원하고, 모두 사라졌으면 경고만 표시하고 clipboard/paste는 변경하지 않는다.
- CSV import는 IMAGE 플레이스홀더 row를 건너뛰고 pinned/use_count를 복원하며, JSON import는 `items` list와 metadata 타입/범위를 검증하고 remap 불가 `collection_id`를 `NULL`로 정리한다.
- `SecureVaultManager.unlock()` 실패 시 `fernet/is_unlocked` 상태를 함께 초기화해 잘못된 재시도 후 반쯤 열린 상태가 남지 않도록 한다.

## 8.4 2026-04-11 기능 리뷰 후속 반영 메모

- `fetch_title`은 URL 추출 후 후행 문장부호를 제거하고, 로컬/사설/메타데이터 주소는 요청 전 차단한다.
- 제목 가져오기는 HTML 응답만 제한 크기로 읽으며, 비 HTML 응답은 title fetch 대상으로 취급하지 않는다.
- `format_phone()`은 `02`, 일반 지역번호, `0505`, `15xx/16xx/18xx` 대표번호까지 지원 범위를 확장했다.
- `copy_rules`의 `custom_replace`는 빈 replacement를 허용하여 삭제 치환에 사용할 수 있다.
- `SecureVaultManager`는 `vault_salt`와 `vault_verification`을 함께 저장/검증하고, 손상 상태는 잠금 화면 Reset 경로로 복구한다.
- `FILE` 항목은 복원 시점 경고만이 아니라 목록/상세/미니 창에서 stale/missing 경로 수를 먼저 보여준다.
- JSON 마이그레이션 문구는 히스토리 메타데이터 + 컬렉션 범위만 의미하도록 정리되었고, 스키마 자체는 확장하지 않았다.
- `smartclipboard.spec`는 이번 변경에서 추가 hidden import 없이 현행 상태를 유지해도 충분하다.

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
2. MainWindow launcher는 `smartclipboard_app/features/dialogs/`에 추가하고 `legacy_main_src.py`는 thin wrapper로 유지
3. 새 파일이 `smartclipboard_app.features` 하위라면 `smartclipboard.spec`의 기존 `collect_submodules` 범위로 충분한지 확인
4. payload 재빌드: `python scripts/build_legacy_payload.py ...`

### 8.4 UI 위젯/섹션 추가

- 신규 위젯: `smartclipboard_app/ui/widgets/` 에 작성
- MainWindow 레이아웃 변경: `smartclipboard_app/features/shell_ui/sections.py` 수정 후 shim 계약 확인
- 스타일: `smartclipboard_app/features/settings/styles/` 에 QSS section 추가 후 `style_sections.py` facade 계약 확인

### 8.5 새 설정값 추가

`ClipboardDB`의 `get_setting()` / `set_setting()` 활용:
```python
db.set_setting("my_feature_enabled", "1")
value = db.get_setting("my_feature_enabled", default="0")
```

### 8.6 변경 후 필수 검증

```powershell
# 정적 분석
pyright

# payload 재빌드 + manifest 갱신 (legacy_main_src.py 변경 시 반드시)
python scripts/build_legacy_payload.py --src smartclipboard_app/legacy_main_src.py --out smartclipboard_app/legacy_main_payload.marshal --smoke-import

# 전체 사전검증
python scripts/preflight_local.py --with-pyright
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
| repo-wide pyright | 해결됨 | `pyright` 0 errors 유지 |
| `legacy_main.py` 소스 복원 | 장기 목표 | 현재는 payload+src 하이브리드 |

---

## 11. 검증 및 빌드 절차

### 로컬 사전검증 (권장)

```powershell
python scripts/preflight_local.py --with-pyright
```

내부 동작:
1. payload 재생성 + manifest 갱신
2. payload smoke import 검증
3. `py_compile` (전체 대상 모듈)
4. `unittest discover`

### 단계별 실행

```powershell
# 1. 정적 분석
pyright

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
| `test_core.py` | DB/액션 회귀 |
| `test_ui_dialogs_widgets.py` | 정렬/보관함/핫키 UI 회귀 |
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
- preflight 단계: `python scripts/preflight_local.py --skip-payload-build --strict-optional-deps --with-pyright`
- PyInstaller/EXE startup smoke는 일반 CI가 아니라 수동 workflow `.github/workflows/package-smoke.yml`에서 실행한다.

## 12. 2026-04-12 Stabilization Delta

- `ExportImportManager`는 public `int` return을 유지하면서 `last_import_report` / `last_export_report`에 결과 요약을 남긴다.
- JSON/CSV import는 pre-import backup 생성 후 파일 단위 단일 트랜잭션으로 반영되어 중간 실패 시 전체 rollback 된다.
- 검색은 FTS-first이며 FTS 0건 시 LIKE 보완 검색을 수행하고, `_last_search_fallback`은 실제 FTS 오류일 때만 UI 경고 상태를 나타낸다.
- URL title fetch는 전용 `QThreadPool(maxThreadCount=4)`과 URL dedupe/cache를 사용하며 stale late result는 현재 row URL을 다시 확인한 뒤에만 저장한다.
- `history` schema는 `file_path` 외에 `file_signature` 기반 FILE duplicate lookup을 사용한다.
- Vault clipboard plaintext는 armed in-process state로 추적되어 30초 조건부 clear와 종료 시 즉시 clear를 모두 수행한다.
- `mini_window_enabled` 저장 후 hotkey 재등록 실패 시 그 설정만 rollback 하고 실제 `_last_hotkey_error`를 사용자에게 노출한다.
- `scripts/preflight_local.py`는 기본 로컬 모드에서 optional dependency 누락을 경고로 보여주고, `--strict-optional-deps` 및 CI에서는 실패로 처리한다.

---

## 13. 2026-04-15 구조 분할 델타

- `smartclipboard_app/features/`가 새 도메인 루트다.
  - `settings/`: 테마/QSS/controller, `styles/` section builders
  - `shell_ui/`: 레이아웃 초기화, drag-drop, UI controller
  - `history/`: 메뉴/테이블 표시/interaction/controller
  - `clipboard/`: runtime pipeline/controller
  - `tray_hotkey/`: 시스템 트레이/글로벌 핫키/controller
  - `shell/`: MainWindow bootstrap, 상태바/정리/종료/controller
  - `dialogs/`: MainWindow dialog launcher
  - `import_export/`, `vault/`, `shared/`: manager 분리 구현, helper services, 공통 bundle
- `smartclipboard_app/ui/mainwindow_parts/*.py`는 더 이상 실구현이 아니라 feature 모듈 재수출 shim이다.
- `smartclipboard_app/ui/controllers/*.py`도 feature controller facade로 축소되었다.
- `legacy_main_src.MainWindow`는 feature controller를 조합해 helper 기반 메서드를 위임하면서 공개 시그니처를 유지한다.
- `smartclipboard_core/actions.py`는 facade이고 실제 구현은 `smartclipboard_core/automation/`로 이동했다.
- `smartclipboard_core/db_parts/*.py`는 facade이고, 분리된 구현은 `db_parts/search/`, `automation/`, `catalog/`, `retention/`, `history/` 하위 패키지로 이동했다.
- `scripts/preflight_local.py`와 `scripts/refactor_signal_snapshot.py`는 새 feature/core 하위 패키지를 재귀적으로 포함하도록 갱신되어야 하며, `smartclipboard.spec`도 `smartclipboard_app.features`/`smartclipboard_core.automation` hidden import 수집을 포함한다.

*이 문서는 2026-03-21 기준 v10.6 코드베이스를 기반으로 작성되었고, 2026-06-10 SOLID 구조 분할, 문서/spec/ignore 정합성, payload sync 반영 상태까지 갱신했습니다.*

## 14. 2026-04-16 기능 후속 정합성 메모

- `process_actions_impl()`는 텍스트 치환 액션 결과를 누적 적용한 뒤 같은 history row와 clipboard를 함께 갱신한다.
- JSON import가 컬렉션을 생성하면 `refresh_collection_filter_options()`를 먼저 호출해 상단 컬렉션 필터가 즉시 최신 상태를 반영한다.
- `get_display_items_impl()`는 query가 있을 때 DB/FTS relevance 순서를 유지하고, `_search_sort_override`가 켜진 경우에만 client-side sort를 적용한다.
- `load_data_impl()`는 검색 0건/빈 히스토리 경로에서도 `update_status_bar(0)`을 호출해 stale 상태 표시를 방지한다.
- 이번 후속 수정은 packaging scope를 바꾸지 않으므로 `smartclipboard.spec`의 hidden imports/datas 목록은 그대로 유지한다.

## 15. 2026-04-27 기능 구현 리뷰 반영

- 클립보드 내부 복사 race 방지를 위해 기존 debounce timer를 먼저 정리한다.
- DB 복원은 read-only SQLite integrity/schema 검증, `pre_restore_*` 백업, 임시 파일 + atomic replace를 사용한다.
- FTS 최초 생성과 빈 FTS table 상태에서 기존 `history` row를 backfill하고, FTS 결과가 실제로 있을 때만 `_last_search_used_fts`를 켠다.
- DB update/delete 계열은 실제 row 변경 여부를 bool로 반환하고, collection name과 non-empty snippet shortcut에는 unique index를 유지한다.
- JSON import는 top-level `items` list와 metadata 타입/범위를 검증하고, CSV import는 pinned/use_count를 복원한다.
- URL title cache는 256개/24시간 TTL/LRU 정책이며, private-network guard와 redirect 후 final URL 검증을 유지한다.
- payload manifest는 source hash뿐 아니라 payload size/SHA-256을 marshal load 전에 검증한다.
- source/frozen app data directory resolver는 `smartclipboard_core.app_paths`로 통합됐다.
- `max_history` 감소와 자동 cleanup은 고정되지 않은 오래된 항목을 휴지통 없이 영구 삭제하므로 UI/문서 경고를 유지한다.
- `pyright`는 repo-wide 0 errors 기준이며, `smartclipboard.spec` 추가 datas/hidden import 증설은 필요 없다.

## 16. 2026-05-11 기능 안정화 반영

- 프라이버시 모드 활성화 시 예약된 `_clipboard_debounce_timer`를 즉시 취소하고, `process_clipboard_impl()` 진입부에서도 privacy 상태를 재확인한다.
- 텍스트 clipboard는 기본 1MB 초과 시 저장하지 않고 status/toast로 안내하며, 이미지 5MB 제한은 유지한다.
- `deleted_history.url_title` migration을 추가하고 soft delete, 전체 삭제, restore, duplicate restore merge, JSON migration export/import에서 `url_title`을 보존한다.
- 텍스트 치환 action writeback 결과가 기존 history row와 같아지는 경우 duplicate를 남기지 않고 기존 row로 merge한다.
- restore 검증은 full/minimal 모드로 분리하고, UI restore는 full 우선 검증과 legacy/minimal 경고 동의 경로를 사용한다. DB replace 전후에는 target DB의 `-wal`, `-shm` sidecar를 정리한다.
- 시작 시 글로벌 핫키 등록 실패는 status bar/tray/toast 중 가능한 경로로 노출하고, 설정 저장은 `set_setting()` 반환값과 read-back을 확인한다.
- 일반 CI는 `scripts/preflight_local.py --skip-payload-build --strict-optional-deps --with-pyright`를 실행하고, PyInstaller/EXE smoke는 수동 `package-smoke` workflow로 분리한다.
- `.gitignore`는 `.db`, `.sqlite`, `.sqlite3` 계열 user DB와 journal/WAL/SHM sidecar, 로그, build/dist, repo-local `.tmp-unittest/`를 제외한다.

## 17. 2026-06-10 SOLID 구조 분할 반영

- `legacy_main_src.MainWindow.__init__`의 초기화 orchestration은 `smartclipboard_app/features/shell/window_bootstrap.py`로 이동했고, constructor 공개 시그니처는 유지한다.
- MainWindow dialog launcher는 `smartclipboard_app/features/dialogs/`, 태그/컬렉션 필터와 헤더 정렬 interaction은 `smartclipboard_app/features/history/interactions.py`에 둔다.
- QSS builder는 `smartclipboard_app/features/settings/styles/`로 분리하고, `features/settings/style_sections.py`는 compatibility facade로 유지한다.
- `ExportImportManager` public API는 유지하며 timestamp/date filter/file path/image/metadata helper는 `smartclipboard_app/features/import_export/services.py`로 이동했다.
- `smartclipboard_core/db_parts/history_ops.py`는 facade이고 실제 history 구현은 `db_parts/history/write.py`, `queries.py`, `metadata.py`, `deletion.py`, `maintenance.py`로 분리했다.
- `scripts/refactor_signal_snapshot.py`는 `features/shell/window_bootstrap.py`를 함께 스캔해 constructor signal connect 이동 후에도 스냅샷 순서를 유지한다.
- `smartclipboard.spec`는 기존 `collect_submodules("smartclipboard_app.features")`와 `collect_submodules("smartclipboard_core.db_parts")`로 새 하위 모듈을 포함하므로 hidden import/datas 추가가 필요 없다.
- `.gitignore`는 `.codegraph/` 로컬 인덱스를 제외한다. `.codegraph/`는 분석 캐시이며 릴리스/런타임 자산이 아니다.

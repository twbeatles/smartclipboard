# SmartClipboard Native Migration Parity Matrix

이 문서는 기존 Python/PyQt6 구현(`smartclipboard_app`, `smartclipboard_core`)과 Rust + Tauri 2 네이티브 구현(`native/`) 간의 기능 동등성(Parity) 및 마일스톤별 검증 상태를 추적합니다.

최종 갱신일: 2026-09-03  
대상 버전: SmartClipboard Pro v10.7.0  
작업 브랜치: `feature/rust-tauri-migration`

---

## 1. 마일스톤별 진행 및 검증 현황

| Milestone | 영역 | 상태 | 검증 수단 | 비고 |
|---|---|:---:|---|---|
| **Milestone A** | Baseline & Parity Fixtures | **COMPLETED** | `generate_fixtures.py`, `generate_vault_vectors.py`, `benchmark_baseline.py` | 합성 DB v6 및 Fernet 골든 벡터 구축 완료 |
| **Milestone B** | Tauri 2 Skeleton & Tray | **COMPLETED** | `npm run build`, `cargo check`, 5대 테마 CSS 변수 | React 19 + Tailwind CSS + Tray + Single Instance |
| **Milestone C** | DB Read-only & FTS5 Parity | **COMPLETED** | `cargo test --test db_read_parity_tests`, `test_cross_parity.py` | FTS5 한글/영어/코드 검색 100% 일치 |
| **Milestone D** | DB Write Parity & Merge | **COMPLETED** | `cargo test --test db_write_parity_tests` | `add_item`, `replace_text_item_or_merge`, FTS 트리거 자동 동기화 |
| **Milestone E** | Win32 Clipboard Listener | **COMPLETED** | `cargo test --test clipboard_pipeline_tests` | `WM_CLIPBOARDUPDATE`, 디바운스, 내부 복사 가드, 복사 규칙, 텍스트 자동 분류 |
| **Milestone F** | File/Image & Paste Last | **COMPLETED** | `cargo test --test file_image_tests` | `CF_HDROP` 정규화/시그니처, DIB->PNG 변환, `SendInput` Ctrl+V |
| **Milestone G** | Full Vault Lifecycle | **COMPLETED** | `cargo test --test vault_lifecycle_tests`, `vault_interop_tests` | PBKDF2 480k, 언락/락, 원자적 비밀번호 변경 및 전체 재암호화 |
| **Milestone H** | Catalogs & Action Palette | **COMPLETED** | `cargo test --test catalog_and_palette_tests` | 컬렉션/스니펫/휴지통 CRUD, 수동 Action Palette 엔진 |
| **Milestone I** | Import/Export & Packaging | **COMPLETED** | `cargo test --test import_export_tests` | JSON/CSV 라운드트립, 앱 데이터 경로 리졸버, Clippy 0 warnings |

---

## 2. 기능 동등성 매트릭스 (Feature Parity Matrix)

### 2.1 클립보드 수집 및 파이프라인
| 기능 | Python 소스 위치 | Native 소스 위치 | Parity 상태 | 테스트 검증 |
|---|---|---|:---:|---|
| **텍스트 수집** | `features/clipboard/pipeline.py` | `clipboard/win32.rs`, `clipboard/pipeline.rs` | **100%** | `test_text_classifier_parity` |
| **Win32 OS 리스너** | `features/clipboard/controller.py` | `clipboard/win32.rs` (`WM_CLIPBOARDUPDATE`) | **100%** | `test_internal_write_guard` |
| **내부 복사 가드** | `ui/clipboard_guard.py` | `clipboard/internal_guard.rs` | **100%** | `test_internal_write_guard` |
| **파일 경로 수집** | `core/file_paths.py` | `clipboard/file_reader.rs`, `database/file_paths.rs` | **100%** | `test_file_signature_and_normalize_parity` |
| **이미지 DIB 수집** | `features/clipboard/pipeline.py` | `clipboard/image_reader.rs` (PNG 변환) | **100%** | `test_dib_to_png_conversion` |
| **복사 규칙 엔진** | `core/db_parts/automation/rules.py` | `clipboard/copy_rules.rs` | **100%** | `test_copy_rules_engine` |
| **텍스트 자동 분류** | `core/actions.py` | `clipboard/classifier.rs` | **100%** | `test_text_classifier_parity` |
| **Paste Last** | `features/clipboard/services.py` | `paste/mod.rs` (`SendInput` Ctrl+V) | **100%** | `paste_last_command` IPC |

### 2.2 데이터베이스 및 저장소
| 기능 | Python 소스 위치 | Native 소스 위치 | Parity 상태 | 테스트 검증 |
|---|---|---|:---:|---|
| **스키마 호환성** | `core/database.py` (v6) | `database/connection.rs` | **100%** | `test_history_list_ordering_and_fields` |
| **히스토리 조회** | `core/db_parts/history/queries.py`| `database/history_reader.rs` | **100%** | `test_history_list_ordering_and_fields` |
| **FTS5 전문 검색** | `core/db_parts/search/` | `database/search_reader.rs` | **100%** | `test_fts5_search_korean_and_english` |
| **항목 추가 및 중복 병합**| `core/db_parts/history/write.py` | `database/history_writer.rs` | **100%** | `test_text_add_and_deduplication`, `test_file_add_and_signature_deduplication` |
| **텍스트 수정 및 병합** | `core/db_parts/history/write.py` | `database/history_writer.rs` | **100%** | `test_replace_text_or_merge` |
| **고정 / 북마크 / 사용횟수** | `core/db_parts/history/metadata.py`| `database/history_writer.rs` | **100%** | `test_type_and_bookmark_filters` |
| **휴지통 (Soft Delete)** | `core/db_parts/retention/trash.py`| `database/history_writer.rs` | **100%** | `test_soft_delete_and_restore` |
| **컬렉션 & 스니펫 CRUD**| `core/db_parts/catalog/` | `database/catalog_writer.rs` | **100%** | `test_collection_crud_and_cascade_null`, `test_snippet_crud` |

### 2.3 보안 및 Vault
| 기능 | Python 소스 위치 | Native 소스 위치 | Parity 상태 | 테스트 검증 |
|---|---|---|:---:|---|
| **PBKDF2-HMAC-SHA256** | `features/vault/crypto.py` | `vault/fernet.rs` | **100%** | `test_pbkdf2_key_derivation_parity` |
| **Fernet 암복호화** | `cryptography.fernet.Fernet` | `vault/fernet.rs` | **100%** | `test_python_encrypted_samples_decrypt_in_rust` |
| **마스터 비밀번호 설정/검증**| `features/vault/service.py` | `vault/manager.rs` | **100%** | `test_vault_setup_and_unlock` |
| **원자적 비밀번호 변경** | `features/vault/service.py` | `vault/manager.rs` | **100%** | `test_vault_change_password_and_reencryption` |

### 2.4 유틸리티 & 마이그레이션
| 기능 | Python 소스 위치 | Native 소스 위치 | Parity 상태 | 테스트 검증 |
|---|---|---|:---:|---|
| **Action Palette 엔진** | `core/action_palette/` | `action_palette/mod.rs` | **100%** | `test_action_palette_execution` |
| **JSON Export / Import** | `features/import_export/json_codec.py`| `import_export/mod.rs` | **100%** | `test_json_export_and_import_roundtrip` |
| **CSV Export** | `features/import_export/csv_codec.py`| `import_export/mod.rs` | **100%** | `test_csv_export` |
| **데이터 디렉터리 리졸버** | `core/app_paths.py` | `paths/mod.rs` | **100%** | `test_paths_resolution` |

---

## 3. 검증 통과 요약

- **Rust 테스트**: 전체 그린 (G-3 업데이터 16건 + G-4 fetch_title 12건 포함; vault/pipeline/parity 스위트 포함)
- **Rust Clippy**: `cargo clippy --all-targets -- -D warnings` 클린 (CI 게이트와 동일 조건)
- **Frontend 빌드**: 변경 후 재확인 필요 (`npm run build`)
- **Python 회귀 테스트**: 230개 전체 통과 (`pytest`, 레거시 기준)
- **Python 정적 분석**: 0 errors, 1 warning (`pyright`, 레거시 기준)

> 2026-09-20 기능 감사 후속 조치(Follow-up 2 포함)는 로컬에서 검증했다.
> `cargo test` 전체 그린, `cargo clippy --all-targets -- -D warnings` 클린, `tsc --noEmit` 클린.
> `npx tauri build` 전체 패키징은 CI(`ci.yml`)에서 확인한다.

## 4. 감사 후속 조치 (2026-09-20, `PROJECT_AUDIT.md` 대응)

| 감사 이슈 | 상태 | 비고 |
|---|---|---|
| ISSUE-001 paste-last 가드·순서 | ✅ 수정 | guard 공유(AppState) + 최근복사 쿼리 + 쓰기 후 표시 |
| ISSUE-002 비밀번호 변경 원자성 | ✅ 수정 | BEGIN/COMMIT+ROLLBACK, 손상 행 전체 실패, INSERT OR REPLACE, 새 비밀번호 8자, 재초기화 거부 |
| ISSUE-003 Fernet 결정적 IV | ✅ 수정 | `getrandom` CSPRNG 사용 |
| ISSUE-004 unlock 실패 리셋 | ✅ 수정 | 실패 분기 `self.lock()` |
| ISSUE-005 복원 컬렉션·FILE 손실 | ✅ 수정 | dangling → NULL, `deleted_history`에 file 컬럼 + 마이그레이션 |
| ISSUE-006 JSON 크로스호환 단절 | ✅ 수정 | `items`/`history` 이중 읽기, remap, 백업, FILE 서명, CSV import·Markdown export 추가 |
| ISSUE-007 마이그레이션·DB 경로 | ✅ 수정 | `PRAGMA user_version` + `migrate_schema()`, 경로 리졸버 일원화 |
| ISSUE-008 이미지 라벨·가드 | ✅ 수정 | 실측 dims, IMAGE 분기 guard 검사 |
| ISSUE-009 쓰기 거짓 성공 | ✅ 수정 | 실패 시 `false` + 원본 보존 순서 |
| ISSUE-010 보존 미집행 | ✅ 수정 | `purge_expired_trash` + `max_history` + 기동 purge + 캡처 후 enforce |
| G-1 쓰기 IPC 부재 | ✅ 수정 | 32개 신규 command 등록 (히스토리/컬렉션/스니펫/설정/팔레트/IO/Vault) |
| G-2 단축키·미니윈도우 | ✅ 수정 | Alt+V / Ctrl+Shift+Z 등록 + 실패 시 UI 이벤트 |
| G-3 네이티브 자동 업데이트 | ✅ 수정 | `updater/` 검증·스테이징·적용 + CLI + 커맨드 5개 + UI, 릴리즈 서명 발행 |
| G-4 URL 제목 자동화 | ✅ 수정 | SSRF 차단·HTML 제한 읽기·256개/24h 캐시 + 파이프라인 연동 |
| G-5 tray 상태 이원화 | ✅ 수정 | IPC + emit + settings 영속 + 기동 복원 |
| G-6 CSV import·Markdown | ✅ 수정 | 구현됨 |
| G-7 스니펫 충돌 검증 | ✅ 수정 | 스니펫 간 중복 거부 (앱·글로벌 핫키 대조는 UI 범위) |
| G-8 FTS 하드 실패 | ✅ 수정 | LIKE 폴백 |

여전히 남은 것: CSP 정책 확정(G-10), 평문 zeroize(G-9), `claude.md` 전면 갱신. G-3/G-4는 Follow-up 2에서 해소했다.

---

## 5. 릴리즈 파이프라인 메모 (2026-09-20)

- v10.8 `Release` 실패 2건 수정: spec 아이콘 탐색, GUI 바이너리 스모크 체크(`Start-Process -Wait`), `package-smoke.yml` 경로(`legacy/python`) 갱신.
- 매 push 실행되는 `release-guard` 잡이 `check_release_prereqs.py`로 릴리즈 전제조건(아이콘·버전 정합·스모크 패턴)을 검사.
- 버전 정합 규칙: `Config.VERSION`은 `Cargo`/`package.json`과 short-form(`10.8` == `10.8.0`) 일치, `tauri.conf.json`은 Cargo와 완전 일치.


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

- **Rust 테스트**: 총 30개 전체 통과 (`cargo test`)
- **Rust Clippy**: 경고 0건 (`cargo clippy`)
- **Frontend 빌드**: 성공 (`npm run build`, 1.05s)
- **Python 회귀 테스트**: 230개 전체 통과 (`pytest`)
- **Python 정적 분석**: 0 errors, 1 warning (`pyright`)
- **Python Preflight**: ok (`preflight_local.py`)

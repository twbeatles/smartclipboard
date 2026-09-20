# Project Audit — SmartClipboard Pro (Native Edition)

> **Follow-up (2026-09-20):** 본 문서가 제안한 모든 항목에 대한 개선을 적용했다.
> High-Risk 10건 수정, Gap 7건 해소(G-3/G-4 제외), 회귀 테스트 17건 추가, IPC 32개·전역 단축키·프론트 연결, `AGENTS.md` 신설.
> 상세는 `docs/NATIVE_PARITY_MATRIX.md` §4를 참조한다.
>
> **Follow-up 2 (2026-09-20):** 남은 G-3/G-4도 구현·검증했다. G-4 URL 제목 자동화(`clipboard/fetch_title.rs`, 파이프라인 연동, 12건 테스트),
> G-3 서명 업데이트(`updater/` 검증·스테이징·적용 + `--smoke`/`--apply-update` CLI + Tauri 커맨드 5개 + 사이드바 UI, 16건 테스트).
> 로컬에서 `cargo test` 전체 그린, `cargo clippy --all-targets -- -D warnings` 클린, `tsc --noEmit` 클린을 확인했다.
> 단, 서명된 새 버전의 실제 cutting(릴리즈 태그·서명)은 CI 시크릿이 필요하므로 로컬이 아닌 릴리즈 워크플로에서 수행한다.

- 감사 일시: 2026-09-20 (UTC)
- 감사 범위: 기능 구현·런타임 안정성 (스타일 제외)
- 감사 대상: `src/` (React 19) + `src-tauri/src/` (Rust + Tauri 2) — 현행 네이티브 에디션. `legacy/python/`은 스펙 대조용 참조로만 사용
- 코드 수정 없음. 감사 리포트만 작성

---

## 1. Executive Summary

프로젝트는 Python/PyQt6 구현을 Rust + Tauri 2로 이전 중인 상태다. 백엔드 로직(DB 읽기/쓰기, Vault, Import/Export, Action Palette)은 Rust로 이식되어 있고 단위 테스트도 갖춰져 있으나, **Tauri IPC·UI에 연결된 것은 읽기 명령 + 클립보드 캡처뿐**이다. 즉 현재 빌드되는 앱은 "캡처 + 읽기 전용 뷰어"이며, 쓰기·Vault·가져오기/내보내기·단축키·자동 업데이트는 코드로만 존재한다.

- 전체 위험도: **Needs Work (상당 부분 손봐야 함)**
- 데이터 손상/유실 가능성: **있다.** 다만 대부분은 아직 IPC에 노출되지 않은 백엔드 함수에 국한된다. Production 도달 가능한 경로(캡처 파이프라인, DB open)에도 중간 수준의 문제 2건이 있다.
- 가장 먼저 수정해야 할 영역: (1) IPC 노출 범위 결정(읽기 전용 유지 vs 쓰기 연결 — 현재 어중간), (2) Vault 변경·해제 경로의 트랜잭션/상태 버그, (3) Python↔Rust JSON 호환 단절과 마이그레이션 부재.

가장 중요한 문제 5개:

1. `paste_last`가 파이프라인과 다른 `InternalWriteGuard` 인스턴스를 만들어 내부복사 가드가 영원히 동작하지 않고, 순서도 pinned-first라 "가장 최근"이 아님 ([ISSUE-001])
2. `change_master_password`가 수동 `BEGIN/COMMIT` + `ROLLBACK` 없음 + 손상 행 silent skip + `.unwrap()` 패닉 + `UPDATE settings`로 키 분실 시 보관함 전체 잠금 ([ISSUE-002])
3. Rust Fernet `encrypt`의 IV가 `SHA256(타임스탬프‖평문)` 결정값 — CSPRNG 미사용, 동일 초·동일 평문은 동일 토큰 (Python `cryptography`는 `os.urandom`) ([ISSUE-003])
4. `unlock()` 실패가 `fernet/is_unlocked`를 초기화하지 않아 이전 잠금해제 상태가 그대로 남음 — CLAUDE.md 계약 위반 ([ISSUE-004])
5. Rust JSON 포맷(`history`)이 Python 포맷(`items`)과 달라 크로스 임포트 불가 + 컬렉션 remap·백업·파일 시그니처 복원 누락 ([ISSUE-006])

---

## 2. Project Understanding

### 목적

Windows용 클립보드 매니저. 복사한 텍스트/이미지/파일을 저장·분류·검색하고, 태그·컬렉션·스니펫·보안 보관함·자동 액션을 제공한다. Python/PyQt6 클래식 에디션을 Rust + Tauri 2 네이티브 에디션으로 이전 중이며, SQLite WAL DB 바이너리 호환을 목표로 한다.

### Entrypoint·핵심 모듈·데이터 저장·의존성

| 구분 | 내용 |
|---|---|
| 진입점 (네이티브) | [main.rs](C:\twbeatles-repos\smartclipboard\src-tauri\src\main.rs) → [lib.rs `run()`](C:\twbeatles-repos\smartclipboard\src-tauri\src\lib.rs) (tray + DB open + clipboard listener + IPC 등록) |
| 진입점 (프론트) | [main.tsx](C:\twbeatles-repos\smartclipboard\src\main.tsx) → [App.tsx](C:\twbeatles-repos\smartclipboard\src\App.tsx) / [MiniApp.tsx](C:\twbeatles-repos\smartclipboard\src\MiniApp.tsx) |
| 캡처 | [clipboard/win32.rs](C:\twbeatles-repos\smartclipboard\src-tauri\src\clipboard\win32.rs) (`WM_CLIPBOARDUPDATE` 리스너) → [clipboard/pipeline.rs](C:\twbeatles-repos\smartclipboard\src-tauri\src\clipboard\pipeline.rs) (FILE → IMAGE → TEXT 우선순위) |
| 저장 | [database/](C:\twbeatles-repos\smartclipboard\src-tauri\src\database) (`connection.rs` 단일 `Mutex<Connection>`, `history_writer.rs`, `history_reader.rs`, `search_reader.rs` FTS5, `catalog_*.rs`, `file_paths.rs`) |
| 보안 보관함 | [vault/fernet.rs](C:\twbeatles-repos\smartclipboard\src-tauri\src\vault\fernet.rs) (PBKDF2 480k + Fernet 직접 구현), [vault/manager.rs](C:\twbeatles-repos\smartclipboard\src-tauri\src\vault\manager.rs) |
| 쓰기/붙여넣기 | [paste/mod.rs](C:\twbeatles-repos\smartclipboard\src-tauri\src\paste\mod.rs) (`SendInput` Ctrl+V), [import_export/mod.rs](C:\twbeatles-repos\smartclipboard\src-tauri\src\import_export\mod.rs), [action_palette/mod.rs](C:\twbeatles-repos\smartclipboard\src-tauri\src\action_palette\mod.rs) |
| IPC (전부) | `history_list/detail/search`, `collections_list`, `snippets_list`, `settings_get_all`, `trash_list`, `vault_status`, `hide_mini_window`, `paste_last_command` — 쓰기 명령 0건 ([commands/mod.rs](C:\twbeatles-repos\smartclipboard\src-tauri\src\commands\mod.rs)) |
| DB | SQLite WAL, FTS5 `history_fts` + 3 트리거, 테이블 `history/deleted_history/collections/snippets/copy_rules/secure_vault/settings` |
| 외부 의존 | Tauri 2, rusqlite(bundled), image(png), regex, sha2/hmac/pbkdf2/aes/cbc/base64/getrandom/zeroize, React 19, `@tauri-apps/api` |

### 핵심 실행 흐름

`WM_CLIPBOARDUPDATE → window_proc CALLBACK → pipeline.process_event (100ms sleep) → privacy/pause 확인 → FILE(CF_HDROP) → IMAGE(CF_DIB→PNG) → TEXT(1MiB 제한·가드·copy_rules·classify) → db.add_item (중복 시 row 갱신) → history_changed emit → React 재조회`

읽기 흐름: `React tauriInvoke → commands → db.list_history/search_items → HistoryItem[]`

쓰기 흐름: **없음.** 백엔드 함수(`add_collection`, `soft_delete`, `add_secret`, `execute_action`, `import_from_json` 등)는 IPC에 등록되지 않아 프로덕션에서 호출자가 없다. 프론트도 "읽기 전용 호환 모드 (M-C)" 배지를 표시한다.

---

## 3. Audit Coverage & Limitations

### 실제 확인한 모듈 (전수 열람)

`lib.rs`, `app_state.rs`, `commands/mod.rs`, `errors.rs`, `clipboard/{pipeline,win32,internal_guard,image_reader,file_reader,copy_rules,classifier}.rs`, `database/{connection,history_writer,history_reader,search_reader,catalog_writer,file_paths,models}.rs`, `vault/{fernet,manager}.rs`, `import_export/mod.rs`, `paste/mod.rs`, `action_palette/mod.rs`, `paths/mod.rs`, `App.tsx`, `MiniApp.tsx`(호출부), `tauri.conf.json`, `Cargo.toml`, `docs/NATIVE_PARITY_MATRIX.md`, `README.md`, `claude.md`, `.gitignore`, 레거시 대조용 `json_codec.py/manager.py`, `db_parts/search/schema.py`.

### CodeGraph 호출 관계 분석

- CodeGraph CLI 사용: `codegraph status`, `explore "clipboard pipeline entrypoint"`, `explore "rust tauri Database add_item history_writer"` — 3회 실행됨.
- 결과: 인덱스가 **레거시 Python 전용**(195 files, python 191, rust 0)으로 stale. 네이티브 호출관계(caller/callee/impact)는 CodeGraph로 얻지 못하고 ripgrep + 직접 열람으로 대체했다. 아래 영향 범위는 직접 확인한 호출자 기준이다.

### 실행한 테스트

- `cargo test` (일반 + `--offline`): **미실행.** 의존성 미캐시 + 샌드박스 네트워크 차단(TLS `SEC_E_NO_CREDENTIALS`)으로 크레이트 다운로드 실패. 문 claims("Rust 30건 통과")를 검증하지 못했다.
- `npm run typecheck`: **미실행.** 샌드박스 CWD 문제(`EISDIR ... lstat 'C:'`, UNC 경로)로 node 기동 실패. 코드 문제가 아니다.
- `git status`: **미실행.** `dubious ownership`으로 차단. git 설정을 건드리지 않았다.
- 루트 잔재 DB 읽기(`.tmp-unittest` 스크래치 스크립트, 실행 후 삭제): `history_count = 0`, 테이블은 v6 풀셋. 실사용자 데이터 아님을 확인했고 스크래치 파일은 제거했다.
- 실행했다고 쓰지 않는다: 위 3종은 모두 미실행이며, 본문의 모든 이슈 근거는 코드 열람 + 검색 결과뿐이다.

### 확인하지 못한 환경/외부 서비스

실제 Windows 클립보드 이벤트, Tauri 윈도우 실행, Python↔Rust 실DB 공유 구동, 릴리즈 서명/업데이트 서버, Linux/macOS(네이티브는 `std::os::windows` 사용으로 Windows 전용 설계 — 컴파일 자체가 Windows-only).

---

## 4. High-Risk Issues

### [ISSUE-001] paste-last의 가드·순서 3중 결함

- **위치:** [commands/mod.rs:57-60](C:\twbeatles-repos\smartclipboard\src-tauri\src\commands\mod.rs), [paste/mod.rs:69-86](C:\twbeatles-repos\smartclipboard\src-tauri\src\paste\mod.rs)
- **우선순위:** High
- **신뢰도:** Confirmed
- **문제:** (a) `paste_last_command`가 매 호출마다 `InternalWriteGuard::new()`를 생성한다. 리스너 파이프라인이 가진 guard와 다른 인스턴스이므로 `mark_internal` 표시를 파이프라인이 절대 인식하지 못한다. (b) `mark_internal(seq + 1)`로 다음 시퀀스 번호를 추측한다. (c) `list_history(1)`은 `pinned DESC` 정렬이라 고정 항목이 있으면 "가장 최근 복사"가 아니라 고정 항목을 붙여넣는다 (CLAUDE.md 계약: `timestamp DESC, id DESC`, pinned 무관).
- **발생 조건:** `paste_last_command` 호출 시 항상. 성공 시 클립보드에 쓴 내용이 내부복사로 인식되지 않아 캡처 파이프라인이 중복 row로 재수집한다.
- **영향:** 붙여넣기 대상 오류 +511 히스토리 오염(중복/갱신 row).
- **근거:** `commands/mod.rs:58`의 fresh guard, `paste/mod.rs:74`의 `seq + 1`, `history_reader.rs:17`의 `ORDER BY pinned DESC, ...`.
- **반증 확인:** 파이프라인 측 `is_internal`은 정상 구현이나 인스턴스가 달라 도달 불가. `GetClipboardSequenceNumber`가 단조 증가한다는 가정도 코드에 없고 추측값이다. 전역 단축키 미등록(§5 G-2)으로 현재 UI에서 호출자는 없으나, IPC에 노출된 순간 발현한다.
- **호출/영향 범위:** caller 없음(미사용 IPC) → callee `list_history`, `write_clipboard_text`, `simulate_ctrl_v`. 수정 시 `lib.rs`의 guard 공유 구조와 함께 봐야 한다.
- **권장 수정 방향:** 파이프라인과 같은 `Arc<InternalWriteGuard>`를 `AppState`에 보관해 공유. 표시 시점은 쓰기 **후** 실제 시퀀스 + 내용 해시로 확정. `paste_last` 조회는 pinned-first가 아닌 `timestamp DESC, id DESC` 전용 쿼리 사용. IMAGE면 텍스트가 아니라 실패가 아니라 이미지 복원/스킵 정책을 명시.
- **필요한 회귀 테스트:** (Unit) 공유 guard에서 mark→is_internal 매칭. (Integration) `paste_last` 후 파이프라인이 해당 이벤트를 스킵함. (Regression) pinned 항목 존재 시에도 가장 최근 timestamp 항목을 선택함.

### [ISSUE-002] 비밀번호 변경 트랜잭션·오류 처리 결함

- **위치:** [vault/manager.rs:150-237](C:\twbeatles-repos\smartclipboard\src-tauri\src\vault\manager.rs) (`change_master_password`)
- **우선순위:** High
- **신뢰도:** Confirmed
- **문제:** (a) `conn.execute("BEGIN TRANSACTION")` 후 수동 `COMMIT`인데 에러 시 `ROLLBACK`이 없다. 중간 `encrypt` 실패 시 커넥션이 트랜잭션에 갇히고(`Mutex<Connection>` 단일 연결이라 이후 모든 DB 호출이 실패), 부분 반영 상태가 남는다. (b) 복호화 실패 행을 `warn!` 후 **조용히 제외**한다 — 해당 비밀은 새 키로 재암호화되지 않아 사실상 분실된다. (c) 기존 salt 디코딩에 `.unwrap()`(167행 인근)이 있어 손상된 salt에서 스레드 패닉. (d) salt/verification 갱신을 `UPDATE ... WHERE key=`로 수행해 키 행이 없으면 0행 갱신·무에러로 지나간다 — 데이터는 새 키, 검증값은 옛 키 상태가 되어 보관함 전체 잠금(lockout). (e) 새 비밀번호 길이 검증이 없다(`set_master_password`의 8자 규칙 미적용).
- **발생 조건:** 손상 행 존재, salt 손상, settings 키 분실, 짧은 새 비밀번호.
- **영향:** 비밀 분실 ~ 보관함 전체 접근 불가. 단일 `Mutex` 연결이라 (a)는 앱 전체 DB 마비로 확산한다.
- **근거:** 코드 직접 확인. Python 계약("원자적 재암호화")과 정면 배치.
- **반증 확인:** `rusqlite` 트랜잭션 헬퍼 미사용을 확인. `UPDATE` 반환 row count를 검사하지 않음을 확인. 현재 `VaultManager`를 생성하는 프로덕션 호출자가 없어(§5 G-1) 도달은 테스트·향후 IPC에 한정 — 그래서 Critical이 아니라 High.
- **호출/영향 범위:** caller는 테스트만. callee `derive_key`, `Fernet::{decrypt,encrypt}`, `db.get_setting/with_conn`.
- **권장 수정 방향:** `conn.transaction()` + RAII 커밋, 실패 시 전체 롤백. 손상 행은 skip이 아니라 전체 실패(원자성) 또는 호출자 선택 옵션. `.unwrap()` 제거. `INSERT OR REPLACE`로 salt/verification 갱신. 새 비밀번호에 set과 동일한 정책 적용.
- **필요한 회귀 테스트:** (Unit) 중간 encrypt 실패 주입 시 전체 롤백 + 기존 키로 전 행 복호화 가능. (Unit) 손상 salt에서 패닉이 아니라 `Err`. (Unit) settings 키 삭제 상태에서 변경 후 unlock→전 행 복호화 성공. (Unit) 8자 미만 새 비밀번호 거부.

### [ISSUE-003] Fernet encrypt의 결정적 IV

- **위치:** [vault/fernet.rs:117-134](C:\twbeatles-repos\smartclipboard\src-tauri\src\vault\fernet.rs) (`encrypt`)
- **우선순위:** High
- **신뢰도:** Confirmed
- **문제:** IV 난수 대신 `SHA256(타임스탬프‖평문)[0..16]`을 사용한다. 같은 초에 같은 평문을 암호화하면 토큰이 완전히 동일하고, IV가 예측 가능하다. `getrandom` 크레이트는 이미 의존성에 있고 salt 생성에 쓰므로 의도된 선택이 아니라 구현 오류로 보인다.
- **발생 조건:** Rust `encrypt`로 암호화하는 모든 행. 동일 비밀을 1초 안에 두 번 저장하면 토큰 동일.
- **영향:** 평문 동일성 노출, 선택 평문 공격 내성 저하. 복호화 호환성 자체는 깨지지 않아 탐지가 늦는다.
- **근거:** 코드 직접 확인. Python `cryptography.Fernet`은 `os.urandom(16)` 사용 — "상호운용" 테스트는 통과해도 보안 속성은 동등하지 않다.
- **반증 확인:** 타임스탬프가 초 단위라 충돌 윈도우가 현실적임을 확인. 현재 Rust `encrypt`의 프로덕션 호출자는 없음(Vault IPC 미노출) — High로 두되 Critical로 올리지 않은 이유.
- **호출/영향 범위:** `manager.rs`의 `set_master_password/add_secret/change_master_password`가 callee. 토큰 포맷 자체는 표준이라 수정 후에도 복호화 호환 유지.
- **권장 수정 방향:** 기본 IV를 `getrandom` 16바이트로 생성. 결정적 IV가 필요한 테스트 벡터는 `iv_opt` 인자로만 주입.
- **필요한 회귀 테스트:** (Unit) 같은 평문 2회 암호화 시 토큰 상이. (Interop) Rust 암호문 Python 복호화 + Python 암호문 Rust 복호화 유지. (Regression) 초 경계 양쪽에서 IV 중복 없음(100회 암호화 후 토큰 집합 크기 = 100).

### [ISSUE-004] unlock 실패 시 잠금 상태 미초기화

- **위치:** [vault/manager.rs:106-148](C:\twbeatles-repos\smartclipboard\src-tauri\src\vault\manager.rs) (`unlock`)
- **우선순위:** High
- **신뢰도:** Confirmed
- **문제:** 비밀번호 불일치(`Ok(false)`) 경로에서 `self.fernet`/`is_unlocked`를 건드리지 않는다. 이전에 잠금해제된 상태에서 틀린 비밀번호로 `unlock`을 호출하면 반환값은 "실패"인데 내부는 여전히 잠금해제 상태로 남는다.
- **발생 조건:** unlock 성공 이력이 있는 세션에서 틀린 비밀번호로 재호출.
- **영향:** 호출자가 `Ok(false)`를 "잠김"으로 믿고 분기하면 보안 판단 오류. CLAUDE.md §3 "unlock() 실패 시 fernet/is_unlocked 반드시 함께 초기화" 계약 위반.
- **근거:** 137–147행 `match ... _ => Ok(false)`에 상태 리셋 없음. `lock()` 메서드는 존재하므로 호출 누락이 확정적.
- **반증 확인:** `is_unlocked()`의 타임아웃 자동잠금과 무관한 경로임을 확인. 프로덕션 호출자 없음(테스트·향후 IPC만) — High 유지.
- **호출/영향 범위:** `VaultManager` 내부 상태. 수정 시 `set_master_password` 성공 경로와 대칭되게.
- **권장 수정 방향:** 실패 분기에 `self.lock()` 호출(또는 `fernet=None` + `is_unlocked=false` 직접 설정).
- **필요한 회귀 테스트:** (Unit) unlock 성공 → 틀린 비밀번호 unlock(`Ok(false)`) → `is_unlocked()==false` + `get_secret` 실패.

### [ISSUE-005] 휴지통 복원 시 컬렉션·FILE 메타데이터 손실

- **위치:** [database/history_writer.rs:311-426](C:\twbeatles-repos\smartclipboard\src-tauri\src\database\history_writer.rs), [database/connection.rs:96-113](C:\twbeatles-repos\smartclipboard\src-tauri\src\database\connection.rs)
- **우선순위:** Medium
- **신뢰도:** Confirmed
- **문제:** (a) `restore_item`이 `collection_id`를 그대로 삽입한다. 원본 컬렉션이 삭제된 경우 존재하지 않는 id가 남아 CLAUDE.md 계약("복원 시 존재하지 않는 컬렉션 참조는 NULL") 위반. 스키마에 FK가 없어 조용히 저장된다. (b) `soft_delete`의 SELECT와 `deleted_history` 스키마에 `file_path/file_signature`가 없어 FILE 항목이 휴지통을 거치면 서명·대표경로가 소실된다. 복원된 FILE row는 이후 동일 파일 재복사 탐지(`file_signature` lookup)에 매칭되지 않아 중복 row가 쌓인다.
- **발생 조건:** 삭제된 컬렉션 소속 항목 복원, FILE 항목의 삭제→복원.
- **영향:** 필터에서 안 보이는 고아 참조, FILE 중복 누적.
- **근거:** 코드 직접 확인. `delete_collection`은 `deleted_history`까지 NULL 처리하는데(우수) 정작 복원 쪽이 무결성을 깬다.
- **반증 확인:** FK·트리거 없음(`connection.rs` 스키마에 외래키 정의 없음). 프로덕션 호출자 없음(IPC 미노출) — Medium.
- **호출/영향 범위:** callee 없음. `catalog_writer.delete_collection`과 대칭 수정 필요.
- **권장 수정 방향:** 복원 시 `collections` 존재 확인 후 없으면 NULL. `deleted_history`에 `file_path/file_signature` 컬럼 추가 + 삭제/복원 SELECT·INSERT에 포함(기존 DB에는 마이그레이션 필요 — ISSUE-007과 연계).
- **필요한 회귀 테스트:** (Unit) 컬렉션 삭제 후 소속 항목 복원 → `collection_id IS NULL`. (Unit) FILE 삭제→복원 후 `file_signature` 보존 + 동일 파일 재추가 시 기존 row 갱신(`updated=true`).

### [ISSUE-006] Python↔Rust 마이그레이션 포맷 단절

- **위치:** [import_export/mod.rs:9-137](C:\twbeatles-repos\smartclipboard\src-tauri\src\import_export\mod.rs), 대조 [legacy/python/.../json_codec.py:184-255](C:\twbeatles-repos\smartclipboard\legacy\python\smartclipboard_app\features\import_export\json_codec.py), [manager.py:138-140](C:\twbeatles-repos\smartclipboard\legacy\python\smartclipboard_app\features\import_export\manager.py)
- **우선순위:** Medium
- **신뢰도:** Confirmed
- **문제:** Python은 최상위 `items` + `collections` 메타를 쓰고 Rust는 `history` + `collections` + `snippets`를 쓴다. 양방향 크로스 임포트가 전부 실패한다(Rust→Python: `items` 없어 `ValueError`; Python→Rust: `history` 필드 없어 serde 에러). 추가로 Rust import는 (a) 컬렉션 ID remap 없이 `INSERT OR IGNORE`(id 충돌 시 다른 컬렉션에 귀속), (b) `file_path/file_signature` 미복원(ISSUE-005와 결합해 FILE 중복), (c) pre-import 백업 없음(Python 계약 위반), (d) 깨진 base64 이미지 `.ok()`로 조용히 버림, (e) 수동 BEGIN/COMMIT + ROLLBACK 없음, (f) CSV import·Markdown export 미구현.
- **발생 조건:** 에디션 간 데이터 이동 시도 시 항상.
- **영향:** "100% DB 바이너리 호환" 주장과 달리 파일 기반 마이그레이션 경로가 단절. import 오귀속은 조용한 데이터 오염.
- **근거:** 양쪽 코드 직접 대조. `import_from_json`의 `params![col.id ...]` + `INSERT OR IGNORE` 확인.
- **반증 확인:** 테스트는 Rust 내부 roundtrip만 검증하는 것으로 보이며 크로스 포맷 테스트는 없다. 프로덕션 호출자 없음 — Medium.
- **호출/영향 범위:** caller 테스트만. Python `manager.py`의 검증 규칙(remap/정규화)과 1:1 매칭 필요.
- **권장 수정 방향:** 한쪽 포맷으로 통일(둘 다 읽기 지원이 현실적) + remap + 백업 + file_sig 복원 + `conn.transaction()` + base64 실패는 에러. CSV import/Markdown은 지원 선언에서 제외하거나 구현.
- **필요한 회귀 테스트:** (Integration) Python 내보내기 샘플 → Rust import 성공 + 컬렉션 remap + FILE 서명 보존. (Integration) Rust 내보내기 → Python import 성공. (Unit) id 충돌 컬렉션 import 시 오귀속 없음. (Unit) import 실패 시 원본 DB 무변경(백업·롤백).

### [ISSUE-007] 스키마 마이그레이션 부재 + CWD 상대 DB 경로

- **위치:** [database/connection.rs:48-151](C:\twbeatles-repos\smartclipboard\src-tauri\src\database\connection.rs) (`init_schema`), [lib.rs:21-44](C:\twbeatles-repos\smartclipboard\src-tauri\src\lib.rs) (`resolve_db_path`)
- **우선순위:** Medium
- **신뢰도:** Confirmed
- **문제:** (a) `init_schema`는 `CREATE ... IF NOT EXISTS`만 있고 `ALTER TABLE`이 없다. 구버전 DB(컬럼 부족)를 열면 쿼리가 `no such column`으로 실패한다. 레거시 Python은 `schema.py`에 10개 이상의 `ALTER TABLE` 마이그레이션을 둔다. FTS 트리거도 구 DB에는 없을 수 있다. (b) `resolve_db_path`가 CWD 상대 dev fixture·adjacent 경로를 사용하고, `open_read_write`가 파일이 없으면 **생성**하므로 실행 위치에 따라 stray DB가 생긴다. 루트의 `clipboard_history_v6.db`(0행, WAL 123KB)가 그 잔재로 보인다. (c) `open_read_write` 실패 시 `open_read_only` 폴백은 파일 생성 이후라 사실상 도달 불가한 분기(읽기전용 의도와 달리 항상 쓰기 모드로 생성).
- **발생 조건:** 구버전 DB로 첫 실행, 레포 루트 등 임의 CWD에서 실행.
- **영향:** 구 DB 사용자의 앱 기동 실패·검색 실패, 레포 오염, 사용자 데이터 위치 불명확.
- **근거:** Rust 전체에서 `ALTER TABLE` 0건(검색 확인) vs 레거시 10건+. 루트 DB 실존 + 0행 확인(읽기전용 조회, 스크래치 삭제済).
- **반증 확인:** `PRAGMA user_version` 같은 버전 관리도 없음. 단, v6 풀스키마 DB에는 문제없음.
- **호출/영향 범위:** 앱 기동 경로(`run()`). `paths/mod.rs`의 `resolve_db_path`와 중복 정의(두 개의 리졸버가 서로 다른 우선순위)도 함께 정리 필요.
- **권장 수정 방향:** `PRAGMA user_version` 기반 마이그레이션(레거시 `schema.py` 규칙 이식). DB 경로는 `paths::resolve_db_path`로 일원화하고 CWD adjacent를 최후순위로. 첫 실행 시 스키마 검증 로그.
- **필요한 회귀 테스트:** (Integration) 컬럼 부족 구 DB 열기 → 자동 마이그레이션 후 읽기/쓰기/FTS 정상. (Unit) 존재하지 않는 CWD에서 stray 파일 미생성.

### [ISSUE-008] 이미지 캡처 경로의 라벨·가드 누락

- **위치:** [clipboard/pipeline.rs:58-66](C:\twbeatles-repos\smartclipboard\src-tauri\src\clipboard\pipeline.rs)
- **우선순위:** Low
- **신뢰도:** Confirmed
- **문제:** (a) 이미지 라벨이 `format!("이미지 [{}x{}]", 0, 0)` 고정이라 목록에 항상 "이미지 [0x0]"으로 표시된다. `dib_to_png`가 dims를 알 수 있는데 전달하지 않는다. (b) TEXT/FILE 분기에는 있는 `write_guard.is_internal` 검사가 IMAGE 분기에 없다.
- **발생 조건:** 이미지 복사 시 항상 (a). (b)는 내부 이미지 쓰기가 현재 존재하지 않아 latent.
- **영향:** (a) cosmetic. (b)将来 이미지 복원 IPC가 생기면 복원 이미지가 중복 row로 재수집(IMAGE는 항상 INSERT).
- **근거:** 코드 직접 확인. Python parity 관점에서도 라벨 규격 미달.
- **반증 확인:** (b)는 현재 도달 불가 — 그래서 Low. IMAGE 5MB 제한(Python 계약)도 Rust에는 없고 DIB 20MB만 있어 큰 이미지가 그대로 PNG 저장되는 점은 테스트로 크기 정책 확정 후 판단.
- **권장 수정 방향:** `dib_to_png`가 dims 반환 → 라벨에 실측 기입. IMAGE 분기에도 guard 검사 추가.
- **필요한 회귀 테스트:** (Unit) DIB fixture 캡처 시 라벨 dims 일치. (Integration) 내부 표시된 이미지 이벤트 스킵.

### [ISSUE-009] 클립보드 쓰기 실패를 성공으로 보고

- **위치:** [clipboard/win32.rs:130-156](C:\twbeatles-repos\smartclipboard\src-tauri\src\clipboard\win32.rs) (`write_clipboard_text`)
- **우선순위:** Medium
- **신뢰도:** Confirmed
- **문제:** `OpenClipboard` 성공 후 `EmptyClipboard()`로 기존 내용을 지우고, `GlobalAlloc` 실패·`GlobalLock` null이어도 `return true`한다. 클립보드는 비워졌는데 호출자는 성공으로 믿는다.
- **발생 조건:** 메모리 압박·클립보드 경합 시의 할당 실패. 드물지만 발생 시 치명적(사용자 클립보드 소실).
- **영향:** 클립보드 데이터 소실 + 후속 `Ctrl+V`가 빈 붙여넣기.
- **근거:** 137–150행 제어흐름 직접 확인.
- **반증 확인:** 재시도 루프(5회)는 `OpenClipboard` 실패에만 있고 할당 실패에는 없음. 현재 호출자는 `paste_last`뿐(미사용 IPC) — Medium으로 유지.
- **권장 수정 방향:** 할당·락 실패 시 `false` 반환. `EmptyClipboard`는 `SetClipboardData` 직전으로 이동(실패 시 원본 보존).
- **필요한 회귀 테스트:** (Unit) 할당 실패 주입 시 `false` + 기존 클립보드 내용 보존. footgun 특성상 단위 테스트는 Win32 API 추상화 후 mock.

### [ISSUE-010] 보존 정책 미집행(휴지통 만료·최대 보관)

- **위치:** `history_writer.rs` (`soft_delete`는 `expires_at` 기록, 읽는 곳 없음 — 검색으로 확인), 파이프라인·writer 전체에 `max_history` 없음
- **우선순위:** Medium
- **신뢰도:** Confirmed
- **문제:** `expires_at`(7일)이 기록만 되고 만료 purge가 어디에도 없다. `max_history`(Python 500 기본) 상당 로직도 네이티브에 없다. 캡처 파이프라인(`add_item`)은 프로덕션 도달 가능 경로라 DB가 무한 증가한다.
- **발생 조건:** 장기 사용 시 항상.
- **영향:** DB肥大·FTS膨胀·UI 로딩 저하. 삭제된ことになっている 데이터가 영구 잔류(보존 정책 위반).
- **근거:** `expires_at|purge|max_history|retention|cleanup` 검색 — Rust에서 만료 읽기·purge·cap 0건.
- **반증 확인:** 단일 `Mutex`라 백그라운드 purge 스레드 추가는 쉽다. 단, Python 계약상 `max_history` 감소 시 영구삭제 경고 UI가 필요 — 네이티브 UI 부재와 연계.
- **권장 수정 방향:** 기동 시 + 주기적 purge(`expires_at < now`), `max_history` 설정 키 + 초과분 오래된 것부터 영구삭제(고정 제외, Python 정책 이식).
- **필요한 회귀 테스트:** (Integration) 만료 행 존재 시 기동 후 purge. (Unit) `max_history=N` 초과 캡처 시 오래된 비고정 N개 초과분 삭제 + 고정 보존.

---

## 5. Potential Functional Gaps

- **Confirmed Gap — G-1. IPC가 읽기 전용이라 Milestone D–I가 제품 기능이 아님.** pin/북마크/메모/태그/컬렉션/스니펫/휴지통/Vault/가져오기/내보내기/삭제 UI가 없고, 백엔드 함수는 테스트에서만 호출된다. Parity Matrix의 "100%"는 백엔드 함수 단위 동등성이지 제품 동등성이 아니다.
- **Confirmed Gap — G-2. 전역 단축키·미니윈도우 동작 없음.** `tauri-plugin-global-shortcut`이 의존성에만 있고 등록 코드가 없다. `mini` 윈도우는 `visible:false` + 보여주는 명령이 없어 영원히 안 뜬다. `paste_last_command`도 호출자가 없다.
- **Confirmed Gap — G-3. 네이티브 자동 업데이트 없음.** Python의 Ed25519 서명 업데이터 상당체가 없고, `updates/latest.json`만 존재한다.
  → ✅ 해소(Follow-up 2): `src-tauri/src/updater/`(manifest 검증·아티팩트 스테이징·적용/롤백·`--apply-update` 헬퍼) + Tauri 커맨드
  (`update_check`/`update_download`/`update_apply`/`update_pending_result`/`quit_for_update`) + 사이드바 UI + 릴리즈 워크플로 서명 발행(`latest-native.json`).
- **Confirmed Gap — G-4. URL 제목 가져오기 등 네트워크 자동화 없음.** README·Python의 `fetch_title`(차단목록·캐시·디바운스 포함) 상당 로직이 네이티브에 없다. copy_rules도 변환 subset만 있다.
  → ✅ 해소(Follow-up 2): `src-tauri/src/clipboard/fetch_title.rs`(SSRF 차단·HTML 제한 읽기·256개/24h 캐시) + 파이프라인 연동 + `history_fetch_title` 커맨드/이벤트.
- **Confirmed Gap — G-5. Tray 토글이 메모리 전용.** privacy/pause 변경이 DB 설정·프론트에 전파되지 않고(emit 없음) 재시작하면 초기화된다. `settings_get_all`과 상태 이원화.
- **Confirmed Gap — G-6. CSV import·Markdown export 미구현.** Python 지원 범위 대비 축소. 지원 선언/README에서 범위 명시 필요.
- **Likely Gap — G-7. 스니펫 단축키 충돌 검증 없음.** Rust `add/update_snippet`이 앱·글로벌·상호 충돌을 검사하지 않는다(Python 계약). 백엔드-only.
- **추정 — G-8. FTS 인덱스 손상 시 검색 전체 실패.** `conn.prepare(&sql)?`가 에러를 그대로 올려 LIKE 폴백에 도달하지 못한다. 단, 토크나이저가 alnum만 남겨 MATCH 인젝션은 구조적으로 불가함을 확인했으므로 실제 발현은 인덱스 손상급에만 해당.
- **추정 — G-9. 평문 비밀 메모리 잔류.** `Fernet` 키는 `Drop` zeroize되나 복호화 평문(`Vec<u8>`/`String`)은 zeroize되지 않는다. Python도 마찬가지일 가능성이 높아 추정으로 둔다.
- **추정 — G-10. `tauri.conf.json`의 `csp: null`.** 명시적 비활성인지 기본값 대체인지 본 감사에서 확정하지 못했다. 보안 강화 관점에서 확인 필요.

---

## 6. Documentation Mismatches

1. **`claude.md`는 루트 Python 프로젝트를 전제로 기술.** 진입점 `클립모드 매니저.py`, `smartclipboard_app/`, `smartclipboard_core/`, `tests/`, `scripts/`, `pyrightconfig.json`, `smartclipboard.spec`, 필수 검증 절차 전부 루트에 존재하지 않는다(실물은 `legacy/python/` 하부). 루트에서 지시대로 실행하면 전부 실패한다. 마이그레이션 후 갱신 누락.
2. **`AGENTS.md` 없음.** 감사 지시문이 확인하라고 한 파일이 루트에 없다(`.agents/skills/`만 존재). 에이전트 진입 문서 부재.
3. **Parity Matrix의 "100%" 과장.** 최소 5건이 코드와 불일치: JSON 포맷 상이(§ISSUE-006), 복원 컬렉션 NULL 규칙 미구현(§ISSUE-005), 스니펫 충돌 검증 부재(G-7), 보존 purge 부재(§ISSUE-010), Fernet 보안 속성 차이(§ISSUE-003). "DB 바이너리 호환 100%"도 마이그레이션 부재(§ISSUE-007) 한정이 없다.
4. **README 범위 불명확.** 자동 업데이트·보안 보관함·스니펫·내보내기 등을 제품 기능처럼 소개하나 네이티브 UI에는 없고, "읽기 전용 호환 모드"라는 한정은 앱 내 배지에만 있다. 테스트 수("30건/230건")·버전 배지는 본 감사에서 검증 불가(오프라인) — 주장 유지 시 검증 수단 명시 필요.
5. **없다고 명시할 것:** `.codegraph/` git 제외는 `.gitignore`와 일치한다. `paths` 우선순위 설명과 `lib.rs resolve_db_path`는 서로 다르나 문서화된 스펙이 없어 mismatch가 아니라 코드 내 중복 정의 문제로 본다(§ISSUE-007).

---

## 7. Recommended Fix Plan

### Phase 1 — Immediate (데이터·보안·기동)

1. ISSUE-003 Fernet IV를 `getrandom`으로 교체 (1줄급, 파급 낮음, 효과 큼).
2. ISSUE-002 비밀번호 변경을 진짜 원자 트랜잭션으로 (`transaction()` + rollback, skip 제거, `INSERT OR REPLACE`, `.unwrap()` 제거, 새 비밀번호 정책).
3. ISSUE-004 `unlock` 실패 분기에 `self.lock()`.
4. ISSUE-007 마이그레이션(`user_version` + 레거시 `schema.py` 이식) — 구 DB 기동 실패를 막는다.
5. 제품 스코프 결정: 읽기 전용 유지라면 Parity Matrix·README의 "100%" 표현을 백엔드 범위로 정정하고, 쓰기 연결이라면 ISSUE-001부터.

### Phase 2 — Stability (검증·복원·보존·경로)

6. ISSUE-006 크로스 포맷 읽기 지원 + remap/백업/file_sig + 트랜잭션.
7. ISSUE-005 복원 NULL 규칙 + `deleted_history` FILE 컬럼 추가(마이그레이션 포함).
8. ISSUE-001 guard 공유 + 최근-복사 쿼리 분리.
9. ISSUE-009 쓰기 실패 보고 수정 + `EmptyClipboard` 순서 변경.
10. ISSUE-010 purge + `max_history` 이식. ISSUE-008 라벨/guard. G-5 tray 상태 전파·영속화. FTS 실패 시 LIKE 폴백(G-8).

### Phase 3 — Structural (제품 완성·테스트 가능성)

11. G-2 단축키 등록 + 미니윈도우 표시 경로, G-1 쓰기 IPC를 도메인별 thin command로 노출(쓰기마다 guard·검증 포함), G-3 업데이터, G-4 fetch 자동화(차단목록·캐시 정책 이식), G-6 범위 명시.
12. `resolve_db_path` 일원화(`paths` vs `lib.rs`), Win32 API 추상화로 단위 테스트 가능하게, CodeGraph 재인덱싱(Rust 포함)으로 감사 가능성 회복.
13. `claude.md` 네이티브 기준으로 재작성 + `AGENTS.md` 신설(또는 명시적 폐기 선언).

실제 코드는 수정하지 않았다.

---

## 8. Test Recommendations

환경 전제: `cargo test`가 오프라인에서도 돌도록 `Cargo.lock` + vendored deps 또는 사전 빌드 캐시 확보가 선행되어야 한다(현재 미충족).

- **Unit — Fernet IV 무작위성:** 같은 평문 200회 암호화 → 토큰 200종. 기대: 전부 상이 + 전부 복호화 성공.
- **Unit — 변경 원자성:** 3행 중 2행째 encrypt 실패 주입 → `Err` + 기존 비밀번호로 3행 전부 복호화 성공 + `vault_salt` 불변.
- **Unit — unlock 실패 리셋:** 성공→실패 호출 후 `is_unlocked()==false`, `get_secret`은 `Err`.
- **Unit — 복원 무결성:** 컬렉션 삭제 후 복원 → `collection_id IS NULL`. FILE 삭제→복원 → `file_signature` 동일 + 재복사 시 `updated=true`, row 수 불변.
- **Unit — guard 공유:** 파이프라인과 동일한 `Arc` guard로 mark 후 `is_internal(seq, content)==true`, 3초 만료 후 `false`.
- **Integration — paste-last E2E:** pinned 1건 + 최신 텍스트 1건 상태에서 호출 → 최신 텍스트가 클립보드에 기록되고, 300ms 내 파이프라인이 추가 row를 만들지 않음.
- **Integration — 크로스 임포트:** Python `items` 포맷 fixture → Rust import → 행 수·컬렉션 remap·FILE 서명·이미지 복원 확인. 역방향도 동일.
- **Integration — 구 DB 마이그레이션:** `url_title` 없는 v5 DB 복사본 open → `user_version` 상승 + 읽기/쓰기/FTS 검색 정상.
- **Concurrency — 캡처 경합:** 50 스레드 동시 `add_item`(동일 내용) → row 1건 + 나머지는 갱신. 단일 Mutex라 통과 예상이나 회귀 방지용.
- **Concurrency — 리스너 과부하:** 10ms 간격 클립보드 변경 50회 → 손실 없이 최소 1건 이상 캡처 + 스레드 패닉 없음(디바운스 병합은 허용, 크래시는 불허).
- **Regression — 쓰기 거짓 성공:** `write_clipboard_text` 할당 실패 주입 → `false` + 이전 클립보드 내용 유지.
- **Regression — 이미지 라벨:** 32/24bit DIB fixture → `이미지 [WxH]` 실측 표기.
- **Platform-specific — 장기 보존:** 만료 휴지통 100건 + `max_history` 초과 상태에서 기동 → purge/cap 동작 + 고정 항목 생존.
- **Platform-specific — 경로:** 1024자 초과 파일 경로(UNC·long path) 캡처 → 잘림 없이 저장·복원(현재 1024 고정 버퍼는 `file_reader.rs:31` — `DragQueryFileW` 요구 길이 재조회로 수정 후 검증).

---

## 9. Final Assessment

| 영역 | 평가 | 근거 |
|---|---|---|
| Functional Correctness | Needs Work | 캡처·읽기는 동작하나 제품 쓰기 경로가 IPC에 없고, 백엔드에 확정 버그 다수(가드·복원·임포트) |
| Runtime Stability | Acceptable | 리스너 별도 스레드·단일 Mutex 직렬화로 치명적 경쟁 없음. 단 `.unwrap()` 패닉 1건과 트랜잭션 고착 리스크 존재 |
| Data Integrity | Needs Work | 롤백 없는 수동 트랜잭션, 손상 행 silent skip, 포맷 단절, 마이그레이션 부재, 보존 미집행 |
| Error Resilience | Needs Work | 쓰기 거짓 성공, FTS 하드 실패, salt `.unwrap()`, 조용한 base64 드롭 |
| Cross-platform Robustness | Acceptable | Windows 전용 설계로 일관됨. Linux/macOS 미지원은 스코프内. long-path 잘림 1건은 Windows 내 이슈 |
| Test Confidence | Needs Work | "30건 통과"를 본 환경에서 재현 불가(오프라인). IPC·E2E·동시성 테스트 부재 |

**실제로 먼저 수정할 문제 3개:**

1. **Fernet 결정적 IV → CSPRNG** ([ISSUE-003]) — 수정 1줄, 보안 효과 최대, 호환성 영향 없음.
2. **비밀번호 변경 원자성 + unlock 실패 리셋** ([ISSUE-002], [ISSUE-004]) — 보관함 전체 잠금/상태 불일치는 IPC 연결 전에 반드시 제거.
3. **제품 스코프 확정 + 스키마 마이그레이션** ([ISSUE-007], §7-5) — 구 DB 기동 실패와 "100%" 문서 과장을 동시에 해소하는 분기점.

# SmartClipboard Pro — Rust + Tauri 네이티브 전환 계획

> **상태: 전체 마일스톤 (Milestone A ~ I) 100% 구현 및 교차 검증 완료 (2026-09-03)**  
> **검증 요약: Rust 네이티브 테스트 30건 PASS · Clippy 0 warnings · Vite 빌드 PASS · Python 회귀 테스트 230건 PASS**  
> 대상 저장소: `twbeatles/smartclipboard`  
> 목표: **기존 Python/PyQt6 버전을 기준 구현(reference implementation)으로 유지하면서, 기존 DB·설정·Vault를 그대로 호환하는 Rust + Tauri 2 네이티브 버전으로 점진 전환한다.**  
> 핵심 원칙: 한 번에 재작성하지 않는다. 데이터 호환성, 보안, 상주 안정성, rollback 가능성을 성능보다 우선한다.

---

## 0. 에이전트 실행 지시

구현 시작 전에 반드시 다음을 먼저 읽는다.

```text
README.md
claude.md
gemini.md
PROJECT_ANALYSIS.md
PROJECT_AUDIT.md
requirements.txt
smartclipboard.spec
smartclipboard_app/
smartclipboard_core/
tests/
scripts/
```

특히 다음 영역을 정밀 확인한다.

```text
smartclipboard_app/features/clipboard/
smartclipboard_app/features/tray_hotkey/
smartclipboard_app/features/vault/
smartclipboard_app/features/action_palette/
smartclipboard_core/database.py
smartclipboard_core/db_parts/
smartclipboard_core/file_paths.py
smartclipboard_core/actions.py
smartclipboard_core/automation/
```

현재 기준선을 먼저 기록한다.

```powershell
pytest
pyright .
python scripts/preflight_local.py
```

기존 실패가 있으면 Rust/Tauri 전환으로 발생한 실패와 분리해 기록한다.

### 안전 규칙

- 실제 사용자 DB를 테스트 fixture로 사용하지 않는다.
- 실제 clipboard history / Vault plaintext를 테스트 자산으로 저장하지 않는다.
- migration 테스트는 synthetic DB 또는 anonymized copy에서만 수행한다.
- 기존 Python 앱과 DB를 초기 단계에서 삭제·변경하지 않는다.
- Vault 초기화, history 전체 삭제, production DB schema destructive migration을 자동 실행하지 않는다.
- password, derived key, Vault plaintext, clipboard plaintext를 로그에 남기지 않는다.

---

# 1. 현재 구조에서 변경 불가 계약

## 1.1 데이터베이스

현재 DB 파일명:

```text
clipboard_history_v6.db
```

현재 SQLite 설정:

```sql
PRAGMA journal_mode=WAL;
PRAGMA synchronous=NORMAL;
```

주요 테이블:

```text
history
snippets
settings
copy_rules
secure_vault
clipboard_actions
collections
deleted_history
```

Native 전환 중 기존 table/column 의미를 바꾸지 않는다.

## 1.2 FTS5

기존 검색 인덱스:

```text
history_fts
```

대상:

```text
content
tags
note
url_title
```

tokenizer:

```text
unicode61
```

기존 INSERT/UPDATE/DELETE trigger를 그대로 활용한다. 초기 Native 버전에서 별도의 검색 스키마로 재설계하지 않는다.

## 1.3 History 중복 병합

TEXT/LINK/CODE/COLOR 등 non-image/non-file 항목은 같은 `content`가 있으면 새 row를 만들지 않고 기존 row의 timestamp/type 등을 최신화한다.

다음 metadata는 보존되어야 한다.

```text
tags
note
bookmark
collection_id
pinned
pin_order
use_count
```

FILE은 기존 `file_signature` 기준으로 병합한다.

IMAGE는 기존과 같이 별도 row를 생성한다.

이 동작은 Rust port 후에도 정확히 유지한다.

---

# 2. Clipboard 동작 계약

현재 clipboard change 후 약 100ms debounce를 거친다.

우선순위:

```text
FILE
→ IMAGE
→ TEXT
```

## TEXT

- UTF-8 기준 최대 1 MiB
- copy rule 적용
- 빈 문자열 제외
- LINK / COLOR / CODE / TEXT 분류
- DB add/merge
- 자동 action 처리

## IMAGE

- clipboard image를 PNG bytes로 저장
- 기존 최대 크기 정책 유지
- 최근 동일 이미지 중복 방지

## FILE

- Explorer clipboard path 목록 추출
- 기존 `file_paths.py`의 serialize/normalize/signature 형식과 완전 호환

Native migration PR에서 이 의미를 동시에 개선하거나 바꾸지 않는다.

---

# 3. Vault 암호화 계약 — 최우선 호환성

현재 Vault:

```text
salt            = random 16 bytes
KDF             = PBKDF2-HMAC-SHA256
iterations      = 480000
derived length  = 32 bytes
key encoding    = URL-safe Base64
cipher          = Fernet
```

settings key:

```text
vault_salt
vault_verification
```

verification plaintext:

```text
VAULT_VERIFIED
```

Native 전환 중 다음 변경 금지:

```text
Argon2 전환
AES-GCM 전환
ChaCha20 전환
PBKDF2 iteration 변경
salt 크기 변경
Fernet 제거
```

암호화 방식 현대화는 Native migration 완료 후 별도 프로젝트로 수행한다.

---

# 4. 최종 목표 아키텍처

```text
┌──────────────────────────────────────┐
│ Tauri 2                              │
│ React + TypeScript                   │
│                                      │
│ Main Window                          │
│ Mini Window                          │
│ Settings / Vault / Snippets          │
│ Trash / Collections / Action Palette │
└─────────────────┬────────────────────┘
                  │ typed commands/events
                  ▼
┌──────────────────────────────────────┐
│ Rust Backend                         │
│                                      │
│ Win32 Clipboard Listener             │
│ Clipboard Reader / Writer            │
│ SQLite + FTS5                        │
│ History / Settings / Trash           │
│ PBKDF2 + Fernet Vault                │
│ Global Hotkeys                       │
│ Tray / Paste / SendInput             │
│ Automation / Import / Export         │
│ Updater / Migration                  │
└──────────────────────────────────────┘
```

최종 배포판에는 Python interpreter와 PyQt6가 없어야 한다.

---

# 5. 왜 PyO3 코어 이관이 아닌 Tauri 병렬 전환인가

이 프로젝트의 Native 이득은 CPU-heavy 연산보다 다음에서 발생한다.

```text
상주 메모리
startup
Windows clipboard event integration
tray
hotkey
배포 구조
상시 실행 안정성
```

따라서 장기간:

```text
PyQt → Python → PyO3 → Rust
```

구조를 유지하는 것보다 Native 앱을 병렬 구현하고 기능 parity 후 교체하는 것이 적합하다.

`pyduplicate-finder`와 접근 방법을 구분한다.

---

# 6. 권장 디렉터리 구조

기존 Python 코드는 그대로 둔다.

```text
smartclipboard/
├─ smartclipboard_app/          # Python reference
├─ smartclipboard_core/         # Python reference
│
├─ native/
│  ├─ package.json
│  ├─ vite.config.ts
│  ├─ tsconfig.json
│  ├─ src/
│  │  ├─ app/
│  │  ├─ components/
│  │  ├─ pages/
│  │  ├─ windows/
│  │  ├─ hooks/
│  │  ├─ types/
│  │  └─ styles/
│  │
│  └─ src-tauri/
│     ├─ Cargo.toml
│     ├─ tauri.conf.json
│     ├─ capabilities/
│     └─ src/
│        ├─ lib.rs
│        ├─ app_state/
│        ├─ commands/
│        ├─ clipboard/
│        │  ├─ listener.rs
│        │  ├─ win32.rs
│        │  ├─ reader.rs
│        │  ├─ writer.rs
│        │  ├─ formats.rs
│        │  └─ internal_guard.rs
│        ├─ database/
│        │  ├─ connection.rs
│        │  ├─ history.rs
│        │  ├─ search.rs
│        │  ├─ settings.rs
│        │  ├─ collections.rs
│        │  ├─ snippets.rs
│        │  ├─ trash.rs
│        │  └─ migrations.rs
│        ├─ vault/
│        ├─ hotkeys/
│        ├─ tray/
│        ├─ paste/
│        ├─ automation/
│        ├─ import_export/
│        ├─ updater/
│        ├─ paths/
│        └─ errors.rs
│
└─ tests/
   └─ native_parity/
```

---

# 7. Frontend 선택

권장:

```text
Tauri 2
React
TypeScript strict
Vite
```

Next.js는 사용하지 않는다. 이 앱은 SSR/SEO가 필요 없는 로컬 데스크톱 앱이다.

Frontend 책임:

```text
rendering
view state
dialogs
forms
theme
keyboard navigation
```

Rust 책임:

```text
clipboard
SQLite
encryption
filesystem
hotkey
tray
network action
updater
```

Frontend에서 SQLite에 직접 접근하지 않는다.

---

# 8. Tauri 보안 원칙

Frontend에 무제한 `fs`, `shell`, `process`, `clipboard` 권한을 주지 않는다.

가능하면 typed command만 노출한다.

예:

```text
history_list
history_search
history_delete
clipboard_copy_item
vault_unlock
vault_lock
settings_get
settings_set
```

Tauri capability는 필요한 command/plugin만 허용한다.

Clipboard content는 untrusted input이므로 React에서 raw HTML로 렌더링하지 않는다.

`dangerouslySetInnerHTML`은 기본 금지한다.

---

# 9. Phase 0 — Baseline / 계약 동결

## 9.1 Feature parity matrix

`docs/NATIVE_PARITY_MATRIX.md` 생성.

예:

| Feature | Python | Native | Test | Status |
|---|---|---|---|---|
| text capture | yes | no | planned | pending |
| image capture | yes | no | planned | pending |
| file capture | yes | no | planned | pending |
| FTS search | yes | no | planned | pending |
| vault decrypt | yes | no | mandatory | pending |
| global hotkey | yes | no | manual | pending |
| mini window | yes | no | UI | pending |
| updater | yes | no | release | pending |

## 9.2 성능 baseline

측정:

```text
cold startup
warm startup
idle RSS
idle CPU
clipboard event → DB 저장 latency
hotkey → main window visible latency
hotkey → paste latency
search latency
DB open time
배포 크기
```

최소 10회 측정 후 median/p95 기록.

## 9.3 Synthetic DB fixture

Python 현재 구현으로 test DB 생성.

포함:

```text
TEXT
LINK
COLOR
CODE
IMAGE
FILE
tags
note
bookmark
pin
collection
snippet
copy rule
clipboard action
trash
settings
vault
```

실제 사용자 DB 금지.

## 9.4 Vault golden vectors

Python `cryptography` 구현으로 test vector를 생성한다.

성공 기준:

```text
Python encrypt → Rust decrypt
Rust encrypt → Python decrypt
```

Fernet ciphertext equality 자체를 요구하지 않는다.

---

# 10. Phase 1 — Tauri Shell

이 단계에서는 clipboard/production DB에 접근하지 않는다.

구현:

```text
Tauri project
React/TS shell
main window
mini window skeleton
tray
single instance
logging
basic theme
```

Tauri 2 official single-instance plugin 사용을 우선한다.

두 번째 실행 시 기존 창을 show/focus 한다.

Tray 메뉴 초기 parity:

```text
보기
프라이버시 모드
모니터링 일시정지
설정
종료
```

UI 디자인 재설계는 하지 않는다.

---

# 11. Phase 2 — 기존 DB Read-only Compatibility

반드시 기존 DB **복사본**으로 먼저 구현한다.

Rust DB 계층은 `rusqlite` 등 검증된 SQLite binding을 우선 검토한다.

Frontend가 SQL을 직접 실행하지 않는다.

최소 read API:

```text
list_history
get_content
search_history
get_tags
get_collections
get_snippets
get_settings
get_trash
vault_has_password
```

## FTS parity

같은 fixture DB에서 Python/Rust 결과를 비교한다.

```text
한글
영문
숫자
prefix
multiple terms
tags
note
url_title
```

정렬 순서까지 확인한다.

---

# 12. Phase 3 — DB Write Parity

Read parity 100% 후 시작한다.

포팅 우선순위:

```text
add_item
replace_text_item_or_merge
metadata
pin/bookmark
collections
delete/trash
restore
settings
```

## Transaction

multi-row operation은 반드시 transaction.

예:

```text
text merge
password change
trash restore
collection remap
import
```

## FTS

Rust가 FTS를 수동으로 중복 갱신하지 않는다.

기존 DB trigger가 동작하게 한다.

INSERT/UPDATE/DELETE 후 FTS 결과를 테스트한다.

---

# 13. Phase 4 — Native Clipboard Listener

Windows clipboard 감지는 polling이 아니라 event-driven으로 구현한다.

권장 Win32 API:

```text
AddClipboardFormatListener
WM_CLIPBOARDUPDATE
RemoveClipboardFormatListener
GetClipboardSequenceNumber
```

권장 구조:

```text
hidden/message window
→ AddClipboardFormatListener
→ WM_CLIPBOARDUPDATE
→ Rust channel
→ debounce
→ clipboard pipeline
→ DB
→ Tauri event
→ UI refresh
```

main window가 숨겨져 있어도 monitoring이 유지되어야 한다.

---

# 14. Clipboard Reader

## Text

우선 `CF_UNICODETEXT` 지원.

UTF-8 변환 후 기존 1 MiB 제한 적용.

## Files

Explorer 파일 복사는 `CF_HDROP`을 읽는다.

기존 `file_paths.py`와 동일한 normalize/serialize/signature 결과를 만들어야 한다.

## Image

기존 DB-compatible PNG bytes로 변환한다.

Windows clipboard에서 최소 다음을 조사/테스트한다.

```text
PNG registered format
CF_DIB
CF_DIBV5
```

초기부터 모든 이미지 포맷을 지원하려 하지 않는다.

---

# 15. Clipboard internal-copy guard

SmartClipboard가 clipboard에 쓴 내용을 다시 history로 수집하면 안 된다.

Rust state 예:

```text
InternalWriteGuard
- sequence_before
- expected_sequence
- content_fingerprint
- expires_at
```

가능하면 `GetClipboardSequenceNumber`를 활용한다.

성공 조건:

```text
앱 자체 copy → history 재추가 없음
외부 앱이 직후 새 copy → 정상 capture
```

---

# 16. Debounce / Retry

초기 debounce는 기존과 동일하게 약 100ms 유지.

`OpenClipboard`가 다른 process 때문에 잠깐 실패할 수 있으므로 bounded retry를 둔다.

```text
짧은 backoff
총 timeout 제한
무한 retry 금지
```

Migration과 behavior tuning을 한 PR에서 같이 하지 않는다.

---

# 17. Clipboard Pipeline Port

Rust pipeline:

```text
clipboard event
→ privacy/pause check
→ format detection
→ size limit
→ copy rules
→ classification
→ history add/merge
→ actions
→ frontend history_changed event
```

Frontend event에 clipboard plaintext 전체를 broadcast하지 않는다.

예:

```text
history_changed { id, type }
```

정도만 보내고 content는 별도 command로 조회한다.

---

# 18. Copy Rule 호환성

기존 action:

```text
trim
lowercase
uppercase
remove_newlines
custom_replace
```

주의: Rust `regex`와 Python `re` 문법은 완전히 동일하지 않다.

따라서 기존 사용자 pattern fixture를 만든 뒤 호환성을 확인한다.

Python-specific regex가 실제 사용될 수 있으면 다음 중 하나를 명시적으로 선택한다.

```text
compatible engine
unsupported pattern detection
migration warning
```

기존 rule을 조용히 다르게 해석하지 않는다.

---

# 19. Classification parity

다음 fixture를 Python/Rust에서 비교한다.

```text
http / https
hex color
rgb / rgba
hsl
code snippets
plain text
Korean text
```

결과는 기존:

```text
LINK
COLOR
CODE
TEXT
```

와 일치해야 한다.

---

# 20. Phase 5 — Global Hotkey / Tray / Paste

Tauri 2 official global-shortcut plugin을 우선 사용한다.

기존 dynamic hotkey:

```text
show_main
show_mini
paste_last
```

을 지원한다.

현재 Python처럼:

```text
기존 hotkey 해제
새 hotkey 등록
실패 시 기존 hotkey 복구
```

rollback semantics를 유지한다.

## Paste Last

```text
latest item 조회
→ clipboard write
→ internal guard
→ 약 100ms
→ Windows SendInput Ctrl+V
```

Python `keyboard` package 의존성을 제거한다.

다음 권한 조합을 실제 Windows에서 테스트한다.

```text
normal → normal
normal → elevated
 elevated → normal
```

---

# 21. Phase 6 — Vault Rust Port

DB/clipboard core가 안정화된 이후에만 진행한다.

## KDF

정확히:

```text
PBKDF2-HMAC-SHA256
480000 iterations
32-byte output
16-byte salt
```

## Fernet

Rust Fernet 구현은 Python `cryptography.fernet.Fernet`과 상호운용 가능해야 한다.

Mandatory tests:

```text
Python encrypt → Rust decrypt
Rust encrypt → Python decrypt
vault_verification decrypt
secure_vault row decrypt
password change
wrong password
corrupted token
```

## Password Change

```text
current password verify
→ 모든 row decrypt
→ new salt/key
→ 모든 row re-encrypt
→ settings update
→ COMMIT
```

하나라도 실패하면 ROLLBACK.

## Key memory

가능하면 key material에 `zeroize` 등을 사용한다.

lock 시 plaintext/key cache를 최대한 제거한다.

---

# 22. Vault timeout / clipboard auto-clear

기존 기본 timeout:

```text
300 seconds
```

유지.

Vault plaintext copy 후 30초 auto-clear는 다음처럼 구현한다.

```text
secret write
→ sequence/fingerprint 저장
→ 30 sec
→ clipboard가 여전히 같은 secret이면 clear
→ 사용자가 다른 내용을 복사했다면 건드리지 않음
```

사용자의 새 clipboard를 실수로 지우지 않는다.

---

# 23. Phase 7 — 나머지 기능

권장 순서:

```text
tags / bookmark / pin
collections
snippets
trash
statistics
automatic actions
action palette
import/export
```

Trash 기존 계약:

```text
soft delete
deleted_history
7-day retention
restore
permanent delete
```

유지.

---

# 24. URL title / Network action

네트워크 작업은 Rust backend에서 수행하는 편을 권장한다.

검토:

```text
reqwest
bounded timeout
redirect limit
response size limit
user-agent
HTML title extraction
```

민감 content에는 기존처럼 외부 network action을 제한한다.

```text
password-like
API-key-like
vault-derived
sensitive tag
```

---

# 25. Import / Export

기존:

```text
JSON
CSV
Markdown export
JSON/CSV import
```

round-trip compatibility 유지.

기존 JSON format을 먼저 그대로 읽고 써야 한다.

Native용 새 format version은 parity 완료 후 별도 migration으로 한다.

---

# 26. App Data Path Migration

현재 frozen Python 앱은 executable directory를 app data 경로로 사용할 수 있다.

Tauri installer가 Program Files에 들어가면 같은 정책을 그대로 쓰기 어렵다.

따라서 Native path resolver를 명시한다.

권장 우선순위:

```text
1. --data-dir override
2. configured legacy data path
3. %LOCALAPPDATA%\SmartClipboard
4. portable legacy DB adjacent to executable
```

정확한 최종 정책은 현재 release 방식 확인 후 확정한다.

## Legacy DB 이동

단순 파일 copy로 WAL consistency를 깨지 않는다.

가능하면 legacy app 종료 상태에서 SQLite backup API를 사용한다.

Migration 성공 후 원본 DB 자동 삭제 금지.

versioned backup을 남긴다.

---

# 27. Python / Native 동시 실행 방지

두 앱이 동시에 clipboard를 monitor하면 duplicate capture가 발생할 수 있다.

Native preview 배포 전 shared named mutex를 검토한다.

Python 쪽에도 최소 호환 패치를 넣어 Native 실행 중일 때 경고 후 종료하도록 할 수 있다.

실제 이름은 기존 single-instance 구현을 조사한 뒤 결정한다.

---

# 28. Updater 전환

기존 Python updater의:

```text
GitHub Releases
Ed25519
SHA-256
backup
rollback
```

동작을 잊지 않는다.

Tauri 2 updater는 signed update를 요구하므로 Native 전용 signing flow를 만든다.

기존 signing key format과 Tauri key format이 동일하다고 가정하지 않는다.

Private key는 repo에 저장하지 않는다.

Tauri 기본 updater가 기존 앱의 rollback UX와 동일하다고 가정하지 않는다.

최소:

```text
DB pre-update backup
config backup
health marker
previous version metadata
recovery path
```

를 설계한다.

---

# 29. Single Instance / Autostart / Tray

현재 Tauri 2 official plugin/API를 우선 검토한다.

```text
single-instance
global-shortcut
autostart
updater
tray
```

정확한 version/API는 구현 시점 공식 stable docs에서 다시 확인한다.

계획서의 예전 API를 그대로 복사하지 않는다.

---

# 30. Rust dependency 후보

구현 시 current stable을 확인한다.

```text
tauri
tauri-plugin-global-shortcut
tauri-plugin-single-instance
tauri-plugin-autostart
tauri-plugin-updater
windows
rusqlite
serde
serde_json
thiserror
tracing
pbkdf2
sha2
hmac
base64
fernet
zeroize
reqwest
```

필요한 경우에만:

```text
image
regex
url
```

추가.

---

# 31. Win32 unsafe 격리

Raw Win32 clipboard API의 `unsafe`는 작은 모듈로 제한한다.

예:

```text
clipboard/win32.rs
```

safe wrapper:

```text
ClipboardListener
ClipboardReader
ClipboardWriter
ClipboardSequence
```

Application logic이 raw pointer/HWND/HGLOBAL을 직접 다루지 않게 한다.

---

# 32. Privacy / Security

Privacy Mode에서는 frontend flag만 믿지 않는다.

Rust backend 자체에서 capture를 차단한다.

로그 금지:

```text
clipboard full text
image bytes
file list 전체
vault plaintext
master password
derived key
secret token
```

외부 telemetry는 기본 활성화하지 않는다.

SQL은 parameter binding을 사용한다.

---

# 33. DB concurrency

Clipboard monitor는 background에서 write하고 UI는 query할 수 있다.

WAL을 유지하면서:

```text
short transactions
serialized writes
concurrent reads
```

를 설계한다.

거대한 Mutex로 connection을 장시간 점유하지 않는다.

필요하면 writer/read connection 분리를 benchmark 후 검토한다.

---

# 34. Image IPC 최적화

History list API에서 모든 image BLOB을 한꺼번에 frontend로 보내지 않는다.

목록에는:

```text
id
type
preview metadata
timestamp
```

정도만 반환.

이미지는 detail/thumbnail command로 별도 로딩.

---

# 35. UI 이관 순서

```text
1. Shell / sidebar
2. History list
3. Search / filter
4. Main actions
5. Mini window
6. Settings
7. Tags / Collections
8. Snippets
9. Trash
10. Action Palette
11. Vault
12. Statistics
```

기존 5개 theme는 CSS token으로 옮긴다.

```text
Dark
Light
Ocean
Purple
Midnight
```

PyQt QSS를 기계 변환하지 않는다.

---

# 36. Test 전략

Python reference:

```text
pytest
pyright
preflight
```

Rust:

```text
cargo fmt --check
cargo test
cargo clippy
```

Frontend:

```text
tsc --noEmit
unit/component tests
```

Native parity:

```text
DB fixture
FTS
history merge
FILE signature
copy rules
classification
Vault interoperability
```

---

# 37. Windows Integration Test Matrix

최소:

```text
Windows 10
Windows 11
100% / 125% / 150% scaling
multi-monitor
sleep/resume
lock/unlock
Explorer restart
Chrome text copy
VS Code text copy
Terminal text copy
Explorer file copy
Snipping Tool image
Paint/Office image
SmartClipboard self-copy
paste_last
```

---

# 38. Soak Test

SmartClipboard는 상시 실행 앱이므로 1회 기능 test만으로 부족하다.

최소:

```text
8~24 hours
thousands of synthetic clipboard events
```

확인:

```text
memory growth
handle leak
thread leak
DB lock
clipboard duplication
hotkey loss
tray disappearance
```

---

# 39. Benchmark Gate

실제 baseline을 측정한 뒤 최종 수치를 확정한다.

권장 목표:

```text
startup p50 <= Python baseline 60%
idle RSS <= Python baseline 50%
idle CPU 악화 없음
clipboard capture latency 악화 없음
FTS search 악화 없음
```

Tauri는 WebView2 child process도 있으므로 main process만 보지 말고 관련 process memory 합계를 비교한다.

---

# 40. Native Preview / Rollback

초기에는 Python 앱을 제거하지 않는다.

권장:

```text
SmartClipboard v10.x
SmartClipboard Native Preview
```

병렬 배포 테스트.

단 동일 DB를 두 앱이 동시에 write/monitor하지 않도록 막는다.

Native에는 개발용 `--read-only` 모드를 두는 것을 권장한다.

이 모드:

```text
DB read/search/UI 가능
clipboard monitor off
DB write off
Vault password change off
delete off
```

---

# 41. DB Write 시작 전 Gate

실제 기존-format DB를 Native가 write mode로 열기 전에:

```text
1. integrity_check
2. backup
3. backup integrity check
4. schema version 확인
5. parity smoke
```

백업 실패 시 migration 중단.

기존 Python과 병행 기간에는 additive schema change만 허용한다.

기존 column rename/delete 금지.

---

# 42. PR 분할

### PR 1 — Baseline

```text
parity matrix
benchmarks
synthetic DB fixture
Vault vectors
```

### PR 2 — Tauri shell

```text
React/TS
main/mini shell
tray
single instance
```

### PR 3 — DB read-only

```text
history
search
settings
collections
```

### PR 4 — DB write parity

```text
add_item
merge
metadata
FTS trigger tests
```

### PR 5 — Native clipboard TEXT

```text
WM_CLIPBOARDUPDATE
text
100ms debounce
internal guard
```

### PR 6 — FILE + IMAGE clipboard

```text
CF_HDROP
image formats
size limits
```

### PR 7 — hotkey / paste / mini

### PR 8 — Vault interoperability

### PR 9 — tags/snippets/trash/actions

### PR 10 — import/export/settings/statistics

### PR 11 — updater/data migration/packaging

### PR 12 — Native default candidate

---

# 43. 최초 구현 범위

에이전트에게 이 문서 전체를 주더라도 첫 작업은 **Milestone A~C만** 수행한다.

## Milestone A — Baseline

- [ ] README / CLAUDE / GEMINI / PROJECT_ANALYSIS / AUDIT 검토
- [ ] pytest baseline
- [ ] pyright baseline
- [ ] preflight baseline
- [ ] parity matrix
- [ ] performance baseline harness
- [ ] synthetic DB fixture
- [ ] Vault golden vectors

## Milestone B — Tauri Skeleton

- [ ] `native/` 생성
- [ ] Tauri 2 build
- [ ] React + TypeScript strict
- [ ] main window
- [ ] mini window skeleton
- [ ] tray
- [ ] single instance
- [ ] logging
- [ ] CI build

**Clipboard monitor/DB write 금지.**

## Milestone C — DB Read-only

- [ ] DB copy open
- [ ] history list
- [ ] content read
- [ ] FTS search
- [ ] settings read
- [ ] tags/collections read
- [ ] Python/Rust parity

Milestone C 종료 후 결과를 보고하고 다음 단계로 넘어간다.

---

# 44. 두 번째 구현 범위

## Milestone D

- [ ] DB write parity
- [ ] add_item
- [ ] duplicate merge
- [ ] FTS trigger verification

## Milestone E

- [ ] Win32 clipboard listener
- [ ] TEXT capture
- [ ] internal copy guard
- [ ] privacy/pause
- [ ] latency benchmark

## Milestone F

- [ ] FILE capture
- [ ] IMAGE capture
- [ ] global hotkeys
- [ ] paste_last
- [ ] mini window actual integration

---

# 45. 세 번째 구현 범위

## Milestone G

- [ ] Python ↔ Rust Fernet compatibility
- [ ] Vault unlock/lock
- [ ] password change
- [ ] auto-lock
- [ ] secret clipboard clear

## Milestone H

- [ ] tags/collections
- [ ] snippets
- [ ] trash
- [ ] actions / palette

## Milestone I

- [ ] import/export
- [ ] updater
- [ ] app data migration
- [ ] packaging
- [ ] Native Preview release

---

# 46. 구현 중 금지사항

- Python 앱 즉시 삭제
- 기존 DB 전면 재설계
- DB 파일명 임의 변경
- Vault cipher 자동 변경
- production DB를 테스트에서 직접 수정
- frontend에 arbitrary SQL 권한 제공
- unrestricted shell/fs capability 허용
- clipboard polling loop
- giant one-shot rewrite
- feature parity 전 Python update channel 제거
- 기존 JSON export format 임의 변경
- regex parity 검증 없는 engine 교체
- signing private key repository 저장
- clipboard/Vault plaintext logging

---

# 47. 최종 완료 조건

다음이 모두 true일 때 Python을 기본 배포에서 제거한다.

- [ ] Feature parity matrix 100%
- [ ] DB parity 100%
- [ ] FTS parity 100%
- [ ] Python ↔ Rust Fernet interoperability
- [ ] 기존-format DB migration 통과
- [ ] text clipboard 안정
- [ ] file clipboard 안정
- [ ] image clipboard 안정
- [ ] hotkey 안정
- [ ] paste_last 안정
- [ ] privacy/pause 안정
- [ ] Vault timeout 안정
- [ ] secret auto-clear 안정
- [ ] updater signing 검증
- [ ] recovery/rollback 검증
- [ ] Windows 10/11 smoke
- [ ] 8~24h soak test
- [ ] startup/idle RAM/capture/search benchmark 기록
- [ ] Python legacy rollback 가능

---

# 48. 포트폴리오 목표

최종적으로 다음 설명이 가능해야 한다.

> **PyQt 기반 Windows 상주형 SmartClipboard를 Rust + Tauri로 점진 마이그레이션했다. Win32 `WM_CLIPBOARDUPDATE` 기반 event-driven clipboard listener, SQLite FTS5, dynamic global shortcuts, tray application, PBKDF2/Fernet Vault를 Rust로 이관하면서 기존 Python DB·Vault와의 하위 호환성을 유지했다. Python/Rust parity fixtures와 cross-language crypto tests를 구축하고 startup·idle-memory·capture-latency benchmark로 Native 전환 효과를 검증했다.**

---

# 49. Milestone 종료 보고 형식

```markdown
## 구현 결과

### 범위
- Milestone:

### 변경 파일
- ...

### 구현 내용
- ...

### Compatibility
- DB:
- FTS:
- Vault:
- Settings:
- Export:

### Tests
- pytest:
- pyright:
- cargo test:
- cargo clippy:
- frontend typecheck:
- native parity:

### Benchmark
| 항목 | Python | Native | 차이 |
|---|---:|---:|---:|
| startup | | | |
| idle RSS | | | |
| capture | | | |
| search | | | |

### Security
- clipboard plaintext logging:
- Vault plaintext logging:
- Tauri capabilities:
- DB backup:

### 남은 문제
- ...

### 다음 단계
- ...
```

성능이 기대보다 낮으면 숨기지 말고 원인을 구분한다.

```text
WebView2 memory
SQLite already fast
clipboard lock contention
IPC overhead
UI rendering
network action latency
```

---

# 50. 에이전트에 바로 던질 최초 명령

```text
이 계획서를 기준으로 SmartClipboard Rust/Tauri 전환을 시작하라.

이번 작업에서는 Milestone A~C까지만 수행한다.
기존 Python 앱, DB 스키마, Vault 데이터를 변경하거나 삭제하지 말라.
실제 사용자 DB 또는 clipboard 데이터를 테스트에 사용하지 말라.

먼저 README.md, claude.md, gemini.md, PROJECT_ANALYSIS.md,
PROJECT_AUDIT.md와 tests를 읽고 현재 동작을 정확히 파악하라.

그 다음 baseline/parity fixture/Tauri skeleton/DB read-only compatibility를 구현하라.
기존 테스트와 신규 테스트를 실행하고 Python과 Native의 DB/FTS 결과가 동일한지 검증하라.

작업 종료 시 이 문서의 'Milestone 종료 보고 형식'으로
변경 내용, 테스트, 호환성, benchmark, 보안 점검, 미구현 사항을 보고하라.
```

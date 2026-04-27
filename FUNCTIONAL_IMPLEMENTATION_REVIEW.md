# SmartClipboard 기능 구현 리스크 점검 보고서

작성일: 2026-04-27  
참조 문서: `README.md`, `claude.md`, `PROJECT_ANALYSIS.md`  
점검 범위: 기능 구현 정합성, 런타임/데이터 안정성, 패키징/검증 흐름, 추가해야 할 회귀 테스트

## 1. 점검 요약

현재 로컬 프리플라이트와 정적 분석은 통과한다.

```powershell
python scripts/preflight_local.py --skip-payload-build
```

결과:
- payload manifest 검증 및 smoke import 성공
- optional dependency 전부 사용 가능
- `py_compile` 성공
- `unittest discover -s tests -v` 성공
- 총 146개 테스트 통과

repo-wide `pyright`도 현재 통과한다.

```powershell
pyright
```

결과:
- 0 errors
- `legacy_main.pyi`, DB mixin typing helper, Qt/test fake object typing 보강으로 기존 299 errors를 정리했다.

결론:
- 내부 copy debounce, DB restore 검증, FTS backfill, import/export metadata, payload hash 검증, app data 경로 통합, cleanup 경고, repo-wide pyright를 구현 및 테스트로 보강했다.
- 이 문서는 원래 리스크 목록과 구현 완료 기준을 함께 남기는 추적 문서로 유지한다.
- 아래 P1/P2/P3 항목의 "현재" 서술은 발견 당시 기준이며, 현재 구현 상태는 1.1과 1.2를 기준으로 한다.

## 1.1 구현 완료 요약

- `on_clipboard_change_impl()`은 기존 debounce timer를 먼저 중지한 뒤 privacy/internal copy 여부를 판단한다.
- DB 복원은 SQLite integrity/schema 검증, `pre_restore_*` 백업, 임시 파일 + atomic replace를 사용한다.
- FTS 최초 생성 및 과거 빈 FTS table 모두 기존 history row를 backfill한다.
- JSON import는 `items` list와 metadata 타입/범위를 검증하고, CSV import는 pinned/use_count를 복원한다.
- URL title cache는 256개/24시간 TTL/LRU 제한을 적용한다.
- payload manifest는 `payload_sha256`과 `payload_size`를 marshal load 전에 검증한다.
- source mode app data directory는 `smartclipboard_app` 기준으로 통합됐다.
- `max_history`/cleanup 영구 삭제 정책은 유지하되 설정 UI/README/claude에 명시했다.
- 검증: `python -m unittest discover -s tests`, `pyright`, `scripts/build_legacy_payload.py --smoke-import` 통과.

## 1.2 패키징/문서 정합성 반영

- `smartclipboard.spec`는 repo-wide `pyright` 0 errors와 payload size/SHA-256 검증 기준으로 주석을 갱신했다.
- 새 runtime 모듈(`smartclipboard_core.app_paths`, DB typing helper 등)은 기존 `collect_submodules` 범위에 포함되므로 추가 hidden import나 datas는 필요 없다.
- `.gitignore`는 SQLite rollback journal 파일을 추가로 제외한다.
- `README.md`, `claude.md`, `.gemini/GEMINI.md`, `PROJECT_ANALYSIS.md`, 레거시 README 보관본은 2026-04-27 기능 구현 완료 기준으로 정합성을 맞췄다.

## 2. 우선순위 높은 잠재 문제

### P1. 내부 복사 플래그와 debounce 타이머 순서 때문에 자기 재수집이 간헐적으로 발생할 수 있음

근거:
- `smartclipboard_app/features/clipboard/pipeline.py:10`
- `smartclipboard_app/features/clipboard/pipeline.py:11`
- `smartclipboard_app/features/clipboard/pipeline.py:15`
- `smartclipboard_app/features/clipboard/pipeline.py:22`

현재 `on_clipboard_change_impl()`은 `is_privacy_mode` 또는 `is_internal_copy`를 먼저 확인하고 바로 return 한다. 기존 `_clipboard_debounce_timer`를 중지하는 코드는 그 뒤에 있다.

가능한 시나리오:
1. 외부 복사 이벤트가 들어와 100ms debounce 타이머가 예약된다.
2. 타이머가 실행되기 전에 앱 내부 복사(`mark_internal_copy()` 후 `clipboard.setText()` 또는 `setMimeData()`)가 발생한다.
3. 내부 복사 이벤트는 `is_internal_copy` 때문에 return 하지만, 기존 debounce 타이머는 취소되지 않는다.
4. 남아 있던 타이머가 현재 clipboard를 처리하면서 내부 복사 내용을 다시 히스토리에 저장할 수 있다.

권장 보완:
- `on_clipboard_change_impl()` 시작 시점에 기존 debounce 타이머를 먼저 중지/삭제한 뒤 privacy/internal copy 여부를 판단한다.
- 또는 debounce 콜백이 예약 당시의 clipboard sequence/snapshot을 확인하도록 한다.
- 회귀 테스트 추가: 외부 이벤트로 타이머 예약 후 내부 복사 이벤트를 발생시키고, 이전 타이머가 처리되지 않는지 검증.

### P1. DB 복원은 선택한 파일을 검증하지 않고 현재 DB를 덮어씀

근거:
- `smartclipboard_app/legacy_main_src.py:818`
- `smartclipboard_app/legacy_main_src.py:826`
- `smartclipboard_app/legacy_main_src.py:836`

`restore_data()`는 선택된 파일에 대해 SQLite integrity/schema 검사를 하지 않고 `shutil.copy2(file_name, target_db_file)`를 수행한다. 잘못된 파일, 손상된 SQLite, 오래된/불완전한 스키마 파일을 선택하면 앱 재시작 후 DB 초기화나 주요 기능이 깨질 수 있다.

권장 보완:
- 복원 전에 별도 연결로 `PRAGMA integrity_check`를 실행한다.
- 필수 테이블/컬럼(`history`, `settings`, `deleted_history`, `collections`, `file_signature` 등)을 확인한다.
- 현재 DB를 `pre_restore_YYYYMMDD_HHMMSS.db`로 강제 백업한 뒤 원자적 replace를 수행한다.
- 복원 실패 시 기존 DB가 그대로 남도록 임시 파일 + atomic move 패턴을 사용한다.

추가 테스트:
- 손상된 파일을 선택했을 때 현재 DB가 유지되는지.
- 필수 스키마가 없는 SQLite 파일을 거부하는지.
- 정상 백업 파일은 복원 후 앱이 재시작 가능한지.

### P1. 기존 DB에서 FTS 인덱스가 처음 생성될 때 기존 history row가 인덱싱되지 않음

근거:
- `smartclipboard_core/db_parts/search/fts.py:23`
- `smartclipboard_core/db_parts/search/fts.py:29`
- `smartclipboard_core/db_parts/search/fts.py:53`

현재 `history_fts`가 없으면 virtual table과 trigger를 만든 뒤 `INSERT INTO history_fts(history_fts) VALUES('rebuild')`를 실행한다. 하지만 이 FTS table은 external-content table이 아니므로 기존 `history` row가 자동으로 backfill되지 않는다.

간단 재현 결과:
- 기존 `history` table에 row를 만든 뒤 `ClipboardDB`를 열면 `history_fts` row count가 `0`이었다.
- 검색 자체는 LIKE fallback으로 결과를 찾지만, FTS 인덱스는 비어 있다.
- `_last_search_used_fts`도 FTS 결과가 0건인 상황에서 True로 남을 수 있어 진단값이 애매해진다.

권장 보완:
- FTS table 신규 생성 시 명시적으로 backfill:
  - `INSERT INTO history_fts(rowid, content, tags, note, url_title) SELECT id, ... FROM history`
- 또는 FTS5 external-content table 구조로 바꾸고 rebuild를 정확히 사용한다.
- 회귀 테스트: FTS 도입 전 형태의 DB fixture를 열었을 때 기존 row가 FTS 검색으로 조회되는지 검증.

### P1. repo-wide pyright가 공식 명령처럼 문서화되어 있지만 발견 당시 실패함

근거:
- `README.md:176`
- `README.md:185`
- `claude.md:65`
- `pyrightconfig.json:3`
- `pyrightconfig.json:7`

문서상 `pyright` 실행을 안내하지만 발견 당시 repo-wide 실행은 299 errors로 실패했다. 문서에는 mixin 노이즈가 남아 있다고 적혀 있었지만, 실제 출력에는 다음처럼 더 넓은 범위의 문제가 포함됐다.

- `smartclipboard_app/bootstrap.py`: 동적 payload 모듈 `legacy_main`에서 `APP_DIR`, `logger` export를 인식하지 못함
- `smartclipboard_app/ui/main_window.py`: `legacy_main.MainWindow` export 인식 실패
- `smartclipboard_app/ui/dialogs/clipboard_actions.py`: `self.actions`가 Qt `actions()` 메서드와 이름 충돌
- `smartclipboard_app/ui/widgets/floating_mini_window.py`, `features/tray_hotkey/services.py`: Protocol이 실제 사용 속성(`statusBar`, `showMessage`)을 충분히 표현하지 못함
- `smartclipboard_core/db_parts/**`: mixin들이 `self.conn`, `self.lock`을 타입상 모름

권장 보완(완료):
- `legacy_main.pyi`로 payload 동적 export를 타입 검사기가 알 수 있게 했다.
- DB mixin typing helper를 정의해 `conn`, `lock`, `_add_item_locked` 등 공통 속성을 타입화했다.
- 테스트 fake object는 Protocol 또는 `typing.cast`로 정리했다.
- README/claude/spec 검증 문구는 repo-wide `pyright` 0 errors 기준으로 갱신했다.

## 3. 중간 우선순위 구현 리스크

### P2. `ClipboardActionsDialog.actions`가 Qt `QWidget.actions()`와 이름이 충돌함

근거:
- `smartclipboard_app/ui/dialogs/clipboard_actions.py:168`
- `smartclipboard_app/ui/dialogs/clipboard_actions.py:175`
- `smartclipboard_app/ui/dialogs/clipboard_actions.py:267`
- `smartclipboard_app/ui/dialogs/clipboard_actions.py:320`

`QWidget`에는 `actions()` 메서드가 있는데, 다이얼로그에서 `self.actions = []`로 같은 이름을 인스턴스 속성으로 덮어쓴다. 현재 기능은 동작하지만, Qt action API를 나중에 사용하거나 타입 검사/리팩토링을 할 때 충돌이 계속 발생한다.

권장 보완:
- `self.actions`를 `self.action_rows` 또는 `self._action_rows`로 변경.
- 관련 테스트는 `move_action`, `load_actions`, `toggle_action`, `delete_action` 경로 중심으로 유지.

### P2. 존재하지 않는 row에 대한 일부 DB 업데이트가 성공처럼 반환됨

확인 결과:
- `db.set_item_metadata(999999, tags="ghost")` -> `True`
- `db.update_url_title(999999, "ghost-title")` -> `True`
- `db.update_snippet(999999, "n", "c")` -> `True`
- `db.delete_snippet(999999)` -> `True`

근거:
- `smartclipboard_core/db_parts/history_ops.py:547`
- `smartclipboard_core/db_parts/history_ops.py:561`
- `smartclipboard_core/db_parts/catalog/tags.py:46`
- `smartclipboard_core/db_parts/automation/snippets.py:39`
- `smartclipboard_core/db_parts/automation/snippets.py:51`

일부 호출자는 사전 조회를 하므로 즉시 장애가 되지는 않는다. 하지만 다이얼로그/외부 API/향후 자동화 흐름에서는 실제 변경이 없는데 성공 UI를 보여줄 수 있다.

권장 보완:
- `UPDATE`/`DELETE` 계열은 `cursor.rowcount == 1` 기준으로 성공 여부를 반환한다.
- `_set_item_metadata_locked()`도 missing row를 False로 반환하도록 바꾸거나, caller가 사전 존재 확인을 강제한다.
- 회귀 테스트: 없는 snippet/history/vault/action id 업데이트가 False 또는 0을 반환하는지 검증.

### P2. JSON import metadata 타입과 범위 정규화가 부족함

근거:
- `smartclipboard_app/features/import_export/json_codec.py:60`
- `smartclipboard_app/features/import_export/json_codec.py:64`
- `smartclipboard_app/features/import_export/json_codec.py:128`
- `smartclipboard_app/features/import_export/manager.py:211`

`build_item_metadata()`는 `bookmark`, `pinned`, `pin_order`, `use_count` 등을 payload에서 그대로 가져온다. SQLite가 타입을 강하게 막지 않기 때문에 문자열, 음수, 과도한 숫자가 그대로 들어갈 수 있다.

또한 `data.get("items", [])`가 list인지 확인하지 않는다. `items`가 dict/string이면 의도하지 않은 skip/성공 결과가 나올 수 있다.

권장 보완:
- `items`는 list가 아니면 import 실패 처리.
- boolean 필드는 `0/1`로 정규화.
- `pin_order`, `use_count`는 음수 방지 및 int 변환.
- `tags`, `note` 길이 제한 또는 최소한 문자열 변환.
- 잘못된 metadata는 report warning에 누적.

### P2. CSV export는 고정/use_count 컬럼을 쓰지만 import는 복원하지 않음

근거:
- `smartclipboard_app/features/import_export/csv_codec.py:11`
- `smartclipboard_app/features/import_export/csv_codec.py:25`
- `smartclipboard_app/features/import_export/csv_codec.py:29`

CSV export는 `고정`, `사용횟수` 컬럼을 기록하지만 import는 content/type/timestamp만 사용한다. CSV가 migration 포맷이 아니라는 정책은 이해되지만, export된 컬럼이 import에서 무시되면 사용자는 round-trip을 기대할 수 있다.

권장 보완:
- 둘 중 하나를 선택해야 한다.
- 옵션 A: CSV import에서 `고정`, `사용횟수`까지 복원한다.
- 옵션 B: UI/report에 “CSV import는 metadata를 복원하지 않음”을 명확히 표시한다.

### P2. URL 제목 가져오기 보안은 강화되어 있지만 DNS TOCTOU와 cache 무제한 리스크가 남아 있음

근거:
- `smartclipboard_core/automation/network_guard.py:32`
- `smartclipboard_core/automation/network_guard.py:50`
- `smartclipboard_core/automation/fetch_title.py:55`
- `smartclipboard_core/automation/fetch_title.py:61`
- `smartclipboard_core/automation/manager.py:35`
- `smartclipboard_core/automation/manager.py:185`

현재는 요청 전 DNS resolve 결과가 global address인지 확인하고 redirect도 수동 처리한다. 그러나 `requests.get()` 내부에서 다시 DNS를 조회하므로 DNS rebinding/TOCTOU 가능성은 완전히 제거되지 않는다. 또한 `_title_cache`는 세션 동안 무제한 증가한다.

권장 보완:
- `_title_cache`에 TTL/LRU 상한을 둔다.
- 높은 보안 수준이 필요하면 검증된 IP로 연결하거나 requests adapter 레벨에서 resolve 결과를 고정하는 방식 검토.
- 네트워크 테스트는 이미 충분히 있으므로, cache 상한과 shutdown 후 late result 무시 테스트를 추가하면 좋다.

### P2. payload manifest가 frozen runtime에서 payload 자체 무결성을 검증하지 않음

근거:
- `smartclipboard_app/legacy_payload.py:21`
- `smartclipboard_app/legacy_payload.py:30`
- `smartclipboard_app/legacy_payload.py:53`
- `smartclipboard_app/legacy_main.py:59`
- `smartclipboard_app/legacy_main_payload.manifest.json:4`

manifest에는 `source_sha256`과 `payload_size`가 있지만 `payload_sha256`은 없다. 또한 frozen runtime에서는 `src_path` 검증을 건너뛰므로 같은 Python minor/implementation이면 payload와 manifest의 실제 결합을 강하게 검증하지 않는다.

권장 보완:
- manifest에 `payload_sha256` 추가.
- loader에서 marshal load 전에 payload hash를 검증.
- `payload_size`도 검증 대상에 포함.
- 테스트: payload 파일을 다른 payload로 바꿨을 때 source fallback 또는 명시 실패가 발생하는지 확인.

### P2. 앱 데이터 디렉터리 기본값이 UI 경로와 core 경로에서 다름

근거:
- `smartclipboard_app/legacy_main_src.py:163`
- `smartclipboard_app/legacy_main_src.py:172`
- `smartclipboard_app/legacy_main_src.py:190`
- `smartclipboard_app/legacy_main_src.py:383`
- `smartclipboard_app/legacy_main_src.py:384`
- `smartclipboard_core/db_parts/shared.py:7`
- `smartclipboard_core/database.py:31`

UI 런타임은 `legacy_main_src.APP_DIR`을 기준으로 `smartclipboard_app/clipboard_history_v6.db`를 사용한다. 반면 `smartclipboard_core.ClipboardDB()`를 직접 만들면 repo root의 `clipboard_history_v6.db`를 기본으로 사용한다.

현재 MainWindow는 명시적으로 `db_file=DB_FILE, app_dir=APP_DIR`를 넘기므로 즉시 문제는 아니다. 하지만 스크립트/외부 호출/향후 리팩토링에서 core DB를 직접 만들면 다른 DB 파일을 보게 된다.

권장 보완:
- 앱 데이터 경로 resolver를 단일 모듈로 통합한다.
- UI와 core가 같은 default를 쓰거나, core default를 제거하고 앱 계층에서 반드시 주입하게 한다.
- 문서에 source 실행 시 실제 DB 위치를 명시한다.

## 4. 정책 또는 UX 관점에서 추가 검토할 항목

### P3. `max_history` 감소와 주기적 cleanup은 휴지통을 거치지 않고 영구 삭제함

근거:
- `smartclipboard_app/ui/dialogs/settings.py:301`
- `smartclipboard_app/ui/dialogs/settings.py:303`
- `smartclipboard_core/db_parts/history_ops.py:364`
- `smartclipboard_core/db_parts/history_ops.py:379`
- `smartclipboard_core/db_parts/history_ops.py:406`

사용자가 “기록 전체 삭제”를 선택하면 휴지통으로 이동한다. 하지만 `max_history` 감소 또는 주기적 cleanup으로 오래된 row가 제거될 때는 `DELETE FROM history`로 바로 삭제된다.

이 동작이 의도라면 괜찮지만, 휴지통 기능이 있는 앱에서는 사용자가 “삭제 복구 가능”을 기대할 수 있다.

권장 보완:
- 설정 저장 시 max history 감소로 몇 개가 영구 삭제되는지 경고한다.
- 또는 cleanup 삭제분도 `deleted_history`로 이동하는 별도 정책을 검토한다.
- 최소한 자동 cleanup은 영구 삭제라는 점을 설정 UI/README에 명시한다.

### P3. 스니펫/규칙/액션/컬렉션 이름에 DB-level unique 제약이 없음

현재 앱 레벨에서 중복을 막는 경로는 있다. 하지만 DB 스키마에는 unique constraint가 없다. 단일 앱/단일 connection이면 큰 문제는 아니지만, import나 future batch 작업에서 중복이 들어오면 UI 중복/우선순위 혼란이 생길 수 있다.

권장 보완:
- 적어도 `collections.name`은 normalized name 기준 unique 정책을 DB 또는 별도 normalized column으로 강화.
- snippet shortcut도 비어 있지 않은 값에 대해 unique 검토.

### P3. `set_setting()`은 실패 여부를 caller가 알 수 없음

근거:
- `smartclipboard_core/db_parts/automation/snippets.py:78`
- `smartclipboard_core/db_parts/automation/snippets.py:81`

`set_setting()`은 실패 시 로그만 남기고 반환값이 없다. 설정 저장 UI는 대부분 성공으로 진행한다. 디스크 full/DB lock/권한 문제에서는 UI가 성공처럼 보일 수 있다.

권장 보완:
- `set_setting()`을 bool 반환으로 변경하되 공개 API 호환성을 고려한다.
- 당장 어렵다면 critical setting 저장 경로(`hotkeys`, `mini_window_enabled`, `theme`)에서는 저장 후 read-back 검증을 추가한다.

## 5. 추가하면 좋은 회귀 테스트 목록

우선순위 순서:

1. `test_internal_copy_event_cancels_pending_debounce`
   - 외부 clipboard 이벤트로 timer 예약 후 내부 copy 이벤트를 발생시킨다.
   - 내부 copy 내용이 history에 재수집되지 않아야 한다.

2. `test_legacy_db_rows_are_backfilled_into_fts_on_first_index_creation`
   - FTS가 없는 기존 DB에 history row를 넣고 `ClipboardDB`를 연다.
   - `history_fts`에 기존 row가 들어가고 FTS 검색으로 조회되어야 한다.

3. `test_restore_data_rejects_invalid_sqlite_without_overwriting_current_db`
   - 잘못된 `.db` 파일 복원 시 기존 DB 파일 hash가 유지되는지 검증한다.

4. `test_restore_data_rejects_missing_required_schema`
   - SQLite이지만 필수 테이블/컬럼이 없는 파일을 거부한다.

5. `test_metadata_update_missing_row_returns_false`
   - `set_item_metadata`, `update_url_title`, `update_snippet`, `delete_snippet` 등 missing id 경로를 검증한다.

6. `test_json_import_rejects_non_list_items_payload`
   - `items`가 list가 아니면 import 실패 또는 명시 warning 처리.

7. `test_json_import_normalizes_numeric_metadata`
   - `pinned`, `bookmark`, `pin_order`, `use_count`가 문자열/음수/None일 때 안전하게 정규화되는지 확인.

8. `test_payload_manifest_validates_payload_hash`
   - payload hash mismatch 시 payload mode가 그대로 실행되지 않는지 확인.

9. `test_title_cache_is_bounded`
   - 많은 URL 제목 fetch 후 cache 크기가 상한을 넘지 않는지 확인.

10. `test_csv_metadata_policy_is_explicit`
   - CSV import가 metadata를 복원한다면 복원 검증.
   - 복원하지 않는 정책이면 report warning 검증.

## 6. 수동 점검이 필요한 영역

자동 테스트는 offscreen Qt와 fake keyboard 중심이다. 아래는 실제 Windows 환경에서 별도 smoke test가 필요하다.

- `Ctrl+Shift+V`, `Alt+V`, `Ctrl+Shift+Z` 글로벌 핫키 등록/해제/충돌
- 트레이 아이콘 표시, 종료, 백그라운드 유지
- Windows Explorer에서 다중 파일 복사 후 FILE 히스토리 저장/복원
- Excel/브라우저/메신저 등 외부 앱으로 `Ctrl+Shift+Z` paste-last 동작
- PyInstaller exe에서 `LEGACY_IMPL_ACTIVE == "payload"` 상태 확인
- exe에서 payload/manifest 누락 시 fallback 또는 오류 동작 확인
- 시작 프로그램 등록 후 재부팅/로그인 시 `--minimized` 동작

## 7. 발견 당시 권장 실행 순서

아래 항목은 발견 당시 실행 계획이며, 현재는 1.1/1.2 범위로 구현 및 검증을 완료했다.

1. P1 항목 3개부터 수정
   - debounce timer 순서
   - DB restore 사전 검증/백업/atomic replace
   - FTS 기존 row backfill

2. 정적 분석 부채 축소
   - `ClipboardActionsDialog.actions` 이름 변경
   - `legacy_main.pyi` 또는 typed export shim 추가
   - DB mixin Protocol 정리

3. import/export 경계 강화
   - JSON payload shape/type 검증
   - metadata coercion
   - CSV metadata 정책 확정

4. payload manifest 강화
   - `payload_sha256` 추가
   - frozen runtime에서도 payload 파일 자체 검증

5. Windows 수동 smoke checklist를 릴리스 절차에 추가

## 8. 현재 상태 판단

현재 코드베이스는 README/claude에 적힌 핵심 안정화 계약과 이번 기능 구현 리뷰 후속 항목을 테스트로 보호한다. 특히 FILE clipboard, JSON migration, 보안 보관함 unlock 실패 처리, paste-last 최신순, pinned-first 정렬, payload fallback에 더해 debounce race, DB restore, FTS backfill, import metadata 정규화, payload hash mismatch, app directory resolver, cleanup warning까지 회귀 테스트가 추가됐다.

이번 작업에서 정리된 항목:

- 기존 사용자 DB를 업그레이드할 때의 FTS backfill
- clipboard 이벤트 타이밍 race
- 손상된 DB 복원
- repo-wide 정적 분석 게이트
- payload binary와 manifest의 결합 무결성

다음 기능 추가 전에는 `pyright`, `scripts/preflight_local.py`, payload smoke import, PyInstaller build를 같은 순서로 유지한다.

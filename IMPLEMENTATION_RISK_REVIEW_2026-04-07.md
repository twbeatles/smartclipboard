# SmartClipboard 구현 리스크 점검 메모

작성일: 2026-04-07

## 검토 기준

- 기준 문서: `claude.md`, `README.md`
- 점검 범위: `smartclipboard_app/`, `smartclipboard_core/`, `scripts/preflight_local.py`, `tests/`
- 실행 검증:
  - `python scripts/preflight_local.py --skip-payload-build` 통과
  - 문서에 적힌 대로 repo-wide `pyright`는 현 시점에서도 환경 의존성/known noise가 많아 기능 게이트로 쓰기 어렵고, 이번 메모는 런타임 동작과 코드 경로 기준으로 정리함

## 우선순위 높은 발견

### 1. 토스트 호출 인자 불일치로 런타임 예외가 발생할 수 있고, URL 제목 가져오기 이후 클립보드 모니터가 끊긴 상태로 남을 수 있음

- 근거:
  - `smartclipboard_app/legacy_main_src.py:1143`
  - `smartclipboard_app/legacy_main_src.py:1162`
  - `smartclipboard_app/legacy_main_src.py:1165`
  - `smartclipboard_app/ui/widgets/toast.py:91`
  - `smartclipboard_app/ui/widgets/toast.py:115`
- 문제:
  - `ToastNotification.show_toast(parent, message, duration=..., toast_type=...)` 시그니처인데, 일부 호출은 세 번째 인자에 본문 문자열을 넘기고 있음
  - 이 경우 문자열이 `duration`으로 들어가고, 내부 `QTimer.singleShot(duration, ...)`에서 예외가 날 가능성이 높음
  - 특히 `on_action_completed()`는 `clipboard.dataChanged.disconnect(...)` 후 토스트를 띄우기 때문에, 여기서 예외가 나면 `connect(...)`가 다시 호출되지 않아 이후 클립보드 수집이 멈출 수 있음
- 영향:
  - URL 제목 가져오기 성공 직후 앱이 조용히 오동작할 수 있음
  - 모니터링 일시정지/재개 토스트도 같은 방식으로 깨질 수 있음
- 권장 조치:
  - 토스트 호출을 전부 키워드 인자로 통일
  - `on_action_completed()`에서는 `disconnect/connect`를 `try/finally`로 감싸서 예외가 나도 재연결되게 변경
- 추천 테스트:
  - URL title fetch 완료 후 `clipboard.dataChanged`가 반드시 재연결되는지
  - `toggle_monitoring_pause()` 호출 시 예외 없이 토스트가 표시되는지

### 2. `Ctrl+Shift+Z`의 "마지막 항목 붙여넣기"가 실제로는 "가장 위에 보이는 항목 붙여넣기"에 가까움

- 근거:
  - `README.md`의 글로벌 핫키 설명: 마지막 항목 즉시 붙여넣기
  - `smartclipboard_app/ui/mainwindow_parts/tray_hotkey_ops.py:141`
  - `smartclipboard_app/ui/mainwindow_parts/tray_hotkey_ops.py:145`
  - `smartclipboard_core/db_parts/shared.py:34`
- 문제:
  - `paste_last_item_slot_impl()`는 `self.db.get_items("", "전체")[0]`을 사용함
  - `get_items()` 기본 정렬은 `pinned DESC, pin_order ASC, timestamp DESC`라서, 고정 항목이 하나라도 있으면 "가장 최근 복사"가 아니라 "가장 위의 고정 항목"이 먼저 선택됨
- 영향:
  - 문서와 실제 동작이 어긋남
  - 사용자는 "마지막 복사"를 기대하지만 전혀 다른 항목이 붙을 수 있음
- 권장 조치:
  - "paste last" 전용 조회 함수를 분리해서 `timestamp DESC, id DESC` 기준 최근 항목을 선택
  - 고정 정책과 최근 항목 정책을 분리
- 추천 테스트:
  - 최신 일반 항목 + 오래된 고정 항목이 동시에 있을 때 hotkey가 최신 일반 항목을 붙이는지

### 3. 사용자 정렬을 내림차순으로 바꾸면 "고정 항목 항상 상단" 규칙이 깨질 수 있음

- 근거:
  - `smartclipboard_app/ui/mainwindow_parts/table_ops.py:95`
  - `smartclipboard_app/ui/mainwindow_parts/table_ops.py:101`
  - `smartclipboard_app/ui/mainwindow_parts/table_ops.py:102`
- 문제:
  - 정렬 키가 `(not pinned, value)`인데, 내림차순에서는 `reverse=True`가 전체 튜플에 적용됨
  - 결과적으로 `True > False` 때문에 비고정 항목이 고정 항목보다 위로 올라갈 수 있음
- 영향:
  - README/claude 문서에서 강조한 pinned-first 정책이 정렬에 따라 깨짐
  - 드래그/핀 순서 인지 모델도 같이 흔들림
- 권장 조치:
  - pinned/unpinned를 먼저 분리한 뒤 각 그룹 내부만 정렬
  - 또는 정렬 키를 `pinned_rank`와 `sort_value`로 분리하고 reverse를 값 부분에만 적용
- 추천 테스트:
  - 고정/비고정 혼합 상태에서 각 컬럼을 오름/내림차순으로 정렬해도 고정 항목이 항상 맨 위에 남는지

### 4. 컬렉션 삭제 후 휴지통 복원 시, 삭제된 컬렉션 ID가 그대로 살아나면서 orphan 상태가 생길 수 있음

- 근거:
  - `smartclipboard_core/db_parts/tags_collections.py:166`
  - `smartclipboard_core/db_parts/tags_collections.py:172`
  - `smartclipboard_core/db_parts/vault_trash.py:83`
  - `smartclipboard_core/db_parts/vault_trash.py:89`
  - `smartclipboard_core/db_parts/vault_trash.py:97`
- 문제:
  - 컬렉션 삭제 시 `history.collection_id`만 `NULL`로 만들고 `deleted_history.collection_id`는 그대로 둠
  - 이후 휴지통 복원은 `deleted_history.collection_id`를 그대로 `history`에 재삽입함
- 영향:
  - 존재하지 않는 컬렉션을 가리키는 히스토리 행이 생길 수 있음
  - 이런 항목은 "미분류"에도 안 나오고, 컬렉션 필터에서도 접근성이 떨어짐
- 권장 조치:
  - 컬렉션 삭제 시 `deleted_history`도 같이 `NULL` 처리
  - 복원 시점에도 `collection_id` 존재 여부를 검사해서 없으면 `NULL`로 복원
  - 가능하면 FK 제약 또는 최소한 앱 레벨 검증 추가
- 추천 테스트:
  - 컬렉션 연결 항목을 휴지통으로 보낸 뒤 컬렉션 삭제 후 복원했을 때 `collection_id`가 `NULL`로 돌아오는지

### 5. 보안 보관함에서 마스터 비밀번호를 바꾼 직후, 열린 다이얼로그의 복사 버튼이 이전 암호문을 잡고 있어 즉시 실패할 수 있음

- 근거:
  - `smartclipboard_app/ui/dialogs/secure_vault.py:158`
  - `smartclipboard_app/ui/dialogs/secure_vault.py:179`
  - `smartclipboard_app/ui/dialogs/secure_vault.py:201`
  - `smartclipboard_app/ui/dialogs/secure_vault.py:234`
  - `smartclipboard_app/ui/dialogs/secure_vault.py:270`
- 문제:
  - `load_items()`에서 각 복사 버튼이 `encrypted` 값을 람다 기본값으로 캡처함
  - `change_master_password()`는 DB 안의 vault row를 재암호화하지만, 성공 후 `load_items()`를 다시 호출하지 않음
- 영향:
  - 비밀번호 변경 직후 같은 다이얼로그에서 "복사"를 누르면 새 키로 이전 암호문을 복호화하려다가 실패할 수 있음
  - 사용자 입장에서는 비밀번호 변경 성공 메시지를 봤는데 바로 다음 동작이 실패하는 형태
- 권장 조치:
  - 비밀번호 변경 성공 후 `load_items()` 재호출
  - 더 안전하게는 버튼 콜백에서 `encrypted`를 캡처하지 말고 `vid`만 받아 DB에서 최신 row를 다시 조회
- 추천 테스트:
  - 비밀번호 변경 직후 다이얼로그를 닫지 않고 기존 행의 복사 버튼을 눌렀을 때 정상 복호화되는지

## 중간 우선순위 발견

### 6. URL 제목 가져오기 worker를 종료 시 정리하지 않아 종료/복원 타이밍에 닫힌 DB로 결과가 들어올 수 있음

- 근거:
  - `smartclipboard_core/actions.py:50`
  - `smartclipboard_core/actions.py:130`
  - `smartclipboard_core/actions.py:138`
  - `smartclipboard_app/ui/mainwindow_parts/status_lifecycle_ops.py:93`
  - `smartclipboard_app/ui/mainwindow_parts/status_lifecycle_ops.py:124`
- 문제:
  - 액션 매니저는 글로벌 `QThreadPool`에 worker를 넣지만 종료 시 `waitForDone()` 또는 result signal 차단이 없음
  - 앱 종료/복원 경로에서는 DB를 먼저 닫음
- 영향:
  - 종료 직전이나 복원 직전 비동기 worker가 끝나면 닫힌 `self.db`로 `update_url_title()`을 시도할 수 있음
  - 사용자에게는 간헐적 종료 로그/경고나 title cache 누락으로 보일 가능성이 큼
- 권장 조치:
  - 종료 전에 `action_manager.threadpool.waitForDone(...)` 또는 종료 플래그를 두고 결과 무시
  - `on_action_completed`/`_handle_title_result`에서 DB 생존 여부 확인

### 7. `legacy_main_src.py`의 import-time 로깅 설정이 반복 import/폴백 시 파일 핸들 경고를 만들 수 있음

- 근거:
  - `smartclipboard_app/legacy_main_src.py:167`
  - `smartclipboard_app/legacy_main_src.py:170`
  - `smartclipboard_app/legacy_main_src.py:174`
  - `tests/test_payload_sync.py` 실행 시 `ResourceWarning: unclosed file` 관찰
- 문제:
  - `logging.basicConfig()` 호출 전에 `RotatingFileHandler(...)`를 바로 생성하고 있음
  - 이미 로깅이 구성된 프로세스에서 이 모듈이 재import되면 handler 객체만 생성되고 닫히지 않을 수 있음
- 영향:
  - 테스트/툴링/폴백 import 상황에서 파일 핸들 누수와 경고 발생
  - 장기적으로는 payload 폴백이나 재로딩 경로를 불안정하게 만들 수 있음
- 권장 조치:
  - root logger에 handler가 없을 때만 `RotatingFileHandler`를 생성
  - 또는 별도 `configure_logging()` 함수로 lazy-init

## 추가하면 좋은 보완 포인트

### A. 회귀 테스트를 바로 추가할 가치가 큰 항목

- 토스트 호출 시그니처 오용 검출 테스트
- `paste_last_item()`이 pinned 항목이 아니라 최신 항목을 선택하는지 검증
- 내림차순 정렬에서도 pinned-first가 유지되는지 검증
- 컬렉션 삭제 후 휴지통 복원 시 orphan `collection_id`가 생기지 않는지 검증
- 보안 보관함 비밀번호 변경 직후 copy 버튼이 계속 동작하는지 검증

### B. 정책을 한 군데로 더 모으면 좋은 항목

- `clipboard.setText()`/`setPixmap()` 경로는 `mark_internal_copy()`를 통하는 규칙을 더 강하게 통일
- 종료 경로에서 창 geometry 저장도 `closeEvent()`에만 의존하지 말고 `quit_app()`에서도 같이 처리
- `collection_id`는 앱 레벨 검증만으로 두지 말고 가능한 한 일관성 체크 경로를 추가

## 총평

- 문서 기준의 주요 기능은 대체로 구현되어 있고, 로컬 프리플라이트도 통과함
- 다만 "문서상 기능 존재"와 "실제 오동작 없이 안전하게 끝까지 수행" 사이의 간극이 몇 군데 남아 있음
- 특히 토스트 호출 인자, paste-last semantics, pinned-first 정렬, 컬렉션 삭제/복원 무결성은 우선적으로 보완하는 편이 좋음

# SmartClipboard 기능 구현 점검 보고서

작성일: 2026-04-15

> 참고: 이 문서는 2026-04-15 시점의 기능 리스크 스냅샷입니다. 후속 구현 반영 결과는 `FUNCTIONAL_REVIEW_2026-04-16.md`를 함께 확인하세요.

## 검토 범위

- 기준 문서: `README.md`, `claude.md`
- 주요 검토 대상: `smartclipboard_core/`, `smartclipboard_app/`, `tests/`
- 실행 검증: `python scripts/preflight_local.py --skip-payload-build`
- 검증 결과: 프리플라이트 통과, `unittest` 115개 모두 통과

## 후속 구현 상태

이 문서는 2026-04-15 시점의 기능 리스크 스냅샷입니다. 이후 같은 날짜의 후속 구현에서 아래 6개 항목은 코드와 테스트에 반영되었습니다.

- 우클릭 컨텍스트 메뉴 selection 동기화
- `항상 위 고정` 초기 체크 상태 정합성
- `설정 초기화`의 핵심 설정 범위 재정의
- 주기 cleanup 후 UI refresh/dirty 처리
- Google 검색 URL helper 공통화
- 복원 실패 후 런타임 DB 경로 유지

최신 구조 기준 참고 문서:
- `README.md`
- `claude.md`
- `.gemini/GEMINI.md`

## 총평

현재 프로젝트는 문서와 테스트가 잘 정리되어 있고, 핵심 회귀 범위도 넓은 편입니다. 다만 아래 항목들은 "현재 테스트는 통과하지만 실제 사용 흐름에서는 기능적으로 문제를 만들 수 있는 지점"입니다. 특히 컨텍스트 메뉴 동작, 설정 초기화 의미, 주기 정리 후 UI 동기화는 사용자 체감 이슈로 이어질 가능성이 높습니다.

## 주요 발견사항

### 1. `우클릭 컨텍스트 메뉴`가 클릭한 행이 아니라 기존 선택 행에 작동할 수 있음

심각도: 높음

근거:
- `smartclipboard_app/ui/mainwindow_parts/ui_init_sections.py:151-152`
- `smartclipboard_app/ui/mainwindow_parts/menu_ops.py:179-260`

문제:
- 테이블은 `customContextMenuRequested`로 메뉴만 띄우고, 우클릭한 행을 선택 상태로 동기화하지 않습니다.
- 그런데 실제 액션은 `itemAt(pos)`로 존재만 확인한 뒤 `self.get_selected_id()`와 `selectionModel().selectedRows()`를 사용합니다.
- 그 결과 사용자가 A행을 선택해 둔 상태에서 B행을 우클릭하면, 메뉴는 B행 위에서 열리지만 복사/삭제/링크 열기/컬렉션 이동은 A행 또는 기존 다중 선택에 적용될 수 있습니다.

영향:
- 잘못된 항목 삭제
- 잘못된 링크 열기
- 다중 선택 상태에서 의도하지 않은 대량 이동/삭제

권장 대응:
- 컨텍스트 메뉴를 열기 전에 `itemAt(pos)` 기준 행을 명시적으로 선택하도록 수정
- 다중 선택을 유지할지, 우클릭 행으로 selection을 교체할지 정책을 명확히 결정

추가 테스트 권장:
- "다른 행을 우클릭했을 때 해당 행 기준으로 컨텍스트 메뉴 액션이 실행되는지" UI 테스트 추가

### 2. `항상 위 고정` 메뉴의 초기 체크 상태와 실제 창 상태가 불일치함

심각도: 높음

근거:
- `smartclipboard_app/legacy_main_src.py:577-578`
- `smartclipboard_app/legacy_main_src.py:611`
- `smartclipboard_app/ui/mainwindow_parts/menu_ops.py:98-101`

문제:
- 내부 상태 `self.always_on_top`는 시작 시 `False`입니다.
- 하지만 메뉴 액션 `self.action_ontop`은 시작 시 `setChecked(True)`로 켜져 있습니다.
- 이어서 `update_always_on_top()`는 `False` 기준으로 실행되므로, UI는 켜짐처럼 보이지만 실제 창은 always-on-top이 아닙니다.

영향:
- 사용자는 옵션이 이미 적용된 것으로 오해합니다.
- 첫 클릭은 "해제"처럼 보이지만 실제 상태 변화가 없어, 두 번째 클릭을 해야 비로소 켜지는 역전 UX가 생깁니다.

권장 대응:
- 액션 체크 상태를 `self.always_on_top`와 동일하게 초기화
- 가능하면 이 값도 설정으로 저장/복원해 재시작 후 일관성 유지

추가 테스트 권장:
- 초기화 직후 `action_ontop.isChecked()`와 내부 `always_on_top` 플래그/윈도우 플래그가 일치하는지 검증

### 3. `설정 초기화`가 "모든 설정 초기화"라고 안내하지만 실제로는 일부만 초기화함

심각도: 중간

근거:
- `smartclipboard_app/legacy_main_src.py:1358-1369`

문제:
- 확인 문구는 "모든 설정을 기본값으로 되돌리시겠습니까?"라고 되어 있습니다.
- 실제 코드는 `theme`와 사용 흔적이 불명확한 `opacity`만 초기화합니다.
- `max_history`, `mini_window_enabled`, `hotkeys`, `log_level`, 자동 실행, 기타 사용자 설정은 남아 있습니다.

영향:
- 사용자가 문제 해결을 위해 "설정 초기화"를 눌러도 기대한 복구가 일어나지 않을 수 있습니다.
- 지원/디버깅 과정에서 "초기화했는데 그대로"라는 혼선을 만들 수 있습니다.

권장 대응:
- 문구를 실제 동작에 맞게 축소하거나
- 정말 전체 설정을 초기화하도록 범위를 넓혀야 합니다.

추가 테스트 권장:
- 설정 초기화 후 어떤 key가 기본값으로 되돌아가는지 명시적으로 검증하는 테스트 추가

### 4. 주기 정리 후 UI 갱신 조건이 너무 좁아서 실제 삭제가 일어나도 화면/상태바가 stale 상태로 남을 수 있음

심각도: 중간

근거:
- `smartclipboard_app/ui/mainwindow_parts/status_lifecycle_ops.py:83-90`
- `smartclipboard_core/db_parts/history_ops.py:364-425`

문제:
- `run_periodic_cleanup_impl()`은 `expired_count > 0`일 때만 `self.load_data()`를 호출합니다.
- 하지만 `self.db.cleanup()`은 임시 항목 만료 외에도 다음 작업을 수행합니다.
- 오래된 이미지 정리
- `max_history` 초과 일반 히스토리 정리
- 주기적 VACUUM
- 즉, 실제로 현재 목록에서 행이 삭제돼도 `expired_count == 0`이면 열린 화면은 그대로 유지될 수 있습니다.

영향:
- 화면에는 남아 있는데 DB에는 없는 항목이 보일 수 있음
- 상태바 개수와 실제 DB 상태가 어긋날 수 있음
- 이어지는 선택/복사 동작에서 `get_content()`가 `None`이 되는 어색한 흐름 가능

권장 대응:
- `cleanup()`이 실제 삭제 건수를 반환하도록 바꾸고, 삭제가 하나라도 있었으면 `load_data()`/`update_status_bar()`를 실행
- 최소한 주기 정리 후에는 상태바는 항상 갱신하도록 변경

추가 테스트 권장:
- 주기 정리로 `max_history` 초과 항목이 삭제된 경우에도 열린 창의 목록이 즉시 갱신되는지 확인

### 5. 링크 컨텍스트 메뉴의 `Google에서 검색` 경로만 URL 인코딩이 빠져 있음

심각도: 중간

근거:
- `smartclipboard_app/ui/mainwindow_parts/menu_ops.py:215-216`
- 비교 경로: `smartclipboard_app/legacy_main_src.py:1445-1450`

문제:
- 일반 검색 버튼 경로는 `quote(text)`로 URL 인코딩을 적용합니다.
- 그러나 링크 컨텍스트 메뉴의 Google 검색은 `https://www.google.com/search?q={url}` 형태로 원문을 그대로 붙입니다.

영향:
- URL에 `&`, `?`, 공백, 한글이 포함된 경우 검색어가 잘리거나 의도와 다르게 파싱될 수 있습니다.
- 문서에 적힌 "Google 검색 URL 인코딩 추가"와 실제 우회 경로가 어긋납니다.

권장 대응:
- 컨텍스트 메뉴 경로도 동일하게 `quote(url)`를 사용
- 가능하면 검색 URL 생성 로직을 한 곳으로 공통화

추가 테스트 권장:
- 쿼리스트링과 한글이 섞인 링크에 대해 컨텍스트 메뉴 검색 URL이 올바르게 인코딩되는지 검증

### 6. `데이터 복원` 실패 후 DB 재초기화 시 런타임 DB 경로를 잃어버릴 수 있음

심각도: 중간

근거:
- `smartclipboard_app/legacy_main_src.py:819-830`

문제:
- 복원 시 실제 대상 DB 파일은 `getattr(self.db, "db_file", DB_FILE)`로 잘 가져옵니다.
- 하지만 예외가 나면 `self.db = ClipboardDB()`로 재생성하여 기본 경로 DB를 다시 열어 버립니다.
- 즉, 커스텀 DB 경로, 테스트 경로, 포터블 경로를 쓰고 있었다면 실패 이후 조용히 기본 DB로 전환될 수 있습니다.

영향:
- 실패 복구 이후 사용자가 다른 DB를 보고 있다고 오해할 수 있음
- 디버깅/복구 과정에서 데이터 위치 혼선 발생

권장 대응:
- 예외 복구 시에도 기존 `db_file`, `app_dir`를 그대로 넘겨 재초기화
- 복원 성공 시 "재시작합니다" 대신 실제 재시작 여부를 명확히 하거나, 문구를 "종료합니다"로 수정

추가 테스트 권장:
- custom `db_file` 환경에서 복원 실패 후에도 동일 경로로 DB가 재연결되는지 검증

## 추가 구현 권장 사항

### 1. 설정/상태의 저장 정책을 문서와 더 맞출 필요가 있음

- `always_on_top`, `privacy_mode`, `monitoring_pause` 중 어떤 값이 세션 간 유지되는지 정책을 정리하면 사용자 혼란이 줄어듭니다.
- 특히 `always_on_top`은 현재 메뉴 상태 이슈와 맞물려 저장/복원 정책이 있으면 자연스럽게 정리됩니다.

### 2. 복원/백업 UX를 조금 더 분명하게 만들 필요가 있음

- 복원 성공 후 자동 재시작을 실제로 수행하거나, 현재처럼 종료만 한다면 안내 문구를 수정하는 것이 좋습니다.
- 실패 시 어떤 DB 경로로 복구했는지 사용자에게 보여주면 문제 추적이 쉬워집니다.

### 3. 회귀 테스트는 강하지만, `실사용 UX 계약` 테스트가 더 필요함

- 우클릭 selection 동기화
- 설정 초기화 범위
- 주기 cleanup 후 열린 화면 갱신
- 메뉴 기반 Google 검색 인코딩
- 복원 실패 후 runtime DB 경로 유지

## 우선순위 제안

1. 컨텍스트 메뉴 selection 동기화 수정
2. always-on-top 초기 상태 불일치 수정
3. 주기 cleanup 후 UI refresh 조건 보강
4. 설정 초기화 범위/문구 정리
5. 복원 실패 시 runtime DB 경로 유지
6. Google 검색 URL 생성 로직 공통화

## 메모

이번 점검은 "기능 구현 리스크" 중심이라 보안/성능/배포 항목은 보조적으로만 봤습니다. 현재 테스트 115개가 모두 통과하므로, 위 항목들은 주로 테스트 공백 또는 UX-기능 불일치 영역으로 보는 것이 맞습니다.

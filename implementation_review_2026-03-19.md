# SmartClipboard 기능 구현 점검 리포트 (2026-03-19)

## 구현 반영 상태 업데이트 (2026-03-19)

- 1차 개선 계획의 범위였던 5건은 코드와 테스트에 반영 완료
  - 스니펫 저장 `datetime` 런타임 오류 수정
  - 동일 비이미지 텍스트 재복사 시 기존 row 갱신 + 메타데이터 보존
  - 보안 보관함/스니펫/URL 복사 경로의 `is_internal_copy` 공통 처리
  - pinned drag-drop helper의 `Qt` 참조 누락 수정
  - JSON `IMAGE` export/import round-trip(`image_data_b64`) 추가
- 후속 검증 결과
  - `python -m unittest discover -s tests -v`: 53개 테스트 통과
  - `python scripts/preflight_local.py --skip-payload-build`: 통과
  - touched files 기준 `pyright`: 0 오류
  - repo-wide `pyright`: `smartclipboard_core/db_parts/*.py` mixin attribute typing 노이즈가 남아 있어 비게이트 상태
- 이번 사이클에서 의도적으로 남긴 항목
  - 스니펫 단축키 UI/실행 경로
  - 휴지통 선택 항목 영구 삭제
  - 핫키 충돌 감지/경고 UI
  - repo-wide `pyright` 정리

## 기준 문서

- `README.md`
- `claude.md`

## 이번 점검에서 실제로 확인한 것

- `python scripts/preflight_local.py --skip-payload-build`: 통과
- `python -m unittest discover -s tests -v`: 46개 테스트 통과
- `pyright`: 실패, 총 208개 오류
- 수동 재현 스크립트로 아래 항목들을 추가 확인
  - `db.add_snippet(...)` 호출 시 `NameError: name 'datetime' is not defined`
  - 동일 텍스트를 다시 복사하면 기존 메타데이터가 사라짐
  - 이미지 1건만 있는 DB를 JSON export 하면 `count=0`, `items=[]`
  - 보관함 복사/스니펫 사용 후에도 부모 창의 `is_internal_copy`는 `False`

## 1. 확인된 구현 결함

### 1-1. 스니펫 신규 저장이 현재 런타임에서 바로 깨집니다

- 근거 코드
  - `smartclipboard_core/db_parts/rules_snippets_actions.py:1-12`
  - `smartclipboard_core/db_parts/rules_snippets_actions.py:11`에서 `datetime.datetime.now()`를 쓰지만 `datetime` import가 없습니다.
- 실제 확인
  - `ClipboardDB().add_snippet("name", "content")` 재현 시 `NameError: name 'datetime' is not defined`
- 영향
  - `README.md:43-47`의 스니펫 기능 중 "새 스니펫 저장"이 실패합니다.
  - 현재 테스트는 스니펫 "사용" 시그니처만 보고 있어서 생성 경로 결함을 못 잡고 있습니다.
- 우선 조치
  - `import datetime` 추가
  - `add_snippet` 성공 경로 테스트 추가

### 1-2. 같은 텍스트를 다시 복사하면 메모/태그/북마크/사용횟수/컬렉션이 유실됩니다

- 근거 코드
  - `smartclipboard_core/db_parts/history_ops.py:14-18`
  - 비이미지 항목은 동일 `content`를 찾으면 기존 row를 `DELETE`한 뒤 새 row를 `INSERT`합니다.
- 실제 확인
  - 메모, 태그, 북마크, 사용횟수를 넣은 항목을 같은 내용으로 다시 `add_item`하면 새 row에는 메타데이터가 비어 있었습니다.
  - 재현 결과: `row= (2, '', '', 0, 0)`
- 영향
  - `README.md:17-21`에서 강조하는 태그/북마크/컬렉션/메모 기능이 "재복사" 한 번으로 조용히 사라질 수 있습니다.
  - 사용 빈도 통계도 왜곡됩니다.
- 우선 조치
  - 기존 row 삭제 대신 `timestamp/use_count` 갱신 또는 메타데이터 merge 방식으로 변경
  - "중복 텍스트 재복사 시 메타데이터 보존" 회귀 테스트 추가

### 1-3. 보안 보관함 복사와 스니펫 사용이 내부 복사로 처리되지 않아 일반 히스토리에 재수집될 수 있습니다

- 근거 코드
  - `smartclipboard_app/ui/dialogs/secure_vault.py:196-204`
  - `smartclipboard_app/ui/dialogs/snippets.py:186-199`
  - 반면 정상 우회 예시는 `smartclipboard_app/ui/widgets/floating_mini_window.py:209-210`에 있습니다.
- 실제 확인
  - 보관함 `copy_item()` 호출 후 부모 창 `is_internal_copy=False`
  - 스니펫 `use_snippet()` 호출 후 부모 창 `is_internal_copy=False`
- 영향
  - 보안 보관함에서 꺼낸 민감 정보가 일반 클립보드 히스토리에 다시 저장될 수 있습니다.
  - 스니펫도 원치 않는 중복 히스토리를 만들 수 있습니다.
- 우선 조치
  - 클립보드 쓰기 전에 공통 helper로 `is_internal_copy=True`를 세팅
  - 보관함/스니펫/컨텍스트 메뉴 복사 경로를 같은 helper로 통합
  - "보관함 복사 시 일반 히스토리에 재수집되지 않음" 테스트 추가

### 1-4. 고정 항목 드래그 정렬 경로에 `Qt` 미정의 참조가 있습니다

- 근거 코드
  - `smartclipboard_app/ui/mainwindow_parts/ui_dragdrop_ops.py:5`
  - 같은 파일 `:77`, `:84`, `:93`에서 `Qt.ItemDataRole.UserRole` 사용
  - 하지만 `Qt` import가 없습니다.
- 영향
  - `README.md:17`의 "고정 및 드래그 정렬 기능"이 실제 드롭 경로에서 `NameError`를 낼 가능성이 높습니다.
  - 현재 테스트 범위에는 드래그 정렬 실동작 회귀가 없습니다.
- 우선 조치
  - `from PyQt6.QtCore import QEvent, QTimer, Qt`로 수정
  - 핀 순서 드래그앤드롭 UI 회귀 테스트 추가

### 1-5. JSON 내보내기/가져오기가 이미지 히스토리를 보존하지 못합니다

- 근거 코드
  - `smartclipboard_app/managers/export_import.py:55-60`
  - `ptype == "IMAGE"`면 export에서 바로 `continue`
  - `smartclipboard_app/managers/export_import.py:187-195`
  - import는 `content`가 없으면 skip하고, `image_data`를 읽지 않습니다.
- 실제 확인
  - 이미지 1건만 있는 DB를 `export_json(..., include_metadata=True)` 했더니 `count=0`, `items=[]`
- 영향
  - `README.md:49-53`의 마이그레이션/백업 기대치와 다르게, 이미지 히스토리는 JSON 기반 이전 시 전부 빠집니다.
  - 사용자는 "백업은 됐다"고 생각하지만 복원 후 이미지가 사라질 수 있습니다.
- 우선 조치
  - JSON에 이미지 BLOB를 base64로 저장하는 경로 추가
  - import 시 `image_data` 복원 지원
  - "이미지 포함 export/import round-trip" 테스트 추가

## 2. 문서 대비 기능 공백 또는 미구현 항목

### 2-1. 휴지통의 "선택 항목 영구 삭제"가 없습니다

- 문서 기준
  - `README.md:37-41`
  - "원클릭 복원 및 영구 삭제", "다중 선택 지원"이 적혀 있습니다.
- 실제 구현
  - `smartclipboard_app/ui/dialogs/trash_dialog.py:137-140`에는 `복원`, `휴지통 비우기`만 있습니다.
  - `smartclipboard_app/ui/dialogs/trash_dialog.py:180-207`은 선택 복원만 있고, 선택 영구 삭제는 없습니다.
- 영향
  - 일부 항목만 즉시 폐기하려는 사용 흐름이 막혀 있습니다.
- 권장
  - `delete_selected()` 추가
  - 다중 선택 영구 삭제 확인 다이얼로그 및 테스트 추가

### 2-2. 스니펫 단축키 할당 기능이 UI/동작 모두 비어 있습니다

- 문서 기준
  - `README.md:43-47`
  - "단축키 할당 가능"
- 실제 구현
  - `smartclipboard_app/ui/dialogs/snippets.py:70-85`
  - 저장 시 `shortcut`을 항상 빈 문자열 `""`로 넘깁니다.
  - 입력 UI도 없고 등록/실행 경로도 없습니다.
- 영향
  - 문서상 제공 기능인데 실제 사용자는 설정할 방법이 없습니다.
- 권장
  - 스니펫 생성/수정 다이얼로그에 shortcut 입력 추가
  - 전역 핫키 또는 앱 내부 shortcut 바인딩 설계 필요

### 2-3. 핫키 충돌 감지/경고는 현재 구현돼 있지 않습니다

- 문서 기준
  - `README.md:266-269`
  - "충돌 핫키 감지 및 경고"
- 실제 구현
  - `smartclipboard_app/ui/dialogs/hotkeys.py:111-120`은 값 저장 후 부모에게 재등록만 요청합니다.
  - `smartclipboard_app/ui/mainwindow_parts/tray_hotkey_ops.py:27-47`은 `keyboard.add_hotkey(...)`를 바로 호출하고, 실패 시 로그 경고만 남깁니다.
- 영향
  - 같은 키를 중복 저장하거나 OS/다른 앱과 충돌해도 사용자에게 명확한 사전 경고가 없습니다.
- 권장
  - 저장 전에 중복 키 자체 검증
  - 등록 실패 시 어떤 키가 왜 실패했는지 UI 메시지 제공

### 2-4. 보안 보관함의 "AES-256" 표기는 구현과 다시 맞춰봐야 합니다

- 문서 기준
  - `README.md:23-27`
- 실제 구현 근거
  - `smartclipboard_app/managers/secure_vault.py:15-18`
  - 현재 구현은 `cryptography.fernet.Fernet` 기반입니다.
- 판단
  - 현재 문구는 "실제 적용 알고리즘/보안 명세"와 정확히 일치하는지 재검토가 필요합니다.
- 권장
  - 문서 문구를 구현에 맞게 정정하거나, 명시한 보안 스펙에 맞게 구현을 조정

## 3. 품질/검증 체계에서 추가로 보이는 리스크

### 3-1. `pyright`가 현재 사실상 게이트 역할을 못 하고 있습니다

- 문서 기준
  - `claude.md:24`
  - `claude.md:35-40`
  - `README.md:122-130`, `README.md:150-155`
- 실제 상태
  - 2026-03-19 기준 `pyright`는 208개 오류로 실패했습니다.
  - 대표 범주
    - 동적 export/payload 로더로 인한 import symbol 오류
    - mixin 속성 타입 미정의 (`self.conn`, `self.lock`)
    - 실제 런타임 결함 신호인 undefined name (`datetime`, `Qt`)도 함께 섞여 있음
- 영향
  - "정적 분석을 필수 검증으로 본다"는 문서 기준과 실제 운영 상태가 다릅니다.
  - 노이즈가 너무 많아서 진짜 문제를 조기에 못 잡습니다.
- 권장
  - mixin base protocol 도입
  - 동적 export 경로용 stub/type shim 추가
  - undefined name 류 오류부터 먼저 0으로 만들기

### 3-2. 현재 테스트는 핵심 결함 몇 가지를 놓치고 있습니다

- 이번에 직접 확인한데도 테스트에 없는 항목
  - `add_snippet` 생성 성공 테스트
  - 드래그앤드롭 핀 순서 변경 실동작 테스트
  - 보관함 복사/스니펫 사용 시 `is_internal_copy` 보호 테스트
  - 이미지 export/import round-trip 테스트
  - 동일 텍스트 재복사 시 메타데이터 보존 테스트
- 해석
  - 현재 회귀 범위는 구조/호환성 쪽은 괜찮지만, 실제 사용 흐름 기반 회귀가 부족합니다.

### 3-3. payload 산출물 검증은 릴리스 직전 한 번 더 확인하는 것이 안전합니다

- `git status --short` 기준으로 현재 워크트리에 `smartclipboard_app/legacy_main_payload.marshal` 변경이 있습니다.
- `claude.md:21-28`에도 적혀 있듯 이 파일은 바이너리 payload라 diff review가 어렵습니다.
- 권장
  - 소스 변경이 반영된 의도된 수정인지 확인
  - 릴리스 전 `tests/test_payload_sync.py` + 빌드 경로 재검증

## 4. 우선순위 제안

1. 바로 수정
   - 스니펫 저장 `datetime` 누락
   - 보관함/스니펫 내부 복사 보호
   - 동일 텍스트 재복사 시 메타데이터 유실
2. 그다음 수정
   - 이미지 JSON export/import
   - 드래그앤드롭 `Qt` 누락
   - 휴지통 선택 영구 삭제
3. 문서 또는 기능 정합성 맞추기
   - 스니펫 단축키
   - 핫키 충돌 감지/경고
   - 보안 보관함 암호화 명세 문구
4. 품질 체계 정리
   - `pyright` 오류 감축
   - 위 결함들에 대한 회귀 테스트 추가

## 한 줄 결론

겉으로는 테스트가 모두 통과하지만, 실제 사용자 흐름 기준으로는 "스니펫 저장 실패", "재복사 시 메타데이터 소실", "보안 보관함 내용의 일반 히스토리 재유입", "이미지 마이그레이션 누락"이 가장 먼저 막아야 할 문제입니다.

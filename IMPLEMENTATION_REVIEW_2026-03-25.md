# SmartClipboard 2026-03-25 구현 반영 요약

## 범위

이 문서는 2026-03-25 기준으로 구현 계획서에 포함됐던 항목들이 코드베이스에 어떻게 반영됐는지 빠르게 확인하기 위한 동기화 문서다.

## 완료된 핵심 변경

### 데이터 정합성

- `cleanup()`가 `id ASC`가 아니라 `timestamp ASC, id ASC` 기준으로 가장 오래된 항목부터 정리되도록 수정됐다.
- 전체 기록 삭제는 영구 삭제 대신 `soft_delete_unpinned()`를 통해 휴지통 이동 정책으로 통일됐다.
- JSON 재-import 시 컬렉션 이름을 정규화해 기존 컬렉션을 재사용하고, 중복 컬렉션 생성을 방지한다.
- 컬렉션 생성/수정은 빈 이름과 중복 이름을 막도록 보강됐다.
- 복사 규칙과 클립보드 액션은 `priority` 컬럼을 실제 UI 정렬과 동기화한다.

### 기능 완성도

- JSON/CSV/Markdown 내보내기에 동일한 날짜·타입 필터를 적용한다.
- JSON만 `IMAGE` 항목의 `image_data_b64`를 보존하고, CSV/Markdown은 이미지 플레이스홀더만 기록한다.
- 스니펫 `shortcut` UI와 app-local 실행 경로가 연결됐다.
- 스니펫 단축키는 기본 앱 단축키, 글로벌 핫키, 다른 스니펫과 충돌하면 저장되지 않는다.
- 핫키 저장은 등록 실패 시 이전 글로벌 핫키 상태로 롤백된다.
- 복사 규칙/클립보드 액션 다이얼로그는 생성·수정·삭제·우선순위 이동을 지원한다.
- 컬렉션 관리 다이얼로그가 추가됐다.

### 보안 보관함

- 마스터 비밀번호 변경 기능이 추가됐다.
- 보안 보관함에서 복호화 복사한 텍스트는 30초 후 자동 삭제된다.
- 자동 삭제는 “현재 클립보드가 동일한 텍스트일 때만” 수행돼 사용자의 후속 복사를 덮어쓰지 않는다.

## 패키징/문서 동기화

- `smartclipboard.spec`에 `smartclipboard_app.ui.dialogs.collections`를 hidden import로 추가했다.
- `README.md`, `PROJECT_ANALYSIS.md`, `claude.md`에 2026-03-25 구현 상태를 반영했다.

## 검증 결과

- `python scripts/build_legacy_payload.py --src smartclipboard_app/legacy_main_src.py --out smartclipboard_app/legacy_main_payload.marshal --smoke-import`
- `python scripts/preflight_local.py`

검증 결과:

- payload 재생성 성공
- smoke import 성공
- `preflight: ok`
- 전체 테스트 63건 통과, 1건 스킵

## 스킵된 검증

- `cryptography` 미설치 환경이라 보안 보관함 비밀번호 변경의 실제 암복호화 테스트 1건은 자동 스킵됐다.
- 기능 코드는 구현되어 있으며, 의존성 설치 환경에서는 해당 테스트가 활성화된다.

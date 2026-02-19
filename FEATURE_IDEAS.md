# SmartClipboard Pro 기능 아이디어 백로그 (FEATURE_IDEAS)

본 문서는 `README.md`, `claude.md` 및 코드베이스 분석을 기반으로 “추가하면 좋은 기능”을 구현 포인트까지 포함해 정리한 백로그입니다.

## 1) 현재 코드 구조 요약 (중요)
- 엔트리: `클립모드 매니저.py` (외부 호환 API/exports 유지가 중요)
- 부트스트랩: `smartclipboard_app/bootstrap.py` (`MainWindow` 생성/예외 핸들러/트레이 메시지)
- 코어 모듈: `smartclipboard_core/`
  - `smartclipboard_core/database.py`: SQLite 스키마/CRUD, FTS5 기반 통합 검색, 태그/노트/북마크/컬렉션/휴지통/임시항목 등
  - `smartclipboard_core/actions.py`: 패턴 기반 액션(전화/이메일 포맷, URL 타이틀 fetch 등) + `Worker`로 비동기 실행
  - `smartclipboard_core/worker.py`: QRunnable worker
- 레거시 런타임: `smartclipboard_app/legacy_main.py`는 로더이며, 실제 구현은 `smartclipboard_app/legacy_main_payload.marshal`
  - 개발/리팩토링용 소스는 `smartclipboard_app/legacy_main_src.py`
  - payload 반영: `python scripts/build_legacy_payload.py --src smartclipboard_app/legacy_main_src.py --out smartclipboard_app/legacy_main_payload.marshal --smoke-import`

## 2) 코드로 확인된 주요 흐름(후킹 포인트)
- 클립보드 감지/처리:
  - `MainWindow.on_clipboard_change()` -> 디바운스 -> `process_clipboard()`
  - 현재는 `mime_data.hasImage()`, `mime_data.hasText()` 위주 처리
- 저장:
  - `ClipboardDB.add_item()`는 TEXT 중복(고정 아닌 경우) “끌어올리기” 형태로 delete 후 insert
  - 이미지 크기 제한/이미지 항목 유지 제한(최신 20개) 등 정책 존재
- 검색:
  - `ClipboardDB.search_items()`는 FTS5가 있으면 MATCH+b m25 정렬, 실패 시 LIKE로 폴백
  - 검색 대상: `content`, `tags`, `note`, `url_title`
- 자동화:
  - `ClipboardActionManager.process()`가 규칙 매칭 후 동기 액션/URL 타이틀 비동기 fetch 실행
  - 별도의 “복사 규칙(copy_rules)”도 존재 (`apply_copy_rules()`)

## 2.1) 구현 반영 상태 업데이트 (2026-02-19)

아래는 본 백로그 작성 이후 반영된 항목/정책입니다.  
기존 아이디어 섹션은 삭제하지 않고, 후속 계획 비교를 위해 그대로 유지합니다.

- 반영 완료:
  - 파일(Explorer) 복사 히스토리 캡처: `mime_data.hasUrls()` 경로 처리 + `FILE` 타입 저장
  - 검색 쿼리 문법 파서(`tag:`, `type:`, `col:`, `is:`, `limit:`) 적용
  - `col:<name>` 미존재 컬렉션 정책: 전체 검색 폴백이 아닌 0건 반환
  - ZIP import 원자성: 단일 트랜잭션 + 오류 시 전체 롤백

- 안정성 보강:
  - 개발/테스트 환경에서 payload 부재 시 `legacy_main_src.py` 자동 폴백
  - 빈 검색어에서도 복합 필터(`tag/type/bookmark/collection/limit`) 일관 적용

- 테스트 보강:
  - `tests/test_core.py`: 빈 쿼리+복합 필터 경계 케이스
  - `tests/test_backup_zip.py`: 깨진 ZIP 참조 시 전체 롤백 검증
  - `tests/test_symbol_inventory.py`: ENV 미설정 facade import 회귀 검증

## 3) 기능 아이디어 (난이도/효과 기준)
표기:
- 난이도: S(1~2일), M(3~10일), L(2주+)
- 영향 범위: Core(DB/액션), UI(레거시/모듈), Build(payload)

### A. 생산성/UX (Quick Wins 위주)
1. 파일(Explorer) 복사 히스토리 지원 (S~M)
- 배경: DB에 `file_path` 컬럼이 이미 있으나, 클립보드 처리에서 URL/파일 mime을 읽지 않음.
- 제안:
  - `mime_data.hasUrls()` 처리 추가(로컬 파일 경로 리스트)
  - 새로운 타입 `FILE` 도입 또는 TEXT에 경로 저장(권장: `FILE`)
  - UI에서 파일 항목 더블클릭 시 Explorer 열기, 우클릭 “경로 복사/폴더 열기”
- 구현 포인트:
  - 클립보드 처리: `smartclipboard_app/legacy_main_src.py`의 `process_clipboard()`에 urls 처리 분기 추가(변경 시 payload 재빌드 필요)
  - DB: `smartclipboard_core/database.py`에 타입 매핑/필터 아이콘 확장(필요 시 스키마는 그대로)
  - 필터/UI 아이콘: `FILTER_TAG_MAP`, `TYPE_ICONS`에 FILE 추가
- 테스트:
  - DB 단위: FILE 항목 add/get/search 동작
  - 수동: 탐색기에서 파일 복사 후 앱에 저장되는지/재복사 가능한지

2. “검색 쿼리 문법” 지원 (S)
- 제안: 검색창에 `tag:`, `type:`, `col:`, `is:pinned`, `is:bookmark`, `limit:` 같은 토큰을 지원
  - 예: `type:link tag:work oauth`
- 구현 포인트:
  - UI 레벨에서 쿼리 파싱 후 `ClipboardDB.search_items(query, type_filter, tag_filter, bookmarked, collection_id, limit)`에 매핑
  - FTS 문자열은 `query`에서 토큰 제거 후 전달
- 테스트:
  - 파서 단위 테스트(토큰 조합/에러 케이스)
  - 검색 결과가 pinned 우선 정렬 유지되는지

3. 일괄 편집(멀티셀렉트) 기능 확장 (S~M)
- 현재: 다중 삭제는 존재. (코드에 `delete_selected_items`, `merge_selected` 등 존재)
- 제안:
  - 다중 선택에 대해 “태그 일괄 추가/제거”, “컬렉션 일괄 이동”, “북마크 토글” 제공
- 구현 포인트:
  - UI 컨텍스트 메뉴/단축키 연결
  - DB는 `set_item_tags`, `assign_to_collection`, `toggle_bookmark` 반복 호출
- 테스트:
  - 다중 선택 상태에서 작업 후 UI/DB 일치 검증

4. 항목 “편집(Edit)” 지원 (S)
- 제안: TEXT/LINK/CODE 항목 내용 수정(정규화/개인정보 마스킹 등)
- 구현 포인트:
  - DB에 update 메서드 추가(현재는 add/delete 중심)
  - FTS 트리거가 content 업데이트를 반영하도록(이미 `history_au` 트리거가 있음) update path에서 동작 확인
- 테스트:
  - 수정 후 검색/FTS 결과 반영 확인

5. “임시(만료) 항목” UI 노출 (S)
- 근거: `ClipboardDB.add_temp_item()`, `expires_at`, `cleanup_expired_items()` 이미 존재.
- 제안:
  - 컨텍스트 메뉴에 “30분만 저장”, “1일만 저장” 같은 옵션
  - UI에서 임시 항목 배지/남은 시간 표시(가능하면)
- 구현 포인트:
  - UI에서 add_temp_item 호출, 주기적 cleanup 호출(이미 lifecycle 쪽 periodic cleanup 존재)
- 테스트:
  - 임시 항목이 만료 후 제거되는지

### B. 자동화/워크플로우
6. “액션(clipboard_actions)”과 “복사 규칙(copy_rules)” 통합 파이프라인 (M)
- 문제: 유사한 기능이 두 군데로 분산(규칙/액션/정규식 검증/우선순위).
- 제안:
  - 하나의 “Automation Pipeline”으로 합치고 UI에서 단계별 실행(Transform -> Tag -> Notify -> FetchTitle 등)
  - 실행 로그/프리뷰 제공
- 구현 포인트:
  - `smartclipboard_core/actions.py` 확장: transform뿐 아니라 tag/collection/secure-vault 이동 같은 액션 타입 추가
  - DB 스키마는 유지하고, UI에서 “파이프라인 그룹”을 구성해도 됨(점진적 접근 권장)
- 테스트:
  - 규칙 우선순위/동시 적용/에러 폴백

7. “민감정보 자동 감지” + 저장 차단/보관함 이동 (M)
- 예: JWT, API Key, 비밀번호 패턴 등
- 제안:
  - 감지 시 (a) 저장 안 함 (b) 보관함으로 이동 (c) 마스킹 저장 옵션
- 구현 포인트:
  - 클립보드 처리 직전에 판별(텍스트 기준)
  - 설정 UI에 패턴 편집/화이트리스트 제공
- 테스트:
  - 다양한 패턴/오탐 방지(길이/엔트로피/접두어 조합)

8. “앱별 제외 목록(Do not capture from …)” (M~L)
- 제안: 특정 프로세스/윈도우(브라우저 시크릿, 패스워드 매니저 등)에서 복사된 내용은 저장하지 않음
- 구현 포인트:
  - Windows API로 포그라운드 프로세스명 획득(추가 의존성 없이 ctypes로 가능, 또는 pywin32 선택)
  - 설정 DB에 ignore list 저장
- 테스트:
  - 지정 앱에서 복사 시 미저장, 그 외 앱 정상 저장

### C. 데이터/백업/동기화
9. “전체 백업(이미지/태그/노트/컬렉션 포함)” ZIP + 선택적 암호화 (M)
- 현재 ExportImportManager는 이미지 제외, 메타(태그/노트/북마크/컬렉션)도 제외.
- 제안:
  - `backup.zip`
    - `items.json` (모든 필드)
    - `images/{id}.png` (blob 분리 저장)
  - 옵션: cryptography로 ZIP 전체 암호화(또는 json+images 암호화)
- 구현 포인트:
  - 신규 export/import 경로 추가(기존 JSON/CSV/MD 유지)
  - import 시 중복/충돌 정책(아래 10번) 필요
- 테스트:
  - round-trip(내보내기->새 DB로 가져오기) 일치

10. 가져오기 충돌 처리 정책 (M)
- 제안:
  - 동일 content(또는 해시) 발견 시: (a) 건너뛰기 (b) 새로 추가 (c) use_count 병합
  - pinned/bookmark/tags/notes 병합 규칙 정의
- 구현 포인트:
  - DB에 “정규화된 비교 키”(예: TEXT는 content, IMAGE는 hash) 기반 merge 로직
- 테스트:
  - 중복 케이스별 결과 검증

11. “스마트 컬렉션(저장된 검색)” (M)
- 제안: 컬렉션을 수동 그룹뿐 아니라 “쿼리로 정의되는 동적 그룹”으로도 제공
- 구현 포인트:
  - `smart_collections` 테이블(이름, query, icon, color) 추가 또는 settings에 JSON 저장(간단)
  - UI에서 선택 시 `search_items()`에 매핑
- 테스트:
  - 쿼리 변경 시 즉시 반영

### D. 링크/콘텐츠 품질
12. 링크 프리뷰 확장(제목+파비콘+설명) (M)
- 현재: URL 제목만 `url_title` 캐시에 저장.
- 제안:
  - favicon URL/og:description/og:image 등 메타 캐시(추가 컬럼 또는 JSON 컬럼)
  - UI에 미리보기 카드
- 구현 포인트:
  - 액션 타입 확장 + 비동기 fetch
  - 네트워크 실패 시 폴백/재시도 정책
- 테스트:
  - 타임아웃/SSL/리다이렉트 처리

13. 코드 감지 고도화 + 언어 추정 (M)
- 제안: `CODE` 항목에 대해 간단한 언어 추정(키워드/파일 헤더 기반) + 내보내기 시 fenced code block 언어 지정
- 구현 포인트:
  - analyze_text() 확장(휴리스틱)
  - DB에 `code_lang` 같은 메타(컬럼 또는 tags/note에 저장) 선택
- 테스트:
  - 대표 언어 샘플

### E. 유지보수/리팩토링(큰 가치, 큰 작업)
14. marshal payload 의존 축소(점진적 모듈화) (L)
- 목표: `legacy_main_src.py`의 거대 클래스/다이얼로그/매니저를 `smartclipboard_core/`, `smartclipboard_app/ui/`로 이동하고, payload는 “최소 쉘”로 축소.
- 리스크: 외부 호환(import/export) 및 시그널 연결 회귀
- 안전장치(이미 존재):
  - `scripts/refactor_symbol_inventory.py` + `tests/test_symbol_inventory.py`
  - `scripts/refactor_signal_snapshot.py` + `tests/test_signal_snapshot.py`
- 단계:
  1) 순수 로직(ExportImportManager, SecureVaultManager 등)부터 분리
  2) UI 다이얼로그를 하나씩 모듈로 이동
  3) MainWindow는 최후에 분해(컨트롤러/서비스 주입 구조)
- 테스트:
  - 기존 baseline 스냅샷 유지
  - 수동 회귀 테스트 체크리스트(핫키/트레이/검색/삭제/보관함/내보내기)

## 4) 추천 우선순위(Top 10)
1. 파일 복사 히스토리(탐색기 경로) 지원
2. 검색 쿼리 문법(`tag:`, `type:` 등)
3. 내보내기/가져오기 “전체 백업 ZIP”(메타+이미지)
4. 임시(만료) 항목 UI 노출
5. 항목 편집(Edit)
6. 다중 선택 일괄 태그/컬렉션/북마크
7. 민감정보 자동 감지/차단
8. 앱별 캡처 제외 목록
9. 링크 프리뷰 확장(제목+메타)
10. 스마트 컬렉션(저장된 검색)

## 5) 테스트/검증 시나리오(기능 추가 시 공통)
- 단위 테스트: `python -m unittest discover -s tests -v`
- 컴파일 체크: `python -m py_compile "클립모드 매니저.py" ...`
- payload 반영이 필요한 변경이면:
  - `python scripts/build_legacy_payload.py --src smartclipboard_app/legacy_main_src.py --out smartclipboard_app/legacy_main_payload.marshal --smoke-import`
- 수동 체크(최소):
  - 클립보드 TEXT/IMAGE 저장, 검색(FTS 폴백 포함), 핫키/트레이 토글, 삭제/휴지통 복원, 보관함 잠금/타임아웃

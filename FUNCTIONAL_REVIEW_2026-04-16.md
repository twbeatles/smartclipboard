# Functional Review 2026-04-16

## 반영 완료 항목

- 자동화 액션 체인 수정:
  - `format_phone`, `format_email`, `transform` 결과를 `replace_text` 계약으로 통일
  - 같은 배치의 후속 액션은 변환된 텍스트 기준으로 평가
  - `fetch_title`은 동기 치환이 끝난 최종 텍스트에서 URL을 추출
- 액션 결과 반영 정합성 수정:
  - 텍스트 치환 결과를 history row와 실제 clipboard에 다시 기록
  - `content`, `type`, `url_title`, `file_path`, `file_signature`를 함께 정리
- JSON import 후 UI 정합성 수정:
  - 새 컬렉션이 생기면 메인 상단 컬렉션 필터를 즉시 새로고침
- 검색/빈 상태 정합성 수정:
  - query가 있을 때 기본 검색 결과는 DB/FTS relevance 순서를 유지
  - 사용자가 직접 헤더 정렬을 바꾼 경우에만 client-side sort override 적용
  - 검색 0건/빈 히스토리에서도 상태바 건수를 `0`으로 즉시 갱신

## 문서/설정 파일 정합성 점검

- `README.md`, `claude.md`, `.gemini/GEMINI.md`, `legacy/README (modular).md`, `legacy/README (legacy).md`, `PROJECT_ANALYSIS.md`에 2026-04-16 기준 구현 계약을 추가 반영
- `smartclipboard.spec` 주석에 이번 기능 보강이 패키징 자산/hidden import 범위를 바꾸지 않는다는 점을 명시
- `.gitignore`는 `build/`, `dist/`, `__pycache__/`, 로그/DB/백업/테스트 임시 경로를 이미 충분히 커버하고 있어 추가 수정은 보류

## 검증

- `python scripts/preflight_local.py`
- `pyinstaller --clean smartclipboard.spec`

# Project Audit

## 1. Executive Summary

본 감사는 SmartClipboard Pro 프로젝트의 전체 아키텍처, 핵심 데이터 흐름, 보안 체계 및 최근 구현된 Ed25519 디지털 서명 기반 GitHub Releases 자동 업데이트 시스템을 기능 구현 및 안정성 관점에서 종합적으로 분석한 결과입니다.

* **전체 위험도**: **Medium-Low (양호)**
* **주요 강점**:
  * Ed25519 비대칭 암호화 서명 검증 및 SHA-256 해시/크기 검증을 통한 안전한 업데이트 파이프라인 구축
  * 업데이트 실패 시 이전 실행 파일 자동 롤백 및 사후 결과 기록/소비 메커니즘 구비
  * PBKDF2-HMAC-SHA256 및 Fernet을 활용한 보안 보관함 암호화 및 5분 타임아웃 자동 잠금
  * FTS5 전문 검색, 내부 복사 루프 방지 가드(`mark_internal_copy`), URL 안전 가드(`NetworkGuard`)
* **핵심 개선 필요 사항**:
  1. 레거시 UI 진입점(`legacy_main_src.py`)의 데이터 복원 로직이 신규 모듈화된 안전 복원 엔진(`backup.py`)을 우회하고 단순 파일 복사를 수행하는 문제
  2. 업데이트 헬퍼 실행 시 메인 프로세스 종료 지연에 따른 타임아웃/파일 잠금 가능성
  3. 백그라운드 주기적 업데이트 확인 옵션 부재 및 관리자 권한(Program Files 설치 시) 대응

---

## 2. Project Understanding

### 2.1 아키텍처 및 핵심 모듈 구조

```
[클립모드 매니저.py (Facade/Entry)]
          │
          ▼
[smartclipboard_app/bootstrap.py]
  ├── --smoke (무결성 진단)
  ├── --apply-update (업데이트 헬퍼)
  └── GUI App 실행 (MainWindow)
          │
          ├── [smartclipboard_app/ui/main_window.py]
          │     ├── ClipboardController (클립보드 모니터링/디바운스/파이프라인)
          │     ├── TableController (목록 표시, FTS 검색, 정렬, 필터)
          │     ├── TrayHotkeyController (글로벌 핫키, 트레이 아이콘)
          │     ├── LifecycleController (시작/종료, 백업/정리)
          │     └── UpdaterController (업데이트 확인, 다운로드, 무결성 검증, 설치)
          │
          └── [smartclipboard_core/]
                ├── config.py (버전, 업데이트 채널, Ed25519 공개키)
                ├── update_manifest.py (Ed25519 서명 검증, 버전 비교, HTTPS)
                ├── update_installer.py (스테이징, 백업, 무결성 교체, 롤백)
                ├── database.py / db_parts/ (SQLite DB, FTS5, 트랜잭션 락)
                ├── automation/ (URL fetch_title, NetworkGuard, 정규식 액션)
                └── action_palette/ (Contextual Action Palette 수동 실행)
```

### 2.2 주요 데이터 흐름 및 실행 흐름

1. **클립보드 캡처 흐름**:
   `QClipboard.dataChanged` 발생 ➔ 100ms 디바운스 ➔ `process_clipboard()` ➔ 내부 복사(`mark_internal_copy`) 여부 및 프라이버시 모드 확인 ➔ 텍스트/이미지/파일 분석 ➔ 복사 규칙 적용 ➔ SQLite DB에 `add_item` (동일 텍스트/파일 중복 시 기존 메타데이터 유지하며 타임스탬프 갱신) ➔ 자동 액션 실행 (URL 제목 조회 등) ➔ UI 갱신

2. **자동 업데이트 흐름**:
   `도움말 > 🚀 업데이트 확인...` 클릭 ➔ 백그라운드 스레드에서 `latest.json` HTTPS 다운로드 ➔ Ed25519 공개키로 디지털 서명 및 버전/해시/만료일 검증 ➔ 새 버전 발견 시 확인 다이얼로그 ➔ `.updates/`에 스트리밍 다운로드 및 스테이징 ➔ 설치 승인 시 `SmartClipboard.exe.vX.Y.bak` 백업 생성 ➔ `update-helper` 독립 프로세스 기동 ➔ 부모 프로세스 종료 대기 ➔ 원자적 교체 및 `--smoke` 검증 ➔ 실패 시 원본 롤백 및 `last-update-result.json` 기록

---

## 3. High-Risk Issues

### [Issue 1] 레거시 `restore_data()` 경로의 안전성 검증 및 백업 누락

* **위치**: `smartclipboard_app/legacy_main_src.py:3663` (`restore_data`)
* **문제**:
  모듈화된 `smartclipboard_app/features/import_export/backup.py`에는 `inspect_restore_database`(무결성 및 테이블 검증), `create_pre_restore_backup`(사전 백업), `replace_database_from_backup`(WAL/SHM sidecar 제거 및 임시 파일 교체)가 구현되어 있으나, 레거시 UI 진입점(`legacy_main_src.py`)에서는 `self.db.conn.close()` 후 검증 없이 `shutil.copy2(file_name, DB_FILE)`를 직접 호출하고 있습니다.
* **영향**:
  사용자가 손상된 DB나 호환되지 않는 파일을 복원용으로 선택할 경우, 사전 백업 없이 기존 DB가 덮어씌워지며 SQLite WAL 잔여 파일 충돌로 DB가 복구 불가능하게 깨질 수 있습니다.
* **근거**:
  `smartclipboard_app/legacy_main_src.py` 3663~3677행:
  ```python
  self.db.conn.close()
  import shutil
  shutil.copy2(file_name, DB_FILE)
  ```
  반면 `backup.py`에 정의된 안전한 복원 함수들이 호출되지 않고 있습니다.
* **권장 수정 방향**:
  `legacy_main_src.py`의 `restore_data()`가 `backup.py`의 `inspect_restore_database`, `create_pre_restore_backup`, `replace_database_from_backup`을 호출하도록 통일합니다.
* **우선순위**: **High**

---

### [Issue 2] 업데이트 헬퍼 프로세스 전환 시 프로세스 잔여 및 파일 잠금 가능성

* **위치**: `smartclipboard_app/features/updater/controller.py:240` 및 `smartclipboard_core/update_installer.py:230`
* **문제**:
  업데이트 설치를 위해 `launch_update_helper()` 실행 후 `QApplication.quit()`을 호출하지만, 백그라운드 스레드(키보드 훅 리스너, QThreadPool, 타이머 등)가 완전히 종료되지 않아 메인 프로세스가 완전히 죽지 않고 파일 핸들을 물고 있을 가능성이 있습니다.
* **영향**:
  `apply_update` 헬퍼가 30초 동안 부모 PID 종료를 대기하다가 `TimeoutError`가 발생하여 업데이트가 실패하고 롤백될 수 있습니다.
* **근거**:
  `_on_download_ready`에서 `launch_update_helper(...)` 직후 단순 `QApplication.quit()`만 호출됨. Windows 환경에서는 서브스레드가 남아있을 경우 프로세스가 즉시 종료되지 않을 수 있음.
* **권장 수정 방향**:
  헬퍼 실행 전 트레이 아이콘 및 핫키 리스너를 명시적으로 unhook/정리하고, 필요 시 `QTimer.singleShot` 또는 `sys.exit(0)`을 통해 프로세스가 신속하게 완전히 종료되도록 보장합니다.
* **우선순위**: **Medium**

---

### [Issue 3] URL 제목 가져오기(`fetch_title`) 레거시 경로와 신규 보안 가드 경로의 이원화

* **위치**: `smartclipboard_app/legacy_main_src.py:1440` vs `smartclipboard_core/automation/fetch_title.py`
* **문제**:
  `smartclipboard_core/automation/network_guard.py`에 로컬/사설망 IP 및 클라우드 메타데이터 IP를 차단하는 `validate_title_fetch_url`이 구현되어 있으나, 레거시 소스 `legacy_main_src.py` 내의 `_fetch_title_logic`에는 이 검증 단계 없이 단순 `requests.get`이 구현되어 있습니다.
* **영향**:
  레거시 런타임 모드(`SMARTCLIPBOARD_LEGACY_IMPL=src`)로 실행될 경우 내부 사설망 IP로의 불필요한 요청(SSRF)이 발생할 수 있습니다.
* **근거**:
  `legacy_main_src.py` 1440~1452행에 `NetworkGuard` 호출 부재.
* **권장 수정 방향**:
  `legacy_main_src.py`의 `_fetch_title_logic`에서도 `smartclipboard_core.automation.network_guard.is_safe_title_fetch_url`을 호출하도록 정합성을 맞춥니다.
* **우선순위**: **Medium**

---

## 4. Potential Functional Gaps

### [Gap 1] 백그라운드 자동 업데이트 주기적 확인 부재 *(추정)*
* **내용**: 현재 업데이트 확인은 사용자가 메뉴를 직접 클릭할 때만 트리거됩니다. 앱 기동 시(시작 1회) 또는 매일 1회 백그라운드에서 조용히 매니페스트를 확인하고 새 버전이 있을 때만 알림을 띄우는 옵션(설정 UI 연동)이 제공되면 사용자 경험이 대폭 향상됩니다.

### [Gap 2] UAC / Program Files 설치 환경 권한 처리 *(추정)*
* **내용**: 사용자가 일반 포터블 경로가 아닌 `C:\Program Files` 등에 실행 파일을 두고 실행할 경우, 일반 권한으로는 실행 파일 교체(`os.replace`) 시 `PermissionError`가 발생합니다. 업데이트 헬퍼 기동 시 권한 오류를 감지하고 UAC 승격(runas)을 요청하는 처리가 추가되면 설치 환경 호환성이 높아집니다.

### [Gap 3] README 및 문서상의 업데이트 기능 설명 미기재 *(실제)*
* **내용**: `README.md` 및 `claude.md`에 이번에 추가된 Ed25519 서명 기반 릴리즈 업데이트 시스템과 배포 방법(Git 태그 푸시)에 대한 설명이 누락되어 있습니다.

---

## 5. Recommended Fix Plan

### 1단계: 즉시 수정 (안전성 및 무결성)
1. **`legacy_main_src.py` 복원 로직 통합**:
   `restore_data()`가 `backup.py`의 `validate_restore_database`, `create_pre_restore_backup`, `replace_database_from_backup`을 호출하도록 교체.
2. **`legacy_main_src.py` fetch_title 보안 가드 통일**:
   `validate_title_fetch_url` 적용.

### 2단계: 안정성 개선 (프로세스 및 헬퍼)
1. **업데이트 헬퍼 프로세스 종료 보장**:
   `UpdaterController`에서 헬퍼 기동 전 핫키 해제 및 `QApplication.exit(0)` / `sys.exit(0)` 클린업 처리 강화.
2. **README.md 및 CLAUDE.md 동기화**:
   자동 업데이트 기능 및 릴리즈 태그 배포 워크플로우 문서화.

### 3단계: 구조 및 기능 개선 (편의성)
1. **주기적/시작 시 백그라운드 업데이트 확인 옵션 추가**:
   설정 다이얼로그에 "시작 시 자동으로 업데이트 확인" 체크박스 추가 및 비간섭형 토스트 알림 연동.
2. **UAC 권한 오류 처리 보강**:
   Program Files 등 쓰기 권한이 없는 경로에서 `PermissionError` 발생 시 안내 또는 UAC 승격 실행 지원.

---

## 6. Test Recommendations

1. **`UpdaterController` UI Mocking 테스트**:
   * 네트워크 다운로드 성공/실패 시그널 흐름 검증
   * 사용자가 업데이트 다이얼로그에서 '나중에' 또는 '업데이트 다운로드'를 눌렀을 때의 상태 전이 검증
2. **`restore_data` 비정상 파일 거부 테스트**:
   * 손상된 SQLite 파일 복원 시도 시 기존 DB 유지 및 에러 알림 검증
   * `-wal`, `-shm` 파일이 존재하는 상태에서의 복원 원자성 검증
3. **업데이트 헬퍼 타임아웃 및 롤백 E2E 시뮬레이션**:
   * 교체 후 `--smoke`가 에러 코드를 반환할 때 백업 파일이 정확하게 원상 복구되는지 검증

# CLAUDE.md — 경영지표 대시보드 (PoC)

이 파일은 Claude Code가 이 프로젝트에서 작업할 때 항상 먼저 읽는 안내서다.
상세 요구사항은 [specs/](specs/) 폴더에 있고, 근거 문서는 「경영지표 대시보드 프로젝트 지침 (기업 미팅 반영판, 2026-10-17)」이다.

## 1. 프로젝트 한 줄 요약

엑셀로 관리하던 **수금·실적·생산·출장보고서 데이터**를 웹앱에서 입력·업로드하면 **팀별 대시보드가 자동으로 만들어지는 PoC**를 한 달 안에 완성한다.

- 사용자: 직원 12명 (대규모 시스템 아님 → 구조는 단순하게)
- 핵심 가치: 연간 목표 대비 달성 현황을 한눈에 보고, 분기마다 부족한 점·개선점을 빠르게 파악
- 화면: 경영지원팀 메인 / 생산팀 / 서비스팀 / 관리자 페이지
- 최종 산출물: 동작하는 웹앱, 시연 시나리오, 발표 자료, 포트폴리오용 설명

## 2. 기술 스택 (확정)

```
Vue.js SPA
    |
    | HTTP / JSON
    v
Django REST Framework
    |
    | Django ORM
    v
PostgreSQL
```

| 구분 | 기술 |
|---|---|
| Frontend | Vue.js 3, Vite, Bootstrap 5.0, HTML5, CSS3, SPA |
| Backend | Python 3, Django, Django REST Framework (REST/JSON API) |
| ORM | Django ORM (SQL 직접 작성 대신 파이썬 코드로 DB 사용) |
| Database | PostgreSQL |

- **사용자 모델**: user와 admin은 Django의 `AbstractUser`를 상속받아 확장한다. 사용자 모델은 **하나만** 만들고 `role`과 소속 팀 필드로 구분한다. → [specs/02-users-permissions.md](specs/02-users-permissions.md)
- ⚠️ `AUTH_USER_MODEL`은 **첫 `migrate` 전에** 설정한다. 나중에 바꾸면 DB를 처음부터 다시 만들어야 할 수 있다.
- 보조 라이브러리 후보(차트, 지도, 엑셀·PDF 읽기, 로그인 방식)는 [specs/01-architecture.md](specs/01-architecture.md)를 본다. 팀이 정하기 전에는 임의로 추가하지 않는다.

## 3. 폴더 구조와 실행 방법

```
ITB2026/
├─ CLAUDE.md
├─ specs/            # 상세 요구사항 문서
├─ samples/          # 기업 샘플 파일 (실제 데이터 → Git 제외)
├─ backend/          # Django 프로젝트
│  ├─ config/        # settings.py, urls.py
│  ├─ accounts/      # 사용자 모델(AbstractUser 확장), 로그인·권한
│  ├─ production/    # 생산팀
│  ├─ service/       # 서비스팀
│  ├─ uploads/       # 업로드 → 추출 → 확인 → 저장
│  └─ requirements.txt
├─ frontend/         # Vue 3 + Vite 프로젝트 (src/router, src/App.vue)
├─ .env              # 비밀 키·DB 접속 정보 (Git 제외, .env.example 참고)
└─ .gitignore
```

### 처음 한 번 (새 PC에서)

```powershell
# 1) .env.example 을 복사해 .env 를 만들고 값을 채운다
# 2) PostgreSQL 준비 (설치 프로그램 대신 압축 파일 버전 사용 — 아래 설명 참고)
#    압축 파일을 C:\pgsql 에 풀고, 데이터 폴더를 만든 뒤 서버를 켜고 DB를 만든다
C:\pgsql\bin\initdb.exe -D C:\pgsql\data -U postgres -E UTF8 --locale=C --auth=scram-sha-256 -W
C:\pgsql\bin\pg_ctl.exe -D C:\pgsql\data -l C:\pgsql\server.log start
C:\pgsql\bin\psql.exe -U postgres -h 127.0.0.1 -c "CREATE DATABASE itb2026;"
# 3) 백엔드 (작업 폴더: C:\ITB2026\backend)
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python manage.py migrate
# 4) 프론트엔드 (작업 폴더: C:\ITB2026\frontend)
npm install
```

### 매일 실행 (DB 서버 + 터미널 2개)

```powershell
# 0) DB 서버 켜기 (PC를 껐다 켜면 매번 필요. 이미 켜져 있으면 "already running" 안내가 나옴)
C:\pgsql\bin\pg_ctl.exe -D C:\pgsql\data -l C:\pgsql\server.log start
# 터미널 1 — C:\ITB2026\backend
.\.venv\Scripts\Activate.ps1; python manage.py runserver
# 터미널 2 — C:\ITB2026\frontend
npm run dev          # 브라우저: http://localhost:5173  (/api 요청은 Django 8000번으로 전달됨)
```

### 자주 쓰는 명령

```powershell
python manage.py makemigrations; python manage.py migrate   # 모델을 바꾼 뒤
python manage.py test                                       # 백엔드 테스트
python manage.py seed_users                                 # 가상 계정 6개 생성 (비밀번호: .env의 SEED_USER_PASSWORD)
python manage.py seed_production                            # 가상 제조내역·목표 생산량 (그 연도 가상 데이터만 새로 만듦)
python manage.py seed_production --year 2025 --target 280   # 다른 연도 가상 데이터 (일련번호 4자리 중복 검색 시연용)
python manage.py make_sample_files                          # 시연용 가상 업로드 파일 → backend/sample_data/
python manage.py seed_service                               # 가상 출장보고서 (--year 2025 로 다른 연도)
npm run build                                               # 프론트 빌드 오류 확인
```

- 가상 계정: `admin`(관리자), `prod_leader`·`prod_member`(생산팀장·팀원), `svc_leader`·`svc_member`(서비스팀장·팀원), `dual_member`(겸직 팀원). Django 기본 관리 화면은 `http://localhost:8000/django-admin/`(admin 계정).
- Django 6.1은 시작할 때 DB 접속을 확인하므로, PostgreSQL이 꺼져 있으면 `runserver`가 실행되지 않는다.
- PostgreSQL은 Windows 서비스로 설치하지 않았다. 사용자 이름에 한글이 있으면 공식 설치 프로그램(EDB)이 임시 폴더 경로를 읽지 못해 `getlocales.ps1` 오류로 실패하기 때문이다(2026-10-18 확인). 대신 압축 파일 버전(`postgresql-17.11-5-windows-x64-binaries.zip`)을 `C:\pgsql`에 풀어 쓴다. DB 끄기: `C:\pgsql\bin\pg_ctl.exe -D C:\pgsql\data stop`

## 4. specs 문서 목록

| 파일 | 내용 |
|---|---|
| [specs/README.md](specs/README.md) | 문서 읽는 법, 표시 규칙(확정·제안·확인 필요), 근거 우선순위 |
| [specs/01-architecture.md](specs/01-architecture.md) | 아키텍처, 기술 스택, 보조 도구 후보 |
| [specs/02-users-permissions.md](specs/02-users-permissions.md) | 사용자 모델, 역할·권한표, 계정·보안, 관리자 페이지 |
| [specs/03-common.md](specs/03-common.md) | 공통 기능: 입력 방식, 기간 보기, 업로드 확인 단계, 과거 데이터 이관 |
| [specs/04-main-management.md](specs/04-main-management.md) | 경영지원팀 메인 화면 |
| [specs/05-production.md](specs/05-production.md) | 생산팀 화면: 생산·판매 실적, 일련번호 조회, 납기 캘린더 |
| [specs/06-service.md](specs/06-service.md) | 서비스팀 화면: 출장보고서 집계, 한국 지도 |
| [specs/07-data-model.md](specs/07-data-model.md) | 테이블 설계안 |
| [specs/08-api.md](specs/08-api.md) | REST API 목록안 |
| [specs/09-metrics.md](specs/09-metrics.md) | 지표 정의·계산식·단위·집계 기간 |
| [specs/10-roadmap.md](specs/10-roadmap.md) | 구현 우선순위, 4주 일정 |
| [specs/11-open-questions.md](specs/11-open-questions.md) | 기업에 확인할 질문 목록 |

기능을 구현하기 전에 해당 spec 파일을 먼저 읽는다.

## 5. 작업 원칙 (바이브 코딩)

1. **쉬운 한국어로 설명한다.** 전문 용어는 뜻과 쓰는 이유를 함께 적는다. 팀원이 발표에서 직접 설명해야 한다.
2. **한 번에 기능 하나씩 작게** 구현한다. 코드를 바꿀 때는 "무엇을, 왜, 어디를 바꾸는지"와 실행 방법(터미널, 작업 폴더, 명령어)을 함께 알려준다.
3. **요청하지 않은 기능이나 복잡성은 추가하지 않는다.** specs에 없는 기능은 만들지 않는다. 이미 동작하는 기능은 유지하고 수정은 최소 범위로 한다.
4. **기존 코드를 확인하지 않고** 구조나 기술 스택을 단정하지 않는다.
5. **직접 실행해 보지 않은 코드는 정상 작동한다고 말하지 않는다.**
6. 오류는 오류 메시지와 관련 코드를 근거로 단계적으로 원인을 좁힌다. 설명 순서는 "현재 상태 → 원인 → 해결 절차 → 검증 방법"이다.
7. 기능 하나가 완성될 때마다 Git 커밋을 권한다. 팀원끼리 같은 파일을 동시에 고치지 않도록 기능 단위로 나눈다.
8. 새 기능 아이디어가 나오면 핵심·선택·추가 구현 중 어디에 속하는지 먼저 분류한다([specs/10-roadmap.md](specs/10-roadmap.md)).
9. 이 문서·specs와 다른 판단이 필요하면 임의로 고르지 않고 차이점을 정리해 사용자에게 묻는다.

## 6. 데이터·지표 원칙

- 확인되지 않은 계산식이나 수치를 임의로 만들지 않는다. 지표는 [specs/09-metrics.md](specs/09-metrics.md)의 정의만 쓴다.
- 형식 통일: **금액은 원 단위 정수**, **날짜는 YYYY-MM-DD**, **지역은 시·도 이름**.
- 데이터는 **월 단위로 저장**하고 분기·연간은 합산해 계산한다(제안).
- 엑셀·PDF 업로드는 **추출 → 사람이 확인·수정 → 저장** 단계를 반드시 거친다. 누락·중복·형식 오류를 점검한다.
- 같은 파일을 두 번 올려도 중복 저장되지 않게 기준 번호(일련번호, 판매번호 등)로 확인한다.
- 회계상 값과 다를 수 있는 지표는 화면에 "간이 지표"로, 예측값은 실제값과 구분해 표시한다.
- AI 코멘트는 계산된 값만 근거로 쓰고 "AI가 생성한 참고용 요약"이라고 표시한다.

## 7. 보안 규칙 (반드시 지킴)

- 회원가입 기능은 만들지 않는다. 계정은 관리자(경영지원팀)가 일괄 발급한다.
- 비밀번호는 해시로 저장한다(Django 기본 기능 사용, 직접 암호화 코드 작성 금지).
- 비밀번호·API 키·DB 접속 정보는 코드에 쓰지 않고 `.env`에 둔다. `.env`는 Git에 올리지 않는다.
- 외부 AI API는 **백엔드에서만** 호출한다(API 키가 화면 코드에 노출되지 않게).
- **실제 기업 데이터와 계정 정보는 Git이나 외부에 올리지 않는다.** 개발·시연은 가상 데이터로 한다.
- 권한 확인은 화면(버튼 숨김)뿐 아니라 **반드시 백엔드 API에서도** 한다.

## 8. 문서 표시 규칙

- **확정**: 기업 미팅에서 직접 요청한 내용
- **(제안)**: 팀이나 AI가 덧붙인 방법. 기업 확인 전까지 바뀔 수 있음
- **(확인 필요)**: 모호하거나 언급되지 않은 내용 → [specs/11-open-questions.md](specs/11-open-questions.md)

결정한 내용이나 바꾼 이유는 날짜와 함께 해당 spec 파일 맨 아래 "변경 기록"에 남긴다.

# 01. 아키텍처와 기술 스택

## 1. 전체 구조 (확정)

화면(Vue.js) → API 서버(Django REST Framework) → 데이터베이스(PostgreSQL)의 3단계다. 화면과 서버는 HTTP로 JSON 데이터를 주고받는다.

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

## 2. 기술 스택 (확정)

| 구분 | 기술 | 하는 일 |
|---|---|---|
| Frontend | Vue.js 3, Vite, Bootstrap 5.0, HTML5, CSS3 | 화면을 한 페이지 앱(SPA: 페이지를 새로 불러오지 않고 화면 일부만 바꾸는 방식)으로 만든다. Vite는 개발 서버·빌드 도구, Bootstrap은 기본 레이아웃과 버튼 스타일을 맡는다 |
| Backend | Python 3, Django, Django REST Framework | 로그인·권한 확인, 지표 계산, 업로드 파일 처리를 하고 REST/JSON API로 화면에 데이터를 준다 |
| ORM | Django ORM | SQL을 직접 쓰지 않고 파이썬 코드로 데이터베이스를 다룬다 |
| Database | PostgreSQL | 사용자, 실적, 제조내역, 출장보고서 데이터를 저장한다 |

## 3. 데이터 모델: 사용자 (확정)

- 사용자(user)와 관리자(admin)는 Django의 `AbstractUser`를 상속받아 확장한다.
- 상세 설계는 [02-users-permissions.md](02-users-permissions.md)를 본다.
- ⚠️ 사용자 모델 확장은 프로젝트를 만든 직후, **첫 `migrate` 전에** `settings.py`의 `AUTH_USER_MODEL`로 설정한다.

## 4. 함께 쓸 도구 후보 (제안, 1주차에 팀 합의)

| 용도 | 후보 | 이유 |
|---|---|---|
| 그래프(도넛·막대) | Chart.js + vue-chartjs | 사용법이 쉽고 참고 자료가 많음 |
| 한국 지도 | 시·도 경계 지도 데이터(GeoJSON) + Leaflet 또는 SVG 지도 | 제주 포함 시·도 단위로 점 표시 가능 |
| 엑셀 읽기 | openpyxl 또는 pandas | 병합된 제목 행, 숫자로 저장된 날짜 처리 가능 |
| PDF 읽기 | pdfplumber | 위치 기준으로 텍스트를 읽을 수 있어 2~3단 양식에 적합 |
| 로그인 방식 | Django 세션 인증 또는 JWT(djangorestframework-simplejwt) | 둘 중 팀이 이해하기 쉬운 쪽 하나로 결정 |
| AI 코멘트 | 외부 AI API를 백엔드에서 호출 | API 키가 화면 코드에 노출되지 않도록 하기 위함 |

> 팀 합의 전에는 위 후보 외의 라이브러리를 추가하지 않는다. 결정되면 이 표에 "결정" 열을 채운다.

### 결정 (2026-10-18, Phase 0)

| 용도 | 결정 | 설치 버전 |
|---|---|---|
| 그래프 | Chart.js + vue-chartjs | chart.js 4.5.1, vue-chartjs 5.3.4 |
| 한국 지도 | Leaflet + 시·도 경계 GeoJSON (배경 타일 없이) | leaflet 1.9.4. 경계 데이터: southkorea-maps의 `kostat/2013/json/skorea_provinces_geo_simple.json` (통계청 2013, "자유롭게 공유·변형 가능"). 옛 이름 강원도·전라북도는 화면에서 지금 이름으로 바꿔 씀 |
| 엑셀 읽기 | openpyxl | 3.1.5 |
| PDF 읽기 | pdfplumber | 0.11.10 |
| 로그인 방식 | Django 세션 인증 (Vite 프록시로 같은 주소 사용 → CORS 설정 불필요) | — |
| `.env` 읽기 | python-dotenv (후보 외 추가: `.env` 규칙을 지키기 위해 필요) | 1.2.4 |
| 납기 캘린더 | 라이브러리 없이 Bootstrap 표로 구현 | — |

그 외 설치 버전: Python 3.14.7, Django 6.1.2, DRF 3.18.3, psycopg 3.3.6, Vue 3.5, Vite 8, vue-router 5, Bootstrap 5.0.2. 전체 목록은 `backend/requirements.txt`, `frontend/package.json`.

## 5. 프로젝트 구성 (제안)

```
backend/
├─ config/          # settings.py, urls.py
├─ accounts/        # 사용자 모델, 로그인, 비밀번호, 관리자 기능
├─ management/      # 경영지원팀: 목표매출, 월별 실적 입력
├─ production/      # 생산팀: 제조내역, 수주서, 목표 생산량
├─ service/         # 서비스팀: 출장보고서
└─ uploads/         # 업로드 → 추출 → 확인 → 저장 공통 처리

frontend/
└─ src/
   ├─ views/        # 로그인, 메인, 생산팀, 서비스팀, 관리자, 비밀번호 변경
   ├─ components/   # 차트, 기간 선택, 업로드 확인 표 등
   ├─ router/       # 화면 주소와 접근 권한
   └─ api/          # 백엔드 호출 함수
```

앱 이름과 나누는 방식은 1주차에 팀이 확정한다.

## 6. 환경 설정 원칙

- DB 접속 정보, `SECRET_KEY`, 외부 AI API 키는 `.env`에 두고 Git에 올리지 않는다.
- 개발·시연은 가상 데이터로 한다. 실제 기업 데이터는 기업 승인 후에만 사용한다.

## 변경 기록

- 2026-10-18: 지침(2026-10-17) 기준으로 최초 작성
- 2026-10-18: 보조 도구 결정 내용 추가 (Phase 0 환경 세팅)

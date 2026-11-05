# BeautyBook 백엔드 (FastAPI)

병원 목록, 리뷰, 예약을 DB에 저장하는 API 서버입니다.
서버를 쓰면 모든 방문자가 같은 리뷰와 예약을 보게 됩니다. 브라우저마다 따로 저장되지 않아요.

## 구조

```
backend/
├─ app/
│  ├─ main.py        API 주소(라우트)와 예약 검증 규칙
│  ├─ models.py      DB 테이블: Clinic, Review, Reservation
│  ├─ db.py          DB 연결 (기본은 SQLite 파일, DATABASE_URL로 변경)
│  ├─ seed.py        샘플 병원·리뷰를 DB에 넣는 스크립트
│  └─ seed_data.json 샘플 병원 데이터 (가상)
├─ tests/            pytest 테스트
├─ requirements.txt
└─ requirements-dev.txt
```

## 내 컴퓨터에서 실행

Python 3.11 이상이 필요합니다.

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt
uvicorn app.main:app --reload
```

- http://localhost:8000 → 사이트가 **서버 모드**로 열립니다. 다른 브라우저나 시크릿 창으로 열어도 같은 리뷰와 예약이 보여요.
- http://localhost:8000/docs → API 문서입니다. 버튼을 눌러 직접 요청을 보내 볼 수 있어요.

처음 실행하면 `backend/beautybook.db` 파일이 생기고 샘플 병원 8곳이 들어갑니다. 처음 상태로 돌리고 싶으면 서버를 끄고 이 파일을 지우세요.

## 진짜 병원 목록 가져오기 (로드맵 2단계)

공공데이터포털의 **건강보험심사평가원_병원정보서비스**에서 진료과목이 성형외과(코드 08)인 의원(종별 31)을 받아 DB에 넣어요.

1. [data.go.kr](https://www.data.go.kr)에서 "건강보험심사평가원_병원정보서비스"를 활용신청해요. 승인 후 키가 실제로 동작하기까지 1시간쯤 걸릴 수 있어요.
2. 마이페이지에 있는 일반 인증키 중 **Decoding** 키를 터미널에 설정해요. 키는 코드나 git에 넣지 마세요.
   ```bash
   export HIRA_SERVICE_KEY='여기에_Decoding_키'
   ```
3. 먼저 미리보기로 확인하고, 괜찮으면 저장해요.
   ```bash
   python -m app.import_hira --sido 110000 --limit 50 --dry-run   # 서울 50곳 미리보기
   python -m app.import_hira --sido 110000 --limit 50 --replace-samples
   ```
4. 서버를 다시 켜면(`uvicorn app.main:app --reload`) 사이트에 진짜 병원이 나와요.

| 옵션 | 설명 |
| --- | --- |
| `--sido 110000` | 지역 (서울 110000, 부산 210000, 경기 410000 등). 없으면 전국 |
| `--limit 100` | 최대 몇 곳 (기본 100) |
| `--replace-samples` | 가상 샘플 병원 8곳과 그 리뷰·예약 삭제 |
| `--dry-run` | DB에 넣지 않고 목록만 출력 |

같은 명령을 다시 실행하면 새 병원은 추가하고, 이미 있는 병원은 이름·주소·전화만 갱신해요. 리뷰와 예약은 그대로 남아요.

공공데이터에는 **진료 시간, 시술, 가격, 사진이 없어서** 진료 시간은 기본값(10:00~19:00, 일요일 휴진)으로 넣고 화면에 "기본값" 안내를 띄워요. 시술은 "일반 상담" 하나만 넣어요. 다국어 이름도 없어서 모든 언어에 한국어 이름을 그대로 보여 줘요.

## 테스트

```bash
cd backend
pytest
```

## API

| 메서드 | 주소 | 설명 |
| --- | --- | --- |
| GET | `/api/clinics` | 병원 목록 (평균 별점, 리뷰 수 포함) |
| GET | `/api/clinics/{id}` | 병원 하나 |
| GET | `/api/clinics/{id}/reviews` | 리뷰 목록 (최신순) |
| POST | `/api/clinics/{id}/reviews` | 리뷰 작성 `{rating 1~5, nick, text}` |
| GET | `/api/clinics/{id}/taken-slots?date=YYYY-MM-DD` | 그날 이미 예약된 시간 |
| GET | `/api/reservations/me` | 내 예약 목록 |
| POST | `/api/reservations` | 예약 `{clinicId, name, phone, procedure, date, time, memo}` |
| DELETE | `/api/reservations/{id}` | 내 예약 취소 |

예약할 때 서버가 확인하는 것: 휴진일, 진료 시간 안의 30분 단위 시간, 오늘~60일 이내, 이미 지난 시간, 그 병원의 시술인지,
그리고 **같은 시간 중복 예약**(DB 제약으로 막아서 동시에 눌러도 한 명만 성공)입니다.

### 아직 로그인이 없어서

브라우저마다 임의의 ID를 만들어 `X-Guest-Id` 헤더로 보내고, 이걸로 "내 예약"과 "내 리뷰"를 구분합니다.
로드맵 4단계(카카오 로그인)에서 이 부분을 진짜 회원 ID로 바꿀 예정입니다.

## 설정 (환경변수)

| 이름 | 기본값 | 설명 |
| --- | --- | --- |
| `DATABASE_URL` | `sqlite:///backend/beautybook.db` | 3단계에서 Supabase 같은 PostgreSQL 주소로 바꿉니다 |
| `CORS_ORIGINS` | `*` | 이 API를 부를 수 있는 사이트 주소. 배포할 때는 `https://hiworld-cloud.github.io`처럼 실제 주소만 적으세요 |

## 프론트와 연결되는 방식

사이트는 `js/config.js`의 `BEAUTYBOOK_API_BASE` 값을 보고 어디에 저장할지 정합니다.

- `null` (기본, GitHub Pages): 지금처럼 브라우저에만 저장
- 이 서버로 사이트를 열면: 서버가 `config.js`를 대신 내려 줘서 자동으로 서버 모드가 됩니다
- 서버를 배포한 뒤: `config.js`에 서버 주소를 적으면 GitHub Pages 사이트도 서버를 사용합니다
- 잠깐 테스트할 때: 주소 뒤에 `?api=http://localhost:8000`을 붙이면 됩니다

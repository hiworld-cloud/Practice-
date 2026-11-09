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
│  ├─ seed_data.json 샘플 병원 데이터 (가상)
│  └─ import_hira.py 공공데이터 API에서 진짜 성형외과 목록을 불러오는 스크립트
├─ .env.example      인증키 적는 파일의 견본 (복사해서 .env 로 만들기)
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

처음 실행하면 `backend/beautybook.db` 파일이 생기고 (DB가 비어 있으면) 샘플 병원 8곳이 들어갑니다. 처음 상태로 돌리고 싶으면 서버를 끄고 이 파일을 지우세요.

## 진짜 성형외과 목록 불러오기 (공공데이터 API)

공공데이터포털의 **건강보험심사평가원_병원정보서비스** API에서 진료과목이 성형외과인 병원의
이름, 주소, 전화번호를 받아 `Clinic` 테이블에 넣습니다.

### 1. 인증키 찾기

1. https://www.data.go.kr 로그인 → 오른쪽 위 **마이페이지**
2. **데이터 활용 → Open API → 활용신청 현황**
3. **건강보험심사평가원_병원정보서비스** 클릭
4. **일반 인증키(Decoding)** 값을 복사 (Encoding 말고 Decoding)

> 인증키는 비밀번호와 같아요. 코드, 채팅, GitHub에 절대 붙여 넣지 마세요.
> 승인 직후에는 키가 실제로 동작하기까지 1~2시간 걸릴 수 있어요.

### 2. `.env` 파일에 키 넣기

`backend` 폴더에서 견본 파일을 복사해 `.env`를 만듭니다.

```bash
cd backend
cp .env.example .env               # Windows: copy .env.example .env
```

`.env`를 메모장이나 VS Code로 열어 `여기에_인증키_붙여넣기` 부분을 복사한 키로 바꾸고 저장하세요. 따옴표는 필요 없어요.

```
HIRA_SERVICE_KEY=복사한키를여기에
```

`.env`는 `.gitignore`에 들어 있어서 `git add -A`를 해도 GitHub에 올라가지 않습니다.
확인하고 싶으면 `git status`를 쳐 보세요. 목록에 `.env`가 안 보이면 안전한 거예요.

### 3. 실행하기

위의 "내 컴퓨터에서 실행"에서 만든 가상환경을 켠 상태(`source .venv/bin/activate`)에서:

```bash
python -m app.import_hira --sido 서울 --limit 5 --dry-run   # ① 키가 되는지만 확인 (DB 저장 X)
python -m app.import_hira --sido 서울 --limit 20             # ② 서울 20곳만 DB에 넣기
python -m app.import_hira --sido 서울 --remove-samples       # ③ 서울 전체 + 가상 샘플 8곳 지우기
python -m app.import_hira                                    # 전국 전체
```

| 옵션 | 뜻 |
| --- | --- |
| `--sido 서울` | 지역만 받기. 서울, 부산, 인천, 대구, 광주, 대전, 울산, 세종, 경기, 강원, 충북, 충남, 전북, 전남, 경북, 경남, 제주 |
| `--limit 20` | 최대 몇 곳까지 받을지 |
| `--dry-run` | DB에 넣지 않고 화면에 목록만 출력 |
| `--remove-samples` | 가상 샘플 병원 8곳과 그 리뷰·예약을 지움 |

여러 번 실행해도 같은 병원이 두 번 생기지 않고, 이름·주소·전화번호만 최신으로 바뀝니다.
그다음 `uvicorn app.main:app --reload`로 서버를 켜고 http://localhost:8000 을 열면 진짜 병원이 보여요.

### 자주 나오는 오류

| 메시지 | 해결 |
| --- | --- |
| 인증키가 없어요 | `backend/.env` 파일이 있는지, 이름이 정확히 `.env`인지 확인 (Windows는 `.env.txt`가 되기 쉬워요) |
| 등록되지 않은 인증키 | 승인 직후면 1~2시간 뒤 다시. 아니면 Decoding 키를 다시 복사 |
| 호출 횟수를 다 썼어요 | 개발계정은 하루 호출 횟수 제한이 있어요. 내일 다시 |

### 아직 공공데이터에 없는 것

공공데이터에는 이름·주소·전화·의사 수 정도만 있어요. 그래서 불러온 병원은

- 시술 목록이 **"상담"** 하나뿐이고 가격은 "가격 문의"로 보여요.
- 진료 시간은 기본값 10:00~19:00, 일요일 휴진으로 넣어요.
- 영어·일본어·중국어 화면에서도 이름과 주소는 한국어로 보여요.

진료 시간은 같은 서비스의 상세정보 API로 나중에 채울 수 있어요.

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
| `HIRA_SERVICE_KEY` | (없음) | 공공데이터포털 인증키(Decoding). `backend/.env`에 적으면 불러오기 스크립트가 읽어요 |

## 프론트와 연결되는 방식

사이트는 `js/config.js`의 `BEAUTYBOOK_API_BASE` 값을 보고 어디에 저장할지 정합니다.

- `null` (기본, GitHub Pages): 지금처럼 브라우저에만 저장
- 이 서버로 사이트를 열면: 서버가 `config.js`를 대신 내려 줘서 자동으로 서버 모드가 됩니다
- 서버를 배포한 뒤: `config.js`에 서버 주소를 적으면 GitHub Pages 사이트도 서버를 사용합니다
- 잠깐 테스트할 때: 주소 뒤에 `?api=http://localhost:8000`을 붙이면 됩니다

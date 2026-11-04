# BeautyBook (연습용 예시 사이트)

성형외과 목록을 보고, 별점을 남기고, 상담 예약을 할 수 있는 정적 웹사이트 예시입니다.
한국어 · English · 日本語 · 中文 네 가지 언어를 지원합니다.

> 모든 병원 정보는 **가상의 샘플 데이터**입니다.
> GitHub Pages에서는 별점과 예약이 **방문자 브라우저(localStorage)** 에만 저장되고,
> `backend/` 서버로 띄우면 **DB에 저장되어 모든 방문자가 공유**합니다.

## 주요 기능

- 병원 목록: 검색(이름·지역), 진료과목 필터, 정렬(별점·리뷰 수·이름)
- 병원 카드를 누르면 상세 팝업: 소개, 진료 시간, 의료진, 시술별 참고 가격
- 예약: 날짜·시간 선택(휴진일, 이미 찬 시간, 지난 시간 자동 차단), '내 예약'에서 확인·취소
- 별점: 1~5점 + 후기 작성, 평균 별점에 바로 반영
- 언어 선택: 선택한 언어를 기억하고, 처음 방문 시 브라우저 언어를 따라감

## 폴더 구조

```
index.html        화면 뼈대
css/style.css     디자인 (라이트/다크 모드, 모바일 대응)
js/i18n.js        화면 문구 번역 (ko/en/ja/zh)
js/config.js      저장 위치 설정 (브라우저 저장 / API 서버 주소)
js/data.js        샘플 병원 데이터 (브라우저 저장 모드용)
js/api.js         데이터 저장/조회 계층 (localStorage 또는 API 서버)
js/app.js         화면 동작
backend/          FastAPI 서버 + DB → backend/README.md 참고
.nojekyll         GitHub Pages가 파일을 그대로 서빙하도록 하는 표시
```

## 내 컴퓨터에서 실행

```bash
python3 -m http.server 8000
# 브라우저에서 http://localhost:8000 열기
```

`index.html`을 바로 더블클릭해도 동작합니다.

## 배포 (GitHub Pages)

1. 저장소 **Settings → Pages** 로 이동
2. **Build and deployment → Source** 를 `Deploy from a branch` 로 선택
3. Branch 를 `main`, 폴더를 `/ (root)` 로 고르고 **Save**
4. 1~2분 뒤 `https://<GitHub아이디>.github.io/<저장소이름>/` 에서 사이트가 열립니다

이후에는 `main`에 머지할 때마다 자동으로 다시 배포됩니다.

## 운영 방법 (작업 흐름)

1. 새 작업은 브랜치에서 합니다: `git checkout -b feature/작업이름`
2. 수정 후 커밋하고 푸시합니다
3. GitHub에서 Pull Request를 열어 변경 내용을 확인합니다
4. `main`에 머지하면 GitHub Pages가 자동 배포합니다

- 병원 추가/수정: `js/data.js`의 `CLINICS` 배열에 항목을 추가합니다
- 문구 수정/언어 추가: `js/i18n.js`에 같은 키로 번역을 넣습니다

## 백엔드 서버로 실행하기 (로드맵 1단계)

```bash
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
uvicorn app.main:app --reload
```

http://localhost:8000 을 열면 사이트가 서버 모드로 동작합니다. 자세한 내용은 [backend/README.md](backend/README.md)를 보세요.

## 다음 단계

1. ~~백엔드 만들기 (FastAPI + DB)~~ ✅
2. 공공데이터포털 API로 진짜 병원 목록 가져오기
3. 서버 배포 (Render + Supabase) 후 `js/config.js`에 서버 주소 넣기
4. 카카오 로그인
5. .com 도메인 연결
6. 전화 인증, 개인정보처리방침, 관리자 기능

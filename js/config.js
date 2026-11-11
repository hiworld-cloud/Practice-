/*
 * 데이터를 어디에 저장할지 정하는 설정.
 *   null  → 서버 없이 이 브라우저(localStorage)에만 저장 (GitHub Pages 기본값)
 *   ""    → 이 사이트를 띄운 서버와 같은 주소의 API 사용 (backend 서버가 자동으로 이 값을 줍니다)
 *   "https://api.example.com" → 그 주소의 API 사용 (서버를 배포한 뒤 여기에 적으면 됩니다)
 * 주소창에 ?api=http://localhost:8000 을 붙이면 잠깐 바꿔서 테스트할 수도 있습니다.
 */
window.BEAUTYBOOK_API_BASE = "https://beautybook-api-a8o9.onrender.com";

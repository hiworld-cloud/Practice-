/*
 * 데이터 접근 계층. 화면 코드(app.js)는 window.API만 사용합니다.
 *
 * 두 가지 모드가 있습니다 (js/config.js 참고).
 *   - 로컬 모드: 서버 없이 이 브라우저의 localStorage에 저장 (GitHub Pages)
 *   - 서버 모드: backend/ 의 FastAPI 서버에 저장 → 모든 방문자가 같은 리뷰와 예약을 봅니다
 *
 *   listClinics()                 GET    /api/clinics
 *   listReviews(clinicId)         GET    /api/clinics/{id}/reviews
 *   addReview(clinicId, data)     POST   /api/clinics/{id}/reviews
 *   takenSlots(clinicId, date)    GET    /api/clinics/{id}/taken-slots?date=YYYY-MM-DD
 *   listReservations()            GET    /api/reservations/me
 *   createReservation(data)       POST   /api/reservations
 *   cancelReservation(id)         DELETE /api/reservations/{id}
 *
 * 실패하면 err.code 가 담긴 Error를 던집니다 (예: "slot_taken", "network").
 */
(function () {
  function apiBase() {
    try {
      const q = new URLSearchParams(location.search).get("api");
      if (q) return q.replace(/\/$/, "");
    } catch (e) {}
    const b = window.BEAUTYBOOK_API_BASE;
    return typeof b === "string" ? b.replace(/\/$/, "") : null;
  }

  function fail(code) {
    const err = new Error(code);
    err.code = code;
    return err;
  }

  /* ---------- 로컬 모드 (localStorage) ---------- */
  function localApi() {
    const KEYS = { reviews: "bb.reviews.v1", reservations: "bb.reservations.v1" };
    const read = key => { try { return JSON.parse(localStorage.getItem(key)) || []; } catch (e) { return []; } };
    const write = (key, v) => { try { localStorage.setItem(key, JSON.stringify(v)); } catch (e) {} };
    const uid = () => Date.now().toString(36) + Math.random().toString(36).slice(2, 7);

    function summary(clinic) {
      const mine = read(KEYS.reviews).filter(r => r.clinicId === clinic.id);
      const sum = clinic.seed.sum + mine.reduce((a, r) => a + r.rating, 0);
      const count = clinic.seed.count + mine.length;
      return { rating: count ? sum / count : 0, count };
    }

    return {
      mode: "local",
      async listClinics() {
        return window.CLINICS.map(c => Object.assign({}, c, summary(c)));
      },
      async listReviews(clinicId) {
        const clinic = window.CLINICS.find(c => c.id === clinicId);
        const mine = read(KEYS.reviews).filter(r => r.clinicId === clinicId)
          .map(r => Object.assign({ mine: true }, r)).reverse();
        return mine.concat(clinic ? clinic.reviews : []);
      },
      async addReview(clinicId, { rating, nick, text }) {
        const all = read(KEYS.reviews);
        const review = { id: uid(), clinicId, rating, nick, text, createdAt: new Date().toISOString() };
        all.push(review);
        write(KEYS.reviews, all);
        return review;
      },
      async takenSlots(clinicId, date) {
        return read(KEYS.reservations).filter(r => r.clinicId === clinicId && r.date === date).map(r => r.time);
      },
      async listReservations() {
        return read(KEYS.reservations).sort((a, b) => (a.date + a.time).localeCompare(b.date + b.time));
      },
      async createReservation(data) {
        if ((await this.takenSlots(data.clinicId, data.date)).includes(data.time)) throw fail("slot_taken");
        const all = read(KEYS.reservations);
        const reservation = Object.assign({ id: uid(), status: "requested", createdAt: new Date().toISOString() }, data);
        all.push(reservation);
        write(KEYS.reservations, all);
        return reservation;
      },
      async cancelReservation(id) {
        write(KEYS.reservations, read(KEYS.reservations).filter(r => r.id !== id));
      }
    };
  }

  /* ---------- 서버 모드 (FastAPI) ---------- */
  function serverApi(base) {
    // 로그인 기능이 생기기 전까지는 브라우저마다 임의 ID를 만들어 "내 예약"을 구분합니다.
    function guestId() {
      let id = null;
      try { id = localStorage.getItem("bb.guestId"); } catch (e) {}
      if (!id) {
        id = "g-" + Date.now().toString(36) + Math.random().toString(36).slice(2, 12);
        try { localStorage.setItem("bb.guestId", id); } catch (e) {}
      }
      return id;
    }

    async function call(method, path, body) {
      let res;
      try {
        res = await fetch(base + path, {
          method,
          headers: Object.assign({ "X-Guest-Id": guestId() }, body ? { "Content-Type": "application/json" } : {}),
          body: body ? JSON.stringify(body) : undefined
        });
      } catch (e) {
        throw fail("network");
      }
      if (res.status === 204) return null;
      const data = await res.json().catch(() => null);
      if (!res.ok) throw fail((data && data.detail && data.detail.code) || "http_" + res.status);
      return data;
    }

    const enc = encodeURIComponent;
    return {
      mode: "server",
      listClinics: () => call("GET", "/api/clinics"),
      listReviews: id => call("GET", `/api/clinics/${enc(id)}/reviews`),
      addReview: (id, data) => call("POST", `/api/clinics/${enc(id)}/reviews`, data),
      takenSlots: (id, date) => call("GET", `/api/clinics/${enc(id)}/taken-slots?date=${enc(date)}`),
      listReservations: () => call("GET", "/api/reservations/me"),
      createReservation: data => call("POST", "/api/reservations", data),
      cancelReservation: id => call("DELETE", `/api/reservations/${enc(id)}`)
    };
  }

  const base = apiBase();
  window.API = base === null ? localApi() : serverApi(base);
})();

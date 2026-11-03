/*
 * 데이터 접근 계층.
 * 지금은 브라우저 localStorage에 저장하지만, 모든 함수가 Promise를 돌려주므로
 * 백엔드가 생기면 함수 안쪽만 fetch("/api/...")로 바꾸면 화면 코드는 그대로 쓸 수 있습니다.
 *
 *   listClinics()              -> GET    /api/clinics
 *   listReviews(clinicId)      -> GET    /api/clinics/{id}/reviews
 *   addReview(clinicId, data)  -> POST   /api/clinics/{id}/reviews
 *   listReservations()         -> GET    /api/reservations/me
 *   createReservation(data)    -> POST   /api/reservations
 *   cancelReservation(id)      -> DELETE /api/reservations/{id}
 */
(function () {
  const KEYS = { reviews: "bb.reviews.v1", reservations: "bb.reservations.v1" };

  function read(key) {
    try { return JSON.parse(localStorage.getItem(key)) || []; } catch (e) { return []; }
  }
  function write(key, value) {
    try { localStorage.setItem(key, JSON.stringify(value)); } catch (e) { /* 저장 불가(사생활 보호 모드 등) */ }
  }
  function uid() {
    return Date.now().toString(36) + Math.random().toString(36).slice(2, 7);
  }

  function summary(clinic) {
    const mine = read(KEYS.reviews).filter(r => r.clinicId === clinic.id);
    const sum = clinic.seed.sum + mine.reduce((a, r) => a + r.rating, 0);
    const count = clinic.seed.count + mine.length;
    return { rating: count ? sum / count : 0, count };
  }

  window.API = {
    async listClinics() {
      return window.CLINICS.map(c => Object.assign({}, c, summary(c)));
    },

    async listReviews(clinicId) {
      const clinic = window.CLINICS.find(c => c.id === clinicId);
      const mine = read(KEYS.reviews)
        .filter(r => r.clinicId === clinicId)
        .map(r => Object.assign({ mine: true }, r))
        .reverse();
      return mine.concat(clinic ? clinic.reviews : []);
    },

    async addReview(clinicId, { rating, nick, text }) {
      const all = read(KEYS.reviews);
      const review = { id: uid(), clinicId, rating, nick, text, createdAt: new Date().toISOString() };
      all.push(review);
      write(KEYS.reviews, all);
      return review;
    },

    async listReservations() {
      return read(KEYS.reservations).sort((a, b) => (a.date + a.time).localeCompare(b.date + b.time));
    },

    async isSlotTaken(clinicId, date, time) {
      return read(KEYS.reservations).some(r => r.clinicId === clinicId && r.date === date && r.time === time);
    },

    async createReservation(data) {
      if (await this.isSlotTaken(data.clinicId, data.date, data.time)) {
        const err = new Error("slot_taken");
        err.code = "slot_taken";
        throw err;
      }
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
})();

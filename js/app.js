(function () {
  const LANGS = ["ko", "en", "ja", "zh"];
  const LOCALES = { ko: "ko-KR", en: "en-US", ja: "ja-JP", zh: "zh-CN" };
  const state = { lang: detectLang(), clinics: [], query: "", specialty: "", sort: "rating", openId: null, tab: "reserve" };

  const $ = sel => document.querySelector(sel);
  const el = {
    grid: $("#clinicGrid"), empty: $("#emptyState"), count: $("#resultCount"),
    search: $("#searchInput"), specialty: $("#specialtyFilter"), sort: $("#sortSelect"),
    lang: $("#langSelect"), modal: $("#clinicModal"), modalBody: $("#clinicModalBody"),
    resModal: $("#reservationsModal"), resList: $("#reservationsList"),
    resBtn: $("#myReservationsBtn"), resCount: $("#reservationCount"), toast: $("#toast")
  };

  /* ---------- 언어 ---------- */
  function detectLang() {
    let saved = null;
    try { saved = localStorage.getItem("bb.lang"); } catch (e) {}
    if (LANGS.includes(saved)) return saved;
    const nav = (navigator.language || "ko").slice(0, 2);
    return LANGS.includes(nav) ? nav : "ko";
  }
  function t(key, vars) {
    let s = (I18N[state.lang] && I18N[state.lang][key]) || I18N.ko[key] || key;
    if (vars) Object.keys(vars).forEach(k => { s = s.replace("{" + k + "}", vars[k]); });
    return s;
  }
  const L = obj => (obj && (obj[state.lang] || obj.ko)) || "";
  const esc = s => String(s).replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const won = n => new Intl.NumberFormat(LOCALES[state.lang], { style: "currency", currency: "KRW" }).format(n);

  function applyStaticText() {
    document.documentElement.lang = state.lang;
    document.querySelectorAll("[data-i18n]").forEach(n => { n.textContent = t(n.dataset.i18n); });
    document.querySelectorAll("[data-i18n-placeholder]").forEach(n => { n.placeholder = t(n.dataset.i18nPlaceholder); });
    el.lang.value = state.lang;
    el.specialty.innerHTML = `<option value="">${esc(t("filter.all"))}</option>` +
      Object.keys(SPECIALTIES).map(k => `<option value="${k}">${esc(L(SPECIALTIES[k]))}</option>`).join("");
    el.specialty.value = state.specialty;
  }

  function setLang(lang) {
    state.lang = lang;
    try { localStorage.setItem("bb.lang", lang); } catch (e) {}
    applyStaticText();
    renderList();
    if (el.modal.open && state.openId) renderDetail();
    if (el.resModal.open) renderReservations();
  }

  /* ---------- 별 ---------- */
  function stars(value) {
    const pct = Math.max(0, Math.min(100, (value / 5) * 100));
    return `<span class="stars" aria-label="${value.toFixed(1)} / 5"><span class="stars-fill" style="width:${pct}%">★★★★★</span>★★★★★</span>`;
  }

  /* ---------- 목록 ---------- */
  async function loadClinics() {
    state.clinics = await API.listClinics();
  }

  function filtered() {
    const q = state.query.trim().toLowerCase();
    let list = state.clinics.filter(c => {
      if (state.specialty && !c.specialties.includes(state.specialty)) return false;
      if (!q) return true;
      const hay = LANGS.map(l => c.name[l] + " " + c.area[l]).join(" ").toLowerCase();
      return hay.includes(q);
    });
    const by = {
      rating: (a, b) => b.rating - a.rating,
      reviews: (a, b) => b.count - a.count,
      name: (a, b) => L(a.name).localeCompare(L(b.name), LOCALES[state.lang])
    };
    return list.sort(by[state.sort]);
  }

  function renderList() {
    const list = filtered();
    el.count.textContent = t("list.count", { n: list.length });
    el.empty.hidden = list.length > 0;
    el.grid.innerHTML = list.map(c => `
      <article class="card" tabindex="0" role="button" data-id="${c.id}" aria-label="${esc(L(c.name))}">
        <div class="card-thumb" style="--h:${c.hue}">
          <span>${esc(L(c.name).charAt(0))}</span>
        </div>
        <div class="card-body">
          <h3>${esc(L(c.name))}</h3>
          <p class="muted">${esc(L(c.area))}</p>
          <div class="rating-row">${stars(c.rating)} <strong>${c.rating.toFixed(1)}</strong>
            <span class="muted">${esc(t("card.reviews", { n: c.count }))}</span></div>
          <div class="tags">${c.specialties.map(s => `<span class="tag">${esc(L(SPECIALTIES[s]))}</span>`).join("")}</div>
          <span class="card-link">${esc(t("card.view"))} →</span>
        </div>
      </article>`).join("");
  }

  /* ---------- 상세 팝업 ---------- */
  function openDetail(id) {
    state.openId = id;
    state.tab = "reserve";
    renderDetail();
    if (!el.modal.open) el.modal.showModal();
  }

  function timeSlots(c) {
    const toMin = s => { const [h, m] = s.split(":").map(Number); return h * 60 + m; };
    const out = [];
    for (let m = toMin(c.hours.open); m + 30 <= toMin(c.hours.close); m += 30) {
      out.push(String(Math.floor(m / 60)).padStart(2, "0") + ":" + String(m % 60).padStart(2, "0"));
    }
    return out;
  }

  function todayISO(offset) {
    const d = new Date();
    d.setDate(d.getDate() + (offset || 0));
    return d.getFullYear() + "-" + String(d.getMonth() + 1).padStart(2, "0") + "-" + String(d.getDate()).padStart(2, "0");
  }

  function nextOpenDay(c) {
    for (let i = 1; i < 8; i++) {
      const iso = todayISO(i);
      if (!c.closedDays.includes(new Date(iso + "T00:00").getDay())) return iso;
    }
    return todayISO(1);
  }

  async function renderDetail() {
    const c = state.clinics.find(x => x.id === state.openId);
    if (!c) return;
    const wd = WEEKDAYS[state.lang];
    const closed = c.closedDays.map(d => wd[d]).join(", ");
    el.modalBody.innerHTML = `
      <div class="modal-head">
        <div>
          <h2>${esc(L(c.name))}</h2>
          <div class="rating-row">${stars(c.rating)} <strong>${c.rating.toFixed(1)}</strong>
            <span class="muted">${esc(t("card.reviews", { n: c.count }))}</span></div>
        </div>
        <button class="icon-btn" type="button" data-close aria-label="${esc(t("common.close"))}">&times;</button>
      </div>
      <div class="detail-grid">
        <section>
          <h4>${esc(t("detail.about"))}</h4>
          <p>${esc(L(c.about))}</p>
          <dl class="facts">
            <dt>${esc(t("detail.hours"))}</dt><dd>${c.hours.open} – ${c.hours.close} · ${esc(t("weekday.closed", { d: closed }))}</dd>
            <dt>${esc(t("detail.address"))}</dt><dd>${esc(L(c.address))}</dd>
            <dt>${esc(t("detail.phone"))}</dt><dd>${esc(c.phone)}</dd>
            <dt>${esc(t("detail.doctors"))}</dt><dd>${c.doctors.map(d => esc(L(d.name))).join(", ")}</dd>
          </dl>
          <h4>${esc(t("detail.procedures"))}</h4>
          <ul class="price-list">${c.procedures.map(p =>
            `<li><span>${esc(L(PROCEDURES[p.key]))}</span><span>${esc(p.price ? t("detail.priceFrom", { p: won(p.price) }) : t("detail.priceAsk"))}</span></li>`).join("")}</ul>
        </section>
        <section class="panel">
          <div class="tabs" role="tablist">
            ${["reserve", "rate", "reviews"].map(k =>
              `<button type="button" role="tab" class="tab ${state.tab === k ? "active" : ""}" data-tab="${k}" aria-selected="${state.tab === k}">${esc(t("tab." + k))}</button>`).join("")}
          </div>
          <div id="tabContent"></div>
        </section>
      </div>`;
    await renderTab(c);
  }

  async function renderTab(c) {
    const box = document.getElementById("tabContent");
    if (state.tab === "reserve") {
      const date = nextOpenDay(c);
      box.innerHTML = `
        <form id="reserveForm" class="form" novalidate>
          <label>${esc(t("reserve.name"))} *<input name="name" required autocomplete="name"></label>
          <label>${esc(t("reserve.phone"))} *<input name="phone" required type="tel" autocomplete="tel" placeholder="010-0000-0000"></label>
          <label>${esc(t("reserve.procedure"))} *
            <select name="procedure" required>${c.procedures.map(p => `<option value="${p.key}">${esc(L(PROCEDURES[p.key]))}</option>`).join("")}</select>
          </label>
          <div class="row">
            <label>${esc(t("reserve.date"))} *<input name="date" type="date" required min="${todayISO(0)}" max="${todayISO(60)}" value="${date}"></label>
            <label>${esc(t("reserve.time"))} *<select name="time" required></select></label>
          </div>
          <p class="hint" id="dateHint"></p>
          <label>${esc(t("reserve.memo"))}<textarea name="memo" rows="2"></textarea></label>
          <button class="btn btn-primary" type="submit">${esc(t("reserve.submit"))}</button>
        </form>`;
      const form = document.getElementById("reserveForm");
      const refreshSlots = async () => {
        const d = form.date.value;
        const isClosed = d && c.closedDays.includes(new Date(d + "T00:00").getDay());
        document.getElementById("dateHint").textContent = isClosed ? t("reserve.closed") : "";
        const slots = timeSlots(c);
        let takenList = [];
        try { takenList = d ? await API.takenSlots(c.id, d) : []; } catch (e) { toast(t("common.serverError"), "error"); }
        const taken = slots.map(s => takenList.includes(s));
        const now = new Date();
        form.time.innerHTML = slots.map((s, i) => {
          const past = d === todayISO(0) && new Date(d + "T" + s) <= now;
          const disabled = isClosed || taken[i] || past;
          return `<option value="${s}" ${disabled ? "disabled" : ""}>${s}${taken[i] ? " ✕" : ""}</option>`;
        }).join("");
        const first = [...form.time.options].find(o => !o.disabled);
        if (first) form.time.value = first.value;
      };
      form.date.addEventListener("change", refreshSlots);
      await refreshSlots();
      form.addEventListener("submit", async e => {
        e.preventDefault();
        const data = Object.fromEntries(new FormData(form));
        const opt = form.time.selectedOptions[0];
        if (!data.name.trim() || !data.phone.trim() || !data.date || !data.time || !opt || opt.disabled) {
          toast(t("reserve.invalid"), "error");
          return;
        }
        if (c.closedDays.includes(new Date(data.date + "T00:00").getDay())) {
          toast(t("reserve.closed"), "error");
          return;
        }
        try {
          await API.createReservation(Object.assign({ clinicId: c.id }, data));
          toast(t("reserve.done"));
          updateReservationBadge();
          await refreshSlots();
          form.memo.value = "";
        } catch (err) {
          toast(errorText(err), "error");
          if (err.code === "slot_taken") await refreshSlots();
        }
      });
    } else if (state.tab === "rate") {
      box.innerHTML = `
        <form id="rateForm" class="form">
          <p class="muted">${esc(t("rate.label"))}</p>
          <div class="star-input" role="radiogroup" aria-label="${esc(t("rate.label"))}">
            ${[1, 2, 3, 4, 5].map(n => `<button type="button" role="radio" aria-checked="false" data-v="${n}" aria-label="${n}">★</button>`).join("")}
          </div>
          <label>${esc(t("rate.nickname"))}<input name="nick" maxlength="20" placeholder="guest"></label>
          <label>${esc(t("rate.comment"))}<textarea name="text" rows="3" maxlength="300"></textarea></label>
          <button class="btn btn-primary" type="submit">${esc(t("rate.submit"))}</button>
        </form>`;
      const form = document.getElementById("rateForm");
      let value = 0;
      const btns = [...form.querySelectorAll(".star-input button")];
      const paint = v => btns.forEach(b => {
        const on = +b.dataset.v <= v;
        b.classList.toggle("on", on);
        b.setAttribute("aria-checked", String(+b.dataset.v === value));
      });
      btns.forEach(b => {
        b.addEventListener("click", () => { value = +b.dataset.v; paint(value); });
        b.addEventListener("mouseenter", () => paint(+b.dataset.v));
      });
      form.querySelector(".star-input").addEventListener("mouseleave", () => paint(value));
      form.addEventListener("submit", async e => {
        e.preventDefault();
        if (!value) { toast(t("rate.need"), "error"); return; }
        try {
          await API.addReview(c.id, { rating: value, nick: form.nick.value.trim() || "guest", text: form.text.value.trim() });
        } catch (err) {
          toast(errorText(err), "error");
          return;
        }
        toast(t("rate.done"));
        await loadClinics();
        renderList();
        state.tab = "reviews";
        renderDetail();
      });
    } else {
      let reviews = [];
      try { reviews = await API.listReviews(c.id); } catch (e) { toast(t("common.serverError"), "error"); }
      box.innerHTML = reviews.length ? `<ul class="reviews">${reviews.map(r => `
        <li>
          <div class="rating-row">${stars(r.rating)} <strong>${esc(r.nick)}</strong>
            ${r.mine ? `<span class="tag">${esc(t("reviews.mine"))}</span>` : ""}</div>
          ${(typeof r.text === "string" ? r.text : L(r.text)) ? `<p>${esc(typeof r.text === "string" ? r.text : L(r.text))}</p>` : ""}
        </li>`).join("")}</ul>` : `<p class="muted">${esc(t("reviews.none"))}</p>`;
    }
  }

  /* ---------- 내 예약 ---------- */
  async function renderReservations() {
    let list = [];
    try { list = await API.listReservations(); } catch (e) { toast(t("common.serverError"), "error"); }
    if (!list.length) {
      el.resList.innerHTML = `<p class="muted">${esc(t("myres.empty"))}</p>`;
      return;
    }
    el.resList.innerHTML = `<ul class="res-list">${list.map(r => {
      const c = state.clinics.find(x => x.id === r.clinicId);
      return `<li>
        <div>
          <strong>${esc(c ? L(c.name) : r.clinicId)}</strong>
          <p class="muted">${esc(r.date)} ${esc(r.time)} · ${esc(L(PROCEDURES[r.procedure]))}</p>
          <p class="muted">${esc(r.name)} · ${esc(r.phone)}</p>
        </div>
        <button class="btn btn-ghost" type="button" data-cancel="${r.id}">${esc(t("myres.cancel"))}</button>
      </li>`;
    }).join("")}</ul>`;
  }

  async function updateReservationBadge() {
    let n = 0;
    try { n = (await API.listReservations()).length; } catch (e) {}
    el.resCount.textContent = n;
    el.resCount.hidden = n === 0;
  }

  /* ---------- 오류 메시지 ---------- */
  function errorText(err) {
    const map = { slot_taken: "reserve.taken", clinic_closed: "reserve.closed", network: "common.serverError" };
    return t(map[err && err.code] || "reserve.invalid");
  }

  /* ---------- 토스트 ---------- */
  let toastTimer;
  function toast(msg, kind) {
    // 모달(dialog)은 최상위 레이어에 그려지므로, 열려 있으면 토스트를 그 안으로 옮깁니다.
    const host = [el.modal, el.resModal].find(m => m.open) || document.body;
    if (el.toast.parentNode !== host) host.appendChild(el.toast);
    el.toast.textContent = msg;
    el.toast.className = "toast show" + (kind === "error" ? " error" : "");
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => { el.toast.className = "toast"; }, 2800);
  }

  /* ---------- 이벤트 ---------- */
  function bind() {
    el.lang.addEventListener("change", e => setLang(e.target.value));
    el.search.addEventListener("input", e => { state.query = e.target.value; renderList(); });
    el.specialty.addEventListener("change", e => { state.specialty = e.target.value; renderList(); });
    el.sort.addEventListener("change", e => { state.sort = e.target.value; renderList(); });

    el.grid.addEventListener("click", e => {
      const card = e.target.closest(".card");
      if (card) openDetail(card.dataset.id);
    });
    el.grid.addEventListener("keydown", e => {
      const card = e.target.closest(".card");
      if (card && (e.key === "Enter" || e.key === " ")) { e.preventDefault(); openDetail(card.dataset.id); }
    });

    el.modalBody.addEventListener("click", e => {
      const tab = e.target.closest("[data-tab]");
      if (tab) { state.tab = tab.dataset.tab; renderDetail(); }
    });

    [el.modal, el.resModal].forEach(m => {
      m.addEventListener("click", e => {
        if (e.target === m || e.target.closest("[data-close]")) m.close();
      });
    });

    el.resBtn.addEventListener("click", async () => {
      await renderReservations();
      el.resModal.showModal();
    });
    el.resList.addEventListener("click", async e => {
      const btn = e.target.closest("[data-cancel]");
      if (!btn || !confirm(t("myres.cancelConfirm"))) return;
      try { await API.cancelReservation(btn.dataset.cancel); } catch (err) { toast(errorText(err), "error"); return; }
      toast(t("myres.canceled"));
      await renderReservations();
      updateReservationBadge();
    });
  }

  async function init() {
    try { await loadClinics(); } catch (e) { state.clinics = []; }
    applyStaticText();
    bind();
    renderList();
    if (!state.clinics.length && API.mode === "server") toast(t("common.serverError"), "error");
    updateReservationBadge();
  }
  init();
})();

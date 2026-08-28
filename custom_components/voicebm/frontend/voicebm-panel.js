// VoiceBM speaker-management panel (native HA web component).
// Talks to the integration over HA's authenticated WebSocket connection —
// no iframe, same-origin, HTTPS-native. `hass` is set as a property by the HA
// frontend when the panel loads.

class VoiceBMPanel extends HTMLElement {
  constructor() {
    super();
    this._hass = null;
    this._data = { enrolled: [], pending: [] };
    this._mergeSel = new Set();
    this._rendered = false;
    this._busy = false;
  }

  set hass(hass) {
    const first = !this._hass;
    this._hass = hass;
    if (first) {
      this._renderShell();
      this._refresh();
    }
  }
  get hass() { return this._hass; }

  connectedCallback() { if (this._hass && !this._rendered) { this._renderShell(); this._refresh(); } }

  async _ws(msg) {
    return this._hass.connection.sendMessagePromise(msg);
  }

  async _refresh() {
    try {
      const res = await this._ws({ type: "voicebm/list" });
      this._data = res || { enrolled: [], pending: [] };
    } catch (e) {
      this._data = { enrolled: [], pending: [], error: String(e && e.message || e) };
    }
    this._renderBody();
  }

  async _do(msg, confirmMsg) {
    if (this._busy) return;
    if (confirmMsg && !window.confirm(confirmMsg)) return;
    this._busy = true;
    try {
      await this._ws(msg);
      // engine republishes asynchronously; give it a moment then refresh
      setTimeout(() => { this._busy = false; this._refresh(); }, 1200);
    } catch (e) {
      this._busy = false;
      alert("Operation failed: " + (e && e.message || e));
    }
  }

  _renderShell() {
    this._rendered = true;
    this.innerHTML = `
      <style>
        :host, .vbm { display:block; }
        .vbm { padding:16px 16px 48px; max-width:900px; margin:0 auto;
               color:var(--primary-text-color); font-family:var(--paper-font-body1_-_font-family,sans-serif); }
        .vbm h1 { font-size:20px; font-weight:500; margin:8px 0 4px; }
        .vbm .sub { color:var(--secondary-text-color); font-size:13px; margin-bottom:16px; }
        .card { background:var(--card-background-color,#fff); border-radius:12px;
                box-shadow:var(--ha-card-box-shadow,0 2px 4px rgba(0,0,0,.1));
                padding:16px; margin-bottom:16px; }
        .card h2 { font-size:16px; font-weight:500; margin:0 0 12px; display:flex; align-items:center; gap:8px; }
        .row { display:flex; align-items:center; gap:8px; padding:8px 0;
               border-bottom:1px solid var(--divider-color,#eee); }
        .row:last-child { border-bottom:none; }
        .grow { flex:1 1 auto; min-width:0; }
        .name { font-weight:500; }
        .muted { color:var(--secondary-text-color); font-size:12px; }
        button { font:inherit; cursor:pointer; border:none; border-radius:8px; padding:6px 12px;
                 background:var(--primary-color,#03a9f4); color:var(--text-primary-color,#fff); }
        button.ghost { background:transparent; color:var(--primary-color,#03a9f4);
                       border:1px solid var(--primary-color,#03a9f4); }
        button.danger { background:var(--error-color,#db4437); }
        button:disabled { opacity:.5; cursor:default; }
        input { font:inherit; padding:6px 8px; border-radius:8px; border:1px solid var(--divider-color,#ccc);
                background:var(--card-background-color,#fff); color:var(--primary-text-color); }
        .toolbar { display:flex; gap:8px; align-items:center; margin-top:12px; flex-wrap:wrap; }
        .empty { color:var(--secondary-text-color); font-size:13px; padding:8px 0; }
        audio { height:32px; }
        .err { color:var(--error-color,#db4437); font-size:13px; }
        .chip { display:inline-flex; align-items:center; }
      </style>
      <div class="vbm">
        <h1>VoiceBM — Speakers</h1>
        <div class="sub">Identify, label, merge, and remove voices. Served through Home Assistant.</div>
        <div id="body"></div>
        <div class="toolbar">
          <button id="refresh" class="ghost">Refresh</button>
        </div>
      </div>`;
    this.querySelector("#refresh").addEventListener("click", () => this._refresh());
  }

  _renderBody() {
    const body = this.querySelector("#body");
    if (!body) return;
    const d = this._data;
    const audioBase = "/api/voicebm/pending_audio/";

    const pendingRows = (d.pending || []).map((p) => `
      <div class="row" data-pending="${p.id}">
        <audio class="grow" controls preload="metadata" src="${_esc(p.audio_url || (audioBase + encodeURIComponent(p.id)))}"></audio>
        <input type="text" placeholder="Name this speaker" data-name="${p.id}" style="width:160px" />
        <button data-enroll="${p.id}">Enroll</button>
      </div>`).join("") || `<div class="empty">No unrecognized voices waiting. Speak a command to your assistant to populate this.</div>`;

    const enrolledRows = (d.enrolled || []).map((e) => `
      <div class="row" data-person="${e.person_id}">
        <label class="chip"><input type="checkbox" data-merge="${e.person_id}" ${this._mergeSel.has(e.person_id) ? "checked" : ""}/></label>
        <div class="grow">
          <div class="name">${_esc(e.display_name)}</div>
          <div class="muted">${e.sample_count} sample${e.sample_count === 1 ? "" : "s"} · id: ${_esc(e.person_id)}</div>
        </div>
        <button class="ghost" data-samples="${e.person_id}">Samples</button>
        <button class="ghost" data-rename="${e.person_id}">Rename</button>
        <button class="danger" data-delete="${e.person_id}">Delete</button>
      </div>
      <div class="samples" data-samplesfor="${e.person_id}" style="display:none"></div>`).join("") || `<div class="empty">Nobody enrolled yet. Name a pending voice above to create the first speaker.</div>`;

    body.innerHTML = `
      ${d.error ? `<div class="card err">Couldn't read the gallery: ${_esc(d.error)}</div>` : ""}
      <div class="card">
        <h2>Pending voices</h2>
        ${pendingRows}
      </div>
      <div class="card">
        <h2>Enrolled speakers</h2>
        ${enrolledRows}
        <div class="toolbar" id="mergebar" style="${this._mergeSel.size >= 2 ? "" : "display:none"}">
          <input type="text" id="mergename" placeholder="Merged name" style="width:160px" />
          <button id="mergebtn">Merge ${this._mergeSel.size} selected</button>
        </div>
      </div>`;

    body.querySelectorAll("[data-enroll]").forEach((b) =>
      b.addEventListener("click", () => {
        const id = b.getAttribute("data-enroll");
        const nm = body.querySelector(`[data-name="${CSS.escape(id)}"]`).value.trim();
        if (!nm) { alert("Enter a name first."); return; }
        this._do({ type: "voicebm/enroll", pending_id: id, display_name: nm });
      }));

    body.querySelectorAll("[data-rename]").forEach((b) =>
      b.addEventListener("click", () => {
        const id = b.getAttribute("data-rename");
        const nm = window.prompt("New name for this speaker:");
        if (nm && nm.trim()) this._do({ type: "voicebm/rename", person_id: id, new_name: nm.trim() });
      }));

    body.querySelectorAll("[data-delete]").forEach((b) =>
      b.addEventListener("click", () => {
        const id = b.getAttribute("data-delete");
        this._do({ type: "voicebm/delete", person_id: id }, `Delete "${id}" permanently? This removes their voiceprints.`);
      }));

    body.querySelectorAll("[data-samples]").forEach((b) =>
      b.addEventListener("click", () => this._toggleSamples(b.getAttribute("data-samples"))));

    body.querySelectorAll("[data-merge]").forEach((c) =>
      c.addEventListener("change", () => {
        const id = c.getAttribute("data-merge");
        if (c.checked) this._mergeSel.add(id); else this._mergeSel.delete(id);
        const bar = body.querySelector("#mergebar");
        if (bar) bar.style.display = this._mergeSel.size >= 2 ? "" : "none";
        const btn = body.querySelector("#mergebtn");
        if (btn) btn.textContent = `Merge ${this._mergeSel.size} selected`;
      }));

    const mergeBtn = body.querySelector("#mergebtn");
    if (mergeBtn) mergeBtn.addEventListener("click", () => {
      const nm = body.querySelector("#mergename").value.trim();
      if (!nm) { alert("Enter a name for the merged identity."); return; }
      const ids = Array.from(this._mergeSel);
      this._do({ type: "voicebm/merge", person_ids: ids, new_name: nm },
        `Merge ${ids.length} identities into "${nm}"?`);
      this._mergeSel.clear();
    });
  }

  async _toggleSamples(pid) {
    const panel = this.querySelector(`[data-samplesfor="${CSS.escape(pid)}"]`);
    if (!panel) return;
    if (panel.style.display !== "none") { panel.style.display = "none"; panel.innerHTML = ""; return; }
    panel.style.display = "";
    panel.innerHTML = `<div class="muted" style="padding:8px 0 8px 34px">Loading samples…</div>`;
    try {
      const res = await this._ws({ type: "voicebm/list_samples", person_id: pid });
      this._renderSamples(panel, pid, (res && res.samples) || []);
    } catch (e) {
      panel.innerHTML = `<div class="err" style="padding:8px 0 8px 34px">Couldn't load samples: ${_esc(e && e.message || e)}</div>`;
    }
  }

  _renderSamples(panel, pid, samples) {
    const audioBase = "/api/voicebm/pending_audio/";  // reused for enrolled recordings too
    if (!samples.length) {
      panel.innerHTML = `<div class="muted" style="padding:8px 0 8px 34px">No individual samples recorded for this speaker.</div>`;
      return;
    }
    const rows = samples.map((s) => `
      <div class="row srow" data-eid="${_esc(s.event_id)}" style="padding-left:34px">
        <div class="grow muted">${_esc(s.enrolled_at || s.event_id)}${s.source ? " · " + _esc(s.source) : ""}</div>
        <button class="danger" data-delsample="${_esc(s.event_id)}">Delete sample</button>
      </div>`).join("");
    panel.innerHTML = `
      <div class="muted" style="padding:6px 0 6px 34px">Prune a sample if it captured the TV, music, or a visitor — the speaker keeps their other samples.</div>
      ${rows}`;
    panel.querySelectorAll("[data-delsample]").forEach((b) =>
      b.addEventListener("click", () => {
        const eid = b.getAttribute("data-delsample");
        if (!window.confirm("Delete this one voice sample? The speaker's other samples are kept.")) return;
        this._deleteSample(pid, eid, panel);
      }));
  }

  async _deleteSample(pid, eid, panel) {
    if (this._busy) return;
    this._busy = true;
    try {
      await this._ws({ type: "voicebm/delete_samples", person_id: pid, event_ids: [eid] });
      // reload this speaker's sample list, and refresh counts after the engine restarts
      const res = await this._ws({ type: "voicebm/list_samples", person_id: pid });
      this._renderSamples(panel, pid, (res && res.samples) || []);
      setTimeout(() => { this._busy = false; this._refresh(); }, 1500);
    } catch (e) {
      this._busy = false;
      alert("Delete failed: " + (e && e.message || e));
    }
  }
}

function _esc(s) {
  return String(s == null ? "" : s).replace(/[&<>"']/g, (c) =>
    ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}

customElements.define("voicebm-panel", VoiceBMPanel);

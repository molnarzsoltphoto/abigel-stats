// =============================================
// HISTORIKUS KÉSÉSI STATISZTIKA – Abigél integráció
// Ezt a kódot az abigel HTML-be kell beilleszteni
// a loadTrains() függvény után.
// =============================================

// A Beállítások oldalon mentett repo URL
function getHistUrl() {
  try { return localStorage.getItem('abigel_hist_url') || ''; } catch(e) { return ''; }
}
function setHistUrl(v) {
  try { localStorage.setItem('abigel_hist_url', v); } catch(e) {}
}

// CSV szöveg → tömb
function parseCSV(text) {
  const lines = text.trim().split('\n');
  if (lines.length < 2) return [];
  const headers = lines[0].split(',');
  return lines.slice(1).map(line => {
    const vals = line.split(',');
    const obj = {};
    headers.forEach((h, i) => obj[h.trim()] = vals[i]?.trim() || '');
    return obj;
  });
}

async function loadHistorikusStat() {
  const url = getHistUrl();
  const el = document.getElementById('hist-stat-wrap');
  if (!url) {
    if (el) el.innerHTML = '<div style="color:var(--gray400);font-size:12px;padding:8px;">Nincs beállítva stat repo URL. Add meg a Beállításoknál.</div>';
    return;
  }
  if (el) el.innerHTML = '<div style="color:var(--gray400);font-size:12px;padding:8px;">⏳ Betöltés...</div>';
  try {
    const r = await fetch(url + '?t=' + Date.now());
    if (!r.ok) throw new Error('HTTP ' + r.status);
    const text = await r.text();
    const rows = parseCSV(text);
    if (!rows.length) throw new Error('Üres adat');
    renderHistorikusStat(rows);
  } catch(e) {
    if (el) el.innerHTML = `<div style="color:#f87171;font-size:12px;padding:8px;">⚠️ Nem sikerült betölteni: ${e.message}</div>`;
  }
}

function renderHistorikusStat(rows) {
  const el = document.getElementById('hist-stat-wrap');
  if (!el) return;

  // Legutóbbi 30 nap
  const last30 = rows.slice(-30);
  const last7 = rows.slice(-7);

  // Átlagok
  const avg = arr => arr.length ? Math.round(arr.reduce((a,b) => a+b, 0) / arr.length) : 0;
  const pct30 = avg(last30.map(r => parseFloat(r.kesik_pct) || 0));
  const pct7  = avg(last7.map(r => parseFloat(r.kesik_pct) || 0));
  const avgDelay30 = avg(last30.map(r => parseFloat(r.atlag_perc) || 0));
  const avgDelay7  = avg(last7.map(r => parseFloat(r.atlag_perc) || 0));
  const maxEver = Math.max(...rows.map(r => parseFloat(r.max_perc) || 0));

  // Trend jel
  const trend = (a, b) => a > b ? `<span style="color:#ef4444">▲</span>` : a < b ? `<span style="color:#22c55e">▼</span>` : '–';

  // Legtöbb késés napja
  const worstDay = [...rows].sort((a,b) => (parseFloat(b.kesik_pct)||0) - (parseFloat(a.kesik_pct)||0))[0];

  // Mini sparkline az utolsó 30 napra
  const sparkData = last30.map(r => parseFloat(r.kesik_pct) || 0);
  const sparkMax = Math.max(...sparkData, 1);
  const sparkW = 200, sparkH = 36;
  const pts = sparkData.map((v, i) => {
    const x = Math.round(i / (sparkData.length - 1) * sparkW);
    const y = Math.round(sparkH - (v / sparkMax) * sparkH);
    return `${x},${y}`;
  }).join(' ');

  el.innerHTML = `
    <div style="background:#f8fafc;border-top:1px solid var(--gray100);padding:12px 18px;">
      <div style="font-size:11px;font-weight:700;color:var(--gray400);text-transform:uppercase;letter-spacing:.07em;margin-bottom:10px;">
        📊 Historikus statisztika · utolsó ${rows.length} nap
      </div>
      <div style="display:flex;gap:20px;flex-wrap:wrap;align-items:flex-start;">

        <div style="display:flex;gap:16px;flex-wrap:wrap;">
          <div class="mstat-item" style="flex-direction:column;align-items:flex-start;gap:2px;">
            <span class="mstat-lbl">Késési arány (30 nap átlag)</span>
            <span class="mstat-val">${pct30}% ${trend(pct30, pct7)}</span>
          </div>
          <div class="mstat-item" style="flex-direction:column;align-items:flex-start;gap:2px;">
            <span class="mstat-lbl">Késési arány (7 nap átlag)</span>
            <span class="mstat-val">${pct7}%</span>
          </div>
          <div class="mstat-item" style="flex-direction:column;align-items:flex-start;gap:2px;">
            <span class="mstat-lbl">Átl. késés perc (30 nap)</span>
            <span class="mstat-val">${avgDelay30} perc ${trend(avgDelay30, avgDelay7)}</span>
          </div>
          <div class="mstat-item" style="flex-direction:column;align-items:flex-start;gap:2px;">
            <span class="mstat-lbl">Átl. késés perc (7 nap)</span>
            <span class="mstat-val">${avgDelay7} perc</span>
          </div>
          <div class="mstat-item" style="flex-direction:column;align-items:flex-start;gap:2px;">
            <span class="mstat-lbl">Legnagyobb mért késés</span>
            <span class="mstat-val" style="color:#ef4444;">${maxEver} perc</span>
          </div>
          <div class="mstat-item" style="flex-direction:column;align-items:flex-start;gap:2px;">
            <span class="mstat-lbl">Legrosszabb nap</span>
            <span class="mstat-val" style="font-size:12px;">${worstDay?.datum || '–'} (${parseFloat(worstDay?.kesik_pct||0).toFixed(0)}%)</span>
          </div>
        </div>

        <div style="flex-shrink:0;">
          <div style="font-size:10px;color:var(--gray400);margin-bottom:4px;">Késési arány – 30 nap</div>
          <svg width="${sparkW}" height="${sparkH+4}" style="display:block;">
            <polyline points="${pts}" fill="none" stroke="#f97316" stroke-width="1.5" stroke-linejoin="round"/>
            <line x1="0" y1="${sparkH}" x2="${sparkW}" y2="${sparkH}" stroke="var(--gray100)" stroke-width="1"/>
          </svg>
        </div>

      </div>
    </div>
  `;
}

// ===== Smart Switch Logic =====
// Ersetzt den alten Power-Button durch einen Toggle, der den Status ANZEIGT und SCHALTET.
// Farb-Logik: gruen = ON/awake, rot = OFF/asleep, gelb = Pending (schaltet gerade).

const POLL_PENDING_MS   = 5000;            // schnelleres Polling waehrend des Schaltens (statt 30s)
const PENDING_TIMEOUT_MS = 4 * 60 * 1000;  // 4 Min Notbremse, falls die Kiste nicht reagiert

// laufende Schaltvorgaenge: mac -> { target, poll, timeout }
const pendingSwitches = {};

function ssT(k){var L='de';try{L=(window.wfGetLang&&window.wfGetLang())||'de';}catch(e){}var D={de:{online:'Online',offline:'Offline',up:'f\u00e4hrt hoch \u2026',down:'f\u00e4hrt runter \u2026',timeout:'Timeout'},en:{online:'Online',offline:'Offline',up:'booting \u2026',down:'shutting down \u2026',timeout:'Timeout'}};return (D[L]&&D[L][k])||D.de[k];}

function ssCheckStatus(sw) {
  const ip = sw.dataset.ipAddress;
  const tt = sw.dataset.testType;
  return fetch(`${check_status_url}?ip_address=${ip}&test_type=${tt}`)
    .then(r => r.text())
    .then(t => t.trim());
}

function ssSetVisual(sw, state) {
  const card  = sw.closest('.card');
  const label = card ? card.querySelector('.smart-status') : null;
  const dot   = card ? card.querySelector('.status-indicator') : null;

  sw.classList.remove('on', 'off', 'pending');
  if (label) label.classList.remove('on', 'off', 'pending', 'timeout');

  if (state === 'on') {
    sw.classList.add('on');
    sw.setAttribute('aria-checked', 'true');
    if (label) { label.innerHTML = '&#9679; ' + ssT('online'); label.classList.add('on'); }
    if (dot) { dot.classList.remove('asleep'); dot.classList.add('awake'); }
  } else if (state === 'off') {
    sw.classList.add('off');
    sw.setAttribute('aria-checked', 'false');
    if (label) { label.innerHTML = '&#9679; ' + ssT('offline'); label.classList.add('off'); }
    if (dot) { dot.classList.remove('awake'); dot.classList.add('asleep'); }
  } else { // 'up' | 'down' -> pending
    sw.classList.add('pending');
    if (label) {
      label.innerHTML = (state === 'up') ? '&#10227; ' + ssT('up')
                                         : '&#10227; ' + ssT('down');
      label.classList.add('pending');
    }
  }
}

function ssRelabelPending(sw, mac) {
  // Pending-Label in der AKTUELLEN Sprache neu rendern (z.B. nach Sprachwechsel),
  // ohne den laufenden Schaltvorgang zu stoeren. target -> 'up' (awake) | 'down' (asleep).
  const p = pendingSwitches[mac];
  if (!p) return;
  ssSetVisual(sw, p.target === 'awake' ? 'up' : 'down');
}

function ssRefresh(sw) {
  const mac = sw.dataset.macAddress;
  if (pendingSwitches[mac]) {                        // Pending-Poller kuemmert sich um den Status,
    ssRelabelPending(sw, mac);                       // aber Label-Sprache trotzdem aktualisieren
    return;
  }
  ssCheckStatus(sw)
    .then(status => {
      if (pendingSwitches[mac]) return;             // inzwischen pending -> nicht ueberschreiben
      ssSetVisual(sw, status === 'awake' ? 'on' : 'off');
    })
    .catch(() => {});
}

function refreshAllSwitches() {
  document.querySelectorAll('.smart-switch').forEach(ssRefresh);
}
window.refreshAllSwitches = refreshAllSwitches;

function ssClearPending(mac) {
  const p = pendingSwitches[mac];
  if (!p) return;
  clearInterval(p.poll);
  clearTimeout(p.timeout);
  delete pendingSwitches[mac];
}

function ssFlashTimeout(sw) {
  const card  = sw.closest('.card');
  const label = card ? card.querySelector('.smart-status') : null;
  if (label) {
    label.classList.add('timeout');
    label.innerHTML = '&#9888; ' + ssT('timeout');
  }
  setTimeout(() => { ssRefresh(sw); }, 3500);       // danach echten Status zeigen
}

function ssOnClick(sw) {
  const mac = sw.dataset.macAddress;
  if (pendingSwitches[mac]) return;                 // schon am Schalten -> ignorieren
  if (sw.classList.contains('pending')) return;

  const isOn   = sw.classList.contains('on');
  const target = isOn ? 'asleep' : 'awake';         // erwarteter Zielzustand

  // sofort optimistisch auf Pending (gelb)
  ssSetVisual(sw, isOn ? 'down' : 'up');

  // Aktion ausloesen: die Route entscheidet selbst WOL vs SOL anhand Live-Ping
  const body = new URLSearchParams();
  body.append('mac_address', mac);
  fetch(wol_or_sol_send_url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    body: body.toString()
  }).catch(() => {});

  // schnelles Polling bis der Zielzustand erreicht ist
  const poll = setInterval(() => {
    ssCheckStatus(sw).then(status => {
      if (status === target) {
        ssClearPending(mac);
        ssSetVisual(sw, target === 'awake' ? 'on' : 'off');
      }
    }).catch(() => {});
  }, POLL_PENDING_MS);

  // Notbremse: nach 4 Min aufgeben -> echter Status + kurzer Timeout-Hinweis
  const timeout = setTimeout(() => {
    ssClearPending(mac);
    ssCheckStatus(sw)
      .then(status => { ssSetVisual(sw, status === 'awake' ? 'on' : 'off'); ssFlashTimeout(sw); })
      .catch(() => { ssSetVisual(sw, isOn ? 'on' : 'off'); ssFlashTimeout(sw); });
  }, PENDING_TIMEOUT_MS);

  pendingSwitches[mac] = { target: target, poll: poll, timeout: timeout };
}

// Init: Klick-Handler binden + initialen Status holen
window.addEventListener('load', function () {
  document.querySelectorAll('.smart-switch').forEach(function (sw) {
    sw.addEventListener('click', function () { ssOnClick(sw); });
    ssRefresh(sw);
  });
});

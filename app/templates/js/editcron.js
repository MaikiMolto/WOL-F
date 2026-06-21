function loadCronSettings(macAddress, deviceName, wolSchedule, solSchedule) {
  const content = document.getElementById('cronSettingsContent');
  const lang = (window.wfGetLang && window.wfGetLang()) || 'de';
  const t = (window.wfCronTexts && window.wfCronTexts[lang]) || {};

  function ecT(key, fallback) {
    return (t && t[key]) || fallback;
  }

  // HTML-escape dynamic values before injecting via innerHTML (XSS guard).
  function ecEsc(s) {
    return String(s == null ? '' : s).replace(/[&<>"']/g, function (c) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c];
    });
  }

  const macSafe = ecEsc(macAddress);

  let html = '';
  html += '<div class="wf-cron-device">' + ecEsc(deviceName) + '</div>';
  html += '<input type="hidden" id="cronMacAddress" value="' + macSafe + '">';

  // WOL Section
  html += '<div class="wf-cron-section">';
  html += '<div class="wf-cron-row">';
  html += '<span class="wf-cron-label">' + ecT('wolSchedule', 'WOL Zeitplan') + '</span>';
  if (wolSchedule) {
    html += '<span class="wf-cron-current">' + ecEsc(wolSchedule) + '</span>';
    html += '<button class="wf-pill wf-pill-danger wf-pill-sm" onclick="deleteCron(\'' + macSafe + '\', \'wol\')">' + ecT('delete', 'Löschen') + '</button>';
  } else {
    html += '<span class="wf-cron-none">' + ecT('noSchedule', 'Kein Zeitplan') + '</span>';
  }
  html += '</div>';

  // WOL add form
  html += '<div class="wf-cron-add">';
  html += '<input type="text" id="wolCronInput" class="wf-cron-input" placeholder="' + ecT('cronPlaceholder', '0 8 * * 1-5') + '">';
  html += '<button class="wf-pill wf-pill-accent wf-pill-sm" onclick="addCron(\'' + macSafe + '\', \'wol\')">' + ecT('add', 'Hinzufügen') + '</button>';
  html += '</div>';
  html += '</div>';

  // SOL Section
  html += '<div class="wf-cron-section">';
  html += '<div class="wf-cron-row">';
  html += '<span class="wf-cron-label">' + ecT('solSchedule', 'SOL Zeitplan') + '</span>';
  if (solSchedule) {
    html += '<span class="wf-cron-current">' + ecEsc(solSchedule) + '</span>';
    html += '<button class="wf-pill wf-pill-danger wf-pill-sm" onclick="deleteCron(\'' + macSafe + '\', \'sol\')">' + ecT('delete', 'Löschen') + '</button>';
  } else {
    html += '<span class="wf-cron-none">' + ecT('noSchedule', 'Kein Zeitplan') + '</span>';
  }
  html += '</div>';

  // SOL add form
  html += '<div class="wf-cron-add">';
  html += '<input type="text" id="solCronInput" class="wf-cron-input" placeholder="' + ecT('cronPlaceholder', '0 23 * * *') + '">';
  html += '<button class="wf-pill wf-pill-accent wf-pill-sm" onclick="addCron(\'' + macSafe + '\', \'sol\')">' + ecT('add', 'Hinzufügen') + '</button>';
  html += '</div>';
  html += '</div>';

  content.innerHTML = html;
}

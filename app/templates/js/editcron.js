// WOL-F friendly schedule builder.
// Replaces the raw cron text field with: presets + weekday toggles + time picker
// + live preview. Generates a standard 5-field cron string under the hood and
// posts it to the existing /add_(wol|sol)_cron and /delete_(wol|sol)_cron routes.

(function () {
  function lang() { return (window.wfGetLang && window.wfGetLang()) || 'de'; }

  // cron day-of-week: 0=Sun .. 6=Sat. Week display order Mon..Sun.
  var WEEK_ORDER = [1, 2, 3, 4, 5, 6, 0];
  var DAY_LABELS = {
    de: { 1: 'Mo', 2: 'Di', 3: 'Mi', 4: 'Do', 5: 'Fr', 6: 'Sa', 0: 'So' },
    en: { 1: 'Mon', 2: 'Tue', 3: 'Wed', 4: 'Thu', 5: 'Fri', 6: 'Sat', 0: 'Sun' }
  };
  var T = {
    de: { wake: 'Wecken', sleep: 'Schlafen', current: 'Aktuell', none: 'Kein Zeitplan',
          workdays: 'Werktags', daily: 'Täglich', weekend: 'Wochenende',
          time: 'Uhrzeit', preview: 'Vorschau', plan: 'Planen', ok: 'OK', del: 'Löschen',
          pickHint: 'Bitte Tag(e) und Uhrzeit wählen.', weekendShort: 'Wochenende' },
    en: { wake: 'Wake', sleep: 'Sleep', current: 'Current', none: 'No schedule',
          workdays: 'Weekdays', daily: 'Daily', weekend: 'Weekend',
          time: 'Time', preview: 'Preview', plan: 'Schedule', ok: 'OK', del: 'Delete',
          pickHint: 'Please pick day(s) and a time.', weekendShort: 'Weekend' }
  };
  function tr(k) { var l = lang(); return (T[l] && T[l][k]) || (T.de[k]) || k; }

  function pad(n) { return (n < 10 ? '0' : '') + n; }
  function fmtTime(h, m, l) {
    if (l === 'en') {
      var ap = h < 12 ? 'AM' : 'PM';
      var h12 = h % 12; if (h12 === 0) h12 = 12;
      return h12 + ':' + pad(m) + ' ' + ap;
    }
    return pad(h) + ':' + pad(m);
  }
  function esc(s) {
    return String(s == null ? '' : s).replace(/[&<>"']/g, function (c) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c];
    });
  }

  // Expand a cron dow field (e.g. "1-5", "0,6", "*") into a Set of day numbers.
  function expandDow(dow) {
    var set = {};
    if (dow === '*' || dow === '') { WEEK_ORDER.forEach(function (d) { set[d] = true; }); return set; }
    dow.split(',').forEach(function (part) {
      var m = part.match(/^(\d)-(\d)$/);
      if (m) {
        var a = +m[1], b = +m[2];
        for (var i = a; i <= b; i++) set[i % 7] = true;
      } else if (/^\d$/.test(part)) {
        set[(+part) % 7] = true;
      }
    });
    return set;
  }

  // Parse "MM HH * * DOW". Returns null if it uses month/day-of-month (expert mode).
  function parseCron(cron) {
    if (!cron) return null;
    var f = String(cron).trim().split(/\s+/);
    if (f.length !== 5) return null;
    if (f[2] !== '*' || f[3] !== '*') return null; // dom/month set -> expert
    var minute = parseInt(f[0], 10), hour = parseInt(f[1], 10);
    if (isNaN(minute) || isNaN(hour)) return null;
    return { minute: minute, hour: hour, days: expandDow(f[4]) };
  }

  function daysToLabel(daysSet) {
    var sel = WEEK_ORDER.filter(function (d) { return daysSet[d]; });
    var L = DAY_LABELS[lang()];
    if (sel.length === 7) return tr('daily');
    if (sel.length === 5 && [1, 2, 3, 4, 5].every(function (d) { return daysSet[d]; })) return L[1] + '\u2013' + L[5];
    if (sel.length === 2 && daysSet[0] && daysSet[6]) return tr('weekendShort');
    return sel.map(function (d) { return L[d]; }).join(', ');
  }

  function prettySchedule(cron) {
    var p = parseCron(cron);
    if (!p) return esc(cron); // expert cron -> show raw
    return daysToLabel(p.days) + ' \u00b7 ' + fmtTime(p.hour, p.minute, lang());
  }

  // Build the cron string from the current UI state of a section.
  function buildCron(prefix) {
    var days = [].slice.call(document.querySelectorAll('#' + prefix + '-days .wf-day.active'))
      .map(function (b) { return parseInt(b.getAttribute('data-day'), 10); });
    var hhEl = document.getElementById(prefix + '-hh'), mmEl = document.getElementById(prefix + '-mm');
    var hhv = hhEl ? hhEl.value.trim() : '', mmv = mmEl ? mmEl.value.trim() : '';
    if (!days.length || hhv === '' || mmv === '') return null;
    var hour = parseInt(hhv, 10), minute = parseInt(mmv, 10);
    if (isNaN(hour) || isNaN(minute) || minute < 0 || minute > 59) return null;
    if (lang() === 'en') {
      if (hour < 1 || hour > 12) return null;
      var apEl = document.getElementById(prefix + '-ampm');
      var ap = apEl ? apEl.getAttribute('data-ampm') : 'AM';
      if (ap === 'PM') hour = (hour === 12 ? 12 : hour + 12);
      else hour = (hour === 12 ? 0 : hour);
    } else {
      if (hour < 0 || hour > 23) return null;
    }
    var ordered = WEEK_ORDER.filter(function (d) { return days.indexOf(d) !== -1; });
    var dow;
    if (ordered.length === 7) dow = '*';
    else if (ordered.length === 5 && [1, 2, 3, 4, 5].every(function (d) { return days.indexOf(d) !== -1; })) dow = '1-5';
    else dow = ordered.join(',');
    return minute + ' ' + hour + ' * * ' + dow;
  }

  function updatePreview(prefix) {
    var el = document.getElementById(prefix + '-preview');
    if (!el) return;
    var cron = buildCron(prefix);
    el.textContent = cron ? prettySchedule(cron) : '\u2014';
    el.classList.toggle('wf-cron-preview-empty', !cron);
  }

  function sectionHTML(prefix, titleKey, icon, mac, type, currentCron) {
    var L = DAY_LABELS[lang()];
    var pre = parseCron(currentCron);
    var dayBtns = WEEK_ORDER.map(function (d) {
      var on = pre && pre.days[d] ? ' active' : '';
      return '<button type="button" class="wf-day' + on + '" data-day="' + d + '">' + L[d] + '</button>';
    }).join('');
    var l = lang();
    var hhVal = '', mmVal = '', ampmVal = 'AM';
    if (pre) {
      mmVal = pad(pre.minute);
      if (l === 'en') {
        ampmVal = pre.hour < 12 ? 'AM' : 'PM';
        var h12v = pre.hour % 12; if (h12v === 0) h12v = 12;
        hhVal = String(h12v);
      } else { hhVal = pad(pre.hour); }
    }
    var hhMin = l === 'en' ? 1 : 0, hhMax = l === 'en' ? 12 : 23;
    var ampmToggle = l === 'en'
      ? '<div class="wf-ampm" id="' + prefix + '-ampm" data-ampm="' + ampmVal + '">'
        + '<button type="button" class="wf-ampm-btn' + (ampmVal === 'AM' ? ' active' : '') + '" data-ap="AM">AM</button>'
        + '<button type="button" class="wf-ampm-btn' + (ampmVal === 'PM' ? ' active' : '') + '" data-ap="PM">PM</button>'
        + '</div>'
      : '';

    var cur = '';
    if (currentCron) {
      cur = '<div class="wf-cron-current-row">' +
            '<span class="wf-cron-current-lbl">' + esc(tr('current')) + ':</span> ' +
            '<span class="wf-cron-current-val">' + prettySchedule(currentCron) + '</span>' +
            '</div>';
    } else {
      cur = '<div class="wf-cron-current-row wf-cron-none">' + esc(tr('none')) + '</div>';
    }

    var actionBtn = currentCron
      ? '<button type="button" class="wf-pill wf-pill-danger wf-pill-sm wf-cron-actbtn" data-mac="' + esc(mac) + '" data-type="' + type + '" data-act="del">' + esc(tr('del')) + '</button>'
      : '<button type="button" class="wf-pill wf-pill-ok wf-pill-sm wf-cron-actbtn" data-mac="' + esc(mac) + '" data-type="' + type + '" data-prefix="' + prefix + '" data-act="plan">' + esc(tr('ok')) + '</button>';

    return '' +
      '<div class="wf-cron-sec" id="' + prefix + '">' +
      '  <div class="wf-cron-sec-title">' + icon + '<span>' + esc(tr(titleKey)) + '</span></div>' +
      cur +
      '  <div class="wf-presets">' +
      '    <button type="button" class="wf-preset" data-preset="workdays">' + esc(tr('workdays')) + '</button>' +
      '    <button type="button" class="wf-preset" data-preset="daily">' + esc(tr('daily')) + '</button>' +
      '    <button type="button" class="wf-preset" data-preset="weekend">' + esc(tr('weekend')) + '</button>' +
      '  </div>' +
      '  <div class="wf-days" id="' + prefix + '-days">' + dayBtns + '</div>' +
      '  <div class="wf-time-row">' +
      '    <label class="wf-cron-lbl">' + esc(tr('time')) + '</label>' +
      '    <input type="number" inputmode="numeric" class="wf-time-num" id="' + prefix + '-hh" min="' + hhMin + '" max="' + hhMax + '" placeholder="HH" value="' + hhVal + '">' +
      '    <span class="wf-time-colon">:</span>' +
      '    <input type="number" inputmode="numeric" class="wf-time-num" id="' + prefix + '-mm" min="0" max="59" placeholder="MM" value="' + mmVal + '">' +
      ampmToggle +
      '  </div>' +
      '  <div class="wf-cron-foot">' +
      '    <span class="wf-cron-preview-lbl">' + esc(tr('preview')) + ':</span> ' +
      '    <span class="wf-cron-preview wf-cron-preview-empty" id="' + prefix + '-preview">\u2014</span>' +
      actionBtn +
      '  </div>' +
      '  <div class="wf-cron-hint" id="' + prefix + '-hint"></div>' +
      '</div>';
  }

  // Signature matches the (fixed) call in wol_form.html: (mac, name, wolCron, solCron)
  window.loadCronSettings = function (macAddress, deviceName, wolSchedule, solSchedule) {
    var content = document.getElementById('cronSettingsContent');
    if (!content) return;
    var html = '<div class="wf-cron-device">' + esc(deviceName) + '</div>' +
      '<div class="wf-cron-builder">' +
      sectionHTML('wfCronWol', 'wake', '<i class="fa-solid fa-sun"></i>', macAddress, 'wol', wolSchedule) +
      sectionHTML('wfCronSol', 'sleep', '<i class="fa-solid fa-moon"></i>', macAddress, 'sol', solSchedule) +
      '</div>';
    content.innerHTML = html;
    updatePreview('wfCronWol');
    updatePreview('wfCronSol');
  };

  function setDays(prefix, dayList) {
    [].slice.call(document.querySelectorAll('#' + prefix + '-days .wf-day')).forEach(function (b) {
      var d = parseInt(b.getAttribute('data-day'), 10);
      b.classList.toggle('active', dayList.indexOf(d) !== -1);
    });
  }

  // Event delegation (content is re-rendered each open).
  document.addEventListener('click', function (e) {
    var dayBtn = e.target.closest && e.target.closest('.wf-day');
    if (dayBtn) {
      dayBtn.classList.toggle('active');
      var sec = dayBtn.closest('.wf-cron-sec');
      if (sec) updatePreview(sec.id);
      return;
    }
    var preset = e.target.closest && e.target.closest('.wf-preset');
    if (preset) {
      var sec2 = preset.closest('.wf-cron-sec');
      if (!sec2) return;
      var p = preset.getAttribute('data-preset');
      var map = { workdays: [1, 2, 3, 4, 5], daily: [0, 1, 2, 3, 4, 5, 6], weekend: [0, 6] };
      setDays(sec2.id, map[p] || []);
      updatePreview(sec2.id);
      return;
    }
    var apb = e.target.closest && e.target.closest('.wf-ampm-btn');
    if (apb) {
      var apw = apb.closest('.wf-ampm');
      if (apw) {
        apw.setAttribute('data-ampm', apb.getAttribute('data-ap'));
        [].slice.call(apw.querySelectorAll('.wf-ampm-btn')).forEach(function (b) { b.classList.toggle('active', b === apb); });
        var apsec = apb.closest('.wf-cron-sec'); if (apsec) updatePreview(apsec.id);
      }
      return;
    }
    var act = e.target.closest && e.target.closest('.wf-cron-actbtn');
    if (act) {
      if (act.getAttribute('data-act') === 'del') wfDeleteCron(act.getAttribute('data-mac'), act.getAttribute('data-type'));
      else wfPlanCron(act.getAttribute('data-mac'), act.getAttribute('data-type'), act.getAttribute('data-prefix'));
      return;
    }
  });

  document.addEventListener('input', function (e) {
    if (e.target && e.target.classList && e.target.classList.contains('wf-time-num')) {
      var sec = e.target.closest('.wf-cron-sec');
      if (sec) updatePreview(sec.id);
    }
  });

  function post(url, mac, extra) {
    var body = 'mac_address=' + encodeURIComponent(mac) + (extra || '');
    return fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
      body: body
    });
  }

  // Plan = replace the schedule of this type (one wake / one sleep time per device).
  window.wfPlanCron = function (mac, type, prefix) {
    var cron = buildCron(prefix);
    var hint = document.getElementById(prefix + '-hint');
    if (!cron) { if (hint) hint.textContent = tr('pickHint'); return; }
    if (hint) hint.textContent = '';
    var addUrl = type === 'wol' ? add_wol_cron_url : add_sol_cron_url;
    var delUrl = type === 'wol' ? delete_wol_cron_url : delete_sol_cron_url;
    post(delUrl, mac)
      .then(function () { return post(addUrl, mac, '&cron_request=' + encodeURIComponent(cron)); })
      .then(function () { location.reload(); })
      .catch(function () { location.reload(); });
  };

  window.wfDeleteCron = function (mac, type) {
    var delUrl = type === 'wol' ? delete_wol_cron_url : delete_sol_cron_url;
    post(delUrl, mac).then(function () { location.reload(); }).catch(function () { location.reload(); });
  };

  // Expose the human-readable formatter and prettify the cron labels shown on
  // the device cards (so the card matches the friendly dialog instead of raw cron).
  window.wfPrettySchedule = prettySchedule;
  window.wfPrettifyCards = function () {
    [].slice.call(document.querySelectorAll('.wf-sched[data-cron]')).forEach(function (el) {
      var c = el.getAttribute('data-cron');
      if (c) el.textContent = prettySchedule(c);
    });
  };
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', window.wfPrettifyCards);
  } else {
    window.wfPrettifyCards();
  }
})();

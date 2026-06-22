function wfCardData(card) {
  const sw = card.querySelector('.smart-switch');
  const nameEl = card.querySelector('.title-sortable .sortable');
  return {
    name: (nameEl ? nameEl.textContent : '').trim(),
    ip: sw ? (sw.dataset.ipAddress || '') : '',
    mac: sw ? (sw.dataset.macAddress || '') : ''
  };
}

function filterComputers() {
  const query = document.querySelector('.search-input').value.toLowerCase();
  const cards = document.querySelectorAll('.computer-card');

  cards.forEach(card => {
    const d = wfCardData(card);
    if (d.name.toLowerCase().includes(query) ||
        d.ip.toLowerCase().includes(query) ||
        d.mac.toLowerCase().includes(query)) {
      card.classList.remove('hidden'); // Show card
    } else {
      card.classList.add('hidden'); // Hide card
    }
  });
}

// Attach the filter function to the input event
document.querySelector('.search-input').addEventListener('input', filterComputers);

function clearSearchInput() {
  const searchInput = document.querySelector('.search-input');
  searchInput.value = '';
  filterComputers(); // Reset the filter
}

function ipToNumber(ip) {
  const parts = String(ip).split('.');
  if (parts.length !== 4) return 0;
  // Use *256 (not <<8) to avoid 32-bit signed overflow for IPs > 127.x
  return parts.reduce((acc, octet) => (acc * 256) + (Number(octet) || 0), 0);
}

function sortComputers(criteria) {
  try { localStorage.setItem('wfSort', criteria); } catch (e) {}
  const cardsContainer = document.querySelector('.row.row-sortable');
  const cards = Array.from(cardsContainer.children); // Convert NodeList to Array

  // Update the active class in the dropdown
  const dropdownItems = document.querySelectorAll('.dropdown-item');
  dropdownItems.forEach(item => item.classList.remove('active'));

  // Sort the cards based on the selected criteria (raw values from data-*)
  cards.sort((a, b) => {
    const da = wfCardData(a);
    const db = wfCardData(b);

    switch (criteria) {
      case 'name':
        if (dropdownItems[0]) dropdownItems[0].classList.add('active');
        return da.name.toLowerCase().localeCompare(db.name.toLowerCase());

      case 'ip':
        if (dropdownItems[1]) dropdownItems[1].classList.add('active');
        return ipToNumber(da.ip) - ipToNumber(db.ip);

      case 'mac':
        if (dropdownItems[2]) dropdownItems[2].classList.add('active');
        return da.mac.toLowerCase().localeCompare(db.mac.toLowerCase());
    }
    return 0;
  });

  // Clear the current cards and append sorted cards
  cardsContainer.innerHTML = '';
  cards.forEach(card => cardsContainer.appendChild(card));
  setTimeout(function () { try { var tgl = document.querySelector('.wf-sortbtn'); if (tgl && window.bootstrap) { window.bootstrap.Dropdown.getOrCreateInstance(tgl).hide(); } var dd = document.querySelector('.wf-sort .dropdown-menu'); if (dd) dd.classList.remove('show'); } catch (e) {} }, 0);
}

// Restore the last-used sort on load (default: name)
(function () {
  function applyStoredSort() {
    var s = 'name';
    try { s = localStorage.getItem('wfSort') || 'name'; } catch (e) {}
    if (typeof sortComputers === 'function') sortComputers(s);
  }
  if (document.readyState === 'loading') { document.addEventListener('DOMContentLoaded', applyStoredSort); } else { applyStoredSort(); }
})();

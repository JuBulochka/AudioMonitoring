(function () {
  var selRegion = document.getElementById('sel_region');
  var selField  = document.getElementById('sel_field');
  var selSite   = document.getElementById('sel_site');

  // Snapshot all original option elements for cascade filtering
  var allFieldOpts  = Array.from(selField.options).slice(1).map(function(o){ return o.cloneNode(true); });
  var allSiteOpts   = Array.from(selSite.options).slice(1).map(function(o){ return o.cloneNode(true); });

  // ── Cascade filter helpers ────────────────────────────────────────
  function filterSelect(sel, allOpts, parentVal, dataAttr) {
    var saved = sel.value;
    sel.innerHTML = sel.options[0].outerHTML;
    allOpts.forEach(function(opt) {
      if (!parentVal || String(opt.dataset[dataAttr] || '') === String(parentVal)) {
        sel.appendChild(opt.cloneNode(true));
      }
    });
    if (saved && Array.from(sel.options).some(function(o){ return o.value === saved; })) {
      sel.value = saved;
    }
  }

  function filterDevices(siteId) {
    var items   = document.querySelectorAll('#deviceMenu .dev-item[data-site]');
    var anyVis  = false;
    items.forEach(function(item) {
      var chk = item.querySelector('.device-chk');
      var matches = !siteId || String(item.dataset.site) === String(siteId);
      item.style.display = matches ? '' : 'none';
      if (!matches) chk.checked = false;
      else anyVis = true;
    });
    document.getElementById('noDevMsg').style.display = anyVis ? 'none' : '';
    updateDeviceBtn();
    updateBadge();
  }

  function updateDeviceBtn() {
    var checked = document.querySelectorAll('.device-chk:checked');
    var lbl = document.getElementById('deviceBtnLabel');
    var chkAll = document.getElementById('chkAll');
    if (checked.length === 0) {
      lbl.textContent = '— Все устройства';
      chkAll.checked = false;
      chkAll.indeterminate = false;
    } else {
      var visibleChks = document.querySelectorAll('.device-chk:not([style*="display: none"])');
      var allChecked  = Array.from(visibleChks).every(function(c){ return c.checked; });
      chkAll.checked       = allChecked;
      chkAll.indeterminate = !allChecked;
      lbl.textContent = checked.length === 1
        ? checked[0].closest('.dev-item').querySelector('span').textContent.trim()
        : 'Выбрано: ' + checked.length + ' устр.';
    }
  }

  // ── Select-all checkbox ───────────────────────────────────────────
  document.getElementById('chkAll').addEventListener('change', function() {
    var visible = document.querySelectorAll('#deviceMenu .dev-item[data-site]:not([style*="display: none"]) .device-chk');
    visible.forEach(function(c){ c.checked = this.checked; }, this);
    updateDeviceBtn();
    updateBadge();
  });

  document.querySelectorAll('.device-chk').forEach(function(chk) {
    chk.addEventListener('change', function() {
      updateDeviceBtn();
      updateBadge();
    });
  });

  // ── Cascade handlers ─────────────────────────────────────────────
  function onRegionChange() {
    filterSelect(selField, allFieldOpts, selRegion.value, 'region');
    selField.value = '';
    onFieldChange();
  }

  function onFieldChange() {
    filterSelect(selSite, allSiteOpts, selField.value, 'field');
    selSite.value = '';
    onSiteChange();
  }

  function onSiteChange() {
    filterDevices(selSite.value);
  }

  selRegion.addEventListener('change', onRegionChange);
  selField.addEventListener('change',  onFieldChange);
  selSite.addEventListener('change',   onSiteChange);

  // ── Scope badge ───────────────────────────────────────────────────
  function updateBadge() {
    var parts = [];
    if (selRegion.value) parts.push(selRegion.options[selRegion.selectedIndex].text);
    if (selField.value)  parts.push(selField.options[selField.selectedIndex].text);
    if (selSite.value)   parts.push(selSite.options[selSite.selectedIndex].text);

    var checked = document.querySelectorAll('.device-chk:checked');
    if (checked.length === 1) {
      parts.push(checked[0].closest('.dev-item').querySelector('span').textContent.trim());
    } else if (checked.length > 1) {
      parts.push('Устройств: ' + checked.length);
    }

    var badge = document.getElementById('scopeBadge');
    if (parts.length) {
      document.getElementById('scopeText').textContent = parts.join(' / ');
      badge.style.display = '';
    } else {
      badge.style.display = 'none';
    }
  }

  // ── Clear all ─────────────────────────────────────────────────────
  document.getElementById('clearFilters').addEventListener('click', function() {
    selRegion.value = '';
    document.querySelectorAll('.device-chk').forEach(function(c){ c.checked = false; });
    document.getElementById('chkAll').checked = false;
    onRegionChange();
  });

  // ── Loading state ─────────────────────────────────────────────────
  var form = document.getElementById('reportForm');
  var btn  = document.getElementById('downloadBtn');
  form.addEventListener('submit', function() {
    btn.disabled = true;
    btn.innerHTML = '<span class="spinner-border spinner-border-sm" role="status"></span><span>Формирование...</span>';
    setTimeout(function() {
      btn.disabled = false;
      btn.innerHTML = '<i class="bi bi-file-earmark-arrow-down fs-5"></i><span>Скачать PDF-отчёт</span>';
    }, 12000);
  });
}());

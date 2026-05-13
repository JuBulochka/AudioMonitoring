(function () {
  // Update field count badge
  var chks = document.querySelectorAll('.field-chk');
  var countEl = document.getElementById('fieldCount');
  function updateCount() {
    countEl.textContent = document.querySelectorAll('.field-chk:checked').length;
  }
  chks.forEach(function(c) { c.addEventListener('change', updateCount); });

  // Highlight checked field labels
  chks.forEach(function(c) {
    function refresh() {
      var lbl = c.closest('.field-label');
      if (c.checked) {
        lbl.style.borderColor = '#238636';
        lbl.style.background  = 'var(--bg-hover)';
      } else {
        lbl.style.borderColor = 'var(--border-clr)';
        lbl.style.background  = 'var(--bg-card-header)';
      }
    }
    refresh();
    c.addEventListener('change', refresh);
  });
}());

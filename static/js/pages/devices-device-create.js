function toggleNew(select, newBlockId) {
  const block = document.getElementById(newBlockId);
  block.style.display = select.value ? "none" : "";
  block.querySelectorAll("input").forEach(i => i.disabled = !!select.value);
}
document.querySelectorAll("select[name$='_id']").forEach(s => toggleNew(s, s.getAttribute("onchange").match(/'([^']+)'/)[1]));

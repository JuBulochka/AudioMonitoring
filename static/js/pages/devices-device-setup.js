function copyCmd(btn) {
  const text = document.getElementById('installCmd').innerText.trim();
  navigator.clipboard.writeText(text).then(() => {
    const orig = btn.innerHTML;
    btn.innerHTML = '<i class="bi bi-check2 me-1"></i>Скопировано';
    setTimeout(() => { btn.innerHTML = orig; }, 1500);
  });
}

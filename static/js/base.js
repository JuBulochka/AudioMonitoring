const html           = document.documentElement;
const themeToggleBtn  = document.getElementById('themeToggle');
const themeToggleMob  = document.getElementById('themeToggleMobile');

function applyTheme(theme) {
  // Тема хранится локально, чтобы интерфейс не мигал при переходе между страницами.
  html.setAttribute('data-theme',    theme);
  html.setAttribute('data-bs-theme', theme);
  localStorage.setItem('pj-theme', theme);
  const icon  = theme === 'dark' ? '<i class="bi bi-sun"></i>' : '<i class="bi bi-moon"></i>';
  const title = theme === 'dark' ? 'Светлая тема' : 'Тёмная тема';
  themeToggleBtn.innerHTML = icon; themeToggleBtn.title = title;
  themeToggleMob.innerHTML = icon; themeToggleMob.title = title;
  document.dispatchEvent(new Event('themeChanged'));
}

applyTheme(localStorage.getItem('pj-theme') || 'light');

themeToggleBtn.addEventListener('click', () => {
  applyTheme(html.getAttribute('data-theme') === 'dark' ? 'light' : 'dark');
});
themeToggleMob.addEventListener('click', () => {
  applyTheme(html.getAttribute('data-theme') === 'dark' ? 'light' : 'dark');
});

function syncOffcanvasClose() {
  const btn = document.getElementById('offcanvasClose');
  if (!btn) return;
  if (html.getAttribute('data-theme') === 'dark') btn.classList.add('btn-close-white');
  else btn.classList.remove('btn-close-white');
}
syncOffcanvasClose();
document.addEventListener('themeChanged', syncOffcanvasClose);

const toastContainer = document.getElementById('toast-container');

function showToast(title, message, level, delay) {
  // Единая отрисовка toast-уведомлений для Django messages и WebSocket-событий.
  delay = delay || 5000;
  const iconMap = {
    success: 'bi-check-circle-fill',
    danger:  'bi-x-circle-fill',
    warning: 'bi-exclamation-triangle-fill',
    info:    'bi-info-circle-fill',
  };
  const colorMap = {
    success: '#1a7f37', danger: '#cf222e',
    warning: '#9a6700', info:   '#0969da',
  };
  const bgMap = {
    success: '#dafbe1', danger: '#ffebe9',
    warning: '#fff8c5', info:   '#ddf4ff',
  };
  const icon  = iconMap[level]  || iconMap.info;
  const color = colorMap[level] || colorMap.info;
  const bg    = bgMap[level]    || bgMap.info;

  const id  = 'toast-' + Date.now() + Math.random().toString(36).slice(2);
  const body = title
    ? `<div style="font-weight:600;margin-bottom:2px">${title}</div><div style="opacity:.85">${message}</div>`
    : `<div>${message}</div>`;

  const html = `
    <div id="${id}" class="toast pj-toast show"
         style="background:${bg};border:1px solid ${color}30"
         role="alert" aria-live="assertive">
      <div class="d-flex align-items-start p-3 gap-2">
        <i class="bi ${icon} mt-1 flex-shrink-0" style="color:${color};font-size:1rem"></i>
        <div class="flex-grow-1" style="color:#1f2328">${body}</div>
        <button type="button" class="btn-close btn-close ms-1 flex-shrink-0"
                style="font-size:.7rem" data-bs-dismiss="toast" aria-label="Close"></button>
      </div>
      <div style="height:3px;background:${color};border-radius:0 0 10px 10px;
                  animation:toastProgress ${delay}ms linear forwards"></div>
    </div>`;

  toastContainer.insertAdjacentHTML('beforeend', html);
  const el = document.getElementById(id);

  setTimeout(() => {
    el.style.transition = 'opacity .4s, transform .4s';
    el.style.opacity    = '0';
    el.style.transform  = 'translateX(20px)';
    setTimeout(() => el.remove(), 400);
  }, delay);

  el.querySelector('[data-bs-dismiss="toast"]').addEventListener('click', () => {
    el.style.transition = 'opacity .2s';
    el.style.opacity    = '0';
    setTimeout(() => el.remove(), 200);
  });
}

const toastStyle = document.createElement('style');
toastStyle.textContent = `
  @keyframes toastProgress {
    from { width: 100%; }
    to   { width: 0%; }
  }
  .pj-toast { animation: toastSlideIn .25s ease; }
  @keyframes toastSlideIn {
    from { opacity:0; transform: translateX(20px); }
    to   { opacity:1; transform: translateX(0); }
  }
`;
document.head.appendChild(toastStyle);

const djMsgEl = document.getElementById('django-messages');
if (djMsgEl) {
  try {
    JSON.parse(djMsgEl.textContent).forEach(m => {
      const lvl = m.tags.includes('error')   ? 'danger'
                : m.tags.includes('success') ? 'success'
                : m.tags.includes('warning') ? 'warning'
                : 'info';
      showToast('', m.text, lvl, 6000);
    });
  } catch(_) {}
}

const badge = document.getElementById('notif-badge');
function updateBadge(count) {
  if (count > 0) { badge.style.display = 'flex'; badge.textContent = count > 99 ? '99+' : count; }
  else { badge.style.display = 'none'; }
}
updateBadge(window.AppConfig.unreadNotificationsCount || 0);

if (window.AppConfig.isAuthenticated) {
// Уведомления приходят в реальном времени, без ручного обновления страницы.
const wsProto = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
const alertWs = new WebSocket(`${wsProto}//${window.location.host}/ws/alerts/`);
alertWs.onmessage = (e) => {
  const data = JSON.parse(e.data);
  if (data.type === 'alert') {
    const cnt = parseInt(badge.textContent || '0') + 1;
    updateBadge(cnt);
    const lvl = data.severity === 'critical' ? 'danger'
              : data.severity === 'warning'  ? 'warning'
              : 'info';
    showToast(data.title, data.message, lvl, 10000);
  }
};
}

function getCookie(name) {
  const v = document.cookie.match('(^|;)\\s*' + name + '\\s*=\\s*([^;]+)');
  return v ? v.pop() : '';
}

function markRead(id) {
  fetch(`/api/v1/alerts/notifications/${id}/read/`, {
    method: 'POST',
    headers: {'X-CSRFToken': getCookie('csrftoken')}
  }).then(() => {
    const row = document.getElementById(`notif-${id}`);
    row.style.background = '';
    row.querySelector('button')?.remove();
  });
}

function markAllRead() {
  fetch('/api/v1/alerts/notifications/mark-all-read/', {
    method: 'POST',
    headers: {'X-CSRFToken': getCookie('csrftoken')}
  }).then(() => location.reload());
}

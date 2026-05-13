function getCookie(name) {
  const v = document.cookie.match('(^|;)\\s*' + name + '\\s*=\\s*([^;]+)');
  return v ? v.pop() : '';
}

function changeStatus(taskId, newStatus, selectEl) {
  const orig = selectEl.dataset.orig || selectEl.value;
  fetch(`/api/v1/tasks/${taskId}/status/`, {
    method: 'PATCH',
    headers: {'Content-Type':'application/json','X-CSRFToken':getCookie('csrftoken')},
    body: JSON.stringify({status: newStatus})
  }).then(r => {
    if (r.ok) {
      const row = document.getElementById('task-row-' + taskId);
      if (row) {
        row.style.transition = 'background .3s';
        row.style.background = 'rgba(26,127,55,.12)';
        setTimeout(() => { row.style.background = ''; }, 800);
      }
      selectEl.dataset.orig = newStatus;
    } else {
      alert('Ошибка смены статуса');
      selectEl.value = orig;
    }
  }).catch(() => { alert('Ошибка сети'); selectEl.value = orig; });
}

let _doneTaskId = null;

function markDone(taskId) {
  _doneTaskId = taskId;
  document.getElementById('done-notes').value = '';
  new bootstrap.Modal(document.getElementById('doneModal')).show();
}

function submitDone() {
  const notes = document.getElementById('done-notes').value.trim();
  fetch(`/api/v1/tasks/${_doneTaskId}/status/`, {
    method: 'PATCH',
    headers: {'Content-Type':'application/json','X-CSRFToken':getCookie('csrftoken')},
    body: JSON.stringify({status:'done', result_notes: notes})
  }).then(r => {
    if (r.ok) {
      bootstrap.Modal.getInstance(document.getElementById('doneModal')).hide();
      location.reload();
    }
  });
}

function showCreateModal() {
  document.getElementById('c-error').style.display = 'none';
  new bootstrap.Modal(document.getElementById('createModal')).show();
}

function submitCreate() {
  const deviceId = document.getElementById('c-device').value;
  const title    = document.getElementById('c-title').value.trim();
  const desc     = document.getElementById('c-desc').value.trim();
  const priority = document.getElementById('c-priority').value;
  const date     = document.getElementById('c-date').value;
  const errEl    = document.getElementById('c-error');

  if (!deviceId) { showErr('Выберите устройство'); return; }
  if (!title)    { showErr('Введите название задачи'); return; }

  const btn = document.getElementById('c-submit-btn');
  btn.disabled = true;

  const payload = {device_id: deviceId, title, description: desc, priority};
  if (date) payload.scheduled_date = date + 'T00:00:00';

  fetch('/api/v1/tasks/', {
    method: 'POST',
    headers: {'Content-Type':'application/json','X-CSRFToken':getCookie('csrftoken')},
    body: JSON.stringify(payload)
  }).then(r => {
    btn.disabled = false;
    if (r.ok) {
      bootstrap.Modal.getInstance(document.getElementById('createModal')).hide();
      location.reload();
    } else {
      r.json().then(d => showErr(JSON.stringify(d)));
    }
  }).catch(() => { btn.disabled = false; showErr('Ошибка сети'); });
}

function showErr(msg) {
  const el = document.getElementById('c-error');
  el.textContent = msg;
  el.style.display = 'block';
}

function getCookie(name) {
  const v = document.cookie.match('(^|;)\\s*' + name + '\\s*=\\s*([^;]+)');
  return v ? v.pop() : '';
}

function addComment() {
  const text = document.getElementById('commentText').value.trim();
  if (!text) return;
  fetch(`/api/v1/incidents/${INCIDENT_ID}/comments/`, {
    method: 'POST',
    headers: {'Content-Type':'application/json', 'X-CSRFToken': getCookie('csrftoken')},
    body: JSON.stringify({text})
  }).then(() => location.reload());
}

function setStatus(status) {
  fetch(`/api/v1/incidents/${INCIDENT_ID}/status/`, {
    method: 'PATCH',
    headers: {'Content-Type':'application/json', 'X-CSRFToken': getCookie('csrftoken')},
    body: JSON.stringify({status})
  }).then(() => location.reload());
}

function submitStatus() {
  const status = document.getElementById('newStatus').value;
  const comment = document.getElementById('statusComment').value;
  const resolution_notes = document.getElementById('resolutionNotes').value;
  fetch(`/api/v1/incidents/${INCIDENT_ID}/status/`, {
    method: 'PATCH',
    headers: {'Content-Type':'application/json', 'X-CSRFToken': getCookie('csrftoken')},
    body: JSON.stringify({status, comment, resolution_notes})
  }).then(() => location.reload());
}

function addTask() {
  const title = document.getElementById('taskTitle').value.trim();
  if (!title) { alert('Введите название задачи'); return; }
  const priority = document.getElementById('taskPriority').value;
  const description = document.getElementById('taskDesc').value.trim();
  fetch(`/api/v1/incidents/${INCIDENT_ID}/tasks/`, {
    method: 'POST',
    headers: {'Content-Type': 'application/json', 'X-CSRFToken': getCookie('csrftoken')},
    body: JSON.stringify({title, priority, description})
  }).then(r => {
    if (r.ok) {
      bootstrap.Modal.getInstance(document.getElementById('taskModal')).hide();
      location.reload();
    } else {
      r.json().then(d => alert('Ошибка: ' + JSON.stringify(d)));
    }
  });
}

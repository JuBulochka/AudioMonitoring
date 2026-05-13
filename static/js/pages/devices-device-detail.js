function changeStatus() {
  const status = document.getElementById('newStatusSelect').value;
  const reason = document.getElementById('statusReason').value;
  fetch(`/api/v1/devices/${DEVICE_ID}/status/`, {
    method: 'PATCH',
    headers: {'Content-Type':'application/json','X-CSRFToken': getCookie('csrftoken')},
    body: JSON.stringify({status, reason})
  }).then(r => r.json()).then(data => {
    if (data.success) location.reload();
    else alert('Ошибка: ' + JSON.stringify(data));
  });
}

function addComment() {
  const text = document.getElementById('commentText').value.trim();
  if (!text) return;
  fetch(`/api/v1/devices/${DEVICE_ID}/comments/`, {
    method: 'POST',
    headers: {'Content-Type':'application/json','X-CSRFToken': getCookie('csrftoken')},
    body: JSON.stringify({text})
  }).then(r => r.json()).then(() => location.reload());
}


function showPacketDetail(id, dt, cls, score, sev) {
  const body = document.getElementById('packetOffcanvasBody');
  body.innerHTML = `<p class="text-muted mb-1" style="font-size:.75rem">Загрузка...</p>`;
  new bootstrap.Offcanvas(document.getElementById('packetOffcanvas')).show();

  fetch(`/api/v1/packets/${id}/`)
    .then(r => r.json())
    .then(p => {
      const scores = (p.class_scores || []).sort((a,b) => b.score - a.score);
      const _cs = getComputedStyle(document.documentElement);
      const _muted = _cs.getPropertyValue('--txt-muted').trim();
      const _dim   = _cs.getPropertyValue('--txt-dim').trim();
      const _prim  = _cs.getPropertyValue('--txt-primary').trim();
      const _border = _cs.getPropertyValue('--border-clr').trim();
      const _warn  = _cs.getPropertyValue('--warning').trim();

      const scoresHtml = scores.map(s => `
        <div class="d-flex align-items-center gap-2 mb-1">
          <div style="width:130px; font-size:.78rem; color:${s.threshold_exceeded ? _warn : _muted}">${s.audio_class_display}</div>
          <div class="progress flex-grow-1" style="height:5px;">
            <div class="progress-bar ${s.threshold_exceeded?'bg-warning':'bg-secondary'}" style="width:${(s.score*100).toFixed(1)}%"></div>
          </div>
          <div style="width:40px; font-size:.75rem; text-align:right; color:${_prim}">${(s.score*100).toFixed(1)}%</div>
        </div>`).join('');

      body.innerHTML = `
        <div class="mb-3">
          <div style="font-size:.72rem; color:${_dim}">Время записи</div>
          <div style="font-family:monospace; font-size:.85rem; color:${_prim}">${dt}</div>
        </div>
        <div class="mb-3">
          <div style="font-size:.72rem; color:${_dim}">Severity / Класс</div>
          <div><span class="sev-${p.severity}">${p.severity_display}</span> · ${p.dominant_class_display} (${(p.dominant_class_score*100).toFixed(1)}%)</div>
        </div>
        <div class="mb-3">
          <div style="font-size:.72rem; color:${_dim}; margin-bottom:4px">Распределение классов</div>
          <div class="mt-1">${scoresHtml || '<span class="text-muted">Нет данных</span>'}</div>
        </div>
        ${p.audio_file_url ? `
        <div class="mb-3">
          <div style="font-size:.72rem; color:${_dim}">Аудиозапись</div>
          <audio controls class="w-100 mt-1" preload="none">
            <source src="${p.audio_file_url}">
          </audio>
        </div>` : ''}
        <div class="mb-2">
          <div style="font-size:.72rem; color:${_dim}">CPU / Temp / Memory / Disk</div>
          <div style="font-size:.78rem; color:${_prim}; font-family:monospace">
            ${p.device_cpu_usage||'?'}% / ${p.device_cpu_temp||'?'}°C / ${p.device_memory_usage_pct||'?'}% / ${p.device_disk_usage_pct||'?'}%
          </div>
        </div>
        <hr style="border-color:${_border}">
        <div style="font-size:.72rem; color:${_dim}">Верификация оператора</div>
        <select id="opsSelect_${id}" class="form-select form-select-sm mt-1">
          <option value="reviewed" ${p.operator_status=='reviewed'?'selected':''}>Проверено</option>
          <option value="false_positive" ${p.operator_status=='false_positive'?'selected':''}>Ложное срабатывание</option>
          <option value="escalated" ${p.operator_status=='escalated'?'selected':''}>Передано</option>
        </select>
        <textarea id="opsNote_${id}" class="form-control form-control-sm mt-1" rows="2" placeholder="Примечание">${p.operator_notes||''}</textarea>
        <button class="btn btn-sm btn-outline-success mt-2 w-100" onclick="reviewPacket('${id}')">Сохранить</button>
      `;
    });
}

function reviewPacket(id) {
  const status = document.getElementById(`opsSelect_${id}`).value;
  const notes = document.getElementById(`opsNote_${id}`).value;
  fetch(`/api/v1/packets/${id}/review/`, {
    method: 'PATCH',
    headers: {'Content-Type':'application/json','X-CSRFToken': getCookie('csrftoken')},
    body: JSON.stringify({operator_status: status, operator_notes: notes})
  }).then(() => location.reload());
}


const classLabels = {'normal':'Норма','noise':'Шум','grinding':'Скрежет','squeak':'Скрип',
  'knock':'Стук','whistle':'Свист','foreign_sounds':'Посторонние','speech':'Речь','other_anomaly':'Иное'};
const labels = Object.keys(chartData).map(k => classLabels[k] || k);
const scores = Object.values(chartData).map(v => (v.avg_score * 100).toFixed(1));

if (labels.length > 0) {
  const rcs = getComputedStyle(document.documentElement);
  const rTickClr = rcs.getPropertyValue('--txt-muted').trim();
  const rGridClr = rcs.getPropertyValue('--border-clr').trim();

  new Chart(document.getElementById('classChart'), {
    type: 'radar',
    data: {
      labels,
      datasets: [{
        label: 'Средний балл (%)',
        data: scores,
        backgroundColor: 'rgba(88,166,255,.15)',
        borderColor: '#58a6ff',
        pointBackgroundColor: '#58a6ff',
        pointRadius: 3,
      }]
    },
    options: {
      responsive: true,
      plugins: { legend: { display: false } },
      scales: {
        r: {
          min: 0, max: 100,
          ticks: { color: rTickClr, font: { size: 9 }, stepSize: 25 },
          grid: { color: rGridClr },
          pointLabels: { color: rTickClr, font: { size: 10 } },
          angleLines: { color: rGridClr }
        }
      }
    }
  });
}

function getCookie(name) {
  const v = document.cookie.match('(^|;)\\s*' + name + '\\s*=\\s*([^;]+)');
  return v ? v.pop() : '';
}

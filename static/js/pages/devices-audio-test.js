var selectedFile  = null;
var elapsedTimer  = null;
var stepTimers    = [];

var fileInput    = document.getElementById('audio-file-input');
var filePickArea = document.getElementById('file-pick-area');
var fileNameEl   = document.getElementById('file-name');
var analyzeBtn   = document.getElementById('analyze-btn');
var uploadError  = document.getElementById('upload-error');
var emptyState   = document.getElementById('empty-state');
var loadingState = document.getElementById('loading-state');
var resultsArea  = document.getElementById('results-area');

fileInput.addEventListener('change', function() {
  if (fileInput.files && fileInput.files.length > 0) {
    selectedFile = fileInput.files[0];
    fileNameEl.textContent = '📎 ' + selectedFile.name + ' (' + (selectedFile.size/1024).toFixed(1) + ' KB)';
    fileNameEl.style.display = 'block';
    analyzeBtn.disabled = false;
    uploadError.classList.add('d-none');
  }
});

filePickArea.addEventListener('dragover', function(e) { e.preventDefault(); filePickArea.style.borderColor='#0969da'; });
filePickArea.addEventListener('dragleave', function() { filePickArea.style.borderColor=''; });
filePickArea.addEventListener('drop', function(e) {
  e.preventDefault();
  filePickArea.style.borderColor = '';
  var files = e.dataTransfer.files;
  if (files.length) {
    selectedFile = files[0];
    fileNameEl.textContent = '📎 ' + selectedFile.name + ' (' + (selectedFile.size/1024).toFixed(1) + ' KB)';
    fileNameEl.style.display = 'block';
    analyzeBtn.disabled = false;
    uploadError.classList.add('d-none');
  }
});

analyzeBtn.addEventListener('click', function() {
  if (!selectedFile) return;

  emptyState.style.display = 'none';
  resultsArea.style.display = 'none';
  loadingState.classList.remove('d-none');
  analyzeBtn.disabled = true;
  uploadError.classList.add('d-none');
  startProgress();

  var formData = new FormData();
  formData.append('audio_file', selectedFile);
  formData.append('csrfmiddlewaretoken', csrfToken);

  fetch(analyzeUrl, {
    method: 'POST',
    headers: { 'X-CSRFToken': csrfToken },
    body: formData
  })
  .then(function(resp) {
    return resp.json().then(function(data) {
      return { ok: resp.ok, status: resp.status, data: data };
    });
  })
  .then(function(result) {
    stopProgress();
    loadingState.classList.add('d-none');
    analyzeBtn.disabled = false;
    if (!result.ok) {
      showError(result.data.error || ('Ошибка сервера: ' + result.status));
      emptyState.style.display = '';
    } else {
      renderResults(result.data);
    }
  })
  .catch(function(err) {
    stopProgress();
    loadingState.classList.add('d-none');
    analyzeBtn.disabled = false;
    showError('Ошибка сети: ' + err.message);
    emptyState.style.display = '';
  });
});

var STEP_SCHEDULE = [
  { id: 'step-2', at: 2000,  pct: 25 },
  { id: 'step-3', at: 6000,  pct: 50 },
  { id: 'step-4', at: 11000, pct: 75 },
  { id: 'step-5', at: 20000, pct: 90 },
];

function activateStep(id) {
  var prev = document.querySelector('.step-active');
  if (prev) {
    prev.classList.remove('step-active');
    prev.style.opacity = '1';
    prev.querySelector('i').className = 'bi bi-check-circle-fill text-success';
  }
  var el = document.getElementById(id);
  if (el) {
    el.style.opacity = '1';
    el.style.fontWeight = '600';
    el.querySelector('i').className = 'bi bi-arrow-right-circle text-primary';
    el.classList.add('step-active');
  }
}

function startProgress() {
  ['step-1','step-2','step-3','step-4','step-5'].forEach(function(id, i) {
    var el = document.getElementById(id);
    if (!el) return;
    el.style.opacity = i === 0 ? '1' : '.4';
    el.style.fontWeight = i === 0 ? '600' : '';
    var icon = el.querySelector('i');
    icon.className = i === 0 ? 'bi bi-arrow-right-circle text-primary' : 'bi bi-circle';
    icon.style.color = i === 0 ? '' : 'var(--txt-dim)';
    el.classList.remove('step-active');
  });
  document.getElementById('step-1').classList.add('step-active');

  var bar = document.getElementById('progress-bar');
  var timerEl = document.getElementById('elapsed-timer');
  bar.style.width = '10%';
  bar.style.background = 'linear-gradient(90deg,#0969da,#58a6ff)';

  var elapsed = 0;
  elapsedTimer = setInterval(function() {
    elapsed++;
    timerEl.textContent = elapsed + 'с';
  }, 1000);

  stepTimers = [];
  STEP_SCHEDULE.forEach(function(s) {
    var t = setTimeout(function() {
      activateStep(s.id);
      document.getElementById('progress-bar').style.width = s.pct + '%';
    }, s.at);
    stepTimers.push(t);
  });
}

function stopProgress() {
  clearInterval(elapsedTimer);
  stepTimers.forEach(function(t) { clearTimeout(t); });
  stepTimers = [];
  var bar = document.getElementById('progress-bar');
  bar.style.width = '100%';
  bar.style.background = '#28a745';
}

function showError(msg) {
  uploadError.textContent = msg;
  uploadError.classList.remove('d-none');
}

var BAR_COLORS = {
  normal:'#28a745', knock:'#dc3545', squeak:'#fd7e14',
  whistle:'#0dcaf0', speech:'#6f42c1', grinding:'#e83e8c',
  noise:'#6c757d', foreign_sounds:'#20c997', other_anomaly:'#adb5bd'
};
var CLASS_LABELS = {
  normal:'Норма', noise:'Шум', grinding:'Скрежет', squeak:'Скрип',
  knock:'Стук', whistle:'Свист', foreign_sounds:'Посторонние звуки',
  speech:'Речь', other_anomaly:'Иная аномалия'
};

function renderResults(data) {
  resultsArea.style.display = 'block';

  var pct       = data.anomaly_pct || 0;
  var isAnomaly = data.is_anomaly;

  document.getElementById('res-filename').textContent = data.filename || '';

  var circle = document.getElementById('anomaly-circle');
  circle.className = 'anomaly-circle mx-auto ' + (pct < 40 ? 'ok' : pct < 70 ? 'warn' : 'crit');
  document.getElementById('anomaly-pct-val').textContent = pct + '%';

  var badge = document.getElementById('anomaly-badge');
  if (!isAnomaly) {
    badge.className = 'badge fs-6 px-3 py-2 mb-2 badge-normal';
    badge.innerHTML = '<i class="bi bi-check-circle-fill me-1"></i> Норма';
  } else if (pct < 70) {
    badge.className = 'badge fs-6 px-3 py-2 mb-2 badge-needs_inspection';
    badge.innerHTML = '<i class="bi bi-exclamation-circle-fill me-1"></i> Возможная аномалия';
  } else {
    badge.className = 'badge fs-6 px-3 py-2 mb-2 badge-site_visit_required';
    badge.innerHTML = '<i class="bi bi-x-circle-fill me-1"></i> Аномалия обнаружена';
  }

  document.getElementById('meta-filename').textContent  = data.filename || '—';
  document.getElementById('meta-filesize').textContent  = data.file_size_kb ? data.file_size_kb + ' KB' : '—';
  document.getElementById('meta-rawscore').textContent  = data.raw_score  != null ? data.raw_score  : '—';
  document.getElementById('meta-threshold').textContent = data.threshold  != null ? data.threshold  : '—';

  var sc = document.getElementById('class-scores-container');
  sc.innerHTML = '';
  var scores = data.class_scores || {};
  Object.entries(scores).sort(function(a,b){ return b[1]-a[1]; }).forEach(function(entry) {
    var cls = entry[0], val = entry[1];
    var p = Math.round(val * 100);
    var row = document.createElement('div');
    row.className = 'd-flex align-items-center gap-2 score-row';
    row.innerHTML = '<span class="score-label">' + (CLASS_LABELS[cls]||cls) + '</span>' +
      '<div class="score-bar-wrap"><div class="score-bar" style="width:'+p+'%;background:'+(BAR_COLORS[cls]||'#0969da')+'"></div></div>' +
      '<span class="score-pct">'+p+'%</span>';
    sc.appendChild(row);
  });

  var gc = document.getElementById('yamnet-groups-container');
  gc.innerHTML = '';
  var groups = data.yamnet_groups || {};
  Object.entries(groups).sort(function(a,b){ return b[1]-a[1]; }).forEach(function(entry) {
    var p = Math.round(entry[1] * 100);
    var row = document.createElement('div');
    row.className = 'd-flex align-items-center gap-2 score-row';
    row.innerHTML = '<span class="score-label">'+entry[0]+'</span>' +
      '<div class="score-bar-wrap"><div class="score-bar" style="width:'+p+'%;background:#0969da"></div></div>' +
      '<span class="score-pct">'+p+'%</span>';
    gc.appendChild(row);
  });

  var tc = document.getElementById('yamnet-top5-container');
  tc.innerHTML = '';
  (data.yamnet_top5 || []).forEach(function(item) {
    var chip = document.createElement('span');
    chip.className = 'yamnet-chip';
    chip.innerHTML = item[0] + ' <span class="sb">' + Math.round(item[1]*100) + '%</span>';
    tc.appendChild(chip);
  });
}

const WS_URL = (location.protocol === 'https:' ? 'wss' : 'ws')
             + '://' + location.host + '/ws/ssh/' + DEVICE_ID + '/';

// ── xterm.js setup ──────────────────────────────────────────────────────────
const term = new Terminal({
  theme: {
    background: '#0d1117',
    foreground: '#c9d1d9',
    cursor:     '#58a6ff',
    cursorAccent: '#0d1117',
    black:   '#484f58',
    red:     '#ff7b72',
    green:   '#3fb950',
    yellow:  '#d29922',
    blue:    '#58a6ff',
    magenta: '#bc8cff',
    cyan:    '#39c5cf',
    white:   '#b1bac4',
    brightBlack:   '#6e7681',
    brightRed:     '#ffa198',
    brightGreen:   '#56d364',
    brightYellow:  '#e3b341',
    brightBlue:    '#79c0ff',
    brightMagenta: '#d2a8ff',
    brightCyan:    '#56d4dd',
    brightWhite:   '#f0f6fc',
  },
  fontFamily: "'Cascadia Code', 'Fira Code', 'Consolas', monospace",
  fontSize: 14,
  lineHeight: 1.3,
  cursorBlink: true,
  allowProposedApi: true,
  scrollback: 5000,
});

const fitAddon = new FitAddon.FitAddon();
term.loadAddon(fitAddon);
term.loadAddon(new WebLinksAddon.WebLinksAddon());
term.open(document.getElementById('terminal'));
fitAddon.fit();

// Resize observer
const resizeObserver = new ResizeObserver(() => {
  fitAddon.fit();
  if (ws && ws.readyState === WebSocket.OPEN) {
    ws.send(JSON.stringify({ type: 'resize', cols: term.cols, rows: term.rows }));
  }
});
resizeObserver.observe(document.getElementById('terminal-container'));

// ── WebSocket ────────────────────────────────────────────────────────────────
let ws = null;

function connect() {
  setStatus('connecting', 'Подключение…');
  showOverlay('spinner', 'Подключение…', `Устанавливается SSH-соединение с ${DEVICE_SERIAL}`);

  ws = new WebSocket(WS_URL);
  ws.binaryType = 'arraybuffer';

  ws.onopen = () => {
    // Send current terminal size right away
    ws.send(JSON.stringify({ type: 'resize', cols: term.cols, rows: term.rows }));
  };

  ws.onmessage = (e) => {
    if (typeof e.data === 'string') {
      try {
        const msg = JSON.parse(e.data);
        if (msg.type === 'status') {
          handleStatus(msg.status, msg.message);
        }
      } catch(_) {}
    } else {
      // Binary: raw terminal output
      term.write(new Uint8Array(e.data));
    }
  };

  ws.onerror = () => {
    setStatus('error', 'Ошибка WebSocket');
  };

  ws.onclose = (e) => {
    if (e.code !== 1000 && e.code !== 4401) {
      setStatus('disconnected', 'Соединение закрыто');
      showOverlay('icon', 'Соединение закрыто',
        'SSH-сессия завершена. Нажмите «Переподключить» для нового сеанса.', true);
    }
  };

}

// Forward keyboard input — registered ONCE, not inside connect()
term.onData(data => {
  if (ws && ws.readyState === WebSocket.OPEN) {
    ws.send(new TextEncoder().encode(data));
  }
});

function handleStatus(status, message) {
  setStatus(status, message);
  if (status === 'connected') {
    hideOverlay();
    term.focus();
  } else if (status === 'error') {
    showOverlay('error', 'Ошибка подключения', message, true);
  } else if (status === 'disconnected') {
    showOverlay('icon', 'Сессия завершена', message, true);
  }
}

function setStatus(status, message) {
  const dot  = document.getElementById('statusDot');
  const text = document.getElementById('statusText');
  dot.className  = 'status-dot ' + status;
  text.className = 'status-text ' + status;
  text.textContent = message;
}

// ── Overlay ──────────────────────────────────────────────────────────────────
function showOverlay(type, title, msg, showRetry = false) {
  const ov = document.getElementById('overlay');
  ov.classList.remove('hidden');
  document.getElementById('overlaySpinner').style.display = type === 'spinner' ? 'block' : 'none';
  document.getElementById('overlayTitle').textContent = title;
  document.getElementById('overlayMsg').textContent   = msg;
  document.getElementById('retryBtn').style.display   = showRetry ? 'inline-block' : 'none';
}

function hideOverlay() {
  document.getElementById('overlay').classList.add('hidden');
}

// ── Actions ──────────────────────────────────────────────────────────────────
function reconnect() {
  if (ws) { try { ws.close(); } catch(_) {} }
  term.reset();
  connect();
}

function clearTerminal() {
  term.clear();
  term.focus();
}

// ── Init ─────────────────────────────────────────────────────────────────────
connect();

// Keep focus when clicking terminal area
document.getElementById('terminal-container').addEventListener('click', () => term.focus());

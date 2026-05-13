const overlayConnecting = document.getElementById("overlayConnecting");
const overlayError      = document.getElementById("overlayError");
const vncFrame          = document.getElementById("vnc-frame");
const statusDot         = document.getElementById("statusDot");
const statusPill        = document.getElementById("statusPill");
const errorMsg          = document.getElementById("errorMsg");

function setStatus(state) {
  const cfg = {
    connecting:   { color: "#58a6ff", text: "Подключение…",  cls: "connecting"   },
    connected:    { color: "#3fb950", text: "Подключено",     cls: "connected"    },
    disconnected: { color: "#f85149", text: "Отключено",      cls: "disconnected" },
    waiting:      { color: "#d29922", text: "Ожидание туннеля…", cls: ""          },
  };
  const s = cfg[state] || cfg.connecting;
  statusDot.style.background = s.color;
  statusPill.textContent = s.text;
  statusPill.className = "status-pill " + s.cls;
}

function showError(msg) {
  overlayConnecting.classList.add("hidden");
  overlayError.classList.remove("hidden");
  vncFrame.style.display = "none";
  if (msg) errorMsg.textContent = msg;
  setStatus("disconnected");
}

function loadVNC() {
  setStatus("connecting");
  overlayConnecting.classList.remove("hidden");
  overlayError.classList.add("hidden");
  vncFrame.style.display = "none";

  // Build noVNC URL with token routing
  // noVNC is proxied at /novnc/ by nginx
  const wsProto = location.protocol === "https:" ? "wss" : "ws";
  const wsHost  = location.host;

  // noVNC URL parameters:
  //   path     — websockify WebSocket path
  //   token    — our device UUID (routes to correct VNC port)
  //   autoconnect=true, resize=scale, password — optional
  const params = new URLSearchParams({
    path:        `novnc/websockify?token=${VNC_TOKEN}`,
    autoconnect: "true",
    resize:      "scale",
    show_dot:    "true",
    bell:        "false",
    logging:     "warn",
  });

  const novncUrl = `/novnc/vnc.html?${params}`;
  vncFrame.src = novncUrl;
  vncFrame.style.display = "block";

  // Listen for iframe load
  vncFrame.onload = () => {
    // Give noVNC a moment to attempt WebSocket connection
    setTimeout(() => {
      try {
        // Try to detect if noVNC loaded OK (same-origin check)
        const doc = vncFrame.contentDocument || vncFrame.contentWindow.document;
        if (doc && doc.readyState === "complete") {
          overlayConnecting.classList.add("hidden");
          setStatus("connected");
        }
      } catch (e) {
        // Cross-origin or other issue
        overlayConnecting.classList.add("hidden");
        setStatus("connected");
      }
    }, 2000);
  };

  vncFrame.onerror = () => {
    showError("Не удалось загрузить noVNC. Убедитесь, что контейнер novnc запущен.");
  };

  // Timeout: if frame doesn't load in 15 sec, show error
  setTimeout(() => {
    if (overlayConnecting && !overlayConnecting.classList.contains("hidden")) {
      showError(
        "Время ожидания истекло. VNC туннель не установлен — " +
        "убедитесь, что edge client запущен на устройстве."
      );
    }
  }, 15000);
}

function retryConnection() {
  loadVNC();
}

// Start connection on page load
loadVNC();

// ── API helpers ────────────────────────────────────────────────────────────

function getCsrf() {
  const m = document.cookie.match(/csrftoken=([^;]+)/);
  return m ? m[1] : CSRF_TOKEN;
}

async function api(method, url, body) {
  const opts = {
    method,
    headers: { "Content-Type": "application/json", "X-CSRFToken": getCsrf() },
  };
  if (body) opts.body = JSON.stringify(body);
  const r = await fetch(url, opts);
  return r;
}

// ── Output panel ───────────────────────────────────────────────────────────

const outputPlaceholder = document.getElementById("outputPlaceholder");
const outputSpinner     = document.getElementById("outputSpinner");
const outputPre         = document.getElementById("outputPre");
const outputTitle       = document.getElementById("outputTitle");
const outputBadge       = document.getElementById("outputBadge");
const outputDuration    = document.getElementById("outputDuration");
const spinnerLabel      = document.getElementById("spinnerLabel");

function showPlaceholder() {
  outputPlaceholder.style.display = "";
  outputSpinner.style.display = "none";
  outputPre.style.display = "none";
  outputBadge.style.display = "none";
  outputDuration.style.display = "none";
  outputTitle.textContent = "Вывод команды";
}

function showSpinner(label) {
  outputPlaceholder.style.display = "none";
  outputSpinner.style.display = "";
  outputPre.style.display = "none";
  spinnerLabel.textContent = label || "";
}

function showOutput(cmdLabel, status, text, durationSec) {
  outputPlaceholder.style.display = "none";
  outputSpinner.style.display = "none";
  outputPre.style.display = "";
  outputTitle.textContent = cmdLabel;

  const badgeCfg = {
    "completed": { bg: "#1b3a2d", color: "#3fb950", text: "Выполнено" },
    "failed":    { bg: "#3d1f1f", color: "#f85149", text: "Ошибка"    },
    "timeout":   { bg: "#3d2a1a", color: "#d29922", text: "Таймаут"   },
    "cancelled": { bg: "#21262d", color: "#8b949e", text: "Отменено"  },
  };
  const cfg = badgeCfg[status] || badgeCfg["completed"];
  outputBadge.style.cssText   = `display:inline;background:${cfg.bg};color:${cfg.color};font-size:.65rem`;
  outputBadge.className       = "badge ms-1";
  outputBadge.textContent     = cfg.text;

  if (durationSec !== null && durationSec !== undefined) {
    outputDuration.style.display = "";
    outputDuration.textContent   = durationSec + "с";
  }

  // Colorise: lines starting with ===
  outputPre.innerHTML = text
    .replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;")
    .split("\n")
    .map(line => {
      if (/^===/.test(line))
        return `<span style="color:#58a6ff;font-weight:700">${line}</span>`;
      if (/^(error|err\b|ERROR)/i.test(line))
        return `<span style="color:#f85149">${line}</span>`;
      if (/^(warn|warning)/i.test(line))
        return `<span style="color:#d29922">${line}</span>`;
      return line;
    })
    .join("\n");

  outputPre.scrollTop = outputPre.scrollHeight;
}

document.getElementById("clearOutputBtn").addEventListener("click", showPlaceholder);

// ── Send command ───────────────────────────────────────────────────────────

let pendingCommandKey   = null;
let pendingCommandLabel = null;
let activeCommandId     = null;
let pollInterval        = null;

document.querySelectorAll(".send-btn").forEach(btn => {
  btn.addEventListener("click", () => {
    const key     = btn.dataset.key;
    const label   = btn.dataset.label;
    const confirm = btn.dataset.confirm === "1";

    if (confirm) {
      pendingCommandKey   = key;
      pendingCommandLabel = label;
      document.getElementById("confirmCmdLabel").textContent = label;
      new bootstrap.Modal(document.getElementById("confirmModal")).show();
    } else {
      sendCommand(key, label);
    }
  });
});

document.getElementById("confirmSendBtn").addEventListener("click", () => {
  bootstrap.Modal.getInstance(document.getElementById("confirmModal")).hide();
  if (pendingCommandKey) sendCommand(pendingCommandKey, pendingCommandLabel);
});

async function sendCommand(key, label) {
  showSpinner(label);

  const r = await api("POST", "/api/v1/commands/", {
    device_id:   DEVICE_ID,
    command_key: key,
  });

  if (!r.ok) {
    const err = await r.json().catch(() => ({}));
    showOutput(label, "failed",
      "Ошибка отправки команды:\n" + (err.error || r.statusText), null);
    return;
  }

  const data = await r.json();
  activeCommandId = data.id;
  spinnerLabel.textContent = label + " — ожидаем ответа от Pi…";

  // Start polling for result
  clearInterval(pollInterval);
  pollInterval = setInterval(() => pollResult(key, label, activeCommandId), 2000);
}

async function pollResult(key, label, cmdId) {
  const r = await api("GET", `/api/v1/commands/${cmdId}/`);
  if (!r.ok) return;

  const d = await r.json();
  const terminal = ["completed", "failed", "timeout", "cancelled"];

  if (terminal.includes(d.status)) {
    clearInterval(pollInterval);
    activeCommandId = null;

    const text = d.output || d.error_message || "(нет вывода)";
    showOutput(label, d.status, text, d.duration_sec);
    loadHistory();
  }
}

// ── History ────────────────────────────────────────────────────────────────

const historyBody  = document.getElementById("historyBody");
const historyEmpty = document.getElementById("historyEmpty");

const STATUS_CFG = {
  pending:   { color: "#8b949e", icon: "bi-hourglass",       text: "Ожидает"   },
  running:   { color: "#58a6ff", icon: "bi-arrow-clockwise", text: "Выполняется" },
  completed: { color: "#3fb950", icon: "bi-check-circle",    text: "Выполнено" },
  failed:    { color: "#f85149", icon: "bi-x-circle",        text: "Ошибка"    },
  timeout:   { color: "#d29922", icon: "bi-clock-history",   text: "Таймаут"   },
  cancelled: { color: "#484f58", icon: "bi-dash-circle",     text: "Отменено"  },
};

async function loadHistory() {
  const r = await fetch(`/api/v1/commands/?device=${DEVICE_ID}`);
  if (!r.ok) return;
  const data = await r.json();

  if (!data.length) {
    historyEmpty.style.display = "";
    historyBody.innerHTML = "";
    return;
  }
  historyEmpty.style.display = "none";

  historyBody.innerHTML = data.slice(0, 30).map(cmd => {
    const cfg  = STATUS_CFG[cmd.status] || STATUS_CFG.completed;
    const date = new Date(cmd.created_at);
    const ts   = date.toLocaleTimeString("ru-RU", { hour: "2-digit", minute: "2-digit" })
               + " " + date.toLocaleDateString("ru-RU", { day: "2-digit", month: "2-digit" });
    const dur  = cmd.duration_sec != null ? `<span style="color:#484f58;font-size:.7rem"> ${cmd.duration_sec}с</span>` : "";

    return `<tr style="border-color:#30363d">
      <td style="color:#c9d1d9;padding:7px 12px;vertical-align:middle">
        <i class="bi ${cmd.icon} me-1" style="color:#8b949e;font-size:.8rem"></i>
        ${escHtml(cmd.label)}
      </td>
      <td style="padding:7px 12px;vertical-align:middle">
        <span style="color:${cfg.color};font-size:.78rem">
          <i class="bi ${cfg.icon} me-1"></i>${cfg.text}${dur}
        </span>
      </td>
      <td style="color:#8b949e;padding:7px 12px;vertical-align:middle;font-size:.73rem">${ts}</td>
      <td style="padding:7px 4px;vertical-align:middle;text-align:right">
        ${cmd.has_output
          ? `<button class="btn btn-sm view-output-btn"
                     data-id="${cmd.id}"
                     data-label="${escAttr(cmd.label)}"
                     data-status="${cmd.status}"
                     style="background:transparent;border-color:#30363d;color:#58a6ff;
                            font-size:.7rem;padding:2px 7px">
               <i class="bi bi-eye"></i>
             </button>`
          : ""
        }
        ${(cmd.status === "pending" || cmd.status === "running")
          ? `<button class="btn btn-sm cancel-btn"
                     data-id="${cmd.id}"
                     style="background:transparent;border-color:#30363d;color:#f85149;
                            font-size:.7rem;padding:2px 7px"
                     title="Отменить">
               <i class="bi bi-x-lg"></i>
             </button>`
          : ""
        }
      </td>
    </tr>`;
  }).join("");

  // View output buttons
  historyBody.querySelectorAll(".view-output-btn").forEach(btn => {
    btn.addEventListener("click", async () => {
      const r = await api("GET", `/api/v1/commands/${btn.dataset.id}/`);
      if (!r.ok) return;
      const d = await r.json();
      showOutput(d.label, d.status, d.output || d.error_message || "(нет вывода)", d.duration_sec);
      window.scrollTo({ top: 0, behavior: "smooth" });
    });
  });

  // Cancel buttons
  historyBody.querySelectorAll(".cancel-btn").forEach(btn => {
    btn.addEventListener("click", async () => {
      await api("POST", `/api/v1/commands/${btn.dataset.id}/cancel/`);
      loadHistory();
    });
  });
}

function escHtml(str) {
  return String(str).replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;");
}
function escAttr(str) {
  return String(str).replace(/"/g,"&quot;");
}

document.getElementById("refreshHistoryBtn").addEventListener("click", loadHistory);

// ── Init ───────────────────────────────────────────────────────────────────
loadHistory();

// Auto-refresh history every 10 seconds if there are running commands
setInterval(async () => {
  const hasRunning = historyBody.querySelector("tr [data-id]");
  if (hasRunning || activeCommandId) loadHistory();
}, 10000);

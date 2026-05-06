import React, { useState, useEffect, useCallback, useRef } from 'react';
import { useParams, Link } from 'react-router-dom';
import AppLayout from '@/components/Layout/AppLayout';
import Spinner from '@/components/UI/Spinner';
import { useApi } from '@/hooks/useApi';
import { getDevice } from '@/api/devices';
import {
  getCommandCatalog,
  getDeviceCommands,
  sendCommand,
  getCommandResult,
  CommandCatalogEntry,
} from '@/api/commands';
import { DeviceCommandItem } from '@/types';
import { formatDate, timeSince } from '@/utils/formatters';

const STATUS_COLOR: Record<string, string> = {
  pending: 'var(--txt-muted)',
  running: 'var(--info)',
  completed: 'var(--online-clr)',
  failed: 'var(--danger)',
  timeout: 'var(--warning)',
  cancelled: 'var(--txt-muted)',
};

const STATUS_LABEL: Record<string, string> = {
  pending: 'Ожидание',
  running: 'Выполняется',
  completed: 'Выполнено',
  failed: 'Ошибка',
  timeout: 'Таймаут',
  cancelled: 'Отменено',
};

export default function Commands() {
  const { deviceId } = useParams<{ deviceId: string }>();

  const [selectedKey, setSelectedKey] = useState('');
  const [confirmKey, setConfirmKey] = useState<string | null>(null);
  const [sending, setSending] = useState(false);
  const [history, setHistory] = useState<DeviceCommandItem[]>([]);
  const [historyLoading, setHistoryLoading] = useState(true);
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [expandedOutput, setExpandedOutput] = useState<Record<string, string>>({});

  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const { data: device } = useApi(() => getDevice(deviceId!), [deviceId]);
  const { data: catalog } = useApi(() => getCommandCatalog(), []);

  // Group catalog by category
  const catalogByCategory = catalog
    ? catalog.reduce<Record<string, CommandCatalogEntry[]>>((acc, cmd) => {
        const cat = cmd.category || 'Прочее';
        if (!acc[cat]) acc[cat] = [];
        acc[cat].push(cmd);
        return acc;
      }, {})
    : {};

  // Load command history
  const loadHistory = useCallback(async () => {
    if (!deviceId) return;
    try {
      const data = await getDeviceCommands(deviceId);
      setHistory(data);
    } catch { /* ignore */ }
    finally {
      setHistoryLoading(false);
    }
  }, [deviceId]);

  useEffect(() => {
    loadHistory();
  }, [loadHistory]);

  // Poll while any command is pending/running
  useEffect(() => {
    const hasPending = history.some((c) => c.status === 'pending' || c.status === 'running');
    if (hasPending) {
      if (!pollRef.current) {
        pollRef.current = setInterval(loadHistory, 3000);
      }
    } else {
      if (pollRef.current) {
        clearInterval(pollRef.current);
        pollRef.current = null;
      }
    }
    return () => {
      if (pollRef.current) {
        clearInterval(pollRef.current);
        pollRef.current = null;
      }
    };
  }, [history, loadHistory]);

  const handleSend = async (key: string) => {
    const catalogEntry = catalog?.find((c) => c.key === key);
    if (!catalogEntry) return;

    if (catalogEntry.requires_confirm && confirmKey !== key) {
      setConfirmKey(key);
      return;
    }

    setConfirmKey(null);
    setSending(true);
    try {
      await sendCommand(deviceId!, key);
      await loadHistory();
    } catch { /* ignore */ }
    finally {
      setSending(false);
    }
  };

  const handleExpand = async (cmdId: string) => {
    if (expandedId === cmdId) {
      setExpandedId(null);
      return;
    }
    setExpandedId(cmdId);
    if (!expandedOutput[cmdId]) {
      try {
        const result = await getCommandResult(cmdId);
        setExpandedOutput((prev) => ({ ...prev, [cmdId]: result.output || '(нет вывода)' }));
      } catch {
        setExpandedOutput((prev) => ({ ...prev, [cmdId]: '(ошибка загрузки)' }));
      }
    }
  };

  const selectedCatalogEntry = catalog?.find((c) => c.key === selectedKey);

  return (
    <AppLayout
      title={
        <>
          <i className="bi bi-send me-2" />
          Команды
          {device && (
            <span style={{ fontSize: '.72rem', color: 'var(--txt-muted)', fontFamily: 'monospace', marginLeft: '.5rem' }}>
              {device.serial_number}
            </span>
          )}
        </>
      }
      actions={
        device && (
          <Link to={`/devices/${device.id}`} className="btn btn-sm btn-outline-secondary">
            <i className="bi bi-cpu me-1" />
            Устройство
          </Link>
        )
      }
    >
      <div className="row g-3">
        {/* ── Send command ────────────────────────────────── */}
        <div className="col-12 col-xl-5">
          <div className="card">
            <div className="card-header">
              <span style={{ fontSize: '.85rem', fontWeight: 600 }}>
                <i className="bi bi-terminal me-2" />
                Отправить команду
              </span>
            </div>
            <div className="card-body">
              {!catalog ? (
                <Spinner size="sm" />
              ) : (
                <>
                  <div className="mb-3">
                    <label className="form-label" style={{ fontSize: '.78rem', color: 'var(--txt-muted)' }}>
                      Выберите команду
                    </label>
                    <select
                      className="form-select form-select-sm"
                      value={selectedKey}
                      onChange={(e) => { setSelectedKey(e.target.value); setConfirmKey(null); }}
                    >
                      <option value="">— выберите —</option>
                      {Object.entries(catalogByCategory).map(([category, cmds]) => (
                        <optgroup key={category} label={category}>
                          {cmds.map((cmd) => (
                            <option key={cmd.key} value={cmd.key}>
                              {cmd.label}
                            </option>
                          ))}
                        </optgroup>
                      ))}
                    </select>
                  </div>

                  {selectedCatalogEntry && (
                    <div
                      className="mb-3"
                      style={{
                        background: 'var(--bg-card-header)',
                        border: '1px solid var(--border-clr)',
                        borderRadius: 6,
                        padding: '.65rem .85rem',
                        fontSize: '.78rem',
                      }}
                    >
                      <div style={{ color: 'var(--txt-primary)', fontWeight: 600, marginBottom: '.25rem' }}>
                        <i className={`bi ${selectedCatalogEntry.icon} me-1`} />
                        {selectedCatalogEntry.label}
                      </div>
                      <div style={{ color: 'var(--txt-muted)' }}>{selectedCatalogEntry.description}</div>
                      <div style={{ marginTop: '.35rem', fontSize: '.7rem', color: 'var(--txt-muted)' }}>
                        Таймаут: {selectedCatalogEntry.timeout} с
                        {selectedCatalogEntry.requires_confirm && (
                          <span
                            style={{
                              marginLeft: '.5rem',
                              color: 'var(--warning)',
                              background: 'rgba(255,193,7,.08)',
                              borderRadius: 4,
                              padding: '0 4px',
                            }}
                          >
                            <i className="bi bi-exclamation-triangle me-1" />
                            Требует подтверждения
                          </span>
                        )}
                      </div>
                    </div>
                  )}

                  {confirmKey === selectedKey && (
                    <div
                      className="mb-2"
                      style={{
                        background: 'rgba(255,193,7,.08)',
                        border: '1px solid var(--warning)',
                        borderRadius: 6,
                        padding: '.5rem .75rem',
                        fontSize: '.78rem',
                        color: 'var(--warning)',
                      }}
                    >
                      <i className="bi bi-exclamation-triangle me-1" />
                      Вы уверены? Нажмите ещё раз для подтверждения.
                    </div>
                  )}

                  <button
                    className="btn btn-sm btn-outline-success w-100"
                    onClick={() => selectedKey && handleSend(selectedKey)}
                    disabled={!selectedKey || sending || !device?.is_online}
                  >
                    {sending ? (
                      <><span className="spinner-border spinner-border-sm me-1" />Отправка…</>
                    ) : (
                      <><i className="bi bi-send me-1" />Отправить</>
                    )}
                  </button>

                  {!device?.is_online && (
                    <div style={{ fontSize: '.72rem', color: 'var(--txt-muted)', marginTop: '.35rem', textAlign: 'center' }}>
                      Устройство офлайн — команды недоступны
                    </div>
                  )}
                </>
              )}
            </div>
          </div>
        </div>

        {/* ── Command history ───────────────────────────── */}
        <div className="col-12 col-xl-7">
          <div className="card">
            <div className="card-header d-flex justify-content-between align-items-center">
              <span style={{ fontSize: '.85rem', fontWeight: 600 }}>
                <i className="bi bi-clock-history me-2" />
                История команд
              </span>
              <button
                className="btn btn-link btn-sm p-0"
                style={{ fontSize: '.72rem', color: 'var(--link-clr)' }}
                onClick={loadHistory}
              >
                <i className="bi bi-arrow-clockwise me-1" />
                Обновить
              </button>
            </div>

            {historyLoading ? (
              <Spinner size="sm" />
            ) : history.length === 0 ? (
              <div style={{ padding: '3rem', textAlign: 'center', color: 'var(--txt-muted)', fontSize: '.82rem' }}>
                <i className="bi bi-inbox" style={{ fontSize: '2rem', display: 'block', marginBottom: '.5rem' }} />
                Команды ещё не отправлялись
              </div>
            ) : (
              history.map((cmd) => (
                <div key={cmd.id}>
                  <div
                    style={{
                      padding: '.65rem 1rem',
                      borderBottom: '1px solid var(--border-clr)',
                      cursor: cmd.has_output ? 'pointer' : 'default',
                    }}
                    onClick={() => cmd.has_output && handleExpand(cmd.id)}
                  >
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '.5rem' }}>
                        <i className={`bi ${cmd.icon || 'bi-terminal'}`} style={{ color: 'var(--txt-muted)', fontSize: '.82rem' }} />
                        <div>
                          <div style={{ fontSize: '.82rem', fontWeight: 500, color: 'var(--txt-primary)' }}>
                            {cmd.label}
                          </div>
                          <div style={{ fontSize: '.7rem', color: 'var(--txt-muted)' }}>
                            {cmd.category}
                            {cmd.sent_by && ` · ${cmd.sent_by}`}
                            {cmd.duration_sec != null && ` · ${cmd.duration_sec.toFixed(1)}с`}
                          </div>
                        </div>
                      </div>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '.5rem', flexShrink: 0 }}>
                        <span
                          style={{
                            fontSize: '.72rem',
                            color: STATUS_COLOR[cmd.status] || 'var(--txt-muted)',
                            display: 'flex',
                            alignItems: 'center',
                            gap: '.25rem',
                          }}
                        >
                          {(cmd.status === 'pending' || cmd.status === 'running') && (
                            <span className="spinner-border spinner-border-sm" style={{ width: 10, height: 10, borderWidth: 2 }} />
                          )}
                          {STATUS_LABEL[cmd.status] || cmd.status}
                          {cmd.exit_code != null && cmd.status !== 'completed' && (
                            <span> ({cmd.exit_code})</span>
                          )}
                        </span>
                        <span style={{ fontSize: '.68rem', color: 'var(--txt-muted)', whiteSpace: 'nowrap' }}>
                          {timeSince(cmd.created_at)}
                        </span>
                        {cmd.has_output && (
                          <i
                            className={`bi bi-chevron-${expandedId === cmd.id ? 'up' : 'down'}`}
                            style={{ fontSize: '.72rem', color: 'var(--txt-muted)' }}
                          />
                        )}
                      </div>
                    </div>
                  </div>

                  {expandedId === cmd.id && (
                    <div
                      style={{
                        background: 'var(--bg-card-header)',
                        borderBottom: '1px solid var(--border-clr)',
                        padding: '.65rem 1rem',
                      }}
                    >
                      <pre
                        style={{
                          margin: 0,
                          fontSize: '.72rem',
                          color: 'var(--txt-secondary)',
                          fontFamily: 'monospace',
                          whiteSpace: 'pre-wrap',
                          wordBreak: 'break-all',
                          maxHeight: 300,
                          overflowY: 'auto',
                        }}
                      >
                        {expandedOutput[cmd.id] ?? <span className="spinner-border spinner-border-sm" />}
                      </pre>
                    </div>
                  )}
                </div>
              ))
            )}
          </div>
        </div>
      </div>
    </AppLayout>
  );
}

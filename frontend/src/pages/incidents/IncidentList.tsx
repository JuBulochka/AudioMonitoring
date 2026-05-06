import React, { useState, useCallback } from 'react';
import { Link } from 'react-router-dom';
import AppLayout from '@/components/Layout/AppLayout';
import Spinner from '@/components/UI/Spinner';
import Pagination from '@/components/UI/Pagination';
import SeverityBadge from '@/components/UI/SeverityBadge';
import { useApi } from '@/hooks/useApi';
import { getIncidents } from '@/api/incidents';
import { formatDate, timeSince } from '@/utils/formatters';

const PAGE_SIZE = 30;

export default function IncidentList() {
  const [page, setPage] = useState(1);
  const [status, setStatus] = useState('');
  const [severity, setSeverity] = useState('');
  const [type, setType] = useState('');
  const [search, setSearch] = useState('');
  const [searchInput, setSearchInput] = useState('');

  const fetcher = useCallback(
    () => getIncidents({ page, page_size: PAGE_SIZE, status: status || undefined, severity: severity || undefined, incident_type: type || undefined, search: search || undefined }),
    [page, status, severity, type, search]
  );

  const { data, loading, error } = useApi(fetcher, [page, status, severity, type, search]);
  const totalPages = data ? Math.ceil(data.count / PAGE_SIZE) : 0;

  const reset = () => {
    setStatus(''); setSeverity(''); setType('');
    setSearch(''); setSearchInput(''); setPage(1);
  };

  const statusColor: Record<string, string> = {
    open: 'var(--danger)',
    acknowledged: 'var(--warning)',
    in_progress: 'var(--info)',
    resolved: 'var(--online-clr)',
    closed: 'var(--txt-muted)',
    false_positive: 'var(--txt-muted)',
  };

  return (
    <AppLayout title="Инциденты">
      {/* Filters */}
      <div className="card mb-3">
        <div className="card-body py-2 px-3">
          <div className="row g-2 align-items-end">
            <div className="col-auto flex-grow-1">
              <div className="input-group input-group-sm">
                <input
                  className="form-control"
                  placeholder="Поиск по названию, устройству…"
                  value={searchInput}
                  onChange={(e) => setSearchInput(e.target.value)}
                  onKeyDown={(e) => { if (e.key === 'Enter') { setSearch(searchInput); setPage(1); } }}
                />
                <button className="btn btn-outline-secondary" onClick={() => { setSearch(searchInput); setPage(1); }}>
                  <i className="bi bi-search" />
                </button>
              </div>
            </div>
            <div className="col-auto">
              <select className="form-select form-select-sm" value={severity} onChange={(e) => { setSeverity(e.target.value); setPage(1); }}>
                <option value="">Все severity</option>
                <option value="critical">Критично</option>
                <option value="warning">Предупреждение</option>
                <option value="info">Информация</option>
              </select>
            </div>
            <div className="col-auto">
              <select className="form-select form-select-sm" value={status} onChange={(e) => { setStatus(e.target.value); setPage(1); }}>
                <option value="">Все статусы</option>
                <option value="open">Открыт</option>
                <option value="acknowledged">Принят</option>
                <option value="in_progress">В работе</option>
                <option value="resolved">Решён</option>
                <option value="closed">Закрыт</option>
              </select>
            </div>
            <div className="col-auto">
              <select className="form-select form-select-sm" value={type} onChange={(e) => { setType(e.target.value); setPage(1); }}>
                <option value="">Все типы</option>
                <option value="anomaly_detected">Аномалия</option>
                <option value="device_offline">Устройство офлайн</option>
                <option value="manual">Вручную</option>
              </select>
            </div>
            <div className="col-auto">
              <button className="btn btn-sm btn-link text-muted" onClick={reset}>Сброс</button>
            </div>
          </div>
        </div>
      </div>

      {/* Table */}
      <div className="card">
        <div className="card-header d-flex justify-content-between align-items-center">
          <span style={{ fontSize: '.85rem', fontWeight: 600 }}>
            <i className="bi bi-exclamation-triangle me-2" />
            Инциденты
          </span>
          {data && <span style={{ fontSize: '.75rem', color: 'var(--txt-muted)' }}>{data.count} инцидентов</span>}
        </div>

        {loading && <Spinner text="Загрузка…" />}
        {error && <div style={{ padding: '1rem', color: 'var(--danger)', fontSize: '.82rem' }}>{error}</div>}

        {data && !loading && (
          <>
            <div className="table-responsive">
              <table className="table table-sm table-hover mb-0">
                <thead>
                  <tr>
                    <th className="ps-3">Инцидент</th>
                    <th>Severity</th>
                    <th>Статус</th>
                    <th>Устройство</th>
                    <th>Назначен</th>
                    <th>Создан</th>
                    <th></th>
                  </tr>
                </thead>
                <tbody>
                  {data.results.length === 0 ? (
                    <tr>
                      <td colSpan={7} className="text-center" style={{ padding: '2rem', color: 'var(--txt-muted)' }}>
                        Инцидентов не найдено
                      </td>
                    </tr>
                  ) : (
                    data.results.map((inc) => (
                      <tr
                        key={inc.id}
                        style={{
                          background: inc.severity === 'critical'
                            ? 'rgba(248,81,73,.04)'
                            : inc.severity === 'warning'
                            ? 'rgba(255,193,7,.03)'
                            : 'transparent',
                        }}
                      >
                        <td className="ps-3">
                          <div style={{ fontSize: '.82rem', color: 'var(--txt-primary)', maxWidth: 280, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                            {inc.title}
                          </div>
                          <div style={{ fontSize: '.7rem', color: 'var(--txt-muted)' }}>{inc.incident_type_display}</div>
                        </td>
                        <td>
                          <SeverityBadge severity={inc.severity} label={inc.severity_display} size="sm" />
                        </td>
                        <td>
                          <span style={{ fontSize: '.78rem', color: statusColor[inc.status] || 'var(--txt-muted)' }}>
                            {inc.status_display}
                          </span>
                        </td>
                        <td>
                          <Link to={`/devices/${inc.device.id}`} style={{ fontSize: '.75rem', fontFamily: 'monospace', color: 'var(--link-clr)' }}>
                            {inc.device.serial_number}
                          </Link>
                        </td>
                        <td style={{ fontSize: '.75rem', color: 'var(--txt-muted)' }}>
                          {inc.assigned_to ? (inc.assigned_to.full_name || inc.assigned_to.username) : '—'}
                        </td>
                        <td style={{ fontSize: '.75rem', color: 'var(--txt-muted)', whiteSpace: 'nowrap' }}>
                          {timeSince(inc.created_at)}
                        </td>
                        <td>
                          <Link to={`/incidents/${inc.id}`} className="btn btn-sm btn-outline-secondary py-0 px-2" style={{ fontSize: '.72rem' }}>
                            <i className="bi bi-chevron-right" />
                          </Link>
                        </td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>
            {totalPages > 1 && (
              <div className="card-footer">
                <Pagination page={page} totalPages={totalPages} totalCount={data.count} pageSize={PAGE_SIZE} onChange={setPage} noun="инцидентов" />
              </div>
            )}
          </>
        )}
      </div>
    </AppLayout>
  );
}

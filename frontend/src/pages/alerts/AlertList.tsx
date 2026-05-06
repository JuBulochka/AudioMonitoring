import React, { useState, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import AppLayout from '@/components/Layout/AppLayout';
import Spinner from '@/components/UI/Spinner';
import Pagination from '@/components/UI/Pagination';
import SeverityBadge from '@/components/UI/SeverityBadge';
import { useApi } from '@/hooks/useApi';
import { getNotifications, markRead, markAllRead } from '@/api/alerts';
import { formatDate } from '@/utils/formatters';

const PAGE_SIZE = 30;

export default function AlertList() {
  const [page, setPage] = useState(1);
  const [unreadOnly, setUnreadOnly] = useState(false);
  const navigate = useNavigate();

  const fetcher = useCallback(
    () => getNotifications({ is_read: unreadOnly ? false : undefined, page }),
    [page, unreadOnly]
  );

  const { data, loading, error, refetch } = useApi(fetcher, [page, unreadOnly]);
  const totalPages = data ? Math.ceil(data.count / PAGE_SIZE) : 0;

  const handleMarkRead = async (id: string) => {
    try { await markRead(id); refetch(); } catch { /* ignore */ }
  };

  const handleMarkAll = async () => {
    try { await markAllRead(); refetch(); } catch { /* ignore */ }
  };

  return (
    <AppLayout
      title="Уведомления"
      actions={
        <button className="btn btn-sm btn-outline-secondary" onClick={handleMarkAll}>
          <i className="bi bi-check-all me-1" />
          Прочитать все
        </button>
      }
    >
      <div className="card mb-3">
        <div className="card-body py-2 px-3">
          <div className="form-check form-switch mb-0">
            <input
              className="form-check-input"
              type="checkbox"
              id="unreadOnly"
              checked={unreadOnly}
              onChange={(e) => { setUnreadOnly(e.target.checked); setPage(1); }}
            />
            <label className="form-check-label" htmlFor="unreadOnly" style={{ fontSize: '.82rem', color: 'var(--txt-muted)' }}>
              Только непрочитанные
            </label>
          </div>
        </div>
      </div>

      <div className="card">
        <div className="card-header d-flex justify-content-between align-items-center">
          <span style={{ fontSize: '.85rem', fontWeight: 600 }}>
            <i className="bi bi-bell me-2" />
            Уведомления
          </span>
          {data && <span style={{ fontSize: '.75rem', color: 'var(--txt-muted)' }}>{data.count}</span>}
        </div>

        {loading && <Spinner />}
        {error && <div style={{ padding: '1rem', color: 'var(--danger)', fontSize: '.82rem' }}>{error}</div>}

        {data && !loading && (
          <>
            {data.results.length === 0 ? (
              <div style={{ padding: '3rem', textAlign: 'center', color: 'var(--txt-muted)' }}>
                <i className="bi bi-bell-slash" style={{ fontSize: '2rem', display: 'block', marginBottom: '.5rem' }} />
                Нет уведомлений
              </div>
            ) : (
              data.results.map((n) => (
                <div
                  key={n.id}
                  style={{
                    padding: '.75rem 1rem',
                    borderBottom: '1px solid var(--border-clr)',
                    background: n.is_read ? 'transparent' : 'rgba(88,166,255,.04)',
                    display: 'flex',
                    gap: '.75rem',
                    alignItems: 'flex-start',
                    cursor: 'pointer',
                  }}
                  onClick={() => {
                    if (!n.is_read) handleMarkRead(n.id);
                    if (n.incident) navigate(`/incidents/${n.incident.id}`);
                    else if (n.device) navigate(`/devices/${n.device.id}`);
                  }}
                >
                  <SeverityBadge severity={n.severity} label="" size="sm" />
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div style={{ fontSize: '.82rem', fontWeight: n.is_read ? 400 : 600, color: 'var(--txt-primary)', marginBottom: '.15rem' }}>
                      {n.title}
                    </div>
                    <div style={{ fontSize: '.78rem', color: 'var(--txt-muted)' }}>{n.message}</div>
                    {(n.device || n.incident) && (
                      <div style={{ fontSize: '.72rem', color: 'var(--link-clr)', marginTop: '.25rem' }}>
                        {n.incident ? `Инцидент: ${n.incident.title}` : `Устройство: ${n.device?.serial_number}`}
                      </div>
                    )}
                  </div>
                  <div style={{ flexShrink: 0, textAlign: 'right' }}>
                    <div style={{ fontSize: '.72rem', color: 'var(--txt-muted)', whiteSpace: 'nowrap' }}>
                      {formatDate(n.created_at)}
                    </div>
                    {!n.is_read && (
                      <button
                        className="btn btn-link btn-sm p-0 mt-1"
                        style={{ fontSize: '.68rem', color: 'var(--link-clr)' }}
                        onClick={(e) => { e.stopPropagation(); handleMarkRead(n.id); }}
                      >
                        Прочитано
                      </button>
                    )}
                  </div>
                </div>
              ))
            )}
            {totalPages > 1 && (
              <div className="card-footer">
                <Pagination page={page} totalPages={totalPages} totalCount={data.count} pageSize={PAGE_SIZE} onChange={setPage} noun="уведомлений" />
              </div>
            )}
          </>
        )}
      </div>
    </AppLayout>
  );
}

import React from 'react';
import { Link } from 'react-router-dom';
import AppLayout from '@/components/Layout/AppLayout';
import Spinner from '@/components/UI/Spinner';
import { useApi } from '@/hooks/useApi';
import { getDevices } from '@/api/devices';
import { timeSince } from '@/utils/formatters';

export default function RemoteAccess() {
  const { data, loading } = useApi(() => getDevices({ page_size: 100 }), []);

  return (
    <AppLayout title="Удалённый доступ">
      <p style={{ fontSize: '.78rem', color: 'var(--txt-muted)', marginBottom: '1rem' }}>
        Нажмите <strong style={{ color: 'var(--txt-primary)' }}>Подключить</strong> — SSH-терминал откроется в новой вкладке.
        Устройство должно быть онлайн и иметь активный reverse-туннель.
      </p>

      {loading && <Spinner />}

      {data && (
        <div className="row g-2">
          {data.results.map((device) => (
            <div key={device.id} className="col-12 col-md-6 col-xl-4">
              <div
                className="card"
                style={{ borderColor: device.is_online ? 'var(--online-clr)' : 'var(--border-clr)' }}
              >
                <div className="card-body" style={{ padding: '.75rem 1rem' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '.5rem' }}>
                    <div>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '.5rem', marginBottom: '.15rem' }}>
                        <span className={device.is_online ? 'online-dot' : 'offline-dot'} />
                        <span style={{ fontWeight: 600, fontSize: '.88rem', color: 'var(--txt-primary)' }}>
                          {device.name}
                        </span>
                      </div>
                      <span style={{ fontSize: '.72rem', color: 'var(--txt-muted)', fontFamily: 'monospace' }}>
                        {device.serial_number}
                      </span>
                    </div>
                    <div style={{ textAlign: 'right' }}>
                      {device.tunnel_port && (
                        <span
                          style={{
                            fontSize: '.68rem',
                            fontFamily: 'monospace',
                            background: 'var(--bg-card-header)',
                            border: '1px solid var(--border-clr)',
                            borderRadius: 4,
                            padding: '1px 6px',
                            color: 'var(--txt-muted)',
                          }}
                        >
                          :{device.tunnel_port}
                        </span>
                      )}
                    </div>
                  </div>

                  <div style={{ fontSize: '.72rem', color: 'var(--txt-muted)', marginBottom: '.75rem' }}>
                    {device.region_name} · {device.site_name}
                    {device.last_seen_at && (
                      <span> · {timeSince(device.last_seen_at)}</span>
                    )}
                  </div>

                  <div style={{ display: 'flex', gap: '.5rem' }}>
                    <a
                      href={`/remote-access/terminal/${device.id}/`}
                      target="_blank"
                      rel="noreferrer"
                      className={`btn btn-sm ${device.is_online ? 'btn-outline-success' : 'btn-outline-secondary'}`}
                      style={{ fontSize: '.75rem' }}
                    >
                      <i className="bi bi-terminal me-1" />
                      Подключить
                    </a>
                    <Link
                      to={`/remote-access/commands/${device.id}`}
                      className="btn btn-sm btn-outline-secondary"
                      style={{ fontSize: '.75rem' }}
                    >
                      <i className="bi bi-send me-1" />
                      Команды
                    </Link>
                    <Link
                      to={`/devices/${device.id}`}
                      className="btn btn-sm btn-outline-secondary"
                      style={{ fontSize: '.75rem' }}
                    >
                      <i className="bi bi-cpu" />
                    </Link>
                  </div>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </AppLayout>
  );
}

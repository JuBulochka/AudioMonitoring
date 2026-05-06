import React, { useState, useCallback } from 'react';
import { Link } from 'react-router-dom';
import AppLayout from '@/components/Layout/AppLayout';
import Spinner from '@/components/UI/Spinner';
import Pagination from '@/components/UI/Pagination';
import SeverityBadge from '@/components/UI/SeverityBadge';
import { useApi } from '@/hooks/useApi';
import { getDevices } from '@/api/devices';
import { timeSince } from '@/utils/formatters';
import { Device } from '@/types';

const PAGE_SIZE = 30;

export default function DeviceList() {
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState('');
  const [searchInput, setSearchInput] = useState('');
  const [statusFilter, setStatusFilter] = useState('');
  const [onlineFilter, setOnlineFilter] = useState('');

  const fetcher = useCallback(
    () =>
      getDevices({
        page,
        page_size: PAGE_SIZE,
        search: search || undefined,
        status: statusFilter || undefined,
        is_online: onlineFilter === 'online' ? true : onlineFilter === 'offline' ? false : undefined,
      }),
    [page, search, statusFilter, onlineFilter]
  );

  const { data, loading, error } = useApi(fetcher, [page, search, statusFilter, onlineFilter]);

  const applySearch = () => {
    setSearch(searchInput);
    setPage(1);
  };

  const resetFilters = () => {
    setSearch('');
    setSearchInput('');
    setStatusFilter('');
    setOnlineFilter('');
    setPage(1);
  };

  const totalPages = data ? Math.ceil(data.count / PAGE_SIZE) : 0;

  const statusColor: Record<string, string> = {
    normal: 'var(--online-clr)',
    needs_inspection: 'var(--warning)',
    site_visit_required: 'var(--danger)',
    offline: 'var(--txt-muted)',
  };

  return (
    <AppLayout title="Устройства">
      {/* Filters */}
      <div className="card mb-3">
        <div className="card-body py-2 px-3">
          <div className="row g-2 align-items-end">
            <div className="col-auto flex-grow-1">
              <div className="input-group input-group-sm">
                <input
                  type="text"
                  className="form-control"
                  placeholder="Серийный номер, название…"
                  value={searchInput}
                  onChange={(e) => setSearchInput(e.target.value)}
                  onKeyDown={(e) => e.key === 'Enter' && applySearch()}
                />
                <button className="btn btn-outline-secondary" onClick={applySearch}>
                  <i className="bi bi-search" />
                </button>
              </div>
            </div>
            <div className="col-auto">
              <select
                className="form-select form-select-sm"
                value={onlineFilter}
                onChange={(e) => { setOnlineFilter(e.target.value); setPage(1); }}
              >
                <option value="">Все устройства</option>
                <option value="online">Онлайн</option>
                <option value="offline">Офлайн</option>
              </select>
            </div>
            <div className="col-auto">
              <select
                className="form-select form-select-sm"
                value={statusFilter}
                onChange={(e) => { setStatusFilter(e.target.value); setPage(1); }}
              >
                <option value="">Все статусы</option>
                <option value="normal">Норма</option>
                <option value="needs_inspection">Требует проверки</option>
                <option value="site_visit_required">Требуется выезд</option>
                <option value="offline">Отключено</option>
              </select>
            </div>
            <div className="col-auto">
              <button className="btn btn-sm btn-link text-muted" onClick={resetFilters}>
                Сброс
              </button>
            </div>
          </div>
        </div>
      </div>

      {/* Table */}
      <div className="card">
        <div className="card-header d-flex align-items-center justify-content-between">
          <span style={{ fontSize: '.85rem', fontWeight: 600 }}>
            <i className="bi bi-cpu me-2" />
            Устройства
          </span>
          {data && (
            <span style={{ fontSize: '.75rem', color: 'var(--txt-muted)' }}>
              {data.count} устройств
            </span>
          )}
        </div>

        {loading && <Spinner text="Загрузка устройств…" />}
        {error && (
          <div style={{ padding: '1rem', color: 'var(--danger)', fontSize: '.82rem' }}>
            <i className="bi bi-exclamation-circle me-1" />
            {error}
          </div>
        )}

        {data && !loading && (
          <>
            <div className="table-responsive">
              <table className="table table-sm table-hover mb-0">
                <thead>
                  <tr>
                    <th className="ps-3">Устройство</th>
                    <th>Регион / Куст</th>
                    <th>Статус</th>
                    <th>Онлайн</th>
                    <th>Последний пакет</th>
                    <th>Прошивка</th>
                    <th></th>
                  </tr>
                </thead>
                <tbody>
                  {data.results.length === 0 ? (
                    <tr>
                      <td colSpan={7} className="text-center" style={{ padding: '2rem', color: 'var(--txt-muted)' }}>
                        Устройств не найдено
                      </td>
                    </tr>
                  ) : (
                    data.results.map((device: Device) => (
                      <tr key={device.id}>
                        <td className="ps-3">
                          <div style={{ display: 'flex', alignItems: 'center', gap: '.5rem' }}>
                            <span
                              className={device.is_online ? 'online-dot' : 'offline-dot'}
                            />
                            <div>
                              <div style={{ fontSize: '.82rem', fontWeight: 500, color: 'var(--txt-primary)' }}>
                                {device.name}
                              </div>
                              <div style={{ fontSize: '.72rem', color: 'var(--txt-muted)', fontFamily: 'monospace' }}>
                                {device.serial_number}
                              </div>
                            </div>
                          </div>
                        </td>
                        <td style={{ fontSize: '.78rem', color: 'var(--txt-muted)' }}>
                          <div>{device.region_name}</div>
                          <div>{device.site_name}</div>
                        </td>
                        <td>
                          <span style={{ fontSize: '.78rem', color: statusColor[device.status] || 'var(--txt-muted)' }}>
                            {device.status_display}
                          </span>
                        </td>
                        <td>
                          <span style={{ fontSize: '.75rem', color: device.is_online ? 'var(--online-clr)' : 'var(--txt-muted)' }}>
                            {device.is_online ? 'Онлайн' : 'Офлайн'}
                          </span>
                        </td>
                        <td style={{ fontSize: '.75rem', color: 'var(--txt-muted)' }}>
                          {timeSince(device.last_packet_at)}
                        </td>
                        <td style={{ fontSize: '.72rem', color: 'var(--txt-muted)', fontFamily: 'monospace' }}>
                          {device.firmware_version || '—'}
                        </td>
                        <td>
                          <Link
                            to={`/devices/${device.id}`}
                            className="btn btn-sm btn-outline-secondary"
                            style={{ fontSize: '.72rem', padding: '2px 8px' }}
                          >
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
                <Pagination
                  page={page}
                  totalPages={totalPages}
                  totalCount={data.count}
                  pageSize={PAGE_SIZE}
                  onChange={setPage}
                  noun="устройств"
                />
              </div>
            )}
          </>
        )}
      </div>
    </AppLayout>
  );
}

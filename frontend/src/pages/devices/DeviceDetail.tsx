import React, { useState, useCallback } from 'react';
import { useParams, Link } from 'react-router-dom';
import AppLayout from '@/components/Layout/AppLayout';
import Spinner from '@/components/UI/Spinner';
import Pagination from '@/components/UI/Pagination';
import SeverityBadge from '@/components/UI/SeverityBadge';
import { useApi } from '@/hooks/useApi';
import { getDevice } from '@/api/devices';
import { getPackets } from '@/api/packets';
import { formatDate, formatPercent, timeSince } from '@/utils/formatters';
import { AudioPacket } from '@/types';

const PAGE_SIZE = 30;

export default function DeviceDetail() {
  const { id } = useParams<{ id: string }>();
  const [packetPage, setPacketPage] = useState(1);
  const [severityFilter, setSeverityFilter] = useState('');
  const [anomalyFilter, setAnomalyFilter] = useState('');
  const [fromDate, setFromDate] = useState('');
  const [toDate, setToDate] = useState('');
  const [selectedPacket, setSelectedPacket] = useState<AudioPacket | null>(null);

  const { data: device, loading: deviceLoading } = useApi(() => getDevice(id!), [id]);

  const packetsFetcher = useCallback(
    () =>
      getPackets({
        device: id,
        page: packetPage,
        page_size: PAGE_SIZE,
        severity: severityFilter || undefined,
        has_anomaly: anomalyFilter === '1' ? true : undefined,
        from_date: fromDate || undefined,
        to_date: toDate || undefined,
      }),
    [id, packetPage, severityFilter, anomalyFilter, fromDate, toDate]
  );

  const { data: packets, loading: packetsLoading } = useApi(packetsFetcher, [
    id, packetPage, severityFilter, anomalyFilter, fromDate, toDate,
  ]);

  const totalPages = packets ? Math.ceil(packets.count / PAGE_SIZE) : 0;

  const resetFilters = () => {
    setSeverityFilter('');
    setAnomalyFilter('');
    setFromDate('');
    setToDate('');
    setPacketPage(1);
  };

  if (deviceLoading) return <AppLayout title="Устройство"><Spinner /></AppLayout>;
  if (!device) return <AppLayout title="Устройство"><div style={{ padding: '2rem', color: 'var(--txt-muted)' }}>Устройство не найдено</div></AppLayout>;

  return (
    <AppLayout
      title={
        <>
          <span className={device.is_online ? 'online-dot me-2' : 'offline-dot me-2'} />
          {device.name}
          <span style={{ fontSize: '.72rem', color: 'var(--txt-muted)', fontFamily: 'monospace', marginLeft: '.5rem' }}>
            {device.serial_number}
          </span>
        </>
      }
      actions={
        <Link
          to={`/remote-access/terminal/${device.id}`}
          className="btn btn-sm btn-outline-success"
          target="_blank"
        >
          <i className="bi bi-terminal me-1" />
          SSH Терминал
        </Link>
      }
    >
      <div className="row g-3">
        {/* Left: info + packets */}
        <div className="col-12 col-xl-8">
          {/* Info cards */}
          <div className="row g-2 mb-3">
            {[
              { label: 'Регион', value: device.region_name },
              { label: 'Месторождение / Куст', value: `${device.field_name} / ${device.site_name}` },
              { label: 'Скважина', value: `№${device.well_number}` },
              { label: 'Прошивка / Модель', value: `${device.firmware_version || '—'} / ${device.model_version || '—'}` },
            ].map((card) => (
              <div key={card.label} className="col-6 col-md-3">
                <div className="stat-card">
                  <div className="label">{card.label}</div>
                  <div style={{ fontSize: '.82rem', color: 'var(--txt-secondary)', fontWeight: 500 }}>
                    {card.value}
                  </div>
                </div>
              </div>
            ))}
          </div>

          {/* Packet filters */}
          <div className="card mb-2">
            <div className="card-body py-2 px-3">
              <div className="row g-2 align-items-end">
                <div className="col-auto">
                  <select
                    className="form-select form-select-sm"
                    value={severityFilter}
                    onChange={(e) => { setSeverityFilter(e.target.value); setPacketPage(1); }}
                  >
                    <option value="">Все severity</option>
                    <option value="info">Информация</option>
                    <option value="warning">Предупреждение</option>
                    <option value="critical">Критично</option>
                  </select>
                </div>
                <div className="col-auto">
                  <select
                    className="form-select form-select-sm"
                    value={anomalyFilter}
                    onChange={(e) => { setAnomalyFilter(e.target.value); setPacketPage(1); }}
                  >
                    <option value="">Все пакеты</option>
                    <option value="1">Только аномалии</option>
                  </select>
                </div>
                <div className="col-auto">
                  <input
                    type="date"
                    className="form-control form-control-sm"
                    value={fromDate}
                    onChange={(e) => { setFromDate(e.target.value); setPacketPage(1); }}
                  />
                </div>
                <div className="col-auto">
                  <input
                    type="date"
                    className="form-control form-control-sm"
                    value={toDate}
                    onChange={(e) => { setToDate(e.target.value); setPacketPage(1); }}
                  />
                </div>
                <div className="col-auto">
                  <button className="btn btn-sm btn-link text-muted" onClick={resetFilters}>Сброс</button>
                </div>
              </div>
            </div>
          </div>

          {/* Packets table */}
          <div className="card">
            <div className="card-header d-flex justify-content-between align-items-center">
              <span style={{ fontSize: '.85rem', fontWeight: 600 }}>
                <i className="bi bi-music-note-list me-2" />
                Аудиопакеты (90 дней)
              </span>
              {packets && (
                <span style={{ fontSize: '.75rem', color: 'var(--txt-muted)' }}>
                  {packets.count} записей
                </span>
              )}
            </div>

            {packetsLoading && <Spinner size="sm" />}

            {packets && (
              <>
                <div className="table-responsive">
                  <table className="table table-sm mb-0">
                    <thead>
                      <tr>
                        <th className="ps-3">Время</th>
                        <th>Severity</th>
                        <th>Класс</th>
                        <th>Уверенность</th>
                        <th>Длит.</th>
                        <th>Аудио</th>
                        <th></th>
                      </tr>
                    </thead>
                    <tbody>
                      {packets.results.length === 0 ? (
                        <tr>
                          <td colSpan={7} className="text-center" style={{ padding: '2rem', color: 'var(--txt-muted)' }}>
                            Пакетов нет
                          </td>
                        </tr>
                      ) : (
                        packets.results.map((pkt: AudioPacket) => (
                          <tr
                            key={pkt.id}
                            style={{
                              background:
                                pkt.severity === 'critical'
                                  ? 'rgba(248,81,73,.04)'
                                  : pkt.severity === 'warning'
                                  ? 'rgba(255,193,7,.03)'
                                  : 'transparent',
                            }}
                          >
                            <td className="ps-3" style={{ fontSize: '.78rem', fontFamily: 'monospace', whiteSpace: 'nowrap' }}>
                              {formatDate(pkt.recorded_at)}
                            </td>
                            <td>
                              <SeverityBadge severity={pkt.severity} label={pkt.severity_display} size="sm" />
                            </td>
                            <td style={{ fontSize: '.78rem' }}>{pkt.dominant_class_display}</td>
                            <td>
                              <div style={{ display: 'flex', alignItems: 'center', gap: '.5rem' }}>
                                <div className="progress" style={{ width: 50, height: 4 }}>
                                  <div
                                    className={`progress-bar ${pkt.severity === 'critical' ? 'bg-danger' : pkt.severity === 'warning' ? 'bg-warning' : 'bg-success'}`}
                                    style={{ width: `${((pkt.dominant_class_score || 0) * 100).toFixed(0)}%` }}
                                  />
                                </div>
                                <span style={{ fontSize: '.72rem', color: 'var(--txt-muted)' }}>
                                  {pkt.dominant_class_score?.toFixed(2) ?? '—'}
                                </span>
                              </div>
                            </td>
                            <td style={{ fontSize: '.72rem', color: 'var(--txt-muted)' }}>
                              {pkt.duration_seconds ? `${Math.round(pkt.duration_seconds)}с` : '—'}
                            </td>
                            <td>
                              {pkt.audio_file ? (
                                <audio controls style={{ height: 24, width: 130 }} preload="none">
                                  <source src={pkt.audio_file} type="audio/wav" />
                                </audio>
                              ) : (
                                <span style={{ fontSize: '.72rem', color: 'var(--txt-muted)' }}>нет файла</span>
                              )}
                            </td>
                            <td>
                              <button
                                className="btn btn-sm btn-outline-secondary py-0 px-1"
                                style={{ fontSize: '.7rem' }}
                                onClick={() => setSelectedPacket(pkt)}
                              >
                                <i className="bi bi-list-ul" />
                              </button>
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
                      page={packetPage}
                      totalPages={totalPages}
                      totalCount={packets.count}
                      pageSize={PAGE_SIZE}
                      onChange={setPacketPage}
                    />
                  </div>
                )}
              </>
            )}
          </div>
        </div>

        {/* Right: packet detail panel */}
        <div className="col-12 col-xl-4">
          {selectedPacket ? (
            <div className="card">
              <div className="card-header d-flex justify-content-between align-items-center">
                <span style={{ fontSize: '.85rem', fontWeight: 600 }}>Детали пакета</span>
                <button
                  className="btn btn-sm btn-link p-0"
                  style={{ color: 'var(--txt-muted)' }}
                  onClick={() => setSelectedPacket(null)}
                >
                  <i className="bi bi-x-lg" />
                </button>
              </div>
              <div className="card-body" style={{ fontSize: '.82rem' }}>
                <div style={{ marginBottom: '.5rem', color: 'var(--txt-muted)', fontSize: '.72rem' }}>
                  Время записи
                </div>
                <div style={{ fontFamily: 'monospace', marginBottom: '1rem' }}>
                  {formatDate(selectedPacket.recorded_at)}
                </div>

                <SeverityBadge
                  severity={selectedPacket.severity}
                  label={`${selectedPacket.severity_display} · ${selectedPacket.dominant_class_display} (${((selectedPacket.dominant_class_score || 0) * 100).toFixed(0)}%)`}
                />

                <div style={{ marginTop: '1rem', marginBottom: '.5rem', fontSize: '.78rem', fontWeight: 600 }}>
                  Распределение классов
                </div>
                {selectedPacket.class_scores.map((cs) => (
                  <div key={cs.audio_class} style={{ marginBottom: '.35rem' }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '.72rem', color: 'var(--txt-muted)', marginBottom: 2 }}>
                      <span>{cs.audio_class}</span>
                      <span>{(cs.score * 100).toFixed(1)}%</span>
                    </div>
                    <div className="progress" style={{ height: 4 }}>
                      <div
                        className={`progress-bar ${cs.threshold_exceeded ? 'bg-danger' : 'bg-secondary'}`}
                        style={{ width: `${(cs.score * 100).toFixed(1)}%` }}
                      />
                    </div>
                  </div>
                ))}

                {selectedPacket.audio_file && (
                  <div style={{ marginTop: '1rem' }}>
                    <div style={{ fontSize: '.78rem', fontWeight: 600, marginBottom: '.35rem' }}>Аудиозапись</div>
                    <audio controls style={{ width: '100%' }} preload="none">
                      <source src={selectedPacket.audio_file} type="audio/wav" />
                    </audio>
                  </div>
                )}
              </div>
            </div>
          ) : (
            <div className="card">
              <div className="card-body text-center" style={{ color: 'var(--txt-muted)', fontSize: '.82rem', padding: '2rem' }}>
                <i className="bi bi-list-ul" style={{ fontSize: '2rem', display: 'block', marginBottom: '.5rem' }} />
                Нажмите на кнопку&nbsp;
                <i className="bi bi-list-ul" />
                &nbsp;в строке пакета, чтобы увидеть детали
              </div>
            </div>
          )}

          {/* Device quick info */}
          <div className="card mt-3">
            <div className="card-header">
              <span style={{ fontSize: '.85rem', fontWeight: 600 }}>
                <i className="bi bi-info-circle me-2" />
                Устройство
              </span>
            </div>
            <div className="card-body" style={{ fontSize: '.82rem' }}>
              <div className="row g-1">
                {[
                  { label: 'Статус', value: device.status_display },
                  { label: 'Последний сигнал', value: timeSince(device.last_seen_at) },
                  { label: 'Последний пакет', value: timeSince(device.last_packet_at) },
                  { label: 'SSH-порт', value: device.tunnel_port ? String(device.tunnel_port) : '—' },
                ].map((row) => (
                  <div key={row.label} className="col-6" style={{ marginBottom: '.35rem' }}>
                    <div style={{ fontSize: '.68rem', color: 'var(--txt-muted)' }}>{row.label}</div>
                    <div style={{ color: 'var(--txt-primary)', fontSize: '.78rem' }}>{row.value}</div>
                  </div>
                ))}
              </div>
              <div className="mt-2 d-flex gap-1 flex-wrap">
                <Link
                  to={`/remote-access/commands/${device.id}`}
                  className="btn btn-sm btn-outline-secondary"
                  style={{ fontSize: '.72rem' }}
                >
                  <i className="bi bi-send me-1" />
                  Команды
                </Link>
                <Link
                  to={`/remote-access/terminal/${device.id}`}
                  className="btn btn-sm btn-outline-success"
                  target="_blank"
                  style={{ fontSize: '.72rem' }}
                >
                  <i className="bi bi-terminal me-1" />
                  Терминал
                </Link>
              </div>
            </div>
          </div>
        </div>
      </div>
    </AppLayout>
  );
}

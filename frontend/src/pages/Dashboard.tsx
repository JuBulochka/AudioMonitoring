import React, { useEffect, useRef } from 'react';
import { Link } from 'react-router-dom';
import { Chart, CategoryScale, LinearScale, BarElement, Tooltip, Legend } from 'chart.js';
import AppLayout from '@/components/Layout/AppLayout';
import Spinner from '@/components/UI/Spinner';
import { useApi } from '@/hooks/useApi';
import { getDashboardSummary } from '@/api/dashboard';
import { timeSince } from '@/utils/formatters';

Chart.register(CategoryScale, LinearScale, BarElement, Tooltip, Legend);

export default function Dashboard() {
  const { data, loading, error, refetch } = useApi(getDashboardSummary, []);
  const chartRef = useRef<HTMLCanvasElement>(null);
  const chartInstance = useRef<Chart | null>(null);

  useEffect(() => {
    if (!data || !chartRef.current) return;

    if (chartInstance.current) chartInstance.current.destroy();

    const ctx = chartRef.current.getContext('2d');
    if (!ctx) return;

    chartInstance.current = new Chart(ctx, {
      type: 'bar',
      data: {
        labels: data.hourly_chart.map((h) => h.hour),
        datasets: [
          {
            label: 'Всего',
            data: data.hourly_chart.map((h) => h.total),
            backgroundColor: 'rgba(88,166,255,.4)',
            borderRadius: 3,
          },
          {
            label: 'Аномалии',
            data: data.hourly_chart.map((h) => h.anomaly),
            backgroundColor: 'rgba(248,81,73,.6)',
            borderRadius: 3,
          },
        ],
      },
      options: {
        responsive: true,
        plugins: {
          legend: { labels: { color: '#8b949e', font: { size: 11 } } },
        },
        scales: {
          x: { ticks: { color: '#8b949e', font: { size: 10 } }, grid: { color: '#21262d' } },
          y: { ticks: { color: '#8b949e', font: { size: 10 } }, grid: { color: '#21262d' } },
        },
      },
    });

    return () => chartInstance.current?.destroy();
  }, [data]);

  const statCards = data
    ? [
        {
          label: 'Устройств онлайн',
          value: `${data.devices.online} / ${data.devices.total}`,
          icon: 'bi-cpu',
          color: 'var(--online-clr)',
          to: '/devices',
        },
        {
          label: 'Пакетов за 24ч',
          value: data.packets_24h.total,
          icon: 'bi-music-note-list',
          color: 'var(--info)',
          to: '/devices',
        },
        {
          label: 'Аномалий за 24ч',
          value: data.packets_24h.anomalies,
          icon: 'bi-exclamation-triangle',
          color: data.packets_24h.anomalies > 0 ? 'var(--warning)' : 'var(--txt-muted)',
          to: '/incidents',
        },
        {
          label: 'Открытых инцидентов',
          value: data.incidents.open,
          icon: 'bi-fire',
          color: data.incidents.open > 0 ? 'var(--danger)' : 'var(--txt-muted)',
          to: '/incidents',
        },
      ]
    : [];

  return (
    <AppLayout title="Дашборд">
      {loading && <Spinner text="Загрузка дашборда…" />}
      {error && (
        <div className="alert" style={{ background: 'rgba(248,81,73,.1)', color: 'var(--danger)', border: '1px solid rgba(248,81,73,.3)', borderRadius: 8 }}>
          <i className="bi bi-exclamation-circle me-2" />
          {error}
          <button className="btn btn-link btn-sm ms-2" onClick={refetch}>Повторить</button>
        </div>
      )}

      {data && (
        <>
          {/* Stat cards */}
          <div className="row g-2 mb-3">
            {statCards.map((card) => (
              <div key={card.label} className="col-6 col-md-3">
                <Link to={card.to} style={{ textDecoration: 'none' }}>
                  <div className="stat-card" style={{ cursor: 'pointer' }}>
                    <div className="label">
                      <i className={`bi ${card.icon} me-1`} />
                      {card.label}
                    </div>
                    <div className="value" style={{ color: card.color }}>
                      {card.value}
                    </div>
                  </div>
                </Link>
              </div>
            ))}
          </div>

          <div className="row g-3">
            {/* Chart */}
            <div className="col-12 col-lg-8">
              <div className="card">
                <div className="card-header">
                  <span style={{ fontSize: '.85rem', fontWeight: 600 }}>
                    <i className="bi bi-bar-chart me-2" />
                    Пакеты за 24 часа
                  </span>
                </div>
                <div className="card-body">
                  <canvas ref={chartRef} height={140} />
                </div>
              </div>
            </div>

            {/* Top problem devices */}
            <div className="col-12 col-lg-4">
              <div className="card h-100">
                <div className="card-header">
                  <span style={{ fontSize: '.85rem', fontWeight: 600 }}>
                    <i className="bi bi-exclamation-triangle me-2 text-warning" />
                    Проблемные устройства (7 дн.)
                  </span>
                </div>
                <div className="card-body p-0">
                  {data.top_problem_devices.length === 0 ? (
                    <div style={{ padding: '1.5rem', textAlign: 'center', color: 'var(--txt-muted)', fontSize: '.82rem' }}>
                      Аномалий не обнаружено
                    </div>
                  ) : (
                    data.top_problem_devices.map((d, idx) => (
                      <Link
                        key={d.device__id}
                        to={`/devices/${d.device__id}`}
                        style={{ textDecoration: 'none' }}
                      >
                        <div
                          style={{
                            display: 'flex',
                            alignItems: 'center',
                            gap: '.75rem',
                            padding: '.5rem .75rem',
                            borderBottom: '1px solid var(--border-clr)',
                          }}
                        >
                          <span
                            style={{
                              width: 22,
                              height: 22,
                              borderRadius: '50%',
                              background: 'var(--bg-card-header)',
                              display: 'flex',
                              alignItems: 'center',
                              justifyContent: 'center',
                              fontSize: '.7rem',
                              color: 'var(--txt-muted)',
                              flexShrink: 0,
                              fontWeight: 600,
                            }}
                          >
                            {idx + 1}
                          </span>
                          <div style={{ flex: 1, minWidth: 0 }}>
                            <div style={{ fontSize: '.8rem', color: 'var(--txt-primary)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                              {d.device__name}
                            </div>
                            <div style={{ fontSize: '.72rem', color: 'var(--txt-muted)', fontFamily: 'monospace' }}>
                              {d.device__serial_number}
                            </div>
                          </div>
                          <span
                            style={{
                              fontSize: '.75rem',
                              fontWeight: 600,
                              color: 'var(--danger)',
                            }}
                          >
                            {d.anomaly_count}
                          </span>
                        </div>
                      </Link>
                    ))
                  )}
                </div>
              </div>
            </div>
          </div>
        </>
      )}
    </AppLayout>
  );
}

import React, { useState, useCallback } from 'react';
import { useParams, Link } from 'react-router-dom';
import AppLayout from '@/components/Layout/AppLayout';
import Spinner from '@/components/UI/Spinner';
import SeverityBadge from '@/components/UI/SeverityBadge';
import { useApi } from '@/hooks/useApi';
import { getIncident, updateIncidentStatus, getIncidentComments, addIncidentComment } from '@/api/incidents';
import { formatDate, timeSince } from '@/utils/formatters';

const STATUS_OPTIONS = [
  { value: 'open', label: 'Открыт' },
  { value: 'acknowledged', label: 'Принят' },
  { value: 'in_progress', label: 'В работе' },
  { value: 'resolved', label: 'Решён' },
  { value: 'closed', label: 'Закрыт' },
  { value: 'false_positive', label: 'Ложная тревога' },
];

const STATUS_COLOR: Record<string, string> = {
  open: 'var(--danger)',
  acknowledged: 'var(--warning)',
  in_progress: 'var(--info)',
  resolved: 'var(--online-clr)',
  closed: 'var(--txt-muted)',
  false_positive: 'var(--txt-muted)',
};

export default function IncidentDetail() {
  const { id } = useParams<{ id: string }>();

  const [newStatus, setNewStatus] = useState('');
  const [comment, setComment] = useState('');
  const [resolution, setResolution] = useState('');
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState('');

  const [newComment, setNewComment] = useState('');
  const [addingComment, setAddingComment] = useState(false);

  const { data: incident, loading: incLoading, refetch: refetchIncident } = useApi(
    () => getIncident(id!),
    [id]
  );

  const { data: comments, loading: commentsLoading, refetch: refetchComments } = useApi(
    () => getIncidentComments(id!),
    [id]
  );

  const handleStatusUpdate = async () => {
    if (!newStatus) return;
    setSaving(true);
    setSaveError('');
    try {
      await updateIncidentStatus(id!, newStatus, comment, resolution);
      setNewStatus('');
      setComment('');
      setResolution('');
      refetchIncident();
      refetchComments();
    } catch {
      setSaveError('Не удалось обновить статус. Попробуйте ещё раз.');
    } finally {
      setSaving(false);
    }
  };

  const handleAddComment = async () => {
    if (!newComment.trim()) return;
    setAddingComment(true);
    try {
      await addIncidentComment(id!, newComment.trim());
      setNewComment('');
      refetchComments();
    } catch { /* ignore */ }
    finally {
      setAddingComment(false);
    }
  };

  if (incLoading) {
    return (
      <AppLayout title="Инцидент">
        <Spinner />
      </AppLayout>
    );
  }

  if (!incident) {
    return (
      <AppLayout title="Инцидент">
        <div style={{ padding: '2rem', color: 'var(--txt-muted)' }}>Инцидент не найден</div>
      </AppLayout>
    );
  }

  const needsResolution = newStatus === 'resolved' || newStatus === 'closed';

  return (
    <AppLayout
      title={
        <>
          <SeverityBadge severity={incident.severity} label="" />
          <span style={{ marginLeft: '.5rem' }}>{incident.title}</span>
        </>
      }
      actions={
        <Link to="/incidents" className="btn btn-sm btn-outline-secondary">
          <i className="bi bi-arrow-left me-1" />
          Назад
        </Link>
      }
    >
      <div className="row g-3">
        {/* ── Left column ─────────────────────────────────────────── */}
        <div className="col-12 col-xl-8">
          {/* Meta cards */}
          <div className="row g-2 mb-3">
            {[
              {
                label: 'Severity',
                value: <SeverityBadge severity={incident.severity} label={incident.severity_display} size="sm" />,
              },
              {
                label: 'Статус',
                value: (
                  <span style={{ fontSize: '.82rem', color: STATUS_COLOR[incident.status] || 'var(--txt-muted)' }}>
                    {incident.status_display}
                  </span>
                ),
              },
              {
                label: 'Тип',
                value: <span style={{ fontSize: '.82rem' }}>{incident.incident_type_display}</span>,
              },
              {
                label: 'Создан',
                value: <span style={{ fontSize: '.82rem' }}>{timeSince(incident.created_at)}</span>,
              },
            ].map((card) => (
              <div key={card.label} className="col-6 col-md-3">
                <div className="stat-card">
                  <div className="label">{card.label}</div>
                  <div style={{ color: 'var(--txt-secondary)', fontWeight: 500 }}>{card.value}</div>
                </div>
              </div>
            ))}
          </div>

          {/* Description */}
          {incident.description && (
            <div className="card mb-3">
              <div className="card-header">
                <span style={{ fontSize: '.85rem', fontWeight: 600 }}>
                  <i className="bi bi-file-text me-2" />
                  Описание
                </span>
              </div>
              <div className="card-body" style={{ fontSize: '.85rem', color: 'var(--txt-secondary)', whiteSpace: 'pre-wrap' }}>
                {incident.description}
              </div>
            </div>
          )}

          {/* Comments */}
          <div className="card">
            <div className="card-header d-flex justify-content-between align-items-center">
              <span style={{ fontSize: '.85rem', fontWeight: 600 }}>
                <i className="bi bi-chat-left-text me-2" />
                Комментарии
              </span>
              {comments && (
                <span style={{ fontSize: '.75rem', color: 'var(--txt-muted)' }}>
                  {comments.length}
                </span>
              )}
            </div>

            {commentsLoading && <Spinner size="sm" />}

            {comments && (
              <>
                {comments.length === 0 ? (
                  <div style={{ padding: '2rem', textAlign: 'center', color: 'var(--txt-muted)', fontSize: '.82rem' }}>
                    Комментариев пока нет
                  </div>
                ) : (
                  comments.map((c) => (
                    <div
                      key={c.id}
                      style={{
                        padding: '.75rem 1rem',
                        borderBottom: '1px solid var(--border-clr)',
                        background: c.is_system ? 'var(--bg-card-header)' : 'transparent',
                      }}
                    >
                      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '.25rem' }}>
                        <span style={{ fontSize: '.75rem', fontWeight: 600, color: 'var(--txt-secondary)' }}>
                          {c.is_system ? (
                            <><i className="bi bi-robot me-1" />Система</>
                          ) : (
                            c.author_name
                          )}
                        </span>
                        <span style={{ fontSize: '.68rem', color: 'var(--txt-muted)' }}>
                          {formatDate(c.created_at)}
                        </span>
                      </div>
                      <div style={{ fontSize: '.82rem', color: 'var(--txt-primary)', whiteSpace: 'pre-wrap' }}>
                        {c.text}
                      </div>
                    </div>
                  ))
                )}

                {/* Add comment */}
                <div style={{ padding: '.75rem 1rem', borderTop: '1px solid var(--border-clr)' }}>
                  <div className="input-group input-group-sm">
                    <input
                      className="form-control"
                      placeholder="Добавить комментарий…"
                      value={newComment}
                      onChange={(e) => setNewComment(e.target.value)}
                      onKeyDown={(e) => {
                        if (e.key === 'Enter' && !e.shiftKey) {
                          e.preventDefault();
                          handleAddComment();
                        }
                      }}
                    />
                    <button
                      className="btn btn-outline-secondary"
                      onClick={handleAddComment}
                      disabled={addingComment || !newComment.trim()}
                    >
                      {addingComment ? (
                        <span className="spinner-border spinner-border-sm" />
                      ) : (
                        <i className="bi bi-send" />
                      )}
                    </button>
                  </div>
                </div>
              </>
            )}
          </div>
        </div>

        {/* ── Right column ─────────────────────────────────────────── */}
        <div className="col-12 col-xl-4">
          {/* Status update */}
          <div className="card mb-3">
            <div className="card-header">
              <span style={{ fontSize: '.85rem', fontWeight: 600 }}>
                <i className="bi bi-pencil-square me-2" />
                Изменить статус
              </span>
            </div>
            <div className="card-body">
              <div className="mb-2">
                <label className="form-label" style={{ fontSize: '.78rem', color: 'var(--txt-muted)' }}>
                  Новый статус
                </label>
                <select
                  className="form-select form-select-sm"
                  value={newStatus}
                  onChange={(e) => setNewStatus(e.target.value)}
                >
                  <option value="">— выберите —</option>
                  {STATUS_OPTIONS.map((o) => (
                    <option key={o.value} value={o.value} disabled={o.value === incident.status}>
                      {o.label}
                    </option>
                  ))}
                </select>
              </div>

              <div className="mb-2">
                <label className="form-label" style={{ fontSize: '.78rem', color: 'var(--txt-muted)' }}>
                  Комментарий
                </label>
                <textarea
                  className="form-control form-control-sm"
                  rows={2}
                  placeholder="Необязательно"
                  value={comment}
                  onChange={(e) => setComment(e.target.value)}
                />
              </div>

              {needsResolution && (
                <div className="mb-2">
                  <label className="form-label" style={{ fontSize: '.78rem', color: 'var(--txt-muted)' }}>
                    Заметки по решению
                  </label>
                  <textarea
                    className="form-control form-control-sm"
                    rows={2}
                    placeholder="Что было сделано?"
                    value={resolution}
                    onChange={(e) => setResolution(e.target.value)}
                  />
                </div>
              )}

              {saveError && (
                <div style={{ fontSize: '.78rem', color: 'var(--danger)', marginBottom: '.5rem' }}>
                  {saveError}
                </div>
              )}

              <button
                className="btn btn-sm btn-outline-primary w-100"
                onClick={handleStatusUpdate}
                disabled={saving || !newStatus}
              >
                {saving ? <span className="spinner-border spinner-border-sm me-1" /> : null}
                Сохранить
              </button>
            </div>
          </div>

          {/* Incident info */}
          <div className="card">
            <div className="card-header">
              <span style={{ fontSize: '.85rem', fontWeight: 600 }}>
                <i className="bi bi-info-circle me-2" />
                Детали
              </span>
            </div>
            <div className="card-body" style={{ fontSize: '.82rem' }}>
              <div className="row g-1">
                {[
                  { label: 'Устройство', value: (
                    <Link to={`/devices/${incident.device.id}`} style={{ color: 'var(--link-clr)', fontFamily: 'monospace', fontSize: '.78rem' }}>
                      {incident.device.serial_number}
                    </Link>
                  )},
                  { label: 'Название устройства', value: incident.device.name },
                  {
                    label: 'Назначен',
                    value: incident.assigned_to
                      ? (incident.assigned_to.full_name || incident.assigned_to.username)
                      : '—',
                  },
                  { label: 'Создан', value: formatDate(incident.created_at) },
                  { label: 'Обновлён', value: formatDate(incident.updated_at) },
                  {
                    label: 'Решён',
                    value: incident.resolved_at ? formatDate(incident.resolved_at) : '—',
                  },
                  ...(incident.trigger_class ? [
                    { label: 'Класс триггера', value: incident.trigger_class },
                    {
                      label: 'Score триггера',
                      value: incident.trigger_score != null
                        ? `${(incident.trigger_score * 100).toFixed(1)}%`
                        : '—',
                    },
                  ] : []),
                ].map((row) => (
                  <div key={row.label} className="col-12" style={{ marginBottom: '.35rem' }}>
                    <div style={{ fontSize: '.68rem', color: 'var(--txt-muted)' }}>{row.label}</div>
                    <div style={{ color: 'var(--txt-primary)', fontSize: '.78rem' }}>{row.value}</div>
                  </div>
                ))}
              </div>

              {incident.resolution_notes && (
                <div style={{ marginTop: '.75rem' }}>
                  <div style={{ fontSize: '.68rem', color: 'var(--txt-muted)', marginBottom: '.25rem' }}>
                    Заметки по решению
                  </div>
                  <div style={{ fontSize: '.78rem', color: 'var(--txt-secondary)', whiteSpace: 'pre-wrap' }}>
                    {incident.resolution_notes}
                  </div>
                </div>
              )}

              <div className="mt-3 d-flex gap-1">
                <Link
                  to={`/devices/${incident.device.id}`}
                  className="btn btn-sm btn-outline-secondary"
                  style={{ fontSize: '.72rem' }}
                >
                  <i className="bi bi-cpu me-1" />
                  Устройство
                </Link>
                <Link
                  to={`/remote-access/commands/${incident.device.id}`}
                  className="btn btn-sm btn-outline-secondary"
                  style={{ fontSize: '.72rem' }}
                >
                  <i className="bi bi-send me-1" />
                  Команды
                </Link>
              </div>
            </div>
          </div>
        </div>
      </div>
    </AppLayout>
  );
}

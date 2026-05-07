import React, { useState, useEffect, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '@/context/AuthContext';
import { getNotifications, markRead, markAllRead } from '@/api/alerts';
import { Notification } from '@/types';

interface TopbarProps {
  title: React.ReactNode;
  actions?: React.ReactNode;
}

export default function Topbar({ title, actions }: TopbarProps) {
  const { user } = useAuth();
  const navigate = useNavigate();

  const [notifications, setNotifications] = useState<Notification[]>([]);
  const [unreadCount, setUnreadCount] = useState(0);
  const [showDropdown, setShowDropdown] = useState(false);
  const dropdownRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    loadNotifications();
    const interval = setInterval(loadNotifications, 30_000);
    return () => clearInterval(interval);
  }, []);

  const loadNotifications = async () => {
    try {
      const res = await getNotifications({ page_size: 10 } as Parameters<typeof getNotifications>[0]);
      setNotifications(res.results);
      setUnreadCount(res.results.filter((n) => !n.is_read).length);
    } catch {
      // ignore
    }
  };

  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (dropdownRef.current && !dropdownRef.current.contains(e.target as Node)) {
        setShowDropdown(false);
      }
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, []);

  const handleMarkRead = async (id: string) => {
    try {
      await markRead(id);
      setNotifications((ns) => ns.map((n) => (n.id === id ? { ...n, is_read: true } : n)));
      setUnreadCount((c) => Math.max(0, c - 1));
    } catch {
      // ignore
    }
  };

  const handleMarkAll = async () => {
    try {
      await markAllRead();
      setNotifications((ns) => ns.map((n) => ({ ...n, is_read: true })));
      setUnreadCount(0);
    } catch {
      // ignore
    }
  };

  const sevIcon: Record<string, string> = {
    critical: 'bi-exclamation-triangle-fill text-danger',
    warning: 'bi-exclamation-circle-fill text-warning',
    info: 'bi-info-circle-fill text-info',
  };

  return (
    <header className="topbar">
      {/* Заголовок страницы */}
      <h1 className="page-title">{title}</h1>

      {/* Правая часть: кастомные действия + колокол уведомлений */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '.5rem' }}>
        {actions}

        {/* Уведомления */}
        <div style={{ position: 'relative' }} ref={dropdownRef}>
          <button
            className="btn btn-sm btn-outline-secondary"
            style={{ position: 'relative' }}
            onClick={() => setShowDropdown((v) => !v)}
            title="Уведомления"
          >
            <i className="bi bi-bell" />
            {unreadCount > 0 && (
              <span className="notif-badge">
                {unreadCount > 99 ? '99+' : unreadCount}
              </span>
            )}
          </button>

          {showDropdown && (
            <div
              style={{
                position: 'absolute',
                right: 0,
                top: 'calc(100% + 6px)',
                width: 340,
                background: 'var(--bg-card)',
                border: '1px solid var(--border-clr)',
                borderRadius: 8,
                zIndex: 600,
                boxShadow: '0 8px 24px rgba(0,0,0,.4)',
              }}
            >
              <div
                style={{
                  padding: '.5rem .75rem',
                  borderBottom: '1px solid var(--border-clr)',
                  display: 'flex',
                  justifyContent: 'space-between',
                  alignItems: 'center',
                }}
              >
                <span style={{ fontSize: '.82rem', fontWeight: 600 }}>Уведомления</span>
                {unreadCount > 0 && (
                  <button
                    className="btn btn-link btn-sm p-0"
                    style={{ fontSize: '.72rem', color: 'var(--link-clr)' }}
                    onClick={handleMarkAll}
                  >
                    Прочитать все
                  </button>
                )}
              </div>
              <div style={{ maxHeight: 320, overflowY: 'auto' }}>
                {notifications.length === 0 ? (
                  <div
                    style={{
                      padding: '1.5rem',
                      textAlign: 'center',
                      color: 'var(--txt-muted)',
                      fontSize: '.82rem',
                    }}
                  >
                    Уведомлений нет
                  </div>
                ) : (
                  notifications.map((n) => (
                    <div
                      key={n.id}
                      style={{
                        padding: '.5rem .75rem',
                        borderBottom: '1px solid var(--border-clr)',
                        background: n.is_read ? 'transparent' : 'rgba(88,166,255,.04)',
                        cursor: 'pointer',
                        display: 'flex',
                        gap: '.5rem',
                        alignItems: 'flex-start',
                      }}
                      onClick={() => {
                        if (!n.is_read) handleMarkRead(n.id);
                        if (n.incident) {
                          navigate(`/incidents/${n.incident.id}`);
                          setShowDropdown(false);
                        } else if (n.device) {
                          navigate(`/devices/${n.device.id}`);
                          setShowDropdown(false);
                        }
                      }}
                    >
                      <i
                        className={`bi ${sevIcon[n.severity] || 'bi-info-circle'}`}
                        style={{ marginTop: 2, flexShrink: 0 }}
                      />
                      <div style={{ flex: 1, minWidth: 0 }}>
                        <div
                          style={{
                            fontSize: '.78rem',
                            fontWeight: n.is_read ? 400 : 600,
                            color: 'var(--txt-primary)',
                          }}
                        >
                          {n.title}
                        </div>
                        <div
                          style={{
                            fontSize: '.72rem',
                            color: 'var(--txt-muted)',
                            marginTop: 1,
                            overflow: 'hidden',
                            textOverflow: 'ellipsis',
                            whiteSpace: 'nowrap',
                          }}
                        >
                          {n.message}
                        </div>
                      </div>
                    </div>
                  ))
                )}
              </div>
              <div style={{ padding: '.5rem .75rem', borderTop: '1px solid var(--border-clr)' }}>
                <button
                  className="btn btn-link btn-sm p-0 w-100 text-center"
                  style={{ fontSize: '.75rem', color: 'var(--txt-muted)' }}
                  onClick={() => {
                    navigate('/alerts');
                    setShowDropdown(false);
                  }}
                >
                  Все уведомления
                </button>
              </div>
            </div>
          )}
        </div>
      </div>
    </header>
  );
}

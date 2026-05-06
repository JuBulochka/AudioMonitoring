import React from 'react';
import { NavLink, useLocation } from 'react-router-dom';
import { useAuth } from '@/context/AuthContext';

interface NavItem {
  to: string;
  icon: string;
  label: string;
  exact?: boolean;
}

interface NavSection {
  title: string;
  items: NavItem[];
}

const NAV: NavSection[] = [
  {
    title: 'Мониторинг',
    items: [
      { to: '/', icon: 'bi-speedometer2', label: 'Дашборд', exact: true },
      { to: '/devices', icon: 'bi-cpu', label: 'Устройства' },
    ],
  },
  {
    title: 'Работа',
    items: [
      { to: '/incidents', icon: 'bi-exclamation-triangle', label: 'Инциденты' },
      { to: '/alerts', icon: 'bi-bell', label: 'Уведомления' },
      { to: '/remote-access', icon: 'bi-terminal', label: 'Удалённый доступ' },
    ],
  },
  {
    title: 'Система',
    items: [
      { to: '/admin/', icon: 'bi-shield-lock', label: 'Администрирование' },
      { to: '/api/docs/', icon: 'bi-file-earmark-code', label: 'API Docs' },
    ],
  },
];

export default function Sidebar() {
  const location = useLocation();
  const { user, logout } = useAuth();

  const isActive = (to: string, exact?: boolean) => {
    if (exact) return location.pathname === to;
    return location.pathname.startsWith(to) && to !== '/';
  };

  return (
    <aside className="sidebar">
      {/* Logo */}
      <NavLink to="/" className="sidebar-logo">
        <i className="bi bi-fire" style={{ color: '#f85149' }} />
        <span>САЮРИ</span>
      </NavLink>

      {/* Navigation */}
      <nav style={{ flex: 1, paddingTop: '.5rem' }}>
        {NAV.map((section) => (
          <div key={section.title}>
            <div className="sidebar-section">{section.title}</div>
            {section.items.map((item) => {
              // Внешние ссылки (Django-served pages)
              if (item.to.startsWith('/api/') || item.to.startsWith('/admin')) {
                return (
                  <a key={item.to} href={item.to} className="sidebar-link" target="_blank" rel="noreferrer">
                    <i className={`bi ${item.icon}`} />
                    {item.label}
                  </a>
                );
              }
              return (
                <NavLink
                  key={item.to}
                  to={item.to}
                  className={`sidebar-link ${isActive(item.to, item.exact) ? 'active' : ''}`}
                >
                  <i className={`bi ${item.icon}`} />
                  {item.label}
                </NavLink>
              );
            })}
          </div>
        ))}
      </nav>

      {/* Footer */}
      <div className="sidebar-footer">
        {user && (
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '.5rem',
              marginBottom: '.5rem',
            }}
          >
            <div
              style={{
                width: 28,
                height: 28,
                borderRadius: '50%',
                background: 'var(--bg-card-header)',
                border: '1px solid var(--border-clr)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                fontSize: '.75rem',
                color: 'var(--txt-muted)',
                flexShrink: 0,
              }}
            >
              <i className="bi bi-person" />
            </div>
            <div style={{ minWidth: 0, flex: 1 }}>
              <div
                style={{
                  fontSize: '.78rem',
                  fontWeight: 500,
                  color: 'var(--txt-primary)',
                  overflow: 'hidden',
                  textOverflow: 'ellipsis',
                  whiteSpace: 'nowrap',
                }}
              >
                {user.full_name || user.username}
              </div>
              <div style={{ fontSize: '.68rem', color: 'var(--txt-muted)' }}>
                {user.role_display || user.role}
              </div>
            </div>
          </div>
        )}
        <button
          className="btn btn-sm btn-outline-secondary w-100"
          onClick={logout}
          style={{ fontSize: '.75rem' }}
        >
          <i className="bi bi-box-arrow-right me-1" />
          Выйти
        </button>
      </div>
    </aside>
  );
}

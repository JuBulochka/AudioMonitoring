import React from 'react';
import { Link, NavLink, useLocation } from 'react-router-dom';
import { useAuth } from '@/context/AuthContext';
import { useTheme } from '@/context/ThemeContext';

interface NavItem {
  to: string;
  icon: string;
  label: string;
  exact?: boolean;
  external?: boolean;
}

interface NavSection {
  title: string;
  items: NavItem[];
}

const NAV: NavSection[] = [
  {
    title: 'Мониторинг',
    items: [
      { to: '/', icon: 'bi-grid-1x2', label: 'Дашборд', exact: true },
      { to: '/devices', icon: 'bi-cpu', label: 'Устройства' },
      { to: '/map/', icon: 'bi-map', label: 'Карта', external: true },
    ],
  },
  {
    title: 'Работа',
    items: [
      { to: '/incidents', icon: 'bi-exclamation-triangle', label: 'Инциденты' },
      { to: '/maintenance/', icon: 'bi-tools', label: 'Обслуживание', external: true },
      { to: '/alerts', icon: 'bi-bell', label: 'Уведомления' },
      { to: '/remote-access', icon: 'bi-terminal', label: 'Удалённый доступ' },
    ],
  },
  {
    title: 'Инструменты',
    items: [
      { to: '/audio-test/', icon: 'bi-soundwave', label: 'Тест аудио', external: true },
    ],
  },
  {
    title: 'Система',
    items: [
      { to: '/admin/', icon: 'bi-shield-lock', label: 'Админка', external: true },
      { to: '/api/docs/', icon: 'bi-code-square', label: 'API Docs', external: true },
    ],
  },
];

export default function Sidebar() {
  const location = useLocation();
  const { user, logout } = useAuth();
  const { theme, toggleTheme } = useTheme();

  const isActive = (to: string, exact?: boolean) => {
    if (exact) return location.pathname === to;
    return location.pathname.startsWith(to) && to !== '/';
  };

  return (
    <aside className="sidebar">
      {/* Логотип */}
      <Link to="/" className="brand">
        <img src="/static/img/logo.png" alt="PumpJack Monitor" style={{ width: 168, height: 'auto' }} />
      </Link>

      {/* Навигация */}
      <nav style={{ flex: 1, paddingTop: '.5rem', paddingBottom: '.5rem' }}>
        {NAV.map((section) => (
          <div key={section.title}>
            <div className="sidebar-section">{section.title}</div>
            {section.items.map((item) => {
              if (item.external) {
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
                  className={`sidebar-link${isActive(item.to, item.exact) ? ' active' : ''}`}
                >
                  <i className={`bi ${item.icon}`} />
                  {item.label}
                </NavLink>
              );
            })}
          </div>
        ))}
      </nav>

      {/* Подвал: пользователь + переключатель темы */}
      <div className="sidebar-footer">
        {user && (
          <div style={{ minWidth: 0, flex: 1 }}>
            <div style={{ color: 'var(--txt-primary)', fontWeight: 500, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
              {user.full_name || user.username}
            </div>
            <div style={{ fontSize: '.7rem', color: 'var(--txt-muted)' }}>
              {user.role_display || user.role}
            </div>
            <a
              href="#"
              style={{ color: 'var(--txt-muted)', fontSize: '.75rem', textDecoration: 'none' }}
              onClick={(e) => { e.preventDefault(); logout(); }}
            >
              Выйти
            </a>
          </div>
        )}
        <button
          className="theme-toggle"
          onClick={toggleTheme}
          title={theme === 'dark' ? 'Светлая тема' : 'Тёмная тема'}
        >
          <i className={`bi ${theme === 'dark' ? 'bi-sun' : 'bi-moon'}`} />
        </button>
      </div>
    </aside>
  );
}

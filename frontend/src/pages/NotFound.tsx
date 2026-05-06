import React from 'react';
import { Link } from 'react-router-dom';
import AppLayout from '@/components/Layout/AppLayout';

export default function NotFound() {
  return (
    <AppLayout title="404">
      <div className="text-center" style={{ padding: '5rem 1rem', color: 'var(--txt-muted)' }}>
        <i
          className="bi bi-exclamation-circle"
          style={{ fontSize: '3rem', display: 'block', marginBottom: '1rem', color: 'var(--txt-secondary)' }}
        />
        <h4 style={{ color: 'var(--txt-primary)', marginBottom: '.5rem' }}>Страница не найдена</h4>
        <p style={{ fontSize: '.9rem', marginBottom: '1.5rem' }}>
          Запрашиваемый ресурс не существует или был перемещён.
        </p>
        <Link to="/" className="btn btn-sm btn-outline-secondary">
          <i className="bi bi-house me-1" />
          На главную
        </Link>
      </div>
    </AppLayout>
  );
}

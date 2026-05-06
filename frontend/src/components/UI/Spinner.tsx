import React from 'react';

interface SpinnerProps {
  size?: 'sm' | 'md' | 'lg';
  text?: string;
}

export default function Spinner({ size = 'md', text }: SpinnerProps) {
  const sz = size === 'sm' ? '1rem' : size === 'lg' ? '3rem' : '2rem';
  return (
    <div
      style={{
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        gap: '.75rem',
        padding: '2rem',
        color: 'var(--txt-muted)',
      }}
    >
      <div
        className="spinner-border"
        style={{ width: sz, height: sz, color: 'var(--link-clr)' }}
        role="status"
      >
        <span className="visually-hidden">Загрузка…</span>
      </div>
      {text && <span style={{ fontSize: '.82rem' }}>{text}</span>}
    </div>
  );
}

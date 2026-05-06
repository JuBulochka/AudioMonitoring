import React from 'react';

interface SeverityBadgeProps {
  severity: string;
  label: string;
  size?: 'sm' | 'md';
}

const colors: Record<string, string> = {
  critical: 'var(--danger)',
  warning: 'var(--warning)',
  info: 'var(--info)',
  normal: 'var(--online-clr)',
};

export default function SeverityBadge({ severity, label, size = 'md' }: SeverityBadgeProps) {
  const color = colors[severity] || 'var(--txt-muted)';
  const fontSize = size === 'sm' ? '.72rem' : '.78rem';
  return (
    <span style={{ color, fontSize, display: 'inline-flex', alignItems: 'center', gap: '.3rem' }}>
      <i className="bi bi-circle-fill" style={{ fontSize: '.45rem' }} />
      {label}
    </span>
  );
}

import React from 'react';

interface PaginationProps {
  page: number;
  totalPages: number;
  totalCount: number;
  pageSize: number;
  onChange: (page: number) => void;
  noun?: string; // «записей», «инцидентов» и т.д.
}

export default function Pagination({
  page,
  totalPages,
  totalCount,
  pageSize,
  onChange,
  noun = 'записей',
}: PaginationProps) {
  if (totalPages <= 1) return null;

  const pages: (number | '...')[] = [];
  for (let i = 1; i <= totalPages; i++) {
    if (i === 1 || i === totalPages || (i >= page - 2 && i <= page + 2)) {
      pages.push(i);
    } else if (pages[pages.length - 1] !== '...') {
      pages.push('...');
    }
  }

  const from = (page - 1) * pageSize + 1;
  const to = Math.min(page * pageSize, totalCount);

  return (
    <div
      className="d-flex align-items-center justify-content-between"
      style={{ padding: '.5rem .75rem' }}
    >
      <span style={{ fontSize: '.75rem', color: 'var(--txt-muted)' }}>
        {from}–{to} из {totalCount} {noun}
      </span>
      <nav>
        <ul className="pagination pagination-sm mb-0" style={{ gap: 2 }}>
          <li className={`page-item ${page === 1 ? 'disabled' : ''}`}>
            <button className="page-link" onClick={() => onChange(1)} style={{ fontSize: '.75rem' }}>
              «
            </button>
          </li>
          <li className={`page-item ${page === 1 ? 'disabled' : ''}`}>
            <button
              className="page-link"
              onClick={() => onChange(page - 1)}
              style={{ fontSize: '.75rem' }}
            >
              ‹
            </button>
          </li>

          {pages.map((p, idx) =>
            p === '...' ? (
              <li key={`dots-${idx}`} className="page-item disabled">
                <span className="page-link" style={{ fontSize: '.75rem' }}>
                  …
                </span>
              </li>
            ) : (
              <li key={p} className={`page-item ${p === page ? 'active' : ''}`}>
                <button
                  className="page-link"
                  onClick={() => onChange(p as number)}
                  style={{ fontSize: '.75rem' }}
                >
                  {p}
                </button>
              </li>
            )
          )}

          <li className={`page-item ${page === totalPages ? 'disabled' : ''}`}>
            <button
              className="page-link"
              onClick={() => onChange(page + 1)}
              style={{ fontSize: '.75rem' }}
            >
              ›
            </button>
          </li>
          <li className={`page-item ${page === totalPages ? 'disabled' : ''}`}>
            <button
              className="page-link"
              onClick={() => onChange(totalPages)}
              style={{ fontSize: '.75rem' }}
            >
              »
            </button>
          </li>
        </ul>
      </nav>
    </div>
  );
}

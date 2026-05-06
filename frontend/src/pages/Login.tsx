import React, { useState, FormEvent } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { useAuth } from '@/context/AuthContext';

export default function Login() {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const { login } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const from = (location.state as { from?: string })?.from || '/';

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setError('');
    setLoading(true);
    try {
      await login(username, password);
      navigate(from, { replace: true });
    } catch {
      setError('Неверный логин или пароль');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div
      style={{
        minHeight: '100vh',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        background: 'var(--bg-body)',
      }}
    >
      <div style={{ width: '100%', maxWidth: 380 }}>
        {/* Logo */}
        <div style={{ textAlign: 'center', marginBottom: '2rem' }}>
          <div style={{ fontSize: '2rem' }}>🔥</div>
          <h1 style={{ fontSize: '1.4rem', fontWeight: 700, color: 'var(--txt-primary)', margin: '.5rem 0 .25rem' }}>
            САЮРИ
          </h1>
          <p style={{ fontSize: '.82rem', color: 'var(--txt-muted)', margin: 0 }}>
            Система аудиомониторинга качалок
          </p>
        </div>

        <div className="card">
          <div className="card-body" style={{ padding: '1.5rem' }}>
            <form onSubmit={handleSubmit}>
              {error && (
                <div
                  className="alert alert-danger"
                  style={{
                    background: 'rgba(248,81,73,.1)',
                    border: '1px solid rgba(248,81,73,.3)',
                    color: 'var(--danger)',
                    borderRadius: 6,
                    padding: '.5rem .75rem',
                    fontSize: '.82rem',
                    marginBottom: '1rem',
                  }}
                >
                  <i className="bi bi-exclamation-circle me-1" />
                  {error}
                </div>
              )}

              <div className="mb-3">
                <label style={{ fontSize: '.82rem', color: 'var(--txt-muted)', marginBottom: '.25rem', display: 'block' }}>
                  Логин
                </label>
                <input
                  type="text"
                  className="form-control"
                  value={username}
                  onChange={(e) => setUsername(e.target.value)}
                  required
                  autoFocus
                  autoComplete="username"
                  placeholder="username"
                />
              </div>

              <div className="mb-4">
                <label style={{ fontSize: '.82rem', color: 'var(--txt-muted)', marginBottom: '.25rem', display: 'block' }}>
                  Пароль
                </label>
                <input
                  type="password"
                  className="form-control"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  required
                  autoComplete="current-password"
                  placeholder="••••••••••"
                />
              </div>

              <button
                type="submit"
                className="btn w-100"
                disabled={loading}
                style={{
                  background: 'var(--accent)',
                  color: '#fff',
                  border: 'none',
                  fontWeight: 600,
                }}
              >
                {loading ? (
                  <>
                    <span className="spinner-border spinner-border-sm me-2" />
                    Вход…
                  </>
                ) : (
                  <>
                    <i className="bi bi-box-arrow-in-right me-2" />
                    Войти
                  </>
                )}
              </button>
            </form>
          </div>
        </div>
      </div>
    </div>
  );
}

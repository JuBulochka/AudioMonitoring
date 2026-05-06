import React from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { AuthProvider, useAuth } from '@/context/AuthContext';
import { ThemeProvider } from '@/context/ThemeContext';

import Login from '@/pages/Login';
import Dashboard from '@/pages/Dashboard';
import DeviceList from '@/pages/devices/DeviceList';
import DeviceDetail from '@/pages/devices/DeviceDetail';
import IncidentList from '@/pages/incidents/IncidentList';
import IncidentDetail from '@/pages/incidents/IncidentDetail';
import AlertList from '@/pages/alerts/AlertList';
import RemoteAccess from '@/pages/remote/RemoteAccess';
import Commands from '@/pages/remote/Commands';
import NotFound from '@/pages/NotFound';

// ── Protected route guard ────────────────────────────────────────────────────
function ProtectedRoute({ children }: { children: React.ReactNode }) {
  const { isAuthenticated, isLoading } = useAuth();

  if (isLoading) {
    return (
      <div
        style={{
          display: 'flex',
          justifyContent: 'center',
          alignItems: 'center',
          height: '100vh',
          background: 'var(--bg-body)',
        }}
      >
        <div className="spinner-border" style={{ color: 'var(--link-clr)' }} role="status">
          <span className="visually-hidden">Загрузка…</span>
        </div>
      </div>
    );
  }

  if (!isAuthenticated) {
    return <Navigate to="/login" replace />;
  }

  return <>{children}</>;
}

// ── Root app ─────────────────────────────────────────────────────────────────
export default function App() {
  return (
    <ThemeProvider>
      <AuthProvider>
        <BrowserRouter>
          <Routes>
            {/* Public */}
            <Route path="/login" element={<Login />} />

            {/* Protected */}
            <Route
              path="/"
              element={
                <ProtectedRoute>
                  <Dashboard />
                </ProtectedRoute>
              }
            />
            <Route
              path="/devices"
              element={
                <ProtectedRoute>
                  <DeviceList />
                </ProtectedRoute>
              }
            />
            <Route
              path="/devices/:id"
              element={
                <ProtectedRoute>
                  <DeviceDetail />
                </ProtectedRoute>
              }
            />
            <Route
              path="/incidents"
              element={
                <ProtectedRoute>
                  <IncidentList />
                </ProtectedRoute>
              }
            />
            <Route
              path="/incidents/:id"
              element={
                <ProtectedRoute>
                  <IncidentDetail />
                </ProtectedRoute>
              }
            />
            <Route
              path="/alerts"
              element={
                <ProtectedRoute>
                  <AlertList />
                </ProtectedRoute>
              }
            />
            <Route
              path="/remote-access"
              element={
                <ProtectedRoute>
                  <RemoteAccess />
                </ProtectedRoute>
              }
            />
            <Route
              path="/remote-access/commands/:deviceId"
              element={
                <ProtectedRoute>
                  <Commands />
                </ProtectedRoute>
              }
            />

            {/* 404 */}
            <Route path="*" element={<NotFound />} />
          </Routes>
        </BrowserRouter>
      </AuthProvider>
    </ThemeProvider>
  );
}

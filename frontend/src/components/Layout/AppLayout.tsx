import React, { ReactNode } from 'react';
import Sidebar from './Sidebar';
import Topbar from './Topbar';

interface AppLayoutProps {
  title: ReactNode;
  actions?: ReactNode;
  children: ReactNode;
}

export default function AppLayout({ title, actions, children }: AppLayoutProps) {
  return (
    <>
      <Sidebar />
      <div className="main-wrap">
        <Topbar title={title} actions={actions} />
        <main className="page-content">{children}</main>
      </div>
    </>
  );
}

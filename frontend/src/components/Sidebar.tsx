// frontend/src/components/Sidebar.tsx

import React from 'react';
import { NavLink } from 'react-router-dom';
import {
  LayoutDashboard,
  ListFilter,
  Activity,
  LineChart,
  Scale,
  Cpu,
  FileText,
  GitPullRequest,
  ShieldCheck,
} from 'lucide-react';

export const Sidebar: React.FC = () => {
  const navItems = [
    { name: 'Overview', path: '/', icon: <LayoutDashboard size={18} /> },
    { name: 'Analyze Commit', path: '/analyze', icon: <Activity size={18} /> },
    { name: 'Review Queue', path: '/queue', icon: <ListFilter size={18} /> },
    { name: 'Repository Insights', path: '/insights', icon: <LineChart size={18} /> },
    { name: 'Reliability & Outcomes', path: '/reliability', icon: <Scale size={18} /> },
    { name: 'Model & Reports', path: '/reports', icon: <FileText size={18} /> },
    { name: 'Developer Integration', path: '/developer', icon: <GitPullRequest size={18} /> },
  ];

  return (
    <aside style={{ width: '260px', backgroundColor: '#0d1424', borderRight: '1px solid #1e293b', minHeight: '100vh', display: 'flex', flexDirection: 'column' }}>
      {/* Brand Header */}
      <div style={{ padding: '1.25rem 1rem', borderBottom: '1px solid #1e293b', display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
        <div style={{ width: '36px', height: '36px', borderRadius: '8px', backgroundColor: '#0284c7', display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#fff', fontSize: '20px' }}>
          🛡️
        </div>
        <div>
          <div style={{ fontWeight: 700, fontSize: '0.95rem', color: '#f8fafc', letterSpacing: '-0.01em' }}>
            Quality Intelligence
          </div>
          <div style={{ fontSize: '0.72rem', color: '#38bdf8', fontWeight: 500 }}>
            Code-Change Risk SaaS
          </div>
        </div>
      </div>

      {/* Model Spec Badge */}
      <div style={{ padding: '0.75rem 1rem' }}>
        <div style={{ backgroundColor: '#131b2e', border: '1px solid #1e293b', borderRadius: '6px', padding: '0.5rem 0.75rem', fontSize: '0.72rem', color: '#94a3b8' }}>
          <div style={{ color: '#f1f5f9', fontWeight: 600 }}>RandomForest (200 trees)</div>
          <div style={{ color: '#64748b', fontSize: '0.68rem', marginTop: '2px' }}>
            26 features • ApacheJIT Schema
          </div>
        </div>
      </div>

      {/* Navigation Items */}
      <nav style={{ flex: 1, padding: '0.5rem 0.75rem', display: 'flex', flexDirection: 'column', gap: '0.25rem' }}>
        {navItems.map((item) => (
          <NavLink
            key={item.path}
            to={item.path}
            end={item.path === '/'}
            style={({ isActive }) => ({
              display: 'flex',
              alignItems: 'center',
              gap: '0.75rem',
              padding: '0.55rem 0.75rem',
              borderRadius: '6px',
              fontSize: '0.85rem',
              fontWeight: isActive ? 600 : 500,
              color: isActive ? '#38bdf8' : '#94a3b8',
              backgroundColor: isActive ? 'rgba(56, 189, 248, 0.1)' : 'transparent',
              textDecoration: 'none',
              transition: 'all 0.15s ease',
            })}
          >
            {item.icon}
            <span>{item.name}</span>
          </NavLink>
        ))}
      </nav>

      {/* Footer System Status */}
      <div style={{ padding: '1rem', borderTop: '1px solid #1e293b', fontSize: '0.72rem', color: '#64748b' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '6px', color: '#10b981', fontWeight: 600, marginBottom: '4px' }}>
          <ShieldCheck size={14} /> System Operational
        </div>
        <div>Streamlit & FastAPI Sync</div>
      </div>
    </aside>
  );
};

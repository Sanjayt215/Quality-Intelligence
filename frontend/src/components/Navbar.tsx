// frontend/src/components/Navbar.tsx

import React, { useEffect, useState } from 'react';
import { api } from '../api/client';
import { PolicyConfig } from '../api/types';

interface NavbarProps {
  currentPolicy: string;
  onPolicyChange: (policyName: string, threshold: number) => void;
}

export const Navbar: React.FC<NavbarProps> = ({ currentPolicy, onPolicyChange }) => {
  const [policies, setPolicies] = useState<Record<string, PolicyConfig>>({});
  const [uptime, setUptime] = useState<number>(0);

  useEffect(() => {
    api.getPolicies().then(setPolicies).catch(console.error);
    api.getHealth().then((h) => setUptime(h.uptime_seconds)).catch(console.error);
  }, []);

  return (
    <header style={{ height: '60px', backgroundColor: '#0d1424', borderBottom: '1px solid #1e293b', display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '0 1.5rem' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: '1rem' }}>
        <span style={{ fontSize: '0.85rem', color: '#64748b' }}>Environment:</span>
        <span style={{ fontSize: '0.8rem', color: '#10b981', fontWeight: 600, display: 'flex', alignItems: 'center', gap: '4px' }}>
          ● Live API (Port 8000)
        </span>
        <span style={{ color: '#334155' }}>|</span>
        <span style={{ fontSize: '0.8rem', color: '#94a3b8' }}>
          Streamlit Dashboard: <a href="http://localhost:8501" target="_blank" rel="noreferrer" style={{ color: '#38bdf8', textDecoration: 'none' }}>:8501</a>
        </span>
      </div>

      <div style={{ display: 'flex', alignItems: 'center', gap: '1rem' }}>
        <label htmlFor="triage-policy-select" style={{ fontSize: '0.8rem', color: '#94a3b8', fontWeight: 500 }}>Active Review Policy:</label>
        <select
          id="triage-policy-select"
          className="qi-select"
          value={currentPolicy}
          onChange={(e) => {
            const pol = policies[e.target.value];
            if (pol) {
              onPolicyChange(pol.policy_name, pol.threshold);
            }
          }}
          style={{ minWidth: '220px' }}
        >
          {Object.keys(policies).map((pName) => (
            <option key={pName} value={pName}>
              {policies[pName].badge} (τ = {policies[pName].threshold.toFixed(2)})
            </option>
          ))}
        </select>
      </div>
    </header>
  );
};

// frontend/src/components/RiskBadge.tsx

import React from 'react';

interface RiskBadgeProps {
  tier: string;
}

export const RiskBadge: React.FC<RiskBadgeProps> = ({ tier }) => {
  const normalized = tier.toLowerCase();
  if (normalized.includes('critical')) {
    return <span className="badge-critical">🔴 CRITICAL RISK</span>;
  }
  if (normalized.includes('elevated')) {
    return <span className="badge-elevated">🟠 ELEVATED RISK</span>;
  }
  if (normalized.includes('moderate')) {
    return <span className="badge-moderate">🟡 MODERATE RISK</span>;
  }
  return <span className="badge-low">🟢 LOW RISK</span>;
};

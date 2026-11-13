// frontend/src/components/MetricCard.tsx

import React from 'react';

interface MetricCardProps {
  label: string;
  value: string | number;
  subtext?: string;
  icon?: React.ReactNode;
  badge?: string;
  trendPositive?: boolean;
}

export const MetricCard: React.FC<MetricCardProps> = ({
  label,
  value,
  subtext,
  icon,
  badge,
}) => {
  return (
    <div className="qi-card flex flex-col justify-between">
      <div className="flex items-center justify-between">
        <span className="metric-label">{label}</span>
        {icon && <div className="text-slate-400">{icon}</div>}
      </div>
      <div className="my-2">
        <div className="metric-value">{value}</div>
      </div>
      <div className="flex items-center justify-between text-xs text-slate-400">
        <span>{subtext}</span>
        {badge && (
          <span className="px-2 py-0.5 rounded text-[11px] font-semibold bg-sky-950 text-sky-400 border border-sky-800">
            {badge}
          </span>
        )}
      </div>
    </div>
  );
};

// frontend/src/components/DataScopeBadge.tsx - Consistent Visual Source Labels

import React from 'react';

export type DataScopeType =
  | 'REAL_GIT_DATA'
  | 'REAL_REPOSITORY_HISTORY'
  | 'MODEL_PREDICTION'
  | 'APACHEJIT_HISTORICAL_BENCHMARK'
  | 'SYNTHETIC_DEMONSTRATION'
  | 'INSUFFICIENT_DATA'
  | 'OUTCOME_PENDING';

interface DataScopeBadgeProps {
  scope: DataScopeType | string;
  size?: 'sm' | 'md';
}

const SCOPE_CONFIG: Record<string, { label: string; bg: string; text: string; border: string }> = {
  REAL_GIT_DATA: {
    label: 'REAL GIT DATA',
    bg: 'rgba(56, 189, 248, 0.12)',
    text: '#38bdf8',
    border: 'rgba(56, 189, 248, 0.35)',
  },
  REAL_GIT_COMMIT: {
    label: 'REAL GIT DATA',
    bg: 'rgba(56, 189, 248, 0.12)',
    text: '#38bdf8',
    border: 'rgba(56, 189, 248, 0.35)',
  },
  REAL_GIT_BRANCH: {
    label: 'REAL BRANCH BATCH',
    bg: 'rgba(56, 189, 248, 0.12)',
    text: '#38bdf8',
    border: 'rgba(56, 189, 248, 0.35)',
  },
  REAL_REPOSITORY_HISTORY: {
    label: 'REAL REPOSITORY HISTORY',
    bg: 'rgba(52, 211, 153, 0.12)',
    text: '#34d399',
    border: 'rgba(52, 211, 153, 0.35)',
  },
  MODEL_PREDICTION: {
    label: 'MODEL PREDICTION',
    bg: 'rgba(168, 85, 247, 0.12)',
    text: '#c084fc',
    border: 'rgba(168, 85, 247, 0.35)',
  },
  APACHEJIT_HISTORICAL_BENCHMARK: {
    label: 'APACHEJIT HISTORICAL BENCHMARK',
    bg: 'rgba(251, 191, 36, 0.12)',
    text: '#fbbf24',
    border: 'rgba(251, 191, 36, 0.35)',
  },
  SYNTHETIC_DEMO: {
    label: 'SYNTHETIC DEMONSTRATION',
    bg: 'rgba(244, 63, 94, 0.12)',
    text: '#fb7185',
    border: 'rgba(244, 63, 94, 0.35)',
  },
  SYNTHETIC_DEMONSTRATION: {
    label: 'SYNTHETIC DEMONSTRATION',
    bg: 'rgba(244, 63, 94, 0.12)',
    text: '#fb7185',
    border: 'rgba(244, 63, 94, 0.35)',
  },
  INSUFFICIENT_DATA: {
    label: 'INSUFFICIENT DATA',
    bg: 'rgba(148, 163, 184, 0.12)',
    text: '#94a3b8',
    border: 'rgba(148, 163, 184, 0.35)',
  },
  OUTCOME_PENDING: {
    label: 'OUTCOME PENDING',
    bg: 'rgba(251, 146, 60, 0.12)',
    text: '#fb923c',
    border: 'rgba(251, 146, 60, 0.35)',
  },
};

export const DataScopeBadge: React.FC<DataScopeBadgeProps> = ({ scope, size = 'sm' }) => {
  const normalized = (scope || 'INSUFFICIENT_DATA').toUpperCase().replace(/\s+/g, '_');
  const cfg = SCOPE_CONFIG[normalized] || {
    label: scope.toUpperCase(),
    bg: 'rgba(148, 163, 184, 0.12)',
    text: '#94a3b8',
    border: 'rgba(148, 163, 184, 0.35)',
  };

  const isSmall = size === 'sm';

  return (
    <span
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        gap: '0.3rem',
        padding: isSmall ? '0.15rem 0.45rem' : '0.25rem 0.65rem',
        borderRadius: '4px',
        fontSize: isSmall ? '0.68rem' : '0.75rem',
        fontWeight: 700,
        letterSpacing: '0.04em',
        backgroundColor: cfg.bg,
        color: cfg.text,
        border: `1px solid ${cfg.border}`,
        whiteSpace: 'nowrap',
        userSelect: 'none',
      }}
    >
      <span
        style={{
          width: isSmall ? '5px' : '6px',
          height: isSmall ? '5px' : '6px',
          borderRadius: '50%',
          backgroundColor: cfg.text,
        }}
      />
      {cfg.label}
    </span>
  );
};

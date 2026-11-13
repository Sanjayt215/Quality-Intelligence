// frontend/src/components/ActiveRepoBar.tsx - Persistent Active Context Bar across all pages

import React from 'react';
import { Link } from 'react-router-dom';
import { useAnalysis } from '../context/AnalysisContext';
import { DataScopeBadge } from './DataScopeBadge';
import { GitBranch, GitCommit, Play, RotateCcw, ShieldAlert, CheckCircle2, ArrowRight } from 'lucide-react';

export const ActiveRepoBar: React.FC = () => {
  const { selectedAnalysis, analysisSource, exitDemoMode } = useAnalysis();

  if (!selectedAnalysis) {
    return (
      <div
        style={{
          backgroundColor: '#0f172a',
          border: '1px solid #1e293b',
          borderRadius: '8px',
          padding: '0.6rem 1rem',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          flexWrap: 'wrap',
          gap: '0.75rem',
          fontSize: '0.82rem',
          color: '#94a3b8',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem' }}>
          <GitBranch size={16} color="#64748b" />
          <span>
            No active Git commit selected. Connect a local repository or public GitHub URL to inspect real code changes.
          </span>
        </div>
        <Link
          to="/analyze"
          className="btn-primary"
          style={{
            textDecoration: 'none',
            fontSize: '0.75rem',
            padding: '0.3rem 0.75rem',
            display: 'flex',
            alignItems: 'center',
            gap: '0.35rem',
          }}
        >
          <Play size={12} /> Connect & Analyze Real Commit
        </Link>
      </div>
    );
  }

  const repoName = selectedAnalysis.repository_name || selectedAnalysis.project || 'Unknown Repo';
  const branchName = selectedAnalysis.display_branch_name || selectedAnalysis.branch_name || 'HEAD';
  const fullSha = selectedAnalysis.commit_sha || selectedAnalysis.commit_id || '';
  const shortSha = selectedAnalysis.commit_short_sha || fullSha.substring(0, 8);
  const runId = selectedAnalysis.run_id ? selectedAnalysis.run_id.substring(0, 24) : 'Active Session';
  const rawScore = selectedAnalysis.defect_risk_score !== undefined ? selectedAnalysis.defect_risk_score : (selectedAnalysis.risk_score || selectedAnalysis.model_score || 0);
  const scorePct = (rawScore * 100).toFixed(1);
  const isFlagged = selectedAnalysis.flagged_for_review === 'FLAGGED' || selectedAnalysis.review_decision === 'FLAGGED' || rawScore >= 0.50;
  const isSynthetic = analysisSource === 'SYNTHETIC_DEMO';
  const isBaselineSha = fullSha.toLowerCase().startsWith('b9b30efb');

  return (
    <div
      style={{
        backgroundColor: '#0b1329',
        border: `1px solid ${isSynthetic ? 'rgba(244, 63, 94, 0.4)' : '#1e3a5f'}`,
        borderRadius: '8px',
        padding: '0.55rem 1rem',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        flexWrap: 'wrap',
        gap: '0.75rem',
        fontSize: '0.82rem',
      }}
    >
      {/* Left items: ACTIVE ANALYSIS Badge | Repo | Branch | Commit SHA | Run ID */}
      <div style={{ display: 'flex', alignItems: 'center', flexWrap: 'wrap', gap: '0.75rem' }}>
        <div style={{
          backgroundColor: isSynthetic ? 'rgba(244, 63, 94, 0.2)' : 'rgba(56, 189, 248, 0.2)',
          color: isSynthetic ? '#fb7185' : '#38bdf8',
          border: `1px solid ${isSynthetic ? '#f43f5e' : '#0284c7'}`,
          borderRadius: '4px',
          padding: '0.15rem 0.5rem',
          fontSize: '0.7rem',
          fontWeight: 700,
          letterSpacing: '0.04em'
        }}>
          ACTIVE ANALYSIS
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '0.35rem', color: '#f8fafc', fontWeight: 600 }}>
          <GitBranch size={15} color={isSynthetic ? '#fb7185' : '#38bdf8'} />
          <span>{repoName}</span>
        </div>

        <span style={{ color: '#334155' }}>|</span>

        <div style={{ display: 'flex', alignItems: 'center', gap: '0.35rem', color: '#94a3b8' }}>
          <span style={{ fontSize: '0.72rem', color: '#64748b' }}>Branch:</span>
          <span style={{ color: '#cbd5e1', fontWeight: 500 }}>{branchName}</span>
        </div>

        <span style={{ color: '#334155' }}>|</span>

        <div style={{ display: 'flex', alignItems: 'center', gap: '0.35rem', color: '#94a3b8' }}>
          <GitCommit size={14} color="#38bdf8" />
          <code
            style={{ color: '#38bdf8', fontSize: '0.78rem', backgroundColor: '#0f172a', padding: '0.1rem 0.4rem', borderRadius: '4px' }}
            title={`Full Commit SHA: ${fullSha}`}
          >
            {shortSha}
          </code>
          {isBaselineSha ? (
            <span style={{ fontSize: '0.65rem', backgroundColor: 'rgba(52, 211, 153, 0.15)', color: '#34d399', padding: '0.05rem 0.35rem', borderRadius: '3px', fontWeight: 600 }}>
              Phase 14 Baseline Commit
            </span>
          ) : (
            <span style={{ fontSize: '0.65rem', backgroundColor: 'rgba(148, 163, 184, 0.15)', color: '#94a3b8', padding: '0.05rem 0.35rem', borderRadius: '3px' }}>
              Selected Commit
            </span>
          )}
        </div>

        <span style={{ color: '#334155' }}>|</span>

        <div style={{ display: 'flex', alignItems: 'center', gap: '0.35rem', color: '#64748b', fontSize: '0.72rem' }}>
          <span>Run:</span>
          <span style={{ color: '#94a3b8', fontFamily: 'monospace' }} title={runId}>{runId}</span>
        </div>
      </div>

      {/* Right items: Score Pill | Scope Badge | Quick Switch */}
      <div style={{ display: 'flex', alignItems: 'center', flexWrap: 'wrap', gap: '0.65rem' }}>
        <div
          style={{
            display: 'inline-flex',
            alignItems: 'center',
            gap: '0.35rem',
            padding: '0.2rem 0.55rem',
            borderRadius: '4px',
            backgroundColor: isFlagged ? 'rgba(245, 158, 11, 0.15)' : 'rgba(52, 211, 153, 0.15)',
            border: `1px solid ${isFlagged ? '#f59e0b' : '#10b981'}`,
            fontSize: '0.75rem',
            color: isFlagged ? '#fbbf24' : '#34d399',
            fontWeight: 600,
          }}
        >
          {isFlagged ? <ShieldAlert size={12} /> : <CheckCircle2 size={12} />}
          <span>{scorePct}%</span>
          <span style={{ color: '#94a3b8', fontWeight: 400 }}>•</span>
          <span>{selectedAnalysis.risk_tier?.split(' ')[0] || 'Tier'}</span>
        </div>

        <DataScopeBadge scope={analysisSource} size="sm" />

        {isSynthetic ? (
          <button
            onClick={() => exitDemoMode()}
            className="btn-secondary"
            style={{
              fontSize: '0.72rem',
              padding: '0.25rem 0.6rem',
              display: 'flex',
              alignItems: 'center',
              gap: '0.3rem',
              color: '#fda4af',
              borderColor: '#f43f5e',
            }}
            title="Restore previously active real Git commit"
          >
            <RotateCcw size={12} /> Exit Demo
          </button>
        ) : (
          <Link
            to="/analyze"
            style={{
              textDecoration: 'none',
              fontSize: '0.72rem',
              color: '#38bdf8',
              display: 'flex',
              alignItems: 'center',
              gap: '0.25rem',
              padding: '0.25rem 0.5rem',
              borderRadius: '4px',
              backgroundColor: 'rgba(56, 189, 248, 0.1)',
            }}
          >
            Switch Commit <ArrowRight size={12} />
          </Link>
        )}
      </div>
    </div>
  );
};

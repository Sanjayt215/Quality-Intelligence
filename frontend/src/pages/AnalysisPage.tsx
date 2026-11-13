// frontend/src/pages/AnalysisPage.tsx - Production-Grade Git & Commit Analysis

import React, { useState, useEffect } from 'react';
import { useAnalysis } from '../context/AnalysisContext';
import { api } from '../api/client';
import { CommitMetricsInput } from '../api/types';
import { RiskBadge } from '../components/RiskBadge';
import { DataScopeBadge } from '../components/DataScopeBadge';
import {
  GitBranch, GitCommit, Sliders, Play, AlertTriangle, Sparkles,
  Layers, FileCode, Check, ThumbsUp, ThumbsDown, ShieldAlert,
  History, RotateCcw, ChevronDown, ChevronRight, ExternalLink,
  ShieldCheck, Info, FileText, Globe, CheckCircle2, ListFilter,
  Search, Download, ArrowUpDown, CheckCircle, XCircle
} from 'lucide-react';
import { Link } from 'react-router-dom';

interface AnalysisPageProps {
  currentPolicy: string;
  currentThreshold: number;
}

const PRESETS: Record<string, { label: string; metrics: CommitMetricsInput; description: string }> = {
  docs: {
    label: 'Routine Doc Update',
    description: 'Single-file typo or documentation fix by experienced contributor.',
    metrics: {
      la: 12, ld: 3, nf: 1, nd: 1, ns: 1, ent: 0.0,
      ndev: 6, age: 15.0, nuc: 10, aexp: 65, arexp: 15, asexp: 40,
    }
  },
  bugfix: {
    label: 'Standard Local Bugfix',
    description: 'Focused fix touching 2 related files in one subsystem.',
    metrics: {
      la: 45, ld: 18, nf: 2, nd: 1, ns: 1, ent: 0.42,
      ndev: 4, age: 30.0, nuc: 8, aexp: 30, arexp: 6, asexp: 18,
    }
  },
  refactor: {
    label: 'Cross-Cutting Architecture Refactor',
    description: 'Massive churn spanning multiple directories and subsystems with high entropy.',
    metrics: {
      la: 1450, ld: 920, nf: 34, nd: 8, ns: 5, ent: 0.94,
      ndev: 2, age: 140.0, nuc: 3, aexp: 12, arexp: 2, asexp: 4,
    }
  },
  junior_core: {
    label: 'New Contributor Core Change',
    description: 'Substantial logic modification by a developer with minimal subsystem history.',
    metrics: {
      la: 380, ld: 65, nf: 8, nd: 3, ns: 2, ent: 0.81,
      ndev: 1, age: 75.0, nuc: 2, aexp: 2, arexp: 1, asexp: 0,
    }
  }
};

export const AnalysisPage: React.FC<AnalysisPageProps> = ({ currentPolicy, currentThreshold }) => {
  const {
    selectedAnalysis,
    analysisSource,
    repositoryPath,
    commitRef,
    connectedRepo,
    branches,
    commits,
    selectedBranch,
    isConnecting,
    isAnalyzing,
    analysisError,
    latestBatchResult,
    connectRepository,
    selectBranch,
    analyzeGitCommit,
    analyzeGitBranch,
    loadSyntheticDemo,
    clearAnalysis,
    restoreLatestRealAnalysis,
  } = useAnalysis();

  // Mode: REAL (default) vs DEMO
  const [activeMode, setActiveMode] = useState<'REAL' | 'DEMO'>(
    analysisSource === 'SYNTHETIC_DEMO' ? 'DEMO' : 'REAL'
  );

  // Form input state
  const [repoInput, setRepoInput] = useState<string>(repositoryPath || (connectedRepo?.repository_path || 'C:\\QI-Pilot\\commons-lang'));
  const [customCommitSha, setCustomCommitSha] = useState<string>(commitRef || 'HEAD');
  const [batchCount, setBatchCount] = useState<number>(10);

  // Batch Result UI State
  const [batchSearch, setBatchSearch] = useState<string>('');
  const [batchTierFilter, setBatchTierFilter] = useState<string>('ALL');
  const [batchSortAsc, setBatchSortAsc] = useState<boolean>(false);

  // Sync state if context changes
  useEffect(() => {
    if (repositoryPath) setRepoInput(repositoryPath);
    if (commitRef) setCustomCommitSha(commitRef);
  }, [repositoryPath, commitRef]);

  // Collapsible sections
  const [showDerivedFeatures, setShowDerivedFeatures] = useState<boolean>(false);
  const [showManifest, setShowManifest] = useState<boolean>(false);
  const [showModifiedFiles, setShowModifiedFiles] = useState<boolean>(false);

  // Reviewer feedback action state
  const [feedbackStatus, setFeedbackStatus] = useState<string | null>(null);
  const [submittingFeedback, setSubmittingFeedback] = useState<boolean>(false);

  const handleConnect = async (e?: React.FormEvent) => {
    if (e) e.preventDefault();
    if (!repoInput.trim()) {
      alert('Please enter a local directory path or public GitHub URL.');
      return;
    }
    try {
      await connectRepository(repoInput.trim());
    } catch {
      // Error in context
    }
  };

  const handleRunCommitAnalysis = async (targetRef?: string) => {
    const refToAnalyze = (targetRef || customCommitSha || 'HEAD').trim();
    const path = repoInput.trim() || repositoryPath;
    if (!path) {
      alert('Please connect a repository first.');
      return;
    }
    try {
      await analyzeGitCommit(path, refToAnalyze, currentPolicy, currentThreshold, selectedBranch);
    } catch {
      // Handled in context
    }
  };

  const handleRunBranchBatch = async () => {
    const path = repoInput.trim() || repositoryPath;
    if (!path) {
      alert('Please connect a repository first.');
      return;
    }
    try {
      await analyzeGitBranch(path, selectedBranch || 'HEAD', batchCount, currentPolicy, currentThreshold);
    } catch {
      // Handled in context
    }
  };

  const handleExportBatchCSV = () => {
    if (!latestBatchResult || !latestBatchResult.commits) return;
    const headers = ['Commit SHA', 'Short SHA', 'Author', 'Timestamp', 'Subject', 'Lines Added', 'Lines Deleted', 'Risk Score', 'Risk Tier', 'Decision', 'Status'];
    const rows = latestBatchResult.commits.map((c) => [
      c.commit_sha || '',
      c.commit_short_sha || '',
      `"${(c.author_name || c.author || '').replace(/"/g, '""')}"`,
      c.commit_timestamp || c.timestamp || '',
      `"${(c.subject || c.commit_subject || '').replace(/"/g, '""')}"`,
      c.lines_added ?? '',
      c.lines_deleted ?? '',
      c.defect_risk_score !== undefined ? c.defect_risk_score : (c.risk_score ?? ''),
      c.risk_tier || '',
      c.review_decision || '',
      (c as any).processing_status || 'SUCCESS',
    ]);
    const csvContent = 'data:text/csv;charset=utf-8,' + [headers.join(','), ...rows.map(r => r.join(','))].join('\n');
    const encodedUri = encodeURI(csvContent);
    const link = document.createElement('a');
    link.setAttribute('href', encodedUri);
    link.setAttribute('download', `qi_batch_${latestBatchResult.branch_name}_${latestBatchResult.batch_run_id.substring(0, 8)}.csv`);
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  };

  const handleSelectBatchCommit = (commit: any) => {
    if (commit.processing_status === 'FAILED') return;
    setCustomCommitSha(commit.commit_sha || commit.commit_id);
    handleRunCommitAnalysis(commit.commit_sha || commit.commit_id);
  };

  const handleRunDemoPreset = async (key: string) => {
    const preset = PRESETS[key];
    if (!preset) return;
    try {
      await loadSyntheticDemo(key, preset.label, preset.metrics, currentPolicy, currentThreshold);
    } catch {
      // Handled in context
    }
  };

  const handleFeedback = async (type: string) => {
    if (!selectedAnalysis) return;
    setSubmittingFeedback(true);
    try {
      await api.submitFeedback({
        commit_sha: selectedAnalysis.commit_sha || selectedAnalysis.commit_id,
        feedback_type: type,
        risk_score: selectedAnalysis.defect_risk_score,
        run_id: selectedAnalysis.run_id,
        notes: `Submitted from UI under ${currentPolicy} (${analysisSource})`,
      });
      setFeedbackStatus(`Feedback saved: ${type}`);
      setTimeout(() => setFeedbackStatus(null), 4000);
    } catch (err: any) {
      alert('Failed to submit feedback: ' + err.message);
    } finally {
      setSubmittingFeedback(false);
    }
  };

  const isFlagged = selectedAnalysis?.flagged_for_review === 'FLAGGED' || selectedAnalysis?.review_decision === 'FLAGGED';
  const isReal = analysisSource === 'REAL_GIT_COMMIT' || analysisSource === 'REAL_GIT_BRANCH';

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
      {/* Top Header & Mode Switcher */}
      <div style={{ backgroundColor: '#131b2e', border: '1px solid #1e293b', borderRadius: '10px', padding: '1.25rem 1.5rem', display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '1rem' }}>
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem' }}>
            <h1 className="qi-title" style={{ margin: 0, fontSize: '1.35rem' }}>Analyze Code-Change Defect Risk</h1>
            <span style={{ fontSize: '0.7rem', color: '#10b981', backgroundColor: 'rgba(16, 185, 129, 0.1)', padding: '0.2rem 0.5rem', borderRadius: '4px', fontWeight: 600 }}>
              ● API CONNECTED
            </span>
          </div>
          <p className="qi-subtitle" style={{ margin: '0.25rem 0 0 0' }}>
            Multi-source code-change risk intelligence: inspect local Git repos, public GitHub repositories, branches, or synthetic archetypes.
          </p>
        </div>

        {/* Real vs Demo Mode Selector */}
        <div style={{ display: 'flex', backgroundColor: '#0f172a', padding: '0.25rem', borderRadius: '8px', border: '1px solid #1e293b' }}>
          <button
            onClick={() => setActiveMode('REAL')}
            style={{
              padding: '0.45rem 0.9rem',
              borderRadius: '6px',
              fontSize: '0.8rem',
              fontWeight: 600,
              border: 'none',
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              gap: '0.4rem',
              backgroundColor: activeMode === 'REAL' ? '#0284c7' : 'transparent',
              color: activeMode === 'REAL' ? '#ffffff' : '#94a3b8',
              transition: 'all 0.15s ease'
            }}
          >
            <GitBranch size={15} /> Real Git / GitHub Analysis
          </button>
          <button
            onClick={() => setActiveMode('DEMO')}
            style={{
              padding: '0.45rem 0.9rem',
              borderRadius: '6px',
              fontSize: '0.8rem',
              fontWeight: 600,
              border: 'none',
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              gap: '0.4rem',
              backgroundColor: activeMode === 'DEMO' ? '#d97706' : 'transparent',
              color: activeMode === 'DEMO' ? '#ffffff' : '#94a3b8',
              transition: 'all 0.15s ease'
            }}
          >
            <Sparkles size={15} /> Demo Simulation Mode
          </button>
        </div>
      </div>

      {/* Error Alert */}
      {analysisError && (
        <div style={{ backgroundColor: 'rgba(239, 68, 68, 0.1)', border: '1px solid #ef4444', borderRadius: '8px', padding: '1rem', color: '#fca5a5', display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
          <AlertTriangle size={18} />
          <div style={{ fontSize: '0.85rem' }}>
            <strong>Analysis Request Failed:</strong> {analysisError}
          </div>
        </div>
      )}

      {/* Loading Progress State */}
      {(isConnecting || isAnalyzing) && (
        <div style={{ backgroundColor: 'rgba(56, 189, 248, 0.1)', border: '1px solid #0284c7', borderRadius: '8px', padding: '0.85rem 1.25rem', color: '#38bdf8', display: 'flex', alignItems: 'center', gap: '0.75rem', fontSize: '0.85rem' }}>
          <div className="animate-spin" style={{ width: '16px', height: '16px', border: '2px solid #38bdf8', borderTopColor: 'transparent', borderRadius: '50%' }} />
          <span>
            {isConnecting ? 'Connecting & inspecting Git repository...' : 'Mining 12 Git metrics & executing 200-tree Random Forest inference...'}
          </span>
        </div>
      )}

      {/* REAL GIT ANALYSIS CONTROLS (Active Mode === 'REAL') */}
      {activeMode === 'REAL' && (
        <div className="card" style={{ padding: '1.25rem', borderLeft: '4px solid #38bdf8' }}>
          {/* Step 1: Repository Connection */}
          <div style={{ marginBottom: '1.25rem', borderBottom: '1px solid #1e293b', paddingBottom: '1rem' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.5rem', flexWrap: 'wrap', gap: '0.5rem' }}>
              <span style={{ fontSize: '0.85rem', fontWeight: 600, color: '#f8fafc', display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
                <Globe size={15} color="#38bdf8" /> 1. Connect Local Repository or Public GitHub URL
              </span>
              <div style={{ display: 'flex', gap: '0.5rem' }}>
                <button
                  type="button"
                  onClick={restoreLatestRealAnalysis}
                  className="btn-secondary"
                  style={{ padding: '0.3rem 0.6rem', fontSize: '0.72rem', display: 'flex', alignItems: 'center', gap: '0.3rem' }}
                  title="Restore latest real analysis"
                >
                  <History size={12} /> Restore Last Run
                </button>
                {selectedAnalysis && (
                  <button
                    type="button"
                    onClick={clearAnalysis}
                    className="btn-secondary"
                    style={{ padding: '0.3rem 0.6rem', fontSize: '0.72rem', display: 'flex', alignItems: 'center', gap: '0.3rem' }}
                  >
                    <RotateCcw size={12} /> Clear
                  </button>
                )}
              </div>
            </div>

            <form onSubmit={handleConnect} style={{ display: 'flex', gap: '0.75rem', alignItems: 'center', flexWrap: 'wrap' }}>
              <input
                type="text"
                className="input-field"
                placeholder="e.g. C:\QI-Pilot\commons-lang or https://github.com/apache/commons-lang"
                value={repoInput}
                onChange={(e) => setRepoInput(e.target.value)}
                style={{ flex: 1, minWidth: '280px' }}
                disabled={isConnecting || isAnalyzing}
              />
              <button
                type="submit"
                className="btn-primary"
                disabled={isConnecting || isAnalyzing}
                style={{ whiteSpace: 'nowrap', padding: '0.5rem 1rem' }}
              >
                {isConnecting ? 'Connecting...' : 'Connect Repository'}
              </button>
            </form>

            {connectedRepo && (
              <div style={{ marginTop: '0.65rem', display: 'flex', alignItems: 'center', gap: '1rem', flexWrap: 'wrap', fontSize: '0.78rem', color: '#94a3b8' }}>
                <span style={{ color: '#34d399', display: 'flex', alignItems: 'center', gap: '0.3rem', fontWeight: 600 }}>
                  <CheckCircle2 size={13} /> {connectedRepo.repository_name}
                </span>
                <span>Path: <code style={{ color: '#cbd5e1' }}>{connectedRepo.repository_path}</code></span>
                {connectedRepo.remote_url && <span>Remote: <code style={{ color: '#38bdf8' }}>{connectedRepo.remote_url}</code></span>}
                <span>Default Branch: <strong>{connectedRepo.default_branch}</strong></span>
              </div>
            )}
          </div>

          {/* Step 2: Branch & Commit Selection */}
          <div>
            <span style={{ fontSize: '0.85rem', fontWeight: 600, color: '#f8fafc', display: 'flex', alignItems: 'center', gap: '0.4rem', marginBottom: '0.75rem' }}>
              <GitBranch size={15} color="#38bdf8" /> 2. Select Branch, Recent Commit, or Enter Exact SHA
            </span>

            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: '0.75rem', marginBottom: '0.85rem' }}>
              {/* Branch Selector */}
              <div>
                <label style={{ fontSize: '0.72rem', color: '#94a3b8', display: 'block', marginBottom: '0.25rem' }}>
                  Branch:
                </label>
                <select
                  className="input-field"
                  value={selectedBranch}
                  onChange={(e) => selectBranch(e.target.value)}
                  disabled={isAnalyzing}
                  style={{ width: '100%' }}
                >
                  {branches.length > 0 ? (
                    branches.map((b) => (
                      <option key={b.git_ref || b.ref || b.name} value={b.branch_name || b.name}>
                        {b.display_name || `${b.name} ${b.is_current ? '(Current)' : ''} ${b.is_remote ? '[remote]' : ''}`}
                      </option>
                    ))
                  ) : (
                    <option value="HEAD">HEAD (Default Branch)</option>
                  )}
                </select>
              </div>

              {/* Recent Commit Picker */}
              <div>
                <label style={{ fontSize: '0.72rem', color: '#94a3b8', display: 'block', marginBottom: '0.25rem' }}>
                  Pick Recent Commit on {selectedBranch}:
                </label>
                <select
                  className="input-field"
                  value={customCommitSha}
                  onChange={(e) => setCustomCommitSha(e.target.value)}
                  disabled={isAnalyzing}
                  style={{ width: '100%' }}
                >
                  <option value="HEAD">HEAD (Branch Tip)</option>
                  {commits.map((c) => (
                    <option key={c.commit_sha} value={c.commit_sha}>
                      [{c.commit_short_sha}] {c.subject.substring(0, 45)}... ({c.author_name})
                    </option>
                  ))}
                </select>
              </div>

              {/* Exact SHA / Ref Input */}
              <div>
                <label style={{ fontSize: '0.72rem', color: '#94a3b8', display: 'block', marginBottom: '0.25rem' }}>
                  Commit SHA / Ref:
                </label>
                <input
                  type="text"
                  className="input-field"
                  placeholder="HEAD or 40-char SHA"
                  value={customCommitSha}
                  onChange={(e) => setCustomCommitSha(e.target.value)}
                  disabled={isAnalyzing}
                  style={{ width: '100%' }}
                />
              </div>
            </div>

            {/* Action Buttons */}
            <div style={{ display: 'flex', gap: '0.75rem', flexWrap: 'wrap', alignItems: 'center' }}>
              <button
                type="button"
                onClick={() => handleRunCommitAnalysis()}
                className="btn-primary"
                disabled={isAnalyzing}
                style={{ padding: '0.55rem 1.25rem', display: 'flex', alignItems: 'center', gap: '0.4rem' }}
              >
                <GitCommit size={15} /> {isAnalyzing ? 'Analyzing Commit...' : 'Analyze Commit'}
              </button>

              <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', backgroundColor: '#0f172a', padding: '0.2rem 0.5rem', borderRadius: '6px', border: '1px solid #1e293b' }}>
                <button
                  type="button"
                  onClick={handleRunBranchBatch}
                  className="btn-secondary"
                  disabled={isAnalyzing}
                  style={{ padding: '0.45rem 1rem', display: 'flex', alignItems: 'center', gap: '0.4rem', border: 'none' }}
                  title="Evaluate recent commits on this branch as a historical sequence"
                >
                  <ListFilter size={15} color="#38bdf8" /> {isAnalyzing ? 'Analyzing Batch...' : `Analyze Branch Batch (${batchCount} commits)`}
                </button>
                <span style={{ color: '#64748b', fontSize: '0.75rem' }}>| Count:</span>
                <input
                  type="number"
                  min={1}
                  max={100}
                  value={batchCount}
                  onChange={(e) => setBatchCount(Math.max(1, Math.min(100, parseInt(e.target.value) || 10)))}
                  disabled={isAnalyzing}
                  style={{
                    width: '52px',
                    backgroundColor: '#1e293b',
                    border: '1px solid #334155',
                    borderRadius: '4px',
                    color: '#f8fafc',
                    padding: '0.25rem 0.4rem',
                    fontSize: '0.8rem',
                    textAlign: 'center'
                  }}
                  title="Batch size: 1 to 100 commits"
                />
              </div>
            </div>
          </div>
        </div>
      )}

      {/* DEMO SIMULATION MODE (Active Mode === 'DEMO') */}
      {activeMode === 'DEMO' && (
        <div className="card" style={{ padding: '1.25rem', borderLeft: '4px solid #f59e0b' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.75rem', flexWrap: 'wrap', gap: '0.5rem' }}>
            <div style={{ fontSize: '0.9rem', fontWeight: 600, color: '#f8fafc', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
              <Sparkles size={16} color="#fbbf24" /> Archetypal Change Scenarios (Synthetic Demo)
            </div>
            <DataScopeBadge scope="SYNTHETIC_DEMONSTRATION" size="sm" />
          </div>

          <p style={{ fontSize: '0.8rem', color: '#94a3b8', marginTop: 0, marginBottom: '0.75rem' }}>
            Test model sensitivity against predefined synthetic code-change archetypes without requiring a local Git clone.
          </p>

          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: '0.75rem' }}>
            {Object.entries(PRESETS).map(([key, p]) => (
              <button
                key={key}
                onClick={() => handleRunDemoPreset(key)}
                disabled={isAnalyzing}
                style={{
                  textAlign: 'left',
                  backgroundColor: selectedAnalysis?.commit_id?.includes(key) && analysisSource === 'SYNTHETIC_DEMO' ? '#1e293b' : '#0f172a',
                  border: `1px solid ${selectedAnalysis?.commit_id?.includes(key) && analysisSource === 'SYNTHETIC_DEMO' ? '#f59e0b' : '#334155'}`,
                  borderRadius: '8px',
                  padding: '0.75rem',
                  cursor: 'pointer',
                  transition: 'all 0.15s ease'
                }}
              >
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <span style={{ fontWeight: 600, color: '#e2e8f0', fontSize: '0.85rem' }}>{p.label}</span>
                  <span style={{ fontSize: '0.65rem', color: '#fbbf24', background: 'rgba(245, 158, 11, 0.2)', padding: '0.1rem 0.35rem', borderRadius: '3px', fontWeight: 600 }}>DEMO</span>
                </div>
                <div style={{ fontSize: '0.75rem', color: '#94a3b8', marginTop: '0.25rem' }}>{p.description}</div>
              </button>
            ))}
          </div>
        </div>
      )}

      {/* BRANCH BATCH RESULTS CARD */}
      {latestBatchResult && latestBatchResult.commits && latestBatchResult.commits.length > 0 && (
        <div className="card" style={{ padding: '1.25rem', borderLeft: '4px solid #38bdf8' }}>
          {/* Header */}
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem', flexWrap: 'wrap', gap: '0.75rem', borderBottom: '1px solid #1e293b', paddingBottom: '0.75rem' }}>
            <div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                <ListFilter size={18} color="#38bdf8" />
                <h3 style={{ margin: 0, fontSize: '1.1rem', color: '#f8fafc' }}>
                  Branch Batch Evaluation: <span style={{ color: '#38bdf8' }}>{latestBatchResult.branch_name}</span>
                </h3>
              </div>
              <div style={{ fontSize: '0.75rem', color: '#94a3b8', marginTop: '0.25rem' }}>
                Run ID: <code style={{ color: '#e2e8f0' }}>{latestBatchResult.batch_run_id}</code> • Ref: <code style={{ color: '#e2e8f0' }}>{latestBatchResult.resolved_git_ref || latestBatchResult.branch_name}</code>
              </div>
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
              <span style={{
                fontSize: '0.72rem',
                fontWeight: 600,
                padding: '0.2rem 0.5rem',
                borderRadius: '4px',
                backgroundColor: latestBatchResult.overall_status === 'COMPLETED' ? 'rgba(16, 185, 129, 0.15)' : 'rgba(245, 158, 11, 0.15)',
                color: latestBatchResult.overall_status === 'COMPLETED' ? '#34d399' : '#fbbf24',
                border: `1px solid ${latestBatchResult.overall_status === 'COMPLETED' ? '#10b981' : '#f59e0b'}`
              }}>
                {latestBatchResult.overall_status || 'COMPLETED'}
              </span>
              <button
                type="button"
                onClick={handleExportBatchCSV}
                className="btn-secondary"
                style={{ padding: '0.35rem 0.75rem', fontSize: '0.75rem', display: 'flex', alignItems: 'center', gap: '0.35rem' }}
                title="Export this batch result as CSV"
              >
                <Download size={13} /> Export CSV
              </button>
            </div>
          </div>

          {/* KPI Summary row */}
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(130px, 1fr))', gap: '0.75rem', marginBottom: '1rem' }}>
            <div style={{ backgroundColor: '#0f172a', padding: '0.75rem', borderRadius: '6px', border: '1px solid #1e293b' }}>
              <div style={{ fontSize: '0.7rem', color: '#94a3b8' }}>Total Processed</div>
              <div style={{ fontSize: '1.2rem', fontWeight: 700, color: '#f8fafc' }}>{latestBatchResult.total_commits_analyzed}</div>
            </div>
            <div style={{ backgroundColor: '#0f172a', padding: '0.75rem', borderRadius: '6px', border: '1px solid #1e293b' }}>
              <div style={{ fontSize: '0.7rem', color: '#94a3b8' }}>Successful</div>
              <div style={{ fontSize: '1.2rem', fontWeight: 700, color: '#34d399' }}>{latestBatchResult.successful_commit_count ?? latestBatchResult.total_commits_analyzed}</div>
            </div>
            <div style={{ backgroundColor: '#0f172a', padding: '0.75rem', borderRadius: '6px', border: '1px solid #1e293b' }}>
              <div style={{ fontSize: '0.7rem', color: '#94a3b8' }}>Failed / Skipped</div>
              <div style={{ fontSize: '1.2rem', fontWeight: 700, color: (latestBatchResult.failed_commit_count ?? 0) > 0 ? '#ef4444' : '#64748b' }}>
                {(latestBatchResult.failed_commit_count ?? 0) + (latestBatchResult.skipped_commit_count ?? 0)}
              </div>
            </div>
            <div style={{ backgroundColor: '#0f172a', padding: '0.75rem', borderRadius: '6px', border: '1px solid #1e293b' }}>
              <div style={{ fontSize: '0.7rem', color: '#94a3b8' }}>Flagged for Review</div>
              <div style={{ fontSize: '1.2rem', fontWeight: 700, color: latestBatchResult.flagged_count > 0 ? '#f87171' : '#38bdf8' }}>
                {latestBatchResult.flagged_count}
              </div>
            </div>
            <div style={{ backgroundColor: '#0f172a', padding: '0.75rem', borderRadius: '6px', border: '1px solid #1e293b' }}>
              <div style={{ fontSize: '0.7rem', color: '#94a3b8' }}>Mean Risk Score</div>
              <div style={{ fontSize: '1.2rem', fontWeight: 700, color: '#38bdf8' }}>
                {(latestBatchResult.mean_risk_score * 100).toFixed(1)}%
              </div>
            </div>
          </div>

          {/* Filter & Search Bar */}
          <div style={{ display: 'flex', gap: '0.75rem', alignItems: 'center', marginBottom: '0.75rem', flexWrap: 'wrap' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.35rem', backgroundColor: '#0f172a', padding: '0.3rem 0.6rem', borderRadius: '6px', border: '1px solid #1e293b', flex: '1 1 200px' }}>
              <Search size={14} color="#64748b" />
              <input
                type="text"
                placeholder="Search by commit SHA or subject..."
                value={batchSearch}
                onChange={(e) => setBatchSearch(e.target.value)}
                style={{ backgroundColor: 'transparent', border: 'none', color: '#f8fafc', fontSize: '0.8rem', outline: 'none', width: '100%' }}
              />
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
              <label style={{ fontSize: '0.75rem', color: '#94a3b8' }}>Risk Tier:</label>
              <select
                className="input-field"
                value={batchTierFilter}
                onChange={(e) => setBatchTierFilter(e.target.value)}
                style={{ padding: '0.3rem 0.6rem', fontSize: '0.8rem' }}
              >
                <option value="ALL">All Tiers</option>
                <option value="Critical Risk">Critical Risk</option>
                <option value="Elevated Risk">Elevated Risk</option>
                <option value="Moderate Risk">Moderate Risk</option>
                <option value="Low Risk">Low Risk</option>
              </select>
            </div>
            <button
              type="button"
              onClick={() => setBatchSortAsc(!batchSortAsc)}
              className="btn-secondary"
              style={{ padding: '0.3rem 0.6rem', fontSize: '0.75rem', display: 'flex', alignItems: 'center', gap: '0.3rem' }}
              title="Toggle sort order by risk score"
            >
              <ArrowUpDown size={13} /> Sort Score ({batchSortAsc ? 'Asc' : 'Desc'})
            </button>
          </div>

          {/* Batch Commits Table */}
          <div style={{ overflowX: 'auto' }}>
            <table className="qi-table" style={{ width: '100%', fontSize: '0.8rem' }}>
              <thead>
                <tr>
                  <th>Commit</th>
                  <th>Author</th>
                  <th>Subject</th>
                  <th>Risk Score</th>
                  <th>Tier</th>
                  <th>Decision</th>
                  <th>Status</th>
                  <th>Action</th>
                </tr>
              </thead>
              <tbody>
                {latestBatchResult.commits
                  .filter((c) => {
                    if (batchTierFilter !== 'ALL' && c.risk_tier !== batchTierFilter) return false;
                    if (batchSearch.trim()) {
                      const q = batchSearch.toLowerCase();
                      const matchSha = (c.commit_sha || '').toLowerCase().includes(q) || (c.commit_short_sha || '').toLowerCase().includes(q);
                      const matchSub = (c.subject || c.commit_subject || '').toLowerCase().includes(q);
                      const matchAuth = (c.author_name || c.author || '').toLowerCase().includes(q);
                      return matchSha || matchSub || matchAuth;
                    }
                    return true;
                  })
                  .sort((a, b) => {
                    const scoreA = a.defect_risk_score !== undefined ? a.defect_risk_score : (a.risk_score || 0);
                    const scoreB = b.defect_risk_score !== undefined ? b.defect_risk_score : (b.risk_score || 0);
                    return batchSortAsc ? scoreA - scoreB : scoreB - scoreA;
                  })
                  .map((c) => {
                    const score = c.defect_risk_score !== undefined ? c.defect_risk_score : (c.risk_score || 0);
                    const isPassed = (c as any).processing_status !== 'FAILED';
                    const isSelected = selectedAnalysis?.commit_sha === c.commit_sha;

                    return (
                      <tr
                        key={c.commit_sha || c.commit_id}
                        style={{
                          backgroundColor: isSelected ? 'rgba(56, 189, 248, 0.08)' : undefined,
                          cursor: isPassed ? 'pointer' : 'default'
                        }}
                        onClick={() => isPassed && handleSelectBatchCommit(c)}
                      >
                        <td>
                          <code style={{ color: isSelected ? '#38bdf8' : '#e2e8f0', fontWeight: 600 }}>
                            {c.commit_short_sha || (c.commit_sha ? c.commit_sha.substring(0, 8) : 'unknown')}
                          </code>
                        </td>
                        <td style={{ color: '#cbd5e1', maxWidth: '140px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                          {c.author_name || c.author || 'Unknown'}
                        </td>
                        <td style={{ color: '#94a3b8', maxWidth: '280px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                          {c.subject || c.commit_subject || 'No subject'}
                        </td>
                        <td>
                          {isPassed ? (
                            <span style={{ fontWeight: 600, color: (score ?? 0) >= currentThreshold ? '#f87171' : '#34d399' }}>
                              {((score ?? 0) * 100).toFixed(1)}%
                            </span>
                          ) : (
                            <span style={{ color: '#64748b' }}>N/A</span>
                          )}
                        </td>
                        <td>
                          {isPassed && c.risk_tier ? (
                            <RiskBadge tier={c.risk_tier as any} />
                          ) : (
                            <span style={{ color: '#ef4444', fontSize: '0.7rem' }}>Failed</span>
                          )}
                        </td>
                        <td>
                          {isPassed ? (
                            <span style={{
                              fontSize: '0.7rem',
                              fontWeight: 600,
                              color: c.review_decision === 'FLAGGED' ? '#ef4444' : '#10b981'
                            }}>
                              {c.review_decision || 'STANDARD'}
                            </span>
                          ) : (
                            <span style={{ color: '#64748b', fontSize: '0.7rem' }}>SKIPPED</span>
                          )}
                        </td>
                        <td>
                          {isPassed ? (
                            <span style={{ display: 'inline-flex', alignItems: 'center', gap: '0.25rem', color: '#34d399', fontSize: '0.72rem' }}>
                              <CheckCircle size={12} /> SUCCESS
                            </span>
                          ) : (
                            <span style={{ display: 'inline-flex', alignItems: 'center', gap: '0.25rem', color: '#ef4444', fontSize: '0.72rem' }} title={(c as any).error_message || 'Processing failed'}>
                              <XCircle size={12} /> FAILED
                            </span>
                          )}
                        </td>
                        <td>
                          {isPassed && (
                            <button
                              type="button"
                              onClick={(e) => {
                                e.stopPropagation();
                                handleSelectBatchCommit(c);
                              }}
                              className="btn-secondary"
                              style={{ padding: '0.2rem 0.5rem', fontSize: '0.7rem' }}
                            >
                              Inspect
                            </button>
                          )}
                        </td>
                      </tr>
                    );
                  })}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* ANALYSIS RESULTS VIEW */}
      {selectedAnalysis ? (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
          {/* Main Decision & Score Banner */}
          <div
            className="card"
            style={{
              padding: '1.5rem',
              borderLeft: `5px solid ${isFlagged ? '#ef4444' : '#10b981'}`,
              backgroundColor: isFlagged ? 'rgba(239, 68, 68, 0.04)' : 'rgba(16, 185, 129, 0.04)'
            }}
          >
            {/* Top row: Context & Source Badge */}
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '1rem', flexWrap: 'wrap', gap: '0.75rem' }}>
              <div>
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem', marginBottom: '0.25rem' }}>
                  <DataScopeBadge scope={analysisSource} size="sm" />
                  <span style={{ fontSize: '0.8rem', color: '#94a3b8' }}>
                    Repository: <strong style={{ color: '#f8fafc' }}>{selectedAnalysis.repository_name || selectedAnalysis.project}</strong>
                  </span>
                  {selectedAnalysis.branch_name && (
                    <span style={{ fontSize: '0.8rem', color: '#94a3b8' }}>
                      • Branch: <strong style={{ color: '#38bdf8' }}>{selectedAnalysis.branch_name}</strong>
                    </span>
                  )}
                </div>

                <div style={{ fontSize: '1.1rem', fontWeight: 700, color: '#f8fafc', display: 'flex', alignItems: 'center', gap: '0.5rem', flexWrap: 'wrap' }}>
                  <span>Commit:</span>
                  <span style={{ fontFamily: 'monospace', color: '#38bdf8', fontSize: '0.95rem' }}>
                    {selectedAnalysis.commit_sha || selectedAnalysis.commit_id}
                  </span>
                  {selectedAnalysis.is_merge_commit && (
                    <span style={{ fontSize: '0.65rem', backgroundColor: '#334155', color: '#94a3b8', padding: '0.1rem 0.4rem', borderRadius: '3px' }}>MERGE COMMIT</span>
                  )}
                  {selectedAnalysis.is_root_commit && (
                    <span style={{ fontSize: '0.65rem', backgroundColor: '#334155', color: '#94a3b8', padding: '0.1rem 0.4rem', borderRadius: '3px' }}>ROOT COMMIT</span>
                  )}
                </div>

                {(selectedAnalysis.commit_subject || selectedAnalysis.subject) && (
                  <div style={{ fontSize: '0.85rem', color: '#cbd5e1', marginTop: '0.35rem', fontStyle: 'italic' }}>
                    "{selectedAnalysis.commit_subject || selectedAnalysis.subject}"
                  </div>
                )}
                {(selectedAnalysis.commit_author || selectedAnalysis.author) && (
                  <div style={{ fontSize: '0.75rem', color: '#64748b', marginTop: '0.2rem' }}>
                    Author: {selectedAnalysis.commit_author || selectedAnalysis.author}
                    {selectedAnalysis.commit_timestamp && ` • ${new Date(selectedAnalysis.commit_timestamp).toLocaleString()}`}
                  </div>
                )}
              </div>

              <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-end', gap: '0.4rem' }}>
                <RiskBadge tier={selectedAnalysis.risk_tier} />
                <span style={{ fontSize: '0.75rem', color: '#94a3b8' }}>
                  Policy: {currentPolicy.split(' ')[0]} (Threshold {currentThreshold.toFixed(2)})
                </span>
              </div>
            </div>

            {/* Middle row: Key Metric Boxes */}
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '1rem', marginBottom: '1.25rem' }}>
              <div style={{ backgroundColor: '#0f172a', padding: '1rem', borderRadius: '8px', border: '1px solid #1e293b' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <div style={{ fontSize: '0.72rem', color: '#94a3b8' }}>DEFECT RISK SCORE</div>
                  <DataScopeBadge scope="MODEL_PREDICTION" size="sm" />
                </div>
                <div style={{ fontSize: '2.2rem', fontWeight: 800, color: isFlagged ? '#ef4444' : '#10b981', lineHeight: 1.1, marginTop: '0.25rem' }}>
                  {((selectedAnalysis.defect_risk_score || 0) * 100).toFixed(1)}%
                </div>
                <div style={{ fontSize: '0.7rem', color: '#64748b', marginTop: '0.35rem' }}>
                  Threshold: {currentThreshold.toFixed(2)} • Random Forest 200-tree
                </div>
              </div>

              <div style={{ backgroundColor: '#0f172a', padding: '1rem', borderRadius: '8px', border: '1px solid #1e293b' }}>
                <div style={{ fontSize: '0.72rem', color: '#94a3b8' }}>REVIEW DECISION</div>
                <div style={{ fontSize: '1.4rem', fontWeight: 700, color: isFlagged ? '#ef4444' : '#10b981', marginTop: '0.35rem' }}>
                  {isFlagged ? 'FLAGGED FOR REVIEW' : 'STANDARD WORKFLOW'}
                </div>
                <div style={{ fontSize: '0.7rem', color: '#94a3b8', marginTop: '0.35rem' }}>
                  {isFlagged ? 'Exceeds operational defect threshold' : 'Within acceptable risk bounds'}
                </div>
              </div>

              <div style={{ backgroundColor: '#0f172a', padding: '1rem', borderRadius: '8px', border: '1px solid #1e293b' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <div style={{ fontSize: '0.72rem', color: '#94a3b8' }}>UNCERTAINTY & EVIDENCE</div>
                  <DataScopeBadge scope="REAL_GIT_DATA" size="sm" />
                </div>
                <div style={{ fontSize: '1.2rem', fontWeight: 700, color: selectedAnalysis.uncertainty?.evidence_status === 'HIGH_CONFIDENCE' ? '#10b981' : '#f59e0b', marginTop: '0.35rem' }}>
                  {selectedAnalysis.uncertainty?.evidence_status || 'STANDARD'}
                </div>
                <div style={{ fontSize: '0.7rem', color: '#94a3b8', marginTop: '0.35rem' }}>
                  {selectedAnalysis.uncertainty?.out_of_distribution_flags?.length ? `${selectedAnalysis.uncertainty.out_of_distribution_flags.length} OOD warning(s)` : 'In-distribution commit'}
                </div>
              </div>
            </div>

            {/* Recommendation callout */}
            <div style={{ backgroundColor: '#0f172a', border: '1px solid #1e293b', borderRadius: '6px', padding: '0.85rem 1rem', fontSize: '0.85rem', color: '#cbd5e1' }}>
              <strong style={{ color: '#f8fafc' }}>Actionable Recommendation:</strong> {selectedAnalysis.recommendation}
            </div>

            {/* Inline Reviewer Feedback Buttons */}
            <div style={{ marginTop: '1rem', paddingTop: '1rem', borderTop: '1px solid #1e293b', display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '0.75rem' }}>
              <span style={{ fontSize: '0.78rem', color: '#94a3b8' }}>
                Reviewer Outcome Feedback (Continuous Learning):
              </span>
              <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap' }}>
                <button
                  type="button"
                  onClick={() => handleFeedback('HELPFUL_FLAG')}
                  disabled={submittingFeedback}
                  className="btn-secondary"
                  style={{ fontSize: '0.75rem', padding: '0.35rem 0.65rem', display: 'flex', alignItems: 'center', gap: '0.3rem', color: '#38bdf8' }}
                >
                  <ThumbsUp size={13} /> Helpful Flag
                </button>
                <button
                  type="button"
                  onClick={() => handleFeedback('FALSE_ALARM')}
                  disabled={submittingFeedback}
                  className="btn-secondary"
                  style={{ fontSize: '0.75rem', padding: '0.35rem 0.65rem', display: 'flex', alignItems: 'center', gap: '0.3rem', color: '#f59e0b' }}
                >
                  <ThumbsDown size={13} /> False Alarm
                </button>
                <button
                  type="button"
                  onClick={() => handleFeedback('CONFIRMED_DEFECT')}
                  disabled={submittingFeedback}
                  className="btn-secondary"
                  style={{ fontSize: '0.75rem', padding: '0.35rem 0.65rem', display: 'flex', alignItems: 'center', gap: '0.3rem', color: '#ef4444' }}
                >
                  <ShieldAlert size={13} /> Confirmed Defect
                </button>
                <button
                  type="button"
                  onClick={() => handleFeedback('BENIGN_PASS')}
                  disabled={submittingFeedback}
                  className="btn-secondary"
                  style={{ fontSize: '0.75rem', padding: '0.35rem 0.65rem', display: 'flex', alignItems: 'center', gap: '0.3rem', color: '#10b981' }}
                >
                  <Check size={13} /> Benign Pass
                </button>
              </div>
            </div>

            {feedbackStatus && (
              <div style={{ marginTop: '0.5rem', fontSize: '0.75rem', color: '#34d399', fontWeight: 600 }}>
                ✓ {feedbackStatus}
              </div>
            )}
          </div>

          {/* 12 Measured Raw Metrics Grid */}
          <div className="card" style={{ padding: '1.25rem' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem', borderBottom: '1px solid #1e293b', paddingBottom: '0.5rem' }}>
              <div style={{ fontSize: '0.9rem', fontWeight: 600, color: '#f8fafc', display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
                <FileCode size={16} color="#38bdf8" /> 12 Mined Software Change Dimensions
              </div>
              <DataScopeBadge scope="REAL_GIT_DATA" size="sm" />
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(170px, 1fr))', gap: '0.75rem' }}>
              <div style={{ backgroundColor: '#0f172a', padding: '0.75rem', borderRadius: '6px', border: '1px solid #1e293b' }}>
                <div style={{ fontSize: '0.7rem', color: '#94a3b8' }}>LINES ADDED (`la`)</div>
                <div style={{ fontSize: '1.25rem', fontWeight: 700, color: '#f8fafc', marginTop: '0.2rem' }}>
                  {(selectedAnalysis.lines_added ?? selectedAnalysis.raw_metrics?.la ?? 0).toLocaleString()}
                </div>
              </div>
              <div style={{ backgroundColor: '#0f172a', padding: '0.75rem', borderRadius: '6px', border: '1px solid #1e293b' }}>
                <div style={{ fontSize: '0.7rem', color: '#94a3b8' }}>LINES DELETED (`ld`)</div>
                <div style={{ fontSize: '1.25rem', fontWeight: 700, color: '#f8fafc', marginTop: '0.2rem' }}>
                  {(selectedAnalysis.lines_deleted ?? selectedAnalysis.raw_metrics?.ld ?? 0).toLocaleString()}
                </div>
              </div>
              <div style={{ backgroundColor: '#0f172a', padding: '0.75rem', borderRadius: '6px', border: '1px solid #1e293b' }}>
                <div style={{ fontSize: '0.7rem', color: '#94a3b8' }}>MODIFIED FILES (`nf`)</div>
                <div style={{ fontSize: '1.25rem', fontWeight: 700, color: '#f8fafc', marginTop: '0.2rem' }}>
                  {selectedAnalysis.modified_files ?? selectedAnalysis.raw_metrics?.nf ?? 1}
                </div>
              </div>
              <div style={{ backgroundColor: '#0f172a', padding: '0.75rem', borderRadius: '6px', border: '1px solid #1e293b' }}>
                <div style={{ fontSize: '0.7rem', color: '#94a3b8' }}>DIRECTORIES (`nd`)</div>
                <div style={{ fontSize: '1.25rem', fontWeight: 700, color: '#f8fafc', marginTop: '0.2rem' }}>
                  {selectedAnalysis.modified_directories ?? selectedAnalysis.raw_metrics?.nd ?? 1}
                </div>
              </div>
              <div style={{ backgroundColor: '#0f172a', padding: '0.75rem', borderRadius: '6px', border: '1px solid #1e293b' }}>
                <div style={{ fontSize: '0.7rem', color: '#94a3b8' }}>SUBSYSTEMS (`ns`)</div>
                <div style={{ fontSize: '1.25rem', fontWeight: 700, color: '#f8fafc', marginTop: '0.2rem' }}>
                  {selectedAnalysis.modified_subsystems ?? selectedAnalysis.raw_metrics?.ns ?? 1}
                </div>
              </div>
              <div style={{ backgroundColor: '#0f172a', padding: '0.75rem', borderRadius: '6px', border: '1px solid #1e293b' }}>
                <div style={{ fontSize: '0.7rem', color: '#94a3b8' }}>CHANGE ENTROPY (`ent`)</div>
                <div style={{ fontSize: '1.25rem', fontWeight: 700, color: '#f8fafc', marginTop: '0.2rem' }}>
                  {(selectedAnalysis.entropy ?? selectedAnalysis.raw_metrics?.ent ?? 0.0).toFixed(2)}
                </div>
              </div>
              <div style={{ backgroundColor: '#0f172a', padding: '0.75rem', borderRadius: '6px', border: '1px solid #1e293b' }}>
                <div style={{ fontSize: '0.7rem', color: '#94a3b8' }}>PAST DEVS (`ndev`)</div>
                <div style={{ fontSize: '1.25rem', fontWeight: 700, color: '#f8fafc', marginTop: '0.2rem' }}>
                  {selectedAnalysis.raw_metrics?.ndev ?? 0}
                </div>
              </div>
              <div style={{ backgroundColor: '#0f172a', padding: '0.75rem', borderRadius: '6px', border: '1px solid #1e293b' }}>
                <div style={{ fontSize: '0.7rem', color: '#94a3b8' }}>FILE AGE DAYS (`age`)</div>
                <div style={{ fontSize: '1.25rem', fontWeight: 700, color: '#f8fafc', marginTop: '0.2rem' }}>
                  {(selectedAnalysis.file_age_days ?? selectedAnalysis.raw_metrics?.age ?? 0.0).toFixed(1)}d
                </div>
              </div>
              <div style={{ backgroundColor: '#0f172a', padding: '0.75rem', borderRadius: '6px', border: '1px solid #1e293b' }}>
                <div style={{ fontSize: '0.7rem', color: '#94a3b8' }}>PRIOR CHANGES (`nuc`)</div>
                <div style={{ fontSize: '1.25rem', fontWeight: 700, color: '#f8fafc', marginTop: '0.2rem' }}>
                  {selectedAnalysis.raw_metrics?.nuc ?? 0}
                </div>
              </div>
              <div style={{ backgroundColor: '#0f172a', padding: '0.75rem', borderRadius: '6px', border: '1px solid #1e293b' }}>
                <div style={{ fontSize: '0.7rem', color: '#94a3b8' }}>AUTHOR TOTAL EXP (`aexp`)</div>
                <div style={{ fontSize: '1.25rem', fontWeight: 700, color: '#f8fafc', marginTop: '0.2rem' }}>
                  {selectedAnalysis.raw_metrics?.aexp ?? 0}
                </div>
              </div>
              <div style={{ backgroundColor: '#0f172a', padding: '0.75rem', borderRadius: '6px', border: '1px solid #1e293b' }}>
                <div style={{ fontSize: '0.7rem', color: '#94a3b8' }}>AUTHOR RECENT EXP (`arexp`)</div>
                <div style={{ fontSize: '1.25rem', fontWeight: 700, color: '#f8fafc', marginTop: '0.2rem' }}>
                  {selectedAnalysis.raw_metrics?.arexp ?? 0}
                </div>
              </div>
              <div style={{ backgroundColor: '#0f172a', padding: '0.75rem', borderRadius: '6px', border: '1px solid #1e293b' }}>
                <div style={{ fontSize: '0.7rem', color: '#94a3b8' }}>SUBSYSTEM EXP (`asexp`)</div>
                <div style={{ fontSize: '1.25rem', fontWeight: 700, color: '#f8fafc', marginTop: '0.2rem' }}>
                  {selectedAnalysis.subsystem_exp ?? selectedAnalysis.raw_metrics?.asexp ?? 0}
                </div>
              </div>
            </div>
          </div>

          {/* Epistemic Uncertainty & OOD Section */}
          {selectedAnalysis.uncertainty && (
            <div className="card" style={{ padding: '1.25rem' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.75rem' }}>
                <span style={{ fontSize: '0.9rem', fontWeight: 600, color: '#f8fafc', display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
                  <ShieldAlert size={16} color="#38bdf8" /> Epistemic Uncertainty Assessment
                </span>
                <span style={{ fontSize: '0.72rem', color: selectedAnalysis.uncertainty.evidence_status === 'HIGH_CONFIDENCE' ? '#34d399' : '#fbbf24', fontWeight: 600 }}>
                  {selectedAnalysis.uncertainty.evidence_status}
                </span>
              </div>
              <p style={{ fontSize: '0.8rem', color: '#94a3b8', margin: '0 0 0.5rem 0' }}>
                {selectedAnalysis.uncertainty.recommended_action}
              </p>
              {selectedAnalysis.uncertainty.out_of_distribution_flags && selectedAnalysis.uncertainty.out_of_distribution_flags.length > 0 && (
                <div style={{ display: 'flex', gap: '0.4rem', flexWrap: 'wrap', marginTop: '0.5rem' }}>
                  {selectedAnalysis.uncertainty.out_of_distribution_flags.map((flag: string, idx: number) => (
                    <span key={idx} style={{ fontSize: '0.72rem', backgroundColor: 'rgba(239, 68, 68, 0.15)', color: '#fca5a5', padding: '0.2rem 0.5rem', borderRadius: '4px', border: '1px solid #ef4444' }}>
                      ⚠️ {flag}
                    </span>
                  ))}
                </div>
              )}
            </div>
          )}

          {/* Collapsible: Modified Files List */}
          {selectedAnalysis.modified_files_list && selectedAnalysis.modified_files_list.length > 0 && (
            <div className="card" style={{ padding: '1rem' }}>
              <button
                type="button"
                onClick={() => setShowModifiedFiles(!showModifiedFiles)}
                style={{ width: '100%', background: 'transparent', border: 'none', color: '#f8fafc', display: 'flex', justifyContent: 'space-between', alignItems: 'center', cursor: 'pointer', padding: 0 }}
              >
                <span style={{ fontSize: '0.85rem', fontWeight: 600, display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
                  <FileText size={15} color="#38bdf8" /> Modified Files ({selectedAnalysis.modified_files_list.length})
                </span>
                {showModifiedFiles ? <ChevronDown size={16} /> : <ChevronRight size={16} />}
              </button>

              {showModifiedFiles && (
                <div style={{ marginTop: '0.75rem', maxHeight: '200px', overflowY: 'auto' }}>
                  <ul style={{ margin: 0, paddingLeft: '1.25rem', fontSize: '0.8rem', color: '#cbd5e1', lineHeight: 1.6 }}>
                    {selectedAnalysis.modified_files_list.map((f, i) => (
                      <li key={i}><code style={{ color: '#38bdf8' }}>{f}</code></li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
          )}

          {/* Collapsible: 26 Derived Engineered Features */}
          {selectedAnalysis.derived_features && (
            <div className="card" style={{ padding: '1rem' }}>
              <button
                type="button"
                onClick={() => setShowDerivedFeatures(!showDerivedFeatures)}
                style={{ width: '100%', background: 'transparent', border: 'none', color: '#f8fafc', display: 'flex', justifyContent: 'space-between', alignItems: 'center', cursor: 'pointer', padding: 0 }}
              >
                <span style={{ fontSize: '0.85rem', fontWeight: 600, display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
                  <Layers size={15} color="#38bdf8" /> 26 Engineered Feature Vector (Random Forest Input)
                </span>
                {showDerivedFeatures ? <ChevronDown size={16} /> : <ChevronRight size={16} />}
              </button>

              {showDerivedFeatures && (
                <div style={{ marginTop: '0.75rem', display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '0.5rem', maxHeight: '280px', overflowY: 'auto' }}>
                  {Object.entries(selectedAnalysis.derived_features).map(([name, val]) => (
                    <div key={name} style={{ backgroundColor: '#0f172a', padding: '0.5rem 0.75rem', borderRadius: '4px', border: '1px solid #1e293b', display: 'flex', justifyContent: 'space-between', fontSize: '0.75rem' }}>
                      <span style={{ color: '#94a3b8', fontFamily: 'monospace' }}>{name}</span>
                      <span style={{ color: '#f8fafc', fontWeight: 600 }}>{typeof val === 'number' ? val.toFixed(4) : val}</span>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}

          {/* Collapsible: Manifest Verification */}
          {selectedAnalysis.manifest && (
            <div className="card" style={{ padding: '1rem' }}>
              <button
                type="button"
                onClick={() => setShowManifest(!showManifest)}
                style={{ width: '100%', background: 'transparent', border: 'none', color: '#f8fafc', display: 'flex', justifyContent: 'space-between', alignItems: 'center', cursor: 'pointer', padding: 0 }}
              >
                <span style={{ fontSize: '0.85rem', fontWeight: 600, display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
                  <ShieldCheck size={15} color="#34d399" /> Cryptographic Run Manifest & Provenance
                </span>
                {showManifest ? <ChevronDown size={16} /> : <ChevronRight size={16} />}
              </button>

              {showManifest && (
                <div style={{ marginTop: '0.75rem', backgroundColor: '#0f172a', padding: '0.75rem', borderRadius: '6px', fontSize: '0.75rem', fontFamily: 'monospace', color: '#cbd5e1', overflowX: 'auto' }}>
                  <pre style={{ margin: 0 }}>{JSON.stringify(selectedAnalysis.manifest, null, 2)}</pre>
                </div>
              )}
            </div>
          )}
        </div>
      ) : (
        <div className="card" style={{ padding: '2.5rem', textAlign: 'center', color: '#94a3b8' }}>
          <GitBranch size={40} color="#334155" style={{ margin: '0 auto 1rem auto' }} />
          <div style={{ fontSize: '1rem', fontWeight: 600, color: '#f8fafc' }}>
            No Active Commit Analysis
          </div>
          <p style={{ fontSize: '0.85rem', maxWidth: '480px', margin: '0.5rem auto 1.5rem auto' }}>
            Connect to a local Git directory (e.g. <code>C:\QI-Pilot\commons-lang</code>) or public GitHub repository above and click <strong>Analyze Commit</strong> to evaluate code change defect risk.
          </p>
        </div>
      )}
    </div>
  );
};

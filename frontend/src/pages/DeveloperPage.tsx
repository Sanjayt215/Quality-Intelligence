// frontend/src/pages/DeveloperPage.tsx - Real Commit Advisory & CI/CD Gate

import React, { useState, useEffect } from 'react';
import { api } from '../api/client';
import { useAnalysis } from '../context/AnalysisContext';
import { PRPreviewResponse } from '../api/types';
import { DataScopeBadge } from '../components/DataScopeBadge';
import {
  GitPullRequest, Play, AlertTriangle, Shield,
  Eye, Copy, Check, Info, GitBranch, GitCommit
} from 'lucide-react';

interface DeveloperPageProps {
  currentPolicy: string;
  currentThreshold: number;
}

export const DeveloperPage: React.FC<DeveloperPageProps> = ({ currentPolicy, currentThreshold }) => {
  const { selectedAnalysis, analysisSource } = useAnalysis();

  const [hasPr, setHasPr] = useState<boolean>(Boolean(selectedAnalysis?.pr_number));
  const [prNumber, setPrNumber] = useState<number>(selectedAnalysis?.pr_number || 0);
  const [project, setProject] = useState<string>(selectedAnalysis?.repository_name || selectedAnalysis?.project || 'commons-lang');
  const [commitId, setCommitId] = useState<string>(selectedAnalysis?.commit_sha || selectedAnalysis?.commit_id || '');
  const [dryRun, setDryRun] = useState<boolean>(true);

  // Sync state whenever selectedAnalysis changes
  useEffect(() => {
    if (selectedAnalysis) {
      setProject(selectedAnalysis.repository_name || selectedAnalysis.project);
      setCommitId(selectedAnalysis.commit_sha || selectedAnalysis.commit_id);
      if (selectedAnalysis.pr_number) {
        setHasPr(true);
        setPrNumber(selectedAnalysis.pr_number);
      } else {
        setHasPr(false);
        setPrNumber(0);
      }
    }
  }, [selectedAnalysis]);

  const [loading, setLoading] = useState<boolean>(false);
  const [result, setResult] = useState<PRPreviewResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [copied, setCopied] = useState<boolean>(false);

  const handleGeneratePreview = async () => {
    if (!selectedAnalysis) {
      setError('No active commit selected. Please analyze a real Git commit first.');
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const raw = selectedAnalysis.raw_metrics || {
        la: selectedAnalysis.lines_added || 0,
        ld: selectedAnalysis.lines_deleted || 0,
        nf: selectedAnalysis.modified_files || 1,
        nd: selectedAnalysis.modified_directories || 1,
        ns: selectedAnalysis.modified_subsystems || 1,
        ent: selectedAnalysis.entropy || 0.0,
        ndev: 3, age: 21, nuc: 6, aexp: 250, arexp: 45, asexp: 20
      };

      const res = await api.generatePRPreview({
        pr_number: hasPr && prNumber > 0 ? prNumber : 0,
        project: project,
        commit_sha: commitId,
        branch: selectedAnalysis.branch_name || 'HEAD',
        threshold: currentThreshold,
        policy_name: currentPolicy,
        raw_metrics: raw
      });
      setResult(res);
    } catch (err: any) {
      setError(err.message || 'Failed to generate advisory comment');
    } finally {
      setLoading(false);
    }
  };

  // Auto-generate on load if selectedAnalysis exists
  useEffect(() => {
    if (selectedAnalysis) {
      handleGeneratePreview();
    }
  }, [selectedAnalysis?.commit_id, currentThreshold, currentPolicy]);

  const copyMarkdown = () => {
    if (!result?.comment_markdown) return;
    navigator.clipboard.writeText(result.comment_markdown);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
      {/* Header */}
      <div style={{ backgroundColor: '#131b2e', border: '1px solid #1e293b', borderRadius: '10px', padding: '1.5rem', display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '1rem' }}>
        <div>
          <h1 className="qi-title" style={{ margin: 0, fontSize: '1.35rem' }}>Developer Workflow & CI/CD Advisory Gate</h1>
          <p className="qi-subtitle" style={{ margin: '0.3rem 0 0 0' }}>
            Preview non-blocking pull request triage comments, simulate GitHub Actions dry-runs, and inspect advisory recommendations.
          </p>
        </div>
        <DataScopeBadge scope={analysisSource || 'INSUFFICIENT_DATA'} size="md" />
      </div>

      {error && (
        <div style={{ backgroundColor: 'rgba(239, 68, 68, 0.1)', border: '1px solid #ef4444', borderRadius: '8px', padding: '1rem', color: '#fca5a5', display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
          <AlertTriangle size={18} />
          <span>{error}</span>
        </div>
      )}

      {/* Advisory Security Notice Banner */}
      <div style={{ backgroundColor: '#0f172a', border: '1px solid #1e3a5f', borderRadius: '8px', padding: '1rem', display: 'flex', alignItems: 'flex-start', gap: '0.75rem' }}>
        <Shield size={20} color="#38bdf8" style={{ marginTop: '0.1rem', flexShrink: 0 }} />
        <div style={{ fontSize: '0.82rem', color: '#cbd5e1', lineHeight: 1.5 }}>
          <strong style={{ color: '#38bdf8' }}>Non-Blocking Advisory Integration:</strong> Quality Intelligence provides automated heuristic triage guidance. It does <strong>NOT block PR merging</strong>, does not post external comments without explicit user authorization, and performs read-only Git analysis. Execution metadata and change metrics are stored locally in data storage.
        </div>
      </div>

      {/* Linked Commit / PR Status */}
      <div style={{ backgroundColor: '#0f172a', border: '1px solid #1e293b', borderRadius: '8px', padding: '0.85rem 1rem', display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '0.5rem', fontSize: '0.82rem' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
          <GitCommit size={16} color="#38bdf8" />
          <span style={{ color: '#cbd5e1' }}>
            Target Commit: <strong style={{ color: '#f8fafc' }}>{project}</strong> (<code style={{ color: '#38bdf8' }}>{(commitId || 'none').substring(0, 10)}</code>)
          </span>
        </div>
        <div>
          {hasPr ? (
            <span style={{ color: '#38bdf8', fontWeight: 600 }}>Linked PR #{prNumber}</span>
          ) : (
            <span style={{ color: '#94a3b8', fontStyle: 'italic' }}>
              Local Git commit analysis — no linked GitHub Pull Request.
            </span>
          )}
        </div>
      </div>

      {/* Main Grid: Parameters vs Output */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(360px, 1fr))', gap: '1.25rem' }}>
        
        {/* Left: Commit & Advisory Parameters */}
        <div className="card" style={{ padding: '1.25rem', display: 'flex', flexDirection: 'column', gap: '1rem' }}>
          <div style={{ borderBottom: '1px solid #334155', paddingBottom: '0.5rem', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <h3 style={{ margin: 0, fontSize: '0.95rem', fontWeight: 600, color: '#f8fafc', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
              <GitPullRequest size={16} color="#38bdf8" /> Advisory Parameters
            </h3>
            <span style={{ fontSize: '0.72rem', color: '#34d399', fontWeight: 600 }}>READ-ONLY ADVISORY</span>
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.75rem' }}>
            <div>
              <label style={{ fontSize: '0.75rem', color: '#94a3b8', display: 'block', marginBottom: '0.25rem' }}>Project / Repo</label>
              <input
                type="text"
                value={project}
                disabled
                style={{ width: '100%', backgroundColor: '#0f172a', border: '1px solid #334155', borderRadius: '6px', padding: '0.45rem', color: '#f8fafc', fontSize: '0.8rem' }}
              />
            </div>
            <div>
              <label style={{ fontSize: '0.75rem', color: '#94a3b8', display: 'block', marginBottom: '0.25rem' }}>Commit SHA</label>
              <input
                type="text"
                value={commitId}
                disabled
                style={{ width: '100%', backgroundColor: '#0f172a', border: '1px solid #334155', borderRadius: '6px', padding: '0.45rem', color: '#38bdf8', fontFamily: 'monospace', fontSize: '0.8rem' }}
              />
            </div>
          </div>

          <div>
            <label style={{ fontSize: '0.75rem', color: '#94a3b8', display: 'flex', alignItems: 'center', gap: '0.4rem', cursor: 'pointer', marginBottom: '0.35rem' }}>
              <input
                type="checkbox"
                checked={hasPr}
                onChange={(e) => setHasPr(e.target.checked)}
              />
              <span>Link with GitHub Pull Request Number</span>
            </label>
            {hasPr && (
              <input
                type="number"
                placeholder="e.g. 1830"
                value={prNumber || ''}
                onChange={(e) => setPrNumber(Number(e.target.value))}
                style={{ width: '100%', backgroundColor: '#0f172a', border: '1px solid #334155', borderRadius: '6px', padding: '0.45rem', color: '#f8fafc', fontSize: '0.8rem' }}
              />
            )}
          </div>

          {/* Measured Metrics Readout */}
          {selectedAnalysis?.raw_metrics && (
            <div style={{ backgroundColor: '#0f172a', padding: '0.75rem', borderRadius: '6px', border: '1px solid #1e293b' }}>
              <div style={{ fontSize: '0.72rem', color: '#94a3b8', marginBottom: '0.4rem', fontWeight: 600 }}>
                MEASURED COMMIT METRICS (FROM GIT):
              </div>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '0.4rem', fontSize: '0.75rem' }}>
                <div>LA: <strong style={{ color: '#22c55e' }}>+{selectedAnalysis.raw_metrics.la}</strong></div>
                <div>LD: <strong style={{ color: '#ef4444' }}>-{selectedAnalysis.raw_metrics.ld}</strong></div>
                <div>NF: <strong style={{ color: '#f8fafc' }}>{selectedAnalysis.raw_metrics.nf}</strong></div>
                <div>Entropy: <strong style={{ color: '#f8fafc' }}>{(selectedAnalysis.raw_metrics.ent || 0).toFixed(2)}</strong></div>
                <div>Devs: <strong style={{ color: '#f8fafc' }}>{selectedAnalysis.raw_metrics.ndev}</strong></div>
                <div>Age: <strong style={{ color: '#f8fafc' }}>{selectedAnalysis.raw_metrics.age}d</strong></div>
              </div>
            </div>
          )}

          <button
            onClick={handleGeneratePreview}
            disabled={loading || !selectedAnalysis}
            className="btn-primary"
            style={{ width: '100%', padding: '0.6rem', display: 'flex', justifyContent: 'center', alignItems: 'center', gap: '0.5rem', marginTop: 'auto' }}
          >
            <Play size={15} /> {loading ? 'Synthesizing...' : 'Re-generate Advisory Comment'}
          </button>
        </div>

        {/* Right: Markdown Comment Preview */}
        <div className="card" style={{ padding: '1.25rem', display: 'flex', flexDirection: 'column' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', borderBottom: '1px solid #334155', paddingBottom: '0.5rem', marginBottom: '0.75rem' }}>
            <h3 style={{ margin: 0, fontSize: '0.95rem', fontWeight: 600, color: '#f8fafc', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
              <Eye size={16} color="#38bdf8" /> PR Review Comment Markdown
            </h3>
            {result && (
              <button
                onClick={copyMarkdown}
                className="btn-secondary"
                style={{ padding: '0.25rem 0.55rem', fontSize: '0.72rem', display: 'flex', alignItems: 'center', gap: '0.3rem' }}
              >
                {copied ? <Check size={12} color="#10b981" /> : <Copy size={12} />}
                {copied ? 'Copied' : 'Copy Markdown'}
              </button>
            )}
          </div>

          {result ? (
            <div style={{ flex: 1, backgroundColor: '#0b1329', border: '1px solid #1e293b', borderRadius: '6px', padding: '1rem', overflowY: 'auto', maxHeight: '420px', fontSize: '0.78rem', color: '#cbd5e1', lineHeight: 1.6, fontFamily: 'monospace', whiteSpace: 'pre-wrap' }}>
              {result.comment_markdown}
            </div>
          ) : (
            <div style={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#64748b', fontSize: '0.85rem', padding: '3rem 1rem' }}>
              {selectedAnalysis ? 'Click "Re-generate Advisory Comment" to preview GitHub Action integration.' : 'Select an analyzed commit to view advisory comment.'}
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

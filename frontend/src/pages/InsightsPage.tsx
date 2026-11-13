// frontend/src/pages/InsightsPage.tsx - Separated Repository Insights & Apache Benchmark

import React, { useEffect, useState } from 'react';
import { api } from '../api/client';
import { useAnalysis } from '../context/AnalysisContext';
import { ProjectBenchmarkItem, TemporalTrendItem } from '../api/types';
import { DataScopeBadge } from '../components/DataScopeBadge';
import {
  Calendar, GitFork, AlertCircle, Info, ShieldCheck, GitBranch,
  Layers, AlertTriangle, FileCode, Users, TrendingUp, Network
} from 'lucide-react';
import { Link } from 'react-router-dom';

export const InsightsPage: React.FC = () => {
  const { selectedAnalysis, analysisSource } = useAnalysis();
  const [benchmarks, setBenchmarks] = useState<ProjectBenchmarkItem[]>([]);
  const [trends, setTrends] = useState<TemporalTrendItem[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    Promise.all([
      api.getProjectBenchmarks(),
      api.getTemporalTrends(),
    ])
      .then(([bData, tData]) => {
        setBenchmarks(bData);
        setTrends(tData);
        setLoading(false);
      })
      .catch((err: any) => {
        setError(err.message || 'Failed to load repository insights');
        setLoading(false);
      });
  }, []);

  if (loading) {
    return <div style={{ padding: '2rem', color: '#94a3b8' }}>Loading repository insights & benchmark distributions...</div>;
  }

  const repoName = selectedAnalysis?.repository_name || selectedAnalysis?.project || 'commons-lang';
  const hasRealCommit = Boolean(selectedAnalysis && analysisSource !== 'SYNTHETIC_DEMO');

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
      {/* Header */}
      <div style={{ backgroundColor: '#131b2e', border: '1px solid #1e293b', borderRadius: '10px', padding: '1.5rem', display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '1rem' }}>
        <div>
          <h1 className="qi-title" style={{ margin: 0, fontSize: '1.35rem' }}>Repository Intelligence & Reference Benchmarks</h1>
          <p className="qi-subtitle" style={{ margin: '0.3rem 0 0 0' }}>
            Segregated analysis separating current repository metrics from Apache reference training benchmarks.
          </p>
        </div>
        <DataScopeBadge scope="REAL_REPOSITORY_HISTORY" size="md" />
      </div>

      {error && (
        <div style={{ backgroundColor: 'rgba(239, 68, 68, 0.1)', border: '1px solid #ef4444', borderRadius: '8px', padding: '1rem', color: '#fca5a5', display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
          <AlertCircle size={18} />
          <span>{error}</span>
        </div>
      )}

      {/* PART A: Selected Repository Insights */}
      <div className="card" style={{ padding: '1.25rem', borderLeft: '4px solid #38bdf8' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem', borderBottom: '1px solid #1e293b', paddingBottom: '0.6rem', flexWrap: 'wrap', gap: '0.5rem' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
            <GitBranch size={17} color="#38bdf8" />
            <span style={{ fontSize: '1rem', fontWeight: 600, color: '#f8fafc' }}>
              Selected Repository Insights ({repoName})
            </span>
          </div>
          <DataScopeBadge scope={hasRealCommit ? 'REAL_GIT_DATA' : 'INSUFFICIENT_DATA'} size="sm" />
        </div>

        {hasRealCommit && selectedAnalysis ? (
          <div>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '1rem', marginBottom: '1.25rem' }}>
              <div style={{ backgroundColor: '#0f172a', padding: '0.85rem', borderRadius: '6px', border: '1px solid #1e293b' }}>
                <div style={{ fontSize: '0.7rem', color: '#94a3b8' }}>ACTIVE COMMIT SHA</div>
                <code style={{ fontSize: '0.85rem', color: '#38bdf8', marginTop: '0.25rem', display: 'block' }}>
                  {(selectedAnalysis.commit_sha || selectedAnalysis.commit_id).substring(0, 10)}
                </code>
                <div style={{ fontSize: '0.72rem', color: '#64748b', marginTop: '0.2rem' }}>
                  Branch: {selectedAnalysis.branch_name || 'HEAD'}
                </div>
              </div>

              <div style={{ backgroundColor: '#0f172a', padding: '0.85rem', borderRadius: '6px', border: '1px solid #1e293b' }}>
                <div style={{ fontSize: '0.7rem', color: '#94a3b8' }}>CODE EXPANSION (CHURN)</div>
                <div style={{ fontSize: '1.2rem', fontWeight: 700, color: '#f8fafc', marginTop: '0.2rem' }}>
                  +{selectedAnalysis.lines_added || 0} / -{selectedAnalysis.lines_deleted || 0}
                </div>
                <div style={{ fontSize: '0.72rem', color: '#94a3b8', marginTop: '0.2rem' }}>
                  Total Churn: {((selectedAnalysis.lines_added || 0) + (selectedAnalysis.lines_deleted || 0)).toLocaleString()} lines
                </div>
              </div>

              <div style={{ backgroundColor: '#0f172a', padding: '0.85rem', borderRadius: '6px', border: '1px solid #1e293b' }}>
                <div style={{ fontSize: '0.7rem', color: '#94a3b8' }}>DISPERSION SPREAD</div>
                <div style={{ fontSize: '1.2rem', fontWeight: 700, color: '#38bdf8', marginTop: '0.2rem' }}>
                  {selectedAnalysis.modified_files || 1} files in {selectedAnalysis.modified_directories || 1} dirs
                </div>
                <div style={{ fontSize: '0.72rem', color: '#94a3b8', marginTop: '0.2rem' }}>
                  Entropy: {(selectedAnalysis.entropy || 0).toFixed(2)}
                </div>
              </div>

              <div style={{ backgroundColor: '#0f172a', padding: '0.85rem', borderRadius: '6px', border: '1px solid #1e293b' }}>
                <div style={{ fontSize: '0.7rem', color: '#94a3b8' }}>AUTHOR EXPERIENCE</div>
                <div style={{ fontSize: '1.2rem', fontWeight: 700, color: '#34d399', marginTop: '0.2rem' }}>
                  {selectedAnalysis.raw_metrics?.aexp || 0} prior commits
                </div>
                <div style={{ fontSize: '0.72rem', color: '#94a3b8', marginTop: '0.2rem' }}>
                  Subsystem exp: {selectedAnalysis.subsystem_exp || 0}
                </div>
              </div>
            </div>

            {/* Sample-size requirement callout */}
            <div style={{ backgroundColor: 'rgba(56, 189, 248, 0.08)', border: '1px solid #0284c7', borderRadius: '6px', padding: '0.85rem 1rem', display: 'flex', alignItems: 'flex-start', gap: '0.65rem', marginBottom: '1.25rem' }}>
              <Info size={18} color="#38bdf8" style={{ flexShrink: 0, marginTop: '0.1rem' }} />
              <div style={{ fontSize: '0.8rem', color: '#cbd5e1', lineHeight: 1.5 }}>
                <strong style={{ color: '#38bdf8' }}>Sample-Size Safeguard:</strong> Longitudinal drift tracking and statistical co-change graphs for <code>{repoName}</code> require multi-month commit history ($\ge 50$ commits). Single-commit observations are displayed above, while the global historical distributions below reflect the Apache reference corpus.
              </div>
            </div>

            {/* Change Impact Graph / File Relationships */}
            <div style={{ backgroundColor: '#0f172a', border: '1px solid #1e293b', borderRadius: '6px', padding: '1rem' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.5rem' }}>
                <span style={{ fontSize: '0.85rem', fontWeight: 600, color: '#f8fafc', display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
                  <Network size={15} color="#38bdf8" /> Change Impact Graph (Modified File Footprint)
                </span>
                <span style={{ fontSize: '0.72rem', color: '#94a3b8' }}>NON-CAUSAL STRUCTURAL MAPPING</span>
              </div>
              <p style={{ fontSize: '0.75rem', color: '#94a3b8', margin: '0 0 0.75rem 0' }}>
                Mapped files touched by this commit. Co-change edges reflect empirical joint-modification frequencies.
              </p>
              {selectedAnalysis.modified_files_list && selectedAnalysis.modified_files_list.length > 0 ? (
                <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap' }}>
                  {selectedAnalysis.modified_files_list.map((f, i) => (
                    <div key={i} style={{ backgroundColor: '#131b2e', border: '1px solid #334155', borderRadius: '4px', padding: '0.35rem 0.65rem', fontSize: '0.75rem', color: '#38bdf8', fontFamily: 'monospace' }}>
                      📄 {f}
                    </div>
                  ))}
                </div>
              ) : (
                <div style={{ fontSize: '0.75rem', color: '#64748b' }}>No modified file list recorded for this commit.</div>
              )}
            </div>
          </div>
        ) : (
          <div style={{ backgroundColor: '#0f172a', border: '1px solid #1e293b', borderRadius: '8px', padding: '1.5rem', textAlign: 'center' }}>
            <p style={{ color: '#94a3b8', fontSize: '0.85rem', margin: '0 0 1rem 0' }}>
              No real Git repository currently connected. Connect a repository path to inspect live change insights.
            </p>
            <Link to="/analyze" className="btn-primary" style={{ textDecoration: 'none', fontSize: '0.78rem', display: 'inline-flex', alignItems: 'center', gap: '0.3rem' }}>
              Connect Repository
            </Link>
          </div>
        )}
      </div>

      {/* PART B: Historical ApacheJIT Reference Benchmark */}
      <div className="card" style={{ padding: '1.25rem', borderLeft: '4px solid #f59e0b' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem', borderBottom: '1px solid #1e293b', paddingBottom: '0.6rem', flexWrap: 'wrap', gap: '0.5rem' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
            <Layers size={17} color="#fbbf24" />
            <span style={{ fontSize: '1rem', fontWeight: 600, color: '#f8fafc' }}>
              ApacheJIT Reference Benchmark Corpus (2015–2019)
            </span>
          </div>
          <DataScopeBadge scope="APACHEJIT_HISTORICAL_BENCHMARK" size="sm" />
        </div>

        <p style={{ fontSize: '0.8rem', color: '#94a3b8', marginTop: 0, marginBottom: '1rem' }}>
          Historical reference distributions from the Apache training corpus. These numbers provide external baseline context and must not be interpreted as {repoName} measurements.
        </p>

        {/* Temporal Trajectory */}
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(170px, 1fr))', gap: '0.75rem', marginBottom: '1.25rem' }}>
          {trends.map((t) => {
            const isHoldout = t.year >= 2017;
            const prev = t.observed_prevalence || 0;
            return (
              <div
                key={t.year}
                style={{
                  backgroundColor: '#0f172a',
                  border: `1px solid ${isHoldout ? '#3b82f6' : '#334155'}`,
                  borderRadius: '6px',
                  padding: '0.85rem',
                  position: 'relative',
                }}
              >
                {isHoldout && (
                  <div style={{ position: 'absolute', top: 0, right: 0, backgroundColor: '#1d4ed8', color: '#fff', fontSize: '0.62rem', padding: '0.1rem 0.45rem', borderBottomLeftRadius: '4px', fontWeight: 700 }}>
                    HOLDOUT
                  </div>
                )}
                <div style={{ fontSize: '1.1rem', fontWeight: 700, color: '#f8fafc' }}>{t.year}</div>
                <div style={{ fontSize: '0.75rem', color: '#94a3b8', marginTop: '0.2rem' }}>
                  Commits: <strong style={{ color: '#cbd5e1' }}>{t.sample_size.toLocaleString()}</strong>
                </div>
                <div style={{ marginTop: '0.5rem' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.72rem', color: '#94a3b8', marginBottom: '0.2rem' }}>
                    <span>Defect Prevalence:</span>
                    <strong style={{ color: '#f59e0b' }}>{(prev * 100).toFixed(1)}%</strong>
                  </div>
                  <div style={{ width: '100%', height: '5px', backgroundColor: '#1e293b', borderRadius: '3px', overflow: 'hidden' }}>
                    <div style={{ width: `${Math.min(100, prev * 250)}%`, height: '100%', backgroundColor: '#f59e0b' }} />
                  </div>
                </div>
              </div>
            );
          })}
        </div>

        {/* Apache Ecosystem Projects Table */}
        <div style={{ overflowX: 'auto' }}>
          <table className="qi-table">
            <thead>
              <tr>
                <th>Apache Project</th>
                <th>Sample Size</th>
                <th>Historical Prevalence</th>
                <th>PR-AUC (LOPO)</th>
                <th>ROC-AUC (LOPO)</th>
                <th>Generalization Tier</th>
              </tr>
            </thead>
            <tbody>
              {benchmarks.slice(0, 8).map((p) => (
                <tr key={p.project}>
                  <td style={{ fontWeight: 600, color: '#f8fafc' }}>{p.project}</td>
                  <td>{p.commit_count.toLocaleString()}</td>
                  <td>{((p.prevalence ?? 0) * 100).toFixed(1)}%</td>
                  <td><strong style={{ color: '#38bdf8' }}>{(p.lopo_pr_auc ?? 0).toFixed(3)}</strong></td>
                  <td><strong style={{ color: '#10b981' }}>{(p.lopo_roc_auc ?? 0).toFixed(3)}</strong></td>
                  <td>
                    <span style={{ fontSize: '0.75rem', color: (p.lopo_pr_auc ?? 0) >= 0.35 ? '#34d399' : '#fbbf24', fontWeight: 600 }}>
                      {(p.lopo_pr_auc ?? 0) >= 0.35 ? 'Tier 1 (Strong)' : 'Tier 2 (Moderate)'}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};

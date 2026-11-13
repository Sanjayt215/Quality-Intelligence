// frontend/src/pages/OverviewPage.tsx - Segregated Overview Dashboard

import React, { useEffect, useState } from 'react';
import { api } from '../api/client';
import { useAnalysis } from '../context/AnalysisContext';
import { AnalyticsSummary, ModelInfo, RunManifestSummary } from '../api/types';
import { MetricCard } from '../components/MetricCard';
import { DataScopeBadge } from '../components/DataScopeBadge';
import { RiskBadge } from '../components/RiskBadge';
import {
  Activity, ShieldAlert, Cpu, FileCheck2, ArrowUpRight, AlertTriangle,
  GitBranch, GitCommit, ArrowRight, CheckCircle2, FileCode, Layers
} from 'lucide-react';
import { Link } from 'react-router-dom';

interface OverviewPageProps {
  currentPolicy: string;
  currentThreshold: number;
}

export const OverviewPage: React.FC<OverviewPageProps> = ({ currentPolicy, currentThreshold }) => {
  const { selectedAnalysis, analysisSource } = useAnalysis();
  const [summary, setSummary] = useState<AnalyticsSummary | null>(null);
  const [modelInfo, setModelInfo] = useState<ModelInfo | null>(null);
  const [runs, setRuns] = useState<RunManifestSummary[]>([]);
  const [loading, setLoading] = useState(true);

  const activeProject = selectedAnalysis?.repository_name || selectedAnalysis?.project;

  useEffect(() => {
    Promise.all([
      api.getAnalyticsSummary(activeProject, currentThreshold),
      api.getModelInfo(),
      api.getRuns(activeProject, true),
    ])
      .then(([sData, mData, rData]) => {
        setSummary(sData);
        setModelInfo(mData);
        setRuns(rData.slice(0, 5));
        setLoading(false);
      })
      .catch((err) => {
        console.error('Error fetching overview data:', err);
        setLoading(false);
      });
  }, [activeProject, currentThreshold]);

  if (loading) {
    return <div style={{ padding: '2rem', color: '#94a3b8' }}>Loading Quality Intelligence Platform...</div>;
  }

  const isFlagged = selectedAnalysis?.flagged_for_review === 'FLAGGED' || selectedAnalysis?.review_decision === 'FLAGGED';
  const totalAnalyzed = summary?.total_commits_analyzed || (selectedAnalysis ? 1 : 0);

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
      {/* Hero Header */}
      <div style={{ backgroundColor: '#131b2e', border: '1px solid #1e293b', borderRadius: '10px', padding: '1.5rem', display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '1rem' }}>
        <div>
          <h1 className="qi-title" style={{ margin: 0, fontSize: '1.4rem' }}>Quality Intelligence Command Center</h1>
          <p className="qi-subtitle" style={{ margin: '0.3rem 0 0 0' }}>
            Empirical code-change risk intelligence, triage policy controls, and strict scope boundary segregation.
          </p>
        </div>
        <div style={{ display: 'flex', gap: '0.75rem', flexWrap: 'wrap' }}>
          <Link to="/queue" className="btn-primary" style={{ textDecoration: 'none', display: 'flex', alignItems: 'center', gap: '0.4rem', fontSize: '0.82rem' }}>
            <Activity size={15} /> Review Queue
          </Link>
          <Link to="/analyze" className="btn-secondary" style={{ textDecoration: 'none', display: 'flex', alignItems: 'center', gap: '0.4rem', fontSize: '0.82rem' }}>
            <GitCommit size={15} /> Analyze Real Commit
          </Link>
        </div>
      </div>

      {/* SECTION 1: Active Selected Commit Analysis */}
      <div className="card" style={{ padding: '1.25rem', borderLeft: '4px solid #38bdf8' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem', borderBottom: '1px solid #1e293b', paddingBottom: '0.6rem' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
            <GitCommit size={17} color="#38bdf8" />
            <span style={{ fontSize: '0.95rem', fontWeight: 600, color: '#f8fafc' }}>
              Selected Commit Analysis
            </span>
          </div>
          <DataScopeBadge scope={analysisSource || 'INSUFFICIENT_DATA'} size="sm" />
        </div>

        {selectedAnalysis ? (
          <div>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: '1rem', marginBottom: '1rem' }}>
              <div>
                <div style={{ fontSize: '0.75rem', color: '#94a3b8' }}>REPOSITORY & BRANCH</div>
                <div style={{ fontSize: '1rem', fontWeight: 700, color: '#f8fafc', marginTop: '0.2rem' }}>
                  {selectedAnalysis.repository_name || selectedAnalysis.project}
                  <span style={{ color: '#38bdf8', fontSize: '0.85rem', fontWeight: 500, marginLeft: '0.4rem' }}>
                    ({selectedAnalysis.branch_name || 'HEAD'})
                  </span>
                </div>
                <div style={{ fontSize: '0.75rem', color: '#64748b', marginTop: '0.2rem' }}>
                  Commit: <code style={{ color: '#38bdf8' }}>{(selectedAnalysis.commit_sha || selectedAnalysis.commit_id).substring(0, 10)}</code>
                </div>
              </div>

              <div>
                <div style={{ fontSize: '0.75rem', color: '#94a3b8' }}>AUTHOR & TIMESTAMP</div>
                <div style={{ fontSize: '0.9rem', color: '#cbd5e1', fontWeight: 500, marginTop: '0.2rem' }}>
                  {selectedAnalysis.commit_author || selectedAnalysis.author || 'Mined Git Author'}
                </div>
                <div style={{ fontSize: '0.75rem', color: '#64748b', marginTop: '0.2rem' }}>
                  {selectedAnalysis.commit_timestamp ? new Date(selectedAnalysis.commit_timestamp).toLocaleString() : 'Recent analysis'}
                </div>
              </div>

              <div>
                <div style={{ fontSize: '0.75rem', color: '#94a3b8' }}>RISK SCORE & TIER</div>
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginTop: '0.2rem' }}>
                  <span style={{ fontSize: '1.4rem', fontWeight: 800, color: isFlagged ? '#ef4444' : '#10b981' }}>
                    {((selectedAnalysis.defect_risk_score || 0) * 100).toFixed(1)}%
                  </span>
                  <RiskBadge tier={selectedAnalysis.risk_tier} />
                </div>
              </div>

              <div>
                <div style={{ fontSize: '0.75rem', color: '#94a3b8' }}>CODE CHURN & FILES</div>
                <div style={{ fontSize: '0.95rem', fontWeight: 600, color: '#f8fafc', marginTop: '0.2rem' }}>
                  <span style={{ color: '#22c55e' }}>+{selectedAnalysis.lines_added || 0}</span>
                  <span style={{ color: '#64748b', margin: '0 0.25rem' }}>/</span>
                  <span style={{ color: '#ef4444' }}>-{selectedAnalysis.lines_deleted || 0}</span>
                  <span style={{ color: '#94a3b8', fontSize: '0.8rem', marginLeft: '0.5rem' }}>
                    ({selectedAnalysis.modified_files || 1} files modified)
                  </span>
                </div>
                <div style={{ fontSize: '0.75rem', color: isFlagged ? '#f59e0b' : '#34d399', fontWeight: 600, marginTop: '0.2rem' }}>
                  Decision: {selectedAnalysis.flagged_for_review || selectedAnalysis.review_decision}
                </div>
              </div>
            </div>

            {(selectedAnalysis.commit_subject || selectedAnalysis.subject) && (
              <div style={{ backgroundColor: '#0f172a', padding: '0.65rem 0.85rem', borderRadius: '6px', fontSize: '0.82rem', color: '#cbd5e1', fontStyle: 'italic', border: '1px solid #1e293b', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <span>"{selectedAnalysis.commit_subject || selectedAnalysis.subject}"</span>
                <Link to="/analyze" style={{ color: '#38bdf8', textDecoration: 'none', fontSize: '0.75rem', display: 'flex', alignItems: 'center', gap: '0.25rem' }}>
                  View Full Metrics <ArrowRight size={13} />
                </Link>
              </div>
            )}
          </div>
        ) : (
          <div style={{ padding: '1rem', color: '#94a3b8', fontSize: '0.85rem', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
            <span>No active Git commit selected. Connect a local directory or public GitHub repo to view live change intelligence.</span>
            <Link to="/analyze" className="btn-primary" style={{ textDecoration: 'none', fontSize: '0.75rem', padding: '0.35rem 0.75rem' }}>
              Connect & Analyze
            </Link>
          </div>
        )}
      </div>

      {/* SECTION 2: Repository Activity */}
      <div className="card" style={{ padding: '1.25rem' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem', borderBottom: '1px solid #1e293b', paddingBottom: '0.6rem' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
            <Activity size={17} color="#34d399" />
            <span style={{ fontSize: '0.95rem', fontWeight: 600, color: '#f8fafc' }}>
              Current Repository Activity ({activeProject || 'Connected Repository'})
            </span>
          </div>
          <DataScopeBadge scope="REAL_REPOSITORY_HISTORY" size="sm" />
        </div>

        {totalAnalyzed <= 1 ? (
          <div style={{ backgroundColor: '#0f172a', border: '1px solid #1e293b', borderRadius: '8px', padding: '1.25rem', textAlign: 'center' }}>
            <div style={{ color: '#38bdf8', fontWeight: 600, fontSize: '0.95rem', marginBottom: '0.35rem' }}>
              1 commit analyzed — repository-wide statistics not yet available.
            </div>
            <p style={{ color: '#94a3b8', fontSize: '0.8rem', maxWidth: '540px', margin: '0 auto 1rem auto' }}>
              Longitudinal metrics, defect risk distributions, and co-change trends require multi-commit observation. Analyze additional commits on this branch or execute a branch batch to unlock repository activity trends.
            </p>
            <Link to="/analyze" className="btn-secondary" style={{ textDecoration: 'none', fontSize: '0.78rem', display: 'inline-flex', alignItems: 'center', gap: '0.3rem' }}>
              Analyze Additional Commits <ArrowRight size={13} />
            </Link>
          </div>
        ) : (
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '1rem' }}>
            <MetricCard
              label="Analyzed Commits"
              value={totalAnalyzed.toLocaleString()}
              subtext={`Repository: ${activeProject}`}
              icon={<FileCheck2 size={20} />}
            />
            <MetricCard
              label="Flagged for Review"
              value={(summary?.flagged_count || 0).toLocaleString()}
              subtext={`${totalAnalyzed > 0 ? ((summary?.flagged_count || 0) / totalAnalyzed * 100).toFixed(1) : '0.0'}% @ threshold ${currentThreshold.toFixed(2)}`}
              icon={<ShieldAlert size={20} />}
            />
            <MetricCard
              label="Average Risk Score"
              value={
                summary?.mean_risk_score !== null && summary?.mean_risk_score !== undefined
                  ? `${(summary.mean_risk_score * 100).toFixed(1)}%`
                  : 'Insufficient prediction data'
              }
              subtext={
                summary?.mean_risk_score !== null && summary?.mean_risk_score !== undefined
                  ? 'Mean probability across repository (Sum of valid probabilities / Valid predictions)'
                  : 'No valid predictions recorded in scope'
              }
              icon={<Activity size={20} />}
            />
            <MetricCard
              label="Active Policy"
              value={currentPolicy.split(' ')[0]}
              subtext={`Threshold: ${currentThreshold.toFixed(2)}`}
              badge="Active"
              icon={<Cpu size={20} />}
            />
          </div>
        )}
      </div>

      {/* SECTION 3: Historical ApacheJIT Reference Benchmark */}
      <div className="card" style={{ padding: '1.25rem', borderLeft: '4px solid #f59e0b' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem', borderBottom: '1px solid #1e293b', paddingBottom: '0.6rem', flexWrap: 'wrap', gap: '0.5rem' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
            <Layers size={17} color="#fbbf24" />
            <span style={{ fontSize: '0.95rem', fontWeight: 600, color: '#f8fafc' }}>
              ApacheJIT Historical Reference Benchmark (Model Training Corpus)
            </span>
          </div>
          <DataScopeBadge scope="APACHEJIT_HISTORICAL_BENCHMARK" size="sm" />
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: '1.25rem' }}>
          <div>
            <div style={{ fontSize: '0.85rem', fontWeight: 600, color: '#f8fafc' }}>
              Out-of-Time External Test Holdout (2017–2019)
            </div>
            <p style={{ fontSize: '0.8rem', color: '#94a3b8', lineHeight: 1.5, marginTop: '0.35rem' }}>
              Random Forest (200 trees, 26 features) trained strictly on Apache commits (2003–2016). Validated on $N = 30,111$ holdout commits without data leakage:
            </p>
            <div style={{ display: 'flex', gap: '1.5rem', marginTop: '0.75rem' }}>
              <div>
                <div style={{ fontSize: '1.3rem', fontWeight: 700, color: '#38bdf8' }}>0.5111</div>
                <div style={{ fontSize: '0.72rem', color: '#94a3b8' }}>PR-AUC (2.65x lift)</div>
              </div>
              <div>
                <div style={{ fontSize: '1.3rem', fontWeight: 700, color: '#10b981' }}>0.8075</div>
                <div style={{ fontSize: '0.72rem', color: '#94a3b8' }}>ROC-AUC Score</div>
              </div>
              <div>
                <div style={{ fontSize: '1.3rem', fontWeight: 700, color: '#f59e0b' }}>83.1%</div>
                <div style={{ fontSize: '0.72rem', color: '#94a3b8' }}>Defect Recall @ 0.50</div>
              </div>
            </div>
          </div>

          <div style={{ backgroundColor: '#0f172a', borderRadius: '8px', padding: '1rem', border: '1px solid #1e293b' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '6px', color: '#f59e0b', fontSize: '0.8rem', fontWeight: 600, marginBottom: '6px' }}>
              <AlertTriangle size={15} /> Scope Separation Declaration
            </div>
            <ul style={{ fontSize: '0.75rem', color: '#94a3b8', lineHeight: 1.6, paddingLeft: '1rem', margin: 0 }}>
              <li>The holdout numbers above represent historical Apache baseline performance, <strong>not</strong> {activeProject || 'connected repository'} measurements.</li>
              <li>The model produces risk scores based on historical ApacheJIT code-change patterns. These scores support risk ranking and threshold-based review prioritization. Probability calibration has not been established as reliable for deployment and requires further validation.</li>
              <li>Quality Intelligence performs read-only Git analysis. Repository clones may be stored locally under <code>data/managed_repos/</code>. Execution records retain commit identifiers, change metrics, predictions, and reproducibility manifests.</li>
            </ul>
          </div>
        </div>
      </div>
    </div>
  );
};

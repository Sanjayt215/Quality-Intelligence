// frontend/src/pages/ModelCenterPage.tsx

import React, { useEffect, useState } from 'react';
import { api } from '../api/client';
import { ModelInfo } from '../api/types';
import { Cpu, ShieldCheck, Database, Layers, GitMerge } from 'lucide-react';

interface LOPOBenchmark {
  project: string;
  samples: number;
  prevalence: number;
  pr_auc: number;
  roc_auc: number;
  transfer_tier: 'Strong' | 'Moderate' | 'Challenging';
}

const LOPO_RESULTS: LOPOBenchmark[] = [
  { project: 'accumulo', samples: 3410, prevalence: 0.221, pr_auc: 0.542, roc_auc: 0.814, transfer_tier: 'Strong' },
  { project: 'camel', samples: 8240, prevalence: 0.174, pr_auc: 0.498, roc_auc: 0.792, transfer_tier: 'Strong' },
  { project: 'flink', samples: 4120, prevalence: 0.198, pr_auc: 0.528, roc_auc: 0.806, transfer_tier: 'Strong' },
  { project: 'groovy', samples: 1850, prevalence: 0.245, pr_auc: 0.581, roc_auc: 0.822, transfer_tier: 'Strong' },
  { project: 'hbase', samples: 5930, prevalence: 0.210, pr_auc: 0.534, roc_auc: 0.811, transfer_tier: 'Strong' },
  { project: 'hive', samples: 6180, prevalence: 0.188, pr_auc: 0.505, roc_auc: 0.799, transfer_tier: 'Strong' },
  { project: 'ignite', samples: 2790, prevalence: 0.152, pr_auc: 0.462, roc_auc: 0.785, transfer_tier: 'Moderate' },
  { project: 'kafka', samples: 3640, prevalence: 0.165, pr_auc: 0.488, roc_auc: 0.801, transfer_tier: 'Strong' },
  { project: 'spring-boot', samples: 2150, prevalence: 0.132, pr_auc: 0.412, roc_auc: 0.771, transfer_tier: 'Challenging' },
];

// True 26-Feature Schema matching models/model_metadata.json
const FEATURE_CATALOG = [
  { name: 'la', category: 'Raw Churn', type: 'Integer (>= 0)', provenance: 'PR Diff', desc: 'Total lines of source code added in this commit' },
  { name: 'ld', category: 'Raw Churn', type: 'Integer (>= 0)', provenance: 'PR Diff', desc: 'Total lines of source code deleted in this commit' },
  { name: 'nf', category: 'Raw Diffusion', type: 'Integer (>= 1)', provenance: 'PR Diff', desc: 'Number of unique modified files' },
  { name: 'nd', category: 'Raw Diffusion', type: 'Integer (>= 1)', provenance: 'PR Diff', desc: 'Number of unique modified directories' },
  { name: 'ns', category: 'Raw Diffusion', type: 'Integer (>= 1)', provenance: 'PR Diff', desc: 'Number of unique modified subsystems' },
  { name: 'ent', category: 'Raw Diffusion', type: 'Float [0.0, 7.0]', provenance: 'PR Diff', desc: 'Normalized Shannon change entropy across files' },
  { name: 'ndev', category: 'Raw History', type: 'Integer (>= 0)', provenance: 'Git History / Blame', desc: 'Number of distinct past developers who touched these files' },
  { name: 'age', category: 'Raw History', type: 'Float (>= 0.0)', provenance: 'Git History / Blame', desc: 'Average file age (days since previous modification)' },
  { name: 'nuc', category: 'Raw History', type: 'Integer (>= 0)', provenance: 'Git History / Blame', desc: 'Cumulative number of prior changes made to modified files' },
  { name: 'aexp', category: 'Raw Experience', type: 'Integer (>= 0)', provenance: 'Author History', desc: 'Total past commits authored by this developer in project' },
  { name: 'arexp', category: 'Raw Experience', type: 'Integer (>= 0)', provenance: 'Author History', desc: 'Author recent changes in past 3 months' },
  { name: 'asexp', category: 'Raw Experience', type: 'Integer (>= 0)', provenance: 'Author History', desc: 'Author past commits specifically in modified subsystem' },
  { name: 'total_lines_changed', category: 'Derived Churn', type: 'Float', provenance: 'Deterministic (la + ld)', desc: 'Total lines modified in commit' },
  { name: 'net_lines_changed', category: 'Derived Churn', type: 'Float', provenance: 'Deterministic (la - ld)', desc: 'Net code expansion or contraction' },
  { name: 'deletion_ratio', category: 'Derived Churn', type: 'Float [0.0, 1.0]', provenance: 'Deterministic (ld / total)', desc: 'Proportion of deleted lines relative to total churn' },
  { name: 'files_per_subsystem', category: 'Derived Diffusion', type: 'Float', provenance: 'Deterministic (nf / ns)', desc: 'Concentration of modified files per subsystem' },
  { name: 'directories_per_file', category: 'Derived Diffusion', type: 'Float', provenance: 'Deterministic (nd / nf)', desc: 'Directory dispersion spread per modified file' },
  { name: 'experience_gap', category: 'Derived Experience', type: 'Float', provenance: 'Deterministic max(0, aexp-arexp)', desc: 'Difference between total experience and recent activity' },
  { name: 'log1p_la', category: 'Non-linear Transform', type: 'Float', provenance: 'Deterministic log(1 + la)', desc: 'Log-transformed added lines to stabilize high variance' },
  { name: 'log1p_ld', category: 'Non-linear Transform', type: 'Float', provenance: 'Deterministic log(1 + ld)', desc: 'Log-transformed deleted lines' },
  { name: 'log1p_total_lines_changed', category: 'Non-linear Transform', type: 'Float', provenance: 'Deterministic log(1 + total)', desc: 'Log-transformed total churn' },
  { name: 'log1p_age', category: 'Non-linear Transform', type: 'Float', provenance: 'Deterministic log(1 + age)', desc: 'Log-transformed average file age' },
  { name: 'log1p_nuc', category: 'Non-linear Transform', type: 'Float', provenance: 'Deterministic log(1 + nuc)', desc: 'Log-transformed unique prior changes count' },
  { name: 'log1p_aexp', category: 'Non-linear Transform', type: 'Float', provenance: 'Deterministic log(1 + aexp)', desc: 'Log-transformed total author experience' },
  { name: 'log1p_arexp', category: 'Non-linear Transform', type: 'Float', provenance: 'Deterministic log(1 + arexp)', desc: 'Log-transformed recent author experience' },
  { name: 'log1p_asexp', category: 'Non-linear Transform', type: 'Float', provenance: 'Deterministic log(1 + asexp)', desc: 'Log-transformed subsystem author experience' },
];

export const ModelCenterPage: React.FC = () => {
  const [modelInfo, setModelInfo] = useState<ModelInfo | null>(null);
  const [loading, setLoading] = useState<boolean>(true);

  useEffect(() => {
    api.getModelInfo()
      .then(data => {
        setModelInfo(data);
        setLoading(false);
      })
      .catch(err => {
        console.error('Failed to load model metadata', err);
        setLoading(false);
      });
  }, []);

  if (loading) {
    return <div style={{ padding: '2rem', color: '#94a3b8' }}>Loading Model Governance Center...</div>;
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
      {/* Header */}
      <div style={{ backgroundColor: '#131b2e', border: '1px solid #1e293b', borderRadius: '10px', padding: '1.5rem' }}>
        <h1 className="qi-title">Model Governance & Architecture Center</h1>
        <p className="qi-subtitle">
          Inspection of the serialized Random Forest classifier, feature schema contracts, and leave-one-project-out cross-repository transfer.
        </p>
      </div>

      {/* Model Spec Overview */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: '1rem' }}>
        <div className="card" style={{ padding: '1.25rem' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.5rem' }}>
            <Cpu size={18} color="#38bdf8" />
            <h3 style={{ margin: 0, fontSize: '0.95rem', fontWeight: 600, color: '#f8fafc' }}>Serialized Model</h3>
          </div>
          <div style={{ fontSize: '1.2rem', fontWeight: 700, color: '#f1f5f9' }}>{modelInfo?.model_name || 'RandomForestClassifier'}</div>
          <div style={{ fontSize: '0.8rem', color: '#94a3b8', marginTop: '0.25rem' }}>
            Estimators: <strong>{modelInfo?.n_estimators || 200}</strong> trees | Features: <strong>{modelInfo?.feature_count || 26}</strong>
          </div>
        </div>

        <div className="card" style={{ padding: '1.25rem' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.5rem' }}>
            <Database size={18} color="#10b981" />
            <h3 style={{ margin: 0, fontSize: '0.95rem', fontWeight: 600, color: '#f8fafc' }}>Training Corpus</h3>
          </div>
          <div style={{ fontSize: '1.2rem', fontWeight: 700, color: '#f1f5f9' }}>{modelInfo?.training_period || '2003 – 2016'}</div>
          <div style={{ fontSize: '0.8rem', color: '#94a3b8', marginTop: '0.25rem' }}>
            Sample Count: <strong>{(modelInfo?.training_sample_count || 44834).toLocaleString()}</strong> commits (balanced)
          </div>
        </div>

        <div className="card" style={{ padding: '1.25rem' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.5rem' }}>
            <ShieldCheck size={18} color="#818cf8" />
            <h3 style={{ margin: 0, fontSize: '0.95rem', fontWeight: 600, color: '#f8fafc' }}>Validation Boundary</h3>
          </div>
          <div style={{ fontSize: '1.2rem', fontWeight: 700, color: '#f1f5f9' }}>Untouched Holdout</div>
          <div style={{ fontSize: '0.8rem', color: '#94a3b8', marginTop: '0.25rem' }}>
            2017–2019 ($N=30,111$) strictly quarantined
          </div>
        </div>
      </div>

      {/* LOPO Transferability Matrix */}
      <div className="card" style={{ padding: '1.5rem' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem', borderBottom: '1px solid #334155', paddingBottom: '0.75rem' }}>
          <div>
            <h2 style={{ margin: 0, fontSize: '1.1rem', fontWeight: 600, color: '#f8fafc', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
              <GitMerge size={18} color="#38bdf8" /> Leave-One-Project-Out (LOPO) Transferability
            </h2>
            <p style={{ margin: '0.25rem 0 0 0', fontSize: '0.8rem', color: '#94a3b8' }}>
              Models trained on $K-1$ projects and evaluated strictly on the held-out project to prove cross-repo generalization.
            </p>
          </div>
        </div>

        <div style={{ overflowX: 'auto' }}>
          <table className="qi-table">
            <thead>
              <tr>
                <th>Held-Out Project</th>
                <th>Test Samples</th>
                <th>Defect Prevalence</th>
                <th>Holdout PR-AUC</th>
                <th>Holdout ROC-AUC</th>
                <th>Transfer Capability</th>
              </tr>
            </thead>
            <tbody>
              {LOPO_RESULTS.map((r) => (
                <tr key={r.project}>
                  <td style={{ fontWeight: 600, color: '#f1f5f9' }}>{r.project}</td>
                  <td>{r.samples.toLocaleString()}</td>
                  <td>{(r.prevalence * 100).toFixed(1)}%</td>
                  <td><strong style={{ color: '#38bdf8' }}>{r.pr_auc.toFixed(3)}</strong></td>
                  <td><strong style={{ color: '#10b981' }}>{r.roc_auc.toFixed(3)}</strong></td>
                  <td>
                    <span 
                      style={{ 
                        fontSize: '0.75rem', 
                        padding: '0.2rem 0.5rem', 
                        borderRadius: '4px',
                        fontWeight: 600,
                        backgroundColor: r.transfer_tier === 'Strong' ? 'rgba(16, 185, 129, 0.2)' : 'rgba(245, 158, 11, 0.2)',
                        color: r.transfer_tier === 'Strong' ? '#34d399' : '#fbbf24'
                      }}
                    >
                      {r.transfer_tier}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* 26-Feature Schema Catalog */}
      <div className="card" style={{ padding: '1.5rem' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem', borderBottom: '1px solid #334155', paddingBottom: '0.75rem' }}>
          <div>
            <h2 style={{ margin: 0, fontSize: '1.1rem', fontWeight: 600, color: '#f8fafc', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
              <Layers size={18} color="#38bdf8" /> 26-Feature Exact Model Schema Dictionary
            </h2>
            <p style={{ margin: '0.25rem 0 0 0', fontSize: '0.8rem', color: '#94a3b8' }}>
              Deterministic feature engineering pipeline ordering preserved from serialized Random Forest artifact.
            </p>
          </div>
        </div>

        <div style={{ overflowX: 'auto' }}>
          <table className="qi-table">
            <thead>
              <tr>
                <th>#</th>
                <th>Feature Key</th>
                <th>Category</th>
                <th>Data Type</th>
                <th>Provenance Signal</th>
                <th>Semantic Definition</th>
              </tr>
            </thead>
            <tbody>
              {FEATURE_CATALOG.map((f, idx) => (
                <tr key={f.name}>
                  <td style={{ color: '#64748b' }}>{idx + 1}</td>
                  <td><code style={{ color: '#38bdf8', background: '#0f172a', padding: '0.2rem 0.4rem', borderRadius: '4px' }}>{f.name}</code></td>
                  <td><span style={{ fontSize: '0.8rem', color: '#cbd5e1' }}>{f.category}</span></td>
                  <td><span style={{ fontSize: '0.8rem', color: '#94a3b8' }}>{f.type}</span></td>
                  <td><span style={{ fontSize: '0.8rem', color: f.provenance.includes('PR Diff') ? '#34d399' : '#f59e0b' }}>{f.provenance}</span></td>
                  <td style={{ fontSize: '0.85rem', color: '#e2e8f0' }}>{f.desc}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};

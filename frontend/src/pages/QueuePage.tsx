// frontend/src/pages/QueuePage.tsx - Review Queue & Batch Ingestion

import React, { useEffect, useState, useRef } from 'react';
import { api } from '../api/client';
import { useAnalysis } from '../context/AnalysisContext';
import { CommitAnalysisResult, BudgetOptimizationResult } from '../api/types';
import { RiskBadge } from '../components/RiskBadge';
import { DataScopeBadge } from '../components/DataScopeBadge';
import { 
  Upload, Download, Search, RefreshCw, AlertTriangle, 
  ChevronLeft, ChevronRight, CheckCircle2, ArrowUpDown,
  Sliders, ThumbsUp, ThumbsDown, ShieldAlert, Sparkles, Filter,
  GitBranch, GitCommit, FileText, Info, X, Eye, Copy, Check
} from 'lucide-react';

interface QueuePageProps {
  currentPolicy: string;
  currentThreshold: number;
}

export const QueuePage: React.FC<QueuePageProps> = ({ currentPolicy, currentThreshold }) => {
  const { selectedAnalysis } = useAnalysis();
  const [commits, setCommits] = useState<CommitAnalysisResult[]>([]);
  const [runs, setRuns] = useState<any[]>([]);
  const [selectedRunId, setSelectedRunId] = useState<string>('');
  const [selectedRunManifest, setSelectedRunManifest] = useState<any>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [uploading, setUploading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);

  // Batch summary state
  const [lastBatchSummary, setLastBatchSummary] = useState<{
    total_uploaded?: number;
    total_processed: number;
    failed_count?: number;
    duplicate_count?: number;
    flagged_count: number;
    standard_count?: number;
    flagged_percentage: number;
    mean_risk_score: number;
    input_format?: string;
    rejected_details?: Array<{ row: number; commit_id?: string; reason: string }>;
  } | null>(null);

  const [showRejectedModal, setShowRejectedModal] = useState<boolean>(false);

  // Drag and drop & file selection state
  const [isDragging, setIsDragging] = useState<boolean>(false);
  const [stagedFile, setStagedFile] = useState<File | null>(null);
  const [showUploadDrawer, setShowUploadDrawer] = useState<boolean>(false);

  // Filters & Search
  const [searchTerm, setSearchTerm] = useState('');
  const [selectedTier, setSelectedTier] = useState<string>('ALL');
  const [selectedDecision, setSelectedDecision] = useState<string>('ALL');
  const [selectedProject, setSelectedProject] = useState<string>('ALL');

  // Sorting & Pagination
  const [sortBy, setSortBy] = useState<'defect_risk_score' | 'churn' | 'entropy' | 'commit_id'>('defect_risk_score');
  const [sortAsc, setSortAsc] = useState<boolean>(false);
  const [currentPage, setCurrentPage] = useState<number>(1);
  const pageSize = 15;

  // Review Budget Optimizer state
  const [budgetK, setBudgetK] = useState<number>(15);
  const [budgetResult, setBudgetResult] = useState<BudgetOptimizationResult | null>(null);
  const [optimizingBudget, setOptimizingBudget] = useState<boolean>(false);
  const [budgetFilterMode, setBudgetFilterMode] = useState<'ALL' | 'SELECTED' | 'EXCLUDED'>('ALL');

  // Inspection modal state
  const [inspectedCommit, setInspectedCommit] = useState<CommitAnalysisResult | null>(null);
  const [copiedSha, setCopiedSha] = useState<boolean>(false);

  // Reviewer feedback action state
  const [submittingFeedbackSha, setSubmittingFeedbackSha] = useState<string | null>(null);
  const [feedbackToast, setFeedbackToast] = useState<string | null>(null);

  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleInlineFeedback = async (commitSha: string, riskScore: number, feedbackType: string) => {
    setSubmittingFeedbackSha(commitSha);
    try {
      await api.submitFeedback({
        commit_sha: commitSha,
        feedback_type: feedbackType,
        risk_score: riskScore,
        notes: `Inline triage feedback`,
      });
      setFeedbackToast(`Recorded feedback for ${commitSha.substring(0, 8)}: ${feedbackType}`);
      setTimeout(() => setFeedbackToast(null), 3500);
    } catch (err: any) {
      alert('Failed to submit feedback: ' + err.message);
    } finally {
      setSubmittingFeedbackSha(null);
    }
  };

  const handleRunBudgetOptimizer = async () => {
    if (commits.length < 2) return;
    setOptimizingBudget(true);
    try {
      const res = await api.optimizeBudget(
        commits,
        budgetK,
        selectedProject === 'ALL' ? undefined : selectedProject
      );
      setBudgetResult(res.budget_optimization);
      setBudgetFilterMode('SELECTED');
      setCurrentPage(1);
    } catch (err: any) {
      alert('Budget optimization failed: ' + err.message);
    } finally {
      setOptimizingBudget(false);
    }
  };

  // Load existing records from latest or selected run
  const fetchQueue = async (targetRunId?: string) => {
    setLoading(true);
    setError(null);
    try {
      const projFilter = selectedAnalysis?.repository_name || selectedAnalysis?.project;
      const availableRuns = await api.getRuns(undefined, true);
      setRuns(availableRuns);

      let runToLoad = targetRunId;
      if (!runToLoad) {
        if (selectedAnalysis?.run_id && availableRuns.some(r => r.run_id === selectedAnalysis.run_id)) {
          runToLoad = selectedAnalysis.run_id;
        } else if (availableRuns.length > 0) {
          const matchingProj = projFilter
            ? availableRuns.find(r => r.input_identifier.toLowerCase().includes(projFilter.toLowerCase()))
            : null;
          runToLoad = matchingProj ? matchingProj.run_id : availableRuns[0].run_id;
        }
      }

      if (runToLoad) {
        setSelectedRunId(runToLoad);
        const details = await api.getRunDetails(runToLoad);
        if (details) {
          setSelectedRunManifest(details.manifest);
          if (details.records && details.records.length > 0) {
            setCommits(details.records);
          } else if (selectedAnalysis && (selectedAnalysis.run_id === runToLoad || !selectedAnalysis.run_id)) {
            setCommits([selectedAnalysis]);
          } else {
            setCommits([]);
          }
        }
      } else if (selectedAnalysis) {
        setSelectedRunId(selectedAnalysis.run_id || 'active_run');
        setSelectedRunManifest(selectedAnalysis.manifest || null);
        setCommits([selectedAnalysis]);
      } else {
        setCommits([]);
        setSelectedRunManifest(null);
      }
    } catch (err: any) {
      setError(err.message || 'Failed to fetch triage queue');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchQueue();
  }, [selectedAnalysis]);

  // Execute batch file upload & analysis
  const executeBatchUpload = async (fileToUpload: File) => {
    setUploading(true);
    setError(null);
    setSuccessMsg(null);

    try {
      const result = await api.analyzeBatchCsv(fileToUpload, currentPolicy, currentThreshold);
      setCommits(result.results);
      setLastBatchSummary({
        total_uploaded: result.total_uploaded ?? result.total_processed,
        total_processed: result.total_processed,
        failed_count: result.failed_count ?? 0,
        duplicate_count: result.duplicate_count ?? 0,
        flagged_count: result.flagged_count,
        standard_count: result.standard_count ?? (result.total_processed - result.flagged_count),
        flagged_percentage: result.flagged_percentage,
        mean_risk_score: result.mean_risk_score,
        input_format: result.input_format,
        rejected_details: result.rejected_details,
      });

      let msg = `Successfully analyzed ${result.total_processed} commits (${result.input_format || 'CSV'}). Flagged: ${result.flagged_count} (${result.flagged_percentage.toFixed(1)}%).`;
      if (result.failed_count && result.failed_count > 0) {
        msg += ` ${result.failed_count} rows rejected due to invalid values.`;
      }
      if (result.duplicate_count && result.duplicate_count > 0) {
        msg += ` ${result.duplicate_count} duplicate commits detected.`;
      }
      setSuccessMsg(msg);
      setStagedFile(null);
      setShowUploadDrawer(false);
      setCurrentPage(1);
      setBudgetResult(null);
      setBudgetFilterMode('ALL');
    } catch (err: any) {
      setError(err.message || 'Batch upload failed. Please verify CSV columns and data types.');
    } finally {
      setUploading(false);
      if (fileInputRef.current) fileInputRef.current.value = '';
    }
  };

  const handleFileInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) {
      setStagedFile(file);
      executeBatchUpload(file);
    }
  };

  // Drag and drop handlers
  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(true);
  };

  const handleDragLeave = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(false);
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(false);

    const files = e.dataTransfer.files;
    if (files && files.length > 0) {
      const file = files[0];
      if (!file.name.toLowerCase().endsWith('.csv')) {
        setError('Only CSV files (.csv) are supported for batch ingestion.');
        return;
      }
      setStagedFile(file);
      executeBatchUpload(file);
    }
  };

  // Export filtered items to CSV
  const handleExportCSV = () => {
    if (filteredCommits.length === 0) return;
    const headers = [
      'commit_id',
      'project',
      'branch',
      'author',
      'subject',
      'defect_risk_score',
      'calibrated_probability',
      'risk_tier',
      'review_decision',
      'flagged_for_review',
      'lines_added',
      'lines_deleted',
      'total_lines_changed',
      'modified_files',
      'modified_directories',
      'modified_subsystems',
      'entropy',
      'la',
      'ld',
      'nf',
      'nd',
      'ns',
      'ent',
      'ndev',
      'age',
      'nuc',
      'aexp',
      'arexp',
      'asexp',
      'recommendation'
    ];
    const rows = filteredCommits.map(c => {
      const la = c.lines_added ?? (c.raw_metrics?.la ?? 0);
      const ld = c.lines_deleted ?? (c.raw_metrics?.ld ?? 0);
      const churn = c.total_lines_changed ?? (la + ld);
      const nf = c.modified_files ?? (c.files_modified ?? (c.raw_metrics?.nf ?? 1));
      const nd = c.modified_directories ?? (c.raw_metrics?.nd ?? 1);
      const ns = c.modified_subsystems ?? (c.raw_metrics?.ns ?? 1);
      const ent = c.entropy ?? (c.raw_metrics?.ent ?? 0.0);
      const score = c.defect_risk_score ?? (c.risk_score ?? (c.model_score ?? 0.0));
      const raw = c.raw_metrics || {};

      return [
        `"${c.commit_id || c.commit_sha || ''}"`,
        `"${c.project || 'Batch'}"`,
        `"${c.branch_name || 'master'}"`,
        `"${(c.author || c.commit_author || 'Batch User').replace(/"/g, '""')}"`,
        `"${(c.subject || c.commit_subject || 'Batch commit').replace(/"/g, '""')}"`,
        score.toFixed(4),
        (c.calibrated_probability ?? score).toFixed(4),
        `"${c.risk_tier || 'Low Risk'}"`,
        `"${c.review_decision || (score >= currentThreshold ? 'FLAGGED' : 'STANDARD')}"`,
        `"${c.flagged_for_review || (score >= currentThreshold ? 'FLAGGED' : 'STANDARD')}"`,
        la,
        ld,
        churn,
        nf,
        nd,
        ns,
        ent,
        raw.la ?? la,
        raw.ld ?? ld,
        raw.nf ?? nf,
        raw.nd ?? nd,
        raw.ns ?? ns,
        raw.ent ?? ent,
        raw.ndev ?? 1.0,
        raw.age ?? 0.0,
        raw.nuc ?? 1.0,
        raw.aexp ?? 1.0,
        raw.arexp ?? 1.0,
        raw.asexp ?? 1.0,
        `"${(c.recommendation || '').replace(/"/g, '""')}"`
      ];
    });

    const csvContent = [headers.join(','), ...rows.map(r => r.join(','))].join('\n');
    const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.setAttribute('href', url);
    link.setAttribute('download', `quality_intelligence_queue_${Date.now()}.csv`);
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  };

  // Copy full SHA to clipboard
  const handleCopySha = (sha: string) => {
    navigator.clipboard.writeText(sha);
    setCopiedSha(true);
    setTimeout(() => setCopiedSha(false), 2000);
  };

  // Unique projects
  const projects = Array.from(new Set(commits.map(c => c.project || 'Unknown'))).sort();

  // Determine commit source based on Budget Filter Mode
  let sourceCommits = commits;
  if (budgetResult && budgetFilterMode === 'SELECTED') {
    sourceCommits = budgetResult.selected_commits;
  } else if (budgetResult && budgetFilterMode === 'EXCLUDED') {
    const selectedShas = new Set(budgetResult.selected_commits.map(c => c.commit_id || c.commit_sha));
    sourceCommits = commits.filter(c => !selectedShas.has(c.commit_id || c.commit_sha));
  }

  // Filter logic
  const filteredCommits = sourceCommits.filter(c => {
    const cScore = c.defect_risk_score !== undefined ? c.defect_risk_score : (c.risk_score ?? (c.model_score ?? 0));
    const isFlagged = c.flagged_for_review === 'FLAGGED' || c.review_decision === 'FLAGGED' || cScore >= currentThreshold;
    const matchesSearch = (c.commit_id || '').toLowerCase().includes(searchTerm.toLowerCase()) || 
                          (c.commit_sha || '').toLowerCase().includes(searchTerm.toLowerCase()) ||
                          (c.author || c.commit_author || '').toLowerCase().includes(searchTerm.toLowerCase()) ||
                          (c.subject || c.commit_subject || '').toLowerCase().includes(searchTerm.toLowerCase()) ||
                          (c.project || '').toLowerCase().includes(searchTerm.toLowerCase());
    const matchesTier = selectedTier === 'ALL' || c.risk_tier === selectedTier;
    const matchesDecision = selectedDecision === 'ALL' || 
                            (selectedDecision === 'FLAGGED' && isFlagged) || 
                            (selectedDecision === 'STANDARD' && !isFlagged);
    const matchesProj = selectedProject === 'ALL' || c.project === selectedProject;
    return matchesSearch && matchesTier && matchesDecision && matchesProj;
  });

  // Sort logic
  const sortedCommits = [...filteredCommits].sort((a, b) => {
    let aVal: number | string = 0;
    let bVal: number | string = 0;
    if (sortBy === 'defect_risk_score') {
      aVal = a.defect_risk_score !== undefined ? a.defect_risk_score : (a.risk_score ?? (a.model_score ?? 0));
      bVal = b.defect_risk_score !== undefined ? b.defect_risk_score : (b.risk_score ?? (b.model_score ?? 0));
    } else if (sortBy === 'churn') {
      aVal = a.total_lines_changed ?? ((a.lines_added || 0) + (a.lines_deleted || 0));
      bVal = b.total_lines_changed ?? ((b.lines_added || 0) + (b.lines_deleted || 0));
    } else if (sortBy === 'entropy') {
      aVal = a.entropy ?? (a.raw_metrics?.ent || 0);
      bVal = b.entropy ?? (b.raw_metrics?.ent || 0);
    } else if (sortBy === 'commit_id') {
      aVal = a.commit_id || a.commit_sha || '';
      bVal = b.commit_id || b.commit_sha || '';
    }
    if (aVal < bVal) return sortAsc ? -1 : 1;
    if (aVal > bVal) return sortAsc ? 1 : -1;
    return 0;
  });

  // Pagination logic
  const totalPages = Math.ceil(sortedCommits.length / pageSize) || 1;
  const paginatedCommits = sortedCommits.slice((currentPage - 1) * pageSize, currentPage * pageSize);

  const totalAnalyzed = commits.length;
  const flaggedCount = commits.filter(c => {
    const sc = c.defect_risk_score ?? (c.risk_score ?? (c.model_score ?? 0));
    return c.flagged_for_review === 'FLAGGED' || c.review_decision === 'FLAGGED' || sc >= currentThreshold;
  }).length;
  const standardCount = totalAnalyzed - flaggedCount;
  const flaggedPct = totalAnalyzed > 0 ? ((flaggedCount / totalAnalyzed) * 100).toFixed(1) : '0.0';
  const meanScore = totalAnalyzed > 0 
    ? (commits.reduce((acc, c) => acc + (c.defect_risk_score ?? c.risk_score ?? c.model_score ?? 0), 0) / totalAnalyzed)
    : 0;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
      {/* Header & Main Ingestion Bar */}
      <div style={{ backgroundColor: '#131b2e', border: '1px solid #1e293b', borderRadius: '10px', padding: '1.5rem', display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '1rem' }}>
        <div>
          <h1 className="qi-title">Review Queue & Batch Ingestion</h1>
          <p className="qi-subtitle">
            Upload commit batch CSVs or triage active repositories under policy <strong>{currentPolicy}</strong> (Active Gate: &ge; {currentThreshold.toFixed(2)}).
          </p>
        </div>
        <div style={{ display: 'flex', gap: '0.75rem', alignItems: 'center', flexWrap: 'wrap' }}>
          <button 
            className="btn-primary" 
            onClick={() => setShowUploadDrawer(!showUploadDrawer)}
            disabled={uploading}
            style={{ display: 'flex', alignItems: 'center', gap: '0.4rem' }}
          >
            <Upload size={16} /> {showUploadDrawer ? 'Hide Upload Zone' : 'Upload CSV Batch'}
          </button>
          <button className="btn-secondary" onClick={handleExportCSV} disabled={filteredCommits.length === 0} style={{ display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
            <Download size={16} /> Export CSV
          </button>
          <button className="btn-secondary" onClick={() => fetchQueue()} title="Refresh Queue">
            <RefreshCw size={16} />
          </button>
        </div>
      </div>

      {/* Professional Drag-and-Drop Ingestion Zone */}
      {showUploadDrawer && (
        <div 
          className="card"
          onDragOver={handleDragOver}
          onDragLeave={handleDragLeave}
          onDrop={handleDrop}
          style={{
            border: isDragging ? '2px dashed #38bdf8' : '1px dashed #334155',
            backgroundColor: isDragging ? 'rgba(56, 189, 248, 0.08)' : '#0b1329',
            padding: '2rem',
            textAlign: 'center',
            transition: 'all 0.2s ease',
          }}
        >
          <input
            type="file"
            ref={fileInputRef}
            style={{ display: 'none' }}
            accept=".csv"
            onChange={handleFileInputChange}
          />

          <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '0.75rem' }}>
            <div style={{ width: '48px', height: '48px', borderRadius: '50%', backgroundColor: 'rgba(56, 189, 248, 0.15)', display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#38bdf8' }}>
              <Upload size={24} />
            </div>
            
            <h3 style={{ margin: 0, fontSize: '1.1rem', color: '#f8fafc' }}>
              Drag & Drop your commit CSV here, or browse files
            </h3>

            <p style={{ margin: 0, fontSize: '0.82rem', color: '#94a3b8', maxWidth: '640px', lineHeight: 1.5 }}>
              Supports both <strong>Format A (12 raw Git metrics)</strong> with automatic feature engineering, and <strong>Format B (26 pre-engineered features)</strong>. Metadata fields (<code>commit_id</code>, <code>project</code>, <code>branch</code>, <code>author</code>, <code>subject</code>) are preserved.
            </p>

            {stagedFile && (
              <div style={{ backgroundColor: '#1e293b', padding: '0.5rem 1rem', borderRadius: '6px', fontSize: '0.85rem', color: '#38bdf8', display: 'flex', alignItems: 'center', gap: '0.5rem', marginTop: '0.5rem' }}>
                <FileText size={16} />
                <span><strong>{stagedFile.name}</strong> ({(stagedFile.size / 1024).toFixed(1)} KB)</span>
              </div>
            )}

            <div style={{ display: 'flex', gap: '0.75rem', marginTop: '0.5rem', flexWrap: 'wrap', justifyContent: 'center' }}>
              <button 
                className="btn-primary" 
                onClick={() => fileInputRef.current?.click()}
                disabled={uploading}
              >
                {uploading ? 'Processing Batch...' : 'Choose File to Analyze'}
              </button>
            </div>

            {/* Template Download Links */}
            <div style={{ marginTop: '1rem', paddingTop: '1rem', borderTop: '1px solid #1e293b', width: '100%', display: 'flex', justifyContent: 'center', gap: '1.5rem', flexWrap: 'wrap', fontSize: '0.78rem', color: '#94a3b8' }}>
              <span>Download Ingestion Templates:</span>
              <a 
                href="/quality_intelligence_raw_metrics_template.csv" 
                download="quality_intelligence_raw_metrics_template.csv"
                style={{ color: '#38bdf8', display: 'flex', alignItems: 'center', gap: '0.3rem', textDecoration: 'none' }}
              >
                <Download size={13} /> Template A: 12 Raw Metrics (.csv)
              </a>
              <span style={{ color: '#475569' }}>|</span>
              <a 
                href="/quality_intelligence_engineered_features_template.csv" 
                download="quality_intelligence_engineered_features_template.csv"
                style={{ color: '#a855f7', display: 'flex', alignItems: 'center', gap: '0.3rem', textDecoration: 'none' }}
              >
                <Download size={13} /> Template B: 26 Engineered Features (.csv)
              </a>
            </div>
          </div>
        </div>
      )}

      {/* Notifications */}
      {error && (
        <div style={{ backgroundColor: 'rgba(239, 68, 68, 0.12)', border: '1px solid #ef4444', borderRadius: '8px', padding: '1rem', color: '#fca5a5', display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', fontWeight: 600 }}>
            <AlertTriangle size={18} color="#ef4444" />
            <span>CSV Ingestion Validation Error</span>
          </div>
          <div style={{ fontSize: '0.85rem', whiteSpace: 'pre-wrap', lineHeight: 1.5, color: '#fecaca' }}>
            {error}
          </div>
        </div>
      )}

      {successMsg && (
        <div style={{ backgroundColor: 'rgba(34, 197, 94, 0.12)', border: '1px solid #22c55e', borderRadius: '8px', padding: '1rem', color: '#86efac', display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '0.5rem' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
            <CheckCircle2 size={18} color="#22c55e" />
            <span style={{ fontSize: '0.9rem' }}>{successMsg}</span>
          </div>
          {lastBatchSummary && lastBatchSummary.failed_count && lastBatchSummary.failed_count > 0 ? (
            <button
              onClick={() => setShowRejectedModal(true)}
              style={{ backgroundColor: 'rgba(239, 68, 68, 0.2)', border: '1px solid #ef4444', color: '#fca5a5', padding: '0.25rem 0.6rem', borderRadius: '4px', fontSize: '0.75rem', cursor: 'pointer' }}
            >
              View {lastBatchSummary.failed_count} Rejected Rows
            </button>
          ) : null}
        </div>
      )}

      {/* Scope and Run Provenance Banner */}
      <div style={{ backgroundColor: '#0f172a', border: '1px solid #1e293b', borderRadius: '8px', padding: '0.85rem 1.25rem', display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '0.75rem' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', flexWrap: 'wrap' }}>
          <span style={{ fontSize: '0.72rem', fontWeight: 700, padding: '0.2rem 0.5rem', borderRadius: '4px', backgroundColor: commits.length === 1 ? 'rgba(56, 189, 248, 0.2)' : commits.length > 1 ? 'rgba(16, 185, 129, 0.2)' : 'rgba(148, 163, 184, 0.2)', color: commits.length === 1 ? '#38bdf8' : commits.length > 1 ? '#34d399' : '#94a3b8' }}>
            {commits.length === 1 ? 'SCOPE: SINGLE COMMIT INSPECTION' : commits.length > 1 ? `SCOPE: MULTI-COMMIT BATCH (${commits.length})` : 'SCOPE: EMPTY QUEUE'}
          </span>
          {selectedRunManifest && (
            <span style={{ fontSize: '0.78rem', color: '#cbd5e1' }}>
              Run: <code style={{ color: '#38bdf8' }}>{selectedRunManifest.run_id}</code> ({selectedRunManifest.schema_status})
            </span>
          )}
        </div>

        {runs.length > 1 && (
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
            <span style={{ fontSize: '0.75rem', color: '#94a3b8' }}>Historical Session:</span>
            <select
              value={selectedRunId}
              onChange={(e) => fetchQueue(e.target.value)}
              style={{ backgroundColor: '#131b2e', color: '#f8fafc', border: '1px solid #334155', borderRadius: '4px', padding: '0.25rem 0.5rem', fontSize: '0.75rem' }}
            >
              {runs.map(r => (
                <option key={r.run_id} value={r.run_id}>
                  {r.input_identifier} ({r.row_count} commits, {r.schema_status})
                </option>
              ))}
            </select>
          </div>
        )}
      </div>

      {commits.length === 1 && (
        <div style={{ backgroundColor: 'rgba(56, 189, 248, 0.08)', border: '1px solid #0284c7', borderRadius: '8px', padding: '0.75rem 1rem', color: '#bae6fd', fontSize: '0.8rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
          <AlertTriangle size={16} color="#38bdf8" />
          <span>
            Single-commit evaluation active. Multi-commit review queue ranking and Review Budget Optimization (top-K) require at least 2 commits. Upload a batch CSV above to perform comparative queue triage.
          </span>
        </div>
      )}

      {/* Batch Summary KPI Strip */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(170px, 1fr))', gap: '0.75rem' }}>
        <div className="card" style={{ padding: '0.9rem' }}>
          <div style={{ fontSize: '0.72rem', color: '#94a3b8', textTransform: 'uppercase' }}>Total Uploaded / Queue</div>
          <div style={{ fontSize: '1.4rem', fontWeight: 700, color: '#f1f5f9', marginTop: '0.2rem' }}>
            {lastBatchSummary?.total_uploaded ?? totalAnalyzed.toLocaleString()}
          </div>
          <div style={{ fontSize: '0.7rem', color: '#64748b' }}>
            {lastBatchSummary?.input_format ? `Format: ${lastBatchSummary.input_format}` : 'Current loaded records'}
          </div>
        </div>

        <div className="card" style={{ padding: '0.9rem' }}>
          <div style={{ fontSize: '0.72rem', color: '#94a3b8', textTransform: 'uppercase' }}>Successfully Analyzed</div>
          <div style={{ fontSize: '1.4rem', fontWeight: 700, color: '#38bdf8', marginTop: '0.2rem' }}>
            {totalAnalyzed.toLocaleString()}
          </div>
          <div style={{ fontSize: '0.7rem', color: '#64748b' }}>Valid model inferences</div>
        </div>

        <div className="card" style={{ padding: '0.9rem' }}>
          <div style={{ fontSize: '0.72rem', color: '#94a3b8', textTransform: 'uppercase' }}>Flagged for Review</div>
          <div style={{ fontSize: '1.4rem', fontWeight: 700, color: '#f59e0b', marginTop: '0.2rem' }}>
            {flaggedCount.toLocaleString()} <span style={{ fontSize: '0.8rem', color: '#94a3b8' }}>({flaggedPct}%)</span>
          </div>
          <div style={{ fontSize: '0.7rem', color: '#64748b' }}>Score &ge; {currentThreshold.toFixed(2)}</div>
        </div>

        <div className="card" style={{ padding: '0.9rem' }}>
          <div style={{ fontSize: '0.72rem', color: '#94a3b8', textTransform: 'uppercase' }}>Standard Decisions</div>
          <div style={{ fontSize: '1.4rem', fontWeight: 700, color: '#10b981', marginTop: '0.2rem' }}>
            {standardCount.toLocaleString()}
          </div>
          <div style={{ fontSize: '0.7rem', color: '#64748b' }}>Standard verification pass</div>
        </div>

        <div className="card" style={{ padding: '0.9rem' }}>
          <div style={{ fontSize: '0.72rem', color: '#94a3b8', textTransform: 'uppercase' }}>Failed / Skipped</div>
          <div style={{ fontSize: '1.4rem', fontWeight: 700, color: (lastBatchSummary?.failed_count ?? 0) > 0 ? '#ef4444' : '#64748b', marginTop: '0.2rem' }}>
            {lastBatchSummary?.failed_count ?? 0}
          </div>
          <div style={{ fontSize: '0.7rem', color: '#64748b' }}>
            {(lastBatchSummary?.duplicate_count ?? 0) > 0 ? `${lastBatchSummary?.duplicate_count} duplicates` : 'No schema errors'}
          </div>
        </div>

        <div className="card" style={{ padding: '0.9rem' }}>
          <div style={{ fontSize: '0.72rem', color: '#94a3b8', textTransform: 'uppercase' }}>Mean Risk Score</div>
          <div style={{ fontSize: '1.4rem', fontWeight: 700, color: '#c084fc', marginTop: '0.2rem' }}>
            {(meanScore * 100).toFixed(1)}%
          </div>
          <div style={{ fontSize: '0.7rem', color: '#64748b' }}>Batch average defect risk</div>
        </div>
      </div>

      {/* Filter & Search Bar */}
      <div className="card" style={{ padding: '1rem', display: 'flex', gap: '1rem', flexWrap: 'wrap', alignItems: 'center' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', flex: '1 1 200px', backgroundColor: '#0f172a', padding: '0.5rem 0.75rem', borderRadius: '6px', border: '1px solid #334155' }}>
          <Search size={16} color="#94a3b8" />
          <input
            type="text"
            placeholder="Search by commit ID, author, or subject..."
            value={searchTerm}
            onChange={(e) => { setSearchTerm(e.target.value); setCurrentPage(1); }}
            style={{ background: 'transparent', border: 'none', color: '#f8fafc', outline: 'none', width: '100%', fontSize: '0.9rem' }}
          />
        </div>

        {/* Project Selector */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
          <span style={{ fontSize: '0.85rem', color: '#94a3b8' }}>Project:</span>
          <select 
            value={selectedProject} 
            onChange={(e) => { setSelectedProject(e.target.value); setCurrentPage(1); }}
            style={{ backgroundColor: '#0f172a', color: '#f8fafc', border: '1px solid #334155', borderRadius: '6px', padding: '0.4rem 0.6rem', fontSize: '0.85rem' }}
          >
            <option value="ALL">All Projects ({projects.length})</option>
            {projects.map(p => <option key={p} value={p}>{p}</option>)}
          </select>
        </div>

        {/* Risk Tier Selector */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
          <span style={{ fontSize: '0.85rem', color: '#94a3b8' }}>Tier:</span>
          <select 
            value={selectedTier} 
            onChange={(e) => { setSelectedTier(e.target.value); setCurrentPage(1); }}
            style={{ backgroundColor: '#0f172a', color: '#f8fafc', border: '1px solid #334155', borderRadius: '6px', padding: '0.4rem 0.6rem', fontSize: '0.85rem' }}
          >
            <option value="ALL">All Tiers</option>
            <option value="Critical Risk">Critical Risk</option>
            <option value="Elevated Risk">Elevated Risk</option>
            <option value="Moderate Risk">Moderate Risk</option>
            <option value="Low Risk">Low Risk</option>
          </select>
        </div>

        {/* Decision Selector */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
          <span style={{ fontSize: '0.85rem', color: '#94a3b8' }}>Decision:</span>
          <select 
            value={selectedDecision} 
            onChange={(e) => { setSelectedDecision(e.target.value); setCurrentPage(1); }}
            style={{ backgroundColor: '#0f172a', color: '#f8fafc', border: '1px solid #334155', borderRadius: '6px', padding: '0.4rem 0.6rem', fontSize: '0.85rem' }}
          >
            <option value="ALL">All Decisions</option>
            <option value="FLAGGED">Flagged Only</option>
            <option value="STANDARD">Standard Only</option>
          </select>
        </div>

        {/* Sort Selector */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
          <span style={{ fontSize: '0.85rem', color: '#94a3b8' }}>Sort:</span>
          <select 
            value={sortBy} 
            onChange={(e: any) => setSortBy(e.target.value)}
            style={{ backgroundColor: '#0f172a', color: '#f8fafc', border: '1px solid #334155', borderRadius: '6px', padding: '0.4rem 0.6rem', fontSize: '0.85rem' }}
          >
            <option value="defect_risk_score">Defect Risk Score</option>
            <option value="churn">Total Churn (LA+LD)</option>
            <option value="entropy">Entropy (ENT)</option>
            <option value="commit_id">Commit SHA</option>
          </select>
          <button 
            onClick={() => setSortAsc(!sortAsc)}
            className="btn-secondary"
            style={{ padding: '0.4rem 0.6rem', fontSize: '0.8rem' }}
            title="Toggle sort direction"
          >
            <ArrowUpDown size={14} /> {sortAsc ? 'Asc' : 'Desc'}
          </button>
        </div>
      </div>

      {/* Review Budget Optimizer Banner */}
      <div className="card" style={{ padding: '1.25rem', borderLeft: '4px solid #a855f7' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '0.75rem', marginBottom: budgetResult ? '1rem' : '0' }}>
          <div>
            <div style={{ fontSize: '0.9rem', fontWeight: 600, color: '#f8fafc', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
              <Sliders size={16} color="#c084fc" /> Review Budget Optimizer & Top-K Triage
            </div>
            <p style={{ fontSize: '0.75rem', color: '#94a3b8', margin: '0.2rem 0 0 0' }}>
              Select highest defect-risk commits within reviewer inspection bandwidth and benchmark against naive churn.
            </p>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
            <span style={{ fontSize: '0.8rem', color: '#cbd5e1' }}>Capacity Budget (K):</span>
            <select
              value={budgetK}
              onChange={(e) => setBudgetK(Number(e.target.value))}
              className="input-field"
              style={{ width: '80px', padding: '0.3rem 0.5rem' }}
            >
              <option value={5}>5</option>
              <option value={10}>10</option>
              <option value={15}>15</option>
              <option value={25}>25</option>
              <option value={50}>50</option>
            </select>
            <button
              className="btn-primary"
              style={{
                padding: '0.4rem 0.75rem',
                fontSize: '0.8rem',
                background: commits.length < 2 ? '#334155' : '#9333ea',
                borderColor: commits.length < 2 ? '#475569' : '#a855f7',
                cursor: commits.length < 2 ? 'not-allowed' : 'pointer',
              }}
              onClick={handleRunBudgetOptimizer}
              disabled={optimizingBudget || commits.length < 2}
              title={commits.length < 2 ? 'Review budget optimization requires at least 2 commits' : 'Run review budget optimization'}
            >
              <Sparkles size={14} /> {optimizingBudget ? 'Optimizing...' : commits.length < 2 ? 'Optimize Budget (Requires ≥ 2)' : 'Optimize Budget'}
            </button>
            {budgetResult && (
              <div style={{ display: 'flex', gap: '0.3rem', marginLeft: '0.5rem' }}>
                <button
                  className={budgetFilterMode === 'SELECTED' ? 'btn-primary' : 'btn-secondary'}
                  style={{ padding: '0.35rem 0.65rem', fontSize: '0.75rem' }}
                  onClick={() => setBudgetFilterMode('SELECTED')}
                >
                  Selected ({budgetResult.selected_commits.length})
                </button>
                <button
                  className={budgetFilterMode === 'EXCLUDED' ? 'btn-primary' : 'btn-secondary'}
                  style={{ padding: '0.35rem 0.65rem', fontSize: '0.75rem' }}
                  onClick={() => setBudgetFilterMode('EXCLUDED')}
                >
                  Excluded ({budgetResult.excluded_count})
                </button>
                <button
                  className={budgetFilterMode === 'ALL' ? 'btn-primary' : 'btn-secondary'}
                  style={{ padding: '0.35rem 0.65rem', fontSize: '0.75rem' }}
                  onClick={() => setBudgetFilterMode('ALL')}
                >
                  Full Queue ({commits.length})
                </button>
              </div>
            )}
          </div>
        </div>

        {budgetResult && (
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: '0.75rem', marginTop: '0.75rem', paddingTop: '0.75rem', borderTop: '1px solid #334155' }}>
            <div style={{ background: '#0f172a', padding: '0.75rem', borderRadius: '6px' }}>
              <div style={{ fontSize: '0.7rem', color: '#94a3b8' }}>SELECTED TOP-K</div>
              <div style={{ fontSize: '1.2rem', fontWeight: 700, color: '#c084fc' }}>
                {budgetResult.selected_commits.length} of {budgetResult.total_candidates}
              </div>
              <div style={{ fontSize: '0.7rem', color: '#64748b' }}>
                Capacity limit: K={budgetResult.budget_k}
              </div>
            </div>
            <div style={{ background: '#0f172a', padding: '0.75rem', borderRadius: '6px' }}>
              <div style={{ fontSize: '0.7rem', color: '#94a3b8' }}>WORKLOAD BYPASSED</div>
              <div style={{ fontSize: '1.2rem', fontWeight: 700, color: '#34d399' }}>
                {budgetResult.workload_bypassed_pct.toFixed(1)}%
              </div>
              <div style={{ fontSize: '0.7rem', color: '#64748b' }}>
                {budgetResult.excluded_count} commits deprioritized
              </div>
            </div>
            <div style={{ background: '#0f172a', padding: '0.75rem', borderRadius: '6px' }}>
              <div style={{ fontSize: '0.7rem', color: '#94a3b8' }}>CHURN BASELINE OVERLAP</div>
              <div style={{ fontSize: '1.2rem', fontWeight: 700, color: '#38bdf8' }}>
                {budgetResult.churn_baseline_overlap_pct.toFixed(1)}%
              </div>
              <div style={{ fontSize: '0.7rem', color: '#64748b' }}>
                Agreement with naive LOC lines
              </div>
            </div>
            <div style={{ background: '#0f172a', padding: '0.75rem', borderRadius: '6px' }}>
              <div style={{ fontSize: '0.7rem', color: '#94a3b8' }}>MODEL DISCOVERY DELTA</div>
              <div style={{ fontSize: '1.2rem', fontWeight: 700, color: '#fbbf24' }}>
                {budgetResult.model_unique_catches_count} Commits
              </div>
              <div style={{ fontSize: '0.7rem', color: '#64748b' }}>
                Prioritized over naive churn
              </div>
            </div>
          </div>
        )}
      </div>

      {feedbackToast && (
        <div style={{ backgroundColor: 'rgba(52, 211, 153, 0.15)', border: '1px solid #10b981', borderRadius: '8px', padding: '0.75rem 1rem', color: '#34d399', display: 'flex', alignItems: 'center', gap: '0.5rem', fontSize: '0.85rem' }}>
          <CheckCircle2 size={16} />
          <span>{feedbackToast}</span>
        </div>
      )}

      {/* Main Commits Table */}
      <div className="card" style={{ padding: '0', overflowX: 'auto' }}>
        <table className="qi-table">
          <thead>
            <tr>
              <th>Commit</th>
              <th>Author</th>
              <th>Subject</th>
              <th>Risk Score</th>
              <th>Risk Tier</th>
              <th>Decision</th>
              <th>Status</th>
              <th>Action</th>
            </tr>
          </thead>
          <tbody>
            {paginatedCommits.length === 0 ? (
              <tr>
                <td colSpan={8} style={{ textAlign: 'center', padding: '3rem', color: '#64748b' }}>
                  {loading ? 'Loading triage queue...' : 'No commits found matching the current filters.'}
                </td>
              </tr>
            ) : (
              paginatedCommits.map((c) => {
                const la = c.lines_added !== undefined ? c.lines_added : (c.raw_metrics?.la ?? 0);
                const ld = c.lines_deleted !== undefined ? c.lines_deleted : (c.raw_metrics?.ld ?? 0);
                const churn = c.total_lines_changed !== undefined ? c.total_lines_changed : (la + ld);
                const files = c.modified_files !== undefined ? c.modified_files : (c.files_modified ?? (c.raw_metrics?.nf ?? 1));
                const ent = c.entropy !== undefined ? c.entropy : (c.raw_metrics?.ent ?? 0.0);
                const score = c.defect_risk_score !== undefined ? c.defect_risk_score : (c.risk_score ?? (c.model_score ?? 0.0));
                const isFlagged = c.flagged_for_review === 'FLAGGED' || c.review_decision === 'FLAGGED' || score >= currentThreshold;
                const isActive = selectedAnalysis && (
                  c.commit_id === selectedAnalysis.commit_id ||
                  c.commit_id === selectedAnalysis.commit_sha ||
                  c.commit_sha === selectedAnalysis.commit_sha ||
                  (selectedAnalysis.commit_sha && c.commit_id?.startsWith(selectedAnalysis.commit_sha.substring(0, 8)))
                );
                const authorDisplay = c.author || c.commit_author || c.author_name || 'Batch User';
                const subjectDisplay = c.subject || c.commit_subject || c.notes || 'Batch commit';
                const shortSha = c.commit_short_sha || (c.commit_id ? c.commit_id.substring(0, 8) : 'unknown');

                return (
                  <tr
                    key={c.commit_id || c.commit_sha}
                    style={{
                      backgroundColor: isActive ? 'rgba(56, 189, 248, 0.05)' : undefined,
                      borderLeft: isActive ? '3px solid #38bdf8' : undefined,
                    }}
                  >
                    {/* Commit */}
                    <td>
                      <div style={{ display: 'flex', flexDirection: 'column', gap: '0.2rem' }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
                          <code style={{ color: '#38bdf8', fontSize: '0.85rem', background: '#0f172a', padding: '0.2rem 0.4rem', borderRadius: '4px' }}>
                            {shortSha}
                          </code>
                          {isActive && (
                            <span style={{ fontSize: '0.65rem', backgroundColor: 'rgba(56, 189, 248, 0.25)', color: '#38bdf8', padding: '0.1rem 0.35rem', borderRadius: '3px', fontWeight: 700 }}>
                              ACTIVE
                            </span>
                          )}
                        </div>
                        <span style={{ fontSize: '0.72rem', color: '#64748b' }}>
                          {c.project || 'Batch'} {c.branch_name ? `(${c.branch_name})` : ''}
                        </span>
                      </div>
                    </td>

                    {/* Author */}
                    <td>
                      <span style={{ fontSize: '0.85rem', color: '#f1f5f9' }}>
                        {authorDisplay.split('<')[0].trim()}
                      </span>
                    </td>

                    {/* Subject */}
                    <td>
                      <div style={{ fontSize: '0.83rem', color: '#cbd5e1', maxWidth: '280px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }} title={subjectDisplay}>
                        {subjectDisplay}
                      </div>
                    </td>

                    {/* Risk Score */}
                    <td>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                        <div style={{ width: '50px', height: '6px', background: '#334155', borderRadius: '3px', overflow: 'hidden' }}>
                          <div
                            style={{
                              width: `${Math.min(100, score * 100)}%`,
                              height: '100%',
                              backgroundColor: score >= currentThreshold ? '#ef4444' : '#10b981'
                            }}
                          />
                        </div>
                        <span style={{ fontFamily: 'monospace', fontWeight: 600 }}>
                          {(score * 100).toFixed(1)}%
                        </span>
                      </div>
                    </td>

                    {/* Risk Tier */}
                    <td>
                      <RiskBadge tier={c.risk_tier} />
                    </td>

                    {/* Decision */}
                    <td>
                      {isFlagged ? (
                        <span style={{ backgroundColor: 'rgba(245, 158, 11, 0.15)', color: '#f59e0b', border: '1px solid #f59e0b', padding: '0.2rem 0.5rem', borderRadius: '4px', fontWeight: 600, fontSize: '0.75rem' }}>
                          FLAGGED
                        </span>
                      ) : (
                        <span style={{ backgroundColor: 'rgba(16, 185, 129, 0.15)', color: '#34d399', border: '1px solid #10b981', padding: '0.2rem 0.5rem', borderRadius: '4px', fontWeight: 600, fontSize: '0.75rem' }}>
                          STANDARD
                        </span>
                      )}
                    </td>

                    {/* Status */}
                    <td>
                      <div style={{ display: 'flex', flexDirection: 'column', gap: '0.1rem', fontSize: '0.78rem' }}>
                        <div>
                          <span style={{ color: '#22c55e' }}>+{la}</span>
                          <span style={{ color: '#64748b', margin: '0 0.15rem' }}>/</span>
                          <span style={{ color: '#ef4444' }}>-{ld}</span>
                        </div>
                        <span style={{ color: '#94a3b8' }}>{files} files (H={Number(ent).toFixed(2)})</span>
                      </div>
                    </td>

                    {/* Action */}
                    <td>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '0.35rem' }}>
                        <button
                          className="btn-secondary"
                          style={{ padding: '0.25rem 0.5rem', fontSize: '0.75rem', display: 'flex', alignItems: 'center', gap: '0.25rem' }}
                          onClick={() => setInspectedCommit(c)}
                          title="Inspect complete commit metrics and details"
                        >
                          <Eye size={13} /> Inspect
                        </button>
                        <button
                          style={{ background: '#0f172a', border: '1px solid #334155', borderRadius: '4px', padding: '0.25rem 0.4rem', cursor: 'pointer' }}
                          title="Feedback: Helpful Target"
                          onClick={() => handleInlineFeedback(c.commit_id || c.commit_sha || '', score, 'HELPFUL_FLAG')}
                          disabled={submittingFeedbackSha === (c.commit_id || c.commit_sha)}
                        >
                          <ThumbsUp size={12} color="#34d399" />
                        </button>
                        <button
                          style={{ background: '#0f172a', border: '1px solid #334155', borderRadius: '4px', padding: '0.25rem 0.4rem', cursor: 'pointer' }}
                          title="Feedback: False Alarm"
                          onClick={() => handleInlineFeedback(c.commit_id || c.commit_sha || '', score, 'FALSE_ALARM')}
                          disabled={submittingFeedbackSha === (c.commit_id || c.commit_sha)}
                        >
                          <ThumbsDown size={12} color="#f59e0b" />
                        </button>
                      </div>
                    </td>
                  </tr>
                );
              })
            )}
          </tbody>
        </table>
      </div>

      {/* Pagination Footer */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '0.5rem 0.25rem' }}>
        <div style={{ fontSize: '0.85rem', color: '#94a3b8' }}>
          Showing {paginatedCommits.length > 0 ? (currentPage - 1) * pageSize + 1 : 0} to{' '}
          {Math.min(currentPage * pageSize, sortedCommits.length)} of {sortedCommits.length} commits
        </div>
        <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center' }}>
          <button 
            className="btn-secondary" 
            onClick={() => setCurrentPage(p => Math.max(1, p - 1))}
            disabled={currentPage === 1}
            style={{ padding: '0.4rem 0.75rem' }}
          >
            <ChevronLeft size={16} /> Prev
          </button>
          <span style={{ fontSize: '0.85rem', color: '#cbd5e1', padding: '0 0.5rem' }}>
            Page {currentPage} of {totalPages}
          </span>
          <button 
            className="btn-secondary" 
            onClick={() => setCurrentPage(p => Math.min(totalPages, p + 1))}
            disabled={currentPage === totalPages}
            style={{ padding: '0.4rem 0.75rem' }}
          >
            Next <ChevronRight size={16} />
          </button>
        </div>
      </div>

      {/* Commit Detail Inspection Modal */}
      {inspectedCommit && (
        <div style={{ position: 'fixed', top: 0, left: 0, right: 0, bottom: 0, backgroundColor: 'rgba(0,0,0,0.75)', display: 'flex', justifyContent: 'center', alignItems: 'center', zIndex: 1000, padding: '1.5rem' }}>
          <div className="card" style={{ maxWidth: '780px', width: '100%', maxHeight: '90vh', overflowY: 'auto', padding: '1.75rem', position: 'relative' }}>
            <button
              onClick={() => setInspectedCommit(null)}
              style={{ position: 'absolute', top: '1.25rem', right: '1.25rem', background: 'transparent', border: 'none', color: '#94a3b8', cursor: 'pointer' }}
            >
              <X size={20} />
            </button>

            <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.5rem' }}>
              <GitCommit size={20} color="#38bdf8" />
              <h2 style={{ margin: 0, fontSize: '1.25rem', color: '#f8fafc' }}>
                Commit Inspection Details
              </h2>
            </div>

            <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '1.25rem' }}>
              <code style={{ fontSize: '0.85rem', color: '#38bdf8', background: '#0f172a', padding: '0.25rem 0.5rem', borderRadius: '4px' }}>
                {inspectedCommit.commit_id || inspectedCommit.commit_sha}
              </code>
              <button
                className="btn-secondary"
                style={{ padding: '0.2rem 0.5rem', fontSize: '0.75rem', display: 'flex', alignItems: 'center', gap: '0.25rem' }}
                onClick={() => handleCopySha(inspectedCommit.commit_id || inspectedCommit.commit_sha || '')}
              >
                {copiedSha ? <Check size={12} color="#10b981" /> : <Copy size={12} />}
                {copiedSha ? 'Copied' : 'Copy SHA'}
              </button>
            </div>

            {/* Quick Metadata Grid */}
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '0.75rem', marginBottom: '1.25rem', background: '#0f172a', padding: '1rem', borderRadius: '8px' }}>
              <div>
                <div style={{ fontSize: '0.7rem', color: '#94a3b8' }}>AUTHOR</div>
                <div style={{ fontSize: '0.85rem', color: '#f1f5f9', fontWeight: 500 }}>
                  {inspectedCommit.author || inspectedCommit.commit_author || 'Batch User'}
                </div>
              </div>
              <div>
                <div style={{ fontSize: '0.7rem', color: '#94a3b8' }}>PROJECT & BRANCH</div>
                <div style={{ fontSize: '0.85rem', color: '#f1f5f9', fontWeight: 500 }}>
                  {inspectedCommit.project || 'Batch'} ({inspectedCommit.branch_name || 'master'})
                </div>
              </div>
              <div>
                <div style={{ fontSize: '0.7rem', color: '#94a3b8' }}>RISK SCORE & TIER</div>
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', marginTop: '0.2rem' }}>
                  <span style={{ fontSize: '1rem', fontWeight: 700, color: '#f8fafc' }}>
                    {((inspectedCommit.defect_risk_score ?? inspectedCommit.risk_score ?? 0) * 100).toFixed(1)}%
                  </span>
                  <RiskBadge tier={inspectedCommit.risk_tier} />
                </div>
              </div>
              <div>
                <div style={{ fontSize: '0.7rem', color: '#94a3b8' }}>DECISION GATE</div>
                <div style={{ fontSize: '0.85rem', fontWeight: 600, color: (inspectedCommit.defect_risk_score ?? 0) >= currentThreshold ? '#f59e0b' : '#34d399', marginTop: '0.2rem' }}>
                  {(inspectedCommit.defect_risk_score ?? 0) >= currentThreshold ? 'FLAGGED FOR PEER REVIEW' : 'STANDARD PASS'}
                </div>
              </div>
            </div>

            {/* Subject */}
            <div style={{ marginBottom: '1.25rem' }}>
              <div style={{ fontSize: '0.75rem', color: '#94a3b8', marginBottom: '0.25rem' }}>COMMIT SUBJECT</div>
              <div style={{ fontSize: '0.9rem', color: '#f1f5f9', background: '#1e293b', padding: '0.6rem 0.85rem', borderRadius: '6px' }}>
                {inspectedCommit.subject || inspectedCommit.commit_subject || 'Batch commit'}
              </div>
            </div>

            {/* 12 Raw Metrics Grid */}
            <div style={{ marginBottom: '1.25rem' }}>
              <div style={{ fontSize: '0.75rem', color: '#94a3b8', marginBottom: '0.5rem', fontWeight: 600 }}>
                12 RAW GIT CHANGE METRICS
              </div>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '0.5rem', fontSize: '0.8rem' }}>
                <div style={{ background: '#0f172a', padding: '0.5rem', borderRadius: '4px' }}>
                  <span style={{ color: '#64748b' }}>Lines Added (la):</span> <strong>{inspectedCommit.lines_added ?? inspectedCommit.raw_metrics?.la ?? 0}</strong>
                </div>
                <div style={{ background: '#0f172a', padding: '0.5rem', borderRadius: '4px' }}>
                  <span style={{ color: '#64748b' }}>Lines Deleted (ld):</span> <strong>{inspectedCommit.lines_deleted ?? inspectedCommit.raw_metrics?.ld ?? 0}</strong>
                </div>
                <div style={{ background: '#0f172a', padding: '0.5rem', borderRadius: '4px' }}>
                  <span style={{ color: '#64748b' }}>Files (nf):</span> <strong>{inspectedCommit.modified_files ?? inspectedCommit.raw_metrics?.nf ?? 1}</strong>
                </div>
                <div style={{ background: '#0f172a', padding: '0.5rem', borderRadius: '4px' }}>
                  <span style={{ color: '#64748b' }}>Directories (nd):</span> <strong>{inspectedCommit.modified_directories ?? inspectedCommit.raw_metrics?.nd ?? 1}</strong>
                </div>
                <div style={{ background: '#0f172a', padding: '0.5rem', borderRadius: '4px' }}>
                  <span style={{ color: '#64748b' }}>Subsystems (ns):</span> <strong>{inspectedCommit.modified_subsystems ?? inspectedCommit.raw_metrics?.ns ?? 1}</strong>
                </div>
                <div style={{ background: '#0f172a', padding: '0.5rem', borderRadius: '4px' }}>
                  <span style={{ color: '#64748b' }}>Entropy (ent):</span> <strong>{Number(inspectedCommit.entropy ?? inspectedCommit.raw_metrics?.ent ?? 0).toFixed(2)}</strong>
                </div>
                <div style={{ background: '#0f172a', padding: '0.5rem', borderRadius: '4px' }}>
                  <span style={{ color: '#64748b' }}>Developers (ndev):</span> <strong>{inspectedCommit.raw_metrics?.ndev ?? 1}</strong>
                </div>
                <div style={{ background: '#0f172a', padding: '0.5rem', borderRadius: '4px' }}>
                  <span style={{ color: '#64748b' }}>File Age (age):</span> <strong>{inspectedCommit.file_age_days ?? inspectedCommit.raw_metrics?.age ?? 0}d</strong>
                </div>
                <div style={{ background: '#0f172a', padding: '0.5rem', borderRadius: '4px' }}>
                  <span style={{ color: '#64748b' }}>Prior Changes (nuc):</span> <strong>{inspectedCommit.raw_metrics?.nuc ?? 1}</strong>
                </div>
                <div style={{ background: '#0f172a', padding: '0.5rem', borderRadius: '4px' }}>
                  <span style={{ color: '#64748b' }}>Total Exp (aexp):</span> <strong>{inspectedCommit.raw_metrics?.aexp ?? 1}</strong>
                </div>
                <div style={{ background: '#0f172a', padding: '0.5rem', borderRadius: '4px' }}>
                  <span style={{ color: '#64748b' }}>Recent Exp (arexp):</span> <strong>{inspectedCommit.raw_metrics?.arexp ?? 1}</strong>
                </div>
                <div style={{ background: '#0f172a', padding: '0.5rem', borderRadius: '4px' }}>
                  <span style={{ color: '#64748b' }}>Subsys Exp (asexp):</span> <strong>{inspectedCommit.subsystem_exp ?? inspectedCommit.raw_metrics?.asexp ?? 1}</strong>
                </div>
              </div>
            </div>

            {/* Recommendation */}
            <div style={{ background: 'rgba(56, 189, 248, 0.08)', border: '1px solid #0284c7', borderRadius: '6px', padding: '0.75rem 1rem', fontSize: '0.85rem', color: '#bae6fd', marginBottom: '1.25rem' }}>
              <strong>Triage Recommendation:</strong> {inspectedCommit.recommendation || ((inspectedCommit.defect_risk_score ?? 0) >= currentThreshold ? 'Secondary peer review required before merge.' : 'Standard automated verification workflow.')}
            </div>

            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '0.75rem' }}>
              <button className="btn-secondary" onClick={() => setInspectedCommit(null)}>
                Close
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Row-Level Errors Modal */}
      {showRejectedModal && lastBatchSummary?.rejected_details && (
        <div style={{ position: 'fixed', top: 0, left: 0, right: 0, bottom: 0, backgroundColor: 'rgba(0,0,0,0.75)', display: 'flex', justifyContent: 'center', alignItems: 'center', zIndex: 1000, padding: '1.5rem' }}>
          <div className="card" style={{ maxWidth: '640px', width: '100%', maxHeight: '80vh', overflowY: 'auto', padding: '1.75rem', position: 'relative' }}>
            <button
              onClick={() => setShowRejectedModal(false)}
              style={{ position: 'absolute', top: '1.25rem', right: '1.25rem', background: 'transparent', border: 'none', color: '#94a3b8', cursor: 'pointer' }}
            >
              <X size={20} />
            </button>

            <h3 style={{ margin: '0 0 1rem 0', color: '#f8fafc', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
              <AlertTriangle size={18} color="#ef4444" /> Rejected CSV Rows ({lastBatchSummary.rejected_details.length})
            </h3>

            <p style={{ fontSize: '0.82rem', color: '#94a3b8', marginBottom: '1rem' }}>
              The following rows could not be parsed as valid numeric metrics and were skipped to protect model inference integrity:
            </p>

            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
              {lastBatchSummary.rejected_details.map((rej, i) => (
                <div key={i} style={{ backgroundColor: '#0f172a', border: '1px solid #334155', borderRadius: '6px', padding: '0.65rem 0.85rem', fontSize: '0.8rem' }}>
                  <div style={{ color: '#ef4444', fontWeight: 600 }}>Row {rej.row} ({rej.commit_id}):</div>
                  <div style={{ color: '#cbd5e1', marginTop: '0.2rem' }}>{rej.reason}</div>
                </div>
              ))}
            </div>

            <div style={{ display: 'flex', justifyContent: 'flex-end', marginTop: '1.25rem' }}>
              <button className="btn-secondary" onClick={() => setShowRejectedModal(false)}>
                Close
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

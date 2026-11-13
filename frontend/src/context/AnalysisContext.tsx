// frontend/src/context/AnalysisContext.tsx - Canonical Shared Analysis Context

import React, { createContext, useContext, useState, useRef, useCallback, useEffect } from 'react';
import { api } from '../api/client';
import {
  CommitAnalysisResult,
  ConnectRepositoryResponse,
  BranchInfo,
  CommitItem,
  BranchBatchAnalysisResponse,
} from '../api/types';

export type AnalysisSourceType =
  | 'REAL_GIT_COMMIT'
  | 'REAL_GIT_BRANCH'
  | 'REAL_GIT_BATCH'
  | 'SYNTHETIC_DEMO'
  | 'HISTORICAL_APACHEJIT'
  | 'NONE';

export interface AnalysisContextType {
  selectedAnalysis: CommitAnalysisResult | null;
  analysisSource: AnalysisSourceType;
  repositoryPath: string;
  commitRef: string;
  connectedRepo: ConnectRepositoryResponse | null;
  branches: BranchInfo[];
  commits: CommitItem[];
  selectedBranch: string;
  isConnecting: boolean;
  isAnalyzing: boolean;
  analysisError: string | null;
  lastAnalysisTimestamp: string | null;
  lastRealAnalysis: CommitAnalysisResult | null;
  latestBatchResult: BranchBatchAnalysisResponse | null;

  // Actions
  connectRepository: (pathOrUrl: string) => Promise<ConnectRepositoryResponse>;
  selectBranch: (branchName: string) => Promise<void>;
  analyzeGitCommit: (
    repoPath: string,
    commitRef: string,
    policyName?: string,
    threshold?: number,
    branchName?: string
  ) => Promise<CommitAnalysisResult>;
  analyzeGitBranch: (
    repoPath: string,
    branchName?: string,
    maxCommits?: number,
    policyName?: string,
    threshold?: number
  ) => Promise<BranchBatchAnalysisResponse>;
  selectHistoricalRun: (runId: string) => Promise<CommitAnalysisResult | null>;
  loadSyntheticDemo: (
    presetKey: string,
    presetLabel: string,
    metrics: any,
    policyName?: string,
    threshold?: number
  ) => Promise<CommitAnalysisResult>;
  exitDemoMode: () => boolean;
  clearAnalysis: () => void;
  restoreLatestRealAnalysis: () => Promise<boolean>;
}

const AnalysisContext = createContext<AnalysisContextType | undefined>(undefined);

const STORAGE_KEY = 'qi_last_analysis_context';
const REAL_CACHE_KEY = 'qi_last_real_analysis';
const REPO_STORAGE_KEY = 'qi_last_connected_repo';

export const AnalysisProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [selectedAnalysis, setSelectedAnalysis] = useState<CommitAnalysisResult | null>(null);
  const [analysisSource, setAnalysisSource] = useState<AnalysisSourceType>('NONE');
  const [repositoryPath, setRepositoryPath] = useState<string>('');
  const [commitRef, setCommitRef] = useState<string>('HEAD');
  const [connectedRepo, setConnectedRepo] = useState<ConnectRepositoryResponse | null>(null);
  const [branches, setBranches] = useState<BranchInfo[]>([]);
  const [commits, setCommits] = useState<CommitItem[]>([]);
  const [selectedBranch, setSelectedBranch] = useState<string>('HEAD');
  const [isConnecting, setIsConnecting] = useState<boolean>(false);
  const [isAnalyzing, setIsAnalyzing] = useState<boolean>(false);
  const [analysisError, setAnalysisError] = useState<string | null>(null);
  const [lastAnalysisTimestamp, setLastAnalysisTimestamp] = useState<string | null>(null);
  const [lastRealAnalysis, setLastRealAnalysis] = useState<CommitAnalysisResult | null>(null);
  const [latestBatchResult, setLatestBatchResult] = useState<BranchBatchAnalysisResponse | null>(null);

  const currentRequestIdRef = useRef<number>(0);

  // Sync to local/session storage safely
  const persistAnalysis = useCallback((
    analysis: CommitAnalysisResult | null,
    source: AnalysisSourceType,
    repo: string,
    ref: string
  ) => {
    try {
      if (analysis) {
        const payload = JSON.stringify({
          selectedAnalysis: analysis,
          analysisSource: source,
          repositoryPath: repo,
          commitRef: ref,
          timestamp: new Date().toISOString(),
        });
        sessionStorage.setItem(STORAGE_KEY, payload);
        localStorage.setItem(STORAGE_KEY, payload);

        if (source === 'REAL_GIT_COMMIT' || source === 'REAL_GIT_BRANCH' || source === 'REAL_GIT_BATCH') {
          sessionStorage.setItem(REAL_CACHE_KEY, JSON.stringify(analysis));
          localStorage.setItem(REAL_CACHE_KEY, JSON.stringify(analysis));
          setLastRealAnalysis(analysis);
        }

        // Notify backend of authoritative active selection
        api.setActiveAnalysis(analysis).catch(() => {});
      } else {
        sessionStorage.removeItem(STORAGE_KEY);
        localStorage.removeItem(STORAGE_KEY);
        api.clearActiveAnalysis().catch(() => {});
      }
    } catch {
      // Storage unavailable or quota exceeded
    }
  }, []);

  // Initial mount hydration: try backend active analysis first, then storage
  useEffect(() => {
    let isMounted = true;

    async function hydrate() {
      // 1. Try backend
      try {
        const backendActive = await api.getActiveAnalysis();
        if (isMounted && backendActive && backendActive.data && backendActive.status === 'ACTIVE_ANALYSIS_AVAILABLE') {
          const act = backendActive.data;
          const src = (act.source_type || act.analysis_source || 'REAL_GIT_COMMIT') as AnalysisSourceType;
          setSelectedAnalysis(act);
          setAnalysisSource(src);
          setRepositoryPath(act.repository_path || '');
          setCommitRef(act.commit_sha || act.commit_id || 'HEAD');
          setSelectedBranch(act.branch_name || 'HEAD');
          setLastAnalysisTimestamp(act.analysis_timestamp || new Date().toISOString());
          if (src === 'REAL_GIT_COMMIT' || src === 'REAL_GIT_BRANCH') {
            setLastRealAnalysis(act);
          }
          return;
        }
      } catch {
        // Backend offline or endpoint error; proceed to local storage
      }

      // 2. Try session / local storage
      try {
        const raw = sessionStorage.getItem(STORAGE_KEY) || localStorage.getItem(STORAGE_KEY);
        if (raw && isMounted) {
          const parsed = JSON.parse(raw);
          if (parsed && parsed.selectedAnalysis) {
            setSelectedAnalysis(parsed.selectedAnalysis);
            setAnalysisSource(parsed.analysisSource || 'REAL_GIT_COMMIT');
            setRepositoryPath(parsed.repositoryPath || '');
            setCommitRef(parsed.commitRef || 'HEAD');
            setLastAnalysisTimestamp(parsed.timestamp || null);
          }
        }
        const realRaw = sessionStorage.getItem(REAL_CACHE_KEY) || localStorage.getItem(REAL_CACHE_KEY);
        if (realRaw && isMounted) {
          setLastRealAnalysis(JSON.parse(realRaw));
        }
        const savedRepo = sessionStorage.getItem(REPO_STORAGE_KEY) || localStorage.getItem(REPO_STORAGE_KEY);
        if (savedRepo && isMounted) {
          setConnectedRepo(JSON.parse(savedRepo));
        }
      } catch {
        // Storage parse error
      }
    }

    hydrate();
    return () => {
      isMounted = false;
    };
  }, []);

  const connectRepository = useCallback(async (pathOrUrl: string): Promise<ConnectRepositoryResponse> => {
    setIsConnecting(true);
    setAnalysisError(null);
    try {
      const repo = await api.connectRepository(pathOrUrl.trim());
      setConnectedRepo(repo);
      setRepositoryPath(repo.repository_path);
      setSelectedBranch(repo.default_branch || repo.current_branch || 'HEAD');

      try {
        sessionStorage.setItem(REPO_STORAGE_KEY, JSON.stringify(repo));
        localStorage.setItem(REPO_STORAGE_KEY, JSON.stringify(repo));
      } catch {}

      // Fetch branches and recent commits
      try {
        const branchList = await api.getRepositoryBranches(repo.repository_path);
        setBranches(branchList);
        const commitList = await api.getRepositoryCommits(repo.repository_path, repo.default_branch || 'HEAD', 30);
        setCommits(commitList);
      } catch (err: any) {
        console.warn('Could not auto-list branches/commits:', err);
      }

      return repo;
    } catch (err: any) {
      const msg = err.message || 'Failed to connect repository. Verify path exists and contains a valid Git repository.';
      setAnalysisError(msg);
      throw err;
    } finally {
      setIsConnecting(false);
    }
  }, []);

  const selectBranch = useCallback(async (branchName: string): Promise<void> => {
    setSelectedBranch(branchName);
    if (!repositoryPath) return;
    try {
      const commitList = await api.getRepositoryCommits(repositoryPath, branchName, 30);
      setCommits(commitList);
    } catch (err: any) {
      console.warn(`Could not list commits on branch ${branchName}:`, err);
    }
  }, [repositoryPath]);

  const clearAnalysis = useCallback(() => {
    currentRequestIdRef.current += 1;
    setSelectedAnalysis(null);
    setAnalysisSource('NONE');
    setAnalysisError(null);
    setIsAnalyzing(false);
    persistAnalysis(null, 'NONE', '', 'HEAD');
  }, [persistAnalysis]);

  const analyzeGitCommit = useCallback(async (
    repoPath: string,
    targetCommitRef: string,
    policyName = 'Balanced Policy (Default)',
    threshold = 0.50,
    branchName?: string
  ): Promise<CommitAnalysisResult> => {
    const requestId = ++currentRequestIdRef.current;
    setIsAnalyzing(true);
    setAnalysisError(null);
    setRepositoryPath(repoPath);
    setCommitRef(targetCommitRef);

    try {
      const activeBranch = branchName || selectedBranch;
      const res = await api.analyzeGitCommit(
        repoPath.trim(),
        targetCommitRef.trim() || 'HEAD',
        policyName,
        threshold,
        activeBranch && activeBranch !== 'HEAD' ? activeBranch : undefined
      );

      if (requestId !== currentRequestIdRef.current) {
        return res;
      }

      const authoritative: CommitAnalysisResult = {
        ...res,
        analysis_source: 'REAL_GIT_COMMIT',
        source_type: 'REAL_GIT_COMMIT',
        data_scope: 'REAL_GIT_COMMIT',
        repository_path: repoPath,
        commit_sha: res.commit_sha || res.commit_id,
        commit_short_sha: (res.commit_sha || res.commit_id).substring(0, 8),
        branch_name: res.branch_name || activeBranch || 'HEAD',
        display_branch_name: res.display_branch_name || activeBranch || 'HEAD',
        policy_name: policyName,
        threshold: threshold,
      };

      setSelectedAnalysis(authoritative);
      if (res.branch_name && res.branch_name !== 'HEAD') {
        setSelectedBranch(res.branch_name);
      }
      setAnalysisSource('REAL_GIT_COMMIT');
      setLastRealAnalysis(authoritative);
      setLastAnalysisTimestamp(new Date().toISOString());
      persistAnalysis(authoritative, 'REAL_GIT_COMMIT', repoPath, targetCommitRef);
      return authoritative;
    } catch (err: any) {
      if (requestId === currentRequestIdRef.current) {
        const errorMsg = err.message || 'Real Git commit analysis failed. Verify repository path and commit SHA.';
        setAnalysisError(errorMsg);
        // Do not overwrite with synthetic
      }
      throw err;
    } finally {
      if (requestId === currentRequestIdRef.current) {
        setIsAnalyzing(false);
      }
    }
  }, [persistAnalysis, selectedBranch]);

  const analyzeGitBranch = useCallback(async (
    repoPath: string,
    branchName = 'HEAD',
    maxCommits = 10,
    policyName = 'Balanced Policy (Default)',
    threshold = 0.50
  ): Promise<BranchBatchAnalysisResponse> => {
    const requestId = ++currentRequestIdRef.current;
    setIsAnalyzing(true);
    setAnalysisError(null);
    setRepositoryPath(repoPath);
    setSelectedBranch(branchName);

    try {
      const res = await api.analyzeGitBranch(repoPath.trim(), branchName, maxCommits, policyName, threshold);

      if (requestId !== currentRequestIdRef.current) {
        return res;
      }

      if (res.commits && res.commits.length > 0) {
        setLatestBatchResult(res);
        const topCommit = res.commits[0];
        const authoritative: CommitAnalysisResult = {
          ...topCommit,
          analysis_source: 'REAL_GIT_BRANCH',
          source_type: 'REAL_GIT_BRANCH',
          data_scope: 'REAL_GIT_BRANCH',
          repository_path: repoPath,
          branch_name: branchName,
          policy_name: policyName,
          threshold: threshold,
        };

        setSelectedAnalysis(authoritative);
        setAnalysisSource('REAL_GIT_BRANCH');
        setLastRealAnalysis(authoritative);
        setLastAnalysisTimestamp(new Date().toISOString());
        persistAnalysis(authoritative, 'REAL_GIT_BRANCH', repoPath, branchName);
      }

      return res;
    } catch (err: any) {
      if (requestId === currentRequestIdRef.current) {
        setAnalysisError(err.message || `Failed to analyze branch '${branchName}'.`);
      }
      throw err;
    } finally {
      if (requestId === currentRequestIdRef.current) {
        setIsAnalyzing(false);
      }
    }
  }, [persistAnalysis]);

  const selectHistoricalRun = useCallback(async (runId: string): Promise<CommitAnalysisResult | null> => {
    try {
      const details = await api.getRunDetails(runId);
      if (!details) return null;

      const manifest = details.manifest || {};
      const isMined = manifest.schema_status === 'VALID_GIT_MINED_26' || manifest.schema_status === 'VALID_GIT_BRANCH_BATCH';
      const source: AnalysisSourceType = isMined ? 'REAL_GIT_COMMIT' : 'SYNTHETIC_DEMO';

      let rec = details.records && details.records.length > 0 ? details.records[0] : null;

      const loaded: CommitAnalysisResult = {
        commit_id: rec ? rec.commit_id : (manifest.input_identifier || runId),
        commit_sha: rec ? rec.commit_id : (manifest.input_identifier || runId),
        commit_short_sha: rec ? rec.commit_id.substring(0, 8) : runId.substring(0, 8),
        project: rec ? rec.project : manifest.input_identifier?.split(':')[0] || 'Unknown',
        repository_name: rec ? rec.project : manifest.input_identifier?.split(':')[0] || 'Unknown',
        defect_risk_score: rec ? rec.risk_score : 0.0,
        calibrated_probability: rec ? rec.risk_score : 0.0,
        review_priority_rank: 1,
        flagged_for_review: rec && rec.flagged ? 'FLAGGED' : 'STANDARD',
        risk_tier: rec ? rec.risk_tier : 'Tier 3 (Moderate Risk)',
        recommendation: rec ? rec.notes : 'Historical execution manifest selection.',
        lines_added: rec?.raw_metrics?.la || 0,
        lines_deleted: rec?.raw_metrics?.ld || 0,
        total_lines_changed: rec?.total_lines_changed || (rec?.raw_metrics?.la || 0) + (rec?.raw_metrics?.ld || 0),
        modified_files: rec?.files_modified || rec?.raw_metrics?.nf || 1,
        modified_directories: rec?.raw_metrics?.nd || 1,
        modified_subsystems: rec?.raw_metrics?.ns || 1,
        entropy: rec?.raw_metrics?.ent || 0.0,
        file_age_days: rec?.raw_metrics?.age || 0.0,
        subsystem_exp: rec?.raw_metrics?.asexp || 0.0,
        raw_metrics: rec?.raw_metrics,
        run_id: runId,
        manifest: manifest,
        analysis_source: source,
        source_type: source,
        data_scope: source,
        analysis_timestamp: manifest.timestamp || new Date().toISOString(),
      };

      setSelectedAnalysis(loaded);
      setAnalysisSource(source);
      if (source === 'REAL_GIT_COMMIT') {
        setLastRealAnalysis(loaded);
      }
      persistAnalysis(loaded, source, loaded.project, loaded.commit_id);
      return loaded;
    } catch (err: any) {
      console.error('Failed to load historical run:', err);
      return null;
    }
  }, [persistAnalysis]);

  const loadSyntheticDemo = useCallback(async (
    presetKey: string,
    presetLabel: string,
    metrics: any,
    policyName = 'Balanced Policy (Default)',
    threshold = 0.50
  ): Promise<CommitAnalysisResult> => {
    const requestId = ++currentRequestIdRef.current;
    setIsAnalyzing(true);
    setAnalysisError(null);
    setAnalysisSource('SYNTHETIC_DEMO');

    try {
      const synthCommitId = `synth_${presetKey}_${Math.random().toString(36).substring(2, 8)}`;
      const res = await api.analyzeCommit({
        metrics: {
          ...metrics,
          commit_id: synthCommitId,
          project: `DEMO_SYNTHETIC_${presetKey.toUpperCase()}`,
        },
        policy_name: policyName,
        threshold: threshold,
      });

      if (requestId !== currentRequestIdRef.current) {
        return res;
      }

      const syntheticResult: CommitAnalysisResult = {
        ...res,
        author: 'Demo Simulator <synthetic@quality.ai>',
        commit_author: 'Demo Simulator <synthetic@quality.ai>',
        subject: `[SYNTHETIC DEMO] ${presetLabel}`,
        commit_subject: `[SYNTHETIC DEMO] ${presetLabel}`,
        analysis_source: 'SYNTHETIC_DEMO',
        source_type: 'SYNTHETIC_DEMO',
        data_scope: 'SYNTHETIC_DEMO',
        branch_name: 'demo-simulation',
        policy_name: policyName,
        threshold: threshold,
      };

      setSelectedAnalysis(syntheticResult);
      setAnalysisSource('SYNTHETIC_DEMO');
      setLastAnalysisTimestamp(new Date().toISOString());
      persistAnalysis(syntheticResult, 'SYNTHETIC_DEMO', 'DEMO_WORKSPACE', synthCommitId);
      return syntheticResult;
    } catch (err: any) {
      if (requestId === currentRequestIdRef.current) {
        setAnalysisError(err.message || 'Synthetic demo evaluation failed.');
      }
      throw err;
    } finally {
      if (requestId === currentRequestIdRef.current) {
        setIsAnalyzing(false);
      }
    }
  }, [persistAnalysis]);

  const exitDemoMode = useCallback((): boolean => {
    if (lastRealAnalysis) {
      setSelectedAnalysis(lastRealAnalysis);
      setAnalysisSource(lastRealAnalysis.source_type || 'REAL_GIT_COMMIT');
      persistAnalysis(
        lastRealAnalysis,
        lastRealAnalysis.source_type || 'REAL_GIT_COMMIT',
        lastRealAnalysis.repository_path || lastRealAnalysis.project,
        lastRealAnalysis.commit_sha || lastRealAnalysis.commit_id
      );
      return true;
    }
    clearAnalysis();
    return false;
  }, [lastRealAnalysis, persistAnalysis, clearAnalysis]);

  const restoreLatestRealAnalysis = useCallback(async (): Promise<boolean> => {
    if (lastRealAnalysis) {
      setSelectedAnalysis(lastRealAnalysis);
      setAnalysisSource(lastRealAnalysis.source_type || 'REAL_GIT_COMMIT');
      return true;
    }
    try {
      const runs = await api.getRuns(undefined, true);
      const realRun = runs.find(r => r.schema_status === 'VALID_GIT_MINED_26' || r.schema_status === 'VALID_GIT_BRANCH_BATCH');
      if (!realRun) return false;
      const res = await selectHistoricalRun(realRun.run_id);
      return res !== null;
    } catch {
      return false;
    }
  }, [lastRealAnalysis, selectHistoricalRun]);

  return (
    <AnalysisContext.Provider
      value={{
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
        lastAnalysisTimestamp,
        lastRealAnalysis,
        latestBatchResult,
        connectRepository,
        selectBranch,
        analyzeGitCommit,
        analyzeGitBranch,
        selectHistoricalRun,
        loadSyntheticDemo,
        exitDemoMode,
        clearAnalysis,
        restoreLatestRealAnalysis,
      }}
    >
      {children}
    </AnalysisContext.Provider>
  );
};

export const useAnalysis = (): AnalysisContextType => {
  const context = useContext(AnalysisContext);
  if (!context) {
    throw new Error('useAnalysis must be used within an AnalysisProvider');
  }
  return context;
};

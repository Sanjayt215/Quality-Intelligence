# Quality Intelligence — Developer Frontend SPA

Modern, responsive dark-themed SaaS web application for the **Quality Intelligence (Code-Change Defect-Risk Predictor)** platform.

## Technology Stack

- **Framework:** React 18 with TypeScript
- **Bundler & Dev Server:** Vite
- **Routing:** React Router v6
- **Iconography:** Lucide React
- **Design System:** Custom Dark SaaS theme (`#090d16` canvas, `#131b2e` cards, `#38bdf8` accent)

---

## 8 Distinct Functional Pages

1. **Overview Command Center (`/`):**
   - High-level KPI metric cards (Total Commits Analyzed, Review Workload %, Active Policy, Drift Status)
   - Recent execution runs & quick-action triggers

2. **Review Queue & Batch Triage (`/queue`):**
   - Batch CSV upload and instant inference
   - Multi-parameter filtering by project, risk tier (Critical, High, Medium, Low), and review flag
   - Sorting, search, pagination, and one-click CSV export

3. **Single Commit Defect-Risk Analyzer (`/analyze`):**
   - Interactive sliders for all 12 ApacheJIT raw change dimensions
   - Archetypal change presets (Doc update, Local bugfix, Cross-cutting refactor, Junior core patch)
   - Instant defect probability calculation, risk tier badge, and 26-feature breakdown

4. **Quality Insights & Temporal Trends (`/insights`):**
   - Longitudinal trajectory tracking across 2015–2019 with chronological holdout indicator
   - Cross-project empirical baseline benchmarks across Apache repositories

5. **Reliability Center & Threshold Policies (`/reliability`):**
   - 4 calibrated operational threshold policies (Balanced F1, High Recall 90%, Workload 20%, Workload 30%)
   - Real-time confusion matrix simulation on the quarantined holdout test set ($N=30,111$)
   - Brier score analysis and drift status indicator

6. **Model Center & Architecture Governance (`/model`):**
   - Serialized Random Forest architecture specifications & training corpus bounds
   - Leave-One-Project-Out (LOPO) cross-repository generalization transfer benchmarks
   - Comprehensive 26-feature schema catalog with categories and semantic definitions

7. **Reports, Cryptographic Provenance & History (`/reports`):**
   - Immutable SHA-256 execution run manifests
   - Cryptographic dataset and model verification
   - Interactive JSON manifest inspector

8. **Developer CI/CD Integration (`/developer`):**
   - Pull Request advisory review comment preview
   - Dry-run simulation mode
   - Non-blocking governance verification notice

---

## Local Development & Setup

### 1. Install Dependencies
```bash
cd frontend
npm install
```

### 2. Start Dev Server
```bash
npm run dev
```
The application will launch at `http://localhost:5173`. API calls are automatically proxied to the FastAPI backend running on `http://localhost:8000`.

### 3. Build for Production
```bash
npm run build
```
Build artifacts are generated in `frontend/dist/`.

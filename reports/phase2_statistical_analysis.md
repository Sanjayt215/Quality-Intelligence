# Phase 2 Statistical Analysis Report
## Empirical Defect-Risk Hypothesis Testing & Multicollinearity Diagnostics
**Dataset Evaluated:** ApacheJIT Training Corpus (`n = 44,834` commits)  
**Target Analyzed:** `buggy` (Defect Commits: `22,421`, Clean Commits: `22,413`)  
**Significance Threshold:** $\alpha = 0.05$ with Benjamini-Hochberg (FDR) multiple-testing adjustment.

---
## 1. Executive Summary of Hypotheses

| Hypothesis | Feature | Question | Test Statistic | Raw p-value | Adjusted q-value | Effect Size (Cliff's $\delta$) | Magnitude | Conclusion |
|---|---|---|---|---|---|---|---|---|
| **H1** | `total_lines_changed` | Total lines of code changed (la + ld) differs by defect status | $U = 3.78e+08$ | $0.00e+00$ | $0.00e+00$ | $0.5043$ | Large | **Reject $H_0$** |
| **H2** | `nf` | Number of modified files (nf) differs by defect status | $U = 3.63e+08$ | $0.00e+00$ | $0.00e+00$ | $0.4452$ | Medium | **Reject $H_0$** |
| **H3** | `ent` | Entropy of change distribution across files (ent) differs by defect status | $U = 3.50e+08$ | $0.00e+00$ | $0.00e+00$ | $0.3946$ | Medium | **Reject $H_0$** |
| **H4_ndev** | `ndev` | Historical metric 'ndev' differs by defect status | $U = 2.23e+08$ | $1.21e-94$ | $1.56e-94$ | $-0.1125$ | Negligible | **Reject $H_0$** |
| **H4_age** | `age` | Historical metric 'age' differs by defect status | $U = 2.89e+08$ | $3.67e-165$ | $6.60e-165$ | $0.1490$ | Small | **Reject $H_0$** |
| **H4_nuc** | `nuc` | Historical metric 'nuc' differs by defect status | $U = 2.81e+08$ | $7.81e-108$ | $1.17e-107$ | $0.1203$ | Negligible | **Reject $H_0$** |
| **H4_aexp** | `aexp` | Historical metric 'aexp' differs by defect status | $U = 2.26e+08$ | $3.24e-75$ | $3.24e-75$ | $-0.1001$ | Negligible | **Reject $H_0$** |
| **H4_arexp** | `arexp` | Historical metric 'arexp' differs by defect status | $U = 2.25e+08$ | $6.19e-83$ | $6.96e-83$ | $-0.1052$ | Negligible | **Reject $H_0$** |
| **H4_asexp** | `asexp` | Historical metric 'asexp' differs by defect status | $U = 1.87e+08$ | $0.00e+00$ | $0.00e+00$ | $-0.2548$ | Small | **Reject $H_0$** |
| **H5** | `project` | Defect-inducing rate varies across software projects | $\chi^2 = 8479.0$ | $0.00e+00$ | $0.00e+00$ | $V = 0.4349$ | Medium | **Reject $H_0$** |

## 2. In-Depth Hypothesis Findings

### Hypothesis 1: Code Change Size (`total_lines_changed`)

- **Null Hypothesis ($H_{0,1}$):** Code change volume does not differ between defect-inducing and clean commits.
- **Alternative Hypothesis ($H_{a,1}$):** Defect-inducing commits have larger code change churn.
- **Empirical Result:** $U = 3.78e+08$, adjusted $q < 10^{-300}$, Cliff's $\delta = 0.5043$ (**Large**).
- **Group Metrics:** Median Buggy = `171.0 lines` (Mean: `480.32`) vs. Median Clean = `31.0 lines` (Mean: `137.52`).
- **95% Bootstrap Median Difference CI:** `[136.0, 145.0] lines`.
- **Substantive Finding:** Changes introducing defects are over 5.5x larger in median lines modified. Change size is the single strongest bivariate predictor of defect risk.

### Hypothesis 2: File Modification Dispersion (`nf`)

- **Empirical Result:** $U = 3.63e+08$, adjusted $q < 10^{-300}$, Cliff's $\delta = 0.4452$ (**Medium**).
- **Group Metrics:** Median Buggy = `5.0 files` vs. Median Clean = `2.0 files`.
- **Substantive Finding:** Commits that touch multiple files exhibit significantly higher risk, consistent with the diffusion risk hypothesis.

### Hypothesis 3: Code Change Entropy (`ent`)

- **Empirical Result:** $U = 3.50e+08$, adjusted $q < 10^{-300}$, Cliff's $\delta = 0.3946$ (**Medium**).
- **Group Metrics:** Median Buggy = `1.67` vs. Median Clean = `0.86`.
- **Substantive Finding:** Even after controlling for file count, modifications scattered unevenly across components have higher defect probability.

### Hypothesis 4: Developer & File History Metrics

- **`ndev`:** $\delta = -0.1125$ (Negligible). Median Buggy: `2.0` vs. Clean: `2.5`. Higher `ndev` is associated with decreased defect risk.
- **`age`:** $\delta = 0.1490$ (Small). Median Buggy: `17.25` vs. Clean: `8.5`. Higher `age` is associated with increased defect risk.
- **`nuc`:** $\delta = 0.1203$ (Negligible). Median Buggy: `22.75` vs. Clean: `14.75`. Higher `nuc` is associated with increased defect risk.
- **`aexp`:** $\delta = -0.1001$ (Negligible). Median Buggy: `221.0` vs. Clean: `323.0`. Higher `aexp` is associated with decreased defect risk.
- **`arexp`:** $\delta = -0.1052$ (Negligible). Median Buggy: `190.5` vs. Clean: `262.48`. Higher `arexp` is associated with decreased defect risk.
- **`asexp`:** $\delta = -0.2548$ (Small). Median Buggy: `8.0` vs. Clean: `72.0`. Higher `asexp` is associated with decreased defect risk.

> [!NOTE]
> **Experience Effect Insight:** Author subsystem experience (`asexp`) has a substantial protective effect > (Cliff's $\delta = -0.2548$, Median Clean: `72.0` vs. Median Buggy: `8.0`). Developers working outside > their familiar subsystems generate a disproportionate fraction of bug-inducing commits.

### Hypothesis 5: Project-Level Defect Rate Variation

- **Empirical Result:** $\chi^2 = 8479.0$ (df = 14, $p < 10^{-300}$), Cramér's $V = 0.4349$ (**Medium**).
- **Project Breakdown in Training Split:**

| Project | Total Commits | Clean | Buggy | Defect Rate % |
|---|---|---|---|---|
| `apache/activemq` | 2,880 | 1,489 | 1,391 | 48.3% |
| `apache/camel` | 8,299 | 5,565 | 2,734 | 32.9% |
| `apache/cassandra` | 5,245 | 2,306 | 2,939 | 56.0% |
| `apache/flink` | 3,534 | 2,023 | 1,511 | 42.8% |
| `apache/groovy` | 3,031 | 1,526 | 1,505 | 49.6% |
| `apache/hadoop` | 2,865 | 2,865 | 0 | 0.0% |
| `apache/hadoop-hdfs` | 2,330 | 360 | 1,970 | 84.5% |
| `apache/hadoop-mapreduce` | 1,088 | 263 | 825 | 75.8% |
| `apache/hbase` | 4,747 | 1,552 | 3,195 | 67.3% |
| `apache/hive` | 4,037 | 761 | 3,276 | 81.2% |
| `apache/ignite` | 4,400 | 2,984 | 1,416 | 32.2% |
| `apache/kafka` | 612 | 144 | 468 | 76.5% |
| `apache/spark` | 684 | 212 | 472 | 69.0% |
| `apache/zeppelin` | 659 | 246 | 413 | 62.7% |
| `apache/zookeeper` | 423 | 117 | 306 | 72.3% |

> [!IMPORTANT]
> **Submodule Labeling Finding:** `apache/hadoop` exhibits 0.0% buggy commits because Jira issue tracking > for Hadoop is linked to specific child modules (`apache/hadoop-hdfs` with 84.5% and `apache/hadoop-mapreduce` with 75.8%). > In Phase 3, evaluations must account for repository-level reporting heterogeneity.

## 3. Multicollinearity & Variance Inflation Factor (VIF) Analysis

Variance Inflation Factor (VIF) measures how much the variance of an estimated regression coefficient is inflated due to collinearity with other predictors:

| Feature | VIF | Risk Level | Interpretation & Recommendation |
|---|---|---|---|
| `aexp` | 13.71 | **High (VIF > 10)** | High collinearity between lifetime and recent experience ($r \approx 0.85$). Tree models tolerate this; for linear models, retain one or use `experience_gap`. |
| `arexp` | 12.82 | **High (VIF > 10)** | High collinearity between lifetime and recent experience ($r \approx 0.85$). Tree models tolerate this; for linear models, retain one or use `experience_gap`. |
| `nf` | 4.97 | **Low (VIF < 5)** | Moderate correlation ($r \approx 0.81$) reflecting files vs directories. Well-tolerated by regularized models. |
| `nd` | 3.47 | **Low (VIF < 5)** | Moderate correlation ($r \approx 0.81$) reflecting files vs directories. Well-tolerated by regularized models. |
| `ent` | 3.06 | **Low (VIF < 5)** | VIF < 5; low multicollinearity risk. |
| `asexp` | 2.83 | **Low (VIF < 5)** | VIF < 5; low multicollinearity risk. |
| `ndev` | 2.75 | **Low (VIF < 5)** | VIF < 5; low multicollinearity risk. |
| `nuc` | 2.64 | **Low (VIF < 5)** | VIF < 5; low multicollinearity risk. |
| `ns` | 1.50 | **Low (VIF < 5)** | VIF < 5; low multicollinearity risk. |
| `la` | 1.38 | **Low (VIF < 5)** | VIF < 5; low multicollinearity risk. |
| `ld` | 1.28 | **Low (VIF < 5)** | VIF < 5; low multicollinearity risk. |
| `age` | 1.04 | **Low (VIF < 5)** | VIF < 5; low multicollinearity risk. |

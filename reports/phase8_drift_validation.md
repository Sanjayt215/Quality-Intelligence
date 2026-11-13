# Phase 8 Temporal and Project Drift Monitoring Report
## AI-Assisted Code Silent Regression Forecaster
**Product Name:** Quality Intelligence — Code-Change Defect-Risk Predictor  
**Date:** 2026-10-19  
**Methodological Notice:** Distribution shifts and prevalence changes are observational patterns. A statistical shift does not by itself prove model degradation, and an apparent prevalence decline should not be assumed to be pure right-censoring without accounting for genuine process improvements.

**Sample Comparison:** Historical Reference ($N_{ref} = 44,834$) vs. Deployment Holdout ($N_{curr} = 30,111$)

---
## 1. Covariate Drift: Feature Distribution Shifts with Benjamini-Hochberg FDR & Cliff's Delta

Comparing historical training features (2003–2016) against deployment holdout features (2017–2019) using Two-Sample Kolmogorov-Smirnov test (with Benjamini-Hochberg FDR multiple-testing correction), Cliff's Delta non-parametric effect sizes (Romano et al. benchmarks), and Wasserstein distance:

| Feature | Ref Med | Curr Med | Shift (%) | KS (D) | Raw p | FDR q | Cliff's d | Effect | Wasserstein | Shift Status |
|---|---|---|---|---|---|---|---|---|---|---|
| `la` | 52.0 | 43.0 | -17.3% | 0.0546 | 4.67e-47 | 7.14e-47 | -0.050 | negligible | 20.58 | ✅ Stable |
| `ld` | 10.0 | 11.0 | +10.0% | 0.0152 | 0.000473 | 0.000492 | +0.015 | negligible | 5.43 | ✅ Stable |
| `nf` | 3.0 | 3.0 | +0.0% | 0.0525 | 1.13e-43 | 1.55e-43 | -0.025 | negligible | 0.49 | ✅ Stable |
| `nd` | 2.0 | 2.0 | +0.0% | 0.0702 | 1.15e-77 | 2e-77 | -0.040 | negligible | 0.28 | ✅ Stable |
| `ns` | 1.0 | 1.0 | +0.0% | 0.0292 | 8.66e-14 | 9.79e-14 | -0.022 | negligible | 0.07 | ✅ Stable |
| `ent` | 1.169 | 1.154 | -1.3% | 0.0531 | 1.28e-44 | 1.84e-44 | -0.011 | negligible | 0.08 | ✅ Stable |
| `ndev` | 2.0 | 3.105 | +55.3% | 0.1281 | 3.61e-258 | 1.88e-257 | +0.164 | small | 2.40 | ⚠️ Shift Detected |
| `age` | 13.0 | 24.5 | +88.5% | 0.1169 | 7.18e-215 | 2.67e-214 | +0.153 | small | 32.90 | ⚠️ Shift Detected |
| `nuc` | 18.551 | 14.0 | -24.5% | 0.1127 | 8.66e-200 | 2.05e-199 | -0.116 | negligible | 57.44 | ⚠️ Shift Detected |
| `aexp` | 266.0 | 126.0 | -52.6% | 0.1425 | 8.68e-320 | 5.64e-319 | -0.163 | small | 808.87 | ⚠️ Shift Detected |
| `arexp` | 220.0 | 99.0 | -55.0% | 0.1962 | 0.0 | 0.0 | -0.206 | small | 280.08 | ⚠️ Shift Detected |
| `asexp` | 33.0 | 16.0 | -51.5% | 0.1144 | 1.07e-205 | 3.08e-205 | -0.117 | negligible | 152.61 | ⚠️ Shift Detected |
| `total_lines_changed` | 77.0 | 71.0 | -7.8% | 0.0314 | 7.15e-16 | 8.45e-16 | -0.023 | negligible | 21.36 | ✅ Stable |
| `net_lines_changed` | 21.0 | 14.0 | -33.3% | 0.0842 | 1.46e-111 | 2.92e-111 | -0.064 | negligible | 23.78 | ⚠️ Shift Detected |
| `deletion_ratio` | 0.245 | 0.295 | +20.5% | 0.0791 | 1.85e-98 | 3.44e-98 | +0.080 | negligible | 0.04 | ✅ Stable |
| `files_per_subsystem` | 2.5 | 2.0 | -20.0% | 0.0372 | 4.77e-22 | 6.2e-22 | -0.020 | negligible | 0.18 | ✅ Stable |
| `directories_per_file` | 0.667 | 0.667 | +0.0% | 0.0120 | 0.0111 | 0.0111 | +0.003 | negligible | 0.01 | ✅ Stable |
| `experience_gap` | 11.633 | 18.5 | +59.0% | 0.0922 | 1.11e-133 | 2.39e-133 | +0.061 | negligible | 529.98 | ⚠️ Shift Detected |
| `log1p_la` | 3.97 | 3.784 | -4.7% | 0.0546 | 4.67e-47 | 7.14e-47 | -0.050 | negligible | 0.20 | ✅ Stable |
| `log1p_ld` | 2.398 | 2.485 | +3.6% | 0.0152 | 0.000473 | 0.000492 | +0.015 | negligible | 0.05 | ✅ Stable |
| `log1p_total_lines_changed` | 4.357 | 4.277 | -1.8% | 0.0314 | 7.15e-16 | 8.45e-16 | -0.023 | negligible | 0.11 | ✅ Stable |
| `log1p_age` | 2.639 | 3.239 | +22.7% | 0.1169 | 7.18e-215 | 2.67e-214 | +0.153 | small | 0.49 | ⚠️ Shift Detected |
| `log1p_nuc` | 2.973 | 2.708 | -8.9% | 0.1127 | 8.66e-200 | 2.05e-199 | -0.116 | negligible | 0.40 | ⚠️ Shift Detected |
| `log1p_aexp` | 5.587 | 4.844 | -13.3% | 0.1425 | 8.68e-320 | 5.64e-319 | -0.163 | small | 0.76 | ⚠️ Shift Detected |
| `log1p_arexp` | 5.398 | 4.605 | -14.7% | 0.1962 | 0.0 | 0.0 | -0.206 | small | 0.78 | ⚠️ Shift Detected |
| `log1p_asexp` | 3.526 | 2.833 | -19.7% | 0.1144 | 1.07e-205 | 3.08e-205 | -0.117 | negligible | 0.50 | ⚠️ Shift Detected |

---
## 2. Prevalence Drift: Ground Truth Defect Frequency Across Partitions

- **Reference Population (2003–2016):** 22,421 defects across 44,834 commits (50.01%)
- **Current Population (2017–2019):** 5,818 defects across 30,111 commits (19.32%)
- **Prevalence Difference:** `-30.69%` points (PREVALENCE_DRIFT)

---
## 3. Repository Composition & Distribution Changes

Comparing the proportion of commits across tracked repositories:

| Project Name | Ref Commits | Ref Share (%) | Curr Commits | Curr Share (%) | Sample Size Caveats |
|---|---|---|---|---|---|
| `apache/activemq` | 2,880 | 6.4% | 273 | 0.9% |  |
| `apache/camel` | 8,299 | 18.5% | 6,432 | 21.4% |  |
| `apache/cassandra` | 5,245 | 11.7% | 554 | 1.8% |  |
| `apache/flink` | 3,534 | 7.9% | 5,454 | 18.1% |  |
| `apache/groovy` | 3,031 | 6.8% | 1,351 | 4.5% |  |
| `apache/hadoop` | 2,865 | 6.4% | 5,421 | 18.0% |  |
| `apache/hadoop-hdfs` | 2,330 | 5.2% | 342 | 1.1% |  |
| `apache/hadoop-mapreduce` | 1,088 | 2.4% | 24 | 0.1% | ⚠️ Very small sample (N < 50) |
| `apache/hbase` | 4,747 | 10.6% | 2,158 | 7.2% |  |
| `apache/hive` | 4,037 | 9.0% | 2,090 | 6.9% |  |
| `apache/ignite` | 4,400 | 9.8% | 3,064 | 10.2% |  |
| `apache/kafka` | 612 | 1.4% | 1,640 | 5.5% |  |
| `apache/spark` | 684 | 1.5% | 539 | 1.8% |  |
| `apache/zeppelin` | 659 | 1.5% | 513 | 1.7% |  |
| `apache/zookeeper` | 423 | 0.9% | 256 | 0.8% |  |

---
## 4. Annual Temporal Trajectory & Ranking Stability (Performance Drift)

Tracking annual observed label prevalence alongside model ranking discrimination:

| Year | Sample Size (N) | Defect Count | Observed Prevalence | Mean Risk Score | ROC-AUC | PR-AUC | Caveats |
|---|---|---|---|---|---|---|---|
| **2017** | 10,187 | 2,775 | 27.2% | 0.4829 | 0.8191 | 0.6442 |  |
| **2018** | 9,365 | 1,970 | 21.0% | 0.4970 | 0.7901 | 0.5162 |  |
| **2019** | 10,559 | 1,073 | 10.2% | 0.4389 | 0.8192 | 0.3211 |  |

---
## 5. Methodological & Operational Recommendations

1. **Multiple Testing Correction:** Applying Benjamini-Hochberg FDR across the 26 features prevents false positives when monitoring distribution changes across large commit volumes.
2. **Effect Sizes vs. Sample Size Inflation:** With large samples ($N > 30,000$), p-values approach zero even for miniscule differences. Cliff's Delta and Wasserstein distance quantify whether shifts are practically substantive rather than merely statistically significant.
3. **Stable Commit ID Alignment:** Analytics and pipeline merges must be keyed explicitly on `commit_id` to prevent silent positional misalignment across independently maintained feature and label artifacts.
4. **Label Maturity & Right-Censoring:** Recent commits in 2018–2019 exhibit lower observed defect rates partially due to discovery latency in SZZ bug extraction (it takes time for bugs to be identified and fixed). However, genuine improvements in tooling or testing culture can also reduce defect rates.
5. **Discrimination Invariance:** Even as observed prevalence shifts, ROC-AUC remains stable across years (~0.79 to ~0.83), confirming that the model's ordering of riskier commits relative to benign commits remains effective.
6. **Small-Sample Safeguards:** Repositories with $N < 100$ commits or $< 10$ defect events must display explicit statistical warnings rather than raw point estimates in developer review queues.
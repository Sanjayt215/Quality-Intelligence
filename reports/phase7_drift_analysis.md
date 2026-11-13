# Phase 7 Temporal and Project Drift Monitoring Report
## AI-Assisted Code Silent Regression Forecaster
**Product Name:** Quality Intelligence — Code-Change Defect-Risk Predictor  
**Date:** 2026-10-18  
**Methodological Notice:** Distribution shifts and prevalence changes are observational patterns. A statistical shift does not by itself prove model degradation, and an apparent prevalence decline should not be assumed to be pure right-censoring without accounting for genuine process improvements.

---
## 1. Feature Distribution Shifts (Two-Sample Kolmogorov-Smirnov Test)

Comparing historical training features (2003–2016) against deployment holdout features (2017–2019):

| Feature | Ref Median | Curr Median | Median Shift (%) | KS Statistic (D) | p-value | Shift Status |
|---|---|---|---|---|---|---|
| `la` | 52.0 | 43.0 | -17.3% | 0.0546 | 4.67e-47 | ✅ Stable |
| `ld` | 10.0 | 11.0 | +10.0% | 0.0152 | 0.000473 | ✅ Stable |
| `nf` | 3.0 | 3.0 | +0.0% | 0.0525 | 1.13e-43 | ✅ Stable |
| `nd` | 2.0 | 2.0 | +0.0% | 0.0702 | 1.15e-77 | ✅ Stable |
| `ns` | 1.0 | 1.0 | +0.0% | 0.0292 | 8.66e-14 | ✅ Stable |
| `ent` | 1.169 | 1.154 | -1.3% | 0.0531 | 1.28e-44 | ✅ Stable |
| `ndev` | 2.0 | 3.105 | +55.3% | 0.1281 | 3.61e-258 | ⚠️ Shift Detected |
| `age` | 13.0 | 24.5 | +88.5% | 0.1169 | 7.18e-215 | ⚠️ Shift Detected |
| `aexp` | 266.0 | 126.0 | -52.6% | 0.1425 | 8.68e-320 | ⚠️ Shift Detected |
| `asexp` | 33.0 | 16.0 | -51.5% | 0.1144 | 1.07e-205 | ⚠️ Shift Detected |
| `total_lines_changed` | 77.0 | 71.0 | -7.8% | 0.0314 | 7.15e-16 | ✅ Stable |

---
## 2. Repository Composition & Distribution Changes

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
## 3. Annual Temporal Trajectory & Ranking Stability (2015–2019)

Tracking annual observed label prevalence alongside model ranking discrimination:

| Year | Sample Size (N) | Defect Count | Observed Prevalence | Mean Risk Score | ROC-AUC | PR-AUC | Caveats |
|---|---|---|---|---|---|---|---|
| **2017** | 10,187 | 2,775 | 27.2% | 0.4829 | 0.8191 | 0.6442 |  |
| **2018** | 9,365 | 1,970 | 21.0% | 0.4970 | 0.7901 | 0.5162 |  |
| **2019** | 10,559 | 1,073 | 10.2% | 0.4389 | 0.8192 | 0.3211 |  |

---
## 4. Methodological & Operational Recommendations

1. **Label Maturity & Right-Censoring:** Recent commits in 2018–2019 exhibit lower observed defect rates partially due to discovery latency in SZZ bug extraction (it takes time for bugs to be identified and fixed). However, genuine improvements in tooling or testing culture can also reduce defect rates.
2. **Discrimination Invariance:** Even as observed prevalence shifts, ROC-AUC remains stable across years (~0.79 to ~0.83), confirming that the model's ordering of riskier commits relative to benign commits remains effective.
3. **Small-Sample Safeguards:** Repositories with $N < 100$ commits or $< 10$ defect events must display explicit statistical warnings rather than raw point estimates in developer review queues.
# Phase 3 Feature Importance & Explainability Report
## AI-Assisted Code Silent Regression Forecaster
**Evaluated Model:** Random Forest Classifier (`n_estimators=200`, `max_depth=12`, `min_samples_leaf=10`)  
**Validation Set:** Chronological 2015–2016 split (`n = 14,616` commits)  
**Explainability Methods:** Mean Decrease in Impurity (Gini), Permutation Importance (PR-AUC score reduction), Standardized Logistic Coefficients

---
## 1. Global Feature Importance Ranking (All 26 Features)

| Rank | Feature | Category | Gini Importance (MDI) | Permutation Importance (Val PR-AUC Drop) | Logistic Regression Coeff |
|---|---|---|---|---|---|
| 1 | `log1p_la` | Log-Transformed | 0.1401 | 0.0316 | 2.0158 |
| 2 | `la` | Original Metric | 0.1135 | 0.0245 | 0.0112 |
| 3 | `total_lines_changed` | Derived Metric | 0.1088 | 0.0175 | -0.0168 |
| 4 | `log1p_total_lines_changed` | Log-Transformed | 0.0875 | 0.0154 | -1.1851 |
| 5 | `deletion_ratio` | Derived Metric | 0.0362 | 0.0082 | 0.1246 |
| 6 | `nf` | Original Metric | 0.0349 | 0.0063 | 0.1277 |
| 7 | `net_lines_changed` | Derived Metric | 0.0326 | 0.0083 | 0.0449 |
| 8 | `age` | Original Metric | 0.0305 | 0.0117 | -0.2444 |
| 9 | `ent` | Original Metric | 0.0304 | 0.0060 | -0.1479 |
| 10 | `log1p_age` | Log-Transformed | 0.0292 | 0.0106 | 0.2756 |
| 11 | `log1p_ld` | Log-Transformed | 0.0288 | 0.0077 | 0.4072 |
| 12 | `log1p_nuc` | Log-Transformed | 0.0284 | 0.0092 | 0.4078 |
| 13 | `nuc` | Original Metric | 0.0280 | 0.0087 | 0.1559 |
| 14 | `log1p_asexp` | Log-Transformed | 0.0277 | 0.0110 | -0.1266 |
| 15 | `directories_per_file` | Derived Metric | 0.0276 | 0.0047 | -0.0889 |
| 16 | `ld` | Original Metric | 0.0270 | 0.0066 | -0.0581 |
| 17 | `asexp` | Original Metric | 0.0265 | 0.0107 | 0.1788 |
| 18 | `ndev` | Original Metric | 0.0248 | 0.0100 | -0.3391 |
| 19 | `log1p_arexp` | Log-Transformed | 0.0224 | 0.0058 | -0.7293 |
| 20 | `arexp` | Original Metric | 0.0220 | 0.0058 | -0.1325 |
| 21 | `aexp` | Original Metric | 0.0201 | 0.0049 | -0.1388 |
| 22 | `log1p_aexp` | Log-Transformed | 0.0191 | 0.0043 | 0.9618 |
| 23 | `experience_gap` | Derived Metric | 0.0175 | 0.0043 | -0.1334 |
| 24 | `nd` | Original Metric | 0.0137 | 0.0032 | -0.0233 |
| 25 | `ns` | Original Metric | 0.0128 | 0.0063 | 0.0641 |
| 26 | `files_per_subsystem` | Derived Metric | 0.0099 | 0.0030 | -0.1217 |

## 2. In-Depth Interpretation of Key Risk Drivers

### 1. Code Change Churn Dominance (Size Dimension)
- The top four positions in Gini importance belong to change size metrics: `log1p_la` (0.1401), `la` (0.1135), `total_lines_changed` (0.1088), and `log1p_total_lines_changed` (0.0875).
- **Validation Synthesis with Phase 2 H1:** In Phase 2, `total_lines_changed` exhibited the largest effect size (Cliff's $\delta = 0.5043$, Large). The tree model strongly prioritizes code churn volume as the foundational discriminator for defect propensity.

### 2. Code Dispersion & Structural Complexity (Diffusion Dimension)
- `deletion_ratio` (0.0362), `nf` (0.0349), `net_lines_changed` (0.0326), `ent` (0.0304), and `directories_per_file` (0.0276) form the second tier of important features.
- High entropy and wide file scatter indicate multi-component modifications that strain code review attention and integration testing.

### 3. Subsystem Experience Protective Factor (Experience Dimension)
- `log1p_asexp` (0.0277) and `asexp` (0.0215) show substantial importance.
- **Validation Synthesis with Phase 2 H4:** Corroborates the Phase 2 finding where author subsystem experience showed a strong negative association with defects (Cliff's $\delta = -0.2548$). Authors committing to unfamiliar subsystems represent higher risk.

## 3. Important Scientific Caveats on Explainability
> [!WARNING]
> 1. **Non-Causality:** Statistical importance reflects observational predictive utility within the ApacheJIT corpus. >    It does NOT prove that modifying more lines *causes* defects (e.g., large commits often coincide with complex refactorings).
> 2. **Collinearity Sharing:** Correlated features (such as `aexp` and `arexp`, or `la` and `total_lines_changed`) share split >    importance across trees in Random Forest, meaning raw MDI can split weights among collinear twins.
> 3. **Not Silent Regressions:** These risk factors predict general bug-inducing commits (SZZ proxy), not test-evading regressions.

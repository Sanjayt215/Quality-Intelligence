# Phase 7 Probability Calibration & Ranking Reliability Report
## Empirical Evaluation of Score Semantics, Calibration Metrics & Prior Shift

**Product Name:** Quality Intelligence — Code-Change Defect-Risk Predictor  
**Repository:** `Data_Analytic_Project`  
**Date:** 2026-10-18  
**Scope:** In-depth audit of probability quality, ranking discrimination, Saerens–Elkan Bayes adjustments, and quarantine guarantees on external test data.

---

## 1. Score Semantics: Ranking Discrimination vs. Absolute Probability

A fundamental principle in empirical software engineering is distinguishing between **ranking scores** and **calibrated posterior probabilities**:

| Dimension | Review Priority / Defect-Risk Score ($\hat{s}$) | Calibrated Posterior Probability ($P(Y=1 \mid \mathbf{x})$) |
|---|---|---|
| **Mathematical Meaning** | Monotonic ordinal score reflecting relative likelihood of a bug-inducing commit. | Frequentist expectation: of 100 commits with score $p$, exactly $100 \times p$ contain defects. |
| **Operational Goal** | Order commits in a developer review queue so highest-risk changes are reviewed first. | Estimate expected defect counts, calculate economic cost/benefit of testing, or set hard risk gates. |
| **Evaluation Metrics** | ROC-AUC ($0.8075$), PR-AUC / Average Precision ($0.5111$). | Brier Score, Log Loss, Expected Calibration Error (ECE), Calibration Intercept & Slope. |
| **Sensitivity to Class Shift**| **Invariant:** Under choice-based sampling, rank ordering and ROC-AUC are preserved. | **Highly Sensitive:** Class balance changes cause severe calibration error ($ECE$) and Brier inflation. |

**Key Finding:** The selected Random Forest is a strong, stable **ranking classifier** ($ROC-AUC = 0.8075$ on external holdout, 2.65x lift in PR-AUC over base rate). However, because it was trained on an artificially balanced corpus (50/50 via negative undersampling), its raw outputs cannot be directly interpreted as true defect probabilities in un-downsampled repositories without prior correction.

---

## 2. Experimental Quarantine & Leakage Verification

All calibration models were developed and selected strictly using **training-only chronological partitions**; the external test set (2017–2019, $N=30,111$) was never used for model fitting or parameter tuning:

```
Historical Training Corpus (2003–2016, N=44,834)
├── Chronological Fit Partition: Years <= 2012 (N=18,169 commits) -> Trains Sub-Period Random Forest
├── Chronological Calibration Partition: Years 2013–2014 (N=12,049 commits) -> Fits Platt & Isotonic Calibrators
└── Internal Validation Holdout: Years 2015–2016 (N=14,616 commits) -> Evaluates Calibration & Selects Policies
─────────────────────────────────────────────────────────────────────────────
External Test Quarantine Boundary (Strictly Untouched Holdout)
└── External Holdout: Years 2017–2019 (N=30,111 commits) -> Final Out-of-Time Verification
```

---

## 3. Calibration Benchmark & Brier Score Analysis

### 3.1 External Holdout Performance (2017–2019, N=30,111, Natural Prevalence = 19.32%)

| Model / Post-Processor | Target Prior ($\pi$) | Brier Score | Log Loss | ECE (10-bins) | Calib. Intercept | Calib. Slope | PR-AUC | ROC-AUC |
|---|---|---|---|---|---|---|---|---|
| **Prevalence-Only Baseline (Constant)** | 19.32% | 0.1559 | 0.4909 | 0.0000 | -0.4698 | 0.6715 | 0.1932 | 0.5000 |
| **Selected Random Forest (Raw Output)** | 50.00% | 0.2158 | 0.6236 | 0.2786 | -1.7671 | 0.9716 | **0.5111** | **0.8075** |
| **Platt / Sigmoid Calibrated** | 50.00% | 0.2082 | 0.6040 | 0.2646 | -1.6441 | 1.0046 | 0.4757 | 0.7954 |
| **Isotonic Regression Calibrated** | 50.00% | 0.2097 | 0.6058 | 0.2648 | -1.6430 | 1.0018 | 0.4581 | 0.7946 |
| **Prior-Corrected (29.3% Natural Training)** | 29.28% | **0.1454** | **0.4452** | **0.1287** | -0.9110 | 0.9721 | **0.5111** | **0.8075** |
| **Prior-Corrected (19.3% Test Scenario)** | 19.32% | **0.1267** | **0.3977** | **0.0468** | **-0.3792** | 0.9719 | **0.5111** | **0.8075** |

### 3.2 Key Analytical Observations:
1. **Why Raw Random Forest Has a High Brier Score:**
   The raw RF outputs have a mean prediction of $0.4718$, reflecting the balanced training distribution. Because the true prevalence in the test holdout is $0.1932$, the mean prediction is biased upwards by $\approx 0.28$. The Brier score decomposes into:
   $$\text{Brier} = \text{Reliability (Calibration Error)} - \text{Resolution} + \text{Uncertainty}$$
   The large calibration error ($ECE = 0.2786$, Intercept = $-1.7671$) inflates the Brier score to $0.2158$.
2. **Why Standard Platt and Isotonic Calibration Fail to Correct the Score:**
   Platt and Isotonic scalers were fitted on the 2013–2014 calibration partition, which was also balanced to 50% defect prevalence. Consequently, they learned to calibrate probabilities to a 50% universe. When tested on a 19.32% universe, their Brier scores remain high ($0.2082$ and $0.2097$).
3. **Resolution via Saerens–Elkan Prior Correction:**
   Adjusting for prior shift using only the training-set natural population prevalence (29.28%) immediately lowers the Brier score to **0.1454** ($ECE = 0.1287$), beating the baseline null model (**0.1559**) without any knowledge of the test set.

---

## 4. Mathematical Audit of the Saerens–Elkan Formulation

Under choice-based (case-control) sampling, positive instances are sampled with probability $P(S=1 \mid Y=1)$ and negative instances with $P(S=1 \mid Y=0)$. By Bayes' rule (Saerens et al., 2002; Elkan, 2001):

$$\hat{P}_{\text{adj}}(Y=1 \mid \mathbf{x}) = \frac{p}{p + \left(\frac{1 - \pi_{\text{target}}}{\pi_{\text{target}}}\right) \cdot \left(\frac{\pi_{\text{train}}}{1 - \pi_{\text{train}}}\right) (1 - p)}$$

Where:
- $p = P_{\text{train}}(Y=1 \mid \mathbf{x})$ is the raw model score.
- $\pi_{\text{train}} = 0.50$ is the training sample defect prevalence.
- $\pi_{\text{target}}$ is the assumed deployment target prevalence.

### Numerical Boundaries & Monotonicity Proof:
1. **Exact 50/50 Simplification:** When $\pi_{\text{train}} = 0.50$, the factor $\frac{\pi_{\text{train}}}{1 - \pi_{\text{train}}} = 1$, reducing the adjustment to:
   $$\hat{P}_{\text{adj}} = \frac{p}{p + \frac{1 - \pi_{\text{target}}}{\pi_{\text{target}}} (1 - p)}$$
2. **Strict Monotonicity:** Let $k = \frac{1 - \pi_{\text{target}}}{\pi_{\text{target}}} > 0$. The derivative is:
   $$\frac{d\hat{P}_{\text{adj}}}{dp} = \frac{k}{(p + k(1 - p))^2} > 0 \quad \forall p \in (0, 1)$$
   Because the first derivative is strictly positive, the transformation is strictly monotonic.
3. **Boundary Limits:**
   - $\lim_{p \to 0} \hat{P}_{\text{adj}} = 0$
   - $\lim_{p \to 1} \hat{P}_{\text{adj}} = 1$
   - Numerical clipping at $[\epsilon, 1 - \epsilon]$ with $\epsilon = 10^{-6}$ prevents zero-division for extreme inputs.
4. **Ranking Invariance:** Monotonic transformations preserve rank orders exactly:
   $$\text{ROC-AUC}(\hat{P}_{\text{adj}}) \equiv \text{ROC-AUC}(p) = 0.8075$$
   $$\text{PR-AUC}(\hat{P}_{\text{adj}}) \equiv \text{PR-AUC}(p) = 0.5111$$

---

## 5. Deployment Policy & Practical Recommendations

1. **Unknown Future Prevalence is an Unknown, Not a Constant:**
   Different software repositories exhibit vastly different natural defect rates (e.g., `apache/camel` has 5.3% defect prevalence, while `apache/hive` has 45.3%). Hardcoding 19.32% or 29.28% as a universal truth is invalid.
2. **Operational Deployment Strategy:**
   - **For Pull Request Review Prioritization:** Use the **Unadjusted Model Defect-Risk Score** ($p \ge \tau$). Ranking is optimal and completely invariant to prior shifts.
   - **For Financial / Risk Estimation:** Use the **Prior-Adjusted Scenario Explorer** where repository owners configure their own observed historical defect rate.

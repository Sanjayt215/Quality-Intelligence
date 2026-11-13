# Scientific Methodology — Quality Intelligence

## 1. Problem Formulation: Just-in-Time (JIT) Defect Prediction

Traditional software defect prediction operates at the file or module level, typically executed periodically after release. In contrast, **Just-in-Time (JIT) Defect Prediction** predicts defect risk immediately when a developer commits code or opens a pull request.

- **Unit of Analysis**: Individual Git commit $C_i$.
- **Binary Target $y_i \in \{0, 1\}$**:
  - $y_i = 1$: The change introduced a bug that subsequently caused a bug-fixing commit (SZZ algorithm ground truth).
  - $y_i = 0$: Clean commit with no associated regression.

---

## 2. Metric Extraction Framework

Following the seminal work by Kamei et al. (IEEE TSE 2013), each change is characterized across four orthogonal metric dimensions:

### A. Diffusion & Scope
- **`nf` (Modified Files)**: Number of files touched in the change.
- **`nd` (Modified Directories)**: Number of unique directories modified.
- **`ns` (Modified Subsystems)**: Number of high-level architectural subsystems modified.
- **`ent` (Change Entropy)**: Normalized Shannon entropy measuring the dispersion of modified lines across files:
  $$H(C) = - \sum_{k=1}^{n} p_k \log_2(p_k)$$
  where $p_k = \frac{\Delta \text{lines}_k}{\sum_j \Delta \text{lines}_j}$.

### B. Change Size
- **`la` (Lines Added)**: Churn added in the commit.
- **`ld` (Lines Deleted)**: Churn deleted in the commit.
- **`total_lines_changed`**: $la + ld$.
- **`net_lines_changed`**: $|la - ld|$.
- **`deletion_ratio`**: $\frac{ld}{la + ld + \epsilon}$.

### C. File History & Churn Dynamics
- **`ndev` (Prior Developers)**: Distinct developers who have historically modified the files in this commit.
- **`age` (File Age)**: Mean time interval (in days) since the files were last modified.
- **`nuc` (Unique Changes)**: Cumulative prior commit count touching the modified files.

### D. Developer Experience
- **`aexp` (Author Total Experience)**: Total lifetime commits authored by this developer across the project.
- **`arexp` (Author Recent Experience)**: Experience weighted inversely by calendar age to reflect recent familiarity.
- **`asexp` (Author Subsystem Experience)**: Number of prior commits authored by this developer specifically within the modified subsystem.
- **`experience_gap`**: $\max(0, aexp - asexp)$.

---

## 3. Strict Temporal Splitting & Leakage Prevention

In software engineering research, standard random $k$-fold cross-validation introduces severe **temporal lookahead bias** (information leakage from future commits into past predictions).

Quality Intelligence enforces strict **temporal partitioning**:
- **Dataset**: ApacheJIT benchmark ($N = 106,674$ commits across 15 Apache open-source projects, 2001–2019).
- **Training Set**: $N_{train} = 44,834$ commits authored strictly prior to the temporal partition boundary.
- **Holdout Test Set**: $N_{test} = 30,111$ commits authored strictly after the boundary.
- **Temporal Invariant**: For any target commit $C_t$ evaluated at timestamp $T$, all historical metrics (`age`, `ndev`, `nuc`, `aexp`, `arexp`, `asexp`) are derived strictly using commits $C$ with $\text{timestamp}(C) < T$.

---

## 4. Probability Calibration

Tree-based ensembles (such as Random Forest) frequently produce push-toward-extremes or uncalibrated posterior probabilities.

To guarantee that a predicted probability of 60% reflects an empirical defect rate of 60%:
- **Isotonic Regression** $m(\hat{p})$ is fitted on holdout validation data.
- Evaluated using **Brier Score** and **Expected Calibration Error (ECE)**.
- In cross-project pilot evaluations on unfamiliar repositories, raw and calibrated probabilities are reported alongside epistemic uncertainty bounds.

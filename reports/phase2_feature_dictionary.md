# Phase 2 Feature Dictionary
## AI-Assisted Code Silent Regression Forecaster

This dictionary documents all 26 approved predictor features engineered during Phase 2. Every feature is derived exclusively from information available at commit authoring time without lookahead bias.

| Feature Name | Category | Description | Formula / Transformation | Purpose | Assumptions / Zero Rules | Status |
|---|---|---|---|---|---|---|
| `la` | Original | Lines of code added in the commit. | `la` | None | Non-negative integer | **Retained** |
| `ld` | Original | Lines of code deleted in the commit. | `ld` | None | Non-negative integer | **Retained** |
| `nf` | Original | Number of modified files in the commit. | `nf` | None | Non-negative integer (>= 1) | **Retained** |
| `nd` | Original | Number of modified directories in the commit. | `nd` | None | Non-negative integer (>= 1) | **Retained** |
| `ns` | Original | Number of modified subsystems in the commit. | `ns` | None | Non-negative integer (>= 1) | **Retained** |
| `ent` | Original | Entropy of code change distribution across files. | `ent` | None | Bounded continuous [0.0, 7.0] | **Retained** |
| `ndev` | Original | Number of prior developers modifying the changed files. | `ndev` | None | Non-negative float | **Retained** |
| `age` | Original | Mean age of modified files in days/weeks. | `age` | None | Non-negative float | **Retained** |
| `nuc` | Original | Number of unique prior changes made to modified files. | `nuc` | None | Non-negative float | **Retained** |
| `aexp` | Original | Author experience (cumulative prior commits). | `aexp` | None | Non-negative integer | **Retained** |
| `arexp` | Original | Author recent experience (recency-weighted commits). | `arexp` | None | Non-negative float | **Retained** |
| `asexp` | Original | Author subsystem experience in modified subsystem. | `asexp` | None | Non-negative float | **Retained** |
| `total_lines_changed` | Derived | Total volume of code change churn. | `la + ld` | Additive size churn | la, ld >= 0 | **Retained** |
| `net_lines_changed` | Derived | Net code growth of the commit. | `la - ld` | Directional change volume | None (can be negative) | **Retained** |
| `deletion_ratio` | Derived | Fraction of code churn represented by deletions. | `ld / (la + ld)` | Refactoring vs expansion | If (la + ld) == 0: 0.0 | **Retained** |
| `files_per_subsystem` | Derived | File dispersion intensity within subsystems. | `nf / ns` | Subsystem concentration | If ns == 0: 0.0 | **Retained** |
| `directories_per_file` | Derived | Directory dispersion ratio per changed file. | `nd / nf` | Structural scattering | If nf == 0: 0.0 | **Retained** |
| `experience_gap` | Derived | Gap between historical and recent author activity. | `max(0, aexp - arexp)` | Author decay/inactivity proxy | aexp >= arexp >= 0 | **Retained** |
| `log1p_la` | Transformed | Natural logarithm of lines added plus 1. | `log(la + 1)` | Compress heavy right skew | la >= 0 | **Retained** |
| `log1p_ld` | Transformed | Natural logarithm of lines deleted plus 1. | `log(ld + 1)` | Compress heavy right skew | ld >= 0 | **Retained** |
| `log1p_total_lines_changed` | Transformed | Natural logarithm of total lines changed plus 1. | `log(total_lines + 1)` | Compress heavy right skew | total_lines >= 0 | **Retained** |
| `log1p_age` | Transformed | Natural logarithm of file age metric plus 1. | `log(age + 1)` | Linearize aging curves | age >= 0 | **Retained** |
| `log1p_nuc` | Transformed | Natural logarithm of prior changes plus 1. | `log(nuc + 1)` | Compress heavy right skew | nuc >= 0 | **Retained** |
| `log1p_aexp` | Transformed | Natural logarithm of author experience plus 1. | `log(aexp + 1)` | Diminishing marginal experience | aexp >= 0 | **Retained** |
| `log1p_arexp` | Transformed | Natural logarithm of recent author experience plus 1. | `log(arexp + 1)` | Diminishing marginal experience | arexp >= 0 | **Retained** |
| `log1p_asexp` | Transformed | Natural logarithm of author subsystem experience plus 1. | `log(asexp + 1)` | Diminishing marginal experience | asexp >= 0 | **Retained** |

## Excluded Columns Summary

| Column | Exclusion Reason | Handling |
|---|---|---|
| `commit_id` | Unique SHA hash; 100% cardinality leads to spurious memorization. | Retained only in label file for traceability. |
| `buggy` | Ground truth prediction target. Direct leakage if included in features. | Stored in separate label file. |
| `fix` | Identifies if commit fixes a prior bug report; target-construction bias. | Excluded from default feature set. |
| `year` | Temporal marker; tree models split on historical year rather than code metrics. | Reserved for temporal partitioning. |
| `author_date` | Unix timestamp; leads to temporal shortcut learning. | Reserved for temporal audit. |
| `project` | Categorical repository identifier (15 Apache projects). | Reserved for domain generalization experiments. |
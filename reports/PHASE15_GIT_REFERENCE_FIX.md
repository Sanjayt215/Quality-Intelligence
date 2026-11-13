# Phase 15 — Git Reference Resolution & Branch Discovery Architecture

## 1. Executive Summary

During real-repository pilot testing against `C:\QI-Pilot\commons-lang`, invoking batch analysis on remote tracking branch `LANG_2_2_X [remote]` failed catastrophically with HTTP 422 and low-level Git failure:
```
fatal: ambiguous argument 'LANG_2_2_X': unknown revision or path not in the working tree.
```

This report documents the architectural root cause and the design and implementation of the robust, cross-platform Git reference resolution engine implemented in `src/git_analyzer.py`.

---

## 2. Root Cause Analysis

### 2.1 Branch Discovery Truncation
In previous iterations, `get_repository_branches()` enumerated Git references using `git branch -a`. For remote branches like `remotes/origin/LANG_2_2_X`, the parser stripped `remotes/origin/` or `origin/` and yielded `name = "LANG_2_2_X"`, with a formatted UI label `LANG_2_2_X [remote]`.

### 2.2 Unqualified Reference Lookup Failure
In a cloned Git repository where the user has not explicitly run `git checkout --track origin/LANG_2_2_X`, no local reference exists under `refs/heads/LANG_2_2_X`. 
When the frontend submitted `{"branch": "LANG_2_2_X"}` or `{"branch": "LANG_2_2_X [remote]"}`, the backend executed:
```bash
git log -n10 --format=... LANG_2_2_X --
```
Because `LANG_2_2_X` is neither a local branch, a tag, nor a valid revision name without its remote prefix (`origin/LANG_2_2_X`), Git returned exit code 128:
`fatal: ambiguous argument 'LANG_2_2_X': unknown revision or path not in the working tree.`

Furthermore, if the frontend sent the annotated display string `"LANG_2_2_X [remote]"`, Git attempted to resolve the literal string containing whitespace and brackets, failing immediately.

---

## 3. Reference Resolution Engine (`resolve_git_reference`)

To ensure deterministic, error-free resolution of any branch or commit identifier across any local or remote topology, `resolve_git_reference()` was implemented in [src/git_analyzer.py](file:///c:/Users/sanja/Downloads/Data_Analytic_Project/src/git_analyzer.py).

### 3.1 Input Normalization & Annotation Stripping
The resolver first sanitizes input strings, stripping UI cosmetic annotations and whitespace:
```python
clean_ref = ref_input.strip()
clean_ref = re.sub(r"\s*\[remote\]\s*$", "", clean_ref, flags=re.IGNORECASE)
clean_ref = re.sub(r"\s*\(current\)\s*$", "", clean_ref, flags=re.IGNORECASE)
clean_ref = clean_ref.strip()
```

### 3.2 Candidate Hierarchy
The resolver attempts resolution across an ordered sequence of candidate formats:
1. `clean_ref` directly (e.g. `master`, `origin/LANG_2_2_X`, `refs/remotes/origin/LANG_2_2_X`, commit SHA)
2. `refs/heads/{clean_ref}` (Local branches)
3. `refs/remotes/{remote}/{clean_ref}` (Remote tracking branches using discovered remotes e.g. `origin`)
4. `{remote}/{clean_ref}` (Standard shorthand remote ref e.g. `origin/master`)
5. `refs/tags/{clean_ref}` (Lightweight and annotated tags)
6. `HEAD` (Current active checkout)

### 3.3 Commit Verification via `git rev-parse`
For each candidate, the resolver invokes:
```powershell
git rev-parse --verify "<candidate>^{commit}"
```
Quoting `^{commit}` ensures compatibility with Windows PowerShell (which otherwise intercepts `{...}` as a scriptblock). This ensures the candidate resolves to an actual commit object, rejecting directories, missing trees, or ambiguous arguments.

### 3.4 Symbolic Full-Name Resolution
Once verified, the canonical ref name is extracted via:
```powershell
git rev-parse --symbolic-full-name "<candidate>"
```
If this returns a full ref (e.g. `refs/remotes/origin/LANG_2_2_X`), the engine parses whether it is a remote tracking branch (`is_remote=True`), identifies the remote (`origin`), and extracts the clean branch name.

### 3.5 Typed Contract
`resolve_git_reference()` returns a strictly structured dictionary:
```python
{
    "display_name": "origin/LANG_2_2_X [remote]",
    "branch_name": "LANG_2_2_X",
    "git_ref": "refs/remotes/origin/LANG_2_2_X",
    "commit_sha": "ff612dc5f284b125efdf97b9ee967816ef062a72",
    "is_remote": True,
    "remote_name": "origin"
}
```

---

## 4. Branch Discovery Architecture (`get_repository_branches`)

The branch enumeration endpoint was upgraded in [src/git_analyzer.py](file:///c:/Users/sanja/Downloads/Data_Analytic_Project/src/git_analyzer.py) to provide complete ref metadata to clients:

1. **`git branch -a --format=%(refname)|||%(objectname)|||%(HEAD)`**:
   Enumerates all local and remote branches in a single atomic Git call.
2. **Metadata Enrichment**:
   - `clean_name`: Unprefixed branch name (e.g. `LANG_2_2_X`).
   - `display_name`: Human-readable label (e.g. `LANG_2_2_X [remote]` or `master (Current)`).
   - `branch_name`: Fully qualified or shorthand branch ref.
   - `ref` / `git_ref`: Fully qualified symbolic ref (`refs/remotes/origin/LANG_2_2_X`).
   - `commit_sha`: Top commit SHA of the branch tip.
   - `is_current`: Boolean flag indicating if branch matches current `HEAD`.
   - `is_remote`: Boolean flag distinguishing remote tracking branches from local heads.
   - `remote_name`: Associated remote (`origin` or custom).

---

## 5. Commit Discovery Pipeline (`get_repository_commits`)

### 5.1 Cross-Platform Delimited Log Parsing
Windows subprocess environments fail with `ValueError: embedded null byte` when `\x00` is used inside format strings. The commit discovery pipeline uses a robust triple-pipe delimiter (`|||`):
```bash
git log -n<count> --format=%H|||%h|||%an|||%ae|||%at|||%P|||%s <resolved_git_ref> --
```

### 5.2 Commit Metadata Extraction
For each discovered commit:
- `%H`: Full 40-character commit SHA.
- `%h`: Abbreviated commit SHA (8 characters).
- `%an`: Author name.
- `%ae`: Author email.
- `%at`: Unix epoch commit timestamp.
- `%P`: Space-separated list of parent commit SHAs.
- `%s`: Commit subject line.

Parent hashes are split to calculate `parent_count` and flag `is_merge = parent_count > 1`.
`branch_name` and canonical `git_ref` are attached to each commit metadata object.

---

## 6. Verification Summary

The resolver was verified across 6 distinct reference patterns in `C:\QI-Pilot\commons-lang`:
1. Local branch: `master` -> `refs/heads/master` (Resolved)
2. UI annotated remote: `LANG_2_2_X [remote]` -> `refs/remotes/origin/LANG_2_2_X` (Resolved)
3. Bare remote: `LANG_2_2_X` -> `refs/remotes/origin/LANG_2_2_X` (Resolved)
4. Full remote: `origin/LANG_2_2_X` -> `refs/remotes/origin/LANG_2_2_X` (Resolved)
5. Full symbolic: `refs/remotes/origin/LANG_2_2_X` -> Verified commit SHA `ff612dc5...` (Resolved)
6. Non-existent branch: `nonexistent_branch_xyz` -> Deterministic HTTP 422 with descriptive error message (Handled cleanly).

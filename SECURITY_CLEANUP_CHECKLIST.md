# Security Cleanup Checklist
## Pre-Deployment Data Breach Remediation

**Severity:** CRITICAL  
**Deadline:** Complete before any commit/deployment  
**Reviewer:** Codex Adversarial Review  

---

## Phase 1: Remove Customer Data from Working Tree

### 1.1 Delete Debug Artifacts
```bash
# Remove OCR debug directory with customer PII
rm -rf backend/debug_markdown/

# Remove test result files
rm -rf backend/tests/test_results/

# Remove benchmark data directories
rm -rf backend/tests/e4b_test_data/
```

**Verification:**
- [ ] `backend/debug_markdown/` directory deleted
- [ ] `backend/tests/test_results/` deleted
- [ ] `backend/tests/e4b_test_data/` deleted
- [ ] No `.md` files with customer data remain in backend/

### 1.2 Remove Problematic Test Scripts
```bash
# These scripts hardcode external endpoints (security risk)
rm backend/tests/run_ab_benchmark.py
rm backend/tests/run_ab_benchmark_fixed.py
rm backend/tests/populate_ground_truth.py
```

**Verification:**
- [ ] `run_ab_benchmark*.py` deleted
- [ ] `populate_ground_truth.py` deleted
- [ ] `backend/tests/` contains only safe test files

### 1.3 Update .gitignore
**File:** `.gitignore` (add these lines)

```
# Test artifacts with customer data
backend/debug_markdown/
backend/tests/test_results/
backend/tests/e4b_test_data/
backend/tests/*.benchmark
test_results/
benchmark_sample_*.csv

# OCR outputs (may contain PII)
*.ocr.md
*.ocr.txt

# Debug files
debug_*/
*.debug.*
```

**Verification:**
- [ ] `.gitignore` updated with all artifact patterns
- [ ] File is committed to prevent re-introduction

---

## Phase 2: Clean Git History

### 2.1 Check for Leaked Data in History
```bash
# Search git history for customer PII patterns
git log --all -S "GSTIN" --oneline
git log --all -S "delivery_address" --oneline
git log --all -S "backend/debug_markdown" --oneline
```

**Verification:**
- [ ] Run command and document findings
- [ ] Note which commits contain leaks
- [ ] If none found: proceed to 2.2
- [ ] If found: escalate to 2.3

### 2.2 No Leaks Found (Expected Case)
If git history is clean:

```bash
# Just verify the files are gone from HEAD
git status
# Should show deleted files, no untracked PII files
```

**Verification:**
- [ ] `git status` shows only deletions
- [ ] No untracked files with `.md` content visible
- [ ] Ready to commit cleanup

### 2.3 Leaks Found in History (If Applicable)
If customer data was committed:

```bash
# OPTION A: Use git-filter-branch (careful, rewrites history)
git filter-branch --tree-filter 'rm -rf backend/debug_markdown' HEAD

# OPTION B: Use BFG Repo Cleaner (safer, faster)
# Follow: https://rtyley.github.io/bfg-repo-cleaner/
bfg --delete-folders backend/debug_markdown .

# OPTION C: Create a new clean repository (cleanest)
git clone --bare <repo> <repo>.clean.git
cd <repo>.clean.git
# Use filter-branch or BFG
# Then mirror-push to restore
```

**Verification (after cleaning history):**
- [ ] Verify no data remains: `git log --all -S "GSTIN"` returns nothing
- [ ] Verify HEAD is clean: `git show HEAD:backend/debug_markdown/` fails
- [ ] Force push to origin (ONLY after verification): `git push -f origin master`
- [ ] Alert team: "Git history rewritten, force-fetch required"

---

## Phase 3: Redesign Benchmark for Local-Only Operation

### 3.1 Create Local Benchmark Framework
**File:** `backend/tests/local_benchmark_runner.py` (NEW)

Requirements:
- [ ] No external endpoints hardcoded
- [ ] Require explicit local Ollama configuration
- [ ] Block execution unless running on local machine
- [ ] Use synthetic/test documents only (no customer data)
- [ ] Write results to immutable log file (never overwrites)

**Template:**
```python
"""
Local Benchmark Runner
- Connects to local Ollama only
- Never sends data outside boundary
- Uses test documents (not production)
"""

import os
from pathlib import Path

# SAFETY: Only local endpoints allowed
ALLOWED_ENDPOINTS = [
    "http://localhost:11434",
    "http://127.0.0.1:11434",
]

def validate_endpoint(endpoint: str) -> bool:
    """Ensure endpoint is local, not external"""
    if not endpoint.startswith("http://localhost") and \
       not endpoint.startswith("http://127.0.0.1"):
        raise ValueError(f"SECURITY: Only local endpoints allowed, got {endpoint}")
    return True

def run_local_benchmark():
    """Run benchmark using ONLY local models"""
    endpoint = os.getenv("OLLAMA_ENDPOINT", "http://localhost:11434")
    
    # Validate safety
    validate_endpoint(endpoint)
    
    # Use test documents only
    test_docs_dir = Path("backend/tests/fixtures/test_documents/")
    if not test_docs_dir.exists():
        raise FileNotFoundError("Test documents not found. Use synthetic data only.")
    
    # Run benchmark...
    # Write results to immutable log
    results_dir = Path("backend/tests/results/") / datetime.now().isoformat()
    results_dir.mkdir(parents=True, exist_ok=True)
    
    # Never overwrite, only append
    # ...
```

**Verification:**
- [ ] Script validates local endpoint only
- [ ] Script refuses to run with external endpoints
- [ ] Script uses test data directory (no customer documents)
- [ ] Results written to timestamped, immutable files
- [ ] README documents: "This benchmark uses synthetic test data only"

### 3.2 Create Immutable Ground Truth
**File:** `backend/tests/fixtures/benchmark_ground_truth.csv` (IMMUTABLE)

Requirements:
- [ ] Use only synthetic/test documents (no customer data)
- [ ] Document sources clearly (e.g., "synthetic PO template")
- [ ] Commit to version control (immutable reference)
- [ ] Never programmatically modify

**Example rows:**
```csv
document_id,file_name,document_type,expected_po_number,expected_amount,source
doc_synthetic_001,test_po_basic.pdf,CUSTOMER_PO,TEST-PO-001,100000,Synthetic template
doc_synthetic_002,test_invoice_complex.pdf,VENDOR_INVOICE,TEST-INV-002,250000,Synthetic template
# Real customer documents: NEVER include in version control
```

**Verification:**
- [ ] No real customer references
- [ ] All sources marked as "Synthetic" or "Test"
- [ ] File committed to git (immutable)
- [ ] Protected branch rule: cannot modify via script

### 3.3 Separate Model Output from Ground Truth
**File:** `backend/tests/results/<timestamp>/candidates.csv` (MUTABLE)

When benchmarking:
1. Read immutable ground truth: `benchmark_ground_truth.csv`
2. Run extraction on test documents
3. Write model output to: `results/<timestamp>/candidates.csv`
4. Compare: ground_truth vs candidates
5. Document accuracy deltas
6. **NEVER update ground_truth.csv from model output**

**Verification:**
- [ ] Results directory is timestamped (prevents overwrites)
- [ ] Ground truth never touched by scripts
- [ ] Benchmark output is separate, readable CSV
- [ ] Git ignores results/ directory

### 3.4 Add Safety Guards to Config
**File:** `backend/app/config.py`

```python
# SECURITY: Benchmark safety gates
BENCHMARK_MODE_ALLOWED = os.getenv("BENCHMARK_MODE", "false").lower() == "true"
BENCHMARK_ENDPOINT = os.getenv("OLLAMA_ENDPOINT", "http://localhost:11434")

def validate_benchmark_config():
    """Ensure benchmarks cannot leak customer data"""
    if BENCHMARK_MODE_ALLOWED:
        # Only local endpoints
        if "localhost" not in BENCHMARK_ENDPOINT and "127.0.0.1" not in BENCHMARK_ENDPOINT:
            raise RuntimeError("Benchmark mode requires local Ollama endpoint only")
        # Log for audit
        logger.warning("BENCHMARK MODE ACTIVE - Using synthetic data only")
```

**Verification:**
- [ ] Config validates endpoint on startup
- [ ] Benchmark mode requires explicit opt-in
- [ ] Warnings logged for audit trail
- [ ] Production deployments: BENCHMARK_MODE=false (default)

---

## Phase 4: Address Original Codex Blockers

These were from the earlier adversarial review. Must fix before shipping:

### 4.1 PO Detail → Profile Navigation Failure
**Status:** ⏳ NOT YET FIXED

**Task:**
- [ ] Reproduce: Open PO detail page → click Profile link → observe error
- [ ] Identify root cause (server error, API response, frontend navigation)
- [ ] Create fix + test
- [ ] Verify: No server-error toasts in console
- [ ] Verify: Profile page loads without "Failed to load profile" message

**Blocking:** Cannot deploy until fixed (breaks main workflow)

### 4.2 Confidence Objects Leaking into UI
**Status:** ⏳ PARTIALLY FIXED

**Task:**
- [ ] Verify document chain displays clean strings (no `{'value': ...}`)
- [ ] Verify warning messages show clean values (no confidence dicts)
- [ ] Verify review-panel fields show clean data
- [ ] Search all UI components for remaining leaks
- [ ] Run regex: grep for `{'value'` in frontend/src/ → should find 0 results
- [ ] Test: Load document with extracted data → verify UI rendering

**Blocking:** Cannot deploy with data leaks

### 4.3 Chat/Assistant 403 Blocker
**Status:** ⏳ UNDETERMINED

**Task:**
- [ ] Check: Is Chat module in MVP scope?
  - [ ] YES → Fix 403 endpoint + test
  - [ ] NO → Remove from navigation (gate it behind feature flag)
- [ ] If YES:
  - [ ] Verify chat endpoint reachable (no 403)
  - [ ] Test with gemma4:e4b model
  - [ ] Verify vision capability works (image upload)
- [ ] If NO:
  - [ ] Add feature flag: `ENABLE_CHAT=false` (default for MVP)
  - [ ] Hide Chat nav link
  - [ ] Document: "Chat deferred to post-MVP"

**Blocking:** If in scope, must be functional. If out of scope, must be hidden.

---

## Phase 5: Security Audit

### 5.1 Scan for Remaining PII in Codebase
```bash
# Search for customer data patterns
grep -r "GSTIN" backend/ frontend/ --include="*.py" --include="*.ts"
grep -r "delivery_address" backend/ frontend/ --include="*.py" --include="*.ts"
grep -r "1PTR\|1DNT\|1ITR" backend/ frontend/  # Real doc references
grep -r "proxy.runpod.net" backend/ frontend/  # External endpoints
```

**Verification:**
- [ ] All grep searches return 0 results (or only in comments)
- [ ] No customer references in code
- [ ] No external endpoints hardcoded
- [ ] Document results in security audit log

### 5.2 Verify .gitignore Effectiveness
```bash
# Check that artifacts would be ignored going forward
git check-ignore -v backend/debug_markdown/*
git check-ignore -v test_results/*
```

**Verification:**
- [ ] Files matching patterns are marked as ignored
- [ ] Future accidental commits prevented

### 5.3 Review Benchmark Documentation
**File:** `backend/tests/README.md` (NEW or UPDATED)

Must document:
- [ ] "This benchmark uses SYNTHETIC DATA ONLY"
- [ ] "Ground truth is immutable and version-controlled"
- [ ] "Model outputs written to separate timestamped directory"
- [ ] "Never modify expected values programmatically"
- [ ] "Local Ollama endpoint required (no external services)"

---

## Phase 6: Final Verification & Commit

### 6.1 Clean Git Status
```bash
git status
```

**Should show:**
- [ ] All problematic files deleted
- [ ] Only modified: `.gitignore`, new safe scripts, documentation
- [ ] No untracked files with customer data
- [ ] No debug artifacts

### 6.2 Create Cleanup Commit
```bash
git add .gitignore backend/tests/local_benchmark_runner.py backend/tests/README.md
git commit -m "security: remove customer PII from benchmark artifacts and git history

- Delete backend/debug_markdown/ (contained customer GSTIN, addresses, contact info)
- Delete run_ab_benchmark*.py scripts (hardcoded external RunPod endpoint)
- Delete populate_ground_truth.py (overwrites canonical benchmark data)
- Add .gitignore patterns to prevent re-introduction of artifacts
- Redesign benchmark: local-only with immutable synthetic ground truth
- Separate model output (candidates.csv) from human-curated ground truth
- Add safety guards: validate local endpoint, block external access
- Document benchmark methodology: synthetic data only, never overwrite truth

Security: Prevents customer data exfiltration to external services.
Compliance: Ensures on-prem data boundary respected.
"
```

**Verification:**
- [ ] Commit message references security fixes
- [ ] Only safe files included
- [ ] Commit history is clean (no rebasing needed)

### 6.3 Final Codex Review (Optional)
```bash
codex review --base development
```

Should now show: ✅ **SHIP-READY** (no blockers)

**Verification:**
- [ ] No high-severity findings
- [ ] No PII detected
- [ ] No external endpoint references
- [ ] Safe to commit and deploy

---

## Timeline

| Phase | Task | Owner | Estimated Time |
|-------|------|-------|-----------------|
| 1 | Remove artifacts | You | 15 min |
| 2 | Clean git history | You | 30 min (if needed) |
| 3 | Redesign benchmark | You | 2-3 hours |
| 4 | Fix original blockers | Team | 4-6 hours |
| 5 | Security audit | You | 1 hour |
| 6 | Final verification | You | 30 min |
| **TOTAL** | | | **8-12 hours** |

---

## Sign-Off

Once completed:

- [ ] All phases done
- [ ] Codex review: SHIP-READY
- [ ] Security audit: PASSED
- [ ] Original blockers: FIXED
- [ ] Ready for RTX 4090 deployment

**Approved by:** ________________  
**Date:** ________________


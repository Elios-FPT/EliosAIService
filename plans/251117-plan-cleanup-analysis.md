# Plan Directory Cleanup Analysis

**Analysis Date**: 2025-11-17
**Current State**: 123 files across 28 directories
**Target**: Streamlined structure with essential files only

---

## Executive Summary

Plans directory contains significant redundancy with:
- **Duplicate directory structures** (8 directories contain only empty reports/ subdirs)
- **Scattered completion markers** (12 different STATUS/COMPLETE/SUMMARY files)
- **Mixed naming conventions** (dated vs descriptive names)
- **Historical cruft** (bug fix reports from weeks ago)
- **Inconsistent organization** (some plans have README.md, others plan.md, some both)

**Recommendation**: Archive completed plans, consolidate active work, establish consistent structure.

---

## Current Structure Analysis

### 1. Plan Directories (28 total)

#### A. Dated Plan Directories (13)
**Pattern**: `YYMMDD-HHMM-feature-name/`

| Directory | Status | Files | Recommendation |
|-----------|--------|-------|----------------|
| `251102-interview-api-websocket-implementation-plan.md` | Single file | 1 | Move to archive/ |
| `251106-2142-adaptive-interview-planning/` | ✅ Complete | 9 | **KEEP** - Reference implementation |
| `251107-2339-adapter-mocking/` | ✅ Complete | 7 | **KEEP** - Reference implementation |
| `251110-documentation-updates/` | Complete | 1 | Move to archive/ |
| `251111-1458-refactor-plan-interview-flow/` | Complete | 6 | Move to archive/ |
| `251112-0022-realtime-interview-enhancement/` | Complete | 10 | Move to archive/ |
| `251112-2117-domain-driven-state-management/` | Complete | 11 | **KEEP** - Important refactoring reference |
| `251114-0205-evaluation-refactoring/` | Unknown | ? | Verify status, archive if complete |
| `251114-1503-refactor-complete-interview-use-case/` | Complete | 5 | Move to archive/ |
| `251115-0107-websocket-url-in-plan-response/` | Complete | 4 | Move to archive/ |
| `251115-0406-voice-support-integration/` | ✅ Complete | 7 | **KEEP** - Reference implementation |
| `251115-0717-qa-question-constraints/` | ✅ Complete | 6 | **KEEP** - Recent, useful reference |
| `251116-2345-langchain-langgraph-integration/` | 🔄 Active | ? | **KEEP** - Current work |

#### B. Descriptive Name Directories (8)
**Pattern**: `feature-name/` (only contains reports/ subdir)

| Directory | Purpose | Recommendation |
|-----------|---------|----------------|
| `adaptive-interview-implementation/` | Reports only | **DELETE** - Merge into 251106-2142 |
| `complete-interview-refactoring/` | Reports only | **DELETE** - Merge into 251114-1503 |
| `phase-5-session-orchestration/` | Reports only | **DELETE** - Merge into 251112-0022 |
| `phase6-final-summary-generation/` | Reports only | **DELETE** - Merge into 251112-0022 |
| `qa-question-constraint-testing/` | Reports only | **DELETE** - Merge into 251115-0717 |
| `question-generation/` | Reports only | **DELETE** - Archive |
| `websocket-integration/` | Reports only | **DELETE** - Merge into 251102 |
| `ws-url-planning-response/` | Reports only | **DELETE** - Merge into 251115-0107 |

#### C. Bug Fix Directories (3)
**Pattern**: `bug-description/`

| Directory | Date | Recommendation |
|-----------|------|----------------|
| `attribution-error-analysis/` | 251109 | **DELETE** - Bug fixed, historical only |
| `ea-6-fix-followup-attribute/` | 251109 | **DELETE** - Bug fixed, historical only |
| `mapper-fix/` | 251108 | **DELETE** - Bug fixed, historical only |

#### D. Shared Directories (3)

| Directory | Purpose | Recommendation |
|-----------|---------|----------------|
| `reports/` | Cross-plan reports (5 files) | **KEEP** - Consolidate orphaned reports here |
| `test-reports/` | Test execution reports (1 file) | **MERGE** into reports/ |
| `templates/` | Plan templates (3 files) | **KEEP** - Active templates |

---

## File Type Analysis

### Completion Markers (12 files)
**Problem**: Inconsistent naming, redundant information

| File Type | Count | Examples |
|-----------|-------|----------|
| `IMPLEMENTATION_COMPLETE.md` | 4 | Voice integration, QA constraints, Adaptive planning |
| `PHASE1-PHASE2-COMPLETE.md` | 1 | Adapter mocking |
| `STATUS.md` | 1 | QA constraints |
| `STATUS_REPORT.md` | 1 | Complete interview refactoring |
| `SUMMARY.md` | 2 | Adapter mocking, Domain state management |
| `IMPLEMENTATION_SUMMARY.md` | 1 | Domain state management |
| `HANDOFF.md` | 1 | Domain state management |
| `CHANGELOG.md` | 1 | Domain state management |

**Recommendation**: Standardize on single `STATUS.md` per plan with completion info.

### Plan Files (15)
**Problem**: Inconsistent naming (plan.md vs README.md)

| Pattern | Count | Recommendation |
|---------|-------|----------------|
| `plan.md` | 10 | **STANDARD** - Use for all plans |
| `README.md` | 5 | Convert to `plan.md` or delete if duplicate |
| Both | 4 | Keep `plan.md`, delete `README.md` if redundant |

### Reports (50+ files)
**Problem**: Scattered across 19 `reports/` subdirectories

**Patterns**:
- Code reviews: `251XXX-code-review-*.md`
- Implementation summaries: `251XXX-implementation-summary.md`
- Test reports: `251XXX-test-*.md`
- Agent handoffs: `251XXX-from-X-to-Y-*.md`

**Recommendation**: Consolidate into plan-specific `reports/` or global `reports/` based on scope.

---

## Redundancy Analysis

### 1. Duplicate Directory Structures (8 cases)

| Dated Directory | Descriptive Duplicate | Action |
|-----------------|----------------------|--------|
| `251106-2142-adaptive-interview-planning/` | `adaptive-interview-implementation/` | Merge descriptive → dated |
| `251114-1503-refactor-complete-interview-use-case/` | `complete-interview-refactoring/` | Merge descriptive → dated |
| `251112-0022-realtime-interview-enhancement/` | `phase-5-session-orchestration/` + `phase6-final-summary-generation/` | Merge both → dated |
| `251115-0717-qa-question-constraints/` | `qa-question-constraint-testing/` | Merge descriptive → dated |
| `251102-interview-api-websocket-implementation-plan.md` | `websocket-integration/` | Merge descriptive → dated |
| `251115-0107-websocket-url-in-plan-response/` | `ws-url-planning-response/` | Merge descriptive → dated |

### 2. Historical Bug Fixes (3 directories)
**All from early November, bugs already fixed**:
- `attribution-error-analysis/` (251109)
- `ea-6-fix-followup-attribute/` (251109)
- `mapper-fix/` (251108)

**Value**: Minimal - root cause analyses useful but not plan-worthy.

**Action**: Extract key lessons to docs/, delete directories.

---

## Recommended Structure

### New Organization

```
plans/
├── active/                          # Current work only
│   └── 251116-2345-langchain-langgraph-integration/
│       ├── plan.md
│       ├── phase-00-prototypes-benchmarks.md
│       ├── phase-01-langchain-adapter.md
│       ├── reports/
│       ├── research/
│       └── scout/
│
├── archive/                         # Completed plans (reference only)
│   ├── 2025-11/                    # Organize by month
│   │   ├── 251106-adaptive-interview-planning/
│   │   ├── 251107-adapter-mocking/
│   │   ├── 251112-domain-state-management/
│   │   ├── 251115-voice-support/
│   │   └── 251115-qa-constraints/
│   │
│   └── 2025-10/                    # Historical
│       └── (older plans if any)
│
├── bug-fixes/                       # Historical bug analyses
│   └── 2025-11/
│       ├── 251108-mapper-fix.md
│       ├── 251109-attribution-error.md
│       └── 251109-followup-attribute.md
│
├── reports/                         # Cross-plan reports
│   ├── 251102-project-manager-completion-summary.md
│   ├── 251102-interview-api-code-review.md
│   └── (other cross-cutting reports)
│
└── templates/                       # Plan templates
    ├── feature-implementation-template.md
    ├── bug-fix-template.md
    ├── refactor-template.md
    └── template-usage-guide.md
```

### File Naming Standards

**Plans**: Always `plan.md` (not README.md)
**Status**: Single `STATUS.md` with completion metadata
**Reports**: `YYMMDD-HHMM-report-type-description.md`
**Phases**: `phase-NN-description.md` (zero-padded)

---

## Cleanup Actions

### Phase 1: Immediate Cleanup (LOW RISK)

**Delete empty report directories** (8 directories):
```bash
rm -rf plans/adaptive-interview-implementation/
rm -rf plans/complete-interview-refactoring/
rm -rf plans/phase-5-session-orchestration/
rm -rf plans/phase6-final-summary-generation/
rm -rf plans/qa-question-constraint-testing/
rm -rf plans/question-generation/
rm -rf plans/websocket-integration/
rm -rf plans/ws-url-planning-response/
```

**Delete bug fix directories** (3 directories):
```bash
# Extract lessons learned first (optional)
cat plans/attribution-error-analysis/QUICK-FIX-GUIDE.md >> docs/troubleshooting.md
cat plans/ea-6-fix-followup-attribute/251109-root-cause-analysis-report.md >> docs/troubleshooting.md

# Then delete
rm -rf plans/attribution-error-analysis/
rm -rf plans/ea-6-fix-followup-attribute/
rm -rf plans/mapper-fix/
```

**Consolidate test reports**:
```bash
mv plans/test-reports/* plans/reports/
rm -rf plans/test-reports/
```

**Result**: 123 → ~100 files, 28 → 16 directories

---

### Phase 2: Archive Completed Plans (MEDIUM RISK)

**Create archive structure**:
```bash
mkdir -p plans/archive/2025-11
```

**Move completed plans**:
```bash
# Less critical completed plans
mv plans/251110-documentation-updates plans/archive/2025-11/
mv plans/251111-1458-refactor-plan-interview-flow plans/archive/2025-11/
mv plans/251112-0022-realtime-interview-enhancement plans/archive/2025-11/
mv plans/251114-0205-evaluation-refactoring plans/archive/2025-11/
mv plans/251114-1503-refactor-complete-interview-use-case plans/archive/2025-11/
mv plans/251115-0107-websocket-url-in-plan-response plans/archive/2025-11/
mv plans/251102-interview-api-websocket-implementation-plan.md plans/archive/2025-11/
```

**Keep in root** (reference implementations, <1 month old):
- `251106-2142-adaptive-interview-planning/` (important pattern reference)
- `251107-2339-adapter-mocking/` (mock adapter patterns)
- `251112-2117-domain-driven-state-management/` (state management patterns)
- `251115-0406-voice-support-integration/` (recent, voice reference)
- `251115-0717-qa-question-constraints/` (recent, QA patterns)
- `251116-2345-langchain-langgraph-integration/` (ACTIVE)

**Result**: ~100 → ~85 files, 16 → 10 directories at root

---

### Phase 3: Standardize File Naming (LOW RISK)

**Consolidate completion markers**:
```bash
# For each plan, consolidate into single STATUS.md
# Example for 251115-0406-voice-support-integration:
cat plans/251115-0406-voice-support-integration/IMPLEMENTATION_COMPLETE.md > \
    plans/251115-0406-voice-support-integration/STATUS.md
rm plans/251115-0406-voice-support-integration/IMPLEMENTATION_COMPLETE.md
```

**Convert README.md to plan.md** (where both exist):
```bash
# If README.md is duplicate of plan.md:
rm plans/251116-2345-langchain-langgraph-integration/README.md

# If README.md is navigational (keep as index):
# Keep both, clarify purpose in each file
```

**Result**: Consistent naming, easier navigation

---

### Phase 4: Create Active Directory (OPTIONAL)

**Move current work to active/**:
```bash
mkdir -p plans/active
mv plans/251116-2345-langchain-langgraph-integration plans/active/
```

**Update references in code/docs** to point to new locations.

**Result**: Clear separation of active vs reference vs archive

---

## File Retention Policy

### Keep Permanently
- **Active plans** (1-2 max at any time)
- **Reference implementations** (last 3-5 major features)
- **Templates** (all)
- **Cross-plan reports** (architecture decisions, completion summaries)

### Archive After Completion
- **Feature plans** older than 1 month
- **Refactoring plans** after verification period
- **Bug fixes** after fix deployed for 2 weeks

### Delete After Archive Period (6 months)
- **Routine bug fixes** (keep lessons in docs/)
- **Failed experiments** (document why in docs/adr/)
- **Superseded plans** (if implementation changed significantly)

---

## Benefits of Cleanup

### Before
- 123 files across 28 directories
- 8 empty directories (reports-only)
- 12 different completion marker formats
- Inconsistent naming (plan.md vs README.md)
- Scattered bug fix analyses

### After (Phase 1-3)
- ~70 active/reference files in 10 root directories
- 0 empty directories
- 1 standard completion format (STATUS.md)
- Consistent naming (plan.md for plans)
- Bug fixes consolidated in docs/

### Improvements
- **50% reduction** in file count
- **60% reduction** in root directory count
- **Faster navigation** (active vs archive clear)
- **Consistent structure** (easier onboarding)
- **Better discoverability** (predictable file names)

---

## Migration Checklist

**Pre-cleanup**:
- [ ] Backup plans/ directory
- [ ] Review git history (ensure nothing in unstaged)
- [ ] Identify truly active plans (currently: 251116-2345)

**Phase 1 Execution** (15 min):
- [ ] Delete 8 empty report directories
- [ ] Delete 3 bug fix directories (extract lessons first)
- [ ] Merge test-reports/ into reports/
- [ ] Verify git status clean

**Phase 2 Execution** (30 min):
- [ ] Create archive/2025-11/
- [ ] Move 7 completed plans to archive
- [ ] Verify 6 reference plans remain at root
- [ ] Update any hardcoded paths in code/docs

**Phase 3 Execution** (20 min):
- [ ] Consolidate completion markers → STATUS.md
- [ ] Handle README.md duplicates
- [ ] Verify consistent naming
- [ ] Update CLAUDE.md if needed

**Post-cleanup**:
- [ ] Commit changes with detailed message
- [ ] Update documentation with new structure
- [ ] Test plan references still work
- [ ] Document retention policy in CLAUDE.md

---

## Unresolved Questions

1. **Archive location**: Keep in repo (`plans/archive/`) or move to wiki/external storage?
2. **Retention period**: 6 months? 1 year? Indefinite for major features?
3. **Active directory**: Create `plans/active/` or keep active plans at root?
4. **Bug fix storage**: `docs/troubleshooting.md` or `plans/bug-fixes/YYMMDD-*.md`?
5. **Template versioning**: Keep old template versions or single latest?

---

## Risk Assessment

### Low Risk Actions
- Deleting empty directories (no content loss)
- Renaming files (git tracks renames)
- Moving to archive/ (easily reversible)

### Medium Risk Actions
- Deleting bug fix directories (ensure lessons captured)
- Consolidating completion markers (verify no unique info lost)

### High Risk Actions
- Deleting old plans entirely (check for references first)
- Changing directory structure (breaks hardcoded paths)

**Mitigation**: Execute phases incrementally, commit after each, verify before next.

---

## Recommended Next Steps

1. **User decision**: Approve Phase 1-3 cleanup approach
2. **User decision**: Resolve unresolved questions (archive location, retention period)
3. **Execute Phase 1**: Immediate cleanup (low risk, high value)
4. **Commit & verify**: Ensure no breakage
5. **Execute Phase 2-3**: Archive & standardize
6. **Document**: Update CLAUDE.md with new structure and retention policy

---

**Analysis Complete**: Ready for user review and approval
**Estimated Cleanup Time**: 1-2 hours (including testing)
**Risk Level**: Low (with git backup and incremental approach)

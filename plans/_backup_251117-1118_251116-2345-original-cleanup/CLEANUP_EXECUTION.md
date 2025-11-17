# Plan Cleanup - Execution Guide

**Date**: 2025-11-17
**Purpose**: Step-by-step instructions to achieve clean "original" plan structure
**Estimated Time**: 5-10 minutes

---

## Prerequisites

- [x] Read `CLEANUP_ANALYSIS.md` to understand rationale
- [ ] Current directory: `plans/251116-2345-langchain-langgraph-integration/`
- [ ] Git working tree clean (optional, but recommended)

---

## Execution Steps

### Step 0: Create Backup

**Why**: Safety net in case we need to rollback

**PowerShell**:
```powershell
cd "H:\AI-course\EliosAIService\plans\251116-2345-langchain-langgraph-integration"

$timestamp = Get-Date -Format "yyMMdd-HHmm"
$backupDir = "..\_backup_$timestamp`_251116-2345-original-cleanup"
Copy-Item -Recurse -Force "." $backupDir
Write-Host "✅ Backup created: $backupDir"
```

**Bash**:
```bash
cd /h/AI-course/EliosAIService/plans/251116-2345-langchain-langgraph-integration

timestamp=$(date +%y%m%d-%H%M)
backup_dir="../_backup_${timestamp}_251116-2345-original-cleanup"
cp -r . "$backup_dir"
echo "✅ Backup created: $backup_dir"
```

**Verification**: Check backup directory exists with all files

---

### Step 1: Consolidate Decision Rationale

**Goal**: Extract unique content from `plan-revision-summary.md` before deletion

**Action**: Append new section to `reports/architectural-decisions-final.md`

**Content to Append**:

```markdown

---

## Decision 3: Phase 3 Split Strategy

### Context
Original Phase 3 combined too many risky changes in a single phase:
- Human-in-loop interrupts (new pattern)
- WebSocket streaming integration (complex protocol)
- Thread ID persistence (new infrastructure)
- Orchestrator refactor (584 → 150 lines)

**Risk**: High likelihood of integration issues if implemented together

### Decision: Split into Phase 3A (Simple) + Phase 3B (Interrupts) ✅

**Rationale**:
Reduce risk by separating synchronous workflow validation from async streaming complexity.

**Phase 3A: Adaptive Workflow (Simple)**
- Duration: 1 week
- Risk: Medium (reduced from High)
- Scope:
  - Build LangGraph workflow WITHOUT interrupts
  - Run complete evaluation loop in single invocation
  - Keep existing WebSocket handler (no changes)
  - Validate StateGraph logic before adding complexity

**Phase 3B: WebSocket Interrupts**
- Duration: 1 week
- Risk: High (isolated to streaming layer)
- Scope:
  - Add interrupt nodes to Phase 3A workflow
  - Real-time WebSocket streaming via astream_events()
  - Thread ID persistence for resume capability
  - 10-minute checkpoint cleanup
- Dependencies: Phase 3A MUST complete successfully

**Benefits of Split Approach**:
1. **Easier Testing**: Phase 3A has synchronous, deterministic workflow (unit testable)
2. **Production Deployment**: Can deploy 3A safely without changing WebSocket protocol
3. **Risk Isolation**: WebSocket/interrupt complexity confined to Phase 3B
4. **Early Validation**: Validate StateGraph logic and performance in 3A before streaming
5. **De-risk 3B**: Workflow already working when adding interrupt layer

**Trade-offs**:
- ⚠️ +1 week timeline (5-7 weeks vs original 4-6 weeks)
- ⚠️ Phase 3A has throwaway WebSocket code (replaced in 3B)
- ✅ Acceptable: Extra week worth the risk reduction

**Implementation Timeline**:
```
Week 1-2: Phase 1 (LangChain Adapter)
Week 3-4: Phase 2 (Planning Workflow)
Week 5:   Phase 3A (Workflow without interrupts) ← Deploy to staging
Week 6:   Phase 3B (Add interrupts) ← Deploy to production
Week 7:   Phase 4 (Observability)
```

**Success Criteria (Phase 3A)**:
- ✅ StateGraph executes full evaluation loop
- ✅ Conditional edges work (max 3, similarity ≥0.8, no gaps)
- ✅ Checkpoint saves/restores correctly
- ✅ 80% reduction in orchestrator complexity achieved

**Success Criteria (Phase 3B)**:
- ✅ Interrupt nodes pause workflow correctly
- ✅ WebSocket streaming shows real-time progress
- ✅ Thread ID lookup enables session resume
- ✅ 10-minute cleanup task removes idle sessions

---

## Decision 4: Prompt Storage Location

### Context
Need to choose where to store LangChain prompt templates for the 13 LLMPort methods.

### Decision: PostgreSQL JSONB + Python Fallback ✅

(See Decision 1 above for full details)

**Key Point for Phase 3 Split**:
Prompt storage complexity isolated to Phase 1. By Phase 3, prompt infrastructure already stable.

---

## Summary of All Decisions

| # | Decision | Choice | Phase Impacted |
|---|----------|--------|----------------|
| 1 | Prompt Storage | PostgreSQL JSONB + Python fallback | Phase 1 |
| 2 | Thread ID Storage | Separate `websocket_sessions` table | Phase 3B |
| 3 | Phase 3 Strategy | **Split into 3A + 3B** | Phase 3 |
| 4 | Checkpointer | PostgreSQL (reuse engine) | Phase 2, 3 |
| 5 | Mock Strategy | Integration tests (mock too brittle) | All phases |
| 6 | Multi-LLM Fallback | Defer to Phase 5 (future) | Phase 1 |
| 7 | WebSocket Timeout | 10 minutes idle before cleanup | Phase 3B |
| 8 | Cost Tolerance | +30% OK, +40% triggers optimization, >50% abort | Phase 0 validation |
| 9 | Prompt Caching | In-memory (5-min TTL) | Phase 1 |
| 10 | Session Cleanup | Background task (APScheduler, 5-min interval) | Phase 3B |

**Total Decisions**: 10 architectural choices finalized
```

**Manual Action**:
1. Open `reports/architectural-decisions-final.md`
2. Scroll to end of file
3. Paste above content
4. Save file

**Verification**: File should be ~600 lines (was ~345 lines)

---

### Step 2: Delete Superseded Phase 3 File

**Goal**: Remove old unified Phase 3 document (replaced by 3A + 3B)

**PowerShell**:
```powershell
Remove-Item "phase-03-langgraph-adaptive.md" -Force
Write-Host "✅ Deleted: phase-03-langgraph-adaptive.md (superseded by 3A + 3B)"
```

**Bash**:
```bash
rm -f "phase-03-langgraph-adaptive.md"
echo "✅ Deleted: phase-03-langgraph-adaptive.md (superseded by 3A + 3B)"
```

**Verification**:
```powershell
Test-Path "phase-03-langgraph-adaptive.md"  # Should return False
Test-Path "phase-03a-adaptive-workflow-simple.md"  # Should return True
Test-Path "phase-03b-websocket-interrupts.md"  # Should return True
```

---

### Step 3: Delete Historical Documentation

**Goal**: Remove changelog files not needed for implementation

**PowerShell**:
```powershell
# Delete update log (changelog cruft)
Remove-Item "PLAN_UPDATES_COMPLETE.md" -Force
Write-Host "✅ Deleted: PLAN_UPDATES_COMPLETE.md"

# Delete plan revision summary (historical)
Remove-Item "reports\plan-revision-summary.md" -Force
Write-Host "✅ Deleted: reports\plan-revision-summary.md"

# Delete plan summary report (duplicates README)
Remove-Item "reports\plan-summary-report.md" -Force
Write-Host "✅ Deleted: reports\plan-summary-report.md"
```

**Bash**:
```bash
rm -f "PLAN_UPDATES_COMPLETE.md"
rm -f "reports/plan-revision-summary.md"
rm -f "reports/plan-summary-report.md"
echo "✅ Deleted: Historical documentation files"
```

**Verification**:
```powershell
# Should only have architectural-decisions-final.md in reports/
Get-ChildItem "reports" | Select-Object Name
```

Expected output:
```
Name
----
architectural-decisions-final.md
```

---

### Step 4: Remove Empty Directory

**Goal**: Clean up unused scout directory

**PowerShell**:
```powershell
if (Test-Path "scout") {
    Remove-Item "scout" -Force -Recurse
    Write-Host "✅ Deleted: scout/ directory"
} else {
    Write-Host "⚠️  scout/ already removed"
}
```

**Bash**:
```bash
if [ -d "scout" ]; then
    rm -rf "scout"
    echo "✅ Deleted: scout/ directory"
else
    echo "⚠️  scout/ already removed"
fi
```

---

### Step 5: Verify No Broken Links

**Goal**: Ensure no files reference deleted documents

**PowerShell**:
```powershell
Write-Host "`n🔍 Checking for broken links to deleted files..."

$deletedFiles = @(
    "phase-03-langgraph-adaptive",
    "PLAN_UPDATES_COMPLETE",
    "plan-revision-summary",
    "plan-summary-report"
)

$allMdFiles = Get-ChildItem -Recurse -Filter "*.md" | Select-Object -ExpandProperty FullName

foreach ($file in $allMdFiles) {
    foreach ($deleted in $deletedFiles) {
        $matches = Select-String -Path $file -Pattern $deleted -CaseSensitive
        if ($matches) {
            Write-Host "⚠️  Found reference in: $file"
            $matches | Format-Table -AutoSize
        }
    }
}

Write-Host "✅ Link verification complete"
```

**Bash**:
```bash
echo "🔍 Checking for broken links to deleted files..."

grep -r "phase-03-langgraph-adaptive\|PLAN_UPDATES_COMPLETE\|plan-revision-summary\|plan-summary-report" \
    *.md reports/*.md research/*.md 2>/dev/null

if [ $? -eq 0 ]; then
    echo "⚠️  Found broken links (see above)"
else
    echo "✅ No broken links found"
fi
```

**Expected**: No matches (if matches found, update those files manually)

---

### Step 6: List Final Structure

**Goal**: Verify clean directory structure

**PowerShell**:
```powershell
Write-Host "`n📂 Final Directory Structure:`n"

# Root files
Write-Host "Root Files:"
Get-ChildItem -Filter "*.md" | Select-Object Name, @{N='Size';E={"{0:N0} KB" -f ($_.Length/1KB)}} | Format-Table -AutoSize

# Reports
Write-Host "`nReports:"
Get-ChildItem "reports" -Filter "*.md" | Select-Object Name, @{N='Size';E={"{0:N0} KB" -f ($_.Length/1KB)}} | Format-Table -AutoSize

# Research
Write-Host "`nResearch:"
Get-ChildItem "research" -Filter "*.md" | Select-Object Name, @{N='Size';E={"{0:N0} KB" -f ($_.Length/1KB)}} | Format-Table -AutoSize

# Count
$totalFiles = (Get-ChildItem -Recurse -Filter "*.md").Count
$totalSize = (Get-ChildItem -Recurse -Filter "*.md" | Measure-Object -Property Length -Sum).Sum / 1KB
Write-Host "`n📊 Total: $totalFiles files, $([math]::Round($totalSize, 1)) KB"
```

**Bash**:
```bash
echo "📂 Final Directory Structure:"
echo ""
echo "Root Files:"
ls -lh *.md | awk '{print $9, $5}'
echo ""
echo "Reports:"
ls -lh reports/*.md | awk '{print $9, $5}'
echo ""
echo "Research:"
ls -lh research/*.md | awk '{print $9, $5}'
echo ""
echo "📊 Total:"
find . -name "*.md" -type f | wc -l
du -sh .
```

**Expected Output**:
```
Root Files (9):
- plan.md
- README.md
- phase-00-prototypes-benchmarks.md
- phase-01-langchain-adapter.md
- phase-01-database-schema.md
- phase-02-langgraph-planning.md
- phase-03a-adaptive-workflow-simple.md
- phase-03b-websocket-interrupts.md
- phase-04-observability.md

Reports (1):
- architectural-decisions-final.md (enhanced)

Research (2):
- researcher-01-langchain-adapters.md
- researcher-02-langgraph-workflows.md

Total: 12 files, ~120 KB
```

---

### Step 7: Cleanup Verification Checklist

**Manual Checklist**:

- [ ] Backup created in `../_backup_YYMMDD-HHMM_251116-2345-original-cleanup/`
- [ ] `architectural-decisions-final.md` contains Decision 3 (Phase 3 split)
- [ ] `phase-03-langgraph-adaptive.md` deleted
- [ ] `PLAN_UPDATES_COMPLETE.md` deleted
- [ ] `reports/plan-revision-summary.md` deleted
- [ ] `reports/plan-summary-report.md` deleted
- [ ] `scout/` directory deleted
- [ ] No broken links found
- [ ] Total files: 12 (9 root + 1 report + 2 research)
- [ ] `README.md` still links to all phases correctly
- [ ] `plan.md` phase table references 3A and 3B (not 3)

**Automated Verification**:
```powershell
# Quick validation script
$expected = @(
    "plan.md",
    "README.md",
    "phase-00-prototypes-benchmarks.md",
    "phase-01-langchain-adapter.md",
    "phase-01-database-schema.md",
    "phase-02-langgraph-planning.md",
    "phase-03a-adaptive-workflow-simple.md",
    "phase-03b-websocket-interrupts.md",
    "phase-04-observability.md",
    "reports\architectural-decisions-final.md",
    "research\researcher-01-langchain-adapters.md",
    "research\researcher-02-langgraph-workflows.md"
)

$missing = @()
foreach ($file in $expected) {
    if (-not (Test-Path $file)) {
        $missing += $file
    }
}

if ($missing.Count -eq 0) {
    Write-Host "✅ All essential files present!"
} else {
    Write-Host "❌ Missing files:"
    $missing | ForEach-Object { Write-Host "  - $_" }
}

# Check for unexpected files
$unexpected = @(
    "phase-03-langgraph-adaptive.md",
    "PLAN_UPDATES_COMPLETE.md",
    "reports\plan-revision-summary.md",
    "reports\plan-summary-report.md"
)

$found = @()
foreach ($file in $unexpected) {
    if (Test-Path $file) {
        $found += $file
    }
}

if ($found.Count -eq 0) {
    Write-Host "✅ All redundant files removed!"
} else {
    Write-Host "❌ Files should be deleted:"
    $found | ForEach-Object { Write-Host "  - $_" }
}
```

---

## Complete Script (All-in-One)

**PowerShell** (run all steps at once):

```powershell
# Navigate to plan directory
cd "H:\AI-course\EliosAIService\plans\251116-2345-langchain-langgraph-integration"

Write-Host "🧹 Starting Plan Cleanup - Original Structure`n"

# Step 0: Backup
Write-Host "📦 Step 0: Creating backup..."
$timestamp = Get-Date -Format "yyMMdd-HHmm"
$backupDir = "..\_backup_$timestamp`_251116-2345-original-cleanup"
Copy-Item -Recurse -Force "." $backupDir
Write-Host "   ✅ Backup: $backupDir`n"

# Step 1: Manual consolidation required
Write-Host "📝 Step 1: MANUAL ACTION REQUIRED"
Write-Host "   → Open reports\architectural-decisions-final.md"
Write-Host "   → Append content from CLEANUP_EXECUTION.md (Step 1)"
Write-Host "   → Save file"
Read-Host "   Press Enter when complete"

# Step 2: Delete superseded Phase 3
Write-Host "`n🗑️  Step 2: Deleting superseded Phase 3 file..."
Remove-Item "phase-03-langgraph-adaptive.md" -Force -ErrorAction SilentlyContinue
Write-Host "   ✅ Deleted: phase-03-langgraph-adaptive.md`n"

# Step 3: Delete historical docs
Write-Host "🗑️  Step 3: Deleting historical documentation..."
Remove-Item "PLAN_UPDATES_COMPLETE.md" -Force -ErrorAction SilentlyContinue
Remove-Item "reports\plan-revision-summary.md" -Force -ErrorAction SilentlyContinue
Remove-Item "reports\plan-summary-report.md" -Force -ErrorAction SilentlyContinue
Write-Host "   ✅ Deleted: PLAN_UPDATES_COMPLETE.md"
Write-Host "   ✅ Deleted: reports\plan-revision-summary.md"
Write-Host "   ✅ Deleted: reports\plan-summary-report.md`n"

# Step 4: Remove empty directory
Write-Host "🗑️  Step 4: Removing empty scout directory..."
Remove-Item "scout" -Force -Recurse -ErrorAction SilentlyContinue
Write-Host "   ✅ Deleted: scout/`n"

# Step 5: Verify links
Write-Host "🔍 Step 5: Checking for broken links..."
$broken = Select-String -Path "*.md","reports\*.md","research\*.md" -Pattern "phase-03-langgraph-adaptive|PLAN_UPDATES_COMPLETE|plan-revision-summary|plan-summary-report" -CaseSensitive
if ($broken) {
    Write-Host "   ⚠️  Found references to deleted files:"
    $broken | Format-Table -AutoSize
} else {
    Write-Host "   ✅ No broken links found`n"
}

# Step 6: List final structure
Write-Host "📂 Step 6: Final structure"
$totalFiles = (Get-ChildItem -Recurse -Filter "*.md").Count
$totalSize = (Get-ChildItem -Recurse -Filter "*.md" | Measure-Object -Property Length -Sum).Sum / 1KB
Write-Host "   Files: $totalFiles"
Write-Host "   Size:  $([math]::Round($totalSize, 1)) KB`n"

Write-Host "✅ Cleanup complete! Original plan structure achieved.`n"
Write-Host "📁 Backup location: $backupDir"
```

---

## Rollback Instructions

If cleanup causes issues:

**PowerShell**:
```powershell
# Find backup directory
$backups = Get-ChildItem ".." -Filter "_backup_*_251116-2345-original-cleanup"
$latest = $backups | Sort-Object LastWriteTime -Descending | Select-Object -First 1

# Restore from backup
Remove-Item "." -Recurse -Force
Copy-Item -Recurse -Force $latest.FullName "."

Write-Host "Restored from: $($latest.FullName)"
```

---

## Summary

**Actions Taken**:
1. ✅ Backup created
2. ✅ Decision 3 added to architectural-decisions-final.md
3. ✅ Deleted phase-03-langgraph-adaptive.md (superseded)
4. ✅ Deleted PLAN_UPDATES_COMPLETE.md (changelog)
5. ✅ Deleted plan-revision-summary.md (historical)
6. ✅ Deleted plan-summary-report.md (duplicate)
7. ✅ Deleted scout/ (empty)
8. ✅ Verified no broken links

**Result**: Clean "original" plan structure with 12 essential files

**Next Steps**: Begin Phase 0 implementation with clean plan directory

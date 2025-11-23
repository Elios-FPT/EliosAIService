# Workflow-Legacy Parity Implementation Plan

**Plan ID:** 251124-0452-workflow-legacy-parity
**Created:** 2025-11-24
**Status:** Ready for Implementation
**Total Effort:** 17-19 hours (3-4 days)

## Quick Links

- **Main Plan:** [plan.md](plan.md) - Overview, phases, tracking
- **Analysis Source:** [INCONSISTENCIES_ANALYSIS.md](../../INCONSISTENCIES_ANALYSIS.md)

### Phase Documents
1. [Phase 1: Critical UX Fixes](phase-01-critical-fixes.md) - Evaluation feedback, TTS, follow-up logic
2. [Phase 2: Message Standardization](phase-02-message-standardization.md) - WebSocket message formats
3. [Phase 3: Gap Strategy](phase-03-gap-strategy.md) - Gap accumulation alignment
4. [Phase 4: Polish & Edge Cases](phase-04-polish.md) - State sync, retry logic, audio storage
5. [Phase 5: Testing & Validation](phase-05-testing.md) - Parity tests, load tests, rollout

## Executive Summary

### Problem
InterviewConversationWorkflow (LangGraph) has 9 behavioral inconsistencies with legacy session_orchestrator, causing critical UX regressions:
- No evaluation feedback sent to clients
- No TTS audio generation (breaks voice interviews)
- Follow-up logic uses wrong criteria (ignores semantic similarity)
- Different WebSocket message formats

### Solution
Fix all 9 inconsistencies in 5 phases over 3-4 days:
1. **Phase 1 (8h):** Fix critical UX issues - evaluation feedback, TTS, follow-up logic
2. **Phase 2 (6h):** Standardize WebSocket messages - follow-up types, metadata
3. **Phase 3 (5h):** Align gap accumulation - hybrid DB + state strategy
4. **Phase 4 (4h):** Polish edge cases - state sync, retry logic, error handling
5. **Phase 5 (5h):** Comprehensive testing - parity tests, load tests, rollout validation

### Impact
- **UX:** Users receive complete feedback (scores, strengths, weaknesses)
- **Accessibility:** Voice interviews work with TTS audio
- **Consistency:** Identical behavior regardless of backend path
- **Production Ready:** Feature flag controls gradual rollout (5% → 100%)

## Issues Fixed

| # | Issue | Priority | Phase | Impact |
|---|-------|----------|-------|--------|
| 1 | Missing evaluation feedback | CRITICAL | 1 | No scores/feedback shown |
| 2 | Wrong follow-up criteria | CRITICAL | 1 | Inconsistent decisions |
| 5 | No TTS audio | CRITICAL | 1 | Voice interviews broken |
| 4 | Wrong message types | HIGH | 2 | Frontend can't style follow-ups |
| 6 | Gap strategy mismatch | MEDIUM | 3 | Duplicate follow-ups possible |
| 7 | State sync issues | LOW | 4 | Edge case: stale state |
| 8 | Incomplete retry logic | LOW | 4 | No transient failure resilience |
| 3 | Missing audio_file_path | LOW | 4 | Storage decision needed |
| 9 | Conversation history | N/A | - | Workflow improvement (keep) |

## Key Deliverables

### Code Changes
- **Modified Files:** 3 (workflow, handler, use case)
- **New Files:** 5 (tests, docs, monitoring)
- **Lines Changed:** ~800 (estimated)

### Tests
- **Unit Tests:** 14 new
- **Integration Tests:** 7 new
- **Parity Tests:** 15 new
- **Load Tests:** 5 new
- **Total:** 41 new tests

### Documentation
- **Decision Records:** 2 (gap strategy, audio storage)
- **API Updates:** WebSocket message schemas
- **Guides:** Rollout checklist, monitoring runbook

## Timeline

```
Day 1 (8h)
├─ 09:00-11:00  Task 1.1: Evaluation return value
├─ 11:00-12:30  Task 1.2: WebSocket evaluation message
├─ 13:30-16:00  Task 1.3: TTS audio generation
└─ 16:00-18:00  Task 1.4: Follow-up logic fix

Day 2 (6h)
├─ 09:00-10:30  Task 2.1: Question type detection
├─ 10:30-12:30  Task 2.2: Workflow metadata
├─ 13:30-15:00  Task 2.3: Message sending update
└─ 15:00-16:00  Task 2.4: Schema validation tests

Day 3 (5h)
├─ 09:00-11:30  Task 3.1: Gap validation node
├─ 11:30-12:30  Task 3.2: Strategy documentation
├─ 13:30-14:00  Task 3.3: Gap monitoring
└─ 14:00-15:00  Task 3.4: Integration tests

Day 4 (9h)
├─ 09:00-10:30  Task 4.1: State refresh
├─ 10:30-11:30  Task 4.2: Retry logic
├─ 11:30-12:00  Task 4.3: Audio decision
├─ 12:00-13:00  Task 4.4: Error audit
├─ 13:00-14:00  Task 5.1: Parity tests
├─ 14:00-15:00  Task 5.2: Load tests
├─ 15:00-15:30  Task 5.3: Feature flag tests
├─ 15:30-16:00  Task 5.4: Monitoring tests
└─ 16:00-17:00  Run full suite, fixes
```

**Total:** 28 hours (realistically 3.5 days with buffer)

## Success Criteria

### Functional
- [ ] All 9 inconsistencies resolved
- [ ] Evaluation feedback messages sent (100% delivery rate)
- [ ] TTS audio in all questions (>99.5% success rate)
- [ ] Follow-up decisions match legacy (+/- 2%)
- [ ] WebSocket message schemas identical

### Technical
- [ ] 41 new tests passing (100% pass rate)
- [ ] Zero regressions (existing 500+ tests still pass)
- [ ] Code coverage > 90% for new code
- [ ] Load test passes (50 concurrent < 15s)
- [ ] Checkpoint table < 50MB after load

### Production Readiness
- [ ] Feature flag controls path selection
- [ ] Monitoring metrics emitting correctly
- [ ] Rollback procedure tested
- [ ] Documentation complete
- [ ] QA sign-off obtained

## Rollout Plan

### Stage 1: Canary (Week 1)
- 5% of production traffic
- Monitor hourly for 24h
- **Rollback if:** Error rate > 1% OR latency > 2s

### Stage 2: Gradual (Week 2)
- Increase to 25%
- Daily metric review
- **Rollback if:** Evaluation delivery < 99%

### Stage 3: Majority (Week 3)
- Increase to 50%
- Side-by-side metric comparison
- **Go/No-Go decision**

### Stage 4: Full (Week 4)
- 100% migration
- 72h freeze for observation
- Legacy path deprecated (Month 2)

## Risks & Mitigation

| Risk | Impact | Mitigation |
|------|--------|------------|
| Breaking frontend clients | High | Feature flag, gradual rollout, backwards compatibility |
| TTS latency increase | Medium | Non-blocking generation, caching, CDN delivery |
| Checkpoint state bloat | Medium | Store evaluation IDs only, monitor table size |
| State-DB divergence | Medium | Hybrid gap validation, monitoring alerts |

## Monitoring

### Key Metrics
- **Evaluation Delivery Rate:** Target 100%, alert < 99%
- **TTS Generation Success:** Target 99.5%, alert < 99%
- **Follow-Up Accuracy:** Within +/- 2% of legacy
- **Gap Validation Mismatch:** < 5/hour, alert > 10/hour
- **Checkpoint Resume:** > 99% success rate

### Dashboards
- Workflow vs Legacy comparison (side-by-side)
- Feature flag rollout progress
- Error rate by issue type
- Latency distribution (p50, p95, p99)

## Getting Started

### For Implementers
1. Read [plan.md](plan.md) for full context
2. Review [INCONSISTENCIES_ANALYSIS.md](../../INCONSISTENCIES_ANALYSIS.md)
3. Start with [Phase 1](phase-01-critical-fixes.md)
4. Follow phase order (1 → 2 → 3 → 4 → 5)
5. Run tests after each phase

### For Reviewers
1. Check code against acceptance criteria in each phase
2. Verify all tests passing
3. Review architectural decisions (AD-1 through AD-4)
4. Validate monitoring metrics
5. Sign off on production readiness checklist

### For QA
1. Run manual test scenarios (8 cases)
2. Execute parity test suite
3. Perform load testing
4. Validate feature flag behavior
5. Document any issues found

## Dependencies

### Required
- LangGraph (already integrated)
- AsyncPostgresSaver (checkpointing)
- pytest (testing framework)

### Optional (Future)
- TTS caching layer (performance optimization)
- State compression (checkpoint size reduction)
- Metrics aggregation (advanced monitoring)

## Questions?

- **Technical:** Review [Architecture Decisions](plan.md#architecture-decisions) in plan.md
- **Testing:** See [Phase 5](phase-05-testing.md) for comprehensive test strategy
- **Rollout:** Check [Rollout Plan](plan.md#rollout-plan) in plan.md
- **Monitoring:** See [Monitoring & Metrics](plan.md#monitoring--metrics) section

---

**Status:** ✅ Plan Complete, Ready for Implementation
**Next Step:** Begin Phase 1 - Critical UX Fixes
**Expected Completion:** Day 4 (3-4 days from start)

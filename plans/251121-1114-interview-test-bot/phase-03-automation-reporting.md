# Phase 3: Automation & Reporting

**Duration**: 3 days
**Deliverable**: Test runner + metrics collector + report generator (JSON/HTML)

---

## Overview

Orchestrate test execution, collect performance/cost metrics, generate comprehensive reports with baseline comparison. Enable automated regression testing for interview system.

---

## File Structure

```
tests/bot/
├── run_tests.py                    # CLI entry point
├── test_runner.py                  # Test orchestration logic
├── metrics_collector.py            # Performance/cost tracking
├── report_generator.py             # JSON/HTML report generation
├── assertion_validator.py          # Assertion evaluation logic
└── templates/
    └── report_template.html        # HTML report template
```

---

## 1. Test Runner

**File**: `tests/bot/test_runner.py`

```python
"""Test runner for orchestrating interview bot tests."""

import asyncio
import json
import logging
import os
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

import httpx
import yaml

from .test_bot_client import InterviewTestBot
from .answer_generator import AnswerGenerator
from .metrics_collector import MetricsCollector
from .assertion_validator import AssertionValidator

logger = logging.getLogger(__name__)


@dataclass
class ScenarioResult:
    """Result of single test scenario."""

    id: str
    name: str
    status: str  # "passed", "failed", "skipped"
    duration_sec: float
    cost_usd: float
    assertions_passed: int
    assertions_failed: int
    errors: list[str] = field(default_factory=list)
    metrics: dict[str, Any] = field(default_factory=dict)


@dataclass
class TestResults:
    """Aggregate results of all tests."""

    total: int
    passed: int
    failed: int
    skipped: int
    total_duration_sec: float
    total_cost_usd: float
    scenarios: list[ScenarioResult]
    metrics: dict[str, Any]
    baseline_comparison: dict[str, Any] | None = None


class TestRunner:
    """Orchestrate interview bot test execution."""

    def __init__(
        self,
        base_url: str = "http://localhost:8000",
        output_dir: str = "reports/",
    ):
        """Initialize test runner.

        Args:
            base_url: API base URL
            output_dir: Report output directory
        """
        self.base_url = base_url
        self.ws_base_url = base_url.replace("http://", "ws://").replace("https://", "wss://")
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

        self.answer_generator = AnswerGenerator()
        self.metrics_collector = MetricsCollector()
        self.assertion_validator = AssertionValidator()

        # HTTP client for API calls
        self.http_client: httpx.AsyncClient | None = None

    async def run_all_tests(
        self,
        scenarios_file: Path,
        enable_baseline_comparison: bool = True,
    ) -> TestResults:
        """Run all scenarios in file.

        Args:
            scenarios_file: Path to YAML scenarios file
            enable_baseline_comparison: Compare to baseline metrics

        Returns:
            Aggregate test results
        """
        logger.info(f"Loading scenarios from {scenarios_file}")
        with open(scenarios_file) as f:
            data = yaml.safe_load(f)

        scenarios = data.get("scenarios", [])
        logger.info(f"Loaded {len(scenarios)} scenarios")

        # Setup HTTP client
        self.http_client = httpx.AsyncClient(base_url=self.base_url, timeout=30.0)

        start_time = time.time()
        results = []

        try:
            for scenario in scenarios:
                # Skip if scenario marked as skip
                if scenario.get("skip", False):
                    logger.info(f"Skipping {scenario['id']}: {scenario.get('skip_reason', 'N/A')}")
                    results.append(ScenarioResult(
                        id=scenario["id"],
                        name=scenario["name"],
                        status="skipped",
                        duration_sec=0,
                        cost_usd=0,
                        assertions_passed=0,
                        assertions_failed=0,
                    ))
                    continue

                # Run scenario
                logger.info(f"\n{'='*60}")
                logger.info(f"Running {scenario['id']}: {scenario['name']}")
                logger.info(f"{'='*60}")

                result = await self.run_scenario(scenario)
                results.append(result)

                logger.info(f"Result: {result.status} ({result.duration_sec:.1f}s, ${result.cost_usd:.3f})")

        finally:
            await self.http_client.aclose()

        total_duration = time.time() - start_time

        # Aggregate results
        test_results = TestResults(
            total=len(results),
            passed=sum(1 for r in results if r.status == "passed"),
            failed=sum(1 for r in results if r.status == "failed"),
            skipped=sum(1 for r in results if r.status == "skipped"),
            total_duration_sec=total_duration,
            total_cost_usd=sum(r.cost_usd for r in results),
            scenarios=results,
            metrics=self.metrics_collector.get_summary(),
        )

        # Baseline comparison
        if enable_baseline_comparison:
            test_results.baseline_comparison = self._compare_to_baseline(
                test_results,
                scenarios_file
            )

        return test_results

    async def run_scenario(self, scenario: dict) -> ScenarioResult:
        """Execute single test scenario.

        Args:
            scenario: Scenario config dict

        Returns:
            Scenario result
        """
        scenario_id = scenario["id"]
        config = scenario["config"]
        assertions = scenario.get("assertions", [])

        start_time = time.time()
        errors = []

        try:
            # Setup: Set USE_MOCK_ADAPTERS env var
            use_mock = config.get("use_mock", True)
            os.environ["USE_MOCK_ADAPTERS"] = "true" if use_mock else "false"

            # Step 1: Create interview via API
            interview_id, ws_url = await self._setup_interview(config)

            # Step 2: Connect bot via WebSocket
            bot = InterviewTestBot(
                interview_id=interview_id,
                timeout=config.get("timeout", 30.0),
                enable_metrics=True,
            )

            await bot.connect(ws_url)

            # Step 3: Run interview flow
            context = await self._run_interview_flow(bot, config, scenario_id)

            # Step 4: Disconnect
            await bot.disconnect()

            # Step 5: Collect metrics
            bot_metrics = bot.get_metrics()
            self.metrics_collector.merge(bot_metrics)

            # Step 6: Validate assertions
            assertions_passed, assertions_failed = await self._validate_assertions(
                assertions,
                context,
                interview_id,
            )

            # Step 7: Calculate cost (for real tests)
            cost = await self._calculate_cost(interview_id, use_mock)

            # Determine status
            if errors:
                status = "failed"
            elif assertions_failed > 0:
                status = "failed"
                errors.append(f"{assertions_failed} assertion(s) failed")
            else:
                status = "passed"

        except Exception as e:
            logger.error(f"Scenario {scenario_id} failed: {e}", exc_info=True)
            status = "failed"
            errors.append(str(e))
            bot_metrics = {}
            assertions_passed = 0
            assertions_failed = len(assertions)
            cost = 0.0

        duration = time.time() - start_time

        return ScenarioResult(
            id=scenario_id,
            name=scenario["name"],
            status=status,
            duration_sec=duration,
            cost_usd=cost,
            assertions_passed=assertions_passed,
            assertions_failed=assertions_failed,
            errors=errors,
            metrics=bot_metrics,
        )

    async def _setup_interview(self, config: dict) -> tuple[UUID, str]:
        """Create interview via API, upload CV, plan interview.

        Args:
            config: Scenario config

        Returns:
            (interview_id, ws_url)
        """
        # Get CV fixture path
        cv_fixture = config.get("cv_fixture")
        cv_path = Path(__file__).parent / "fixtures" / "cvs" / cv_fixture

        if not cv_path.exists():
            raise FileNotFoundError(f"CV fixture not found: {cv_path}")

        # Step 1: Create candidate
        candidate_resp = await self.http_client.post(
            "/api/candidates",
            json={
                "name": "Test Candidate",
                "email": "test@example.com",
            }
        )
        candidate_resp.raise_for_status()
        candidate_id = candidate_resp.json()["id"]

        # Step 2: Upload CV
        with open(cv_path, "rb") as f:
            cv_resp = await self.http_client.post(
                f"/api/candidates/{candidate_id}/cv",
                files={"file": f}
            )
        cv_resp.raise_for_status()

        # Step 3: Plan interview
        plan_resp = await self.http_client.post(
            "/api/interviews/plan",
            json={
                "candidate_id": candidate_id,
                "question_count": config.get("expected_questions", 3),
            }
        )
        plan_resp.raise_for_status()
        plan_data = plan_resp.json()

        interview_id = UUID(plan_data["interview_id"])
        ws_url = plan_data["ws_url"]  # Assume ws_url returned in response

        logger.info(f"Setup complete: interview={interview_id}, ws_url={ws_url}")

        return interview_id, ws_url

    async def _run_interview_flow(
        self,
        bot: InterviewTestBot,
        config: dict,
        scenario_id: str,
    ) -> dict[str, Any]:
        """Run interview flow (question/answer loop).

        Args:
            bot: Test bot instance
            config: Scenario config
            scenario_id: Scenario ID for logging

        Returns:
            Context dict with questions, answers, evaluations, etc.
        """
        context = {
            "questions": [],
            "answers": [],
            "evaluations": [],
            "follow_ups": [],
            "summary": None,
        }

        answer_quality = config.get("answer_quality", "good")
        expected_questions = config.get("expected_questions", 3)

        # Loop: receive question → send answer → receive eval
        for i in range(expected_questions + 10):  # +10 buffer for follow-ups
            try:
                # Wait for question or follow-up
                try:
                    message = await bot.wait_for_question(timeout=5.0)
                    message_type = "question"
                except TimeoutError:
                    # Try follow-up
                    try:
                        message = await bot.wait_for_follow_up(timeout=5.0)
                        message_type = "follow_up"
                    except TimeoutError:
                        # Try completion
                        try:
                            completion = await bot.wait_for_completion(timeout=5.0)
                            context["summary"] = completion
                            logger.info("Interview completed")
                            break
                        except TimeoutError:
                            logger.warning(f"No message after {i} iterations, assuming done")
                            break

                # Store question/follow-up
                if message_type == "question":
                    context["questions"].append(message)
                else:
                    context["follow_ups"].append(message)

                # Generate answer
                question_text = message["text"]
                answer_text = self.answer_generator.generate(question_text, answer_quality)

                # Send answer
                question_id = UUID(message["question_id"])
                await bot.send_text_answer(question_id, answer_text)

                context["answers"].append({
                    "question_id": str(question_id),
                    "text": answer_text,
                })

                # Wait for evaluation
                evaluation = await bot.wait_for_evaluation(timeout=10.0)
                context["evaluations"].append(evaluation)

            except Exception as e:
                logger.error(f"Error in interview flow: {e}")
                raise

        return context

    async def _validate_assertions(
        self,
        assertions: list[dict],
        context: dict,
        interview_id: UUID,
    ) -> tuple[int, int]:
        """Validate assertions against context.

        Args:
            assertions: List of assertion dicts
            context: Interview context (questions, answers, etc.)
            interview_id: Interview UUID

        Returns:
            (assertions_passed, assertions_failed)
        """
        if not assertions:
            return 0, 0

        passed = 0
        failed = 0

        for assertion in assertions:
            expression = assertion["expression"]
            message = assertion.get("message", "Assertion failed")

            try:
                result = await self.assertion_validator.evaluate(
                    expression,
                    context,
                    interview_id,
                    self.http_client,
                )

                if result:
                    passed += 1
                    logger.info(f"✓ {message}")
                else:
                    failed += 1
                    logger.error(f"✗ {message} (expression: {expression})")

            except Exception as e:
                failed += 1
                logger.error(f"✗ {message} (error: {e})")

        return passed, failed

    async def _calculate_cost(self, interview_id: UUID, use_mock: bool) -> float:
        """Calculate cost for interview.

        Args:
            interview_id: Interview UUID
            use_mock: Whether mock adapters used

        Returns:
            Cost in USD
        """
        if use_mock:
            return 0.0

        # Query LangSmith API for interview cost
        # (Requires LangSmith API key and interview metadata tagging)
        try:
            from src.infrastructure.observability.cost_tracking import get_interview_cost
            from src.infrastructure.config.settings import get_settings

            settings = get_settings()

            if not settings.langsmith_api_key:
                logger.warning("LangSmith API key not set, cost tracking disabled")
                return 0.0

            cost_data = await get_interview_cost(
                interview_id=interview_id,
                langsmith_api_key=settings.langsmith_api_key,
                project_name=settings.langchain_project,
            )

            return cost_data.get("total_cost_usd", 0.0)

        except Exception as e:
            logger.warning(f"Failed to calculate cost: {e}")
            return 0.0

    def _compare_to_baseline(
        self,
        results: TestResults,
        scenarios_file: Path,
    ) -> dict[str, Any]:
        """Compare results to baseline metrics.

        Args:
            results: Test results
            scenarios_file: Scenarios file (determines baseline file)

        Returns:
            Comparison dict
        """
        baseline_path = Path(__file__).parent / "fixtures" / "baselines" / "baseline_metrics.json"

        if not baseline_path.exists():
            logger.warning(f"Baseline not found: {baseline_path}")
            return {}

        with open(baseline_path) as f:
            baseline = json.load(f)

        # Determine test type (mock or real)
        is_mock = "mock" in str(scenarios_file)
        baseline_data = baseline.get("mock_tests" if is_mock else "real_tests", {})

        if not baseline_data:
            return {}

        # Calculate metrics
        actual_avg_duration = results.total_duration_sec / results.total if results.total > 0 else 0
        actual_avg_cost = results.total_cost_usd / results.total if results.total > 0 else 0

        baseline_avg_duration = baseline_data.get("avg_duration_sec", 0)
        baseline_avg_cost = baseline_data.get("avg_cost_usd", 0)

        # Calculate deltas
        duration_delta_pct = (
            ((actual_avg_duration - baseline_avg_duration) / baseline_avg_duration * 100)
            if baseline_avg_duration > 0 else 0
        )

        cost_delta_pct = (
            ((actual_avg_cost - baseline_avg_cost) / baseline_avg_cost * 100)
            if baseline_avg_cost > 0 else 0
        )

        # Determine status (pass/warn/fail)
        duration_status = "pass"
        if duration_delta_pct > 20:
            duration_status = "fail"
        elif duration_delta_pct > 10:
            duration_status = "warn"

        cost_status = "pass"
        if cost_delta_pct > 20:
            cost_status = "fail"
        elif cost_delta_pct > 10:
            cost_status = "warn"

        return {
            "duration": {
                "actual": actual_avg_duration,
                "baseline": baseline_avg_duration,
                "delta_pct": duration_delta_pct,
                "status": duration_status,
            },
            "cost": {
                "actual": actual_avg_cost,
                "baseline": baseline_avg_cost,
                "delta_pct": cost_delta_pct,
                "status": cost_status,
            },
        }
```

---

## 2. Metrics Collector

**File**: `tests/bot/metrics_collector.py`

```python
"""Metrics collection for interview bot tests."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class MetricsCollector:
    """Track performance and cost metrics across tests."""

    latency: dict[str, list[float]] = field(default_factory=dict)
    states: list[tuple[datetime, str]] = field(default_factory=list)
    errors: list[tuple[datetime, str, str]] = field(default_factory=list)
    tokens: dict[str, int] = field(default_factory=dict)
    cost: dict[str, float] = field(default_factory=dict)

    def merge(self, bot_metrics: dict[str, Any]) -> None:
        """Merge metrics from bot.

        Args:
            bot_metrics: Metrics dict from InterviewTestBot.get_metrics()
        """
        # Merge latency
        for key, data in bot_metrics.get("latency", {}).items():
            if key not in self.latency:
                self.latency[key] = []
            # Extract values from aggregated data
            if isinstance(data, dict):
                # Assume data has "count", "avg", etc.
                avg = data.get("avg", 0)
                count = data.get("count", 1)
                self.latency[key].extend([avg] * count)
            elif isinstance(data, list):
                self.latency[key].extend(data)

        # Merge states
        for state_data in bot_metrics.get("states", []):
            timestamp = datetime.fromisoformat(state_data["timestamp"])
            state = state_data["state"]
            self.states.append((timestamp, state))

        # Merge errors
        for error_data in bot_metrics.get("errors", []):
            timestamp = datetime.fromisoformat(error_data["timestamp"])
            code = error_data["code"]
            message = error_data["message"]
            self.errors.append((timestamp, code, message))

    def get_summary(self) -> dict[str, Any]:
        """Get aggregated metrics summary.

        Returns:
            Summary dict
        """
        return {
            "latency": {
                key: {
                    "count": len(values),
                    "avg": sum(values) / len(values) if values else 0,
                    "min": min(values) if values else 0,
                    "max": max(values) if values else 0,
                    "p50": self._percentile(values, 0.5),
                    "p95": self._percentile(values, 0.95),
                    "p99": self._percentile(values, 0.99),
                }
                for key, values in self.latency.items()
            },
            "state_transitions": {
                "count": len(self.states),
                "timeline": [
                    {"timestamp": ts.isoformat(), "state": state}
                    for ts, state in self.states
                ],
            },
            "errors": {
                "count": len(self.errors),
                "details": [
                    {"timestamp": ts.isoformat(), "code": code, "message": msg}
                    for ts, code, msg in self.errors
                ],
            },
            "tokens": self.tokens,
            "cost": self.cost,
        }

    def _percentile(self, values: list[float], p: float) -> float:
        """Calculate percentile.

        Args:
            values: List of values
            p: Percentile (0.0-1.0)

        Returns:
            Percentile value
        """
        if not values:
            return 0.0

        sorted_values = sorted(values)
        index = int(p * len(sorted_values))
        return sorted_values[min(index, len(sorted_values) - 1)]
```

---

## 3. Assertion Validator

**File**: `tests/bot/assertion_validator.py`

```python
"""Assertion validation for test scenarios."""

import logging
import re
from typing import Any
from uuid import UUID

import httpx

logger = logging.getLogger(__name__)


class AssertionValidator:
    """Evaluate assertion expressions against context."""

    async def evaluate(
        self,
        expression: str,
        context: dict[str, Any],
        interview_id: UUID,
        http_client: httpx.AsyncClient,
    ) -> bool:
        """Evaluate assertion expression.

        Args:
            expression: Python expression to evaluate
            context: Context dict (questions, answers, etc.)
            interview_id: Interview UUID
            http_client: HTTP client for API queries

        Returns:
            True if assertion passes

        Raises:
            Exception: If evaluation fails
        """
        # Build evaluation namespace
        namespace = {
            # Context variables
            "interview_id": interview_id,
            "questions": context.get("questions", []),
            "answers": context.get("answers", []),
            "evaluations": context.get("evaluations", []),
            "follow_ups": context.get("follow_ups", []),
            "summary": context.get("summary"),

            # Helper functions
            "len": len,
            "all": all,
            "any": any,
            "sum": sum,
            "min": min,
            "max": max,

            # Custom helpers
            "is_verbal_question": self._is_verbal_question,
            "has_difficulty_distribution": self._has_difficulty_distribution,
            "skill_coverage": self._skill_coverage,
            "no_code_writing_questions": self._no_code_writing_questions,
            "no_diagram_questions": self._no_diagram_questions,
            "is_context_aware": self._is_context_aware,
            "targets_gaps": self._targets_gaps,
            "unique_skills": self._unique_skills,
            "skill_diversity": self._skill_diversity,
            "weighted_avg": self._weighted_avg,
            "no_invalid_transitions": self._no_invalid_transitions,
            "no_cross_contamination": self._no_cross_contamination,

            # DB query helpers
            "db": DBHelper(http_client),
        }

        # Fetch interview from DB for assertions
        namespace["interview"] = await self._fetch_interview(interview_id, http_client)

        try:
            result = eval(expression, {}, namespace)
            return bool(result)
        except Exception as e:
            logger.error(f"Assertion evaluation failed: {expression} → {e}")
            raise

    async def _fetch_interview(
        self,
        interview_id: UUID,
        http_client: httpx.AsyncClient,
    ) -> dict:
        """Fetch interview from API.

        Args:
            interview_id: Interview UUID
            http_client: HTTP client

        Returns:
            Interview dict
        """
        try:
            resp = await http_client.get(f"/api/interviews/{interview_id}")
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            logger.error(f"Failed to fetch interview: {e}")
            return {}

    # Helper functions (from answer_generator.py)

    def _is_verbal_question(self, question_text: str) -> bool:
        """Check if question is verbal (no code/diagram)."""
        from .answer_generator import is_verbal_question
        return is_verbal_question(question_text)

    def _no_code_writing_questions(self, questions: list) -> bool:
        """Verify no code-writing questions."""
        from .answer_generator import no_code_writing_questions
        return no_code_writing_questions(questions)

    def _no_diagram_questions(self, questions: list) -> bool:
        """Verify no diagram questions."""
        from .answer_generator import no_diagram_questions
        return no_diagram_questions(questions)

    def _has_difficulty_distribution(
        self,
        questions: list,
        expected_difficulties: list[str],
    ) -> bool:
        """Check if questions have expected difficulty distribution."""
        actual_difficulties = [q.get("difficulty") for q in questions]
        return all(d in actual_difficulties for d in expected_difficulties)

    def _skill_coverage(
        self,
        questions: list,
        cv_skills: list[str],
    ) -> float:
        """Calculate skill coverage ratio."""
        question_skills = set()
        for q in questions:
            question_skills.update(q.get("skills", []))

        if not cv_skills:
            return 1.0

        covered = sum(1 for skill in cv_skills if skill in question_skills)
        return covered / len(cv_skills)

    def _is_context_aware(
        self,
        follow_up: dict,
        parent_question: dict,
        answer: dict,
    ) -> bool:
        """Check if follow-up is context-aware."""
        # Simple heuristic: follow-up text mentions parent question topic
        follow_up_text = follow_up.get("text", "").lower()
        parent_text = parent_question.get("text", "").lower()

        # Extract key terms from parent question
        key_terms = re.findall(r'\b[A-Z][a-z]+\b', parent_text)

        return any(term.lower() in follow_up_text for term in key_terms)

    def _targets_gaps(self, follow_up: dict, gaps: list) -> bool:
        """Check if follow-up targets identified gaps."""
        if not gaps:
            return False

        follow_up_text = follow_up.get("text", "").lower()

        # Check if any gap concept mentioned in follow-up
        for gap in gaps:
            concepts = gap.get("concepts", [])
            if any(concept.lower() in follow_up_text for concept in concepts):
                return True

        return False

    def _unique_skills(self, questions: list) -> list[str]:
        """Extract unique skills from questions."""
        skills = set()
        for q in questions:
            skills.update(q.get("skills", []))
        return list(skills)

    def _skill_diversity(self, questions: list) -> float:
        """Calculate skill diversity ratio."""
        total_skills = sum(len(q.get("skills", [])) for q in questions)
        unique_skills = len(self._unique_skills(questions))

        if total_skills == 0:
            return 0.0

        return unique_skills / total_skills

    def _weighted_avg(self, evaluations: list) -> float:
        """Calculate weighted average score."""
        if not evaluations:
            return 0.0

        # Simple average for now (can add weights later)
        scores = [e.get("score", 0) for e in evaluations]
        return sum(scores) / len(scores)

    def _no_invalid_transitions(self, transitions: list[str]) -> bool:
        """Verify no invalid state transitions."""
        from src.domain.models.interview import Interview

        valid_transitions = Interview.VALID_TRANSITIONS

        for i in range(len(transitions) - 1):
            current = transitions[i]
            next_state = transitions[i + 1]

            if next_state not in valid_transitions.get(current, []):
                logger.error(f"Invalid transition: {current} → {next_state}")
                return False

        return True

    def _no_cross_contamination(
        self,
        interview_1: dict,
        interview_2: dict,
    ) -> bool:
        """Verify no data leakage between interviews."""
        # Check question IDs don't overlap
        q1_ids = set(interview_1.get("question_ids", []))
        q2_ids = set(interview_2.get("question_ids", []))

        if q1_ids & q2_ids:
            logger.error(f"Question ID overlap: {q1_ids & q2_ids}")
            return False

        # Check answer IDs don't overlap
        a1_ids = set(interview_1.get("answer_ids", []))
        a2_ids = set(interview_2.get("answer_ids", []))

        if a1_ids & a2_ids:
            logger.error(f"Answer ID overlap: {a1_ids & a2_ids}")
            return False

        return True


class DBHelper:
    """Helper for DB queries in assertions."""

    def __init__(self, http_client: httpx.AsyncClient):
        self.http_client = http_client

    async def interview_exists(self, interview_id: UUID) -> bool:
        """Check if interview exists in DB."""
        try:
            resp = await self.http_client.get(f"/api/interviews/{interview_id}")
            return resp.status_code == 200
        except Exception:
            return False

    async def count_answers(self, interview_id: UUID) -> int:
        """Count answers for interview."""
        try:
            resp = await self.http_client.get(f"/api/interviews/{interview_id}/answers")
            if resp.status_code == 200:
                answers = resp.json()
                return len(answers)
            return 0
        except Exception:
            return 0
```

---

## 4. Report Generator

**File**: `tests/bot/report_generator.py`

```python
"""Generate test reports (JSON and HTML)."""

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from jinja2 import Template

from .test_runner import TestResults


class ReportGenerator:
    """Generate JSON and HTML test reports."""

    def generate_json(
        self,
        results: TestResults,
        output_path: Path,
    ) -> None:
        """Generate JSON report.

        Args:
            results: Test results
            output_path: Output file path
        """
        report = {
            "timestamp": datetime.utcnow().isoformat(),
            "summary": {
                "total_tests": results.total,
                "passed": results.passed,
                "failed": results.failed,
                "skipped": results.skipped,
                "pass_rate": results.passed / results.total if results.total > 0 else 0,
                "total_duration_sec": results.total_duration_sec,
                "total_cost_usd": results.total_cost_usd,
            },
            "scenarios": [
                {
                    "id": s.id,
                    "name": s.name,
                    "status": s.status,
                    "duration_sec": s.duration_sec,
                    "cost_usd": s.cost_usd,
                    "assertions": {
                        "passed": s.assertions_passed,
                        "failed": s.assertions_failed,
                        "total": s.assertions_passed + s.assertions_failed,
                    },
                    "errors": s.errors,
                    "metrics": s.metrics,
                }
                for s in results.scenarios
            ],
            "metrics": results.metrics,
            "baseline_comparison": results.baseline_comparison,
        }

        with open(output_path, "w") as f:
            json.dump(report, f, indent=2)

        print(f"JSON report saved: {output_path}")

    def generate_html(
        self,
        results: TestResults,
        output_path: Path,
    ) -> None:
        """Generate HTML report.

        Args:
            results: Test results
            output_path: Output file path
        """
        template_path = Path(__file__).parent / "templates" / "report_template.html"

        with open(template_path) as f:
            template = Template(f.read())

        # Render template
        html = template.render(
            results=results,
            timestamp=datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"),
        )

        with open(output_path, "w") as f:
            f.write(html)

        print(f"HTML report saved: {output_path}")
```

---

## 5. CLI Entry Point

**File**: `tests/bot/run_tests.py`

```python
"""CLI entry point for interview test bot."""

import argparse
import asyncio
import logging
import sys
from pathlib import Path

from .test_runner import TestRunner
from .report_generator import ReportGenerator

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)


async def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Interview Test Bot")

    parser.add_argument(
        "--scenarios",
        choices=["all", "mock", "real"],
        default="all",
        help="Which scenarios to run"
    )

    parser.add_argument(
        "--scenario",
        type=str,
        help="Run single scenario by ID"
    )

    parser.add_argument(
        "--output",
        type=str,
        default="reports/",
        help="Report output directory"
    )

    parser.add_argument(
        "--base-url",
        type=str,
        default="http://localhost:8000",
        help="API base URL"
    )

    parser.add_argument(
        "--no-baseline",
        action="store_true",
        help="Disable baseline comparison"
    )

    args = parser.parse_args()

    # Determine scenarios file
    if args.scenario:
        # Single scenario: find in mock or real
        mock_path = Path("tests/bot/scenarios/mock_scenarios.yaml")
        real_path = Path("tests/bot/scenarios/real_scenarios.yaml")

        # Try both files
        scenarios_file = mock_path if mock_path.exists() else real_path
        print(f"Running single scenario: {args.scenario}")

    elif args.scenarios == "mock":
        scenarios_file = Path("tests/bot/scenarios/mock_scenarios.yaml")
    elif args.scenarios == "real":
        scenarios_file = Path("tests/bot/scenarios/real_scenarios.yaml")
    else:
        # Run both
        print("Running all scenarios (mock + real)")
        await run_both(args)
        return

    # Run tests
    runner = TestRunner(base_url=args.base_url, output_dir=args.output)
    results = await runner.run_all_tests(
        scenarios_file=scenarios_file,
        enable_baseline_comparison=not args.no_baseline,
    )

    # Generate reports
    output_dir = Path(args.output)
    report_gen = ReportGenerator()

    json_path = output_dir / "latest.json"
    html_path = output_dir / "latest.html"

    report_gen.generate_json(results, json_path)
    report_gen.generate_html(results, html_path)

    # Print summary
    print_summary(results)

    # Exit code
    sys.exit(0 if results.failed == 0 else 1)


async def run_both(args):
    """Run both mock and real scenarios."""
    runner = TestRunner(base_url=args.base_url, output_dir=args.output)

    # Run mock
    print("\n" + "="*60)
    print("MOCK TESTS")
    print("="*60)
    mock_results = await runner.run_all_tests(
        scenarios_file=Path("tests/bot/scenarios/mock_scenarios.yaml"),
        enable_baseline_comparison=not args.no_baseline,
    )

    # Run real
    print("\n" + "="*60)
    print("REAL TESTS")
    print("="*60)
    real_results = await runner.run_all_tests(
        scenarios_file=Path("tests/bot/scenarios/real_scenarios.yaml"),
        enable_baseline_comparison=not args.no_baseline,
    )

    # Combine results
    combined_results = TestResults(
        total=mock_results.total + real_results.total,
        passed=mock_results.passed + real_results.passed,
        failed=mock_results.failed + real_results.failed,
        skipped=mock_results.skipped + real_results.skipped,
        total_duration_sec=mock_results.total_duration_sec + real_results.total_duration_sec,
        total_cost_usd=mock_results.total_cost_usd + real_results.total_cost_usd,
        scenarios=mock_results.scenarios + real_results.scenarios,
        metrics={
            "mock": mock_results.metrics,
            "real": real_results.metrics,
        },
        baseline_comparison={
            "mock": mock_results.baseline_comparison,
            "real": real_results.baseline_comparison,
        },
    )

    # Generate combined report
    output_dir = Path(args.output)
    report_gen = ReportGenerator()

    json_path = output_dir / "combined.json"
    html_path = output_dir / "combined.html"

    report_gen.generate_json(combined_results, json_path)
    report_gen.generate_html(combined_results, html_path)

    print_summary(combined_results)

    sys.exit(0 if combined_results.failed == 0 else 1)


def print_summary(results):
    """Print results summary."""
    print("\n" + "="*60)
    print("TEST SUMMARY")
    print("="*60)
    print(f"Total: {results.total}")
    print(f"Passed: {results.passed} ({results.passed/results.total*100:.1f}%)")
    print(f"Failed: {results.failed}")
    print(f"Skipped: {results.skipped}")
    print(f"Duration: {results.total_duration_sec:.1f}s")
    print(f"Cost: ${results.total_cost_usd:.3f}")

    if results.baseline_comparison:
        print("\nBaseline Comparison:")
        for key, data in results.baseline_comparison.items():
            if isinstance(data, dict):
                print(f"  {key}:")
                for metric, values in data.items():
                    if isinstance(values, dict):
                        status = values.get("status", "unknown")
                        delta = values.get("delta_pct", 0)
                        emoji = "✅" if status == "pass" else "⚠️" if status == "warn" else "❌"
                        print(f"    {emoji} {metric}: {delta:+.1f}%")


if __name__ == "__main__":
    asyncio.run(main())
```

---

## 6. HTML Report Template

**File**: `tests/bot/templates/report_template.html`

```html
<!DOCTYPE html>
<html>
<head>
    <title>Interview Test Bot Report</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 20px; }
        h1 { color: #333; }
        table { border-collapse: collapse; width: 100%; margin-top: 20px; }
        th, td { border: 1px solid #ddd; padding: 8px; text-align: left; }
        th { background-color: #4CAF50; color: white; }
        .passed { color: green; font-weight: bold; }
        .failed { color: red; font-weight: bold; }
        .skipped { color: gray; font-weight: bold; }
        .summary { background-color: #f2f2f2; padding: 15px; margin-bottom: 20px; }
        .metric { margin: 5px 0; }
    </style>
</head>
<body>
    <h1>Interview Test Bot Report</h1>
    <p>Generated: {{ timestamp }}</p>

    <div class="summary">
        <h2>Summary</h2>
        <div class="metric"><strong>Total Tests:</strong> {{ results.total }}</div>
        <div class="metric"><strong>Passed:</strong> <span class="passed">{{ results.passed }}</span></div>
        <div class="metric"><strong>Failed:</strong> <span class="failed">{{ results.failed }}</span></div>
        <div class="metric"><strong>Skipped:</strong> <span class="skipped">{{ results.skipped }}</span></div>
        <div class="metric"><strong>Duration:</strong> {{ "%.1f"|format(results.total_duration_sec) }}s</div>
        <div class="metric"><strong>Cost:</strong> ${{ "%.3f"|format(results.total_cost_usd) }}</div>
    </div>

    {% if results.baseline_comparison %}
    <div class="summary">
        <h2>Baseline Comparison</h2>
        {% for key, data in results.baseline_comparison.items() %}
        <p><strong>{{ key }}:</strong></p>
        <ul>
            {% for metric, values in data.items() %}
            {% if values is mapping %}
            <li>
                {{ metric }}: {{ "%.1f"|format(values.delta_pct) }}%
                ({{ values.status }})
            </li>
            {% endif %}
            {% endfor %}
        </ul>
        {% endfor %}
    </div>
    {% endif %}

    <h2>Scenario Results</h2>
    <table>
        <thead>
            <tr>
                <th>ID</th>
                <th>Name</th>
                <th>Status</th>
                <th>Duration (s)</th>
                <th>Cost ($)</th>
                <th>Assertions</th>
                <th>Errors</th>
            </tr>
        </thead>
        <tbody>
            {% for scenario in results.scenarios %}
            <tr>
                <td>{{ scenario.id }}</td>
                <td>{{ scenario.name }}</td>
                <td class="{{ scenario.status }}">{{ scenario.status }}</td>
                <td>{{ "%.1f"|format(scenario.duration_sec) }}</td>
                <td>{{ "%.3f"|format(scenario.cost_usd) }}</td>
                <td>{{ scenario.assertions_passed }}/{{ scenario.assertions_passed + scenario.assertions_failed }}</td>
                <td>{{ scenario.errors|length }}</td>
            </tr>
            {% endfor %}
        </tbody>
    </table>
</body>
</html>
```

---

## Acceptance Criteria

- [ ] Test runner orchestrates 15 scenarios (10 mock + 5 real)
- [ ] Metrics collector tracks latency, tokens, cost, states, errors
- [ ] Assertion validator evaluates all assertion types
- [ ] Report generator creates JSON + HTML reports
- [ ] CLI entry point supports `--scenarios all/mock/real`
- [ ] Baseline comparison highlights regressions
- [ ] Tests complete in <90 seconds
- [ ] Total cost <$0.50
- [ ] Pass rate 100% (no failures)

---

## Timeline

**Day 1**:
- AM: Implement test runner core logic
- PM: Implement metrics collector + assertion validator

**Day 2**:
- AM: Implement report generator (JSON + HTML template)
- PM: CLI entry point + integration testing

**Day 3**:
- AM: End-to-end testing (run full suite)
- PM: Bug fixes, documentation, final report

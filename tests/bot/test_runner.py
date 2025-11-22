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
from uuid import UUID

import httpx
import yaml

from .answer_generator import AnswerGenerator
from .assertion_validator import AssertionValidator
from .config import BotConfig, get_config
from .metrics_collector import MetricsCollector
from .test_bot_client import InterviewTestBot

logger = logging.getLogger(__name__)


class LogCaptureHandler(logging.Handler):
    """Custom log handler that captures log records in memory."""

    def __init__(self):
        super().__init__()
        self.logs: list[str] = []

    def emit(self, record: logging.LogRecord):
        """Capture log record as formatted string."""
        log_entry = self.format(record)
        self.logs.append(log_entry)

    def get_logs(self) -> list[str]:
        """Get captured logs."""
        return self.logs

    def clear(self):
        """Clear captured logs."""
        self.logs.clear()


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
    logs: list[str] = field(default_factory=list)


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
        base_url: str | None = None,
        output_dir: str | None = None,
        config: BotConfig | None = None,
    ):
        """Initialize test runner.

        Args:
            base_url: API base URL (overrides config if provided)
            output_dir: Report output directory (overrides config if provided)
            config: Bot configuration (uses global config if not provided)
        """
        self.config = config or get_config()

        # Use explicit params if provided, otherwise use config
        self.base_url = base_url or self.config.api.base_url
        self.output_dir = Path(output_dir or self.config.paths.output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

        self.ws_base_url = self.base_url.replace("http://", "ws://").replace(
            "https://", "wss://"
        )

        self.answer_generator = AnswerGenerator()
        self.metrics_collector = MetricsCollector()
        self.assertion_validator = AssertionValidator()

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

        self.http_client = httpx.AsyncClient(
            base_url=self.base_url, timeout=self.config.api.timeout_sec
        )

        start_time = time.time()
        results = []

        try:
            for scenario in scenarios:
                if scenario.get("skip", False):
                    logger.info(
                        f"Skipping {scenario['id']}: "
                        f"{scenario.get('skip_reason', 'N/A')}"
                    )
                    results.append(
                        ScenarioResult(
                            id=scenario["id"],
                            name=scenario["name"],
                            status="skipped",
                            duration_sec=0,
                            cost_usd=0,
                            assertions_passed=0,
                            assertions_failed=0,
                        )
                    )
                    continue

                logger.info(f"\n{'='*60}")
                logger.info(f"Running {scenario['id']}: {scenario['name']}")
                logger.info(f"{'='*60}")

                result = await self.run_scenario(scenario)
                results.append(result)

                logger.info(
                    f"Result: {result.status} "
                    f"({result.duration_sec:.1f}s, ${result.cost_usd:.3f})"
                )

        finally:
            await self.http_client.aclose()

        total_duration = time.time() - start_time

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

        if enable_baseline_comparison:
            test_results.baseline_comparison = self._compare_to_baseline(
                test_results, scenarios_file
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

        # Setup log capture
        log_handler = LogCaptureHandler()
        log_handler.setLevel(logging.DEBUG)
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        log_handler.setFormatter(formatter)

        # Add handler to root logger to capture all logs
        root_logger = logging.getLogger()
        root_logger.addHandler(log_handler)

        start_time = time.time()
        errors = []
        bot_metrics = {}
        assertions_passed = 0
        assertions_failed = 0
        cost = 0.0

        try:
            use_mock = config.get("use_mock", True)
            os.environ["USE_MOCK_ADAPTERS"] = "true" if use_mock else "false"

            # Execute based on test type
            if use_mock:
                # Mock test: Use DB helper to insert data, skip API calls
                interview_id, ws_url, context = await self._run_mock_scenario(config)
            else:
                # Real test: Full API flow (CV upload → plan → WebSocket QA)
                interview_id, ws_url, context = await self._run_real_scenario(config)

            # Validate assertions
            assertions_passed, assertions_failed = await self._validate_assertions(
                assertions, context, interview_id
            )

            # Calculate cost (for real tests)
            cost = await self._calculate_cost(interview_id, use_mock)

            # Collect metrics
            bot_metrics = context.get("bot_metrics", {})
            self.metrics_collector.merge(bot_metrics)

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
            assertions_failed = len(assertions)

        finally:
            # Capture logs and remove handler
            captured_logs = log_handler.get_logs()
            root_logger.removeHandler(log_handler)

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
            logs=captured_logs,
        )

    async def _run_mock_scenario(
        self, config: dict
    ) -> tuple[UUID, str, dict[str, Any]]:
        """Run mock scenario (DB insert + WebSocket QA only).

        Args:
            config: Scenario config

        Returns:
            (interview_id, ws_url, context)
        """
        from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
        from sqlalchemy.orm import sessionmaker
        from src.infrastructure.config.settings import get_settings
        from .db_helper import DatabaseHelper

        settings = get_settings()

        # Create DB session
        engine = create_async_engine(settings.async_database_url, echo=False)
        async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

        try:
            async with async_session() as session:
                db_helper = DatabaseHelper(session, self.config)

                # Insert pre-defined data
                candidate_id, interview_id, question_ids = await db_helper.insert_mock_interview_data(
                    cv_fixture=config["cv_fixture"],
                    expected_questions=config["expected_questions"],
                )

            # Construct WebSocket URL
            ws_url = f"{self.ws_base_url}/ws/interviews/{interview_id}"

            # Run WebSocket QA phase only
            context = await self._run_websocket_qa(interview_id, ws_url, config)

            return interview_id, ws_url, context

        finally:
            # Cleanup engine
            await engine.dispose()

    async def _run_real_scenario(
        self, config: dict
    ) -> tuple[UUID, str, dict[str, Any]]:
        """Run real scenario (full API flow).

        Args:
            config: Scenario config

        Returns:
            (interview_id, ws_url, context)
        """
        # Load CV fixture
        cv_fixture = config["cv_fixture"]
        cv_path = Path(__file__).parent / "fixtures" / "cvs" / cv_fixture

        if not cv_path.exists():
            raise FileNotFoundError(f"CV fixture not found: {cv_path}")

        with open(cv_path) as f:
            cv_data = json.load(f)

        # Step 1: Create candidate
        candidate_resp = await self.http_client.post(
            "/api/candidates",
            json={"name": cv_data["name"], "email": cv_data["email"]},
        )
        candidate_resp.raise_for_status()
        candidate_id = candidate_resp.json()["id"]

        logger.info(f"Created candidate: {candidate_id}")

        # Step 2: Upload CV (convert JSON to file-like format)
        files = {"file": (cv_fixture, json.dumps(cv_data), "application/json")}
        cv_resp = await self.http_client.post(
            f"/api/candidates/{candidate_id}/cv", files=files
        )
        cv_resp.raise_for_status()

        logger.info(f"Uploaded CV: {cv_fixture}")

        # Step 3: Plan interview
        plan_resp = await self.http_client.post(
            "/api/interviews/plan",
            json={
                "candidate_id": candidate_id,
                "question_count": config.get(
                    "expected_questions", self.config.interview.default_expected_questions
                ),
            },
        )
        plan_resp.raise_for_status()
        plan_data = plan_resp.json()

        interview_id = UUID(plan_data["interview_id"])
        ws_url = plan_data.get("ws_url") or f"{self.ws_base_url}/ws/interviews/{interview_id}"

        logger.info(f"Planned interview: {interview_id}")

        # Step 4: Run WebSocket QA phase
        context = await self._run_websocket_qa(interview_id, ws_url, config)

        return interview_id, ws_url, context

    async def _run_websocket_qa(
        self, interview_id: UUID, ws_url: str, config: dict
    ) -> dict[str, Any]:
        """Run WebSocket QA phase (common for both mock and real tests).

        Args:
            interview_id: Interview UUID
            ws_url: WebSocket URL
            config: Scenario config

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

        # Create bot
        bot = InterviewTestBot(
            interview_id=interview_id,
            timeout=config.get("timeout", self.config.timeouts.interview_timeout_sec),
            enable_metrics=True,
        )

        try:
            # Connect
            await bot.connect(ws_url)

            # Run QA loop
            answer_quality = config.get(
                "answer_quality", self.config.interview.default_answer_quality
            )
            expected_questions = config.get(
                "expected_questions", self.config.interview.default_expected_questions
            )

            for i in range(
                expected_questions + self.config.interview.qa_loop_buffer
            ):  # Buffer for follow-ups
                try:
                    # Wait for next question (regular, follow-up, or completion)
                    message = None
                    message_type = None

                    try:
                        message_type, message = await bot.wait_for_next_question(
                            timeout=self.config.timeouts.question_timeout_sec
                        )

                        # Check if interview completed
                        if message_type == "complete":
                            context["summary"] = message
                            logger.info("Interview completed")
                            break

                    except TimeoutError:
                        # Timeout without completion message - interview may have ended
                        logger.warning(f"Timeout after {i} iterations - interview may be incomplete")
                        break

                    if not message:
                        break

                    # Store question/follow-up
                    if message_type == "question":
                        context["questions"].append(message)
                    elif message_type == "follow_up":
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
                    evaluation = await bot.wait_for_evaluation(
                        timeout=self.config.timeouts.evaluation_timeout_sec
                    )
                    context["evaluations"].append(evaluation)

                except Exception as e:
                    logger.error(f"Error in QA loop: {e}")
                    raise

        finally:
            # Disconnect
            await bot.disconnect()

            # Store bot metrics
            context["bot_metrics"] = bot.get_metrics()

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
            context: Interview context
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
                    expression, context, interview_id, self.http_client
                )

                if result:
                    passed += 1
                    logger.info(f"[PASS] {message}")
                else:
                    failed += 1
                    logger.error(f"[FAIL] {message} (expression: {expression})")

            except Exception as e:
                failed += 1
                logger.error(f"[FAIL] {message} (error: {e})")

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

        # For MVP: Return 0.0 (cost tracking deferred)
        # TODO: Implement tiktoken or LangSmith API integration
        return 0.0

    def _compare_to_baseline(
        self,
        results: TestResults,
        scenarios_file: Path,
    ) -> dict[str, Any]:
        """Compare results to baseline metrics.

        Args:
            results: Test results
            scenarios_file: Scenarios file path

        Returns:
            Comparison dict
        """
        baseline_path = Path(__file__).parent / self.config.paths.baseline_path

        if not baseline_path.exists():
            logger.warning(f"Baseline not found: {baseline_path}")
            return {}

        with open(baseline_path) as f:
            baseline = json.load(f)

        # Determine test type (mock or real)
        test_type = "mock_tests" if "mock" in scenarios_file.name else "real_tests"
        baseline_data = baseline.get(test_type, {})

        if not baseline_data:
            return {}

        avg_duration = results.total_duration_sec / results.total if results.total > 0 else 0
        avg_cost = results.total_cost_usd / results.total if results.total > 0 else 0

        return {
            "test_type": test_type,
            "baseline_version": baseline.get("version"),
            "comparisons": {
                "duration": {
                    "current": avg_duration,
                    "baseline": baseline_data.get("avg_duration_sec", 0),
                    "delta_pct": (
                        (
                            (avg_duration - baseline_data.get("avg_duration_sec", 0))
                            / baseline_data.get("avg_duration_sec", 1)
                        )
                        * 100
                    ),
                },
                "cost": {
                    "current": avg_cost,
                    "baseline": baseline_data.get("avg_cost_usd", 0),
                    "delta_pct": (
                        (
                            (avg_cost - baseline_data.get("avg_cost_usd", 0))
                            / baseline_data.get("avg_cost_usd", 0.01)
                        )
                        * 100
                        if baseline_data.get("avg_cost_usd", 0) > 0
                        else 0
                    ),
                },
            },
        }

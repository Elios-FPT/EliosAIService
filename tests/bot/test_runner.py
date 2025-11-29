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
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from .answer_generator import AnswerGenerator
from .answer_strategy import AnswerStrategyEngine
from .assertion_validator import AssertionValidator
from .config import BotConfig, get_config
from .metrics_collector import MetricsCollector
from .sql_loader import (
    DataSeedConfig,
    build_data_seed_config,
    execute_sql_fixture,
)
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


class AttrDict(dict):
    """Dictionary with attribute access (used in assertions)."""

    def __getattr__(self, item: str):
        try:
            value = self[item]
        except KeyError as exc:
            raise AttributeError(item) from exc

        if isinstance(value, dict):
            return AttrDict(value)
        if isinstance(value, list):
            return [_as_attr_dict(v) for v in value]
        return value


def _as_attr_dict(value: Any):
    """Recursively convert dicts to AttrDict for attribute access."""
    if isinstance(value, dict):
        return AttrDict({k: _as_attr_dict(v) for k, v in value.items()})
    if isinstance(value, list):
        return [_as_attr_dict(item) for item in value]
    return value


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
    metadata: dict[str, Any] = field(default_factory=dict)


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
        config: BotConfig | None = None,
    ):
        """Initialize test runner.

        Args:
            base_url: API base URL (overrides config if provided)
            config: Bot configuration (uses global config if not provided)
        """
        self.config = config or get_config()

        # Use explicit params if provided, otherwise use config
        self.base_url = base_url or self.config.api.base_url
        self.output_dir = Path(self.config.paths.output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

        self.ws_base_url = self.base_url.replace("http://", "ws://").replace(
            "https://", "wss://"
        )

        self.answer_generator = AnswerGenerator()
        self.metrics_collector = MetricsCollector()
        self.assertion_validator = AssertionValidator()

        self.http_client: httpx.AsyncClient | None = None
        self._bot_root = Path(__file__).parent

    async def run_all_tests(
        self,
        scenarios_file: Path,
    ) -> TestResults:
        """Run all scenarios in file.

        Args:
            scenarios_file: Path to YAML scenarios file

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

        test_results.baseline_comparison = self._compare_to_baseline(
            test_results, scenarios_file
        )

        return test_results

    async def run_single_test(
        self,
        scenarios_file: Path,
        scenario_id: str,
    ) -> TestResults:
        """Run a single scenario from file without iterating through others."""
        logger.info(
            f"Loading single scenario '{scenario_id}' from {scenarios_file}"
        )
        with open(scenarios_file) as f:
            data = yaml.safe_load(f)

        scenarios = data.get("scenarios", [])
        scenario = next(
            (s for s in scenarios if s.get("id") == scenario_id), None
        )
        if not scenario:
            msg = (
                f"Scenario '{scenario_id}' not found in {scenarios_file}"
            )
            logger.error(msg)
            raise ValueError(msg)

        self.http_client = httpx.AsyncClient(
            base_url=self.base_url, timeout=self.config.api.timeout_sec
        )

        start_time = time.time()
        try:
            result = await self.run_scenario(scenario)
        finally:
            await self.http_client.aclose()

        total_duration = time.time() - start_time

        test_results = TestResults(
            total=1,
            passed=1 if result.status == "passed" else 0,
            failed=1 if result.status == "failed" else 0,
            skipped=1 if result.status == "skipped" else 0,
            total_duration_sec=total_duration,
            total_cost_usd=result.cost_usd,
            scenarios=[result],
            metrics=self.metrics_collector.get_summary(),
        )

        # Always compare to baseline
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
        scenario_metadata: dict[str, Any] = {}

        try:
            # Always use mock adapters
            os.environ["USE_MOCK_ADAPTERS"] = "true"

            # Execute mock scenario
            (
                interview_id,
                ws_url,
                context,
                metadata,
                question_map,
            ) = await self._run_mock_scenario(scenario_id, config)

            scenario_metadata.update(metadata)

            # Log expected vs actual responses/states for easier debugging
            self._log_expectations(
                scenario_id=scenario_id,
                config=config,
                context=context,
            )

            # Validate assertions
            assertions_passed, assertions_failed = await self._validate_assertions(
                assertions, context, interview_id
            )

            # Calculate cost (always 0.0 for mock tests)
            cost = await self._calculate_cost(interview_id)

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
            metadata=scenario_metadata,
        )

    async def _run_mock_scenario(
        self, scenario_id: str, config: dict
    ) -> tuple[
        UUID, str, dict[str, Any], dict[str, Any], dict[UUID, UUID] | None
    ]:
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
        metadata: dict[str, Any] = {}

        # Create DB session/engine
        engine = create_async_engine(settings.async_database_url, echo=False)
        async_session = sessionmaker(
            engine, class_=AsyncSession, expire_on_commit=False
        )

        try:
            data_seed_config = build_data_seed_config(
                config.get("data_seed"),
                self._bot_root,
            )

            if data_seed_config:
                fixture_result = await execute_sql_fixture(
                    engine, data_seed_config.sql_path
                )
                metadata["data_seed"] = {
                    "sql_file": str(data_seed_config.sql_path.relative_to(self._bot_root)),
                    "checksum": fixture_result.checksum,
                    "statements": fixture_result.statements_executed,
                    "duration_ms": fixture_result.duration_ms,
                }

                async with async_session() as session:
                    await self._verify_seeded_data(session, data_seed_config)

                interview_id = data_seed_config.interview_id
                question_map = None
            else:
                async with async_session() as session:
                    db_helper = DatabaseHelper(session, self.config)

                    (
                        _candidate_id,
                        interview_id,
                        _question_ids,
                        question_map,
                    ) = await db_helper.insert_mock_interview_data(
                        cv_fixture=config["cv_fixture"],
                        expected_questions=config["expected_questions"],
                        question_fixture=config.get("question_fixture"),
                    )

            ws_url = f"{self.ws_base_url}/ws/interviews/{interview_id}"

            ideal_answer_map = self._load_ideal_answers(
                config.get("question_fixture"), question_map
            )

            # Run WebSocket QA phase only
            context = await self._run_websocket_qa(
                scenario_id,
                interview_id,
                ws_url,
                config,
                ideal_answer_map,
                question_map,
            )

            return interview_id, ws_url, context, metadata, question_map

        finally:
            # Cleanup engine
            await engine.dispose()

    def _load_ideal_answers(
        self,
        fixture_name: str | None,
        question_map: dict[UUID, UUID] | None = None,
    ) -> dict[str, str]:
        """Load ideal answers from question fixture (if provided)."""
        if not fixture_name:
            return {}

        fixtures_dir = Path(__file__).parent / "fixtures" / "questions"
        fixture_path = fixtures_dir / fixture_name

        if not fixture_path.exists():
            logger.warning("Question fixture not found for ideal answers: %s", fixture_path)
            return {}

        try:
            with open(fixture_path) as f:
                data = json.load(f)
        except Exception as exc:
            logger.warning(
                "Failed to read question fixture %s: %s", fixture_path, exc
            )
            return {}

        ideal_map: dict[str, str] = {}
        for payload in data.get("questions", []):
            question_id = payload.get("id")
            ideal_answer = payload.get("ideal_answer")
            if question_id and ideal_answer:
                actual_question_id = question_id
                if question_map:
                    try:
                        original_uuid = UUID(str(question_id))
                    except (ValueError, TypeError):
                        original_uuid = None

                    if original_uuid and original_uuid in question_map:
                        actual_question_id = question_map[original_uuid]

                ideal_map[str(actual_question_id)] = ideal_answer

        return ideal_map

    async def _verify_seeded_data(
        self,
        session: AsyncSession,
        data_seed: DataSeedConfig,
    ) -> None:
        """Ensure SQL fixtures inserted the expected records."""
        interview_exists = await session.execute(
            text("SELECT 1 FROM interviews WHERE id = :id"),
            {"id": data_seed.interview_id},
        )
        if interview_exists.scalar_one_or_none() is None:
            raise ValueError(
                f"SQL fixture did not insert interview {data_seed.interview_id}"
            )

        missing_questions: list[str] = []
        for question_id in data_seed.question_ids:
            question_exists = await session.execute(
                text("SELECT 1 FROM questions WHERE id = :id"),
                {"id": question_id},
            )
            if question_exists.scalar_one_or_none() is None:
                missing_questions.append(str(question_id))

        if missing_questions:
            raise ValueError(
                "SQL fixture missing question IDs: " + ", ".join(missing_questions)
            )


    async def _run_websocket_qa(
        self,
        scenario_id: str,
        interview_id: UUID,
        ws_url: str,
        config: dict,
        ideal_answer_map: dict[str, str] | None = None,
        question_map: dict[UUID, UUID] | None = None,
    ) -> dict[str, Any]:
        """Run WebSocket QA phase (common for both mock and real tests).

        Args:
            interview_id: Interview UUID
            ws_url: WebSocket URL
            config: Scenario config
            ideal_answer_map: Optional mapping of question_id -> ideal answer text

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

        strategy_engine = AnswerStrategyEngine(
            scenario_id=scenario_id,
            strategy_config=config.get("answer_strategy"),
            ideal_answers=ideal_answer_map or {},
            question_map=question_map,
        )

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
            expected_questions = config.get(
                "expected_questions", self.config.interview.default_expected_questions
            )

            loop_start_time = time.time()
            for i in range(
                expected_questions + self.config.interview.qa_loop_buffer
            ):  # Buffer for follow-ups
                try:
                    # Wait for next question (regular, follow-up, or completion)
                    message = None
                    message_type = None

                    iteration_start = time.time()
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
                        elapsed = time.time() - loop_start_time
                        waited = time.time() - iteration_start
                        logger.warning(
                            "Timeout after %s iterations (waited %.1fs, total %.1fs) - interview may be incomplete",
                            i,
                            waited,
                            elapsed,
                        )
                        break

                    if not message:
                        break

                    # Store question/follow-up
                    if message_type == "question":
                        context["questions"].append(message)
                    elif message_type == "follow_up":
                        context["follow_ups"].append(message)

                    # Generate answer
                    question_id_str = message["question_id"]
                    question_id = UUID(question_id_str)

                    def default_answer() -> str:
                        if config.get("answer_text") is not None:
                            return config["answer_text"]
                        answer_quality = config.get(
                            "answer_quality",
                            self.config.interview.default_answer_quality,
                        )
                        length_target = config.get("answer_text_length")
                        return self.answer_generator.generate(
                            message["text"],
                            answer_quality,
                            length_target=length_target,
                        )

                    answer_text = strategy_engine.get_answer(
                        question_id,
                        message["text"],
                        default_answer,
                    )

                    # Send answer (allow empty for error testing scenarios)
                    allow_empty = config.get("expect_error", False)
                    await bot.send_text_answer(question_id, answer_text, allow_empty=allow_empty)

                    context["answers"].append(
                        {
                            "type": "text_answer",
                            "question_id": str(question_id),
                            "answer_text": answer_text,
                        }
                    )

                    # Wait for evaluation
                    evaluation = await bot.wait_for_evaluation(
                        timeout=self.config.timeouts.evaluation_timeout_sec
                    )
                    context["evaluations"].append(_as_attr_dict(evaluation))

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

    async def _calculate_cost(self, interview_id: UUID) -> float:
        """Calculate cost for interview (always 0.0 for mock tests).

        Args:
            interview_id: Interview UUID

        Returns:
            Cost in USD (always 0.0 for mock adapters)
        """
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

        # Always use mock_tests (real tests removed)
        test_type = "mock_tests"
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

    def _log_expectations(
        self,
        scenario_id: str,
        config: dict[str, Any],
        context: dict[str, Any],
    ) -> None:
        """Log expected vs actual interview responses/states."""

        def log_pair(label: str, expected: Any, actual: Any) -> None:
            logger.info(
                "[%s] %s expected=%s actual=%s",
                scenario_id,
                label,
                expected,
                actual,
            )

        questions = context.get("questions", [])
        evaluations = context.get("evaluations", [])
        follow_ups = context.get("follow_ups", [])
        summary = context.get("summary") or {}
        metrics = context.get("bot_metrics") or {}
        metrics_summary = metrics.get("summary") or {}

        expected_questions = config.get("expected_questions")
        if expected_questions is not None:
            actual_questions = len(questions)
            actual_answers = len(context.get("answers", []))
            actual_evaluations = len(evaluations)
            log_pair("questions_received", expected_questions, actual_questions)
            log_pair("answers_sent", expected_questions, actual_answers)
            log_pair("evaluations_received", expected_questions, actual_evaluations)

        expected_follow_ups = config.get("expected_follow_ups")
        if expected_follow_ups is not None:
            log_pair("follow_ups_received", expected_follow_ups, len(follow_ups))

        if "expected_follow_ups" in config or metrics_summary:
            summary_counts = {
                "questions": metrics_summary.get("questions_received"),
                "answers": metrics_summary.get("answers_sent"),
                "evaluations": metrics_summary.get("evaluations_received"),
                "follow_ups": metrics_summary.get("follow_ups_received"),
            }
            logger.info(
                "[%s] bot_metrics.summary=%s",
                scenario_id,
                summary_counts,
            )

        expected_error = config.get("expect_error")
        if expected_error is not None:
            bot_errors = metrics.get("errors") or []
            summary_status = summary.get("status")
            actual_error = bool(bot_errors) or (summary_status == "ERROR")
            log_pair("error_state", bool(expected_error), actual_error)

        expected_state = config.get("expected_final_state")
        if expected_state is None:
            expected_state = "ERROR" if expected_error else "COMPLETE"

        actual_state = (
            summary.get("status")
            or summary.get("interview_status")
            or summary.get("state")
            or "UNKNOWN"
        )
        log_pair("final_state", expected_state, actual_state)

        if summary:
            summary_snapshot = {
                key: summary.get(key)
                for key in ["status", "overall_score", "total_questions", "ended_at"]
                if key in summary
            }
            logger.info(
                "[%s] completion_summary=%s",
                scenario_id,
                summary_snapshot or summary,
            )

        if config.get("track_transitions"):
            states = [entry.get("state") for entry in metrics.get("states", [])]
            logger.info(
                "[%s] state_transitions expected=tracked actual=%s",
                scenario_id,
                states or [],
            )

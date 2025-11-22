"""CLI entry point for running interview test bot.

Usage:
    python -m tests.bot.run_tests --scenarios all
    python -m tests.bot.run_tests --scenarios mock
    python -m tests.bot.run_tests --scenarios real
    python -m tests.bot.run_tests --scenario mock_001_basic_flow
"""

import argparse
import asyncio
import logging
import os
import sys
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv

from .config import BotConfig, reload_config
from .report_generator import ReportGenerator
from .test_runner import TestRunner

# Check for test environment setup
load_dotenv()
if os.getenv("ENVIRONMENT", "").lower() != "test":
    print("[WARN] ENVIRONMENT is not set to 'test'")
    print("   The main application server will not load .env.test configuration")
    print("   To fix this:")
    print("   1. Copy .env.test.example to .env.test")
    print("   2. Set ENVIRONMENT=test in .env.test")
    print("   3. Start server: python -m src.main")
    print("   4. Run tests: python -m tests.bot.run_tests")
    print()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)

logger = logging.getLogger(__name__)


async def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Interview Test Bot - Automated testing for interview system"
    )

    parser.add_argument(
        "--scenarios",
        choices=["all", "mock", "real"],
        default="all",
        help="Which scenarios to run (default: all)",
    )

    parser.add_argument(
        "--scenario",
        type=str,
        help="Run single scenario by ID (e.g., mock_001_basic_flow)",
    )

    parser.add_argument(
        "--output",
        type=str,
        default="reports/",
        help="Output directory for reports (default: reports/)",
    )

    parser.add_argument(
        "--base-url",
        type=str,
        default="http://localhost:8000",
        help="API base URL (default: http://localhost:8000)",
    )

    parser.add_argument(
        "--no-baseline",
        action="store_true",
        help="Disable baseline comparison",
    )

    parser.add_argument(
        "--config",
        type=str,
        help="Path to custom bot configuration YAML file",
    )

    args = parser.parse_args()

    # Load config (custom if provided, otherwise default)
    config = reload_config(args.config) if args.config else BotConfig.load()

    # Determine scenarios file(s)
    scenarios_dir = Path(__file__).parent / config.paths.scenarios_dir
    scenarios_files = []

    if args.scenario:
        # Run single scenario (need to find which file it's in)
        for scenario_file in scenarios_dir.glob("*.yaml"):
            scenarios_files.append(scenario_file)
    elif args.scenarios == "all":
        scenarios_files = list(scenarios_dir.glob("*.yaml"))
    elif args.scenarios == "mock":
        scenarios_files = [scenarios_dir / "mock_scenarios.yaml"]
    elif args.scenarios == "real":
        scenarios_files = [scenarios_dir / "real_scenarios.yaml"]

    if not scenarios_files:
        logger.error("No scenario files found")
        sys.exit(1)

    logger.info(f"Running scenarios from {len(scenarios_files)} file(s)")

    # Create runner (CLI args override config values)
    runner = TestRunner(
        base_url=args.base_url if args.base_url != parser.get_default("base_url") else None,
        output_dir=args.output if args.output != parser.get_default("output") else None,
        config=config,
    )

    # Run tests
    all_results = []

    for scenarios_file in scenarios_files:
        logger.info(f"\nRunning scenarios from: {scenarios_file}")

        results = await runner.run_all_tests(
            scenarios_file=scenarios_file,
            enable_baseline_comparison=not args.no_baseline,
        )

        all_results.append((scenarios_file, results))

    # Generate reports
    report_gen = ReportGenerator()
    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")

    for scenarios_file, results in all_results:
        # Determine report prefix
        file_prefix = scenarios_file.stem  # e.g., "mock_scenarios"

        # JSON report
        json_path = Path(args.output) / f"{file_prefix}_{timestamp}.json"
        report_gen.generate_json(results, json_path)

        # HTML report
        html_path = Path(args.output) / f"{file_prefix}_{timestamp}.html"
        report_gen.generate_html(results, html_path)

        # Console summary
        console_summary = report_gen.generate_console_summary(results)
        print(console_summary)

    # Exit with error if any tests failed
    total_failed = sum(r.failed for _, r in all_results)
    if total_failed > 0:
        logger.error(f"FAILED: {total_failed} test(s) failed")
        sys.exit(1)
    else:
        logger.info("SUCCESS: All tests passed")
        sys.exit(0)


if __name__ == "__main__":
    asyncio.run(main())

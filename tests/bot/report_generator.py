"""Generate JSON and HTML test reports."""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any

from .test_runner import TestResults

logger = logging.getLogger(__name__)


class ReportGenerator:
    """Generate JSON and HTML test reports."""

    def generate_json(self, results: TestResults, output_path: Path) -> None:
        """Generate structured JSON report.

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
                    "assertions_passed": s.assertions_passed,
                    "assertions_failed": s.assertions_failed,
                    "errors": s.errors,
                }
                for s in results.scenarios
            ],
            "metrics": results.metrics,
            "baseline_comparison": results.baseline_comparison,
        }

        with open(output_path, "w") as f:
            json.dump(report, f, indent=2)

        logger.info(f"JSON report generated: {output_path}")

    def generate_html(self, results: TestResults, output_path: Path) -> None:
        """Generate human-readable HTML report.

        Args:
            results: Test results
            output_path: Output file path
        """
        # Calculate pass rate
        pass_rate = (
            (results.passed / results.total * 100) if results.total > 0 else 0
        )

        # Generate scenario rows
        scenario_rows = ""
        for s in results.scenarios:
            status_class = {
                "passed": "success",
                "failed": "danger",
                "skipped": "secondary",
            }.get(s.status, "secondary")

            scenario_rows += f"""
            <tr class="table-{status_class}">
                <td>{s.id}</td>
                <td>{s.name}</td>
                <td><span class="badge bg-{status_class}">{s.status.upper()}</span></td>
                <td>{s.duration_sec:.2f}s</td>
                <td>${s.cost_usd:.4f}</td>
                <td>{s.assertions_passed}/{s.assertions_passed + s.assertions_failed}</td>
            </tr>
            """

        # Baseline comparison HTML
        baseline_html = ""
        if results.baseline_comparison:
            comp = results.baseline_comparison.get("comparisons", {})
            duration_comp = comp.get("duration", {})
            cost_comp = comp.get("cost", {})

            baseline_html = f"""
            <h3>Baseline Comparison</h3>
            <ul>
                <li>Duration: {duration_comp.get('current', 0):.2f}s
                    (baseline: {duration_comp.get('baseline', 0):.2f}s,
                    {duration_comp.get('delta_pct', 0):+.1f}%)</li>
                <li>Cost: ${cost_comp.get('current', 0):.4f}
                    (baseline: ${cost_comp.get('baseline', 0):.4f},
                    {cost_comp.get('delta_pct', 0):+.1f}%)</li>
            </ul>
            """

        html = f"""
<!DOCTYPE html>
<html>
<head>
    <title>Interview Test Bot Report</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <style>
        body {{ padding: 20px; }}
        .summary-card {{ margin-bottom: 20px; }}
    </style>
</head>
<body>
    <div class="container">
        <h1>Interview Test Bot Report</h1>
        <p class="text-muted">Generated: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}</p>

        <div class="row summary-card">
            <div class="col-md-3">
                <div class="card">
                    <div class="card-body">
                        <h5 class="card-title">Total Tests</h5>
                        <p class="card-text display-4">{results.total}</p>
                    </div>
                </div>
            </div>
            <div class="col-md-3">
                <div class="card text-white bg-success">
                    <div class="card-body">
                        <h5 class="card-title">Passed</h5>
                        <p class="card-text display-4">{results.passed}</p>
                    </div>
                </div>
            </div>
            <div class="col-md-3">
                <div class="card text-white bg-danger">
                    <div class="card-body">
                        <h5 class="card-title">Failed</h5>
                        <p class="card-text display-4">{results.failed}</p>
                    </div>
                </div>
            </div>
            <div class="col-md-3">
                <div class="card">
                    <div class="card-body">
                        <h5 class="card-title">Pass Rate</h5>
                        <p class="card-text display-4">{pass_rate:.0f}%</p>
                    </div>
                </div>
            </div>
        </div>

        <div class="card mb-4">
            <div class="card-body">
                <h3>Summary</h3>
                <ul>
                    <li>Total Duration: {results.total_duration_sec:.2f}s</li>
                    <li>Total Cost: ${results.total_cost_usd:.4f}</li>
                    <li>Skipped: {results.skipped}</li>
                </ul>
                {baseline_html}
            </div>
        </div>

        <h2>Test Scenarios</h2>
        <table class="table table-striped">
            <thead>
                <tr>
                    <th>ID</th>
                    <th>Name</th>
                    <th>Status</th>
                    <th>Duration</th>
                    <th>Cost</th>
                    <th>Assertions</th>
                </tr>
            </thead>
            <tbody>
                {scenario_rows}
            </tbody>
        </table>
    </div>
</body>
</html>
        """

        with open(output_path, "w") as f:
            f.write(html)

        logger.info(f"HTML report generated: {output_path}")

    def generate_console_summary(self, results: TestResults) -> str:
        """Generate console-friendly summary.

        Args:
            results: Test results

        Returns:
            Summary text
        """
        pass_rate = (
            (results.passed / results.total * 100) if results.total > 0 else 0
        )

        summary = f"""
{'='*60}
Interview Test Bot Report
{'='*60}
Run Date: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}
Duration: {results.total_duration_sec:.1f}s
Total Cost: ${results.total_cost_usd:.4f}

Summary:
--------
Total Tests: {results.total}
Passed: {results.passed} ({pass_rate:.0f}%)
Failed: {results.failed}
Skipped: {results.skipped}

Scenarios:
----------
"""

        for s in results.scenarios:
            status_icon = {"passed": "✓", "failed": "✗", "skipped": "-"}.get(
                s.status, "?"
            )
            summary += f"{status_icon} {s.id}: {s.status} ({s.duration_sec:.1f}s)\n"

        if results.baseline_comparison:
            comp = results.baseline_comparison.get("comparisons", {})
            summary += f"\nBaseline Comparison:\n"
            summary += f"--------------------\n"

            duration_comp = comp.get("duration", {})
            cost_comp = comp.get("cost", {})

            summary += (
                f"Duration: {duration_comp.get('current', 0):.2f}s "
                f"(baseline: {duration_comp.get('baseline', 0):.2f}s, "
                f"{duration_comp.get('delta_pct', 0):+.1f}%)\n"
            )

            summary += (
                f"Cost: ${cost_comp.get('current', 0):.4f} "
                f"(baseline: ${cost_comp.get('baseline', 0):.4f}, "
                f"{cost_comp.get('delta_pct', 0):+.1f}%)\n"
            )

        summary += f"\n{'='*60}\n"

        return summary

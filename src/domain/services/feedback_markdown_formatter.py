"""Markdown formatter for feedback results."""

from ...domain.models.feedback_result import (
    ActionableRecommendations,
    BestPractices,
    CodeActionableRecommendation,
    CodeQuality,
    CodeReviewFeedbackResult,
    CVFeedbackResult,
    FeedbackResult,
    MarketCompetitiveness,
    OverallAssessment,
    Recommendation,
    SectionFeedback,
)


class FeedbackMarkdownFormatter:
    """Convert FeedbackResult to markdown for frontend display.

    Pure domain service with no external dependencies.
    Formats CV and CODE feedback results with structured sections,
    headers, and styling (bold, emphasis, code blocks).
    """

    def format(self, result: FeedbackResult) -> str:
        """Format any FeedbackResult as markdown.

        Args:
            result: CVFeedbackResult or CodeReviewFeedbackResult

        Returns:
            Formatted markdown string

        Raises:
            ValueError: If result type is not supported
        """
        if isinstance(result, CVFeedbackResult):
            return self._format_cv_result(result)
        elif isinstance(result, CodeReviewFeedbackResult):
            return self._format_code_result(result)
        else:
            raise ValueError(f"Unsupported result type: {type(result)}")

    def _format_cv_result(self, result: CVFeedbackResult) -> str:
        """Format CV feedback as markdown.

        Args:
            result: CVFeedbackResult to format

        Returns:
            Formatted markdown string
        """
        lines = ["# CV Feedback Analysis", ""]

        # Overall Assessment
        lines.append("## Overall Assessment")
        lines.append("")
        lines.append(f"**Score**: {result.overall_assessment.overall_score:.1f}/100")
        lines.append("")
        lines.append(result.overall_assessment.summary)
        lines.append("")
        lines.append("---")
        lines.append("")

        # Professional Summary
        lines.append("## Professional Summary")
        lines.append("")
        lines.extend(
            self._format_section_feedback(
                result.professional_summary, "Professional Summary", max_score=15.0
            )
        )
        lines.append("")

        # Work Experience
        lines.append("## Work Experience")
        lines.append("")
        lines.extend(
            self._format_section_feedback(
                result.work_experience, "Work Experience", max_score=25.0
            )
        )
        lines.append("")

        # Projects
        lines.append("## Projects")
        lines.append("")
        lines.extend(
            self._format_section_feedback(result.projects, "Projects", max_score=25.0)
        )
        lines.append("")

        # Skills
        lines.append("## Skills")
        lines.append("")
        lines.extend(
            self._format_section_feedback(result.skills, "Skills", max_score=20.0)
        )
        lines.append("")

        # Actionable Recommendations
        lines.append("## Actionable Recommendations")
        lines.append("")
        lines.extend(self._format_recommendations(result.actionable_recommendations))
        lines.append("")

        # Market Competitiveness
        lines.append("## Market Competitiveness")
        lines.append("")
        lines.append(f"**Assessment**: {result.market_competitiveness.assessment}")
        lines.append("")

        if result.market_competitiveness.target_roles:
            lines.append("**Target Roles**:")
            for role in result.market_competitiveness.target_roles:
                lines.append(f"- {role}")
            lines.append("")

        if result.market_competitiveness.improvement_areas:
            lines.append("**Improvement Areas**:")
            for area in result.market_competitiveness.improvement_areas:
                lines.append(f"- {area}")
            lines.append("")

        return "\n".join(lines)

    def _format_code_result(self, result: CodeReviewFeedbackResult) -> str:
        """Format code feedback as markdown.

        Args:
            result: CodeReviewFeedbackResult to format

        Returns:
            Formatted markdown string
        """
        lines = ["# Code Review Feedback", ""]

        # Overall Assessment
        lines.append("## Overall Assessment")
        lines.append("")
        lines.append(f"**Score**: {result.overall_assessment.overall_score:.1f}/100")
        lines.append("")
        lines.append(result.overall_assessment.summary)
        lines.append("")
        lines.append("---")
        lines.append("")

        # Code Quality
        lines.append("## Code Quality")
        lines.append("")
        lines.append(f"**Score**: {result.code_quality.score:.1f}/25")
        lines.append("")
        lines.append(f"**Feedback**: {result.code_quality.feedback}")
        lines.append("")

        if result.code_quality.suggestions:
            lines.append("**Suggestions**:")
            for suggestion in result.code_quality.suggestions:
                lines.append(f"- {suggestion}")
            lines.append("")

        # Best Practices
        lines.append("## Best Practices")
        lines.append("")
        lines.append(f"**Score**: {result.best_practices.score:.1f}/20")
        lines.append("")
        lines.append(f"**Feedback**: {result.best_practices.feedback}")
        lines.append("")

        if result.best_practices.principles_followed:
            lines.append("**Principles Followed**:")
            for principle in result.best_practices.principles_followed:
                lines.append(f"- *{principle}*")
            lines.append("")

        if result.best_practices.principles_violated:
            lines.append("**Principles Violated**:")
            for principle in result.best_practices.principles_violated:
                lines.append(f"- **{principle}**")
            lines.append("")

        if result.best_practices.suggestions:
            lines.append("**Suggestions**:")
            for suggestion in result.best_practices.suggestions:
                lines.append(f"- {suggestion}")
            lines.append("")

        # Top Recommendation
        lines.append("## Top Recommendation")
        lines.append("")
        lines.append(f"**Recommendation**: {result.actionable_recommendations.recommendation}")
        lines.append("")
        lines.append(f"**Impact**: {result.actionable_recommendations.impact}")
        lines.append("")
        lines.append(f"**Effort**: {result.actionable_recommendations.effort}")
        lines.append("")

        if result.actionable_recommendations.line_reference:
            lines.append(f"**Line Reference**: `` `{result.actionable_recommendations.line_reference}` ``")
            lines.append("")

        return "\n".join(lines)

    def _format_score(self, score: float, max_score: float) -> str:
        """Format score with max score.

        Args:
            score: Current score
            max_score: Maximum possible score

        Returns:
            Formatted score string
        """
        return f"{score:.1f}/{max_score:.0f}"

    def _format_section_feedback(
        self, section: SectionFeedback, title: str, max_score: float
    ) -> list[str]:
        """Format section feedback as markdown.

        Args:
            section: SectionFeedback to format
            title: Section title
            max_score: Maximum score for this section

        Returns:
            List of markdown lines
        """
        lines = []
        lines.append(f"**Score**: {self._format_score(section.score, max_score)}")
        lines.append("")
        lines.append(f"**Feedback**: {section.feedback}")
        lines.append("")

        if section.suggestions:
            lines.append("**Suggestions**:")
            for suggestion in section.suggestions:
                lines.append(f"- {suggestion}")
            lines.append("")

        return lines

    def _format_recommendations(
        self, recommendations: ActionableRecommendations
    ) -> list[str]:
        """Format actionable recommendations as markdown.

        Args:
            recommendations: ActionableRecommendations to format

        Returns:
            List of markdown lines
        """
        lines = []

        if recommendations.high_priority:
            lines.append("### High Priority")
            for idx, rec in enumerate(recommendations.high_priority, 1):
                lines.append(
                    f"{idx}. **{rec.recommendation}** - *Impact*: {rec.impact} | *Effort*: {rec.effort}"
                )
            lines.append("")

        if recommendations.medium_priority:
            lines.append("### Medium Priority")
            for idx, rec in enumerate(recommendations.medium_priority, 1):
                lines.append(
                    f"{idx}. **{rec.recommendation}** - *Impact*: {rec.impact} | *Effort*: {rec.effort}"
                )
            lines.append("")

        if recommendations.low_priority:
            lines.append("### Low Priority")
            for idx, rec in enumerate(recommendations.low_priority, 1):
                lines.append(
                    f"{idx}. **{rec.recommendation}** - *Impact*: {rec.impact} | *Effort*: {rec.effort}"
                )
            lines.append("")

        if not any(
            [
                recommendations.high_priority,
                recommendations.medium_priority,
                recommendations.low_priority,
            ]
        ):
            lines.append("*No recommendations provided.*")
            lines.append("")

        return lines


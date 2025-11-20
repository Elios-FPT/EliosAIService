"""Confidence scoring for extracted CV fields.

This module calculates confidence scores (0.0-1.0) for extracted fields
to guide LLM fallback decisions.
"""

import re


class ConfidenceScorer:
    """Calculate confidence scores for extracted CV fields.

    Confidence range: 0.0 (no confidence) to 1.0 (certain).
    Scores guide LLM fallback decision (threshold: 0.7).
    """

    # Field-specific confidence weights
    FIELD_WEIGHTS = {
        "email": 1.0,  # Critical field
        "phone": 0.9,  # Important
        "dates": 0.7,  # Supporting
        "sections": 0.8,  # Structure indicator
        "urls": 0.6,  # Optional
    }

    def score_field(
        self,
        field_type: str,
        extracted_values: list[str] | dict[str, tuple[int, str]],
        validation_passed: bool = True,
    ) -> float:
        """Calculate confidence score for a single field.

        Args:
            field_type: Type of field ("email", "phone", "dates", "sections", "urls")
            extracted_values: List of extracted values or dict of sections
            validation_passed: Whether extracted values passed validation

        Returns:
            Confidence score 0.0-1.0

        Scoring Logic:
        - Regex match + validation pass = 0.95 (high confidence)
        - Regex match + validation fail = 0.50 (low confidence)
        - No match = 0.0 (no confidence)
        """
        if not extracted_values:
            return 0.0  # No extraction

        # Base confidence for successful regex match
        if validation_passed:
            base_confidence = 0.95
        else:
            base_confidence = 0.50  # Extracted but suspicious

        # Adjust by field type (structured fields more reliable)
        if field_type in ["email", "phone"]:
            # Structured formats → high confidence
            return base_confidence
        elif field_type == "dates":
            # Multiple date formats → medium confidence
            return base_confidence * 0.90
        elif field_type == "sections":
            # Section headers → medium-high confidence
            section_count = len(extracted_values)
            if section_count >= 3:  # Good CV structure
                return 0.90
            elif section_count >= 2:
                return 0.75
            else:
                return 0.50  # Poorly structured CV
        elif field_type == "urls":
            # URLs optional → lower priority
            return 0.85 if validation_passed else 0.40
        else:
            return 0.50  # Unknown field type

    def aggregate_confidence(
        self, field_scores: dict[str, float], critical_fields: list[str] | None = None
    ) -> float:
        """Aggregate field-level confidences into overall score.

        Args:
            field_scores: Dict of field_type → confidence score
            critical_fields: Fields that must have high confidence
                (defaults to ["email", "phone", "sections"])

        Returns:
            Aggregated confidence 0.0-1.0

        Aggregation Strategy:
        - Weighted average across all fields
        - Penalty if critical fields missing or low confidence
        """
        if critical_fields is None:
            critical_fields = ["email", "phone", "sections"]

        if not field_scores:
            return 0.0

        # Weighted sum
        weighted_sum = 0.0
        total_weight = 0.0

        for field, score in field_scores.items():
            weight = self.FIELD_WEIGHTS.get(field, 0.5)
            weighted_sum += score * weight
            total_weight += weight

        if total_weight == 0:
            return 0.0

        avg_confidence = weighted_sum / total_weight

        # Apply penalty for missing/low critical fields
        penalty = 1.0
        for critical_field in critical_fields:
            if critical_field not in field_scores:
                penalty *= 0.80  # 20% penalty per missing field
            elif field_scores[critical_field] < 0.50:
                penalty *= 0.90  # 10% penalty for low confidence

        return avg_confidence * penalty

    def validate_email(self, email: str) -> bool:
        """Validate email format beyond regex (basic checks).

        Additional checks:
        - Single @ symbol
        - No consecutive dots
        - Domain has valid TLD
        - Local part not too long

        Args:
            email: Email address to validate

        Returns:
            True if validation passes, False otherwise
        """
        if ".." in email:
            return False
        # Check for exactly one @ symbol
        if email.count("@") != 1:
            return False
        local, domain = email.rsplit("@", 1)
        if len(local) > 64:  # RFC 5321 limit
            return False
        if "." not in domain:
            return False
        return True

    def validate_phone(self, phone: str) -> bool:
        """Validate phone number (basic length check).

        Args:
            phone: Phone number to validate

        Returns:
            True if validation passes, False otherwise
        """
        digits = re.sub(r"\D", "", phone)
        # US: 10 digits, International: 10-15 digits
        return 10 <= len(digits) <= 15

    def validate_date(self, date_str: str) -> bool:
        """Validate date format (basic check).

        Args:
            date_str: Date string to validate

        Returns:
            True if validation passes, False otherwise
        """
        # Accept "Present", "Current" as valid
        if date_str.lower() in ["present", "current", "now", "ongoing"]:
            return True
        # Accept if contains 4-digit year
        return bool(re.search(r"\b\d{4}\b", date_str))

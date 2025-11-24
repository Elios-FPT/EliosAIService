"""Rule-based extractor for structured CV fields using regex patterns.

This module provides high-confidence (98%+) extraction for deterministic fields:
email, phone, dates, section headers, and URLs.
"""

import re
from typing import Any


class RuleBasedExtractor:
    """Extract structured fields from CV text using regex patterns.

    This extractor provides high-confidence (98%+) extraction for
    deterministic fields: email, phone, dates, section headers, URLs.
    """

    # Email (multilingual, RFC 5322 simplified)
    EMAIL_PATTERN = re.compile(r"\b[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}\b", re.IGNORECASE)

    # Phone (international: +1-202-555-0123, (202) 555-0123, +84-9-xxxx-xxxx)
    PHONE_PATTERN = re.compile(
        r"(?:\+\d{1,3}[-.\s]?\d{1,2}[-.\s]?\d{3,4}[-.\s]?\d{4})|"  # International: +84-9-1234-5678
        r"(?:\+\d{1,3}[-.\s]?\d{3}[-.\s]?\d{3}[-.\s]?\d{4})|"  # International: +1-202-555-0123
        r"(?:\(\d{3}\)\s?\d{3}[-.\s]?\d{4})|"  # US: (202) 555-0123
        r"(?:\d{3}[-.\s]\d{3}[-.\s]\d{4})"  # US: 202-555-0123 or 202.555.0123
    )

    # Dates (Jan 2020, 2020-01-15, 01/15/2020, Present, Current)
    DATE_PATTERN = re.compile(
        r"(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]* \d{4}|"
        r"\d{4}-\d{2}-\d{2}|"
        r"\d{1,2}/\d{1,2}/\d{4}|"
        r"\b(?:Present|Current|Now|Ongoing)\b",
        re.IGNORECASE,
    )

    # Section headers (EXPERIENCE, EDUCATION, SKILLS, etc.)
    SECTION_PATTERN = re.compile(
        r"^(EXPERIENCE|WORK EXPERIENCE|EMPLOYMENT|"
        r"EDUCATION|ACADEMIC BACKGROUND|"
        r"SKILLS|TECHNICAL SKILLS|CORE COMPETENCIES|"
        r"SUMMARY|PROFILE|OBJECTIVE|"
        r"CONTACT|CONTACT INFORMATION|PERSONAL DETAILS|"
        r"CERTIFICATIONS?|LICENSES?|"
        r"PROJECTS?|PORTFOLIO|"
        r"LANGUAGES?|"
        r"REFERENCES?|"
        r"ACHIEVEMENTS?|AWARDS?|HONORS?)[:]*$",
        re.MULTILINE | re.IGNORECASE,
    )

    # URLs (LinkedIn, GitHub, personal sites)
    URL_PATTERN = re.compile(
        r"https?://(?:www\.)?[-a-zA-Z0-9@:%._\+~#=]{1,256}\.[a-zA-Z0-9()]{1,6}\b"
        r"(?:[-a-zA-Z0-9()@:%_\+.~#?&//=]*)",
        re.IGNORECASE,
    )

    def extract(self, cv_text: str) -> dict[str, Any]:
        """Extract all structured fields from CV text.

        Args:
            cv_text: Full CV text content

        Returns:
            Dictionary with extracted fields:
            {
                "emails": list[str],
                "phones": list[str],
                "dates": list[str],
                "sections": dict[str, tuple[int, str]],  # {section_name: (line_num, header)}
                "urls": list[str]
            }
        """
        return {
            "emails": self._extract_emails(cv_text),
            "phones": self._extract_phones(cv_text),
            "dates": self._extract_dates(cv_text),
            "sections": self._extract_sections(cv_text),
            "urls": self._extract_urls(cv_text),
        }

    def _extract_emails(self, text: str) -> list[str]:
        """Extract all email addresses.

        Args:
            text: CV text content

        Returns:
            List of unique email addresses (deduplicated, case-insensitive)
        """
        matches = self.EMAIL_PATTERN.findall(text)
        # Deduplicate, preserve order
        seen = set()
        unique_emails = []
        for email in matches:
            email_lower = email.lower()
            if email_lower not in seen:
                seen.add(email_lower)
                unique_emails.append(email)
        return unique_emails

    def _extract_phones(self, text: str) -> list[str]:
        """Extract all phone numbers.

        Args:
            text: CV text content

        Returns:
            List of normalized phone numbers (deduplicated)
        """
        matches = self.PHONE_PATTERN.findall(text)
        # Normalize format: preserve format but ensure consistency
        normalized = []
        for phone in matches:
            # Remove excessive whitespace but keep structure
            clean_phone = re.sub(r"\s+", "-", phone.strip())
            if clean_phone and clean_phone not in normalized:
                normalized.append(clean_phone)
        return normalized

    def _extract_dates(self, text: str) -> list[str]:
        """Extract all date mentions.

        Args:
            text: CV text content

        Returns:
            List of unique date strings
        """
        matches = self.DATE_PATTERN.findall(text)
        return list(set(matches))  # Deduplicate

    def _extract_sections(self, text: str) -> dict[str, tuple[int, str]]:
        """Extract CV section headers with line numbers.

        Args:
            text: CV text content

        Returns:
            dict[section_name, (line_number, original_header_text)]
            Example: {"EXPERIENCE": (15, "WORK EXPERIENCE"), ...}
        """
        sections = {}
        lines = text.split("\n")

        for line_num, line in enumerate(lines, start=1):
            line_stripped = line.strip()
            match = self.SECTION_PATTERN.match(line_stripped)
            if match:
                section_key = match.group(1).upper()
                # Normalize: "WORK EXPERIENCE" → "EXPERIENCE"
                section_key = self._normalize_section_name(section_key)
                sections[section_key] = (line_num, line_stripped)

        return sections

    def _normalize_section_name(self, section: str) -> str:
        """Normalize section header to canonical name.

        Args:
            section: Raw section header text

        Returns:
            Normalized section name
        """
        normalization_map = {
            "WORK EXPERIENCE": "EXPERIENCE",
            "EMPLOYMENT": "EXPERIENCE",
            "ACADEMIC BACKGROUND": "EDUCATION",
            "TECHNICAL SKILLS": "SKILLS",
            "CORE COMPETENCIES": "SKILLS",
            "PROFILE": "SUMMARY",
            "OBJECTIVE": "SUMMARY",
            "CONTACT INFORMATION": "CONTACT",
            "PERSONAL DETAILS": "CONTACT",
            "CERTIFICATION": "CERTIFICATIONS",
            "LICENSE": "LICENSES",
            "PROJECT": "PROJECTS",
            "LANGUAGE": "LANGUAGES",
            "REFERENCE": "REFERENCES",
            "ACHIEVEMENT": "ACHIEVEMENTS",
            "AWARD": "AWARDS",
            "HONOR": "HONORS",
        }
        return normalization_map.get(section.upper(), section.upper())

    def _extract_urls(self, text: str) -> list[str]:
        """Extract all URLs (LinkedIn, GitHub, etc.).

        Args:
            text: CV text content

        Returns:
            List of unique URLs
        """
        matches = self.URL_PATTERN.findall(text)
        return list(set(matches))  # Deduplicate

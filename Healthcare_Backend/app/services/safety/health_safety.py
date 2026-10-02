"""
app/services/safety/health_safety.py

Safety validation and response processing for healthcare responses.
This layer is separate from the LLM service and can be reused across
different AI providers (Nemotron, Gemini, RAG, etc.).
"""
import re
from typing import Tuple

# Mandatory disclaimer for all health responses
MANDATORY_DISCLAIMER = (
    "This information is general health information and is not a diagnosis "
    "or a substitute for professional medical advice."
)

# Patterns that indicate potentially dangerous content
DANGEROUS_PATTERNS = [
    # Diagnosis claims
    r"\b(you have|you are suffering from|you definitely have|this is|this confirms|diagnosed with)\b",
    # Prescription claims - medication names and dosages
    r"\b(take|prescribe|dosage of|mg of|milligrams of)\b.*\b(medication|medicine|drug|pill)\b",
    r"\b\d+\s*(mg|milligrams|mcg|micrograms|g|grams|ml|milliliters|units?)\b.*\b(of|daily|twice|once)\b",
    r"\b(take|prescribe)\b.*\b\d+\s*(mg|milligrams|mcg|micrograms|g|grams|ml|milliliters|units?)\b",
    # Stop medication claims
    r"\b(stop taking|discontinue|quit|halt)\b.*\b(medication|medicine|prescription|drug)\b",
    # Certainty claims about user's condition
    r"\b(this proves|this confirms|this means you have|you certainly have)\b",
    # Emergency instructions that could be dangerous
    r"\b(do not call|don't call|avoid|instead of)\b.*\b(911|emergency|ambulance|hospital)\b",
]

# Patterns for urgent symptoms that should trigger professional care advice
URGENT_SYMPTOMS = [
    r"\bchest pain\b",
    r"\bdifficulty breathing\b",
    r"\bshortness of breath\b",
    r"\bsevere.*bleeding\b",
    r"\bloss of consciousness\b",
    r"\bunconscious\b",
    r"\bstroke\b",
    r"\bheart attack\b",
    r"\bsevere.*allergic\b",
    r"\banaphylaxis\b",
    r"\bsuicidal\b",
    r"\bself.harm\b",
    r"\boverdose\b",
]


class SafetyValidator:
    """Validates and processes health responses for safety."""

    def __init__(self):
        self.dangerous_regex = [re.compile(p, re.IGNORECASE) for p in DANGEROUS_PATTERNS]
        self.urgent_regex = [re.compile(p, re.IGNORECASE) for p in URGENT_SYMPTOMS]

    def validate_response(self, response: str) -> Tuple[bool, list[str]]:
        """
        Check response for dangerous content.

        Returns:
            (is_safe, list_of_issues)
        """
        issues = []

        for pattern in self.dangerous_regex:
            if pattern.search(response):
                issues.append(f"Potentially dangerous content detected: {pattern.pattern}")

        return len(issues) == 0, issues

    def check_urgent_symptoms(self, user_message: str) -> bool:
        """Check if user message mentions urgent symptoms."""
        for pattern in self.urgent_regex:
            if pattern.search(user_message):
                return True
        return False

    def append_disclaimer(self, response: str) -> str:
        """Append mandatory disclaimer if not already present."""
        if MANDATORY_DISCLAIMER not in response:
            return f"{response}\n\n{MANDATORY_DISCLAIMER}"
        return response

    def append_urgent_warning(self, response: str) -> str:
        """Append urgent care warning if not present."""
        urgent_warning = (
            "If you are experiencing a medical emergency, please call emergency services "
            "(911 in the US) or go to the nearest emergency room immediately."
        )
        if urgent_warning not in response:
            return f"{response}\n\n{urgent_warning}"
        return response

    def process_response(self, user_message: str, model_response: str) -> str:
        """
        Full safety processing pipeline.

        1. Validate model response for dangerous content
        2. Check for urgent symptoms in user message
        3. Append mandatory disclaimer
        4. Append urgent warning if needed

        Returns the final safe response.
        """
        # Validate model response
        is_safe, issues = self.validate_response(model_response)
        if not is_safe:
            # Log issues (in production, use proper logging)
            # For safety, return a fallback response
            fallback = (
                "I'm unable to provide a safe response to that question. "
                "Please consult a healthcare professional for personalized medical advice."
            )
            return self.append_disclaimer(fallback)

        # Start with model response
        final_response = model_response

        # Add disclaimer
        final_response = self.append_disclaimer(final_response)

        # Check for urgent symptoms in user message
        if self.check_urgent_symptoms(user_message):
            final_response = self.append_urgent_warning(final_response)

        return final_response


# Singleton instance
_safety_validator: SafetyValidator = None


def get_safety_validator() -> SafetyValidator:
    """Get the singleton SafetyValidator instance."""
    global _safety_validator
    if _safety_validator is None:
        _safety_validator = SafetyValidator()
    return _safety_validator
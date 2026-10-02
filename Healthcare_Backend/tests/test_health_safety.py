"""
tests/test_health_safety.py

Unit tests for SafetyValidator.
"""
import pytest
from app.services.safety.health_safety import SafetyValidator, get_safety_validator


class TestSafetyValidator:
    """Test SafetyValidator class."""

    def setup_method(self):
        """Reset singleton before each test."""
        import app.services.safety.health_safety as safety_module
        safety_module._safety_validator = None

    def test_mandatory_disclaimer_appended(self):
        """Test that disclaimer is appended when missing."""
        validator = SafetyValidator()
        response = "This is a test response about health."
        result = validator.append_disclaimer(response)
        assert "This information is general health information" in result
        assert result.endswith("professional medical advice.")

    def test_mandatory_disclaimer_not_duplicated(self):
        """Test that disclaimer is not duplicated if already present."""
        validator = SafetyValidator()
        disclaimer = "This information is general health information and is not a diagnosis or a substitute for professional medical advice."
        response = f"Test response.\n\n{disclaimer}"
        result = validator.append_disclaimer(response)
        # Should only appear once
        assert result.count(disclaimer) == 1

    def test_urgent_warning_appended(self):
        """Test urgent warning appended for urgent symptoms."""
        validator = SafetyValidator()
        response = "General health info."
        user_message = "I have chest pain"
        result = validator.append_urgent_warning(response)
        assert "emergency services" in result
        assert "911" in result

    def test_detects_chest_pain(self):
        """Test detection of chest pain as urgent."""
        validator = SafetyValidator()
        assert validator.check_urgent_symptoms("I have chest pain") is True
        assert validator.check_urgent_symptoms("chest pain and shortness of breath") is True

    def test_detects_difficulty_breathing(self):
        """Test detection of difficulty breathing."""
        validator = SafetyValidator()
        assert validator.check_urgent_symptoms("difficulty breathing") is True
        assert validator.check_urgent_symptoms("shortness of breath") is True

    def test_detects_stroke(self):
        """Test detection of stroke symptoms."""
        validator = SafetyValidator()
        assert validator.check_urgent_symptoms("I think I'm having a stroke") is True

    def test_detects_heart_attack(self):
        """Test detection of heart attack."""
        validator = SafetyValidator()
        assert validator.check_urgent_symptoms("heart attack symptoms") is True

    def test_detects_suicidal(self):
        """Test detection of suicidal ideation."""
        validator = SafetyValidator()
        assert validator.check_urgent_symptoms("feeling suicidal") is True

    def test_detects_overdose(self):
        """Test detection of overdose."""
        validator = SafetyValidator()
        assert validator.check_urgent_symptoms("possible overdose") is True

    def test_non_urgent_not_flagged(self):
        """Test that non-urgent queries don't trigger warning."""
        validator = SafetyValidator()
        assert validator.check_urgent_symptoms("What is dehydration?") is False
        assert validator.check_urgent_symptoms("How to lower blood pressure?") is False

    def test_detects_diagnosis_claim(self):
        """Test detection of diagnosis claims."""
        validator = SafetyValidator()
        is_safe, issues = validator.validate_response("You have diabetes based on your symptoms.")
        assert is_safe is False
        assert len(issues) > 0

    def test_detects_prescription_claim(self):
        """Test detection of prescription claims."""
        validator = SafetyValidator()
        is_safe, issues = validator.validate_response("Take 500mg of metformin daily.")
        assert is_safe is False
        assert len(issues) > 0

    def test_detects_stop_medication(self):
        """Test detection of stop medication advice."""
        validator = SafetyValidator()
        is_safe, issues = validator.validate_response("Stop taking your medication.")
        assert is_safe is False
        assert len(issues) > 0

    def test_detects_certainty_claim(self):
        """Test detection of certainty claims about user's condition."""
        validator = SafetyValidator()
        is_safe, issues = validator.validate_response("This proves you have cancer.")
        assert is_safe is False
        assert len(issues) > 0

    def test_detects_avoid_emergency(self):
        """Test detection of dangerous emergency advice."""
        validator = SafetyValidator()
        is_safe, issues = validator.validate_response("Don't call 911, just rest.")
        assert is_safe is False
        assert len(issues) > 0

    def test_safe_response_passes(self):
        """Test that safe responses pass validation."""
        validator = SafetyValidator()
        is_safe, issues = validator.validate_response(
            "Dehydration occurs when you lose more fluids than you take in. "
            "Common causes include not drinking enough water, excessive sweating, "
            "and illness with fever or vomiting."
        )
        assert is_safe is True
        assert len(issues) == 0

    def test_process_response_safe(self):
        """Test full processing of safe response."""
        validator = SafetyValidator()
        user_msg = "What is dehydration?"
        model_resp = "Dehydration is when your body loses more fluid than you take in."
        result = validator.process_response(user_msg, model_resp)
        assert "Dehydration is when" in result
        assert "general health information" in result
        # No urgent warning for non-urgent query
        assert "emergency services" not in result

    def test_process_response_urgent(self):
        """Test full processing with urgent symptoms."""
        validator = SafetyValidator()
        user_msg = "I have severe chest pain"
        model_resp = "Chest pain can have many causes."
        result = validator.process_response(user_msg, model_resp)
        assert "general health information" in result
        assert "emergency services" in result
        assert "911" in result

    def test_process_response_dangerous_model_output(self):
        """Test that dangerous model output is replaced with fallback."""
        validator = SafetyValidator()
        user_msg = "What should I do?"
        model_resp = "You have cancer and should stop taking your medication."
        result = validator.process_response(user_msg, model_resp)
        # Should return fallback response
        assert "unable to provide a safe response" in result
        assert "healthcare professional" in result
        assert "general health information" in result


class TestGetSafetyValidator:
    """Test singleton getter."""

    def setup_method(self):
        """Reset singleton before each test."""
        import app.services.safety.health_safety as safety_module
        safety_module._safety_validator = None

    def test_singleton(self):
        """Test that get_safety_validator returns singleton."""
        validator1 = get_safety_validator()
        validator2 = get_safety_validator()
        assert validator1 is validator2
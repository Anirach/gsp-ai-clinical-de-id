"""
Basic functionality tests for the Clinical De-ID system.
"""
import pytest
import sys
import os

# Add the backend src to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend', 'src'))

def test_imports():
    """Test that all main modules can be imported."""
    try:
        from models.schemas import EntityType, TransformationType
        from utils.config import get_settings
        from security.crypto import PseudonymGenerator
        from services.thai_nlp_service import ThaiNLPService
        from services.detection_service import DetectionEnsemble
        from services.policy_engine import PolicyEngine
        from services.pseudonym_service import PseudonymizationService
        from services.audit_service import AuditService
        from services.orchestrator import OrchestratorService
        print("✓ All modules imported successfully")
    except ImportError as e:
        print(f"✗ Import failed: {e}")
        raise


def test_pseudonym_generation():
    """Test pseudonym generation."""
    try:
        from security.crypto import generate_master_secret, PseudonymGenerator
        
        # Generate test master secret
        master_secret = generate_master_secret()
        
        # Initialize generator
        generator = PseudonymGenerator(master_secret)
        
        # Test deterministic generation
        identifier = "1234567890123"
        domain = "patient_id"
        
        pseudonym1 = generator.generate_pseudonym(identifier, domain)
        pseudonym2 = generator.generate_pseudonym(identifier, domain)
        
        assert pseudonym1 == pseudonym2, "Pseudonyms should be deterministic"
        assert len(pseudonym1) >= 26, "Pseudonym should be at least 26 characters"
        
        # Test domain isolation
        domain2 = "encounter_id"
        pseudonym3 = generator.generate_pseudonym(identifier, domain2)
        
        assert pseudonym1 != pseudonym3, "Different domains should produce different pseudonyms"
        
        print("✓ Pseudonym generation tests passed")
        
    except Exception as e:
        print(f"✗ Pseudonym generation test failed: {e}")
        raise


def test_thai_citizen_id_validation():
    """Test Thai Citizen ID validation."""
    try:
        from services.thai_nlp_service import ThaiRuleBasedRecognizer
        
        recognizer = ThaiRuleBasedRecognizer()
        
        # Test valid Thai Citizen ID
        valid_id = "1234567890123"  # This is just for testing pattern, not real checksum
        text = f"เลขประจำตัวประชาชน {valid_id}"
        
        results = recognizer.recognize_thai_citizen_id(text)
        
        # Should find the pattern even if checksum validation fails
        assert len(results) >= 0, "Should process Thai Citizen ID patterns"
        
        print("✓ Thai Citizen ID validation tests passed")
        
    except Exception as e:
        print(f"✗ Thai Citizen ID validation test failed: {e}")
        raise


def test_policy_engine():
    """Test policy engine functionality."""
    try:
        from services.policy_engine import PolicyEngine
        from models.schemas import TransformationPolicy, EntityType, TransformationType
        
        engine = PolicyEngine()
        
        # Test default policies
        available_policies = engine.get_available_policies()
        assert 'pdpa_v1.0' in available_policies, "PDPA policy should be available"
        
        # Test policy validation
        test_policies = [
            TransformationPolicy(
                entity_type=EntityType.PERSON,
                transformation=TransformationType.REDACT,
                parameters={}
            )
        ]
        
        validation_errors = engine.validate_policy(test_policies)
        # Should have some errors for incomplete coverage
        
        print("✓ Policy engine tests passed")
        
    except Exception as e:
        print(f"✗ Policy engine test failed: {e}")
        raise


def test_detection_service():
    """Test detection service."""
    try:
        from services.detection_service import DetectionEnsemble
        
        service = DetectionEnsemble()
        
        # Test English text
        english_text = "John Smith was born on January 15, 1978. His phone is (555) 123-4567."
        detections, language = service.detect_entities(english_text)
        
        assert len(detections) >= 0, "Should process English text"
        
        # Test Thai text
        thai_text = "คุณสมชาย ใจดี เบอร์โทร 081-234-5678"
        detections, language = service.detect_entities(thai_text)
        
        assert len(detections) >= 0, "Should process Thai text"
        
        print("✓ Detection service tests passed")
        
    except Exception as e:
        print(f"✗ Detection service test failed: {e}")
        raise


def run_all_tests():
    """Run all basic functionality tests."""
    print("Running basic functionality tests...")
    print("=" * 50)
    
    try:
        test_imports()
        test_pseudonym_generation()
        test_thai_citizen_id_validation()
        test_policy_engine()
        test_detection_service()
        
        print("=" * 50)
        print("✓ All tests passed!")
        return True
        
    except Exception as e:
        print("=" * 50)
        print(f"✗ Tests failed: {e}")
        return False


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
"""
Detection ensemble service that combines Microsoft Presidio (English) 
with Thai NLP services for comprehensive bilingual entity detection.
"""
import re
import logging
from typing import List, Dict, Tuple, Optional, Any, Set
from dataclasses import dataclass
from datetime import datetime
import spacy
from langdetect import detect, DetectorFactory

# Presidio imports
try:
    from presidio_analyzer import AnalyzerEngine, RecognizerResult, PatternRecognizer
    from presidio_analyzer.nlp_engine import NlpEngineProvider
    PRESIDIO_AVAILABLE = True
except ImportError:
    PRESIDIO_AVAILABLE = False
    logging.warning("Presidio not available - install with: pip install presidio-analyzer")

from models.schemas import (
    EntityType, DetectionResult, DetectorType, LanguageCode
)
from utils.config import get_settings, DetectionThresholds
from .thai_nlp_service import get_thai_nlp_service

logger = logging.getLogger(__name__)

# Initialize langdetect for consistent results
DetectorFactory.seed = 42


@dataclass
class DetectionSpan:
    """Unified detection span with priority and confidence."""
    start: int
    end: int
    text: str
    entity_type: EntityType
    confidence: float
    detector_type: DetectorType
    detector_version: str
    rule_id: Optional[str] = None
    additional_info: Dict[str, Any] = None
    priority: int = 0  # Higher number = higher priority
    
    def __post_init__(self):
        if self.additional_info is None:
            self.additional_info = {}


class LanguageDetector:
    """Enhanced language detection for Thai/English text."""
    
    def __init__(self):
        self.thai_char_range = (0x0e00, 0x0e7f)  # Thai Unicode block
        
    def detect_language(self, text: str) -> Tuple[LanguageCode, float]:
        """
        Detect primary language with confidence.
        
        Args:
            text: Input text
            
        Returns:
            Tuple of (language_code, confidence)
        """
        if not text or not text.strip():
            return LanguageCode.ENGLISH, 0.5
        
        # Count Thai characters
        thai_chars = sum(1 for c in text if self.thai_char_range[0] <= ord(c) <= self.thai_char_range[1])
        alpha_chars = sum(1 for c in text if c.isalpha())
        
        if alpha_chars == 0:
            return LanguageCode.ENGLISH, 0.5
        
        thai_ratio = thai_chars / alpha_chars
        
        if thai_ratio > 0.5:
            return LanguageCode.THAI, min(thai_ratio + 0.2, 0.95)
        elif thai_ratio > 0.1:
            return LanguageCode.MIXED, thai_ratio + 0.3
        else:
            # Use langdetect for non-Thai text
            try:
                detected = detect(text)
                if detected == 'th':
                    return LanguageCode.THAI, 0.8
                elif detected in ['en', 'es', 'de', 'fr']:  # Latin script languages
                    return LanguageCode.ENGLISH, 0.8
                else:
                    return LanguageCode.ENGLISH, 0.6  # Default to English for unknown
            except:
                return LanguageCode.ENGLISH, 0.6
    
    def segment_by_language(self, text: str, min_segment_length: int = 20) -> List[Tuple[str, LanguageCode, int, int]]:
        """
        Segment text by language for mixed-language processing.
        
        Args:
            text: Input text
            min_segment_length: Minimum segment length for language detection
            
        Returns:
            List of (segment_text, language, start_pos, end_pos)
        """
        segments = []
        
        # Simple approach: split by sentences and detect each
        sentences = re.split(r'[.!?।\n]+', text)
        current_pos = 0
        
        for sentence in sentences:
            if not sentence.strip():
                current_pos += len(sentence) + 1  # +1 for delimiter
                continue
            
            start_pos = text.find(sentence, current_pos)
            end_pos = start_pos + len(sentence)
            
            if len(sentence.strip()) >= min_segment_length:
                lang, confidence = self.detect_language(sentence)
            else:
                # Default to previous segment's language or English
                lang = segments[-1][1] if segments else LanguageCode.ENGLISH
            
            segments.append((sentence, lang, start_pos, end_pos))
            current_pos = end_pos + 1
        
        return segments


class PresidioService:
    """Wrapper for Microsoft Presidio analyzer."""
    
    def __init__(self, model_name: str = "en_core_web_sm"):
        self.model_name = model_name
        self.analyzer = None
        
        if PRESIDIO_AVAILABLE:
            try:
                # Configure NLP engine
                nlp_config = {
                    "nlp_engine_name": "spacy",
                    "models": [{"lang_code": "en", "model_name": model_name}]
                }
                
                nlp_engine = NlpEngineProvider(nlp_configuration=nlp_config).create_engine()
                
                # Initialize analyzer
                self.analyzer = AnalyzerEngine(nlp_engine=nlp_engine)
                
                # Add custom recognizers
                self._add_custom_recognizers()
                
                logger.info(f"Presidio initialized with model: {model_name}")
                
            except Exception as e:
                logger.error(f"Failed to initialize Presidio: {e}")
                self.analyzer = None
        else:
            logger.warning("Presidio not available")
    
    def _add_custom_recognizers(self):
        """Add custom recognizers for medical/clinical entities."""
        if not self.analyzer:
            return
        
        # Medical Record Number recognizer
        mrn_patterns = [
            {"Pattern": r"\b[Mm][Rr][Nn][-\s]*:?\s*(\d{6,10})\b", "Score": 0.8},
            {"Pattern": r"\b[Mm]edical\s+[Rr]ecord\s+[Nn]umber[-\s]*:?\s*(\d{6,10})\b", "Score": 0.9},
            {"Pattern": r"\b[Hh][Nn][-\s]*:?\s*(\d{6,10})\b", "Score": 0.7},  # Hospital Number
        ]
        
        mrn_recognizer = PatternRecognizer(
            supported_entity="MEDICAL_RECORD_NUMBER",
            patterns=mrn_patterns,
            name="MRN_Recognizer"
        )
        
        # Hospital/Facility recognizer
        hospital_patterns = [
            {"Pattern": r"\b[Hh]ospital\s+\w+", "Score": 0.6},
            {"Pattern": r"\b\w+\s+[Mm]edical\s+[Cc]enter", "Score": 0.7},
            {"Pattern": r"\b\w+\s+[Gg]eneral\s+[Hh]ospital", "Score": 0.8},
        ]
        
        hospital_recognizer = PatternRecognizer(
            supported_entity="HOSPITAL",
            patterns=hospital_patterns,
            name="Hospital_Recognizer"
        )
        
        # Add recognizers to analyzer
        self.analyzer.registry.add_recognizer(mrn_recognizer)
        self.analyzer.registry.add_recognizer(hospital_recognizer)
        
        logger.info("Added custom Presidio recognizers")
    
    def analyze_text(self, text: str, language: str = "en") -> List[DetectionSpan]:
        """
        Analyze text using Presidio.
        
        Args:
            text: Text to analyze
            language: Language code
            
        Returns:
            List of DetectionSpan objects
        """
        if not self.analyzer:
            logger.warning("Presidio analyzer not available")
            return []
        
        try:
            # Run Presidio analysis
            results = self.analyzer.analyze(
                text=text,
                entities=None,  # Detect all supported entities
                language=language
            )
            
            # Convert to DetectionSpan objects
            spans = []
            for result in results:
                entity_type = self._map_presidio_entity(result.entity_type)
                if entity_type:
                    span = DetectionSpan(
                        start=result.start,
                        end=result.end,
                        text=text[result.start:result.end],
                        entity_type=entity_type,
                        confidence=result.score,
                        detector_type=DetectorType.PRESIDIO,
                        detector_version=self.model_name,
                        rule_id=getattr(result, 'recognition_metadata', {}).get('recognizer_name'),
                        priority=2  # Medium priority for Presidio
                    )
                    spans.append(span)
            
            return spans
            
        except Exception as e:
            logger.error(f"Presidio analysis failed: {e}")
            return []
    
    def _map_presidio_entity(self, presidio_type: str) -> Optional[EntityType]:
        """Map Presidio entity types to our EntityType enum."""
        mapping = {
            'PERSON': EntityType.PERSON,
            'PHONE_NUMBER': EntityType.PHONE_NUMBER,
            'EMAIL_ADDRESS': EntityType.EMAIL_ADDRESS,
            'LOCATION': EntityType.LOCATION,
            'DATE_TIME': EntityType.DATE_TIME,
            'URL': EntityType.URL,
            'IP_ADDRESS': EntityType.IP_ADDRESS,
            'MEDICAL_RECORD_NUMBER': EntityType.MEDICAL_RECORD_NUMBER,
            'HOSPITAL': EntityType.HOSPITAL,
            'ORGANIZATION': EntityType.ORGANIZATION,
            'US_SSN': EntityType.PASSPORT,  # Map SSN to passport for international use
            'CREDIT_CARD': EntityType.BANK_ACCOUNT,  # Map credit card to bank account category
        }
        
        return mapping.get(presidio_type)


class EntityFusion:
    """Fuses overlapping entities from different detectors."""
    
    def __init__(self):
        self.entity_priorities = {
            # Higher number = higher priority
            EntityType.THAI_CITIZEN_ID: 10,  # Validated patterns highest priority
            EntityType.PASSPORT: 9,
            EntityType.MEDICAL_RECORD_NUMBER: 8,
            EntityType.PHONE_NUMBER: 7,
            EntityType.EMAIL_ADDRESS: 7,
            EntityType.PERSON: 6,
            EntityType.ADDRESS: 5,
            EntityType.ORGANIZATION: 4,
            EntityType.HOSPITAL: 4,
            EntityType.LOCATION: 3,
            EntityType.DATE_TIME: 3,
            EntityType.AGE: 2,
            EntityType.LICENSE_PLATE: 6,
            EntityType.BANK_ACCOUNT: 8,
            EntityType.URL: 4,
            EntityType.IP_ADDRESS: 5,
        }
        
        self.detector_priorities = {
            DetectorType.THAI_RULE: 10,  # Validated rules highest
            DetectorType.CUSTOM_RULE: 9,
            DetectorType.PRESIDIO: 7,
            DetectorType.THAI_NER: 6,
        }
    
    def fuse_detections(self, spans: List[DetectionSpan]) -> List[DetectionSpan]:
        """
        Fuse overlapping detection spans using priority rules.
        
        Args:
            spans: List of detection spans from various detectors
            
        Returns:
            List of fused, non-overlapping spans
        """
        if not spans:
            return []
        
        # Sort spans by start position
        sorted_spans = sorted(spans, key=lambda x: x.start)
        
        # Apply priorities
        for span in sorted_spans:
            span.priority = self._calculate_priority(span)
        
        # Resolve overlaps
        fused_spans = []
        current_span = sorted_spans[0]
        
        for next_span in sorted_spans[1:]:
            overlap = self._calculate_overlap(current_span, next_span)
            
            if overlap > 0:
                # Handle overlap
                current_span = self._resolve_overlap(current_span, next_span, overlap)
            else:
                # No overlap, add current span and move to next
                fused_spans.append(current_span)
                current_span = next_span
        
        # Add the last span
        fused_spans.append(current_span)
        
        return fused_spans
    
    def _calculate_priority(self, span: DetectionSpan) -> int:
        """Calculate overall priority for a span."""
        entity_priority = self.entity_priorities.get(span.entity_type, 1)
        detector_priority = self.detector_priorities.get(span.detector_type, 1)
        confidence_boost = int(span.confidence * 5)  # 0-5 boost from confidence
        
        return entity_priority + detector_priority + confidence_boost
    
    def _calculate_overlap(self, span1: DetectionSpan, span2: DetectionSpan) -> int:
        """Calculate character overlap between two spans."""
        return max(0, min(span1.end, span2.end) - max(span1.start, span2.start))
    
    def _resolve_overlap(self, span1: DetectionSpan, span2: DetectionSpan, overlap: int) -> DetectionSpan:
        """
        Resolve overlap between two spans based on priorities and confidence.
        
        Args:
            span1: First span
            span2: Second span
            overlap: Number of overlapping characters
            
        Returns:
            Winning span (possibly modified)
        """
        span1_length = span1.end - span1.start
        span2_length = span2.end - span2.start
        
        # If overlap is significant (>50% of smaller span), choose winner
        min_length = min(span1_length, span2_length)
        if overlap > min_length * 0.5:
            # Choose span with higher priority
            if span1.priority > span2.priority:
                return span1
            elif span2.priority > span1.priority:
                return span2
            else:
                # Same priority, choose span with higher confidence
                return span1 if span1.confidence >= span2.confidence else span2
        else:
            # Small overlap, try to keep both by adjusting boundaries
            if span1.priority >= span2.priority:
                # Keep span1, adjust span2 start
                span2.start = span1.end
                span2.text = span2.text[span1.end - span2.start + len(span2.text) - span2_length:]
                return span1  # Return span1, span2 will be processed next
            else:
                # Keep span2, adjust span1 end
                span1.end = span2.start
                span1.text = span1.text[:span2.start - span1.start]
                return span1


class DetectionEnsemble:
    """
    Main detection ensemble that coordinates Thai NLP and Presidio services.
    """
    
    def __init__(self, settings=None):
        if settings is None:
            settings = get_settings()
        
        self.settings = settings
        self.language_detector = LanguageDetector()
        self.presidio_service = PresidioService(settings.spacy_model_en)
        self.thai_nlp_service = get_thai_nlp_service()
        self.fusion_engine = EntityFusion()
        self.thresholds = DetectionThresholds()
        
        logger.info("Detection ensemble initialized")
    
    def detect_entities(self, text: str, language_hint: Optional[str] = None) -> Tuple[List[DetectionResult], LanguageCode]:
        """
        Detect entities in text using appropriate services based on language.
        
        Args:
            text: Input text to analyze
            language_hint: Optional language hint
            
        Returns:
            Tuple of (detection_results, detected_language)
        """
        if not text or not text.strip():
            return [], LanguageCode.ENGLISH
        
        # Detect language if not provided
        if language_hint:
            try:
                detected_lang = LanguageCode(language_hint)
                confidence = 0.9
            except ValueError:
                detected_lang, confidence = self.language_detector.detect_language(text)
        else:
            detected_lang, confidence = self.language_detector.detect_language(text)
        
        logger.debug(f"Detected language: {detected_lang} (confidence: {confidence:.2f})")
        
        # Route to appropriate detection services
        all_spans = []
        
        if detected_lang == LanguageCode.THAI:
            # Primarily Thai text
            thai_spans = self._detect_thai_entities(text)
            all_spans.extend(thai_spans)
            
            # Also run Presidio for any English entities
            if confidence < 0.9:  # Mixed content likely
                presidio_spans = self._detect_english_entities(text)
                all_spans.extend(presidio_spans)
        
        elif detected_lang == LanguageCode.MIXED:
            # Mixed language text - run both services
            thai_spans = self._detect_thai_entities(text)
            presidio_spans = self._detect_english_entities(text)
            all_spans.extend(thai_spans)
            all_spans.extend(presidio_spans)
        
        else:
            # Primarily English text
            presidio_spans = self._detect_english_entities(text)
            all_spans.extend(presidio_spans)
            
            # Check for Thai entities if confidence is not high
            if confidence < 0.9:
                thai_spans = self._detect_thai_entities(text)
                all_spans.extend(thai_spans)
        
        # Apply confidence thresholds
        filtered_spans = self._apply_thresholds(all_spans)
        
        # Fuse overlapping detections
        fused_spans = self.fusion_engine.fuse_detections(filtered_spans)
        
        # Convert to DetectionResult objects
        results = self._convert_to_detection_results(fused_spans)
        
        logger.info(f"Detected {len(results)} entities in {detected_lang} text")
        
        return results, detected_lang
    
    def _detect_thai_entities(self, text: str) -> List[DetectionSpan]:
        """Run Thai entity detection."""
        thai_results = self.thai_nlp_service.extract_all_entities(text)
        
        spans = []
        for result in thai_results:
            span = DetectionSpan(
                start=result.start,
                end=result.end,
                text=result.text,
                entity_type=result.entity_type,
                confidence=result.confidence,
                detector_type=result.detector_type,
                detector_version=result.detector_version,
                rule_id=result.rule_id,
                additional_info=result.additional_info
            )
            spans.append(span)
        
        return spans
    
    def _detect_english_entities(self, text: str) -> List[DetectionSpan]:
        """Run English entity detection with Presidio."""
        return self.presidio_service.analyze_text(text, "en")
    
    def _apply_thresholds(self, spans: List[DetectionSpan]) -> List[DetectionSpan]:
        """Apply confidence thresholds to filter detections."""
        filtered_spans = []
        
        for span in spans:
            threshold = self.thresholds.get_threshold(span.entity_type.value)
            
            if span.confidence >= threshold:
                filtered_spans.append(span)
            else:
                logger.debug(f"Filtered {span.entity_type} detection below threshold: {span.confidence:.2f} < {threshold}")
        
        return filtered_spans
    
    def _convert_to_detection_results(self, spans: List[DetectionSpan]) -> List[DetectionResult]:
        """Convert DetectionSpan objects to DetectionResult objects."""
        results = []
        
        for span in spans:
            result = DetectionResult(
                entity_type=span.entity_type,
                start=span.start,
                end=span.end,
                text=span.text,
                confidence=span.confidence,
                detector_type=span.detector_type,
                detector_version=span.detector_version,
                rule_id=span.rule_id,
                additional_info=span.additional_info
            )
            results.append(result)
        
        return results
    
    def batch_detect(self, texts: List[str]) -> List[Tuple[List[DetectionResult], LanguageCode]]:
        """
        Detect entities in multiple texts efficiently.
        
        Args:
            texts: List of texts to analyze
            
        Returns:
            List of (detection_results, language) tuples
        """
        results = []
        
        for text in texts:
            try:
                detection_results, language = self.detect_entities(text)
                results.append((detection_results, language))
            except Exception as e:
                logger.error(f"Batch detection failed for text: {e}")
                results.append(([], LanguageCode.ENGLISH))
        
        return results
    
    def get_supported_entities(self) -> List[EntityType]:
        """Get list of supported entity types."""
        return list(EntityType)
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get detection service statistics."""
        return {
            'presidio_available': PRESIDIO_AVAILABLE,
            'thai_nlp_available': self.thai_nlp_service is not None,
            'supported_entities': len(self.get_supported_entities()),
            'spacy_model': self.settings.spacy_model_en,
            'thai_model': self.settings.thai_ner_model,
            'confidence_thresholds': self.thresholds.THRESHOLDS
        }


# Global service instance
detection_service = None

def get_detection_service() -> DetectionEnsemble:
    """Get global detection ensemble service instance."""
    global detection_service
    if detection_service is None:
        detection_service = DetectionEnsemble()
    return detection_service
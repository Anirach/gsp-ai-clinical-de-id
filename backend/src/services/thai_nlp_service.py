"""
Thai NLP service using PyThaiNLP for tokenization, NER, and text processing.
Handles Thai-specific language processing including Buddhist Era dates,
Thai numerals, and cultural context.
"""
import re
import logging
from typing import List, Dict, Tuple, Optional, Any
from dataclasses import dataclass
from datetime import datetime

# PyThaiNLP imports
try:
    import pythainlp
    from pythainlp import word_tokenize, sent_tokenize
    from pythainlp.tag import pos_tag
    from pythainlp.corpus import thai_words
    from pythainlp.transliterate import transliterate
    from pythainlp.util import normalize
    # NER imports (may need additional setup)
    try:
        from pythainlp.tag.named_entity import ThaiNameTagger
        THAI_NER_AVAILABLE = True
    except ImportError:
        THAI_NER_AVAILABLE = False
        logging.warning("Thai NER not available - install additional models")
except ImportError:
    logging.error("PyThaiNLP not installed. Install with: pip install pythainlp")
    raise

from models.schemas import EntityType, DetectionResult, DetectorType
from utils.config import ThaiLanguageConfig

logger = logging.getLogger(__name__)


@dataclass
class ThaiTextSpan:
    """Represents a span of Thai text with metadata."""
    start: int
    end: int
    text: str
    entity_type: Optional[str] = None
    confidence: float = 0.0
    additional_info: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.additional_info is None:
            self.additional_info = {}


class ThaiTextNormalizer:
    """Normalizes Thai text for consistent processing."""
    
    def __init__(self):
        self.thai_to_arabic = ThaiLanguageConfig.THAI_TO_ARABIC
        self.thai_months = ThaiLanguageConfig.THAI_MONTHS
        
    def normalize_thai_numerals(self, text: str) -> str:
        """Convert Thai numerals (๐-๙) to Arabic numerals (0-9)."""
        for thai_digit, arabic_digit in self.thai_to_arabic.items():
            text = text.replace(thai_digit, arabic_digit)
        return text
    
    def normalize_text(self, text: str) -> str:
        """Apply various Thai text normalizations."""
        # Unicode normalization
        text = normalize(text)
        
        # Convert Thai numerals to Arabic for processing
        text = self.normalize_thai_numerals(text)
        
        # Normalize whitespace
        text = re.sub(r'\s+', ' ', text).strip()
        
        return text
    
    def extract_date_components(self, text: str) -> List[Dict[str, Any]]:
        """Extract Thai date components with BE/CE conversion."""
        date_patterns = []
        
        # Pattern for Thai dates with month names
        thai_date_pattern = r'(\d{1,2})\s*(มกราคม|กุมภาพันธ์|มีนาคม|เมษายน|พฤษภาคม|มิถุนายน|กรกฎาคม|สิงหาคม|กันยายน|ตุลาคม|พฤศจิกายน|ธันวาคม|ม\.ค\.|ก\.พ\.|มี\.ค\.|เม\.ย\.|พ\.ค\.|มิ\.ย\.|ก\.ค\.|ส\.ค\.|ก\.ย\.|ต\.ค\.|พ\.ย\.|ธ\.ค\.)\s*(\d{4})'
        
        for match in re.finditer(thai_date_pattern, text):
            day = int(match.group(1))
            month_thai = match.group(2)
            year = int(match.group(3))
            
            month_num = self.thai_months.get(month_thai, 0)
            
            # Determine if Buddhist Era (BE) or Common Era (CE)
            is_be = year > 2100  # Reasonable heuristic
            ce_year = year - 543 if is_be else year
            
            date_patterns.append({
                'start': match.start(),
                'end': match.end(),
                'text': match.group(0),
                'day': day,
                'month': month_num,
                'year': year,
                'ce_year': ce_year,
                'is_be': is_be,
                'type': 'thai_date'
            })
        
        return date_patterns


class ThaiNERService:
    """Thai Named Entity Recognition service."""
    
    def __init__(self, model_name: str = "thai2fit_wangchanberta"):
        self.model_name = model_name
        self.tagger = None
        
        if THAI_NER_AVAILABLE:
            try:
                self.tagger = ThaiNameTagger()
                logger.info(f"Thai NER initialized with model: {model_name}")
            except Exception as e:
                logger.warning(f"Could not initialize Thai NER: {e}")
        else:
            logger.warning("Thai NER not available")
    
    def extract_entities(self, text: str) -> List[ThaiTextSpan]:
        """
        Extract named entities from Thai text.
        
        Args:
            text: Thai text to analyze
            
        Returns:
            List of detected entity spans
        """
        entities = []
        
        if not self.tagger:
            logger.warning("Thai NER not available, using rule-based fallback")
            return self._rule_based_extraction(text)
        
        try:
            # Use PyThaiNLP NER
            ner_results = self.tagger.get_ner(text)
            
            for result in ner_results:
                if isinstance(result, dict):
                    entity_type = self._map_ner_type(result.get('type', 'UNKNOWN'))
                    confidence = result.get('confidence', 0.8)
                    
                    span = ThaiTextSpan(
                        start=result.get('start', 0),
                        end=result.get('end', 0),
                        text=result.get('text', ''),
                        entity_type=entity_type,
                        confidence=confidence
                    )
                    entities.append(span)
                    
        except Exception as e:
            logger.error(f"Thai NER extraction failed: {e}")
            return self._rule_based_extraction(text)
        
        return entities
    
    def _map_ner_type(self, ner_type: str) -> str:
        """Map Thai NER types to our entity types."""
        mapping = {
            'PERSON': EntityType.PERSON,
            'ORG': EntityType.ORGANIZATION,
            'LOC': EntityType.LOCATION,
            'DATE': EntityType.DATE_TIME,
            'MISC': 'MISC'
        }
        return mapping.get(ner_type.upper(), 'UNKNOWN')
    
    def _rule_based_extraction(self, text: str) -> List[ThaiTextSpan]:
        """Fallback rule-based entity extraction for Thai text."""
        entities = []
        
        # Thai person name patterns (simplified)
        thai_name_patterns = [
            r'(นาย|นาง|นางสาว|ดร\.|ศ\.|รศ\.|ผศ\.)\s*([ก-๙\s]{2,30})',
            r'คุณ\s*([ก-๙\s]{2,20})',
        ]
        
        for pattern in thai_name_patterns:
            for match in re.finditer(pattern, text):
                entities.append(ThaiTextSpan(
                    start=match.start(),
                    end=match.end(),
                    text=match.group(0),
                    entity_type=EntityType.PERSON,
                    confidence=0.7
                ))
        
        # Thai organization patterns
        org_patterns = [
            r'โรงพยาบาล[ก-๙\s]{3,20}',
            r'มหาวิทยาลัย[ก-๙\s]{3,20}',
            r'บริษัท\s*[ก-๙\s]{3,30}\s*จำกัด',
        ]
        
        for pattern in org_patterns:
            for match in re.finditer(pattern, text):
                entities.append(ThaiTextSpan(
                    start=match.start(),
                    end=match.end(),
                    text=match.group(0),
                    entity_type=EntityType.ORGANIZATION,
                    confidence=0.6
                ))
        
        return entities


class ThaiRuleBasedRecognizer:
    """Rule-based recognizer for Thai-specific patterns."""
    
    def __init__(self):
        self.provinces = ThaiLanguageConfig.PROVINCES
        self.address_keywords = ThaiLanguageConfig.ADDRESS_KEYWORDS
        
    def recognize_thai_citizen_id(self, text: str) -> List[ThaiTextSpan]:
        """
        Recognize Thai Citizen ID (13 digits with checksum validation).
        
        Pattern: X-XXXX-XXXXX-XX-X where checksum is validated
        """
        entities = []
        
        # Pattern for Thai Citizen ID (with or without dashes)
        pattern = r'\b(\d{1}[-\s]?\d{4}[-\s]?\d{5}[-\s]?\d{2}[-\s]?\d{1})\b'
        
        for match in re.finditer(pattern, text):
            id_text = match.group(1)
            # Remove separators for validation
            clean_id = re.sub(r'[-\s]', '', id_text)
            
            if len(clean_id) == 13 and self._validate_thai_citizen_id(clean_id):
                entities.append(ThaiTextSpan(
                    start=match.start(),
                    end=match.end(),
                    text=id_text,
                    entity_type=EntityType.THAI_CITIZEN_ID,
                    confidence=0.95,
                    additional_info={'validated': True, 'clean_id': clean_id}
                ))
        
        return entities
    
    def _validate_thai_citizen_id(self, id_str: str) -> bool:
        """Validate Thai Citizen ID checksum."""
        if len(id_str) != 13 or not id_str.isdigit():
            return False
        
        # Checksum calculation
        sum_digits = 0
        for i in range(12):
            sum_digits += int(id_str[i]) * (13 - i)
        
        remainder = sum_digits % 11
        check_digit = (11 - remainder) % 10
        
        return check_digit == int(id_str[12])
    
    def recognize_thai_phone_numbers(self, text: str) -> List[ThaiTextSpan]:
        """Recognize Thai phone number patterns."""
        entities = []
        
        # Thai mobile patterns (08x, 09x, 06x)
        mobile_patterns = [
            r'\b(0[689]\d{8})\b',  # 10-digit mobile
            r'\b(\+66\s*[689]\d{8})\b',  # International format
            r'\b(0[689]\d[-\s]?\d{3}[-\s]?\d{4})\b',  # With separators
        ]
        
        # Thai landline patterns
        landline_patterns = [
            r'\b(0[2-7]\d{7})\b',  # 9-digit landline
            r'\b(0[2-7]\d[-\s]?\d{3}[-\s]?\d{4})\b',  # With separators
        ]
        
        all_patterns = mobile_patterns + landline_patterns
        
        for pattern in all_patterns:
            for match in re.finditer(pattern, text):
                phone_text = match.group(1)
                confidence = 0.9 if any(phone_text.startswith(p) for p in ['08', '09', '06']) else 0.85
                
                entities.append(ThaiTextSpan(
                    start=match.start(),
                    end=match.end(),
                    text=phone_text,
                    entity_type=EntityType.PHONE_NUMBER,
                    confidence=confidence,
                    additional_info={'type': 'thai_phone'}
                ))
        
        return entities
    
    def recognize_thai_addresses(self, text: str) -> List[ThaiTextSpan]:
        """Recognize Thai address patterns."""
        entities = []
        
        # Look for address components
        address_pattern = r'(บ้านเลขที่\s*\d+.*?(?:จังหวัด\s*[ก-๙]+|รหัสไปรษณีย์\s*\d{5}))'
        
        for match in re.finditer(address_pattern, text):
            address_text = match.group(1)
            
            # Check if contains province
            has_province = any(province in address_text for province in self.provinces)
            confidence = 0.8 if has_province else 0.6
            
            entities.append(ThaiTextSpan(
                start=match.start(),
                end=match.end(),
                text=address_text,
                entity_type=EntityType.ADDRESS,
                confidence=confidence,
                additional_info={'has_province': has_province}
            ))
        
        return entities
    
    def recognize_thai_license_plates(self, text: str) -> List[ThaiTextSpan]:
        """Recognize Thai license plate patterns."""
        entities = []
        
        # Thai license plate patterns
        patterns = [
            r'\b([ก-ฮ]{1,2}\s*\d{1,4}\s*[ก-ฮ]{0,2})\b',  # Standard format
            r'\b(\d{1,2}[ก-ฮ]{1,2}\s*\d{1,4})\b',  # Alternate format
        ]
        
        for pattern in patterns:
            for match in re.finditer(pattern, text):
                plate_text = match.group(1)
                
                entities.append(ThaiTextSpan(
                    start=match.start(),
                    end=match.end(),
                    text=plate_text,
                    entity_type=EntityType.LICENSE_PLATE,
                    confidence=0.85,
                    additional_info={'type': 'thai_license_plate'}
                ))
        
        return entities


class ThaiNLPService:
    """
    Main Thai NLP service that coordinates all Thai language processing.
    """
    
    def __init__(self, model_name: str = "thai2fit_wangchanberta"):
        self.normalizer = ThaiTextNormalizer()
        self.ner_service = ThaiNERService(model_name)
        self.rule_recognizer = ThaiRuleBasedRecognizer()
        
        logger.info("Thai NLP Service initialized")
    
    def tokenize(self, text: str, engine: str = "newmm") -> List[str]:
        """
        Tokenize Thai text.
        
        Args:
            text: Thai text to tokenize
            engine: Tokenization engine ('newmm', 'longest', 'attacut', etc.)
            
        Returns:
            List of tokens
        """
        normalized_text = self.normalizer.normalize_text(text)
        return word_tokenize(normalized_text, engine=engine)
    
    def detect_language(self, text: str) -> Tuple[str, float]:
        """
        Detect if text is primarily Thai.
        
        Args:
            text: Text to analyze
            
        Returns:
            Tuple of (language_code, confidence)
        """
        # Simple heuristic based on Thai character frequency
        thai_chars = sum(1 for c in text if '\u0e00' <= c <= '\u0e7f')
        total_chars = len([c for c in text if c.isalpha()])
        
        if total_chars == 0:
            return 'unknown', 0.0
        
        thai_ratio = thai_chars / total_chars
        
        if thai_ratio > 0.5:
            return 'th', min(thai_ratio, 0.95)
        elif thai_ratio > 0.1:
            return 'mixed', thai_ratio
        else:
            return 'en', 1.0 - thai_ratio
    
    def extract_all_entities(self, text: str) -> List[DetectionResult]:
        """
        Extract all entities from Thai text using NER + rules.
        
        Args:
            text: Thai text to analyze
            
        Returns:
            List of DetectionResult objects
        """
        results = []
        
        # Normalize text first
        normalized_text = self.normalizer.normalize_text(text)
        
        # NER-based extraction
        ner_entities = self.ner_service.extract_entities(normalized_text)
        for entity in ner_entities:
            if entity.entity_type and entity.entity_type != 'UNKNOWN':
                results.append(DetectionResult(
                    entity_type=EntityType(entity.entity_type),
                    start=entity.start,
                    end=entity.end,
                    text=entity.text,
                    confidence=entity.confidence,
                    detector_type=DetectorType.THAI_NER,
                    detector_version=self.ner_service.model_name,
                    additional_info=entity.additional_info or {}
                ))
        
        # Rule-based extraction
        rule_methods = [
            self.rule_recognizer.recognize_thai_citizen_id,
            self.rule_recognizer.recognize_thai_phone_numbers,
            self.rule_recognizer.recognize_thai_addresses,
            self.rule_recognizer.recognize_thai_license_plates,
        ]
        
        for method in rule_methods:
            try:
                rule_entities = method(normalized_text)
                for entity in rule_entities:
                    results.append(DetectionResult(
                        entity_type=EntityType(entity.entity_type),
                        start=entity.start,
                        end=entity.end,
                        text=entity.text,
                        confidence=entity.confidence,
                        detector_type=DetectorType.THAI_RULE,
                        detector_version="v1.0",
                        rule_id=method.__name__,
                        additional_info=entity.additional_info or {}
                    ))
            except Exception as e:
                logger.error(f"Error in rule method {method.__name__}: {e}")
        
        # Sort by start position
        results.sort(key=lambda x: x.start)
        
        return results
    
    def process_dates(self, text: str) -> List[Dict[str, Any]]:
        """Extract and process Thai dates with BE/CE conversion."""
        return self.normalizer.extract_date_components(text)


# Global service instance
thai_nlp_service = None

def get_thai_nlp_service() -> ThaiNLPService:
    """Get global Thai NLP service instance."""
    global thai_nlp_service
    if thai_nlp_service is None:
        thai_nlp_service = ThaiNLPService()
    return thai_nlp_service
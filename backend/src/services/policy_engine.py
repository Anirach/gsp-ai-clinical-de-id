"""
Policy engine for de-identification transformations.
Implements policy-driven transformation strategies with support for
PDPA, HIPAA Safe Harbor, and custom compliance frameworks.
"""
import re
import logging
import random
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass
from abc import ABC, abstractmethod

from models.schemas import (
    EntityType, TransformationType, TransformationPolicy, 
    TransformationResult, DetectionResult
)
from utils.config import get_settings, PolicyTemplates, ThaiLanguageConfig
from security.crypto import SecureHasher
from .pseudonym_service import get_pseudonym_service, PseudonymRequest

logger = logging.getLogger(__name__)


@dataclass
class TransformationContext:
    """Context information for transformations."""
    document_id: str
    job_id: str
    linkage_domain: str
    patient_salt: Optional[str] = None  # For consistent date shifting
    session_id: str = "default"
    additional_context: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.additional_context is None:
            self.additional_context = {}


class BaseTransformer(ABC):
    """Base class for entity transformers."""
    
    @abstractmethod
    def transform(
        self, 
        text: str, 
        entity_type: EntityType, 
        parameters: Dict[str, Any],
        context: TransformationContext
    ) -> str:
        """Transform detected entity text."""
        pass
    
    @abstractmethod
    def get_default_parameters(self) -> Dict[str, Any]:
        """Get default transformation parameters."""
        pass


class RedactionTransformer(BaseTransformer):
    """Redacts entities by replacing with category tokens."""
    
    def transform(
        self, 
        text: str, 
        entity_type: EntityType, 
        parameters: Dict[str, Any],
        context: TransformationContext
    ) -> str:
        """Replace text with redaction token."""
        token_format = parameters.get('token_format', '[{entity_type}]')
        preserve_length = parameters.get('preserve_length', False)
        
        if preserve_length:
            # Create length-preserving redaction
            char_replacement = parameters.get('replacement_char', '*')
            return char_replacement * len(text)
        else:
            # Use category token
            return token_format.format(entity_type=entity_type.value)
    
    def get_default_parameters(self) -> Dict[str, Any]:
        return {
            'token_format': '[{entity_type}]',
            'preserve_length': False,
            'replacement_char': '*'
        }


class MaskingTransformer(BaseTransformer):
    """Masks entities while preserving some structure."""
    
    def transform(
        self, 
        text: str, 
        entity_type: EntityType, 
        parameters: Dict[str, Any],
        context: TransformationContext
    ) -> str:
        """Apply masking based on entity type."""
        mask_char = parameters.get('mask_char', '*')
        preserve_start = parameters.get('preserve_start', 0)
        preserve_end = parameters.get('preserve_end', 0)
        
        if len(text) <= preserve_start + preserve_end:
            return mask_char * len(text)
        
        start_part = text[:preserve_start] if preserve_start > 0 else ''
        end_part = text[-preserve_end:] if preserve_end > 0 else ''
        middle_length = len(text) - preserve_start - preserve_end
        middle_part = mask_char * middle_length
        
        return start_part + middle_part + end_part
    
    def get_default_parameters(self) -> Dict[str, Any]:
        return {
            'mask_char': '*',
            'preserve_start': 2,
            'preserve_end': 2
        }


class GeneralizationTransformer(BaseTransformer):
    """Generalizes entities to broader categories."""
    
    def __init__(self):
        self.thai_provinces = ThaiLanguageConfig.PROVINCES
        
    def transform(
        self, 
        text: str, 
        entity_type: EntityType, 
        parameters: Dict[str, Any],
        context: TransformationContext
    ) -> str:
        """Apply generalization based on entity type and parameters."""
        
        if entity_type == EntityType.ADDRESS:
            return self._generalize_address(text, parameters)
        elif entity_type == EntityType.AGE:
            return self._generalize_age(text, parameters)
        elif entity_type == EntityType.DATE_TIME:
            return self._generalize_date(text, parameters)
        elif entity_type == EntityType.LOCATION:
            return self._generalize_location(text, parameters)
        else:
            # Default generalization
            return parameters.get('default_value', f'[{entity_type.value}]')
    
    def _generalize_address(self, text: str, parameters: Dict[str, Any]) -> str:
        """Generalize address to province or region level."""
        level = parameters.get('level', 'province')
        
        # Find Thai province in text
        for province in self.thai_provinces:
            if province in text:
                if level == 'province':
                    return f"จังหวัด{province}"
                elif level == 'region':
                    return self._get_thai_region(province)
                
        # If no province found, use generic generalization
        if level == 'province':
            return "จังหวัดที่ไม่ระบุ"
        else:
            return "ภูมิภาคที่ไม่ระบุ"
    
    def _generalize_age(self, text: str, parameters: Dict[str, Any]) -> str:
        """Generalize age to age bands."""
        use_bands = parameters.get('bands', True)
        
        # Extract age number
        age_match = re.search(r'(\d+)', text)
        if not age_match:
            return "[AGE]"
        
        age = int(age_match.group(1))
        
        if not use_bands:
            return str(age)
        
        # Age bands following HIPAA guidelines
        if age < 2:
            return "0-1"
        elif age < 5:
            return "2-4"
        elif age < 10:
            return "5-9"
        elif age < 15:
            return "10-14"
        elif age < 20:
            return "15-19"
        elif age < 30:
            return "20-29"
        elif age < 40:
            return "30-39"
        elif age < 50:
            return "40-49"
        elif age < 60:
            return "50-59"
        elif age < 70:
            return "60-69"
        elif age < 80:
            return "70-79"
        elif age < 90:
            return "80-89"
        else:
            return "90+"  # High risk category
    
    def _generalize_date(self, text: str, parameters: Dict[str, Any]) -> str:
        """Generalize dates (keep year only by default)."""
        keep_year = parameters.get('keep_year', True)
        
        if keep_year:
            # Extract year from date
            year_match = re.search(r'(\d{4})', text)
            if year_match:
                return year_match.group(1)
        
        return "[DATE]"
    
    def _generalize_location(self, text: str, parameters: Dict[str, Any]) -> str:
        """Generalize location to broader geographic area."""
        level = parameters.get('level', 'province')
        
        # Check for Thai provinces
        for province in self.thai_provinces:
            if province in text:
                if level == 'province':
                    return province
                elif level == 'region':
                    return self._get_thai_region(province)
        
        return "[LOCATION]"
    
    def _get_thai_region(self, province: str) -> str:
        """Get Thai region from province."""
        # Simplified mapping - in production, use complete mapping
        central_provinces = ['กรุงเทพมหานคร', 'นนทบุรี', 'ปทุมธานี', 'สมุทรปราการ']
        northern_provinces = ['เชียงใหม่', 'เชียงราย', 'ลำพูน', 'ลำปาง']
        northeastern_provinces = ['นครราชสีมา', 'ขอนแก่น', 'อุดรธานี', 'อุบลราชธานี']
        southern_provinces = ['สุราษฎร์ธานี', 'สงขลา', 'ภูเก็ต', 'กระบี่']
        
        if province in central_provinces:
            return "ภาคกลาง"
        elif province in northern_provinces:
            return "ภาคเหนือ"
        elif province in northeastern_provinces:
            return "ภาคตะวันออกเฉียงเหนือ"
        elif province in southern_provinces:
            return "ภาคใต้"
        else:
            return "ภูมิภาคอื่น"
    
    def get_default_parameters(self) -> Dict[str, Any]:
        return {
            'level': 'province',
            'bands': True,
            'keep_year': True,
            'default_value': '[GENERALIZED]'
        }


class DateShiftTransformer(BaseTransformer):
    """Shifts dates by consistent offset per patient."""
    
    def __init__(self):
        self.thai_months = ThaiLanguageConfig.THAI_MONTHS
        self.be_offset = 543  # Buddhist Era offset
        
    def transform(
        self, 
        text: str, 
        entity_type: EntityType, 
        parameters: Dict[str, Any],
        context: TransformationContext
    ) -> str:
        """Shift date by consistent offset."""
        max_shift_days = parameters.get('max_shift_days', 365)
        preserve_intervals = parameters.get('preserve_intervals', True)
        preserve_day_of_week = parameters.get('preserve_day_of_week', False)
        
        # Get patient-specific shift
        shift_days = self._get_patient_shift(context.patient_salt or context.document_id, max_shift_days)
        
        # Extract and parse date
        parsed_date = self._parse_thai_date(text)
        if not parsed_date:
            return text  # Return original if can't parse
        
        original_date, is_be, format_info = parsed_date
        
        # Apply shift
        shifted_date = original_date + timedelta(days=shift_days)
        
        # Format back to original style
        return self._format_thai_date(shifted_date, is_be, format_info)
    
    def _get_patient_shift(self, patient_id: str, max_shift: int) -> int:
        """Get consistent shift for patient."""
        # Use hash of patient ID to generate deterministic shift
        hash_value = hash(patient_id) % (2 * max_shift + 1) - max_shift
        return hash_value
    
    def _parse_thai_date(self, text: str) -> Optional[Tuple[datetime, bool, Dict[str, Any]]]:
        """Parse Thai date text to datetime object."""
        # Normalize Thai numerals first
        normalized_text = text
        for thai_digit, arabic_digit in ThaiLanguageConfig.THAI_TO_ARABIC.items():
            normalized_text = normalized_text.replace(thai_digit, arabic_digit)
        
        # Pattern for Thai dates
        date_patterns = [
            (r'(\d{1,2})\s*(มกราคม|กุมภาพันธ์|มีนาคม|เมษายน|พฤษภาคม|มิถุนายน|กรกฎาคม|สิงหาคม|กันยายน|ตุลาคม|พฤศจิกายน|ธันวาคม)\s*(\d{4})', 'thai_full'),
            (r'(\d{1,2})[-/](\d{1,2})[-/](\d{4})', 'numeric'),
            (r'(\d{4})[-/](\d{1,2})[-/](\d{1,2})', 'iso'),
        ]
        
        for pattern, format_type in date_patterns:
            match = re.search(pattern, normalized_text)
            if match:
                try:
                    if format_type == 'thai_full':
                        day = int(match.group(1))
                        month_thai = match.group(2)
                        year = int(match.group(3))
                        month = self.thai_months.get(month_thai, 1)
                    elif format_type == 'numeric':
                        day = int(match.group(1))
                        month = int(match.group(2))
                        year = int(match.group(3))
                    elif format_type == 'iso':
                        year = int(match.group(1))
                        month = int(match.group(2))
                        day = int(match.group(3))
                    
                    # Determine if Buddhist Era
                    is_be = year > 2100
                    ce_year = year - self.be_offset if is_be else year
                    
                    parsed_date = datetime(ce_year, month, day)
                    format_info = {
                        'format_type': format_type,
                        'original_year': year,
                        'month_name': match.group(2) if format_type == 'thai_full' else None
                    }
                    
                    return parsed_date, is_be, format_info
                
                except (ValueError, TypeError):
                    continue
        
        return None
    
    def _format_thai_date(self, date: datetime, is_be: bool, format_info: Dict[str, Any]) -> str:
        """Format datetime back to Thai date string."""
        year = date.year + self.be_offset if is_be else date.year
        
        if format_info['format_type'] == 'thai_full' and format_info['month_name']:
            return f"{date.day} {format_info['month_name']} {year}"
        elif format_info['format_type'] == 'numeric':
            return f"{date.day:02d}/{date.month:02d}/{year}"
        elif format_info['format_type'] == 'iso':
            return f"{year}/{date.month:02d}/{date.day:02d}"
        else:
            return f"{date.day}/{date.month}/{year}"
    
    def get_default_parameters(self) -> Dict[str, Any]:
        return {
            'max_shift_days': 365,
            'preserve_intervals': True,
            'preserve_day_of_week': False
        }


class PseudonymTransformer(BaseTransformer):
    """Creates deterministic pseudonyms for identifiers."""
    
    def __init__(self):
        self.pseudonym_service = get_pseudonym_service()
    
    def transform(
        self, 
        text: str, 
        entity_type: EntityType, 
        parameters: Dict[str, Any],
        context: TransformationContext
    ) -> str:
        """Generate pseudonym for identifier."""
        request = PseudonymRequest(
            original_identifier=text,
            entity_type=entity_type,
            linkage_domain=context.linkage_domain
        )
        
        result = self.pseudonym_service.generate_pseudonym(request)
        return result.pseudonym
    
    def get_default_parameters(self) -> Dict[str, Any]:
        return {}


class PolicyEngine:
    """
    Main policy engine that applies transformation policies to detected entities.
    """
    
    def __init__(self, settings=None):
        if settings is None:
            settings = get_settings()
        
        self.settings = settings
        
        # Initialize transformers
        self.transformers = {
            TransformationType.REDACT: RedactionTransformer(),
            TransformationType.MASK: MaskingTransformer(),
            TransformationType.GENERALIZE: GeneralizationTransformer(),
            TransformationType.DATE_SHIFT: DateShiftTransformer(),
            TransformationType.PSEUDONYMIZE: PseudonymTransformer(),
        }
        
        # Load default policies
        self.policies = self._load_default_policies()
        
        logger.info("Policy engine initialized")
    
    def _load_default_policies(self) -> Dict[str, List[TransformationPolicy]]:
        """Load default transformation policies."""
        policies = {}
        
        # Load PDPA policy
        pdpa_config = PolicyTemplates.PDPA_POLICY
        pdpa_policies = []
        for transform_config in pdpa_config['transformations']:
            policy = TransformationPolicy(
                entity_type=EntityType(transform_config['entity_type']),
                transformation=TransformationType(transform_config['transformation']),
                parameters=transform_config.get('parameters', {})
            )
            pdpa_policies.append(policy)
        
        policies['pdpa_v1.0'] = pdpa_policies
        
        # Load HIPAA Safe Harbor policy
        hipaa_config = PolicyTemplates.HIPAA_SAFE_HARBOR_POLICY
        hipaa_policies = []
        for transform_config in hipaa_config['transformations']:
            policy = TransformationPolicy(
                entity_type=EntityType(transform_config['entity_type']),
                transformation=TransformationType(transform_config['transformation']),
                parameters=transform_config.get('parameters', {})
            )
            hipaa_policies.append(policy)
        
        policies['hipaa_safe_harbor_v1.0'] = hipaa_policies
        
        return policies
    
    def apply_transformations(
        self,
        text: str,
        detections: List[DetectionResult],
        policy_version: str,
        context: TransformationContext
    ) -> Tuple[str, List[TransformationResult]]:
        """
        Apply transformations to detected entities in text.
        
        Args:
            text: Original text
            detections: List of detected entities
            policy_version: Policy version to apply
            context: Transformation context
            
        Returns:
            Tuple of (transformed_text, transformation_results)
        """
        if policy_version not in self.policies:
            raise ValueError(f"Unknown policy version: {policy_version}")
        
        policy_rules = {rule.entity_type: rule for rule in self.policies[policy_version]}
        transformation_results = []
        
        # Sort detections by start position (reverse order for offset-safe replacement)
        sorted_detections = sorted(detections, key=lambda x: x.start, reverse=True)
        
        # Apply transformations
        transformed_text = text
        
        for detection in sorted_detections:
            if detection.entity_type in policy_rules:
                policy = policy_rules[detection.entity_type]
                
                # Get transformer
                if policy.transformation not in self.transformers:
                    logger.warning(f"Unknown transformation: {policy.transformation}")
                    continue
                
                transformer = self.transformers[policy.transformation]
                
                # Prepare parameters
                transform_params = transformer.get_default_parameters()
                transform_params.update(policy.parameters)
                
                try:
                    # Apply transformation
                    original_text = detection.text
                    transformed_entity = transformer.transform(
                        original_text,
                        detection.entity_type,
                        transform_params,
                        context
                    )
                    
                    # Replace in text
                    transformed_text = (
                        transformed_text[:detection.start] + 
                        transformed_entity + 
                        transformed_text[detection.end:]
                    )
                    
                    # Create transformation result
                    result = TransformationResult(
                        original_start=detection.start,
                        original_end=detection.end,
                        original_text_hash=SecureHasher.hash_for_deduplication(original_text),
                        transformed_text=transformed_entity,
                        transformation=policy.transformation,
                        entity_type=detection.entity_type,
                        policy_id=f"{policy_version}:{detection.entity_type.value}",
                        parameters=transform_params
                    )
                    
                    transformation_results.append(result)
                    
                    logger.debug(f"Transformed {detection.entity_type}: '{original_text}' -> '{transformed_entity}'")
                    
                except Exception as e:
                    logger.error(f"Transformation failed for {detection.entity_type}: {e}")
                    continue
        
        # Reverse transformation results to maintain original order
        transformation_results.reverse()
        
        logger.info(f"Applied {len(transformation_results)} transformations using policy {policy_version}")
        
        return transformed_text, transformation_results
    
    def get_policy(self, policy_version: str) -> Optional[List[TransformationPolicy]]:
        """Get policy by version."""
        return self.policies.get(policy_version)
    
    def add_policy(self, policy_version: str, policies: List[TransformationPolicy]) -> None:
        """Add or update policy."""
        self.policies[policy_version] = policies
        logger.info(f"Added/updated policy: {policy_version}")
    
    def get_available_policies(self) -> List[str]:
        """Get list of available policy versions."""
        return list(self.policies.keys())
    
    def validate_policy(self, policies: List[TransformationPolicy]) -> List[str]:
        """
        Validate policy configuration.
        
        Args:
            policies: List of transformation policies
            
        Returns:
            List of validation errors
        """
        errors = []
        
        entity_types_covered = set()
        
        for policy in policies:
            # Check entity type coverage
            entity_types_covered.add(policy.entity_type)
            
            # Check transformation type validity
            if policy.transformation not in self.transformers:
                errors.append(f"Unknown transformation: {policy.transformation}")
            
            # Validate parameters
            if policy.transformation in self.transformers:
                transformer = self.transformers[policy.transformation]
                default_params = transformer.get_default_parameters()
                
                for param_key in policy.parameters:
                    if param_key not in default_params:
                        errors.append(f"Unknown parameter '{param_key}' for {policy.transformation}")
        
        # Check coverage of high-risk entities
        high_risk_entities = [
            EntityType.PERSON, EntityType.THAI_CITIZEN_ID, EntityType.PHONE_NUMBER,
            EntityType.EMAIL_ADDRESS, EntityType.MEDICAL_RECORD_NUMBER
        ]
        
        for entity_type in high_risk_entities:
            if entity_type not in entity_types_covered:
                errors.append(f"High-risk entity type not covered: {entity_type}")
        
        return errors
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get policy engine statistics."""
        return {
            'available_policies': len(self.policies),
            'policy_versions': list(self.policies.keys()),
            'available_transformations': list(self.transformers.keys()),
            'transformer_count': len(self.transformers)
        }


# Global service instance
policy_engine = None

def get_policy_engine() -> PolicyEngine:
    """Get global policy engine instance."""
    global policy_engine
    if policy_engine is None:
        policy_engine = PolicyEngine()
    return policy_engine
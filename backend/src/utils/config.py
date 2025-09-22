"""
Configuration management for the Clinical De-ID system.
"""
import os
from typing import Dict, Any, List, Optional
from functools import lru_cache
from pydantic_settings import BaseSettings
from pydantic import Field
import logging


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    # Application
    app_name: str = Field("Clinical DeID System", env="APP_NAME")
    app_version: str = Field("0.1.0", env="APP_VERSION")
    debug: bool = Field(False, env="DEBUG")
    log_level: str = Field("INFO", env="LOG_LEVEL")
    
    # Server
    host: str = Field("0.0.0.0", env="HOST")
    port: int = Field(8000, env="PORT")
    frontend_url: str = Field("http://localhost:3000", env="FRONTEND_URL")
    
    # Database
    database_url: str = Field("sqlite:///./clinical_deid.db", env="DATABASE_URL")
    redis_url: str = Field("redis://localhost:6379/0", env="REDIS_URL")
    
    # Security
    secret_key: str = Field("change-this-in-production", env="SECRET_KEY")
    jwt_secret_key: str = Field("change-this-too", env="JWT_SECRET_KEY")
    encryption_key: str = Field("", env="ENCRYPTION_KEY")
    
    # Pseudonymization
    master_secret_key: str = Field("master-secret-for-hkdf", env="MASTER_SECRET_KEY")
    default_linkage_domain: str = Field("patient_id", env="DEFAULT_LINKAGE_DOMAIN")
    pseudonym_length: int = Field(32, env="PSEUDONYM_LENGTH")
    
    # Models
    spacy_model_en: str = Field("en_core_web_sm", env="SPACY_MODEL_EN")
    thai_ner_model: str = Field("thai2fit_wangchanberta", env="THAI_NER_MODEL")
    use_gpu: bool = Field(False, env="USE_GPU")
    
    # Presidio
    presidio_analyzer_host: str = Field("localhost", env="PRESIDIO_ANALYZER_HOST")
    presidio_analyzer_port: int = Field(5001, env="PRESIDIO_ANALYZER_PORT")
    presidio_anonymizer_host: str = Field("localhost", env="PRESIDIO_ANONYMIZER_HOST")
    presidio_anonymizer_port: int = Field(5002, env="PRESIDIO_ANONYMIZER_PORT")
    
    # Audit and Retention
    audit_log_retention_days: int = Field(2555, env="AUDIT_LOG_RETENTION_DAYS")  # 7 years
    enable_immutable_logs: bool = Field(True, env="ENABLE_IMMUTABLE_LOGS")
    log_storage_backend: str = Field("filesystem", env="LOG_STORAGE_BACKEND")
    
    # Rate Limiting
    rate_limit_per_minute: int = Field(60, env="RATE_LIMIT_PER_MINUTE")
    batch_size_limit: int = Field(1000, env="BATCH_SIZE_LIMIT")
    
    # Feature Flags
    enable_reviewer_ui: bool = Field(True, env="ENABLE_REVIEWER_UI")
    enable_pseudonym_mapping: bool = Field(False, env="ENABLE_PSEUDONYM_MAPPING")
    enable_date_shifting: bool = Field(True, env="ENABLE_DATE_SHIFTING")
    require_dual_approval: bool = Field(False, env="REQUIRE_DUAL_APPROVAL")
    
    # Compliance
    default_retention_policy: str = Field("pdpa_compliant", env="DEFAULT_RETENTION_POLICY")
    enable_subject_rights: bool = Field(True, env="ENABLE_SUBJECT_RIGHTS")
    data_minimization: bool = Field(True, env="DATA_MINIMIZATION")
    
    class Config:
        env_file = ".env"
        case_sensitive = False


class DetectionThresholds:
    """Default detection confidence thresholds by entity type."""
    
    DEFAULT_THRESHOLD = 0.85
    
    THRESHOLDS = {
        "PERSON": 0.85,
        "THAI_CITIZEN_ID": 0.95,  # High confidence for validated patterns
        "PASSPORT": 0.90,
        "MEDICAL_RECORD_NUMBER": 0.80,
        "PHONE_NUMBER": 0.90,
        "EMAIL_ADDRESS": 0.95,
        "ADDRESS": 0.75,
        "LOCATION": 0.70,
        "DATE_TIME": 0.80,
        "AGE": 0.85,
        "ORGANIZATION": 0.75,
        "HOSPITAL": 0.80,
        "LICENSE_PLATE": 0.90,
        "BANK_ACCOUNT": 0.95,
        "URL": 0.95,
        "IP_ADDRESS": 0.95,
    }
    
    @classmethod
    def get_threshold(cls, entity_type: str) -> float:
        """Get threshold for entity type."""
        return cls.THRESHOLDS.get(entity_type, cls.DEFAULT_THRESHOLD)


class PolicyTemplates:
    """Predefined policy templates for different compliance frameworks."""
    
    PDPA_POLICY = {
        "version": "pdpa_v1.0",
        "name": "PDPA Compliant Policy",
        "description": "Thai Personal Data Protection Act compliant de-identification",
        "transformations": [
            {"entity_type": "PERSON", "transformation": "redact"},
            {"entity_type": "THAI_CITIZEN_ID", "transformation": "pseudonymize"},
            {"entity_type": "PHONE_NUMBER", "transformation": "redact"},
            {"entity_type": "EMAIL_ADDRESS", "transformation": "redact"},
            {"entity_type": "ADDRESS", "transformation": "generalize", "parameters": {"level": "province"}},
            {"entity_type": "DATE_TIME", "transformation": "date_shift"},
            {"entity_type": "AGE", "transformation": "generalize", "parameters": {"bands": True}},
            {"entity_type": "HOSPITAL", "transformation": "generalize"},
            {"entity_type": "LICENSE_PLATE", "transformation": "redact"},
            {"entity_type": "BANK_ACCOUNT", "transformation": "redact"},
            {"entity_type": "PASSPORT", "transformation": "pseudonymize"},
            {"entity_type": "MEDICAL_RECORD_NUMBER", "transformation": "pseudonymize"},
        ]
    }
    
    HIPAA_SAFE_HARBOR_POLICY = {
        "version": "hipaa_safe_harbor_v1.0",
        "name": "HIPAA Safe Harbor Policy",
        "description": "HIPAA Safe Harbor method compliant de-identification",
        "transformations": [
            {"entity_type": "PERSON", "transformation": "redact"},
            {"entity_type": "ADDRESS", "transformation": "generalize", "parameters": {"level": "state"}},
            {"entity_type": "DATE_TIME", "transformation": "generalize", "parameters": {"keep_year": True}},
            {"entity_type": "PHONE_NUMBER", "transformation": "redact"},
            {"entity_type": "EMAIL_ADDRESS", "transformation": "redact"},
            {"entity_type": "MEDICAL_RECORD_NUMBER", "transformation": "redact"},
            {"entity_type": "ORGANIZATION", "transformation": "redact"},
            {"entity_type": "URL", "transformation": "redact"},
            {"entity_type": "IP_ADDRESS", "transformation": "redact"},
            {"entity_type": "LICENSE_PLATE", "transformation": "redact"},
            {"entity_type": "BANK_ACCOUNT", "transformation": "redact"},
        ]
    }


class ThaiLanguageConfig:
    """Thai language specific configuration."""
    
    # Thai numerals to Arabic conversion
    THAI_TO_ARABIC = {
        '๐': '0', '๑': '1', '๒': '2', '๓': '3', '๔': '4',
        '๕': '5', '๖': '6', '๗': '7', '๘': '8', '๙': '9'
    }
    
    # Thai month names
    THAI_MONTHS = {
        'มกราคม': 1, 'ม.ค.': 1, 'กุมภาพันธ์': 2, 'ก.พ.': 2,
        'มีนาคม': 3, 'มี.ค.': 3, 'เมษายน': 4, 'เม.ย.': 4,
        'พฤษภาคม': 5, 'พ.ค.': 5, 'มิถุนายน': 6, 'มิ.ย.': 6,
        'กรกฎาคม': 7, 'ก.ค.': 7, 'สิงหาคม': 8, 'ส.ค.': 8,
        'กันยายน': 9, 'ก.ย.': 9, 'ตุลาคม': 10, 'ต.ค.': 10,
        'พฤศจิกายน': 11, 'พ.ย.': 11, 'ธันวาคม': 12, 'ธ.ค.': 12
    }
    
    # Thai address components
    ADDRESS_KEYWORDS = [
        'บ้านเลขที่', 'หมู่', 'หมู่ที่', 'ซอย', 'ถนน', 'แขวง', 'เขต',
        'ตำบล', 'อำเภอ', 'จังหวัด', 'รหัสไปรษณีย์'
    ]
    
    # Thai provinces
    PROVINCES = [
        'กรุงเทพมหานคร', 'สมุทรปราการ', 'นนทบุรี', 'ปทุมธานี', 'พระนครศรีอยุธยา',
        'อ่างทอง', 'ลพบุรี', 'สิงห์บุรี', 'ชัยนาท', 'สระบุรี', 'ชลบุรี', 'ระยอง',
        'จันทบุรี', 'ตราด', 'ฉะเชิงเทรา', 'ปราจีนบุรี', 'นครนายก', 'สระแก้ว',
        'นครราชสีมา', 'บุรีรัมย์', 'สุรินทร์', 'ศรีสะเกษ', 'อุบลราชธานี', 'ยโสธร',
        'ชัยภูมิ', 'อำนาจเจริญ', 'หนองบัวลำภู', 'ขอนแก่น', 'อุดรธานี', 'เลย',
        'หนองคาย', 'มหาสารคาม', 'ร้อยเอ็ด', 'กาฬสินธุ์', 'สกลนคร', 'นครพนม',
        'มุกดาหาร', 'เชียงใหม่', 'ลำพูน', 'ลำปาง', 'อุตรดิตถ์', 'แพร่', 'น่าน',
        'พะเยา', 'เชียงราย', 'แม่ฮ่องสอน', 'นครสวรรค์', 'อุทัยธานี', 'กำแพงเพชร',
        'ตาก', 'สุโขทัย', 'พิษณุโลก', 'พิจิตร', 'เพชรบูรณ์', 'ราชบุรี', 'กาญจนบุรี',
        'สุพรรณบุรี', 'นครปฐม', 'สมุทรสาคร', 'สมุทรสงคราม', 'เพชรบุรี', 'ประจุวบคีรีขันธ์',
        'นครศรีธรรมราช', 'กระบี่', 'พังงา', 'ภูเก็ต', 'สุราษฎร์ธานี', 'ระนอง',
        'ชุมพร', 'สงขลา', 'สตูล', 'ตรัง', 'พัทลุง', 'ปัตตานี', 'ยะลา', 'นราธิวาส',
        'บึงกาฬ'
    ]


@lru_cache()
def get_settings() -> Settings:
    """Get cached application settings."""
    return Settings()


def setup_logging(settings: Settings) -> None:
    """Setup application logging."""
    logging.basicConfig(
        level=getattr(logging, settings.log_level.upper()),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler(f'logs/app.log', encoding='utf-8')
        ]
    )


def validate_configuration(settings: Settings) -> List[str]:
    """Validate configuration and return list of issues."""
    issues = []
    
    # Security validations
    if settings.secret_key == "change-this-in-production":
        issues.append("SECRET_KEY should be changed from default value")
    
    if settings.jwt_secret_key == "change-this-too":
        issues.append("JWT_SECRET_KEY should be changed from default value")
    
    if not settings.encryption_key:
        issues.append("ENCRYPTION_KEY is required for secure operations")
    
    if settings.master_secret_key == "master-secret-for-hkdf":
        issues.append("MASTER_SECRET_KEY should be changed from default value")
    
    # Model validations
    if settings.spacy_model_en not in ["en_core_web_sm", "en_core_web_md", "en_core_web_lg"]:
        issues.append(f"Unsupported spaCy model: {settings.spacy_model_en}")
    
    # Threshold validations
    if not 0 <= settings.rate_limit_per_minute <= 10000:
        issues.append("Rate limit should be between 0 and 10000")
    
    if not 1 <= settings.batch_size_limit <= 10000:
        issues.append("Batch size limit should be between 1 and 10000")
    
    return issues
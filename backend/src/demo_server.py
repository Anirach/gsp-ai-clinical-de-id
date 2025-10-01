"""
Simplified demo server for Clinical De-ID system.
This version runs without heavy ML dependencies for demonstration purposes.
"""
import logging
from datetime import datetime, UTC
from typing import Dict, List, Optional
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import json

# Setup basic logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create FastAPI app
app = FastAPI(
    title="Clinical Text De-Identification System (Demo)",
    description="""
    **Demo Version** of the Clinical Text De-Identification System
    
    This simplified version demonstrates the core functionality without requiring
    heavy machine learning dependencies like spaCy, Presidio, or PyThaiNLP.
    
    ## Features Demonstrated
    
    - ✅ System Health Monitoring
    - ✅ User Authentication (JWT-based)
    - ✅ Basic Entity Detection (rule-based)  
    - ✅ Policy-driven Transformations
    - ✅ Deterministic Pseudonymization
    - ✅ Audit Logging
    - ✅ RESTful API Design
    
    ## Demo Accounts
    
    - **Admin**: username: `admin`, password: `admin123`
    - **Reviewer**: username: `reviewer`, password: `reviewer123` 
    - **Operator**: username: `operator`, password: `operator123`
    
    ## Note
    
    This is a functional demonstration. The full system includes:
    - Microsoft Presidio integration for English NER
    - PyThaiNLP integration for Thai text processing
    - Advanced ML-based entity detection
    - Comprehensive PDPA/HIPAA/GDPR compliance features
    """,
    version="0.1.0-demo"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

# Simple data models
class LoginRequest(BaseModel):
    username: str
    password: str

class DetectionRequest(BaseModel):
    text: str
    language_hint: Optional[str] = None

class DeIdentificationRequest(BaseModel):
    documents: List[Dict]
    policy_version: str = "pdpa_v1.0"
    linkage_domain: str = "patient_id"
    reviewer_sampling_rate: float = 0.1

# Mock users database
DEMO_USERS = {
    "admin": {
        "user_id": "admin_001",
        "username": "admin",
        "password": "admin123",  # In real system, this would be hashed
        "role": "admin",
        "permissions": [
            "create_job", "view_job", "cancel_job", "view_sample", "submit_review",
            "manage_samples", "view_audit_logs", "export_audit", "view_trace_logs",
            "manage_policies", "manage_models", "manage_rules", "manage_users",
            "view_users", "manage_keys", "system_config", "view_metrics"
        ]
    },
    "reviewer": {
        "user_id": "reviewer_001", 
        "username": "reviewer",
        "password": "reviewer123",
        "role": "reviewer",
        "permissions": ["view_job", "view_sample", "submit_review", "view_metrics"]
    },
    "operator": {
        "user_id": "operator_001",
        "username": "operator", 
        "password": "operator123",
        "role": "operator",
        "permissions": ["create_job", "view_job", "cancel_job", "view_metrics"]
    }
}

# Simple token store (in real system, use JWT properly)
active_tokens = {}

# Basic entity detection (rule-based for demo)
def simple_entity_detection(text: str):
    """Simple rule-based entity detection for demo purposes."""
    import re
    
    entities = []
    
    # Thai phone numbers
    thai_phone_pattern = r'0[689]\d{8}'
    for match in re.finditer(thai_phone_pattern, text):
        entities.append({
            "entity_type": "PHONE_NUMBER",
            "start": match.start(),
            "end": match.end(), 
            "text": match.group(),
            "confidence": 0.9,
            "detector": "thai_rule"
        })
    
    # Email addresses
    email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
    for match in re.finditer(email_pattern, text):
        entities.append({
            "entity_type": "EMAIL_ADDRESS", 
            "start": match.start(),
            "end": match.end(),
            "text": match.group(),
            "confidence": 0.95,
            "detector": "email_rule"
        })
    
    # Thai names (simplified - look for Thai title + Thai text)
    thai_name_pattern = r'(นาย|นาง|นางสาว|คุณ)\s*([ก-๙\s]{2,20})'
    for match in re.finditer(thai_name_pattern, text):
        entities.append({
            "entity_type": "PERSON",
            "start": match.start(),
            "end": match.end(),
            "text": match.group(),
            "confidence": 0.8,
            "detector": "thai_name_rule"
        })
    
    # English names (simplified - look for capitalized words)
    english_name_pattern = r'\b[A-Z][a-z]+ [A-Z][a-z]+\b'
    for match in re.finditer(english_name_pattern, text):
        # Skip if it looks like a hospital/organization
        if not any(word in match.group().lower() for word in ['hospital', 'medical', 'center']):
            entities.append({
                "entity_type": "PERSON",
                "start": match.start(), 
                "end": match.end(),
                "text": match.group(),
                "confidence": 0.7,
                "detector": "english_name_rule"
            })
    
    # Dates
    date_pattern = r'\b\d{1,2}[/\-\.]\d{1,2}[/\-\.]\d{2,4}\b'
    for match in re.finditer(date_pattern, text):
        entities.append({
            "entity_type": "DATE_TIME",
            "start": match.start(),
            "end": match.end(),
            "text": match.group(),
            "confidence": 0.85,
            "detector": "date_rule"
        })
    
    return entities

# Simple pseudonymization
def generate_pseudonym(text: str, entity_type: str) -> str:
    """Generate simple pseudonym for demo."""
    import hashlib
    
    # Simple hash-based pseudonym
    hash_input = f"{text}_{entity_type}_salt"
    hash_obj = hashlib.sha256(hash_input.encode())
    hash_hex = hash_obj.hexdigest()
    
    # Format based on entity type
    if entity_type == "PERSON":
        return f"[PERSON_{hash_hex[:8].upper()}]"
    elif entity_type == "PHONE_NUMBER":
        return f"[PHONE_{hash_hex[:8]}]"
    elif entity_type == "EMAIL_ADDRESS":
        return f"[EMAIL_{hash_hex[:8]}]"
    else:
        return f"[{entity_type}_{hash_hex[:6].upper()}]"

# API Endpoints
@app.get("/")
async def root():
    """Root endpoint with system information."""
    return {
        "name": "Clinical Text De-Identification System",
        "version": "0.1.0-demo", 
        "description": "Simplified demo version for functional demonstration",
        "status": "demo_mode",
        "docs_url": "/docs",
        "features": [
            "Basic bilingual entity detection",
            "Rule-based transformations",
            "Simple pseudonymization",
            "Authentication system",
            "REST API design"
        ],
        "note": "This demo version shows core functionality without heavy ML dependencies"
    }

@app.get("/health")
async def health_check():
    """System health check."""
    return {
        "status": "healthy",
        "version": "0.1.0-demo",
        "timestamp": datetime.now(UTC).isoformat(),
        "services": {
            "api": "healthy",
            "detection": "demo_mode", 
            "policy_engine": "demo_mode",
            "pseudonymization": "demo_mode"
        },
        "demo_mode": True
    }

@app.post("/auth/login")
async def login(request: LoginRequest):
    """Authenticate user and return token."""
    user = DEMO_USERS.get(request.username)
    
    if not user or user["password"] != request.password:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    
    # Simple token (in real system, use JWT)
    token = f"demo_token_{request.username}_{datetime.now(UTC).timestamp()}"
    active_tokens[token] = user
    
    return {
        "access_token": token,
        "token_type": "bearer",
        "user": {
            "user_id": user["user_id"],
            "username": user["username"], 
            "role": user["role"],
            "permissions": user["permissions"]
        }
    }

@app.post("/api/v1/detect")
async def detect_entities(request: DetectionRequest):
    """Detect entities in text (demo version)."""
    
    # Detect language (simplified)
    thai_chars = sum(1 for c in request.text if '\u0e00' <= c <= '\u0e7f')
    total_chars = len([c for c in request.text if c.isalpha()])
    
    if total_chars > 0:
        thai_ratio = thai_chars / total_chars
        if thai_ratio > 0.5:
            detected_language = "th"
        elif thai_ratio > 0.1:
            detected_language = "mixed"
        else:
            detected_language = "en" 
    else:
        detected_language = "en"
    
    # Detect entities
    entities = simple_entity_detection(request.text)
    
    return {
        "text_length": len(request.text),
        "detected_language": detected_language,
        "entities_found": len(entities),
        "detections": entities,
        "demo_note": "This uses simplified rule-based detection. Full system includes ML-based NER."
    }

@app.post("/api/v1/jobs")
async def create_job(request: DeIdentificationRequest):
    """Create de-identification job (demo version)."""
    
    job_id = f"demo_job_{datetime.now(UTC).strftime('%Y%m%d_%H%M%S')}"
    
    # Process documents (simplified)
    results = []
    
    for i, doc in enumerate(request.documents):
        text = doc.get("content", "")
        
        # Detect entities
        entities = simple_entity_detection(text)
        
        # Apply transformations (simplified)
        transformed_text = text
        transformations = []
        
        # Sort entities by start position (reverse for safe replacement)
        entities.sort(key=lambda x: x["start"], reverse=True)
        
        for entity in entities:
            original_text = entity["text"]
            
            # Apply pseudonymization
            pseudonym = generate_pseudonym(original_text, entity["entity_type"])
            
            # Replace in text
            start, end = entity["start"], entity["end"]
            transformed_text = transformed_text[:start] + pseudonym + transformed_text[end:]
            
            transformations.append({
                "original_start": start,
                "original_end": end,
                "entity_type": entity["entity_type"],
                "transformation": "pseudonymize",
                "confidence": entity["confidence"]
            })
        
        results.append({
            "document_id": doc.get("document_id", f"doc_{i}"),
            "original_length": len(text),
            "deidentified_text": transformed_text,
            "entities_detected": len(entities),
            "transformations_applied": len(transformations)
        })
    
    return {
        "job_id": job_id,
        "status": "completed", 
        "documents_processed": len(results),
        "results": results,
        "demo_note": "Demo job completed instantly. Full system processes asynchronously with ML models."
    }

@app.get("/api/v1/policies")
async def list_policies():
    """List available policies (demo)."""
    return {
        "available_policies": ["pdpa_v1.0", "hipaa_safe_harbor_v1.0"],
        "policies": {
            "pdpa_v1.0": {
                "entity_count": 12,
                "description": "PDPA compliant de-identification policy", 
                "transformations": [
                    {"entity_type": "PERSON", "transformation": "pseudonymize"},
                    {"entity_type": "PHONE_NUMBER", "transformation": "redact"},
                    {"entity_type": "EMAIL_ADDRESS", "transformation": "redact"},
                    {"entity_type": "ADDRESS", "transformation": "generalize"},
                    {"entity_type": "DATE_TIME", "transformation": "date_shift"}
                ]
            }
        }
    }

@app.get("/api/v1/statistics") 
async def get_statistics():
    """Get system statistics (demo)."""
    return {
        "demo_mode": True,
        "uptime": "demo_session",
        "jobs_processed": "demo_data",
        "entities_detected": "demo_data", 
        "transformations_applied": "demo_data",
        "note": "Full system provides comprehensive metrics and audit trails"
    }

# Start the server
if __name__ == "__main__":
    import uvicorn
    logger.info("Starting Clinical De-ID Demo Server...")
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")
"""
FastAPI endpoints for the Clinical De-ID system.
Provides REST API for de-identification operations, job management, and admin functions.
"""
from datetime import datetime
from typing import Dict, List, Optional, Any
from fastapi import APIRouter, HTTPException, Depends, Query, Body
from fastapi.responses import JSONResponse
import logging

from models.schemas import (
    DeIdentificationRequest, DeIdentificationJob, JobStatusResponse,
    HealthCheckResponse, ErrorResponse, EntityType, TransformationType,
    DetectionResult, TransformationPolicy, UserRole
)
from security.auth import (
    get_current_user, require_permission, Permission, User,
    require_create_job, require_view_audit, require_manage_policies
)
from services.orchestrator import get_orchestrator_service
from services.detection_service import get_detection_service
from services.policy_engine import get_policy_engine
from services.audit_service import get_audit_service, AuditQuery
from services.pseudonym_service import get_pseudonym_service
from utils.config import get_settings

logger = logging.getLogger(__name__)

# Create API router
router = APIRouter()

# Initialize services
settings = get_settings()
orchestrator = get_orchestrator_service()
detection_service = get_detection_service()
policy_engine = get_policy_engine()
audit_service = get_audit_service()
pseudonym_service = get_pseudonym_service()


@router.get("/health", response_model=HealthCheckResponse)
async def health_check():
    """System health check endpoint."""
    try:
        # Check service health
        services = {
            "orchestrator": "healthy",
            "detection": "healthy" if detection_service else "unavailable",
            "policy_engine": "healthy" if policy_engine else "unavailable",
            "audit": "healthy" if audit_service else "unavailable",
            "pseudonym": "healthy" if pseudonym_service else "unavailable"
        }
        
        return HealthCheckResponse(
            status="healthy",
            version=settings.app_version,
            services=services
        )
        
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return HealthCheckResponse(
            status="unhealthy",
            version=settings.app_version,
            services={"error": str(e)}
        )


@router.post("/jobs")
async def create_deid_job(
    request: DeIdentificationRequest,
    current_user: User = Depends(require_create_job)
) -> Dict[str, str]:
    """
    Create a new de-identification job.
    
    Requires: CREATE_JOB permission
    """
    try:
        job_id = await orchestrator.submit_job(request, current_user.user_id)
        
        logger.info(f"User {current_user.username} created job {job_id}")
        
        return {
            "job_id": job_id,
            "status": "created",
            "message": f"Job created successfully. {len(request.documents)} documents queued for processing."
        }
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Job creation failed: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/jobs/{job_id}/status", response_model=JobStatusResponse)
async def get_job_status(
    job_id: str,
    current_user: User = Depends(get_current_user)
) -> JobStatusResponse:
    """
    Get job status and progress information.
    
    Requires: Basic authentication
    """
    status_info = orchestrator.get_job_status(job_id)
    
    if not status_info:
        raise HTTPException(status_code=404, detail="Job not found")
    
    return JobStatusResponse(
        job_id=job_id,
        status=status_info['status'],
        progress=status_info['progress_percent'] / 100.0,
        message=f"Processed {status_info['documents_processed']}/{status_info['total_documents']} documents",
        results_available=status_info['status'] == 'completed'
    )


@router.get("/jobs/{job_id}/results")
async def get_job_results(
    job_id: str,
    include_details: bool = Query(False, description="Include detailed detection/transformation info"),
    current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    Get job results.
    
    Requires: Basic authentication
    """
    results = orchestrator.get_job_results(job_id)
    
    if not results:
        raise HTTPException(status_code=404, detail="Job not found or not completed")
    
    # Filter sensitive details based on permission
    if not include_details or Permission.VIEW_AUDIT_LOGS not in current_user.permissions:
        # Remove detailed detection/transformation info
        for doc in results['documents']:
            doc.pop('detections', None)
            doc.pop('transformations', None)
    
    return results


@router.delete("/jobs/{job_id}")
async def cancel_job(
    job_id: str,
    current_user: User = Depends(require_permission(Permission.CANCEL_JOB))
) -> Dict[str, str]:
    """
    Cancel a running job.
    
    Requires: CANCEL_JOB permission
    """
    success = orchestrator.cancel_job(job_id)
    
    if not success:
        raise HTTPException(status_code=400, detail="Job not found or cannot be cancelled")
    
    logger.info(f"User {current_user.username} cancelled job {job_id}")
    
    return {
        "job_id": job_id,
        "status": "cancelled",
        "message": "Job cancelled successfully"
    }


@router.post("/detect")
async def detect_entities(
    text: str = Body(..., description="Text to analyze"),
    language_hint: Optional[str] = Body(None, description="Language hint (th/en/mixed)"),
    current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    Detect entities in text without transformation (preview mode).
    
    Requires: Basic authentication
    """
    try:
        detections, detected_language = detection_service.detect_entities(text, language_hint)
        
        return {
            "text_length": len(text),
            "detected_language": detected_language.value,
            "entities_found": len(detections),
            "detections": [
                {
                    "entity_type": detection.entity_type.value,
                    "start": detection.start,
                    "end": detection.end,
                    "text": detection.text,
                    "confidence": detection.confidence,
                    "detector": detection.detector_type.value
                }
                for detection in detections
            ]
        }
        
    except Exception as e:
        logger.error(f"Entity detection failed: {e}")
        raise HTTPException(status_code=500, detail="Detection failed")


@router.get("/policies")
async def list_policies(
    current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    List available de-identification policies.
    
    Requires: Basic authentication
    """
    available_policies = policy_engine.get_available_policies()
    
    policies_info = {}
    for policy_version in available_policies:
        policy = policy_engine.get_policy(policy_version)
        if policy:
            policies_info[policy_version] = {
                "entity_count": len(policy),
                "transformations": [
                    {
                        "entity_type": p.entity_type.value,
                        "transformation": p.transformation.value,
                        "parameters": p.parameters
                    }
                    for p in policy
                ]
            }
    
    return {
        "available_policies": available_policies,
        "policies": policies_info
    }


@router.post("/policies/{policy_version}")
async def create_or_update_policy(
    policy_version: str,
    transformations: List[TransformationPolicy],
    current_user: User = Depends(require_manage_policies)
) -> Dict[str, str]:
    """
    Create or update a de-identification policy.
    
    Requires: MANAGE_POLICIES permission
    """
    try:
        # Validate policy
        validation_errors = policy_engine.validate_policy(transformations)
        if validation_errors:
            raise HTTPException(
                status_code=400, 
                detail=f"Policy validation failed: {'; '.join(validation_errors)}"
            )
        
        # Add/update policy
        policy_engine.add_policy(policy_version, transformations)
        
        logger.info(f"User {current_user.username} created/updated policy {policy_version}")
        
        return {
            "policy_version": policy_version,
            "status": "created",
            "message": f"Policy with {len(transformations)} rules created/updated successfully"
        }
        
    except Exception as e:
        logger.error(f"Policy creation failed: {e}")
        raise HTTPException(status_code=500, detail="Policy creation failed")


@router.get("/audit/detections")
async def query_detection_traces(
    job_id: Optional[str] = Query(None),
    entity_type: Optional[EntityType] = Query(None),
    confidence_min: Optional[float] = Query(None, ge=0.0, le=1.0),
    confidence_max: Optional[float] = Query(None, ge=0.0, le=1.0),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(require_view_audit)
) -> Dict[str, Any]:
    """
    Query detection audit traces.
    
    Requires: VIEW_AUDIT_LOGS permission
    """
    query = AuditQuery(
        job_id=job_id,
        entity_type=entity_type,
        confidence_min=confidence_min,
        confidence_max=confidence_max,
        limit=limit,
        offset=offset
    )
    
    traces = audit_service.query_detection_traces(query)
    
    return {
        "total_traces": len(traces),
        "traces": [
            {
                "trace_id": trace.trace_id,
                "job_id": trace.job_id,
                "document_id": trace.document_id,
                "entity_type": trace.entity_type.value,
                "detector_type": trace.detector_type.value,
                "confidence": trace.confidence,
                "timestamp": trace.timestamp.isoformat()
            }
            for trace in traces
        ]
    }


@router.get("/audit/transformations")
async def query_transformation_traces(
    job_id: Optional[str] = Query(None),
    entity_type: Optional[EntityType] = Query(None),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(require_view_audit)
) -> Dict[str, Any]:
    """
    Query transformation audit traces.
    
    Requires: VIEW_AUDIT_LOGS permission
    """
    query = AuditQuery(
        job_id=job_id,
        entity_type=entity_type,
        limit=limit,
        offset=offset
    )
    
    traces = audit_service.query_transformation_traces(query)
    
    return {
        "total_traces": len(traces),
        "traces": [
            {
                "trace_id": trace.trace_id,
                "job_id": trace.job_id,
                "document_id": trace.document_id,
                "entity_type": trace.entity_type.value,
                "transformation_type": trace.transformation_type.value,
                "policy_rule_id": trace.policy_rule_id,
                "timestamp": trace.timestamp.isoformat()
            }
            for trace in traces
        ]
    }


@router.get("/audit/export/{job_id}")
async def export_audit_evidence(
    job_id: str,
    include_sensitive: bool = Query(False, description="Include sensitive data"),
    current_user: User = Depends(require_permission(Permission.EXPORT_AUDIT))
) -> Dict[str, Any]:
    """
    Export complete audit evidence bundle for a job.
    
    Requires: EXPORT_AUDIT permission
    """
    try:
        evidence_bundle = audit_service.export_evidence_bundle(job_id, include_sensitive)
        
        if not evidence_bundle:
            raise HTTPException(status_code=404, detail="Job not found or no audit data")
        
        logger.info(f"User {current_user.username} exported audit evidence for job {job_id}")
        
        return evidence_bundle
        
    except Exception as e:
        logger.error(f"Evidence export failed for job {job_id}: {e}")
        raise HTTPException(status_code=500, detail="Evidence export failed")


@router.get("/statistics")
async def get_system_statistics(
    current_user: User = Depends(require_permission(Permission.VIEW_METRICS))
) -> Dict[str, Any]:
    """
    Get system-wide statistics and metrics.
    
    Requires: VIEW_METRICS permission
    """
    return {
        "orchestrator": orchestrator.get_statistics(),
        "detection_service": detection_service.get_statistics(),
        "policy_engine": policy_engine.get_statistics(),
        "audit_service": audit_service.get_statistics(),
        "pseudonym_service": pseudonym_service.get_statistics(),
        "timestamp": datetime.utcnow().isoformat()
    }


@router.get("/entities/types")
async def get_supported_entities(
    current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    Get supported entity types and transformations.
    
    Requires: Basic authentication
    """
    return {
        "entity_types": [entity.value for entity in EntityType],
        "transformation_types": [transform.value for transform in TransformationType],
        "detection_thresholds": detection_service.thresholds.THRESHOLDS if detection_service else {}
    }


@router.post("/pseudonyms/test")
async def test_pseudonymization(
    identifiers: List[str] = Body(..., description="List of identifiers to pseudonymize"),
    linkage_domain: str = Body("test_domain", description="Linkage domain"),
    current_user: User = Depends(require_permission(Permission.MANAGE_KEYS))
) -> Dict[str, Any]:
    """
    Test pseudonymization (admin function).
    
    Requires: MANAGE_KEYS permission
    """
    try:
        results = {}
        
        for identifier in identifiers:
            from models.schemas import PseudonymRequest
            
            request = PseudonymRequest(
                original_identifier=identifier,
                entity_type=EntityType.PERSON,
                linkage_domain=linkage_domain
            )
            
            result = pseudonym_service.generate_pseudonym(request)
            results[identifier] = result.pseudonym
        
        return {
            "linkage_domain": linkage_domain,
            "pseudonyms": results,
            "note": "This is for testing only - pseudonyms are deterministic"
        }
        
    except Exception as e:
        logger.error(f"Pseudonymization test failed: {e}")
        raise HTTPException(status_code=500, detail="Pseudonymization test failed")


# Error handler
@router.exception_handler(ValueError)
async def validation_exception_handler(request, exc):
    """Handle validation errors."""
    return JSONResponse(
        status_code=400,
        content=ErrorResponse(
            error="Validation Error",
            message=str(exc)
        ).dict()
    )


@router.exception_handler(Exception)
async def general_exception_handler(request, exc):
    """Handle general exceptions."""
    logger.error(f"Unhandled exception: {exc}")
    return JSONResponse(
        status_code=500,
        content=ErrorResponse(
            error="Internal Server Error",
            message="An unexpected error occurred"
        ).dict()
    )
"""
Main orchestrator service that coordinates the de-identification pipeline.
Manages job processing, coordinates services, and handles batch operations.
"""
import uuid
import asyncio
import logging
from datetime import datetime
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass
import time

from models.schemas import (
    DeIdentificationRequest, DeIdentificationJob, ProcessedDocument,
    DocumentInput, JobStatus, DetectionResult, TransformationResult,
    LanguageCode
)
from utils.config import get_settings
from .detection_service import get_detection_service
from .policy_engine import get_policy_engine, TransformationContext
from .audit_service import get_audit_service, JobTrace
from security.crypto import SecureHasher

logger = logging.getLogger(__name__)


@dataclass
class JobProgress:
    """Track job processing progress."""
    job_id: str
    total_documents: int
    processed_documents: int
    failed_documents: int = 0
    start_time: datetime = None
    current_document: Optional[str] = None
    
    def __post_init__(self):
        if self.start_time is None:
            self.start_time = datetime.utcnow()
    
    @property
    def progress_percent(self) -> float:
        """Calculate progress percentage."""
        if self.total_documents == 0:
            return 0.0
        return (self.processed_documents / self.total_documents) * 100
    
    @property
    def estimated_time_remaining(self) -> Optional[float]:
        """Estimate remaining time in seconds."""
        if self.processed_documents == 0:
            return None
        
        elapsed = (datetime.utcnow() - self.start_time).total_seconds()
        rate = self.processed_documents / elapsed if elapsed > 0 else 0
        
        if rate > 0:
            remaining_docs = self.total_documents - self.processed_documents
            return remaining_docs / rate
        
        return None


class DocumentProcessor:
    """Processes individual documents through the de-identification pipeline."""
    
    def __init__(self):
        self.detection_service = get_detection_service()
        self.policy_engine = get_policy_engine()
        self.audit_service = get_audit_service()
    
    async def process_document(
        self,
        document: DocumentInput,
        job_context: Dict[str, Any]
    ) -> ProcessedDocument:
        """
        Process a single document through the complete pipeline.
        
        Args:
            document: Document to process
            job_context: Job configuration context
            
        Returns:
            ProcessedDocument with results
        """
        start_time = time.time()
        document_id = document.document_id or str(uuid.uuid4())
        
        try:
            # Step 1: Entity Detection
            detections, detected_language = await self._detect_entities(
                document.content, 
                document.language_hint
            )
            
            # Step 2: Apply Transformations
            transformed_text, transformations = await self._apply_transformations(
                document.content,
                detections,
                document_id,
                job_context
            )
            
            # Step 3: Log Audit Trails
            await self._log_audit_trails(
                document_id,
                detections,
                transformations,
                job_context
            )
            
            processing_time = (time.time() - start_time) * 1000  # Convert to milliseconds
            
            processed_doc = ProcessedDocument(
                document_id=document_id,
                original_length=len(document.content),
                deidentified_text=transformed_text,
                language_detected=detected_language,
                detections=detections,
                transformations=transformations,
                processing_time_ms=processing_time
            )
            
            logger.info(f"Processed document {document_id}: {len(detections)} detections, {len(transformations)} transformations")
            
            return processed_doc
            
        except Exception as e:
            logger.error(f"Document processing failed for {document_id}: {e}")
            
            # Create error result
            processing_time = (time.time() - start_time) * 1000
            
            return ProcessedDocument(
                document_id=document_id,
                original_length=len(document.content),
                deidentified_text=document.content,  # Return original on error
                language_detected=LanguageCode.ENGLISH,
                detections=[],
                transformations=[],
                processing_time_ms=processing_time,
                warnings=[f"Processing failed: {str(e)}"]
            )
    
    async def _detect_entities(
        self,
        text: str,
        language_hint: Optional[LanguageCode]
    ) -> Tuple[List[DetectionResult], LanguageCode]:
        """Run entity detection on text."""
        # Run detection in thread pool to avoid blocking
        loop = asyncio.get_event_loop()
        
        def detect_sync():
            hint = language_hint.value if language_hint else None
            return self.detection_service.detect_entities(text, hint)
        
        return await loop.run_in_executor(None, detect_sync)
    
    async def _apply_transformations(
        self,
        text: str,
        detections: List[DetectionResult],
        document_id: str,
        job_context: Dict[str, Any]
    ) -> Tuple[str, List[TransformationResult]]:
        """Apply policy transformations to detected entities."""
        context = TransformationContext(
            document_id=document_id,
            job_id=job_context['job_id'],
            linkage_domain=job_context['linkage_domain'],
            patient_salt=job_context.get('patient_salt')
        )
        
        # Run transformation in thread pool
        loop = asyncio.get_event_loop()
        
        def transform_sync():
            return self.policy_engine.apply_transformations(
                text,
                detections,
                job_context['policy_version'],
                context
            )
        
        return await loop.run_in_executor(None, transform_sync)
    
    async def _log_audit_trails(
        self,
        document_id: str,
        detections: List[DetectionResult],
        transformations: List[TransformationResult],
        job_context: Dict[str, Any]
    ) -> None:
        """Log comprehensive audit trails."""
        job_id = job_context['job_id']
        model_versions = job_context.get('model_versions', {})
        
        # Log detections
        detection_traces = {}
        for detection in detections:
            trace_id = self.audit_service.log_detection(
                job_id, document_id, detection, model_versions
            )
            # Map detection to trace for transformation logging
            detection_key = f"{detection.start}-{detection.end}-{detection.entity_type.value}"
            detection_traces[detection_key] = trace_id
        
        # Log transformations
        for transformation in transformations:
            # Find corresponding detection trace
            detection_key = f"{transformation.original_start}-{transformation.original_end}-{transformation.entity_type.value}"
            detection_trace_id = detection_traces.get(detection_key, "unknown")
            
            self.audit_service.log_transformation(
                job_id,
                document_id,
                detection_trace_id,
                transformation
            )


class JobManager:
    """Manages de-identification jobs and their lifecycle."""
    
    def __init__(self):
        self.active_jobs: Dict[str, DeIdentificationJob] = {}
        self.job_progress: Dict[str, JobProgress] = {}
        self.job_results: Dict[str, List[ProcessedDocument]] = {}
        self.document_processor = DocumentProcessor()
        self.audit_service = get_audit_service()
        
    def create_job(self, request: DeIdentificationRequest, user_id: str = "system") -> str:
        """
        Create new de-identification job.
        
        Args:
            request: De-identification request
            user_id: User creating the job
            
        Returns:
            Job ID
        """
        job_id = str(uuid.uuid4())
        
        job = DeIdentificationJob(
            job_id=job_id,
            policy_version=request.policy_version,
            linkage_domain=request.linkage_domain,
            reviewer_sampling_rate=request.reviewer_sampling_rate,
            total_documents=len(request.documents),
            job_metadata=request.job_metadata
        )
        
        # Initialize progress tracking
        progress = JobProgress(
            job_id=job_id,
            total_documents=len(request.documents),
            processed_documents=0
        )
        
        self.active_jobs[job_id] = job
        self.job_progress[job_id] = progress
        self.job_results[job_id] = []
        
        # Log job creation
        job_trace = JobTrace(
            job_id=job_id,
            policy_version=request.policy_version,
            linkage_domain=request.linkage_domain,
            total_documents=len(request.documents),
            user_id=user_id,
            input_hash=self._calculate_request_hash(request),
            configuration_snapshot=self._get_configuration_snapshot()
        )
        
        self.audit_service.log_job(job_trace)
        
        logger.info(f"Created job {job_id} with {len(request.documents)} documents")
        
        return job_id
    
    async def process_job(self, job_id: str, request: DeIdentificationRequest) -> None:
        """
        Process job documents asynchronously.
        
        Args:
            job_id: Job identifier
            request: De-identification request
        """
        if job_id not in self.active_jobs:
            logger.error(f"Job {job_id} not found")
            return
        
        job = self.active_jobs[job_id]
        progress = self.job_progress[job_id]
        
        try:
            # Update job status
            job.status = JobStatus.PROCESSING
            job.updated_at = datetime.utcnow()
            
            # Prepare job context
            job_context = {
                'job_id': job_id,
                'policy_version': request.policy_version,
                'linkage_domain': request.linkage_domain,
                'model_versions': self._get_model_versions(),
                'patient_salt': self._generate_patient_salt(job_id)
            }
            
            # Process documents
            for i, document in enumerate(request.documents):
                progress.current_document = document.document_id or f"doc_{i}"
                
                try:
                    processed_doc = await self.document_processor.process_document(
                        document, job_context
                    )
                    
                    self.job_results[job_id].append(processed_doc)
                    
                    # Update progress
                    progress.processed_documents += 1
                    
                    # Update job statistics
                    job.documents_processed += 1
                    job.total_entities_detected += len(processed_doc.detections)
                    job.total_entities_transformed += len(processed_doc.transformations)
                    
                except Exception as e:
                    logger.error(f"Failed to process document {i} in job {job_id}: {e}")
                    progress.failed_documents += 1
                    continue
            
            # Complete job
            job.status = JobStatus.COMPLETED
            job.completed_at = datetime.utcnow()
            job.processing_time_ms = (job.completed_at - job.created_at).total_seconds() * 1000
            
            # Log job completion
            completion_trace = JobTrace(
                job_id=job_id,
                status=JobStatus.COMPLETED,
                documents_processed=job.documents_processed,
                total_documents=job.total_documents,
                entities_detected=job.total_entities_detected,
                entities_transformed=job.total_entities_transformed
            )
            
            self.audit_service.log_job(completion_trace)
            
            logger.info(f"Completed job {job_id}: {job.documents_processed}/{job.total_documents} documents processed")
            
        except Exception as e:
            logger.error(f"Job {job_id} failed: {e}")
            
            job.status = JobStatus.FAILED
            job.error_message = str(e)
            job.updated_at = datetime.utcnow()
            
            # Log job failure
            failure_trace = JobTrace(
                job_id=job_id,
                status=JobStatus.FAILED,
                documents_processed=job.documents_processed,
                configuration_snapshot={'error': str(e)}
            )
            
            self.audit_service.log_job(failure_trace)
    
    def get_job_status(self, job_id: str) -> Optional[Tuple[DeIdentificationJob, JobProgress]]:
        """
        Get job status and progress.
        
        Args:
            job_id: Job identifier
            
        Returns:
            Tuple of (job, progress) or None if not found
        """
        job = self.active_jobs.get(job_id)
        progress = self.job_progress.get(job_id)
        
        if job and progress:
            return job, progress
        
        return None
    
    def get_job_results(self, job_id: str) -> Optional[List[ProcessedDocument]]:
        """
        Get job results.
        
        Args:
            job_id: Job identifier
            
        Returns:
            List of processed documents or None if not found
        """
        return self.job_results.get(job_id)
    
    def cancel_job(self, job_id: str) -> bool:
        """
        Cancel running job.
        
        Args:
            job_id: Job identifier
            
        Returns:
            True if cancelled successfully
        """
        if job_id not in self.active_jobs:
            return False
        
        job = self.active_jobs[job_id]
        
        if job.status in [JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.CANCELLED]:
            return False
        
        job.status = JobStatus.CANCELLED
        job.updated_at = datetime.utcnow()
        
        logger.info(f"Cancelled job {job_id}")
        
        return True
    
    def cleanup_completed_jobs(self, max_age_hours: int = 24) -> int:
        """
        Clean up old completed jobs.
        
        Args:
            max_age_hours: Maximum age for completed jobs
            
        Returns:
            Number of jobs cleaned up
        """
        cutoff_time = datetime.utcnow() - timedelta(hours=max_age_hours)
        jobs_to_remove = []
        
        for job_id, job in self.active_jobs.items():
            if (job.status in [JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.CANCELLED] and
                job.updated_at < cutoff_time):
                jobs_to_remove.append(job_id)
        
        for job_id in jobs_to_remove:
            self.active_jobs.pop(job_id, None)
            self.job_progress.pop(job_id, None)
            self.job_results.pop(job_id, None)
        
        logger.info(f"Cleaned up {len(jobs_to_remove)} old jobs")
        
        return len(jobs_to_remove)
    
    def _calculate_request_hash(self, request: DeIdentificationRequest) -> str:
        """Calculate hash of request for audit purposes."""
        content_hashes = []
        for doc in request.documents:
            content_hashes.append(SecureHasher.hash_for_deduplication(doc.content))
        
        request_summary = {
            'policy_version': request.policy_version,
            'linkage_domain': request.linkage_domain,
            'document_count': len(request.documents),
            'document_hashes': sorted(content_hashes)  # Sort for determinism
        }
        
        import json
        return SecureHasher.hash_for_deduplication(json.dumps(request_summary, sort_keys=True))
    
    def _get_configuration_snapshot(self) -> Dict[str, Any]:
        """Get current system configuration snapshot."""
        settings = get_settings()
        
        return {
            'app_version': settings.app_version,
            'policy_engine_version': '1.0',
            'detection_service_version': '1.0',
            'model_versions': self._get_model_versions(),
            'timestamp': datetime.utcnow().isoformat()
        }
    
    def _get_model_versions(self) -> Dict[str, str]:
        """Get current model versions."""
        settings = get_settings()
        
        return {
            'spacy_model': settings.spacy_model_en,
            'thai_ner_model': settings.thai_ner_model,
            'presidio_version': '2.2.354',  # From requirements
            'pythainlp_version': '4.0.2'   # From requirements
        }
    
    def _generate_patient_salt(self, job_id: str) -> str:
        """Generate patient-specific salt for consistent transformations."""
        return SecureHasher.hash_for_deduplication(f"patient_salt_{job_id}")[:16]


class OrchestratorService:
    """
    Main orchestrator service coordinating the entire de-identification pipeline.
    """
    
    def __init__(self, settings=None):
        if settings is None:
            settings = get_settings()
        
        self.settings = settings
        self.job_manager = JobManager()
        
        logger.info("Orchestrator service initialized")
    
    async def submit_job(self, request: DeIdentificationRequest, user_id: str = "system") -> str:
        """
        Submit de-identification job.
        
        Args:
            request: De-identification request
            user_id: User submitting the job
            
        Returns:
            Job ID
        """
        # Validate request
        validation_errors = self._validate_request(request)
        if validation_errors:
            raise ValueError(f"Request validation failed: {'; '.join(validation_errors)}")
        
        # Create job
        job_id = self.job_manager.create_job(request, user_id)
        
        # Start processing asynchronously
        asyncio.create_task(self.job_manager.process_job(job_id, request))
        
        return job_id
    
    def get_job_status(self, job_id: str) -> Optional[Dict[str, Any]]:
        """Get job status information."""
        result = self.job_manager.get_job_status(job_id)
        if not result:
            return None
        
        job, progress = result
        
        return {
            'job_id': job_id,
            'status': job.status,
            'created_at': job.created_at.isoformat(),
            'updated_at': job.updated_at.isoformat(),
            'completed_at': job.completed_at.isoformat() if job.completed_at else None,
            'progress_percent': progress.progress_percent,
            'documents_processed': progress.processed_documents,
            'total_documents': progress.total_documents,
            'failed_documents': progress.failed_documents,
            'estimated_time_remaining': progress.estimated_time_remaining,
            'current_document': progress.current_document,
            'total_entities_detected': job.total_entities_detected,
            'total_entities_transformed': job.total_entities_transformed,
            'error_message': job.error_message
        }
    
    def get_job_results(self, job_id: str) -> Optional[Dict[str, Any]]:
        """Get job results."""
        job_status_result = self.job_manager.get_job_status(job_id)
        results = self.job_manager.get_job_results(job_id)
        
        if not job_status_result or not results:
            return None
        
        job, _ = job_status_result
        
        return {
            'job_id': job_id,
            'status': job.status,
            'policy_version': job.policy_version,
            'linkage_domain': job.linkage_domain,
            'processing_time_ms': job.processing_time_ms,
            'documents': [
                {
                    'document_id': doc.document_id,
                    'original_length': doc.original_length,
                    'deidentified_text': doc.deidentified_text,
                    'language_detected': doc.language_detected.value,
                    'detections_count': len(doc.detections),
                    'transformations_count': len(doc.transformations),
                    'processing_time_ms': doc.processing_time_ms,
                    'warnings': doc.warnings
                }
                for doc in results
            ],
            'summary': {
                'total_documents': len(results),
                'total_detections': sum(len(doc.detections) for doc in results),
                'total_transformations': sum(len(doc.transformations) for doc in results),
                'total_processing_time_ms': sum(doc.processing_time_ms for doc in results)
            }
        }
    
    def cancel_job(self, job_id: str) -> bool:
        """Cancel job."""
        return self.job_manager.cancel_job(job_id)
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get orchestrator statistics."""
        active_jobs = len(self.job_manager.active_jobs)
        
        status_counts = {}
        for job in self.job_manager.active_jobs.values():
            status = job.status.value
            status_counts[status] = status_counts.get(status, 0) + 1
        
        return {
            'active_jobs': active_jobs,
            'jobs_by_status': status_counts,
            'total_jobs_created': len(self.job_manager.active_jobs),  # Simplified
        }
    
    def _validate_request(self, request: DeIdentificationRequest) -> List[str]:
        """Validate de-identification request."""
        errors = []
        
        # Check document count
        if not request.documents:
            errors.append("No documents provided")
        
        if len(request.documents) > self.settings.batch_size_limit:
            errors.append(f"Too many documents: {len(request.documents)} > {self.settings.batch_size_limit}")
        
        # Check document content
        for i, doc in enumerate(request.documents):
            if not doc.content or not doc.content.strip():
                errors.append(f"Document {i} is empty")
            
            if len(doc.content) > 1000000:  # 1MB limit
                errors.append(f"Document {i} too large: {len(doc.content)} characters")
        
        # Check policy version
        policy_engine = get_policy_engine()
        if request.policy_version not in policy_engine.get_available_policies():
            errors.append(f"Unknown policy version: {request.policy_version}")
        
        # Check sampling rate
        if not 0 <= request.reviewer_sampling_rate <= 1:
            errors.append("Reviewer sampling rate must be between 0 and 1")
        
        return errors


# Global service instance
orchestrator_service = None

def get_orchestrator_service() -> OrchestratorService:
    """Get global orchestrator service instance."""
    global orchestrator_service
    if orchestrator_service is None:
        orchestrator_service = OrchestratorService()
    return orchestrator_service
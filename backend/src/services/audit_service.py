"""
Audit and trace logging service for comprehensive de-identification traceability.
Provides immutable, queryable audit trails for compliance and quality assurance.
"""
import json
import logging
import uuid
from datetime import datetime
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, asdict
from pathlib import Path
import threading

from models.schemas import (
    DetectionTrace, TransformationTrace, DetectionResult, 
    TransformationResult, EntityType, JobStatus
)
from utils.config import get_settings
from security.crypto import SecureHasher

logger = logging.getLogger(__name__)


@dataclass
class JobTrace:
    """Comprehensive job trace record."""
    job_id: str
    trace_id: str = None
    status: JobStatus = JobStatus.PENDING
    created_at: datetime = None
    updated_at: datetime = None
    
    # Configuration
    policy_version: str = ""
    linkage_domain: str = ""
    model_versions: Dict[str, str] = None
    
    # Statistics
    documents_processed: int = 0
    total_documents: int = 0
    entities_detected: int = 0
    entities_transformed: int = 0
    
    # Metadata
    user_id: str = ""
    input_hash: str = ""
    configuration_snapshot: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.trace_id is None:
            self.trace_id = str(uuid.uuid4())
        if self.created_at is None:
            self.created_at = datetime.utcnow()
        if self.updated_at is None:
            self.updated_at = datetime.utcnow()
        if self.model_versions is None:
            self.model_versions = {}
        if self.configuration_snapshot is None:
            self.configuration_snapshot = {}


@dataclass
class AuditQuery:
    """Query parameters for audit log search."""
    job_id: Optional[str] = None
    entity_type: Optional[EntityType] = None
    detector_type: Optional[str] = None
    date_from: Optional[datetime] = None
    date_to: Optional[datetime] = None
    confidence_min: Optional[float] = None
    confidence_max: Optional[float] = None
    limit: int = 1000
    offset: int = 0


class ImmutableLogStore:
    """
    Immutable log storage backend with write-once semantics.
    In production, this would be backed by tamper-evident storage.
    """
    
    def __init__(self, storage_path: str = "logs/audit"):
        self.storage_path = Path(storage_path)
        self.storage_path.mkdir(parents=True, exist_ok=True)
        
        # File locks for thread safety
        self._locks = {}
        self._global_lock = threading.Lock()
        
        logger.info(f"Initialized immutable log store at: {self.storage_path}")
    
    def _get_file_lock(self, file_path: str) -> threading.Lock:
        """Get or create file-specific lock."""
        with self._global_lock:
            if file_path not in self._locks:
                self._locks[file_path] = threading.Lock()
            return self._locks[file_path]
    
    def write_record(self, record_type: str, record_id: str, data: Dict[str, Any]) -> bool:
        """
        Write immutable record to storage.
        
        Args:
            record_type: Type of record ('detection', 'transformation', 'job')
            record_id: Unique record identifier
            data: Record data
            
        Returns:
            True if write successful
        """
        try:
            # Create directory structure by date
            date_str = datetime.utcnow().strftime("%Y-%m-%d")
            dir_path = self.storage_path / record_type / date_str
            dir_path.mkdir(parents=True, exist_ok=True)
            
            # File name with timestamp and ID
            timestamp = datetime.utcnow().strftime("%H%M%S")
            file_name = f"{timestamp}_{record_id}.json"
            file_path = dir_path / file_name
            
            # Prepare record with integrity hash
            record = {
                'id': record_id,
                'type': record_type,
                'timestamp': datetime.utcnow().isoformat(),
                'data': data,
                'integrity_hash': self._calculate_integrity_hash(data)
            }
            
            # Write with file lock
            lock = self._get_file_lock(str(file_path))
            with lock:
                if file_path.exists():
                    logger.warning(f"Record {record_id} already exists - immutable storage violation")
                    return False
                
                with open(file_path, 'w', encoding='utf-8') as f:
                    json.dump(record, f, indent=2, default=str, ensure_ascii=False)
            
            logger.debug(f"Wrote immutable record: {record_type}/{record_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to write immutable record {record_id}: {e}")
            return False
    
    def read_records(
        self, 
        record_type: str, 
        query: AuditQuery
    ) -> List[Dict[str, Any]]:
        """
        Read records matching query criteria.
        
        Args:
            record_type: Type of records to read
            query: Query parameters
            
        Returns:
            List of matching records
        """
        try:
            records = []
            base_path = self.storage_path / record_type
            
            if not base_path.exists():
                return records
            
            # Collect files to scan
            files_to_scan = []
            
            if query.date_from or query.date_to:
                # Scan specific date ranges
                for date_dir in base_path.iterdir():
                    if date_dir.is_dir():
                        try:
                            dir_date = datetime.strptime(date_dir.name, "%Y-%m-%d")
                            
                            include_dir = True
                            if query.date_from and dir_date < query.date_from.replace(hour=0, minute=0, second=0):
                                include_dir = False
                            if query.date_to and dir_date > query.date_to.replace(hour=23, minute=59, second=59):
                                include_dir = False
                            
                            if include_dir:
                                files_to_scan.extend(date_dir.glob("*.json"))
                        except ValueError:
                            continue
            else:
                # Scan all files
                files_to_scan = list(base_path.rglob("*.json"))
            
            # Read and filter records
            for file_path in files_to_scan:
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        record = json.load(f)
                    
                    # Verify integrity
                    if not self._verify_integrity(record):
                        logger.warning(f"Integrity check failed for {file_path}")
                        continue
                    
                    # Apply filters
                    if self._matches_query(record, query):
                        records.append(record)
                        
                        # Apply limit
                        if len(records) >= query.limit + query.offset:
                            break
                            
                except Exception as e:
                    logger.error(f"Failed to read record {file_path}: {e}")
                    continue
            
            # Apply offset and limit
            return records[query.offset:query.offset + query.limit]
            
        except Exception as e:
            logger.error(f"Failed to read records: {e}")
            return []
    
    def _calculate_integrity_hash(self, data: Dict[str, Any]) -> str:
        """Calculate integrity hash for record."""
        # Create deterministic JSON representation
        json_str = json.dumps(data, sort_keys=True, default=str)
        return SecureHasher.hash_for_deduplication(json_str)
    
    def _verify_integrity(self, record: Dict[str, Any]) -> bool:
        """Verify record integrity."""
        if 'integrity_hash' not in record:
            return True  # Legacy records without hash
        
        expected_hash = self._calculate_integrity_hash(record.get('data', {}))
        return expected_hash == record['integrity_hash']
    
    def _matches_query(self, record: Dict[str, Any], query: AuditQuery) -> bool:
        """Check if record matches query criteria."""
        data = record.get('data', {})
        
        # Job ID filter
        if query.job_id and data.get('job_id') != query.job_id:
            return False
        
        # Entity type filter
        if query.entity_type and data.get('entity_type') != query.entity_type.value:
            return False
        
        # Detector type filter
        if query.detector_type and data.get('detector_type') != query.detector_type:
            return False
        
        # Confidence filters
        if query.confidence_min is not None:
            confidence = data.get('confidence')
            if confidence is None or confidence < query.confidence_min:
                return False
        
        if query.confidence_max is not None:
            confidence = data.get('confidence')
            if confidence is None or confidence > query.confidence_max:
                return False
        
        # Date filters
        record_time = datetime.fromisoformat(record.get('timestamp', ''))
        
        if query.date_from and record_time < query.date_from:
            return False
        
        if query.date_to and record_time > query.date_to:
            return False
        
        return True


class AuditService:
    """
    Main audit service for comprehensive traceability.
    """
    
    def __init__(self, settings=None):
        if settings is None:
            settings = get_settings()
        
        self.settings = settings
        self.log_store = ImmutableLogStore(settings.log_storage_backend)
        
        # Statistics
        self.stats = {
            'detection_traces': 0,
            'transformation_traces': 0,
            'job_traces': 0,
            'integrity_violations': 0
        }
        
        logger.info("Audit service initialized")
    
    def log_detection(
        self,
        job_id: str,
        document_id: str,
        detection: DetectionResult,
        model_versions: Dict[str, str]
    ) -> str:
        """
        Log entity detection event.
        
        Args:
            job_id: Job identifier
            document_id: Document identifier
            detection: Detection result
            model_versions: Model version information
            
        Returns:
            Trace ID
        """
        trace = DetectionTrace(
            job_id=job_id,
            document_id=document_id,
            span_start=detection.start,
            span_end=detection.end,
            text_hash=SecureHasher.hash_for_deduplication(detection.text),
            entity_type=detection.entity_type,
            detector_type=detection.detector_type,
            detector_version=detection.detector_version,
            confidence=detection.confidence,
            rule_id=detection.rule_id,
            model_versions=model_versions
        )
        
        # Store in immutable log
        success = self.log_store.write_record(
            'detection',
            trace.trace_id,
            asdict(trace)
        )
        
        if success:
            self.stats['detection_traces'] += 1
        else:
            self.stats['integrity_violations'] += 1
        
        return trace.trace_id
    
    def log_transformation(
        self,
        job_id: str,
        document_id: str,
        detection_trace_id: str,
        transformation: TransformationResult,
        key_version: Optional[str] = None
    ) -> str:
        """
        Log entity transformation event.
        
        Args:
            job_id: Job identifier
            document_id: Document identifier
            detection_trace_id: Related detection trace ID
            transformation: Transformation result
            key_version: Cryptographic key version (if applicable)
            
        Returns:
            Trace ID
        """
        trace = TransformationTrace(
            job_id=job_id,
            document_id=document_id,
            detection_trace_id=detection_trace_id,
            entity_type=transformation.entity_type,
            transformation_type=transformation.transformation,
            policy_rule_id=transformation.policy_id,
            parameters=transformation.parameters,
            output_span_start=transformation.original_start,
            output_span_end=transformation.original_end,
            output_text=transformation.transformed_text,
            key_version=key_version
        )
        
        # Store in immutable log
        success = self.log_store.write_record(
            'transformation',
            trace.trace_id,
            asdict(trace)
        )
        
        if success:
            self.stats['transformation_traces'] += 1
        else:
            self.stats['integrity_violations'] += 1
        
        return trace.trace_id
    
    def log_job(self, job_trace: JobTrace) -> bool:
        """
        Log job-level event.
        
        Args:
            job_trace: Job trace record
            
        Returns:
            True if logged successfully
        """
        success = self.log_store.write_record(
            'job',
            job_trace.trace_id,
            asdict(job_trace)
        )
        
        if success:
            self.stats['job_traces'] += 1
        else:
            self.stats['integrity_violations'] += 1
        
        return success
    
    def query_detection_traces(self, query: AuditQuery) -> List[DetectionTrace]:
        """
        Query detection traces.
        
        Args:
            query: Query parameters
            
        Returns:
            List of matching detection traces
        """
        records = self.log_store.read_records('detection', query)
        
        traces = []
        for record in records:
            try:
                data = record['data']
                trace = DetectionTrace(
                    trace_id=data['trace_id'],
                    job_id=data['job_id'],
                    document_id=data['document_id'],
                    span_start=data['span_start'],
                    span_end=data['span_end'],
                    text_hash=data['text_hash'],
                    entity_type=EntityType(data['entity_type']),
                    detector_type=data['detector_type'],
                    detector_version=data['detector_version'],
                    confidence=data['confidence'],
                    rule_id=data.get('rule_id'),
                    timestamp=datetime.fromisoformat(data['timestamp']),
                    model_versions=data.get('model_versions', {})
                )
                traces.append(trace)
            except Exception as e:
                logger.error(f"Failed to parse detection trace: {e}")
                continue
        
        return traces
    
    def query_transformation_traces(self, query: AuditQuery) -> List[TransformationTrace]:
        """
        Query transformation traces.
        
        Args:
            query: Query parameters
            
        Returns:
            List of matching transformation traces
        """
        records = self.log_store.read_records('transformation', query)
        
        traces = []
        for record in records:
            try:
                data = record['data']
                trace = TransformationTrace(
                    trace_id=data['trace_id'],
                    job_id=data['job_id'],
                    document_id=data['document_id'],
                    detection_trace_id=data['detection_trace_id'],
                    entity_type=EntityType(data['entity_type']),
                    transformation_type=data['transformation_type'],
                    policy_rule_id=data['policy_rule_id'],
                    parameters=data.get('parameters', {}),
                    output_span_start=data['output_span_start'],
                    output_span_end=data['output_span_end'],
                    output_text=data['output_text'],
                    timestamp=datetime.fromisoformat(data['timestamp']),
                    key_version=data.get('key_version')
                )
                traces.append(trace)
            except Exception as e:
                logger.error(f"Failed to parse transformation trace: {e}")
                continue
        
        return traces
    
    def export_evidence_bundle(
        self,
        job_id: str,
        include_sensitive: bool = False
    ) -> Dict[str, Any]:
        """
        Export complete evidence bundle for a job.
        
        Args:
            job_id: Job identifier
            include_sensitive: Whether to include sensitive data
            
        Returns:
            Evidence bundle dictionary
        """
        query = AuditQuery(job_id=job_id, limit=10000)
        
        detection_traces = self.query_detection_traces(query)
        transformation_traces = self.query_transformation_traces(query)
        
        # Get job traces
        job_records = self.log_store.read_records('job', query)
        
        evidence_bundle = {
            'job_id': job_id,
            'export_timestamp': datetime.utcnow().isoformat(),
            'export_version': '1.0',
            'detection_traces': [asdict(trace) for trace in detection_traces],
            'transformation_traces': [asdict(trace) for trace in transformation_traces],
            'job_records': job_records,
            'statistics': {
                'total_detections': len(detection_traces),
                'total_transformations': len(transformation_traces),
                'entity_type_counts': self._count_by_entity_type(detection_traces),
                'detector_type_counts': self._count_by_detector_type(detection_traces)
            }
        }
        
        # Remove sensitive data if requested
        if not include_sensitive:
            evidence_bundle = self._sanitize_evidence_bundle(evidence_bundle)
        
        return evidence_bundle
    
    def _count_by_entity_type(self, traces: List[DetectionTrace]) -> Dict[str, int]:
        """Count traces by entity type."""
        counts = {}
        for trace in traces:
            entity_type = trace.entity_type.value
            counts[entity_type] = counts.get(entity_type, 0) + 1
        return counts
    
    def _count_by_detector_type(self, traces: List[DetectionTrace]) -> Dict[str, int]:
        """Count traces by detector type."""
        counts = {}
        for trace in traces:
            detector_type = trace.detector_type.value
            counts[detector_type] = counts.get(detector_type, 0) + 1
        return counts
    
    def _sanitize_evidence_bundle(self, bundle: Dict[str, Any]) -> Dict[str, Any]:
        """Remove sensitive information from evidence bundle."""
        # Remove text hashes and other potentially sensitive fields
        sanitized = bundle.copy()
        
        for trace in sanitized.get('detection_traces', []):
            trace.pop('text_hash', None)
        
        for trace in sanitized.get('transformation_traces', []):
            trace.pop('output_text', None)
        
        return sanitized
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get audit service statistics."""
        return {
            **self.stats,
            'storage_path': str(self.log_store.storage_path),
            'immutable_logs_enabled': self.settings.enable_immutable_logs,
            'retention_days': self.settings.audit_log_retention_days
        }
    
    def cleanup_expired_logs(self, retention_days: int = None) -> int:
        """
        Clean up expired audit logs.
        
        Args:
            retention_days: Retention period (uses config default if None)
            
        Returns:
            Number of files cleaned up
        """
        if retention_days is None:
            retention_days = self.settings.audit_log_retention_days
        
        cutoff_date = datetime.utcnow() - timedelta(days=retention_days)
        cleaned_count = 0
        
        # This is a simplified implementation
        # In production, would need proper retention policies
        
        logger.info(f"Log cleanup not implemented (retention: {retention_days} days)")
        
        return cleaned_count


# Global service instance
audit_service = None

def get_audit_service() -> AuditService:
    """Get global audit service instance."""
    global audit_service
    if audit_service is None:
        audit_service = AuditService()
    return audit_service
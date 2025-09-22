"""
Pseudonymization service implementing deterministic pseudonyms with HKDF/HMAC.
Provides secure, consistent, and auditable pseudonym generation.
"""
import logging
from datetime import datetime
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, asdict
import json

from security.crypto import PseudonymGenerator, KeyRotationManager
from models.schemas import (
    EntityType, PseudonymRequest, PseudonymResult, 
    TransformationType, TransformationResult
)
from utils.config import get_settings

logger = logging.getLogger(__name__)


@dataclass
class PseudonymMapping:
    """Optional mapping record for re-identification (if enabled by policy)."""
    pseudonym: str
    original_hash: str  # SHA-256 hash of original, not plaintext
    entity_type: EntityType
    linkage_domain: str
    key_version: str
    created_at: datetime
    tenant_id: str = "default"


class PseudonymMappingStore:
    """
    Secure storage for pseudonym mappings (when enabled by policy).
    In production, this would be backed by encrypted database or HSM.
    """
    
    def __init__(self, enable_mapping: bool = False):
        self.enable_mapping = enable_mapping
        self.mappings: Dict[str, PseudonymMapping] = {}  # pseudonym -> mapping
        self.reverse_mappings: Dict[str, str] = {}  # hash -> pseudonym
        
        if not enable_mapping:
            logger.info("Pseudonym mapping storage disabled for privacy")
        else:
            logger.warning("Pseudonym mapping storage enabled - ensure proper security controls")
    
    def store_mapping(self, mapping: PseudonymMapping) -> None:
        """Store pseudonym mapping if enabled."""
        if not self.enable_mapping:
            return
        
        self.mappings[mapping.pseudonym] = mapping
        self.reverse_mappings[mapping.original_hash] = mapping.pseudonym
        
        logger.debug(f"Stored mapping for entity type {mapping.entity_type}")
    
    def get_mapping(self, pseudonym: str) -> Optional[PseudonymMapping]:
        """Get mapping by pseudonym."""
        if not self.enable_mapping:
            return None
        
        return self.mappings.get(pseudonym)
    
    def find_by_hash(self, original_hash: str) -> Optional[str]:
        """Find pseudonym by original hash."""
        if not self.enable_mapping:
            return None
        
        return self.reverse_mappings.get(original_hash)
    
    def list_mappings(
        self, 
        entity_type: Optional[EntityType] = None,
        linkage_domain: Optional[str] = None
    ) -> List[PseudonymMapping]:
        """List mappings with optional filtering."""
        if not self.enable_mapping:
            return []
        
        mappings = list(self.mappings.values())
        
        if entity_type:
            mappings = [m for m in mappings if m.entity_type == entity_type]
        
        if linkage_domain:
            mappings = [m for m in mappings if m.linkage_domain == linkage_domain]
        
        return mappings
    
    def cleanup_expired(self, retention_days: int = 2555) -> int:
        """Clean up expired mappings."""
        if not self.enable_mapping:
            return 0
        
        cutoff = datetime.utcnow().timestamp() - (retention_days * 24 * 3600)
        expired_pseudonyms = []
        
        for pseudonym, mapping in self.mappings.items():
            if mapping.created_at.timestamp() < cutoff:
                expired_pseudonyms.append(pseudonym)
        
        for pseudonym in expired_pseudonyms:
            mapping = self.mappings.pop(pseudonym)
            self.reverse_mappings.pop(mapping.original_hash, None)
        
        logger.info(f"Cleaned up {len(expired_pseudonyms)} expired mappings")
        return len(expired_pseudonyms)


class PseudonymizationService:
    """
    Main pseudonymization service providing deterministic, secure pseudonyms.
    """
    
    def __init__(self, settings=None):
        if settings is None:
            settings = get_settings()
        
        self.settings = settings
        
        # Initialize key management
        self.key_manager = KeyRotationManager()
        self.key_manager.register_key("v1.0", settings.master_secret_key)
        
        # Initialize mapping store
        self.mapping_store = PseudonymMappingStore(
            enable_mapping=settings.enable_pseudonym_mapping
        )
        
        # Statistics
        self.stats = {
            'pseudonyms_generated': 0,
            'cache_hits': 0,
            'key_rotations': 0
        }
        
        logger.info(f"Pseudonymization service initialized (mapping: {settings.enable_pseudonym_mapping})")
    
    def generate_pseudonym(self, request: PseudonymRequest) -> PseudonymResult:
        """
        Generate deterministic pseudonym for identifier.
        
        Args:
            request: Pseudonym generation request
            
        Returns:
            PseudonymResult with generated pseudonym
        """
        try:
            # Get active pseudonym generator
            generator = self.key_manager.get_pseudonym_generator()
            
            # Generate pseudonym
            pseudonym = generator.generate_pseudonym(
                original_identifier=request.original_identifier,
                linkage_domain=request.linkage_domain,
                tenant_id="default",  # TODO: Multi-tenancy support
                length=self.settings.pseudonym_length
            )
            
            # Create result
            result = PseudonymResult(
                pseudonym=pseudonym,
                linkage_domain=request.linkage_domain,
                entity_type=request.entity_type,
                key_version=generator.key_version
            )
            
            # Optionally store mapping
            if self.settings.enable_pseudonym_mapping:
                from security.crypto import SecureHasher
                
                original_hash = SecureHasher.hash_for_deduplication(request.original_identifier)
                
                mapping = PseudonymMapping(
                    pseudonym=pseudonym,
                    original_hash=original_hash,
                    entity_type=request.entity_type,
                    linkage_domain=request.linkage_domain,
                    key_version=generator.key_version,
                    created_at=datetime.utcnow()
                )
                
                self.mapping_store.store_mapping(mapping)
            
            # Update statistics
            self.stats['pseudonyms_generated'] += 1
            
            logger.debug(f"Generated pseudonym for {request.entity_type} in domain {request.linkage_domain}")
            
            return result
            
        except Exception as e:
            logger.error(f"Pseudonym generation failed: {e}")
            raise
    
    def batch_pseudonymize(self, requests: List[PseudonymRequest]) -> List[PseudonymResult]:
        """
        Generate pseudonyms for multiple identifiers efficiently.
        
        Args:
            requests: List of pseudonym requests
            
        Returns:
            List of pseudonym results
        """
        results = []
        
        for request in requests:
            try:
                result = self.generate_pseudonym(request)
                results.append(result)
            except Exception as e:
                logger.error(f"Failed to generate pseudonym for {request.entity_type}: {e}")
                # Continue with other requests
                continue
        
        logger.info(f"Batch pseudonymized {len(results)}/{len(requests)} identifiers")
        
        return results
    
    def verify_pseudonym(
        self, 
        original_identifier: str, 
        pseudonym: str, 
        linkage_domain: str,
        entity_type: EntityType
    ) -> bool:
        """
        Verify that pseudonym was generated from original identifier.
        
        Args:
            original_identifier: Original identifier
            pseudonym: Claimed pseudonym
            linkage_domain: Context domain
            entity_type: Entity type
            
        Returns:
            True if pseudonym is valid
        """
        try:
            generator = self.key_manager.get_pseudonym_generator()
            return generator.verify_pseudonym(
                original_identifier, pseudonym, linkage_domain
            )
        except Exception as e:
            logger.error(f"Pseudonym verification failed: {e}")
            return False
    
    def create_transformation_result(
        self,
        original_text: str,
        start: int,
        end: int,
        entity_type: EntityType,
        linkage_domain: str,
        policy_id: str = "default"
    ) -> TransformationResult:
        """
        Create transformation result for pseudonymization.
        
        Args:
            original_text: Original text span
            start: Start position
            end: End position
            entity_type: Type of entity
            linkage_domain: Linkage domain for pseudonym
            policy_id: Policy rule ID
            
        Returns:
            TransformationResult with pseudonym
        """
        from security.crypto import SecureHasher
        
        # Generate pseudonym
        request = PseudonymRequest(
            original_identifier=original_text,
            entity_type=entity_type,
            linkage_domain=linkage_domain
        )
        
        result = self.generate_pseudonym(request)
        
        # Create transformation result
        return TransformationResult(
            original_start=start,
            original_end=end,
            original_text_hash=SecureHasher.hash_for_deduplication(original_text),
            transformed_text=result.pseudonym,
            transformation=TransformationType.PSEUDONYMIZE,
            entity_type=entity_type,
            policy_id=policy_id,
            parameters={
                'linkage_domain': linkage_domain,
                'key_version': result.key_version,
                'pseudonym_length': len(result.pseudonym)
            }
        )
    
    def get_linkage_consistency(
        self, 
        identifiers: List[str], 
        linkage_domain: str
    ) -> Dict[str, str]:
        """
        Get consistent pseudonyms for multiple related identifiers.
        
        Args:
            identifiers: List of identifiers to pseudonymize
            linkage_domain: Common linkage domain
            
        Returns:
            Dictionary mapping original identifiers to pseudonyms
        """
        mapping = {}
        
        for identifier in identifiers:
            request = PseudonymRequest(
                original_identifier=identifier,
                entity_type=EntityType.PERSON,  # Default type
                linkage_domain=linkage_domain
            )
            
            result = self.generate_pseudonym(request)
            mapping[identifier] = result.pseudonym
        
        return mapping
    
    def rotate_keys(self, new_master_secret: str) -> str:
        """
        Rotate pseudonymization keys.
        
        Args:
            new_master_secret: New master secret
            
        Returns:
            New key version
        """
        new_version = self.key_manager.rotate_keys(new_master_secret)
        self.stats['key_rotations'] += 1
        
        logger.info(f"Keys rotated to version {new_version}")
        
        return new_version
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get service statistics."""
        mapping_stats = {
            'total_mappings': len(self.mapping_store.mappings),
            'mapping_enabled': self.mapping_store.enable_mapping
        }
        
        return {
            **self.stats,
            **mapping_stats,
            'active_key_version': self.key_manager.active_version,
            'available_key_versions': list(self.key_manager.key_registry.keys())
        }
    
    def export_mappings(
        self, 
        linkage_domain: Optional[str] = None,
        entity_type: Optional[EntityType] = None
    ) -> List[Dict[str, Any]]:
        """
        Export pseudonym mappings for audit or migration.
        
        Args:
            linkage_domain: Optional domain filter
            entity_type: Optional entity type filter
            
        Returns:
            List of mapping records (without original identifiers)
        """
        if not self.mapping_store.enable_mapping:
            logger.warning("Mapping export requested but mapping is disabled")
            return []
        
        mappings = self.mapping_store.list_mappings(entity_type, linkage_domain)
        
        # Convert to serializable format (no original data)
        export_data = []
        for mapping in mappings:
            export_record = {
                'pseudonym': mapping.pseudonym,
                'original_hash': mapping.original_hash,
                'entity_type': mapping.entity_type.value,
                'linkage_domain': mapping.linkage_domain,
                'key_version': mapping.key_version,
                'created_at': mapping.created_at.isoformat(),
                'tenant_id': mapping.tenant_id
            }
            export_data.append(export_record)
        
        logger.info(f"Exported {len(export_data)} pseudonym mappings")
        
        return export_data
    
    def cleanup_expired_mappings(self, retention_days: int = None) -> int:
        """
        Clean up expired pseudonym mappings.
        
        Args:
            retention_days: Retention period (uses config default if None)
            
        Returns:
            Number of mappings cleaned up
        """
        if retention_days is None:
            retention_days = self.settings.audit_log_retention_days
        
        return self.mapping_store.cleanup_expired(retention_days)


class ConsistencyManager:
    """
    Manages consistency of pseudonyms across documents and sessions.
    """
    
    def __init__(self, pseudonym_service: PseudonymizationService):
        self.pseudonym_service = pseudonym_service
        
        # Session cache for within-document consistency
        self.session_cache: Dict[str, Dict[str, str]] = {}  # session_id -> {original: pseudonym}
    
    def get_consistent_pseudonym(
        self,
        original_identifier: str,
        entity_type: EntityType,
        linkage_domain: str,
        session_id: str = "default"
    ) -> str:
        """
        Get consistent pseudonym for identifier within session.
        
        Args:
            original_identifier: Original identifier
            entity_type: Entity type
            linkage_domain: Linkage domain
            session_id: Session identifier for consistency
            
        Returns:
            Consistent pseudonym
        """
        # Check session cache first
        cache_key = f"{linkage_domain}:{original_identifier}"
        
        if session_id not in self.session_cache:
            self.session_cache[session_id] = {}
        
        session_mappings = self.session_cache[session_id]
        
        if cache_key in session_mappings:
            return session_mappings[cache_key]
        
        # Generate new pseudonym
        request = PseudonymRequest(
            original_identifier=original_identifier,
            entity_type=entity_type,
            linkage_domain=linkage_domain
        )
        
        result = self.pseudonym_service.generate_pseudonym(request)
        
        # Cache for session consistency
        session_mappings[cache_key] = result.pseudonym
        
        return result.pseudonym
    
    def clear_session(self, session_id: str) -> None:
        """Clear session cache."""
        self.session_cache.pop(session_id, None)
    
    def get_session_statistics(self, session_id: str) -> Dict[str, Any]:
        """Get statistics for session."""
        session_mappings = self.session_cache.get(session_id, {})
        
        return {
            'session_id': session_id,
            'cached_mappings': len(session_mappings),
            'unique_identifiers': len(set(k.split(':', 1)[1] for k in session_mappings.keys())),
            'linkage_domains': len(set(k.split(':', 1)[0] for k in session_mappings.keys()))
        }


# Global service instance
pseudonym_service = None

def get_pseudonym_service() -> PseudonymizationService:
    """Get global pseudonymization service instance."""
    global pseudonym_service
    if pseudonym_service is None:
        pseudonym_service = PseudonymizationService()
    return pseudonym_service
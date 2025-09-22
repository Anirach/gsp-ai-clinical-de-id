"""
Cryptographic utilities for secure pseudonymization and key management.
Implements HKDF key derivation and HMAC-based deterministic pseudonyms.
"""
import base64
import hashlib
import hmac
import secrets
from typing import Optional, Tuple
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.fernet import Fernet
import logging

logger = logging.getLogger(__name__)


class PseudonymGenerator:
    """
    Generates deterministic pseudonyms using HKDF key derivation and HMAC.
    
    Design:
    1. Master secret is stored securely (HSM/KMS in production)
    2. Context-specific keys derived using HKDF with linkage domain
    3. Pseudonyms generated using HMAC-SHA256 and Base32 encoding
    4. Collision resistance through sufficient entropy (≥128 bits)
    """
    
    def __init__(self, master_secret: str, default_length: int = 32):
        """
        Initialize pseudonym generator.
        
        Args:
            master_secret: Base64-encoded master secret (≥32 bytes recommended)
            default_length: Default pseudonym length in characters
        """
        self.master_secret = base64.b64decode(master_secret.encode())
        self.default_length = default_length
        self.key_version = "v1.0"  # For key rotation support
        
        if len(self.master_secret) < 32:
            logger.warning("Master secret should be at least 32 bytes for security")
    
    def derive_key(self, linkage_domain: str, tenant_id: str = "default") -> bytes:
        """
        Derive context-specific key using HKDF.
        
        Args:
            linkage_domain: Context identifier (e.g., "patient_id", "encounter_id")
            tenant_id: Tenant identifier for multi-tenancy
            
        Returns:
            Derived key bytes (32 bytes)
        """
        info = f"{linkage_domain}||{tenant_id}".encode('utf-8')
        
        hkdf = HKDF(
            algorithm=hashes.SHA256(),
            length=32,
            salt=b"clinical_deid_salt_v1",  # Fixed salt for determinism
            info=info,
        )
        
        return hkdf.derive(self.master_secret)
    
    def generate_pseudonym(
        self, 
        original_identifier: str, 
        linkage_domain: str,
        tenant_id: str = "default",
        length: Optional[int] = None
    ) -> str:
        """
        Generate deterministic pseudonym for identifier.
        
        Args:
            original_identifier: Original identifier to pseudonymize
            linkage_domain: Context for key derivation
            tenant_id: Tenant identifier
            length: Pseudonym length (uses default if None)
            
        Returns:
            Base32-encoded pseudonym string
        """
        if not original_identifier or not original_identifier.strip():
            raise ValueError("Original identifier cannot be empty")
        
        # Normalize identifier
        canonical_id = self._canonicalize_identifier(original_identifier)
        
        # Derive context-specific key
        derived_key = self.derive_key(linkage_domain, tenant_id)
        
        # Generate HMAC
        hmac_digest = hmac.new(
            derived_key, 
            canonical_id.encode('utf-8'), 
            hashlib.sha256
        ).digest()
        
        # Encode to Base32 and truncate
        pseudonym_length = length or self.default_length
        pseudonym = base64.b32encode(hmac_digest).decode('ascii')
        
        # Truncate to desired length (ensure minimum 128 bits = 26 chars)
        min_length = max(26, pseudonym_length)
        return pseudonym[:min_length].rstrip('=')
    
    def _canonicalize_identifier(self, identifier: str) -> str:
        """
        Canonicalize identifier for consistent pseudonym generation.
        
        Args:
            identifier: Raw identifier
            
        Returns:
            Canonicalized identifier
        """
        # Normalize case, whitespace, and common separators
        canonical = identifier.strip().upper()
        canonical = ''.join(c for c in canonical if c.isalnum())
        
        if not canonical:
            raise ValueError("Identifier contains no alphanumeric characters")
        
        return canonical
    
    def verify_pseudonym(
        self, 
        original_identifier: str, 
        pseudonym: str, 
        linkage_domain: str,
        tenant_id: str = "default"
    ) -> bool:
        """
        Verify that pseudonym was generated from original identifier.
        
        Args:
            original_identifier: Original identifier
            pseudonym: Claimed pseudonym
            linkage_domain: Context used for generation
            tenant_id: Tenant identifier
            
        Returns:
            True if pseudonym is valid for identifier
        """
        try:
            expected_pseudonym = self.generate_pseudonym(
                original_identifier, linkage_domain, tenant_id, len(pseudonym)
            )
            return hmac.compare_digest(expected_pseudonym, pseudonym)
        except Exception as e:
            logger.error(f"Pseudonym verification failed: {e}")
            return False


class SecureHasher:
    """Secure hashing utilities for audit trails."""
    
    @staticmethod
    def hash_text(text: str, salt: Optional[str] = None) -> str:
        """
        Generate SHA-256 hash of text for audit purposes.
        
        Args:
            text: Text to hash
            salt: Optional salt (uses random if None)
            
        Returns:
            Base64-encoded hash
        """
        if salt is None:
            salt = base64.b64encode(secrets.token_bytes(16)).decode('ascii')
        
        salted_text = f"{salt}:{text}"
        hash_digest = hashlib.sha256(salted_text.encode('utf-8')).digest()
        
        return base64.b64encode(hash_digest).decode('ascii')
    
    @staticmethod
    def hash_for_deduplication(text: str) -> str:
        """
        Generate consistent hash for deduplication (no salt).
        
        Args:
            text: Text to hash
            
        Returns:
            Hex-encoded hash
        """
        return hashlib.sha256(text.encode('utf-8')).hexdigest()


class EncryptionManager:
    """
    Manages encryption for sensitive data storage.
    Uses Fernet (AES-128 CBC + HMAC-SHA256) for symmetric encryption.
    """
    
    def __init__(self, encryption_key: Optional[str] = None):
        """
        Initialize encryption manager.
        
        Args:
            encryption_key: Base64-encoded Fernet key (generates if None)
        """
        if encryption_key:
            self.key = encryption_key.encode()
        else:
            self.key = Fernet.generate_key()
        
        self.fernet = Fernet(self.key)
    
    def encrypt(self, plaintext: str) -> str:
        """
        Encrypt plaintext string.
        
        Args:
            plaintext: String to encrypt
            
        Returns:
            Base64-encoded encrypted data
        """
        encrypted_bytes = self.fernet.encrypt(plaintext.encode('utf-8'))
        return base64.b64encode(encrypted_bytes).decode('ascii')
    
    def decrypt(self, ciphertext: str) -> str:
        """
        Decrypt ciphertext string.
        
        Args:
            ciphertext: Base64-encoded encrypted data
            
        Returns:
            Decrypted plaintext
        """
        encrypted_bytes = base64.b64decode(ciphertext.encode('ascii'))
        decrypted_bytes = self.fernet.decrypt(encrypted_bytes)
        return decrypted_bytes.decode('utf-8')
    
    def get_key_b64(self) -> str:
        """Get base64-encoded encryption key."""
        return base64.b64encode(self.key).decode('ascii')


class KeyRotationManager:
    """
    Manages cryptographic key rotation for pseudonyms and encryption.
    """
    
    def __init__(self):
        self.active_version = "v1.0"
        self.key_registry = {}
    
    def register_key(self, version: str, master_secret: str) -> None:
        """
        Register a key version.
        
        Args:
            version: Key version identifier
            master_secret: Base64-encoded master secret
        """
        self.key_registry[version] = master_secret
        logger.info(f"Registered key version: {version}")
    
    def get_pseudonym_generator(self, version: str = None) -> PseudonymGenerator:
        """
        Get pseudonym generator for specified version.
        
        Args:
            version: Key version (uses active if None)
            
        Returns:
            PseudonymGenerator instance
        """
        key_version = version or self.active_version
        
        if key_version not in self.key_registry:
            raise ValueError(f"Key version {key_version} not found")
        
        master_secret = self.key_registry[key_version]
        generator = PseudonymGenerator(master_secret)
        generator.key_version = key_version
        
        return generator
    
    def rotate_keys(self, new_master_secret: str) -> str:
        """
        Rotate to new key version.
        
        Args:
            new_master_secret: New master secret
            
        Returns:
            New key version identifier
        """
        # Generate new version
        current_major = int(self.active_version.split('.')[0][1:])
        new_version = f"v{current_major + 1}.0"
        
        # Register new key
        self.register_key(new_version, new_master_secret)
        
        # Update active version
        old_version = self.active_version
        self.active_version = new_version
        
        logger.info(f"Key rotation: {old_version} -> {new_version}")
        
        return new_version


def generate_master_secret() -> str:
    """
    Generate a cryptographically secure master secret.
    
    Returns:
        Base64-encoded master secret (32 bytes)
    """
    secret_bytes = secrets.token_bytes(32)
    return base64.b64encode(secret_bytes).decode('ascii')


def derive_encryption_key() -> str:
    """
    Generate a Fernet-compatible encryption key.
    
    Returns:
        Base64-encoded encryption key
    """
    return Fernet.generate_key().decode('ascii')


# Utility functions for secure operations
def secure_compare(a: str, b: str) -> bool:
    """Timing-safe string comparison."""
    return hmac.compare_digest(a.encode('utf-8'), b.encode('utf-8'))


def generate_salt(length: int = 16) -> str:
    """Generate random salt for hashing."""
    return base64.b64encode(secrets.token_bytes(length)).decode('ascii')


# Example usage and testing
if __name__ == "__main__":
    # Generate keys
    master_secret = generate_master_secret()
    print(f"Master secret: {master_secret}")
    
    # Initialize pseudonym generator
    generator = PseudonymGenerator(master_secret)
    
    # Generate pseudonyms
    test_id = "1234567890123"  # Thai citizen ID
    patient_pseudonym = generator.generate_pseudonym(test_id, "patient_id")
    encounter_pseudonym = generator.generate_pseudonym(test_id, "encounter_id")
    
    print(f"Original ID: {test_id}")
    print(f"Patient pseudonym: {patient_pseudonym}")
    print(f"Encounter pseudonym: {encounter_pseudonym}")
    
    # Verify consistency
    patient_pseudonym2 = generator.generate_pseudonym(test_id, "patient_id")
    print(f"Consistent: {patient_pseudonym == patient_pseudonym2}")
    
    # Verify linkage isolation
    print(f"Linkage isolated: {patient_pseudonym != encounter_pseudonym}")
    
    # Test encryption
    encryptor = EncryptionManager()
    encrypted = encryptor.encrypt("Sensitive medical data")
    decrypted = encryptor.decrypt(encrypted)
    print(f"Encryption test: {decrypted == 'Sensitive medical data'}")
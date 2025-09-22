"""
Authentication and authorization system for Clinical De-ID.
Implements role-based access control (RBAC) with JWT tokens.
"""
import jwt
import bcrypt
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Set
from fastapi import HTTPException, Security, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
import logging

from models.schemas import UserRole
from utils.config import get_settings

logger = logging.getLogger(__name__)
security = HTTPBearer()


class User(BaseModel):
    """User model for authentication."""
    user_id: str
    username: str
    email: str
    role: UserRole
    permissions: List[str]
    is_active: bool = True
    created_at: datetime
    last_login: Optional[datetime] = None


class TokenData(BaseModel):
    """JWT token payload data."""
    user_id: str
    username: str
    role: str
    permissions: List[str]
    exp: datetime
    iat: datetime


class Permission:
    """Define system permissions."""
    
    # Job operations
    CREATE_JOB = "create_job"
    VIEW_JOB = "view_job"
    CANCEL_JOB = "cancel_job"
    
    # Review operations
    VIEW_SAMPLE = "view_sample"
    SUBMIT_REVIEW = "submit_review"
    MANAGE_SAMPLES = "manage_samples"
    
    # Audit operations
    VIEW_AUDIT_LOGS = "view_audit_logs"
    EXPORT_AUDIT = "export_audit"
    VIEW_TRACE_LOGS = "view_trace_logs"
    
    # Configuration operations
    MANAGE_POLICIES = "manage_policies"
    MANAGE_MODELS = "manage_models"
    MANAGE_RULES = "manage_rules"
    
    # User management
    MANAGE_USERS = "manage_users"
    VIEW_USERS = "view_users"
    
    # System administration
    MANAGE_KEYS = "manage_keys"
    SYSTEM_CONFIG = "system_config"
    VIEW_METRICS = "view_metrics"


class RolePermissions:
    """Role-based permission mappings."""
    
    OPERATOR = [
        Permission.CREATE_JOB,
        Permission.VIEW_JOB,
        Permission.CANCEL_JOB,
        Permission.VIEW_METRICS,
    ]
    
    REVIEWER = [
        Permission.VIEW_JOB,
        Permission.VIEW_SAMPLE,
        Permission.SUBMIT_REVIEW,
        Permission.VIEW_METRICS,
    ]
    
    AUDITOR = [
        Permission.VIEW_JOB,
        Permission.VIEW_AUDIT_LOGS,
        Permission.EXPORT_AUDIT,
        Permission.VIEW_TRACE_LOGS,
        Permission.VIEW_USERS,
        Permission.VIEW_METRICS,
    ]
    
    ADMIN = [
        # All permissions
        Permission.CREATE_JOB,
        Permission.VIEW_JOB,
        Permission.CANCEL_JOB,
        Permission.VIEW_SAMPLE,
        Permission.SUBMIT_REVIEW,
        Permission.MANAGE_SAMPLES,
        Permission.VIEW_AUDIT_LOGS,
        Permission.EXPORT_AUDIT,
        Permission.VIEW_TRACE_LOGS,
        Permission.MANAGE_POLICIES,
        Permission.MANAGE_MODELS,
        Permission.MANAGE_RULES,
        Permission.MANAGE_USERS,
        Permission.VIEW_USERS,
        Permission.MANAGE_KEYS,
        Permission.SYSTEM_CONFIG,
        Permission.VIEW_METRICS,
    ]
    
    @classmethod
    def get_permissions(cls, role: UserRole) -> List[str]:
        """Get permissions for role."""
        permission_map = {
            UserRole.OPERATOR: cls.OPERATOR,
            UserRole.REVIEWER: cls.REVIEWER,
            UserRole.AUDITOR: cls.AUDITOR,
            UserRole.ADMIN: cls.ADMIN,
        }
        return permission_map.get(role, [])


class AuthenticationManager:
    """Manages user authentication and JWT tokens."""
    
    def __init__(self, secret_key: str, algorithm: str = "HS256"):
        self.secret_key = secret_key
        self.algorithm = algorithm
        self.token_expiry_hours = 24
        
        # In-memory user store (replace with database in production)
        self.users: Dict[str, User] = {}
        self.user_credentials: Dict[str, str] = {}  # username -> hashed_password
        
        # Create default admin user
        self._create_default_users()
    
    def _create_default_users(self) -> None:
        """Create default system users."""
        # Admin user
        admin_user = User(
            user_id="admin_001",
            username="admin",
            email="admin@clinical-deid.local",
            role=UserRole.ADMIN,
            permissions=RolePermissions.get_permissions(UserRole.ADMIN),
            created_at=datetime.utcnow()
        )
        self.users["admin"] = admin_user
        self.user_credentials["admin"] = self._hash_password("admin123")
        
        # Default reviewer
        reviewer_user = User(
            user_id="reviewer_001",
            username="reviewer",
            email="reviewer@clinical-deid.local",
            role=UserRole.REVIEWER,
            permissions=RolePermissions.get_permissions(UserRole.REVIEWER),
            created_at=datetime.utcnow()
        )
        self.users["reviewer"] = reviewer_user
        self.user_credentials["reviewer"] = self._hash_password("reviewer123")
        
        # Default operator
        operator_user = User(
            user_id="operator_001",
            username="operator",
            email="operator@clinical-deid.local",
            role=UserRole.OPERATOR,
            permissions=RolePermissions.get_permissions(UserRole.OPERATOR),
            created_at=datetime.utcnow()
        )
        self.users["operator"] = operator_user
        self.user_credentials["operator"] = self._hash_password("operator123")
        
        logger.info("Created default users: admin, reviewer, operator")
    
    def _hash_password(self, password: str) -> str:
        """Hash password with bcrypt."""
        return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
    
    def _verify_password(self, password: str, hashed: str) -> bool:
        """Verify password against hash."""
        return bcrypt.checkpw(password.encode('utf-8'), hashed.encode('utf-8'))
    
    def authenticate_user(self, username: str, password: str) -> Optional[User]:
        """
        Authenticate user with username and password.
        
        Args:
            username: Username
            password: Plain text password
            
        Returns:
            User object if authentication successful, None otherwise
        """
        if username not in self.users or username not in self.user_credentials:
            return None
        
        user = self.users[username]
        if not user.is_active:
            return None
        
        hashed_password = self.user_credentials[username]
        if not self._verify_password(password, hashed_password):
            return None
        
        # Update last login
        user.last_login = datetime.utcnow()
        
        logger.info(f"User {username} authenticated successfully")
        return user
    
    def create_access_token(self, user: User) -> str:
        """
        Create JWT access token for user.
        
        Args:
            user: Authenticated user
            
        Returns:
            JWT token string
        """
        now = datetime.utcnow()
        exp = now + timedelta(hours=self.token_expiry_hours)
        
        payload = {
            "user_id": user.user_id,
            "username": user.username,
            "role": user.role.value,
            "permissions": user.permissions,
            "exp": exp,
            "iat": now,
            "sub": user.username,
        }
        
        token = jwt.encode(payload, self.secret_key, algorithm=self.algorithm)
        
        logger.info(f"Access token created for user {user.username}")
        return token
    
    def verify_token(self, token: str) -> Optional[TokenData]:
        """
        Verify and decode JWT token.
        
        Args:
            token: JWT token string
            
        Returns:
            TokenData if valid, None otherwise
        """
        try:
            payload = jwt.decode(token, self.secret_key, algorithms=[self.algorithm])
            
            token_data = TokenData(
                user_id=payload["user_id"],
                username=payload["username"],
                role=payload["role"],
                permissions=payload["permissions"],
                exp=datetime.fromtimestamp(payload["exp"]),
                iat=datetime.fromtimestamp(payload["iat"])
            )
            
            # Check if token is expired
            if token_data.exp < datetime.utcnow():
                logger.warning(f"Expired token for user {token_data.username}")
                return None
            
            return token_data
            
        except jwt.InvalidTokenError as e:
            logger.warning(f"Invalid token: {e}")
            return None
    
    def create_user(
        self, 
        username: str, 
        email: str, 
        password: str, 
        role: UserRole
    ) -> User:
        """
        Create new user.
        
        Args:
            username: Username (must be unique)
            email: Email address
            password: Plain text password
            role: User role
            
        Returns:
            Created user
            
        Raises:
            ValueError: If username already exists
        """
        if username in self.users:
            raise ValueError(f"Username {username} already exists")
        
        user = User(
            user_id=f"{role.value}_{len(self.users):03d}",
            username=username,
            email=email,
            role=role,
            permissions=RolePermissions.get_permissions(role),
            created_at=datetime.utcnow()
        )
        
        self.users[username] = user
        self.user_credentials[username] = self._hash_password(password)
        
        logger.info(f"Created user {username} with role {role.value}")
        return user


# Global authentication manager instance
settings = get_settings()
auth_manager = AuthenticationManager(settings.jwt_secret_key)


# Dependency functions for FastAPI
async def get_current_user(credentials: HTTPAuthorizationCredentials = Security(security)) -> User:
    """
    FastAPI dependency to get current authenticated user.
    
    Args:
        credentials: HTTP authorization credentials
        
    Returns:
        Current user
        
    Raises:
        HTTPException: If authentication fails
    """
    token = credentials.credentials
    token_data = auth_manager.verify_token(token)
    
    if not token_data:
        raise HTTPException(
            status_code=401,
            detail="Invalid authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    username = token_data.username
    if username not in auth_manager.users:
        raise HTTPException(
            status_code=401,
            detail="User not found",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    user = auth_manager.users[username]
    if not user.is_active:
        raise HTTPException(status_code=401, detail="Inactive user")
    
    return user


def require_permission(permission: str):
    """
    Create dependency function that requires specific permission.
    
    Args:
        permission: Required permission
        
    Returns:
        Dependency function
    """
    def permission_check(current_user: User = Depends(get_current_user)) -> User:
        if permission not in current_user.permissions:
            raise HTTPException(
                status_code=403,
                detail=f"Insufficient permissions. Required: {permission}"
            )
        return current_user
    
    return permission_check


def require_role(required_role: UserRole):
    """
    Create dependency function that requires specific role.
    
    Args:
        required_role: Required user role
        
    Returns:
        Dependency function
    """
    def role_check(current_user: User = Depends(get_current_user)) -> User:
        if current_user.role != required_role:
            raise HTTPException(
                status_code=403,
                detail=f"Insufficient role. Required: {required_role.value}"
            )
        return current_user
    
    return role_check


# Convenience dependencies for common roles
require_admin = require_role(UserRole.ADMIN)
require_reviewer = require_role(UserRole.REVIEWER)
require_auditor = require_role(UserRole.AUDITOR)
require_operator = require_role(UserRole.OPERATOR)

# Convenience dependencies for common permissions
require_create_job = require_permission(Permission.CREATE_JOB)
require_view_audit = require_permission(Permission.VIEW_AUDIT_LOGS)
require_manage_policies = require_permission(Permission.MANAGE_POLICIES)


class AuditLogger:
    """Audit logging for security events."""
    
    def __init__(self):
        self.logger = logging.getLogger("audit")
    
    def log_authentication(self, username: str, success: bool, ip_address: str = None):
        """Log authentication attempt."""
        status = "SUCCESS" if success else "FAILURE"
        self.logger.info(f"AUTH {status}: user={username} ip={ip_address}")
    
    def log_authorization(self, username: str, action: str, resource: str, success: bool):
        """Log authorization check."""
        status = "ALLOWED" if success else "DENIED"
        self.logger.info(f"AUTHZ {status}: user={username} action={action} resource={resource}")
    
    def log_key_operation(self, username: str, operation: str, key_version: str = None):
        """Log cryptographic key operations."""
        self.logger.info(f"KEY_OP: user={username} operation={operation} version={key_version}")
    
    def log_data_access(self, username: str, data_type: str, record_count: int = None):
        """Log access to sensitive data."""
        self.logger.info(f"DATA_ACCESS: user={username} type={data_type} count={record_count}")


# Global audit logger
audit_logger = AuditLogger()
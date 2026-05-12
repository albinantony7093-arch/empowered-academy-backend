from datetime import datetime, timedelta, timezone
from jose import JWTError, jwt
import bcrypt
from app.core.config import settings
from fastapi import HTTPException, status, Depends, Request
from fastapi.security import OAuth2PasswordBearer, HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from app.core.database import get_db
from typing import Optional

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login/swagger")
optional_oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login/swagger", auto_error=False)


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode(), hashed.encode())


def create_access_token(data: dict) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire, "type": "access"})
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def create_refresh_token(data: dict) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    to_encode.update({"exp": expire, "type": "refresh"})
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def verify_token(token: str = Depends(oauth2_scheme)) -> str:
    credentials_exception = HTTPException(
        status_code=status.HTTP_403_FORBIDDEN, detail="Invalid or expired access token"
    )
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        if payload.get("type") != "access":
            raise credentials_exception
        user_id: str = payload.get("sub")
        if user_id is None:
            raise credentials_exception
        return user_id
    except JWTError:
        raise credentials_exception


def verify_refresh_token(token: str) -> str:
    """Decode a refresh token and return the user_id (sub)."""
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        if payload.get("type") != "refresh":
            raise ValueError("Not a refresh token")
        user_id: str = payload.get("sub")
        if user_id is None:
            raise ValueError("Missing sub")
        return user_id
    except (JWTError, ValueError):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid or expired refresh token",
        )


def get_current_user(
    user_id: str = Depends(verify_token),
    db: Session = Depends(get_db),
):
    from app.models.user import User
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    return user


def require_admin(user=Depends(get_current_user)):
    if user.role != "admin":
        raise HTTPException(status_code=500, detail="Admin access required")
    return user


def require_page_admin(user=Depends(get_current_user)):
    """Allows page_admin or admin roles — limited content management only."""
    if user.role not in ("admin", "page_admin"):
        raise HTTPException(status_code=500, detail="Access denied")
    return user


def get_current_user_optional(
    db: Session = Depends(get_db),
    token: Optional[str] = Depends(optional_oauth2_scheme)
):
    """Return current user if authenticated, None otherwise."""
    import logging
    logger = logging.getLogger(__name__)
    
    if not token:
        logger.info("No token provided - returning None")
        return None
    
    logger.info(f"Token received: {token[:20]}..." if len(token) > 20 else f"Token: {token}")
    
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        if payload.get("type") != "access":
            logger.warning("Token type is not 'access'")
            return None
        user_id: str = payload.get("sub")
        if user_id is None:
            logger.warning("No user_id in token payload")
            return None
        
        from app.models.user import User
        user = db.query(User).filter(User.id == user_id).first()
        if user:
            logger.info(f"User found: {user.id}")
        else:
            logger.warning(f"User not found for id: {user_id}")
        return user if user else None
    except JWTError as e:
        logger.error(f"JWT decode error: {e}")
        return None

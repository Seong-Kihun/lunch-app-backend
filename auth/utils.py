import jwt
import secrets
import hashlib
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from flask import current_app
from config.auth_config import AuthConfig
# db 객체는 지연 import로 처리

class AuthUtils:
    """인증 관련 유틸리티 클래스"""
    
    @staticmethod
    def generate_jwt_token(user_id: int, token_type: str = 'access') -> str:
        """JWT 토큰 생성"""
        if token_type == 'access':
            expires = datetime.utcnow() + AuthConfig.JWT_ACCESS_TOKEN_EXPIRES
        else:  # refresh
            expires = datetime.utcnow() + AuthConfig.JWT_REFRESH_TOKEN_EXPIRES
        
        payload = {
            'user_id': user_id,
            'token_type': token_type,
            'exp': expires,
            'iat': datetime.utcnow()
        }
        
        return jwt.encode(payload, AuthConfig.JWT_SECRET_KEY, algorithm='HS256')
    
    @staticmethod
    def verify_jwt_token(token: str) -> Optional[Dict[str, Any]]:
        """JWT 토큰 검증"""
        try:
            print(f"DEBUG: Verifying JWT token with secret key: {AuthConfig.JWT_SECRET_KEY[:20]}...")
            payload = jwt.decode(token, AuthConfig.JWT_SECRET_KEY, algorithms=['HS256'])
            print(f"DEBUG: JWT token verified successfully: {payload}")
            return payload
        except jwt.ExpiredSignatureError as e:
            print(f"DEBUG: JWT token expired: {e}")
            return None
        except jwt.InvalidTokenError as e:
            print(f"DEBUG: JWT token invalid: {e}")
            return None
        except Exception as e:
            print(f"DEBUG: JWT token verification error: {e}")
            return None
    
    @staticmethod
    def create_magic_link_token(email: str) -> tuple[str, str]:
        """매직링크 토큰 생성"""
        # 지연 import로 순환 참조 방지
        from .models import MagicLinkToken
        
        # 원본 토큰 생성
        original_token = secrets.token_urlsafe(32)
        
        # 해시된 토큰 생성
        token_hash = hashlib.sha256(original_token.encode()).hexdigest()
        
        # 만료 시간 설정
        expires_at = datetime.utcnow() + AuthConfig.MAGIC_LINK_EXPIRES
        
        # DB에 저장
        magic_token = MagicLinkToken(
            token_hash=token_hash,
            email=email,
            expires_at=expires_at
        )
        
        # 지연 import로 순환 참조 방지
        from .models import db
        db.session.add(magic_token)
        db.session.commit()
        
        return original_token, token_hash
    
    @staticmethod
    def verify_magic_link_token(token: str) -> Optional[Dict[str, Any]]:
        """매직링크 토큰 검증"""
        # 지연 import로 순환 참조 방지
        from .models import MagicLinkToken, User
        
        # 토큰 해시화
        token_hash = hashlib.sha256(token.encode()).hexdigest()
        
        # DB에서 토큰 조회
        magic_token = MagicLinkToken.query.filter_by(
            token_hash=token_hash,
            is_used=False
        ).first()
        
        if not magic_token:
            return None
        
        # 만료 여부 확인
        if magic_token.is_expired():
            # 만료된 토큰 삭제
            from .models import db
            db.session.delete(magic_token)
            db.session.commit()
            return None
        
        # 사용자 조회
        user = User.query.filter_by(email=magic_token.email).first()
        
        # 토큰 사용 처리
        magic_token.is_used = True
        from .models import db
        db.session.commit()
        
        return {
            'email': magic_token.email,
            'user': user,
            'is_new_user': user is None
        }
    
    @staticmethod
    def create_refresh_token(user_id: int) -> tuple[str, str]:
        """리프레시 토큰 생성"""
        # 지연 import로 순환 참조 방지
        from .models import RefreshToken
        
        # 원본 토큰 생성
        original_token = secrets.token_urlsafe(32)
        
        # 해시된 토큰 생성
        token_hash = hashlib.sha256(original_token.encode()).hexdigest()
        
        # 만료 시간 설정
        expires_at = datetime.utcnow() + AuthConfig.JWT_REFRESH_TOKEN_EXPIRES
        
        # DB에 저장
        refresh_token = RefreshToken(
            token_hash=token_hash,
            user_id=user_id,
            expires_at=expires_at
        )
        
        from .models import db
        db.session.add(refresh_token)
        db.session.commit()
        
        return original_token, token_hash
    
    @staticmethod
    def verify_refresh_token(token: str) -> Optional[Dict[str, Any]]:
        """리프레시 토큰 검증"""
        # 지연 import로 순환 참조 방지
        from .models import RefreshToken, User
        
        # 토큰 해시화
        token_hash = hashlib.sha256(token.encode()).hexdigest()
        
        # DB에서 토큰 조회
        refresh_token = RefreshToken.query.filter_by(
            token_hash=token_hash,
            is_revoked=False
        ).first()
        
        if not refresh_token:
            return None
        
        # 만료 여부 확인
        if refresh_token.is_expired():
            # 만료된 토큰 삭제
            from .models import db
            db.session.delete(refresh_token)
            db.session.commit()
            return None
        
        return refresh_token.user
    
    @staticmethod
    def revoke_refresh_token(token: str) -> bool:
        """리프레시 토큰 무효화"""
        # 지연 import로 순환 참조 방지
        from .models import RefreshToken, RevokedToken
        
        # 토큰 해시화
        token_hash = hashlib.sha256(token.encode()).hexdigest()
        
        # DB에서 토큰 조회
        refresh_token = RefreshToken.query.filter_by(
            token_hash=token_hash,
            is_revoked=False
        ).first()
        
        if not refresh_token:
            return False
        
        # 무효화 처리
        refresh_token.is_revoked = True
        
        # 블랙리스트에 추가
        revoked_token = RevokedToken(
            token_hash=token_hash,
            user_id=refresh_token.user_id
        )
        
        from .models import db
        db.session.add(revoked_token)
        db.session.commit()
        
        return True
    
    @staticmethod
    def generate_employee_id() -> str:
        """고유한 직원 ID 생성"""
        # 지연 import로 순환 참조 방지
        from .models import User
        import random
        import string
        
        while True:
            # KOICA + 3자리 숫자
            employee_id = f"KOICA{random.randint(100, 999)}"
            
            # 중복 확인
            if not User.query.filter_by(employee_id=employee_id).first():
                return employee_id
    
    @staticmethod
    def is_token_revoked(token_hash: str) -> bool:
        """토큰이 무효화되었는지 확인"""
        # 지연 import로 순환 참조 방지
        from .models import RevokedToken
        return RevokedToken.query.filter_by(token_hash=token_hash).first() is not None

def require_auth(f):
    """인증이 필요한 API를 위한 데코레이터"""
    from functools import wraps
    from flask import request, jsonify
    
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # 지연 import로 순환 참조 방지
        from .models import User
        
        auth_header = request.headers.get('Authorization')
        
        if not auth_header:
            print(f"DEBUG: Authorization header missing for {request.endpoint}")
            return jsonify({'error': 'Authorization header missing'}), 401
        
        try:
            # Bearer 토큰 추출
            token = auth_header.split(' ')[1]
            print(f"DEBUG: Token received: {token[:20]}... for {request.endpoint}")
            
            # JWT 토큰 검증
            payload = AuthUtils.verify_jwt_token(token)
            if not payload:
                print(f"DEBUG: Token verification failed for {request.endpoint}")
                return jsonify({'error': 'Invalid or expired token'}), 401
            
            print(f"DEBUG: Token verified successfully for {request.endpoint}, user_id: {payload.get('user_id')}")
            
            # 토큰 타입 확인
            if payload.get('token_type') != 'access':
                print(f"DEBUG: Invalid token type: {payload.get('token_type')} for {request.endpoint}")
                return jsonify({'error': 'Invalid token type'}), 401
            
            # 사용자 조회
            user = User.query.get(payload['user_id'])
            if not user or not user.is_active:
                print(f"DEBUG: User not found or inactive: {payload['user_id']} for {request.endpoint}")
                return jsonify({'error': 'User not found or inactive'}), 401
            
            # 토큰 무효화 여부 확인
            if AuthUtils.is_token_revoked(token):
                print(f"DEBUG: Token revoked for {request.endpoint}")
                return jsonify({'error': 'Token has been revoked'}), 401
            
            # request 객체에 사용자 정보 추가
            request.current_user = user
            
            return f(*args, **kwargs)
            
        except (IndexError, KeyError) as e:
            print(f"DEBUG: Authorization header format error: {e} for {request.endpoint}")
            return jsonify({'error': 'Invalid authorization header format'}), 401
        except Exception as e:
            print(f"DEBUG: Authentication error: {e} for {request.endpoint}")
            return jsonify({'error': 'Authentication failed'}), 401
    
    return decorated_function

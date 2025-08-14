from datetime import datetime, timedelta
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
import secrets
import hashlib

db = SQLAlchemy()

class User(db.Model):
    """사용자 모델"""
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    nickname = db.Column(db.String(50), nullable=False)
    employee_id = db.Column(db.String(20), unique=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    is_active = db.Column(db.Boolean, default=True)
    
    # 기존 앱과의 호환성을 위한 필드들
    points = db.Column(db.Integer, default=0)
    profile_image = db.Column(db.String(255))
    
    def __repr__(self):
        return f'<User {self.email}>'
    
    def to_dict(self):
        return {
            'id': self.id,
            'email': self.email,
            'nickname': self.nickname,
            'employee_id': self.employee_id,
            'created_at': self.created_at.isoformat(),
            'points': self.points,
            'profile_image': self.profile_image
        }

class MagicLinkToken(db.Model):
    """매직링크 토큰 모델"""
    __tablename__ = 'magic_link_tokens'
    
    id = db.Column(db.Integer, primary_key=True)
    token_hash = db.Column(db.String(64), unique=True, nullable=False, index=True)
    email = db.Column(db.String(120), nullable=False, index=True)
    expires_at = db.Column(db.DateTime, nullable=False)
    is_used = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f'<MagicLinkToken {self.email}>'
    
    @staticmethod
    def generate_token():
        """암호학적으로 안전한 토큰 생성"""
        return secrets.token_urlsafe(32)
    
    @staticmethod
    def hash_token(token):
        """토큰을 해시화"""
        return hashlib.sha256(token.encode()).hexdigest()
    
    def is_expired(self):
        """토큰 만료 여부 확인"""
        return datetime.utcnow() > self.expires_at

class RefreshToken(db.Model):
    """리프레시 토큰 모델"""
    __tablename__ = 'refresh_tokens'
    
    id = db.Column(db.Integer, primary_key=True)
    token_hash = db.Column(db.String(64), unique=True, nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    expires_at = db.Column(db.DateTime, nullable=False)
    is_revoked = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    user = db.relationship('User', backref='refresh_tokens')
    
    def __repr__(self):
        return f'<RefreshToken {self.user_id}>'
    
    @staticmethod
    def generate_token():
        """암호학적으로 안전한 토큰 생성"""
        return secrets.token_urlsafe(32)
    
    @staticmethod
    def hash_token(token):
        """토큰을 해시화"""
        return hashlib.sha256(token.encode()).hexdigest()
    
    def is_expired(self):
        """토큰 만료 여부 확인"""
        return datetime.utcnow() > self.expires_at

class RevokedToken(db.Model):
    """무효화된 토큰 블랙리스트"""
    __tablename__ = 'revoked_tokens'
    
    id = db.Column(db.Integer, primary_key=True)
    token_hash = db.Column(db.String(64), unique=True, nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    revoked_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    user = db.relationship('User', backref='revoked_tokens')
    
    def __repr__(self):
        return f'<RevokedToken {self.user_id}>'

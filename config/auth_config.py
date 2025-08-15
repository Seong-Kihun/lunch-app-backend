import os
from datetime import timedelta
from .env_loader import get_env_var

class AuthConfig:
    """인증 시스템 설정"""
    
    # JWT 토큰 설정
    JWT_SECRET_KEY = get_env_var('JWT_SECRET_KEY', 'dev-jwt-secret-key-change-in-production')
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(hours=24)  # 1일
    JWT_REFRESH_TOKEN_EXPIRES = timedelta(days=365)  # 1년
    
    # 매직링크 설정
    MAGIC_LINK_EXPIRES = timedelta(minutes=10)  # 10분
    
    # 이메일 설정
    MAIL_SERVER = get_env_var('MAIL_SERVER', 'smtp.gmail.com')  # Gmail 서버
    MAIL_PORT = int(get_env_var('MAIL_PORT', '587'))
    MAIL_USE_TLS = get_env_var('MAIL_USE_TLS', 'true').lower() == 'true'
    MAIL_USERNAME = get_env_var('MAIL_USERNAME', '')  # 환경 변수에서 가져옴
    MAIL_PASSWORD = get_env_var('MAIL_PASSWORD', '')  # 환경 변수에서 가져옴
    
    # 앱 설정
    APP_NAME = '밥플떼기'
    APP_DOMAIN = get_env_var('APP_DOMAIN', 'https://api.bal-plateggi.com')
    FRONTEND_DOMAIN = get_env_var('FRONTEND_DOMAIN', 'https://app.bal-plateggi.com')
    
    # 딥링크 설정
    DEEP_LINK_SCHEME = 'balplateggi'
    UNIVERSAL_LINK_DOMAIN = 'api.bal-plateggi.com'
    
    # 보안 설정
    PASSWORD_SALT_ROUNDS = 12
    MAX_LOGIN_ATTEMPTS = 5
    LOCKOUT_DURATION = timedelta(minutes=15)
    
    # 데이터베이스 설정
    DB_CONNECTION_STRING = get_env_var('DATABASE_URL', 'sqlite:///site.db')
    
    @classmethod
    def get_magic_link_url(cls, token):
        """매직링크 URL 생성"""
        return f"{cls.APP_DOMAIN}/auth/verify-link?token={token}"
    
    @classmethod
    def get_deep_link_url(cls, action, **params):
        """딥링크 URL 생성"""
        param_string = '&'.join([f"{k}={v}" for k, v in params.items()])
        return f"{cls.DEEP_LINK_SCHEME}://{action}?{param_string}"

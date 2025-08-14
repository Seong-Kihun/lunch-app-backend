import os
from datetime import timedelta

class AuthConfig:
    """인증 시스템 설정"""
    
    # JWT 토큰 설정
    JWT_SECRET_KEY = os.environ.get('JWT_SECRET_KEY', 'your-super-secret-jwt-key-change-in-production')
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(hours=24)  # 1일
    JWT_REFRESH_TOKEN_EXPIRES = timedelta(days=365)  # 1년
    
    # 매직링크 설정
    MAGIC_LINK_EXPIRES = timedelta(minutes=10)  # 10분
    
    # 이메일 설정
    MAIL_SERVER = os.environ.get('MAIL_SERVER', 'smtp.gmail.com')
    MAIL_PORT = int(os.environ.get('MAIL_PORT', 587))
    MAIL_USE_TLS = os.environ.get('MAIL_USE_TLS', 'true').lower() == 'true'
    MAIL_USERNAME = os.environ.get('MAIL_USERNAME', 'your-email@gmail.com')
    MAIL_PASSWORD = os.environ.get('MAIL_PASSWORD', 'your-app-password')
    
    # 앱 설정
    APP_NAME = '발플때기'
    APP_DOMAIN = os.environ.get('APP_DOMAIN', 'https://api.bal-plateggi.com')
    FRONTEND_DOMAIN = os.environ.get('FRONTEND_DOMAIN', 'https://app.bal-plateggi.com')
    
    # 딥링크 설정
    DEEP_LINK_SCHEME = 'balplateggi'
    UNIVERSAL_LINK_DOMAIN = 'api.bal-plateggi.com'
    
    # 보안 설정
    PASSWORD_SALT_ROUNDS = 12
    MAX_LOGIN_ATTEMPTS = 5
    LOCKOUT_DURATION = timedelta(minutes=15)
    
    # 데이터베이스 설정
    DB_CONNECTION_STRING = os.environ.get('DATABASE_URL', 'sqlite:///site.db')
    
    @classmethod
    def get_magic_link_url(cls, token):
        """매직링크 URL 생성"""
        return f"{cls.APP_DOMAIN}/auth/verify-link?token={token}"
    
    @classmethod
    def get_deep_link_url(cls, action, **params):
        """딥링크 URL 생성"""
        param_string = '&'.join([f"{k}={v}" for k, v in params.items()])
        return f"{cls.DEEP_LINK_SCHEME}://{action}?{param_string}"

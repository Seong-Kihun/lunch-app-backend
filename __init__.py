from flask import Flask
from auth.models import db, User, MagicLinkToken, RefreshToken, RevokedToken
from auth.routes import auth_bp
from auth.utils import AuthUtils
from auth.email_service import email_service

def init_auth(app: Flask):
    """인증 시스템 초기화"""
    
    # 데이터베이스 설정
    app.config['SQLALCHEMY_DATABASE_URI'] = app.config.get('SQLALCHEMY_DATABASE_URI', 'sqlite:///site.db')
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    
    # 데이터베이스 초기화
    db.init_app(app)
    
    # 블루프린트 등록
    app.register_blueprint(auth_bp)
    
    # 데이터베이스 테이블 생성
    with app.app_context():
        # 기존 테이블 삭제 (개발 환경에서만)
        db.drop_all()
        db.create_all()
        print("인증 시스템 데이터베이스 테이블이 재생성되었습니다.")
    
    return app

def create_tables():
    """데이터베이스 테이블 생성 (마이그레이션용)"""
    db.create_all()
    print("인증 시스템 테이블이 생성되었습니다.")

# 모듈 레벨에서 db 객체를 사용할 수 있도록 설정
__all__ = [
    'db', 
    'User', 
    'MagicLinkToken', 
    'RefreshToken', 
    'RevokedToken',
    'AuthUtils',
    'email_service',
    'init_auth',
    'create_tables'
]

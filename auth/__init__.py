def init_auth(app):
    """인증 시스템 초기화"""
    
    # 지연 import로 순환 참조 방지
    from .routes import auth_bp
    from .models import db
    
    # 블루프린트 등록
    app.register_blueprint(auth_bp)
    
    # 데이터베이스 테이블 생성
    with app.app_context():
        db.create_all()
        print("✅ 인증 시스템 데이터베이스 테이블이 생성되었습니다.")
    
    return app

def create_tables():
    """데이터베이스 테이블 생성 (마이그레이션용)"""
    # 지연 import로 순환 참조 방지
    from .models import db
    db.create_all()
    print("✅ 인증 시스템 테이블이 생성되었습니다.")

# 모듈 레벨에서 db 객체를 사용할 수 있도록 설정
__all__ = [
    'init_auth',
    'create_tables'
]

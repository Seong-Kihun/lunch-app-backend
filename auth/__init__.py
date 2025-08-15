def init_auth(app):
    """인증 시스템 초기화"""
    
    # 지연 import로 순환 참조 방지
    from .models import db
    from .utils import require_auth
    
    # 데이터베이스 테이블 생성 (db는 이미 app.py에서 연결됨)
    with app.app_context():
        db.create_all()
        print("✅ 인증 시스템 데이터베이스 테이블이 생성되었습니다.")
    
    # require_auth 데코레이터를 전역에서 사용할 수 있도록 설정
    app.require_auth = require_auth
    
    return app

# db 객체를 모듈 레벨에서 사용할 수 있도록 설정
from .models import db

def create_tables():
    """데이터베이스 테이블 생성 (마이그레이션용)"""
    # 지연 import로 순환 참조 방지
    from .models import db
    db.create_all()
    print("✅ 인증 시스템 테이블이 생성되었습니다.")

# 모듈 레벨에서 db 객체를 사용할 수 있도록 설정
__all__ = [
    'init_auth',
    'create_tables',
    'db'
]

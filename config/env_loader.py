import os
from pathlib import Path
from dotenv import load_dotenv


def load_environment_variables():
    """환경변수를 안전하게 로드"""
    # .env 파일 경로 찾기
    env_paths = [
        Path.cwd() / ".env",
        Path.cwd() / "lunch_app" / ".env",
        Path(__file__).parent.parent / ".env",
        Path(__file__).parent.parent.parent / ".env",
    ]

    # .env 파일이 있으면 로드
    for env_path in env_paths:
        if env_path.exists():
            load_dotenv(env_path)
            print(f"✅ 환경변수 파일 로드됨: {env_path}")
            break
    else:
        print("⚠️ .env 파일을 찾을 수 없습니다. 시스템 환경변수를 사용합니다.")

    # 필수 환경변수 확인 및 기본값 설정
    required_vars = {
        "JWT_SECRET_KEY": "dev-jwt-secret-key-change-in-production",
        "SECRET_KEY": "dev-flask-secret-key-change-in-production",
        "DATABASE_URL": "sqlite:///site.db",
        "REDIS_URL": "redis://localhost:6379/0",
        "CELERY_BROKER_URL": "redis://localhost:6379/1",
        "CELERY_RESULT_BACKEND": "redis://localhost:6379/2",
    }

    # 환경변수 설정
    for var_name, default_value in required_vars.items():
        if not os.getenv(var_name):
            os.environ[var_name] = default_value
            print(f"⚠️ {var_name} 환경변수가 설정되지 않아 기본값을 사용합니다.")

    # 개발 환경 확인
    is_development = (
        os.getenv("FLASK_ENV") == "development" or os.getenv("ENV") == "development"
    )

    if is_development:
        print("🔧 개발 환경으로 실행됩니다.")
    else:
        print("🚀 프로덕션 환경으로 실행됩니다.")
        # 프로덕션에서는 보안 키가 기본값이면 경고
        if os.getenv("JWT_SECRET_KEY") == required_vars["JWT_SECRET_KEY"]:
            print("🚨 경고: 프로덕션 환경에서 기본 JWT_SECRET_KEY를 사용하고 있습니다!")
        if os.getenv("SECRET_KEY") == required_vars["SECRET_KEY"]:
            print("🚨 경고: 프로덕션 환경에서 기본 SECRET_KEY를 사용하고 있습니다!")


def get_env_var(var_name, default=None, required=False):
    """환경변수를 안전하게 가져오기"""
    value = os.getenv(var_name, default)

    if required and not value:
        raise ValueError(f"필수 환경변수 {var_name}이 설정되지 않았습니다.")

    return value

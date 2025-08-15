from flask import jsonify, current_app
from functools import wraps
import logging
import traceback

logger = logging.getLogger(__name__)

class AppError(Exception):
    """애플리케이션 에러 클래스"""
    def __init__(self, message, status_code=500, error_code=None, details=None):
        super().__init__()
        self.message = message
        self.status_code = status_code
        self.error_code = error_code
        self.details = details

class ValidationError(AppError):
    """데이터 검증 에러"""
    def __init__(self, message, details=None):
        super().__init__(message, 400, 'VALIDATION_ERROR', details)

class AuthenticationError(AppError):
    """인증 에러"""
    def __init__(self, message="인증이 필요합니다"):
        super().__init__(message, 401, 'AUTHENTICATION_ERROR')

class AuthorizationError(AppError):
    """권한 에러"""
    def __init__(self, message="권한이 없습니다"):
        super().__init__(message, 403, 'AUTHORIZATION_ERROR')

class NotFoundError(AppError):
    """리소스 없음 에러"""
    def __init__(self, message="리소스를 찾을 수 없습니다"):
        super().__init__(message, 404, 'NOT_FOUND_ERROR')

class ConflictError(AppError):
    """충돌 에러"""
    def __init__(self, message="리소스 충돌이 발생했습니다"):
        super().__init__(message, 409, 'CONFLICT_ERROR')

def handle_errors(f):
    """에러 핸들링 데코레이터"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        try:
            return f(*args, **kwargs)
        except AppError as e:
            logger.warning(f"애플리케이션 에러: {e.message}", extra={
                'error_code': e.error_code,
                'status_code': e.status_code,
                'details': e.details
            })
            return jsonify({
                'error': e.message,
                'error_code': e.error_code,
                'details': e.details
            }), e.status_code
        except Exception as e:
            logger.error(f"예상치 못한 에러: {str(e)}", extra={
                'traceback': traceback.format_exc()
            })
            return jsonify({
                'error': '서버 내부 오류가 발생했습니다',
                'error_code': 'INTERNAL_ERROR'
            }), 500
    return decorated_function

def safe_execute(func, *args, **kwargs):
    """안전한 함수 실행"""
    try:
        return func(*args, **kwargs), None
    except Exception as e:
        logger.error(f"함수 실행 실패: {func.__name__}", extra={
            'error': str(e),
            'traceback': traceback.format_exc()
        })
        return None, str(e)

def log_error(error, context=None):
    """에러 로깅"""
    error_data = {
        'error_type': type(error).__name__,
        'error_message': str(error),
        'context': context or {}
    }
    
    if hasattr(error, 'status_code'):
        error_data['status_code'] = error.status_code
    if hasattr(error, 'error_code'):
        error_data['error_code'] = error.error_code
    
    logger.error("에러 발생", extra=error_data)
    return error_data

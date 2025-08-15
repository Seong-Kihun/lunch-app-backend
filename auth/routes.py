from flask import Blueprint, request, jsonify, current_app
from datetime import datetime, timedelta
import re
from config.auth_config import AuthConfig

# 인증 블루프린트 생성
auth_bp = Blueprint('auth', __name__, url_prefix='/auth')

@auth_bp.route('/magic-link', methods=['POST'])
def send_magic_link():
    """매직링크 이메일 발송"""
    # 지연 import로 순환 참조 방지
    from .models import User
    from .utils import AuthUtils
    from .email_service import email_service
    
    try:
        data = request.get_json()
        
        if not data or 'email' not in data:
            return jsonify({'error': '이메일 주소가 필요합니다.'}), 400
        
        email = data['email'].strip().lower()
        
        # 이메일 형식 검증
        if not re.match(r'^[a-zA-Z0-9._%+-]+@koica\.go\.kr$', email):
            return jsonify({'error': 'KOICA 이메일 주소만 사용 가능합니다.'}), 400
        
        # 사용자 조회 (신규/기존 사용자 구분)
        user = User.query.filter_by(email=email).first()
        
        # 매직링크 토큰 생성
        original_token, token_hash = AuthUtils.create_magic_link_token(email)
        
        # 이메일 발송
        nickname = user.nickname if user else None
        if email_service.send_magic_link_email(email, original_token, nickname):
            return jsonify({
                'message': '인증 이메일을 발송했습니다.',
                'email': email,
                'is_new_user': user is None
            }), 200
        else:
            return jsonify({'error': '이메일 발송에 실패했습니다. 잠시 후 다시 시도해주세요.'}), 500
            
    except Exception as e:
        current_app.logger.error(f"매직링크 발송 실패: {str(e)}")
        return jsonify({'error': '서버 오류가 발생했습니다.'}), 500

@auth_bp.route('/test-login/<employee_id>', methods=['GET'])
def test_login(employee_id):
    """개발/테스트용 임시 로그인 (프로덕션에서는 제거)"""
    try:
        from .models import User
        from .utils import AuthUtils
        
        # 테스트용 사용자 조회
        user = User.query.filter_by(employee_id=employee_id).first()
        
        if not user:
            return jsonify({'error': f'사용자를 찾을 수 없습니다: {employee_id}'}), 404
        
        # 액세스 토큰과 리프레시 토큰 발급
        access_token = AuthUtils.generate_jwt_token(user.id, 'access')
        refresh_token, _ = AuthUtils.create_refresh_token(user.id)
        
        return jsonify({
            'type': 'test_login',
            'user': user.to_dict(),
            'access_token': access_token,
            'refresh_token': refresh_token,
            'message': '테스트 로그인 성공'
        }), 200
        
    except Exception as e:
        current_app.logger.error(f"테스트 로그인 실패: {str(e)}")
        return jsonify({'error': '서버 오류가 발생했습니다.'}), 500

@auth_bp.route('/verify-link', methods=['GET'])
def verify_magic_link():
    """매직링크 검증 및 사용자 분기 처리"""
    # 지연 import로 순환 참조 방지
    from .utils import AuthUtils
    
    try:
        token = request.args.get('token')
        
        if not token:
            return jsonify({'error': '토큰이 필요합니다.'}), 400
        
        # 토큰 검증
        verification_result = AuthUtils.verify_magic_link_token(token)
        
        if not verification_result:
            return jsonify({'error': '유효하지 않거나 만료된 링크입니다.'}), 400
        
        email = verification_result['email']
        user = verification_result['user']
        is_new_user = verification_result['is_new_user']
        
        if is_new_user:
            # 신규 사용자: 임시 토큰 발급
            temp_token = AuthUtils.generate_jwt_token(0, 'temp')  # user_id 0은 임시
            
            # 딥링크로 앱 실행
            deep_link = AuthConfig.get_deep_link_url('register', tempToken=temp_token)
            
            return jsonify({
                'type': 'register',
                'email': email,
                'deep_link': deep_link,
                'message': '신규 사용자입니다. 프로필을 설정해주세요.'
            }), 200
        else:
            # 기존 사용자: 액세스 토큰과 리프레시 토큰 발급
            access_token = AuthUtils.generate_jwt_token(user.id, 'access')
            refresh_token, _ = AuthUtils.create_refresh_token(user.id)
            
            # 딥링크로 앱 실행
            deep_link = AuthConfig.get_deep_link_url('login', 
                                                   accessToken=access_token, 
                                                   refreshToken=refresh_token)
            
            return jsonify({
                'type': 'login',
                'user': user.to_dict(),
                'access_token': access_token,
                'refresh_token': refresh_token,
                'deep_link': deep_link,
                'message': '로그인 성공'
            }), 200
            
    except Exception as e:
        current_app.logger.error(f"매직링크 검증 실패: {str(e)}")
        return jsonify({'error': '서버 오류가 발생했습니다.'}), 500

@auth_bp.route('/register', methods=['POST'])
def register_user():
    """신규 사용자 회원가입 완료"""
    # 지연 import로 순환 참조 방지
    from .models import User, db
    from .utils import AuthUtils
    
    try:
        # 임시 토큰 검증
        auth_header = request.headers.get('Authorization')
        if not auth_header:
            return jsonify({'error': '인증이 필요합니다.'}), 401
        
        temp_token = auth_header.split(' ')[1]
        payload = AuthUtils.verify_jwt_token(temp_token)
        
        if not payload or payload.get('token_type') != 'temp':
            return jsonify({'error': '유효하지 않은 임시 토큰입니다.'}), 401
        
        data = request.get_json()
        
        if not data or 'nickname' not in data:
            return jsonify({'error': '닉네임이 필요합니다.'}), 400
        
        nickname = data['nickname'].strip()
        agreements = data.get('agreements', {})
        
        # 입력값 검증
        if len(nickname) < 2 or len(nickname) > 8:
            return jsonify({'error': '닉네임은 2~8자로 입력해주세요.'}), 400
        
        if not re.match(r'^[a-zA-Z0-9가-힣]+$', nickname):
            return jsonify({'error': '닉네임에는 특수문자를 사용할 수 없습니다.'}), 400
        
        # 필수 약관 동의 확인
        required_agreements = ['service_terms', 'privacy_policy']
        for agreement in required_agreements:
            if not agreements.get(agreement):
                return jsonify({'error': '필수 약관에 동의해주세요.'}), 400
        
        # 닉네임 중복 확인
        if User.query.filter_by(nickname=nickname).first():
            return jsonify({'error': '이미 사용 중인 닉네임입니다.'}), 400
        
        # 사용자 생성
        user = User(
            email=data.get('email'),  # 임시 토큰에서 이메일 추출 필요
            nickname=nickname,
            employee_id=AuthUtils.generate_employee_id()
        )
        
        db.session.add(user)
        db.session.commit()
        
        # 최종 토큰 발급
        access_token = AuthUtils.generate_jwt_token(user.id, 'access')
        refresh_token, _ = AuthUtils.create_refresh_token(user.id)
        
        return jsonify({
            'message': '회원가입이 완료되었습니다.',
            'user': user.to_dict(),
            'access_token': access_token,
            'refresh_token': refresh_token
        }), 201
        
    except Exception as e:
        current_app.logger.error(f"회원가입 실패: {str(e)}")
        return jsonify({'error': '서버 오류가 발생했습니다.'}), 500

@auth_bp.route('/refresh', methods=['POST'])
def refresh_access_token():
    """액세스 토큰 갱신"""
    # 지연 import로 순환 참조 방지
    from .utils import AuthUtils
    
    try:
        data = request.get_json()
        
        if not data or 'refresh_token' not in data:
            return jsonify({'error': '리프레시 토큰이 필요합니다.'}), 400
        
        refresh_token = data['refresh_token']
        
        # 리프레시 토큰 검증
        user = AuthUtils.verify_refresh_token(refresh_token)
        
        if not user:
            return jsonify({'error': '유효하지 않거나 만료된 리프레시 토큰입니다.'}), 401
        
        # 새로운 액세스 토큰 발급
        new_access_token = AuthUtils.generate_jwt_token(user.id, 'access')
        
        return jsonify({
            'access_token': new_access_token,
            'message': '토큰이 갱신되었습니다.'
        }), 200
        
    except Exception as e:
        current_app.logger.error(f"토큰 갱신 실패: {str(e)}")
        return jsonify({'error': '서버 오류가 발생했습니다.'}), 500

@auth_bp.route('/logout', methods=['POST'])
def logout():
    """로그아웃"""
    # 지연 import로 순환 참조 방지
    from .utils import AuthUtils
    
    try:
        data = request.get_json()
        
        if not data or 'refresh_token' not in data:
            return jsonify({'error': '리프레시 토큰이 필요합니다.'}), 400
        
        refresh_token = data['refresh_token']
        
        # 리프레시 토큰 무효화
        if AuthUtils.revoke_refresh_token(refresh_token):
            return jsonify({'message': '로그아웃 되었습니다.'}), 200
        else:
            return jsonify({'error': '유효하지 않은 토큰입니다.'}), 400
            
    except Exception as e:
        current_app.logger.error(f"로그아웃 실패: {str(e)}")
        return jsonify({'error': '서버 오류가 발생했습니다.'}), 500

@auth_bp.route('/profile', methods=['GET'])
def get_profile():
    """사용자 프로필 조회"""
    # 지연 import로 순환 참조 방지
    from .utils import require_auth
    
    @require_auth
    def protected_profile():
        try:
            user = request.current_user
            return jsonify({
                'user': user.to_dict(),
                'message': '프로필 조회 성공'
            }), 200
            
        except Exception as e:
            current_app.logger.error(f"프로필 조회 실패: {str(e)}")
            return jsonify({'error': '서버 오류가 발생했습니다.'}), 500
    
    return protected_profile()

@auth_bp.route('/profile', methods=['PUT'])
def update_profile():
    """사용자 프로필 수정"""
    # 지연 import로 순환 참조 방지
    from .utils import require_auth
    from .models import User, db
    
    @require_auth
    def protected_update():
        try:
            user = request.current_user
            data = request.get_json()
            
            if 'nickname' in data:
                nickname = data['nickname'].strip()
                
                # 입력값 검증
                if len(nickname) < 2 or len(nickname) > 8:
                    return jsonify({'error': '닉네임은 2~8자로 입력해주세요.'}), 400
                
                if not re.match(r'^[a-zA-Z0-9가-힣]+$', nickname):
                    return jsonify({'error': '닉네임에는 특수문자를 사용할 수 없습니다.'}), 400
                
                # 닉네임 중복 확인 (자신 제외)
                existing_user = User.query.filter_by(nickname=nickname).first()
                if existing_user and existing_user.id != user.id:
                    return jsonify({'error': '이미 사용 중인 닉네임입니다.'}), 400
                
                user.nickname = nickname
            
            if 'profile_image' in data:
                user.profile_image = data['profile_image']
            
            user.updated_at = datetime.utcnow()
            db.session.commit()
            
            return jsonify({
                'user': user.to_dict(),
                'message': '프로필이 수정되었습니다.'
            }), 200
            
        except Exception as e:
            current_app.logger.error(f"프로필 수정 실패: {str(e)}")
            return jsonify({'error': '서버 오류가 발생했습니다.'}), 500
    
    return protected_update()

@auth_bp.route('/delete-account', methods=['DELETE'])
def delete_account():
    """계정 삭제"""
    # 지연 import로 순환 참조 방지
    from .utils import require_auth
    from .models import db
    
    @require_auth
    def protected_delete():
        try:
            user = request.current_user
            
            # 사용자 관련 데이터 삭제 (실제로는 비식별화 처리 권장)
            # 여기서는 간단하게 삭제 처리
            
            # 리프레시 토큰들 무효화
            for refresh_token in user.refresh_tokens:
                refresh_token.is_revoked = True
            
            # 사용자 비활성화
            user.is_active = False
            db.session.commit()
            
            return jsonify({'message': '계정이 성공적으로 삭제되었습니다.'}), 200
            
        except Exception as e:
            current_app.logger.error(f"계정 삭제 실패: {str(e)}")
            return jsonify({'error': '서버 오류가 발생했습니다.'}), 500
    
    return protected_delete()

# 에러 핸들러
@auth_bp.errorhandler(404)
def not_found(error):
    return jsonify({'error': '인증 엔드포인트를 찾을 수 없습니다.'}), 404

@auth_bp.errorhandler(500)
def internal_error(error):
    return jsonify({'error': '인증 서버 오류가 발생했습니다.'}), 500

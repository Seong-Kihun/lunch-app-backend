from flask import Blueprint, request, jsonify
from datetime import datetime
from utils.points_system import PointsSystem
from utils.challenge_system import ChallengeSystem
from utils.badge_system import BadgeSystem
from utils.friend_invite_system import FriendInviteSystem

# 블루프린트 생성
points_api = Blueprint('points_api', __name__)

@points_api.route('/points/earn', methods=['POST'])
def earn_points():
    """포인트 획득 API"""
    try:
        data = request.get_json()
        user_id = data.get('user_id')
        activity_type = data.get('activity_type')
        points = data.get('points', 0)
        description = data.get('description')
        
        if not user_id or not activity_type:
            return jsonify({'error': '필수 파라미터가 누락되었습니다.'}), 400
        
        # 포인트 획득 처리
        success = PointsSystem.earn_points(user_id, activity_type, points, description)
        
        if success:
            # 연속 활동 확인 및 추가 포인트 지급
            consecutive_days, bonus_points = PointsSystem.check_consecutive_activity(user_id, activity_type)
            
            if bonus_points > 0:
                PointsSystem.earn_points(
                    user_id, 
                    f"{activity_type}_consecutive_{consecutive_days}", 
                    bonus_points, 
                    f"연속 {consecutive_days}일 {description}"
                )
            
            return jsonify({
                'success': True,
                'message': f'{points}포인트를 획득했습니다.',
                'points_earned': points + bonus_points,
                'consecutive_days': consecutive_days,
                'bonus_points': bonus_points
            })
        else:
            return jsonify({'error': '포인트 획득에 실패했습니다.'}), 500
            
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@points_api.route('/points/status/<user_id>', methods=['GET'])
def get_points_status(user_id):
    """사용자 포인트 상태 조회 API"""
    try:
        from app import User
        
        user = User.query.filter_by(employee_id=user_id).first()
        if not user:
            return jsonify({'error': '사용자를 찾을 수 없습니다.'}), 404
        
        # 레벨 및 칭호 계산
        current_level = PointsSystem.calculate_level(user.total_points)
        level_title = PointsSystem.get_level_title(current_level)
        
        # 다음 레벨까지 필요한 포인트 계산
        next_level_points = 0
        if current_level == 1:
            next_level_points = 5000 - user.total_points
        elif current_level == 2:
            next_level_points = 15000 - user.total_points
        elif current_level == 3:
            next_level_points = 30000 - user.total_points
        elif current_level == 4:
            next_level_points = 50000 - user.total_points
        elif current_level == 5:
            next_level_points = 80000 - user.total_points
        elif current_level == 6:
            next_level_points = 120000 - user.total_points
        elif current_level == 7:
            next_level_points = 200000 - user.total_points
        else:
            next_level_points = 0
        
        # 진행률 계산
        progress_percentage = 0
        if next_level_points > 0:
            if current_level == 1:
                progress_percentage = int((user.total_points / 5000) * 100)
            elif current_level == 2:
                progress_percentage = int(((user.total_points - 5000) / 10000) * 100)
            elif current_level == 3:
                progress_percentage = int(((user.total_points - 15000) / 15000) * 100)
            elif current_level == 4:
                progress_percentage = int(((user.total_points - 30000) / 20000) * 100)
            elif current_level == 5:
                progress_percentage = int(((user.total_points - 50000) / 30000) * 100)
            elif current_level == 6:
                progress_percentage = int(((user.total_points - 80000) / 40000) * 100)
            elif current_level == 7:
                progress_percentage = int(((user.total_points - 120000) / 80000) * 100)
        
        return jsonify({
            'user_id': user_id,
            'total_points': user.total_points,
            'current_level': current_level,
            'level_title': level_title,
            'next_level_points': next_level_points,
            'progress_percentage': progress_percentage
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@points_api.route('/challenges/<user_id>', methods=['GET'])
def get_user_challenges(user_id):
    """사용자 챌린지 목록 조회 API"""
    try:
        challenges = ChallengeSystem.get_user_challenges(user_id)
        
        # 각 챌린지의 진행률 및 완료 여부 확인
        challenge_data = {}
        for challenge_type, challenge_list in challenges.items():
            challenge_data[challenge_type] = []
            for challenge in challenge_list:
                progress, is_completed = ChallengeSystem.check_challenge_progress(user_id, challenge)
                
                challenge_data[challenge_type].append({
                    'id': challenge.challenge_id,
                    'name': challenge.name,
                    'description': challenge.description,
                    'points': challenge.points,
                    'progress': progress,
                    'required': challenge.requirement_count,
                    'is_completed': is_completed,
                    'start_date': challenge.start_date.isoformat(),
                    'end_date': challenge.end_date.isoformat()
                })
        
        return jsonify(challenge_data)
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@points_api.route('/challenges/<user_id>/complete/<challenge_id>', methods=['POST'])
def complete_challenge(user_id, challenge_id):
    """챌린지 완료 처리 API"""
    try:
        # 챌린지 정보 조회
        challenges = ChallengeSystem.get_user_challenges(user_id)
        target_challenge = None
        
        for challenge_list in challenges.values():
            for challenge in challenge_list:
                if challenge.challenge_id == challenge_id:
                    target_challenge = challenge
                    break
            if target_challenge:
                break
        
        if not target_challenge:
            return jsonify({'error': '챌린지를 찾을 수 없습니다.'}), 404
        
        # 진행률 확인
        progress, is_completed = ChallengeSystem.check_challenge_progress(user_id, target_challenge)
        
        if not is_completed:
            return jsonify({'error': '챌린지 조건을 충족하지 않았습니다.'}), 400
        
        # 포인트 지급
        success = PointsSystem.earn_points(
            user_id, 
            f"challenge_{target_challenge.challenge_type.value}", 
            target_challenge.points, 
            f"챌린지 완료: {target_challenge.name}"
        )
        
        if success:
            return jsonify({
                'success': True,
                'message': f'챌린지 "{target_challenge.name}" 완료! {target_challenge.points}포인트 획득!',
                'points_earned': target_challenge.points
            })
        else:
            return jsonify({'error': '포인트 지급에 실패했습니다.'}), 500
            
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@points_api.route('/badges/<user_id>', methods=['GET'])
def get_user_badges(user_id):
    """사용자 배지 목록 조회 API"""
    try:
        badges = BadgeSystem.get_user_badges(user_id)
        return jsonify({'badges': badges})
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@points_api.route('/badges/<user_id>/award/<badge_id>', methods=['POST'])
def award_badge(user_id, badge_id):
    """배지 지급 API"""
    try:
        success = BadgeSystem.award_badge(user_id, badge_id)
        
        if success:
            return jsonify({
                'success': True,
                'message': '새로운 배지를 획득했습니다!'
            })
        else:
            return jsonify({'error': '배지 지급에 실패했습니다.'}), 500
            
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@points_api.route('/friend-invite/create', methods=['POST'])
def create_friend_invite():
    """친구 초대 링크 생성 API"""
    try:
        data = request.get_json()
        inviter_id = data.get('user_id')
        
        if not inviter_id:
            return jsonify({'error': '사용자 ID가 필요합니다.'}), 400
        
        invite_code = FriendInviteSystem.create_invite(inviter_id)
        
        if invite_code:
            return jsonify({
                'success': True,
                'invite_code': invite_code,
                'message': '초대 링크가 생성되었습니다.'
            })
        else:
            return jsonify({'error': '초대 링크 생성에 실패했습니다.'}), 500
            
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@points_api.route('/friend-invite/use', methods=['POST'])
def use_friend_invite():
    """친구 초대 코드 사용 API"""
    try:
        data = request.get_json()
        invite_code = data.get('invite_code')
        invitee_id = data.get('user_id')
        
        if not invite_code or not invitee_id:
            return jsonify({'error': '초대 코드와 사용자 ID가 필요합니다.'}), 400
        
        success = FriendInviteSystem.use_invite_code(invite_code, invitee_id)
        
        if success:
            return jsonify({
                'success': True,
                'message': '초대 코드가 성공적으로 사용되었습니다! 50포인트를 획득했습니다.'
            })
        else:
            return jsonify({'error': '초대 코드 사용에 실패했습니다.'}), 500
            
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@points_api.route('/friend-invite/stats/<user_id>', methods=['GET'])
def get_invite_stats(user_id):
    """초대 통계 조회 API"""
    try:
        stats = FriendInviteSystem.get_invite_stats(user_id)
        return jsonify(stats)
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@points_api.route('/review/like', methods=['POST'])
def like_review():
    """리뷰 좋아요 API - 좋아요를 누른 사용자와 리뷰 작성자 모두에게 포인트 지급"""
    try:
        data = request.get_json()
        liker_id = data.get('liker_id')  # 좋아요를 누른 사용자
        review_id = data.get('review_id')  # 리뷰 ID
        review_author_id = data.get('review_author_id')  # 리뷰 작성자 ID
        
        if not liker_id or not review_id or not review_author_id:
            return jsonify({'error': '필수 정보가 누락되었습니다.'}), 400
        
        # 같은 사용자가 자신의 리뷰에 좋아요를 누르는 것을 방지
        if liker_id == review_author_id:
            return jsonify({'error': '자신의 리뷰에는 좋아요를 누를 수 없습니다.'}), 400
        
        # 좋아요를 누른 사용자에게 포인트 지급 (좋아요 활동)
        liker_success = PointsSystem.earn_points(
            user_id=liker_id,
            activity_type="review_like_given",
            points=5,
            description=f"리뷰 좋아요 활동"
        )
        
        # 리뷰 작성자에게 포인트 지급 (좋아요 받음)
        author_success = PointsSystem.earn_points(
            user_id=review_author_id,
            activity_type="review_like_received",
            points=10,
            description=f"리뷰가 도움이 되었다고 평가받음"
        )
        
        if liker_success and author_success:
            return jsonify({
                'success': True,
                'message': '리뷰 좋아요가 처리되었습니다!',
                'liker_points_earned': 5,
                'author_points_earned': 10
            })
        else:
            return jsonify({'error': '포인트 지급에 실패했습니다.'}), 500
            
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@points_api.route('/review/likes/<review_id>', methods=['GET'])
def get_review_likes(review_id):
    """리뷰 좋아요 수 조회 API"""
    try:
        # 실제 구현에서는 데이터베이스에서 좋아요 수를 조회
        # 현재는 임시로 0 반환
        return jsonify({
            'review_id': review_id,
            'likes_count': 0,
            'message': '좋아요 수 조회 성공'
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

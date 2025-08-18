from datetime import datetime, timedelta
from flask_sqlalchemy import SQLAlchemy
from typing import Optional, Dict, List, Tuple

db = SQLAlchemy()

class PointsSystem:
    """포인트 시스템 관리 클래스"""
    
    @staticmethod
    def calculate_level(points: int) -> int:
        """포인트에 따른 레벨 계산"""
        if points < 5000:
            return 1      # 점심 루키
        elif points < 15000:
            return 2      # 점심 애호가  
        elif points < 30000:
            return 3      # 점심 탐험가
        elif points < 50000:
            return 4      # 점심 전문가
        elif points < 80000:
            return 5      # 점심 마스터
        elif points < 120000:
            return 6      # 점심 전설
        elif points < 200000:
            return 7      # 점심 신화
        else:
            return 8      # 점심 제왕
    
    @staticmethod
    def get_level_title(level: int) -> str:
        """레벨에 따른 칭호 반환 (10레벨마다 변경)"""
        if level <= 10:
            titles = ["점심 루키", "점심 애호가", "점심 탐험가"]
            return titles[(level - 1) % 3]
        elif level <= 20:
            titles = ["점심 전문가", "점심 마스터", "점심 전설"]
            return titles[(level - 1) % 3]
        elif level <= 30:
            titles = ["점심 신화", "점심 제왕", "점심 황제"]
            return titles[(level - 1) % 3]
        elif level <= 40:
            titles = ["점심 성자", "점심 신", "점심 창조주"]
            return titles[(level - 1) % 3]
        elif level <= 50:
            titles = ["점심 우주", "점심 차원", "점심 절대자"]
            return titles[(level - 1) % 3]
        else:
            return "점심 절대자"
    
    @staticmethod
    def get_activity_points(activity_type: str) -> int:
        """활동별 포인트 반환"""
        points_map = {
            # 기존 활동들
            "restaurant_visit": 50,
            "review_write": 30,
            "party_create": 100,
            "party_join": 80,
            "random_lunch": 60,
            "friend_invite": 50,
            "consecutive_visit": 20,
            "consecutive_review": 15,
            "consecutive_party": 25,
            
            # 리뷰 좋아요 관련 활동 추가
            "review_like_given": 5,      # 리뷰에 좋아요를 누른 사용자
            "review_like_received": 10,  # 리뷰를 받은 사용자
            
            # 기타 활동들
            "first_visit": 100,
            "first_review": 50,
            "first_party": 150,
            "weekly_goal": 200,
            "monthly_goal": 500
        }
        
        return points_map.get(activity_type, 0)
    
    @staticmethod
    def earn_points(user_id: str, activity_type: str, points: int, description: str = None) -> bool:
        """포인트 획득 처리"""
        try:
            from app import User, UserActivity, db
            
            # 사용자 포인트 업데이트
            user = User.query.filter_by(employee_id=user_id).first()
            if user:
                user.total_points += points
                user.current_level = PointsSystem.calculate_level(user.total_points)
                db.session.commit()
                
                # 활동 기록
                activity = UserActivity(user_id, activity_type, points, description)
                db.session.add(activity)
                db.session.commit()
                
                return True
        except Exception as e:
            print(f"포인트 획득 실패: {e}")
            db.session.rollback()
            return False
    
    @staticmethod
    def check_consecutive_activity(user_id: str, activity_type: str) -> Tuple[int, int]:
        """연속 활동 확인 및 포인트 계산"""
        try:
            from app import UserActivity, db
            
            # 최근 30일간의 활동 기록 조회
            thirty_days_ago = datetime.utcnow() - timedelta(days=30)
            activities = UserActivity.query.filter(
                UserActivity.user_id == user_id,
                UserActivity.activity_type == activity_type,
                UserActivity.created_at >= thirty_days_ago
            ).order_by(UserActivity.created_at.desc()).all()
            
            if not activities:
                return 0, 0
            
            # 연속 일수 계산
            consecutive_days = 1
            current_date = activities[0].created_at.date()
            
            for activity in activities[1:]:
                if (current_date - activity.created_at.date()).days == 1:
                    consecutive_days += 1
                    current_date = activity.created_at.date()
                else:
                    break
            
            # 연속 활동에 따른 포인트 계산
            if activity_type == 'random_lunch':
                if consecutive_days >= 7:
                    return consecutive_days, 50
                elif consecutive_days >= 3:
                    return consecutive_days, 15
            elif activity_type == 'party':
                if consecutive_days >= 10:
                    return consecutive_days, 80
                elif consecutive_days >= 5:
                    return consecutive_days, 30
            elif activity_type == 'review':
                if consecutive_days >= 10:
                    return consecutive_days, 60
                elif consecutive_days >= 5:
                    return consecutive_days, 25
            
            return consecutive_days, 0
            
        except Exception as e:
            print(f"연속 활동 확인 실패: {e}")
            return 0, 0

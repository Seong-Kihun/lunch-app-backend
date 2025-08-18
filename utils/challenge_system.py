from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from enum import Enum

class ChallengeType(Enum):
    """챌린지 유형"""
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    SPECIAL = "special"

class ChallengeStatus(Enum):
    """챌린지 상태"""
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    EXPIRED = "expired"

class Challenge:
    """챌린지 정보 클래스"""
    
    def __init__(self, challenge_id: str, name: str, description: str, 
                 challenge_type: ChallengeType, points: int, requirements: Dict,
                 start_date: datetime, end_date: datetime):
        self.challenge_id = challenge_id
        self.name = name
        self.description = description
        self.challenge_type = challenge_type
        self.points = points
        self.requirements = requirements
        self.start_date = start_date
        self.end_date = end_date
        self.status = ChallengeStatus.IN_PROGRESS

class ChallengeSystem:
    """챌린지 시스템 관리 클래스"""
    
    @staticmethod
    def get_daily_challenges() -> List[Challenge]:
        """일일 미션 목록 반환"""
        today = datetime.now()
        tomorrow = today + timedelta(days=1)
        tomorrow = tomorrow.replace(hour=0, minute=0, second=0, microsecond=0)
        
        challenges = [
            Challenge(
                "daily_review", "오늘의 기록", "오늘 먹은 음식 리뷰 작성하기",
                ChallengeType.DAILY, 25, {"review_count": 1}, today, tomorrow
            ),
            Challenge(
                "daily_photo", "사진 작가", "리뷰에 사진 첨부하기",
                ChallengeType.DAILY, 30, {"photo_review_count": 1}, today, tomorrow
            ),
            Challenge(
                "daily_social", "소통하기", "파티나 랜덤런치 참여하기",
                ChallengeType.DAILY, 40, {"social_activity_count": 1}, today, tomorrow
            ),
            Challenge(
                "daily_friend", "친구와 함께", "친구와 함께 식사하기",
                ChallengeType.DAILY, 35, {"friend_meal_count": 1}, today, tomorrow
            ),
            Challenge(
                "daily_discovery", "오늘의 발견", "새로운 음식 종류 리뷰하기",
                ChallengeType.DAILY, 20, {"new_food_review_count": 1}, today, tomorrow
            ),
            Challenge(
                "daily_time", "기분 전환", "다른 시간대에 식사하기",
                ChallengeType.DAILY, 15, {"different_time_meal": 1}, today, tomorrow
            ),
            Challenge(
                "daily_restaurant", "오늘의 맛", "평소와 다른 음식점 방문하기",
                ChallengeType.DAILY, 30, {"different_restaurant": 1}, today, tomorrow
            )
        ]
        
        return challenges
    
    @staticmethod
    def get_weekly_challenges() -> List[Challenge]:
        """주간 미션 목록 반환"""
        today = datetime.now()
        week_start = today - timedelta(days=today.weekday())
        week_start = week_start.replace(hour=0, minute=0, second=0, microsecond=0)
        week_end = week_start + timedelta(days=7)
        
        challenges = [
            Challenge(
                "weekly_explorer", "탐험가", "이번 주 3개 파티 참여하기",
                ChallengeType.WEEKLY, 200, {"party_participate_count": 3}, week_start, week_end
            ),
            Challenge(
                "weekly_reviewer", "리뷰어", "이번 주 5개 리뷰 작성하기",
                ChallengeType.WEEKLY, 150, {"review_write_count": 5}, week_start, week_end
            ),
            Challenge(
                "weekly_social", "소셜 플레이어", "이번 주 2번 랜덤런치 참여하기",
                ChallengeType.WEEKLY, 120, {"random_lunch_count": 2}, week_start, week_end
            ),
            Challenge(
                "weekly_photographer", "사진 작가", "이번 주 3개 사진 리뷰 작성하기",
                ChallengeType.WEEKLY, 100, {"photo_review_count": 3}, week_start, week_end
            ),
            Challenge(
                "weekly_new_meeting", "새로운 만남", "이번 주 처음 만난 동료와 식사하기",
                ChallengeType.WEEKLY, 180, {"new_colleague_meal": 1}, week_start, week_end
            )
        ]
        
        return challenges
    
    @staticmethod
    def get_monthly_challenges() -> List[Challenge]:
        """월간 미션 목록 반환"""
        today = datetime.now()
        month_start = today.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        if today.month == 12:
            month_end = today.replace(year=today.year + 1, month=1, day=1)
        else:
            month_end = today.replace(month=today.month + 1, day=1)
        
        challenges = [
            Challenge(
                "monthly_party_master", "파티 마스터", "이번 달 10개 파티 참여하기",
                ChallengeType.MONTHLY, 800, {"party_participate_count": 10}, month_start, month_end
            ),
            Challenge(
                "monthly_review_master", "리뷰 마스터", "이번 달 20개 리뷰 작성하기",
                ChallengeType.MONTHLY, 600, {"review_write_count": 20}, month_start, month_end
            ),
            Challenge(
                "monthly_random_lunch_master", "랜덤런치 마스터", "이번 달 8번 랜덤런치 참여하기",
                ChallengeType.MONTHLY, 500, {"random_lunch_count": 8}, month_start, month_end
            ),
            Challenge(
                "monthly_explorer", "탐험가", "이번 달 15개 다른 식당 방문하기",
                ChallengeType.MONTHLY, 700, {"different_restaurant_count": 15}, month_start, month_end
            ),
            Challenge(
                "monthly_social_master", "소셜 마스터", "이번 달 30명의 다른 동료와 식사하기",
                ChallengeType.MONTHLY, 1000, {"different_colleague_count": 30}, month_start, month_end
            )
        ]
        
        return challenges
    
    @staticmethod
    def get_special_challenges() -> List[Challenge]:
        """특별 미션 목록 반환 (상시 진행)"""
        challenges = [
            Challenge(
                "special_first_visit", "첫 발걸음", "첫 식당 방문",
                ChallengeType.SPECIAL, 100, {"first_restaurant_visit": 1}, 
                datetime.min, datetime.max
            ),
            Challenge(
                "special_first_review", "첫 이야기", "첫 리뷰 작성",
                ChallengeType.SPECIAL, 80, {"first_review": 1}, 
                datetime.min, datetime.max
            ),
            Challenge(
                "special_first_party", "첫 만남", "첫 파티 참여",
                ChallengeType.SPECIAL, 120, {"first_party": 1}, 
                datetime.min, datetime.max
            ),
            Challenge(
                "special_first_random_lunch", "첫 도전", "첫 랜덤런치",
                ChallengeType.SPECIAL, 150, {"first_random_lunch": 1}, 
                datetime.min, datetime.max
            ),
            Challenge(
                "special_friend_invite", "친구 초대", "친구 초대하기",
                ChallengeType.SPECIAL, 200, {"friend_invite": 1}, 
                datetime.min, datetime.max
            )
        ]
        
        return challenges
    
    @staticmethod
    def check_challenge_progress(user_id: str, challenge: Challenge) -> Tuple[int, bool]:
        """챌린지 진행률 확인"""
        try:
            from app import UserActivity, db
            
            # 챌린지 기간 내 활동 확인
            activities = UserActivity.query.filter(
                UserActivity.user_id == user_id,
                UserActivity.created_at >= challenge.start_date,
                UserActivity.created_at < challenge.end_date
            ).all()
            
            # 요구사항에 따른 진행률 계산
            progress = 0
            for requirement_type, required_count in challenge.requirements.items():
                if requirement_type == "review_count":
                    progress = len([a for a in activities if a.activity_type == "review_write"])
                elif requirement_type == "photo_review_count":
                    progress = len([a for a in activities if a.activity_type == "review_photo"])
                elif requirement_type == "social_activity_count":
                    progress = len([a for a in activities if a.activity_type in ["party_participate", "random_lunch_participate"]])
                elif requirement_type == "friend_meal_count":
                    progress = len([a for a in activities if a.activity_type == "friend_meal"])
                elif requirement_type == "new_food_review_count":
                    progress = len([a for a in activities if a.activity_type == "new_food_review"])
                elif requirement_type == "different_time_meal":
                    progress = len([a for a in activities if a.activity_type == "different_time_meal"])
                elif requirement_type == "different_restaurant":
                    progress = len([a for a in activities if a.activity_type == "different_restaurant"])
                elif requirement_type == "party_participate_count":
                    progress = len([a for a in activities if a.activity_type == "party_participate"])
                elif requirement_type == "review_write_count":
                    progress = len([a for a in activities if a.activity_type == "review_write"])
                elif requirement_type == "random_lunch_count":
                    progress = len([a for a in activities if a.activity_type == "random_lunch_participate"])
                elif requirement_type == "new_colleague_meal":
                    progress = len([a for a in activities if a.activity_type == "new_colleague_meal"])
                elif requirement_type == "different_restaurant_count":
                    progress = len([a for a in activities if a.activity_type == "different_restaurant"])
                elif requirement_type == "different_colleague_count":
                    progress = len([a for a in activities if a.activity_type == "different_colleague_meal"])
                elif requirement_type == "first_restaurant_visit":
                    progress = len([a for a in activities if a.activity_type == "first_restaurant_visit"])
                elif requirement_type == "first_review":
                    progress = len([a for a in activities if a.activity_type == "first_review"])
                elif requirement_type == "first_party":
                    progress = len([a for a in activities if a.activity_type == "first_party"])
                elif requirement_type == "first_random_lunch":
                    progress = len([a for a in activities if a.activity_type == "first_random_lunch"])
                elif requirement_type == "friend_invite":
                    progress = len([a for a in activities if a.activity_type == "friend_invite"])
            
            # 완료 여부 확인
            is_completed = progress >= required_count
            
            return progress, is_completed
            
        except Exception as e:
            print(f"챌린지 진행률 확인 실패: {e}")
            return 0, False
    
    @staticmethod
    def get_user_challenges(user_id: str) -> Dict[str, List[Challenge]]:
        """사용자의 모든 챌린지 반환"""
        return {
            "daily": ChallengeSystem.get_daily_challenges(),
            "weekly": ChallengeSystem.get_weekly_challenges(),
            "monthly": ChallengeSystem.get_monthly_challenges(),
            "special": ChallengeSystem.get_special_challenges()
        }

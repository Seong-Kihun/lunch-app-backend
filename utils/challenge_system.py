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
    
    def __init__(self, id: str, name: str, description: str, points: int, 
                 type: ChallengeType, requirements: Dict, category: str):
        self.id = id
        self.name = name
        self.description = description
        self.points = points
        self.type = type
        self.requirements = requirements
        self.category = category
        self.created_at = datetime.now()
        
        # 타입에 따른 만료 시간 설정
        if type == ChallengeType.DAILY:
            self.expires_at = self.created_at.replace(hour=23, minute=59, second=59, microsecond=999999)
        elif type == ChallengeType.WEEKLY:
            # 이번 주 일요일 자정
            days_until_sunday = (6 - self.created_at.weekday()) % 7
            self.expires_at = (self.created_at + timedelta(days=days_until_sunday)).replace(hour=23, minute=59, second=59, microsecond=999999)
        elif type == ChallengeType.MONTHLY:
            # 이번 달 마지막 날
            if self.created_at.month == 12:
                next_month = self.created_at.replace(year=self.created_at.year + 1, month=1, day=1)
            else:
                next_month = self.created_at.replace(month=self.created_at.month + 1, day=1)
            self.expires_at = (next_month - timedelta(days=1)).replace(hour=23, minute=59, second=59, microsecond=999999)
        else:  # SPECIAL
            self.expires_at = self.created_at + timedelta(days=30)  # 기본 30일

class ChallengeSystem:
    """챌린지 시스템 관리 클래스"""
    
    @staticmethod
    def get_daily_challenges() -> List[Challenge]:
        """일일 챌린지 목록 반환"""
        return [
            Challenge(
                id="daily_1",
                name="오늘의 기록",
                description="오늘 점심 메뉴를 기록하기",
                points=20,
                type=ChallengeType.DAILY,
                requirements={"action": "record_lunch", "count": 1},
                category="기록"
            ),
            Challenge(
                id="daily_2",
                name="사진 작가",
                description="점심 사진을 찍어서 공유하기",
                points=30,
                type=ChallengeType.DAILY,
                requirements={"action": "share_photo", "count": 1},
                category="공유"
            ),
            Challenge(
                id="daily_3",
                name="소통하기",
                description="파티나 랜덤런치에 참여하기",
                points=40,
                type=ChallengeType.DAILY,
                requirements={"action": "join_party", "count": 1},
                category="소통"
            ),
            Challenge(
                id="daily_4",
                name="맛집 탐험",
                description="새로운 식당에 방문하기",
                points=50,
                type=ChallengeType.DAILY,
                requirements={"action": "visit_new_restaurant", "count": 1},
                category="탐험"
            ),
            Challenge(
                id="daily_5",
                name="리뷰 작성",
                description="방문한 식당에 리뷰 작성하기",
                points=25,
                type=ChallengeType.DAILY,
                requirements={"action": "write_review", "count": 1},
                category="리뷰"
            ),
            Challenge(
                id="daily_6",
                name="친구와 식사",
                description="친구와 함께 점심 먹기",
                points=35,
                type=ChallengeType.DAILY,
                requirements={"action": "dine_with_friend", "count": 1},
                category="소통"
            ),
            Challenge(
                id="daily_7",
                name="건강한 선택",
                description="건강한 메뉴 선택하기",
                points=20,
                type=ChallengeType.DAILY,
                requirements={"action": "healthy_choice", "count": 1},
                category="건강"
            ),
            Challenge(
                id="daily_8",
                name="시간 지키기",
                description="점심 시간을 정확히 지키기",
                points=15,
                type=ChallengeType.DAILY,
                requirements={"action": "on_time_lunch", "count": 1},
                category="습관"
            )
        ]
    
    @staticmethod
    def get_weekly_challenges() -> List[Challenge]:
        """주간 챌린지 목록 반환"""
        return [
            Challenge(
                id="weekly_1",
                name="맛집 탐험가",
                description="일주일 동안 5개의 다른 식당 방문하기",
                points=150,
                type=ChallengeType.WEEKLY,
                requirements={"action": "visit_restaurants", "count": 5},
                category="탐험"
            ),
            Challenge(
                id="weekly_2",
                name="소셜 플레이어",
                description="일주일 동안 3번의 파티나 랜덤런치 참여하기",
                points=200,
                type=ChallengeType.WEEKLY,
                requirements={"action": "join_activities", "count": 3},
                category="소통"
            ),
            Challenge(
                id="weekly_3",
                name="리뷰 마스터",
                description="일주일 동안 7개의 리뷰 작성하기",
                points=180,
                type=ChallengeType.WEEKLY,
                requirements={"action": "write_reviews", "count": 7},
                category="리뷰"
            ),
            Challenge(
                id="weekly_4",
                name="친구 사랑",
                description="일주일 동안 5명의 다른 친구와 식사하기",
                points=250,
                type=ChallengeType.WEEKLY,
                requirements={"action": "dine_with_friends", "count": 5},
                category="소통"
            ),
            Challenge(
                id="weekly_5",
                name="사진 컬렉터",
                description="일주일 동안 10장의 점심 사진 촬영하기",
                points=120,
                type=ChallengeType.WEEKLY,
                requirements={"action": "take_photos", "count": 10},
                category="기록"
            ),
            Challenge(
                id="weekly_6",
                name="건강 관리",
                description="일주일 동안 5번의 건강한 메뉴 선택하기",
                points=100,
                type=ChallengeType.WEEKLY,
                requirements={"action": "healthy_choices", "count": 5},
                category="건강"
            ),
            Challenge(
                id="weekly_7",
                name="시간 관리",
                description="일주일 동안 5번의 정시 점심 시간 지키기",
                points=80,
                type=ChallengeType.WEEKLY,
                requirements={"action": "on_time_lunches", "count": 5},
                category="습관"
            )
        ]
    
    @staticmethod
    def get_monthly_challenges() -> List[Challenge]:
        """월간 챌린지 목록 반환"""
        return [
            Challenge(
                id="monthly_1",
                name="맛집 마스터",
                description="한 달 동안 20개의 다른 식당 방문하기",
                points=500,
                type=ChallengeType.MONTHLY,
                requirements={"action": "visit_restaurants", "count": 20},
                category="탐험"
            ),
            Challenge(
                id="monthly_2",
                name="소셜 스타",
                description="한 달 동안 15번의 파티나 랜덤런치 참여하기",
                points=600,
                type=ChallengeType.MONTHLY,
                requirements={"action": "join_activities", "count": 15},
                category="소통"
            ),
            Challenge(
                id="monthly_3",
                name="리뷰 전문가",
                description="한 달 동안 30개의 리뷰 작성하기",
                points=400,
                type=ChallengeType.MONTHLY,
                requirements={"action": "write_reviews", "count": 30},
                category="리뷰"
            ),
            Challenge(
                id="monthly_4",
                name="친구 네트워커",
                description="한 달 동안 20명의 다른 친구와 식사하기",
                points=800,
                type=ChallengeType.MONTHLY,
                requirements={"action": "dine_with_friends", "count": 20},
                category="소통"
            ),
            Challenge(
                id="monthly_5",
                name="사진 아티스트",
                description="한 달 동안 50장의 점심 사진 촬영하기",
                points=300,
                type=ChallengeType.MONTHLY,
                requirements={"action": "take_photos", "count": 50},
                category="기록"
            ),
            Challenge(
                id="monthly_6",
                name="건강 전문가",
                description="한 달 동안 20번의 건강한 메뉴 선택하기",
                points=250,
                type=ChallengeType.MONTHLY,
                requirements={"action": "healthy_choices", "count": 20},
                category="건강"
            ),
            Challenge(
                id="monthly_7",
                name="시간 관리자",
                description="한 달 동안 20번의 정시 점심 시간 지키기",
                points=200,
                type=ChallengeType.MONTHLY,
                requirements={"action": "on_time_lunches", "count": 20},
                category="습관"
            )
        ]
    
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

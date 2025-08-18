from typing import Dict, List, Optional, Tuple
from enum import Enum

class BadgeCategory(Enum):
    """배지 카테고리"""
    VISIT = "visit"
    REVIEW = "review"
    PARTY = "party"
    RANDOM_LUNCH = "random_lunch"
    FOOD_PREFERENCE = "food_preference"
    SOCIAL = "social"

class Badge:
    """배지 정보 클래스"""
    
    def __init__(self, badge_id: str, name: str, description: str, 
                 category: BadgeCategory, icon: str, color: str, 
                 requirement_type: str, requirement_count: int):
        self.badge_id = badge_id
        self.name = name
        self.description = description
        self.category = category
        self.icon = icon
        self.color = color
        self.requirement_type = requirement_type
        self.requirement_count = requirement_count

class BadgeSystem:
    """배지 시스템 관리 클래스"""
    
    @staticmethod
    def get_all_badges() -> List[Badge]:
        """모든 배지 목록 반환"""
        badges = [
            # 방문 관련 배지
            Badge("first_visit", "첫 발걸음", "첫 식당 방문", 
                  BadgeCategory.VISIT, "footsteps", "#10B981", "first_restaurant_visit", 1),
            Badge("explorer_start", "탐험의 시작", "10개 식당 방문", 
                  BadgeCategory.VISIT, "map", "#3B82F6", "restaurant_visit_count", 10),
            Badge("restaurant_hunter", "맛집 헌터", "50개 식당 방문", 
                  BadgeCategory.VISIT, "search", "#F59E0B", "restaurant_visit_count", 50),
            Badge("map_maker", "지도 제작자", "100개 식당 방문", 
                  BadgeCategory.VISIT, "map-outline", "#8B5CF6", "restaurant_visit_count", 100),
            
            # 리뷰 관련 배지
            Badge("first_story", "첫 이야기", "첫 리뷰 작성", 
                  BadgeCategory.REVIEW, "chatbubble", "#10B981", "first_review", 1),
            Badge("storyteller", "이야기꾼", "10개 리뷰", 
                  BadgeCategory.REVIEW, "chatbubbles", "#3B82F6", "review_count", 10),
            Badge("review_master", "리뷰 마스터", "50개 리뷰", 
                  BadgeCategory.REVIEW, "star", "#F59E0B", "review_count", 50),
            Badge("photographer", "사진 작가", "20개 사진 리뷰", 
                  BadgeCategory.REVIEW, "camera", "#8B5CF6", "photo_review_count", 20),
            Badge("keyword_master", "키워드 마스터", "100개 키워드 사용", 
                  BadgeCategory.REVIEW, "pricetag", "#06B6D4", "keyword_count", 100),
            Badge("emotion_expresser", "감정 표현가", "다양한 감정 표현 리뷰", 
                  BadgeCategory.REVIEW, "heart", "#EF4444", "emotion_variety", 5),
            
            # 파티 관련 배지
            Badge("first_meeting", "첫 만남", "첫 파티 참여", 
                  BadgeCategory.PARTY, "people", "#10B981", "first_party", 1),
            Badge("social_butterfly", "사교적", "10개 파티 참여", 
                  BadgeCategory.PARTY, "people-circle", "#3B82F6", "party_count", 10),
            Badge("party_lover", "파티 애호가", "50개 파티 참여", 
                  BadgeCategory.PARTY, "people-circle-outline", "#F59E0B", "party_count", 50),
            Badge("party_host", "파티 호스트", "20개 파티 생성", 
                  BadgeCategory.PARTY, "person-add", "#8B5CF6", "party_create_count", 20),
            Badge("popular_person", "인기 인사", "100명 이상이 참여한 파티 생성", 
                  BadgeCategory.PARTY, "trophy", "#06B6D4", "popular_party", 1),
            
            # 랜덤런치 관련 배지
            Badge("first_challenge", "첫 도전", "첫 랜덤런치", 
                  BadgeCategory.RANDOM_LUNCH, "shuffle", "#10B981", "first_random_lunch", 1),
            Badge("new_meeting", "새로운 만남", "20번 랜덤런치", 
                  BadgeCategory.RANDOM_LUNCH, "shuffle-outline", "#3B82F6", "random_lunch_count", 20),
            Badge("random_lunch_master", "랜덤런치 마스터", "100번 랜덤런치", 
                  BadgeCategory.RANDOM_LUNCH, "shuffle", "#F59E0B", "random_lunch_count", 100),
            Badge("social_player", "소셜 플레이어", "50명의 다른 동료와 랜덤런치", 
                  BadgeCategory.RANDOM_LUNCH, "people", "#8B5CF6", "different_colleague_random_lunch", 50),
            
            # 음식 취향 배지
            Badge("korean_food_lover", "한식 애호가", "한식 리뷰 30개", 
                  BadgeCategory.FOOD_PREFERENCE, "restaurant", "#10B981", "korean_food_review_count", 30),
            Badge("western_food_master", "양식 마스터", "양식 리뷰 30개", 
                  BadgeCategory.FOOD_PREFERENCE, "pizza", "#3B82F6", "western_food_review_count", 30),
            Badge("chinese_food_expert", "중식 전문가", "중식 리뷰 30개", 
                  BadgeCategory.FOOD_PREFERENCE, "fast-food", "#F59E0B", "chinese_food_review_count", 30),
            Badge("japanese_food_lover", "일식 애호가", "일식 리뷰 30개", 
                  BadgeCategory.FOOD_PREFERENCE, "fish", "#8B5CF6", "japanese_food_review_count", 30),
            Badge("cafe_hunter", "카페 헌터", "카페 리뷰 20개", 
                  BadgeCategory.FOOD_PREFERENCE, "cafe", "#06B6D4", "cafe_review_count", 20),
            Badge("dessert_master", "디저트 마스터", "디저트 리뷰 20개", 
                  BadgeCategory.FOOD_PREFERENCE, "ice-cream", "#EF4444", "dessert_review_count", 20),
            
            # 사회적 배지
            Badge("friend_lover", "친구 사랑", "10명의 친구와 식사", 
                  BadgeCategory.SOCIAL, "heart", "#10B981", "friend_meal_count", 10),
            Badge("new_meeting_expert", "새로운 만남", "처음 만난 동료와 식사 20회", 
                  BadgeCategory.SOCIAL, "person-add", "#3B82F6", "new_colleague_meal_count", 20),
            Badge("mentor", "멘토", "신입 동료와 식사 15회", 
                  BadgeCategory.SOCIAL, "school", "#F59E0B", "junior_colleague_meal_count", 15)
        ]
        
        return badges
    
    @staticmethod
    def get_badges_by_category(category: BadgeCategory) -> List[Badge]:
        """카테고리별 배지 목록 반환"""
        all_badges = BadgeSystem.get_all_badges()
        return [badge for badge in all_badges if badge.category == category]
    
    @staticmethod
    def check_badge_earned(user_id: str, badge: Badge) -> Tuple[bool, int]:
        """배지 획득 여부 및 진행률 확인"""
        try:
            from app import UserActivity, db
            
            # 사용자 활동 기록 조회
            activities = UserActivity.query.filter_by(user_id=user_id).all()
            
            # 요구사항에 따른 진행률 계산
            progress = 0
            if badge.requirement_type == "first_restaurant_visit":
                progress = len([a for a in activities if a.activity_type == "first_restaurant_visit"])
            elif badge.requirement_type == "restaurant_visit_count":
                progress = len([a for a in activities if a.activity_type == "restaurant_visit"])
            elif badge.requirement_type == "first_review":
                progress = len([a for a in activities if a.activity_type == "first_review"])
            elif badge.requirement_type == "review_count":
                progress = len([a for a in activities if a.activity_type == "review_write"])
            elif badge.requirement_type == "photo_review_count":
                progress = len([a for a in activities if a.activity_type == "review_photo"])
            elif badge.requirement_type == "keyword_count":
                progress = len([a for a in activities if a.activity_type == "keyword_used"])
            elif badge.requirement_type == "emotion_variety":
                progress = len(set([a.description for a in activities if a.activity_type == "emotion_expression"]))
            elif badge.requirement_type == "first_party":
                progress = len([a for a in activities if a.activity_type == "first_party"])
            elif badge.requirement_type == "party_count":
                progress = len([a for a in activities if a.activity_type == "party_participate"])
            elif badge.requirement_type == "party_create_count":
                progress = len([a for a in activities if a.activity_type == "party_create"])
            elif badge.requirement_type == "popular_party":
                progress = len([a for a in activities if a.activity_type == "popular_party_create"])
            elif badge.requirement_type == "first_random_lunch":
                progress = len([a for a in activities if a.activity_type == "first_random_lunch"])
            elif badge.requirement_type == "random_lunch_count":
                progress = len([a for a in activities if a.activity_type == "random_lunch_participate"])
            elif badge.requirement_type == "different_colleague_random_lunch":
                progress = len(set([a.description for a in activities if a.activity_type == "random_lunch_participate"]))
            elif badge.requirement_type == "korean_food_review_count":
                progress = len([a for a in activities if a.activity_type == "korean_food_review"])
            elif badge.requirement_type == "western_food_review_count":
                progress = len([a for a in activities if a.activity_type == "western_food_review"])
            elif badge.requirement_type == "chinese_food_review_count":
                progress = len([a for a in activities if a.activity_type == "chinese_food_review"])
            elif badge.requirement_type == "japanese_food_review_count":
                progress = len([a for a in activities if a.activity_type == "japanese_food_review"])
            elif badge.requirement_type == "cafe_review_count":
                progress = len([a for a in activities if a.activity_type == "cafe_review"])
            elif badge.requirement_type == "dessert_review_count":
                progress = len([a for a in activities if a.activity_type == "dessert_review"])
            elif badge.requirement_type == "friend_meal_count":
                progress = len([a for a in activities if a.activity_type == "friend_meal"])
            elif badge.requirement_type == "new_colleague_meal_count":
                progress = len([a for a in activities if a.activity_type == "new_colleague_meal"])
            elif badge.requirement_type == "junior_colleague_meal_count":
                progress = len([a for a in activities if a.activity_type == "junior_colleague_meal"])
            
            # 배지 획득 여부 확인
            is_earned = progress >= badge.requirement_count
            
            return is_earned, progress
            
        except Exception as e:
            print(f"배지 확인 실패: {e}")
            return False, 0
    
    @staticmethod
    def get_user_badges(user_id: str) -> List[Dict]:
        """사용자의 배지 정보 반환"""
        try:
            from app import UserBadge, db
            
            # 사용자가 획득한 배지 조회
            user_badges = UserBadge.query.filter_by(user_id=user_id).all()
            earned_badge_ids = [ub.badge_id for ub in user_badges]
            
            # 모든 배지 정보 가져오기
            all_badges = BadgeSystem.get_all_badges()
            
            # 사용자별 배지 정보 구성
            user_badge_info = []
            for badge in all_badges:
                is_earned = badge.id in earned_badge_ids
                progress = 0
                
                if not is_earned:
                    # 미획득 배지의 경우 진행률 확인
                    _, progress = BadgeSystem.check_badge_earned(user_id, badge)
                
                user_badge_info.append({
                    "id": badge.badge_id,
                    "name": badge.name,
                    "description": badge.description,
                    "icon": badge.icon,
                    "color": badge.color,
                    "category": badge.category.value,
                    "is_earned": is_earned,
                    "progress": progress,
                    "required": badge.requirement_count
                })
            
            return user_badge_info
            
        except Exception as e:
            print(f"사용자 배지 정보 조회 실패: {e}")
            return []
    
    @staticmethod
    def award_badge(user_id: str, badge_id: str) -> bool:
        """배지 지급"""
        try:
            from app import UserBadge, db
            
            # 이미 획득한 배지인지 확인
            existing_badge = UserBadge.query.filter_by(
                user_id=user_id, 
                badge_id=badge_id
            ).first()
            
            if existing_badge:
                return False  # 이미 획득한 배지
            
            # 새 배지 지급
            new_badge = UserBadge(user_id=user_id, badge_id=badge_id)
            db.session.add(new_badge)
            db.session.commit()
            
            return True
            
        except Exception as e:
            print(f"배지 지급 실패: {e}")
            db.session.rollback()
            return False

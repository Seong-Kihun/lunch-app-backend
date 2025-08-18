import secrets
import hashlib
from datetime import datetime, timedelta
from typing import Optional, Dict, List
from flask_sqlalchemy import SQLAlchemy

# db 객체는 app.py에서 가져와야 함
db = None

class FriendInvite:
    """친구 초대 정보 클래스"""
    
    def __init__(self, invite_id: str, inviter_id: str, invite_code: str, 
                 created_at: datetime, expires_at: datetime, is_used: bool = False):
        self.invite_id = invite_id
        self.inviter_id = inviter_id
        self.invite_code = invite_code
        self.created_at = created_at
        self.expires_at = expires_at
        self.is_used = is_used

class FriendInviteSystem:
    """친구 초대 시스템 관리 클래스"""
    
    @staticmethod
    def set_db(database):
        """데이터베이스 객체 설정"""
        global db
        db = database
    
    @staticmethod
    def generate_invite_code() -> str:
        """초대 코드 생성"""
        # 8자리 랜덤 코드 생성
        return secrets.token_urlsafe(6)[:8].upper()
    
    @staticmethod
    def create_invite(inviter_id: str) -> Optional[str]:
        """초대 링크 생성"""
        try:
            if not db:
                print("데이터베이스가 초기화되지 않았습니다.")
                return None
            
            # 초대 코드 생성
            invite_code = FriendInviteSystem.generate_invite_code()
            
            # 만료 시간 설정 (7일)
            expires_at = datetime.utcnow() + timedelta(days=7)
            
            # 초대 정보 저장
            from app import FriendInvite
            
            invite = FriendInvite(
                invite_id=hashlib.md5(f"{inviter_id}_{datetime.utcnow()}".encode()).hexdigest(),
                inviter_id=inviter_id,
                invite_code=invite_code,
                created_at=datetime.utcnow(),
                expires_at=expires_at
            )
            
            # 데이터베이스에 저장
            db.session.add(invite)
            db.session.commit()
            
            return invite_code
            
        except Exception as e:
            print(f"초대 링크 생성 실패: {e}")
            if db and db.session:
                db.session.rollback()
            return None
    
    @staticmethod
    def validate_invite_code(invite_code: str) -> Optional[str]:
        """초대 코드 검증 및 초대자 ID 반환"""
        try:
            # 초대 코드 검증 로직
            # 실제 구현 시 데이터베이스에서 조회
            
            # 임시로 하드코딩된 코드 반환 (테스트용)
            if invite_code == "TEST1234":
                return "KOICA001"
            
            return None
            
        except Exception as e:
            print(f"초대 코드 검증 실패: {e}")
            return None
    
    @staticmethod
    def use_invite_code(invite_code: str, invitee_id: str) -> bool:
        """초대 코드 사용"""
        try:
            # 초대 코드 사용 처리
            # 실제 구현 시 데이터베이스 업데이트
            
            # 포인트 지급
            from .points_system import PointsSystem
            success = PointsSystem.earn_points(
                user_id=invitee_id,
                activity_type="friend_invite",
                points=50,
                description="친구 초대 보상"
            )
            
            if success:
                # 초대자에게도 포인트 지급
                inviter_id = FriendInviteSystem.validate_invite_code(invite_code)
                if inviter_id:
                    PointsSystem.earn_points(
                        user_id=inviter_id,
                        activity_type="friend_invite",
                        points=50,
                        description="친구 초대 성공 보상"
                    )
                
                return True
            
            return False
            
        except Exception as e:
            print(f"초대 코드 사용 실패: {e}")
            return False
    
    @staticmethod
    def get_user_invites(user_id: str) -> List[Dict]:
        """사용자의 초대 목록 조회"""
        try:
            # 사용자의 초대 목록 조회
            # 실제 구현 시 데이터베이스에서 조회
            
            # 임시 데이터 반환
            return [
                {
                    "invite_id": "invite_1",
                    "invite_code": "ABC12345",
                    "created_at": datetime.utcnow().isoformat(),
                    "expires_at": (datetime.utcnow() + timedelta(days=7)).isoformat(),
                    "is_used": False
                }
            ]
            
        except Exception as e:
            print(f"초대 목록 조회 실패: {e}")
            return []
    
    @staticmethod
    def get_invite_stats(user_id: str) -> Dict:
        """사용자의 초대 통계 조회"""
        try:
            # 초대 통계 조회
            # 실제 구현 시 데이터베이스에서 계산
            
            return {
                "total_invites": 5,
                "successful_invites": 3,
                "pending_invites": 2,
                "total_points_earned": 150
            }
            
        except Exception as e:
            print(f"초대 통계 조회 실패: {e}")
            return {
                "total_invites": 0,
                "successful_invites": 0,
                "pending_invites": 0,
                "total_points_earned": 0
            }

import random
import json
from datetime import datetime, date, timedelta, time as dt_time
from flask import Flask, request, jsonify, current_app
from flask_sqlalchemy import SQLAlchemy
from flask_cors import CORS
from flask_socketio import SocketIO, emit, join_room, leave_room
from sqlalchemy import desc, or_, and_, func, text
import pandas as pd
import os
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}})

app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///site.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = 'your-secret-key-here'
db = SQLAlchemy(app)
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')

# 추천 그룹 캐시 (사용자별, 날짜별)
RECOMMENDATION_CACHE = {}
CACHE_GENERATION_DATE = None

# --- 유틸리티 함수 ---
def get_seoul_today():
    """한국 시간의 오늘 날짜를 datetime.date 타입으로 반환"""
    korean_time = datetime.now() + timedelta(hours=9)
    return korean_time.date()

def generate_recommendation_cache():
    """1달간의 추천 그룹을 미리 생성하여 캐시에 저장"""
    global RECOMMENDATION_CACHE, CACHE_GENERATION_DATE
    
    today = get_seoul_today()
    current_date_str = today.strftime('%Y-%m-%d')
    
    # 이미 오늘 생성된 캐시가 있으면 재사용
    if CACHE_GENERATION_DATE == current_date_str and RECOMMENDATION_CACHE:
        print(f"DEBUG: Using existing cache for {current_date_str}")
        return
    
    print(f"DEBUG: Generating recommendation cache for 1 month starting from {current_date_str}")
    RECOMMENDATION_CACHE = {}
    CACHE_GENERATION_DATE = current_date_str
    
    # 모든 사용자 조회
    all_users = db.session.query(User).all()
    
    # 1달간 (30일) 각 날짜에 대해 추천 그룹 생성
    for day_offset in range(30):
        target_date = today + timedelta(days=day_offset)
        target_date_str = target_date.strftime('%Y-%m-%d')
        
        # 주말 제외
        if target_date.weekday() >= 5:
            continue
            
        print(f"DEBUG: Generating recommendations for {target_date_str}")
        
        # 각 사용자에 대해 추천 그룹 생성
        for user in all_users:
            employee_id = user.employee_id
            
            # 해당 날짜에 사용 가능한 사용자 조회
            available_users = db.session.query(User).filter(
                and_(
                    getattr(User, 'employee_id') != employee_id,
                    ~db.session.query(Party).filter(
                        and_(
                            getattr(Party, 'party_date') == target_date_str,
                            or_(getattr(Party, 'host_employee_id') == getattr(User, 'employee_id'),
                                getattr(Party, 'members_employee_ids').contains(getattr(User, 'employee_id')))
                        )
                    ).exists(),
                    ~db.session.query(PersonalSchedule).filter(
                        and_(
                            getattr(PersonalSchedule, 'schedule_date') == target_date_str,
                            getattr(PersonalSchedule, 'employee_id') == getattr(User, 'employee_id')
                        )
                    ).exists()
                )
            ).all()
            
            if not available_users:
                print(f"DEBUG: No available users for {employee_id} on {target_date_str}")
                continue
                
            # 사용자 점수 계산 (랜덤 요소 포함)
            scored_users = []
            for available_user in available_users:
                preference_score = calculate_compatibility_score(user, available_user)
                pattern_score = calculate_pattern_score(user, available_user)
                # 랜덤 점수 추가 (0~100 범위)
                random_score = random.uniform(0, 100)
                total_score = preference_score + pattern_score + random_score
                scored_users.append((available_user, total_score))
            
            # 점수로 정렬 (높은 점수 순)
            scored_users.sort(key=lambda x: x[1], reverse=True)
            
            # 정확히 10개 그룹 생성
            all_groups = []
            
            # 3명 그룹 우선 생성 (정확히 10개)
            for i in range(len(scored_users)):
                for j in range(i + 1, len(scored_users)):
                    for k in range(j + 1, len(scored_users)):
                        if len(all_groups) >= 10:
                            break
                        group = [scored_users[i][0], scored_users[j][0], scored_users[k][0]]
                        all_groups.append(group)
                    if len(all_groups) >= 10:
                        break
                if len(all_groups) >= 10:
                    break
            
            # 3명 그룹이 부족하면 2명 그룹 생성
            if len(all_groups) < 10 and len(scored_users) >= 2:
                for i in range(len(scored_users)):
                    for j in range(i + 1, len(scored_users)):
                        if len(all_groups) >= 10:
                            break
                        group = [scored_users[i][0], scored_users[j][0]]
                        all_groups.append(group)
                    if len(all_groups) >= 10:
                        break
            
            # 2명 그룹도 부족하면 1명 그룹 생성
            if len(all_groups) < 10 and len(scored_users) >= 1:
                for i in range(len(scored_users)):
                    if len(all_groups) >= 10:
                        break
                    group = [scored_users[i][0]]
                    all_groups.append(group)
            
            # 캐시에 저장할 형태로 변환
            recommendations = []
            for group_idx, group in enumerate(all_groups[:10]):
                recommendation = {
                    'proposed_date': target_date_str,
                    'recommended_group': [
                        {
                            'employee_id': member.employee_id,
                            'nickname': member.nickname or '익명',
                            'lunch_preference': member.lunch_preference or '',
                            'main_dish_genre': member.main_dish_genre or '',
                            'last_dining_together': get_last_dining_together(employee_id, member.employee_id)
                        }
                        for member in group
                    ]
                }
                recommendations.append(recommendation)
            
            # 캐시에 저장
            cache_key = f"{employee_id}_{target_date_str}"
            RECOMMENDATION_CACHE[cache_key] = recommendations
            print(f"DEBUG: Created {len(recommendations)} recommendations for {cache_key}")
    
    print(f"DEBUG: Cache generation completed. Total cache entries: {len(RECOMMENDATION_CACHE)}")

def get_korean_time():
    """한국 시간을 반환하는 함수"""
    korean_tz = datetime.now().replace(tzinfo=None) + timedelta(hours=9)
    return korean_tz

def format_korean_time(dt):
    """한국 시간으로 포맷팅하는 함수"""
    if dt:
        korean_time = dt + timedelta(hours=9)
        return korean_time.strftime('%Y-%m-%d %H:%M')
    return None

# --- AI/외부 API 연동 (가상 함수) ---
def geocode_address(address):
    lat = 37.4452 + (random.random() - 0.5) * 0.01
    lon = 127.1023 + (random.random() - 0.5) * 0.01
    return lat, lon

def extract_keywords_from_reviews(reviews):
    if not reviews: return []
    text = ' '.join([r.comment for r in reviews if r.comment])
    words = [w.strip() for w in text.split() if len(w.strip()) > 1]
    if not words: return []
    word_counts = {}
    for word in words: word_counts[word] = word_counts.get(word, 0) + 1
    sorted_words = sorted(word_counts.items(), key=lambda item: item[1], reverse=True)
    return [f"#{word}" for word, count in sorted_words[:3]]

# --- Helper Function ---
def reset_user_match_status_if_needed(user):
    today = get_seoul_today()
    if user.match_request_time and user.match_request_time.date() != today:
        user.matching_status = 'idle'
        user.match_request_time = None
        db.session.commit()
    return user

# --- 데이터베이스 모델 정의 ---
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    employee_id = db.Column(db.String(50), unique=True, nullable=False)
    nickname = db.Column(db.String(50), nullable=True)
    lunch_preference = db.Column(db.String(200), nullable=True)
    gender = db.Column(db.String(10), nullable=True)
    age_group = db.Column(db.String(20), nullable=True)
    main_dish_genre = db.Column(db.String(100), nullable=True)
    matching_status = db.Column(db.String(20), default='idle')
    match_request_time = db.Column(db.DateTime, nullable=True)
    # 사용자 선호도 필드들
    food_preferences = db.Column(db.Text, nullable=True)  # 음식 선호도
    allergies = db.Column(db.Text, nullable=True)  # 알레르기 정보
    preferred_time = db.Column(db.String(10), nullable=True)  # 선호 시간대
    frequent_areas = db.Column(db.Text, nullable=True)  # 자주 가는 지역
    notification_settings = db.Column(db.Text, nullable=True)  # 알림 설정
    def __init__(self, employee_id, nickname, lunch_preference, main_dish_genre):
        self.employee_id = employee_id
        self.nickname = nickname
        self.lunch_preference = lunch_preference
        self.main_dish_genre = main_dish_genre

class Restaurant(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    category = db.Column(db.String(50), nullable=False)
    address = db.Column(db.String(200), nullable=True)
    latitude = db.Column(db.Float, nullable=True)
    longitude = db.Column(db.Float, nullable=True)
    reviews = db.relationship('Review', backref='restaurant', lazy=True, cascade="all, delete-orphan")
    
    def __init__(self, name, category, address=None, latitude=None, longitude=None):
        self.name = name
        self.category = category
        self.address = address
        self.latitude = latitude
        self.longitude = longitude
    
    @property
    def review_count(self):
        return len(self.reviews)  # type: ignore
    
    @property
    def avg_rating(self):
        if self.reviews and len(self.reviews) > 0:  # type: ignore
            return sum(r.rating for r in self.reviews) / len(self.reviews)  # type: ignore
        return 0

class Review(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    restaurant_id = db.Column(db.Integer, db.ForeignKey('restaurant.id'), nullable=False)
    user_id = db.Column(db.String(50), nullable=False)
    nickname = db.Column(db.String(50), nullable=False)
    rating = db.Column(db.Integer, nullable=False)
    comment = db.Column(db.Text, nullable=True)
    photo_url = db.Column(db.String(500), nullable=True)  # 사진 URL
    tags = db.Column(db.String(200), nullable=True)  # 태그 (맛있어요, 깔끔해요 등)
    likes = db.Column(db.Integer, default=0)  # 좋아요 수
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    def __init__(self, restaurant_id, user_id, nickname, rating, comment=None, photo_url=None, tags=None):
        self.restaurant_id = restaurant_id
        self.user_id = user_id
        self.nickname = nickname
        self.rating = rating
        self.comment = comment
        self.photo_url = photo_url
        self.tags = tags

class Party(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    host_employee_id = db.Column(db.String(50), nullable=False)
    title = db.Column(db.String(100), nullable=False)
    restaurant_name = db.Column(db.String(100), nullable=False)
    restaurant_address = db.Column(db.String(200), nullable=True)
    party_date = db.Column(db.String(20), nullable=False)
    party_time = db.Column(db.String(10), nullable=False)
    meeting_location = db.Column(db.String(200), nullable=True)
    max_members = db.Column(db.Integer, nullable=False, default=4)
    members_employee_ids = db.Column(db.Text, default='')
    is_from_match = db.Column(db.Boolean, default=False)
    def __init__(self, host_employee_id, title, restaurant_name, restaurant_address, party_date, party_time, meeting_location, max_members, members_employee_ids, is_from_match=False):
        self.host_employee_id = host_employee_id
        self.title = title
        self.restaurant_name = restaurant_name
        self.restaurant_address = restaurant_address
        self.party_date = party_date
        self.party_time = party_time
        self.meeting_location = meeting_location
        self.max_members = max_members
        self.members_employee_ids = members_employee_ids
        self.is_from_match = is_from_match

    @property
    def current_members(self):
        if not self.members_employee_ids: return 0
        return len(self.members_employee_ids.split(','))
    
    def create_chat_room(self):
        """파티 생성 시 자동으로 채팅방과 참여자들을 생성"""
        # 채팅방 생성
        chat_room = ChatRoom(
            name=self.title,
            type='group',
            party_id=self.id
        )
        db.session.add(chat_room)
        db.session.flush()  # ID를 얻기 위해 flush
        
        # 참여자들 추가
        member_ids = self.members_employee_ids.split(',') if self.members_employee_ids else []
        for member_id in member_ids:
            participant = ChatParticipant(room_id=chat_room.id, user_id=member_id)
            db.session.add(participant)

class PersonalSchedule(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    employee_id = db.Column(db.String(50), nullable=False)
    schedule_date = db.Column(db.String(10), nullable=False)
    title = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text, nullable=True)
    def __init__(self, employee_id, schedule_date, title, description=None):
        self.employee_id = employee_id
        self.schedule_date = schedule_date
        self.title = title
        self.description = description

class LunchProposal(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    proposer_id = db.Column(db.String(50), nullable=False)
    recipient_ids = db.Column(db.Text, nullable=False)
    proposed_date = db.Column(db.String(20), nullable=False)
    status = db.Column(db.String(20), default='pending')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    expires_at = db.Column(db.DateTime, nullable=False)
    
    def __init__(self, proposer_id, recipient_ids, proposed_date):
        self.proposer_id = proposer_id
        self.recipient_ids = recipient_ids
        self.proposed_date = proposed_date
        self.expires_at = datetime.utcnow() + timedelta(hours=24)

class ProposalAcceptance(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    proposal_id = db.Column(db.Integer, db.ForeignKey('lunch_proposal.id'), nullable=False)
    user_id = db.Column(db.String(50), nullable=False)
    accepted_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def __init__(self, proposal_id, user_id):
        self.proposal_id = proposal_id
        self.user_id = user_id

class ChatMessage(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    chat_type = db.Column(db.String(20), nullable=False)  # 'party', 'dangolpot'
    chat_id = db.Column(db.Integer, nullable=False)  # party_id or dangolpot_id
    sender_employee_id = db.Column(db.String(50), nullable=False)
    sender_nickname = db.Column(db.String(50), nullable=False)
    message = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Notification(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.String(50), nullable=False)
    type = db.Column(db.String(50), nullable=False)  # 'friend_request', 'party_invite', 'chat_message', 'review_like'
    title = db.Column(db.String(100), nullable=False)
    message = db.Column(db.Text, nullable=False)
    related_id = db.Column(db.Integer, nullable=True)  # 관련 ID (파티 ID, 채팅방 ID 등)
    is_read = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def __init__(self, user_id, type, title, message, related_id=None):
        self.user_id = user_id
        self.type = type
        self.title = title
        self.message = message
        self.related_id = related_id

class UserAnalytics(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.String(50), nullable=False)
    date = db.Column(db.Date, nullable=False)
    total_parties_joined = db.Column(db.Integer, default=0)
    total_reviews_written = db.Column(db.Integer, default=0)
    total_friends_added = db.Column(db.Integer, default=0)
    favorite_restaurant_category = db.Column(db.String(50), nullable=True)
    average_rating_given = db.Column(db.Float, default=0.0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def __init__(self, user_id, date):
        self.user_id = user_id
        self.date = date

class RestaurantAnalytics(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    restaurant_id = db.Column(db.Integer, db.ForeignKey('restaurant.id'), nullable=False)
    date = db.Column(db.Date, nullable=False)
    total_visits = db.Column(db.Integer, default=0)
    total_reviews = db.Column(db.Integer, default=0)
    average_rating = db.Column(db.Float, default=0.0)
    total_likes = db.Column(db.Integer, default=0)
    popular_tags = db.Column(db.String(500), nullable=True)  # JSON 형태로 저장
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def __init__(self, restaurant_id, date):
        self.restaurant_id = restaurant_id
        self.date = date

class OfflineData(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.String(50), nullable=False)
    data_type = db.Column(db.String(50), nullable=False)  # 'restaurants', 'parties', 'reviews'
    data_json = db.Column(db.Text, nullable=False)  # JSON 형태로 저장된 데이터
    last_sync = db.Column(db.DateTime, default=datetime.utcnow)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def __init__(self, user_id, data_type, data_json):
        self.user_id = user_id
        self.data_type = data_type
        self.data_json = data_json

class DangolPot(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text, nullable=True)
    tags = db.Column(db.String(200), nullable=True)
    category = db.Column(db.String(50), nullable=True)
    host_id = db.Column(db.String(50), nullable=False)
    members = db.Column(db.Text, default='')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    def __init__(self, name, description, tags, category, host_id, members):
        self.name = name
        self.description = description
        self.tags = tags
        self.category = category
        self.host_id = host_id
        self.members = members
    @property
    def member_count(self):
        if not self.members:
            return 0
        return len(self.members.split(','))
    
    def create_chat_room(self):
        """단골파티 생성 시 자동으로 채팅방과 참여자들을 생성"""
        # 채팅방 생성
        chat_room = ChatRoom(
            name=self.name,
            type='dangolpot',
            dangolpot_id=self.id
        )
        db.session.add(chat_room)
        db.session.flush()  # ID를 얻기 위해 flush
        
        # 참여자들 추가
        member_ids = self.members.split(',') if self.members else []
        for member_id in member_ids:
            participant = ChatParticipant(room_id=chat_room.id, user_id=member_id)
            db.session.add(participant)

# --- 새로운 모델들 ---
class Friendship(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    requester_id = db.Column(db.String(50), nullable=False)
    receiver_id = db.Column(db.String(50), nullable=False)
    status = db.Column(db.String(20), default='pending')  # 'pending', 'accepted'
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def __init__(self, requester_id, receiver_id):
        self.requester_id = requester_id
        self.receiver_id = receiver_id

class ChatRoom(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=True)  # 그룹 채팅방 이름
    type = db.Column(db.String(20), nullable=False)  # 'friend', 'group', 'dangolpot'
    party_id = db.Column(db.Integer, db.ForeignKey('party.id'), nullable=True)
    dangolpot_id = db.Column(db.Integer, db.ForeignKey('dangol_pot.id'), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def __init__(self, name, type, party_id=None, dangolpot_id=None):
        self.name = name
        self.type = type
        self.party_id = party_id
        self.dangolpot_id = dangolpot_id

class ChatParticipant(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    room_id = db.Column(db.Integer, db.ForeignKey('chat_room.id'), nullable=False)
    user_id = db.Column(db.String(50), nullable=False)
    joined_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def __init__(self, room_id, user_id):
        self.room_id = room_id
        self.user_id = user_id

class ChatMessageRead(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    message_id = db.Column(db.Integer, db.ForeignKey('chat_message.id'), nullable=False)
    user_id = db.Column(db.String(50), nullable=False)
    read_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __init__(self, message_id, user_id):
        self.message_id = message_id
        self.user_id = user_id

class VotingSession(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    chat_room_id = db.Column(db.Integer, nullable=False)
    title = db.Column(db.String(100), nullable=False)
    restaurant_name = db.Column(db.String(100), nullable=True)
    restaurant_address = db.Column(db.String(200), nullable=True)
    meeting_location = db.Column(db.String(200), nullable=True)
    meeting_time = db.Column(db.String(10), nullable=True)
    participants = db.Column(db.Text, nullable=False)  # JSON 형태로 참가자 목록
    available_dates = db.Column(db.Text, nullable=True)  # JSON 형태로 가능한 날짜 목록
    expires_at = db.Column(db.DateTime, nullable=False)
    status = db.Column(db.String(20), default='active')  # active, completed, cancelled
    created_by = db.Column(db.String(50), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    confirmed_date = db.Column(db.String(20), nullable=True)  # 확정된 날짜
    confirmed_at = db.Column(db.DateTime, nullable=True)

    def __init__(self, chat_room_id, title, participants, created_by, expires_at, restaurant_name=None, 
                 restaurant_address=None, meeting_location=None, meeting_time=None):
        self.chat_room_id = chat_room_id
        self.title = title
        self.restaurant_name = restaurant_name
        self.restaurant_address = restaurant_address
        self.meeting_location = meeting_location
        self.meeting_time = meeting_time
        self.participants = participants
        self.created_by = created_by
        self.expires_at = expires_at

class DateVote(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    voting_session_id = db.Column(db.Integer, db.ForeignKey('voting_session.id'), nullable=False)
    voter_id = db.Column(db.String(50), nullable=False)
    voted_date = db.Column(db.String(20), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __init__(self, voting_session_id, voter_id, voted_date):
        self.voting_session_id = voting_session_id
        self.voter_id = voter_id
        self.voted_date = voted_date

class DailyRecommendation(db.Model):
    """일별 추천 그룹 모델"""
    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.String(20), nullable=False)  # YYYY-MM-DD 형식
    group_members = db.Column(db.Text, nullable=False)  # JSON 형태로 멤버 정보 저장
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def __init__(self, date, group_members):
        self.date = date
        self.group_members = group_members

class RestaurantRequest(db.Model):
    """식당 신청/수정/삭제 요청 모델"""
    id = db.Column(db.Integer, primary_key=True)
    request_type = db.Column(db.String(20), nullable=False)  # 'add', 'update', 'delete'
    restaurant_name = db.Column(db.String(100), nullable=True)
    restaurant_address = db.Column(db.String(200), nullable=True)
    restaurant_id = db.Column(db.Integer, db.ForeignKey('restaurant.id'), nullable=True)  # 수정/삭제 시
    reason = db.Column(db.Text, nullable=True)  # 수정/삭제 사유
    status = db.Column(db.String(20), default='pending')  # 'pending', 'approved', 'rejected'
    requester_id = db.Column(db.String(50), nullable=False)
    requester_nickname = db.Column(db.String(50), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    approved_at = db.Column(db.DateTime, nullable=True)
    approved_by = db.Column(db.String(50), nullable=True)
    rejection_reason = db.Column(db.Text, nullable=True)  # 거절 사유
    
    def __init__(self, request_type, requester_id, requester_nickname, restaurant_name=None, 
                 restaurant_address=None, restaurant_id=None, reason=None):
        self.request_type = request_type
        self.requester_id = requester_id
        self.requester_nickname = requester_nickname
        self.restaurant_name = restaurant_name
        self.restaurant_address = restaurant_address
        self.restaurant_id = restaurant_id
        self.reason = reason

# --- 앱 실행 시 초기화 ---
@app.before_request
def create_tables_and_init_data():
    if not hasattr(app, '_db_initialized'):
        with app.app_context():
            db.create_all()
            if User.query.count() == 0:
                users_data = [
                    {'employee_id': 'KOICA001', 'nickname': '김코이카', 'lunch_preference': '조용한 식사,빠른 식사', 'main_dish_genre': '한식,분식'},
                    {'employee_id': 'KOICA002', 'nickname': '이해외', 'lunch_preference': '대화 선호,가성비 추구', 'main_dish_genre': '한식,중식'},
                    {'employee_id': 'KOICA003', 'nickname': '박봉사', 'lunch_preference': '새로운 맛집 탐방', 'main_dish_genre': '일식,양식'},
                    {'employee_id': 'KOICA004', 'nickname': '최점심', 'lunch_preference': '맛집 탐방,사진 촬영', 'main_dish_genre': '한식,양식'},
                    {'employee_id': 'KOICA005', 'nickname': '정식사', 'lunch_preference': '건강한 식사,채식 선호', 'main_dish_genre': '한식,샐러드'},
                    {'employee_id': 'KOICA006', 'nickname': '한식당', 'lunch_preference': '전통 한식,가족 분위기', 'main_dish_genre': '한식,분식'},
                    {'employee_id': 'KOICA007', 'nickname': '중국집', 'lunch_preference': '매운 음식,대량 주문', 'main_dish_genre': '중식,분식'},
                    {'employee_id': 'KOICA008', 'nickname': '일본인', 'lunch_preference': '신선한 재료,정갈한 맛', 'main_dish_genre': '일식,한식'},
                    {'employee_id': 'KOICA009', 'nickname': '양식당', 'lunch_preference': '분위기 좋은 곳,와인', 'main_dish_genre': '양식,한식'},
                    {'employee_id': 'KOICA010', 'nickname': '분식왕', 'lunch_preference': '빠른 식사,가성비', 'main_dish_genre': '분식,한식'},
                    {'employee_id': 'KOICA011', 'nickname': '카페인', 'lunch_preference': '커피와 함께,브런치', 'main_dish_genre': '양식,카페'},
                    {'employee_id': 'KOICA012', 'nickname': '맛집탐험가', 'lunch_preference': '새로운 맛집,인스타그램', 'main_dish_genre': '한식,양식,일식'},
                ]
                # User 생성 (초기 데이터)
                for user_data in users_data:
                    db.session.add(User(
                        employee_id=user_data.get('employee_id'),
                        nickname=user_data.get('nickname'),
                        lunch_preference=user_data.get('lunch_preference'),
                        main_dish_genre=user_data.get('main_dish_genre')
                    ))
            
            # Restaurant 초기 데이터 추가
            if Restaurant.query.count() == 0:
                import pandas as pd
                import os
                # 여러 가능한 CSV 파일 경로 시도
                possible_paths = [
                    os.path.join(os.path.dirname(__file__), 'data/restaurants.csv'),
                    os.path.join(os.path.dirname(__file__), 'restaurants.csv'),
                    'data/restaurants.csv',
                    'restaurants.csv'
                ]
                
                csv_path = None
                for path in possible_paths:
                    if os.path.exists(path):
                        csv_path = path
                        break
                
                if csv_path:
                    print(f"CSV 파일을 찾았습니다: {csv_path}")
                    df = pd.read_csv(csv_path, encoding='utf-8')
                    print(f"CSV 파일에서 {len(df)}개의 행을 읽었습니다.")
                    
                    # CSV 파일이 '사업장명', '소재지(지번)' 컬럼을 갖고 있다고 가정
                    for idx, row in df.iterrows():
                        name = str(row.get('사업장명', '')).strip()
                        address = str(row.get('소재지(지번)', '')).strip()
                        if not name or not address:
                            continue
                        # 중복 체크 (이름+주소)
                        exists = Restaurant.query.filter_by(name=name, address=address).first()
                        if exists:
                            continue
                        
                        # 주소를 좌표로 변환
                        lat, lon = geocode_address(address)
                        
                        db.session.add(Restaurant(
                            name=name,
                            category='',
                            address=address,
                            latitude=lat,
                            longitude=lon
                        ))
                    db.session.commit()
                    print(f"CSV 파일에서 {Restaurant.query.count()}개의 식당을 등록했습니다.")
                else:
                    # 기존 하드코딩 데이터 (엑셀 없을 때만)
                    restaurants_data = [
                        {'name': '판교역 맛집', 'category': '한식', 'address': '경기도 성남시 분당구 판교역로 146'},
                        {'name': '분당 맛집', 'category': '중식', 'address': '경기도 성남시 분당구 정자로 123'},
                        {'name': '일식당', 'category': '일식', 'address': '경기도 성남시 분당구 판교로 456'},
                        {'name': '양식점', 'category': '양식', 'address': '경기도 성남시 분당구 정자동 789'},
                        {'name': '분식점', 'category': '분식', 'address': '경기도 성남시 분당구 판교동 321'},
                    ]
                    for restaurant_data in restaurants_data:
                        lat, lon = geocode_address(restaurant_data['address'])
                        db.session.add(Restaurant(
                            name=restaurant_data['name'],
                            category=restaurant_data['category'],
                            address=restaurant_data['address'],
                            latitude=lat,
                            longitude=lon
                        ))
            
            # 성사된 랜덤런치 그룹 테스트 데이터 추가
            if Party.query.filter_by(is_from_match=True).count() == 0:
                test_parties = [
                    {
                        'host_employee_id': 'KOICA001',
                        'title': '랜덤 런치',
                        'restaurant_name': '판교역 맛집',
                        'restaurant_address': '경기도 성남시 분당구 판교역로 146',
                        'party_date': '2024-01-15',
                        'party_time': '12:00',
                        'meeting_location': 'KOICA 본사',
                        'max_members': 3,
                        'members_employee_ids': 'KOICA001,KOICA002,KOICA003',
                        'is_from_match': True
                    },
                    {
                        'host_employee_id': 'KOICA001',
                        'title': '랜덤 런치',
                        'restaurant_name': '분당 맛집',
                        'restaurant_address': '경기도 성남시 분당구 정자로 123',
                        'party_date': '2024-01-16',
                        'party_time': '12:30',
                        'meeting_location': 'KOICA 본사',
                        'max_members': 4,
                        'members_employee_ids': 'KOICA001,KOICA004,KOICA005,KOICA006',
                        'is_from_match': True
                    },
                    {
                        'host_employee_id': 'KOICA007',
                        'title': '랜덤 런치',
                        'restaurant_name': '일식당',
                        'restaurant_address': '경기도 성남시 분당구 판교로 456',
                        'party_date': '2024-01-17',
                        'party_time': '12:00',
                        'meeting_location': 'KOICA 본사',
                        'max_members': 2,
                        'members_employee_ids': 'KOICA007,KOICA001',
                        'is_from_match': True
                    }
                ]
                
                # 테스트 파티 생성
                for party_data in test_parties:
                    db.session.add(Party(**party_data))
            
            db.session.commit()
            setattr(app, '_db_initialized', True)
            
            # 앱 시작 시 추천 그룹 캐시 생성
            print("DEBUG: Initializing recommendation cache...")
            generate_recommendation_cache()
            print("DEBUG: Recommendation cache initialization completed.")

# --- API 엔드포인트 ---
@app.route('/cafeteria/today', methods=['GET'])
def get_today_menu(): return jsonify({'menu': ['제육볶음', '계란찜']})

# --- 이벤트 (약속) 통합 API ---
@app.route('/events/<employee_id>', methods=['GET'])
def get_events(employee_id):
    events = {}
    today = get_seoul_today()
    # 파티/랜덤런치 조회
    parties = Party.query.filter(Party.members_employee_ids.contains(employee_id)).all()  # type: ignore
    for p in parties:
        # 오늘 날짜 이전의 약속은 제외
        if datetime.strptime(p.party_date, '%Y-%m-%d').date() < today:
            continue
        if p.party_date not in events: events[p.party_date] = []
        member_ids = p.members_employee_ids.split(',') if p.members_employee_ids else []
        other_member_ids = [mid for mid in member_ids if mid != employee_id]
        users = User.query.filter(User.employee_id.in_(other_member_ids)).all()  # type: ignore
        member_nicknames = [user.nickname for user in users]
        all_users = User.query.filter(User.employee_id.in_(member_ids)).all()  # type: ignore
        all_member_nicknames = [user.nickname for user in all_users]
        events[p.party_date].append({
            'type': '랜덤 런치' if p.is_from_match else '파티',
            'id': p.id, 'title': p.title, 'restaurant': p.restaurant_name, 'address': p.restaurant_address,
            'date': p.party_date, 'time': p.party_time, 'location': p.meeting_location,
            'members': member_nicknames, 'all_members': all_member_nicknames
        })
    # 개인 일정 조회
    schedules = PersonalSchedule.query.filter_by(employee_id=employee_id).all()
    for s in schedules:
        if datetime.strptime(s.schedule_date, '%Y-%m-%d').date() < today:
            continue
        if s.schedule_date not in events: events[s.schedule_date] = []
        events[s.schedule_date].append({
            'type': '개인 일정', 'id': s.id, 'title': s.title, 'description': s.description, 'date': s.schedule_date
        })
    return jsonify(events)

# --- 개인 일정 API ---
@app.route('/personal_schedules', methods=['POST'])
def add_personal_schedule():
    data = request.get_json() or {}
    # PersonalSchedule 생성
    new_schedule = PersonalSchedule(
        employee_id=data.get('employee_id'),
        schedule_date=data.get('schedule_date'),
        title=data.get('title'),
        description=data.get('description', '')
    )
    db.session.add(new_schedule)
    db.session.commit()
    return jsonify({'message': '개인 일정이 추가되었습니다.', 'id': new_schedule.id}), 201

@app.route('/personal_schedules/<int:schedule_id>', methods=['PUT'])
def update_personal_schedule(schedule_id):
    schedule = PersonalSchedule.query.get(schedule_id)
    if not schedule: return jsonify({'message': '일정을 찾을 수 없습니다.'}), 404
    data = request.get_json()
    schedule.title = data.get('title', schedule.title)
    schedule.description = data.get('description', schedule.description)
    db.session.commit()
    return jsonify({'message': '일정이 수정되었습니다.'})

@app.route('/personal_schedules/<int:schedule_id>', methods=['DELETE'])
def delete_personal_schedule(schedule_id):
    schedule = PersonalSchedule.query.get(schedule_id)
    if not schedule: return jsonify({'message': '일정을 찾을 수 없습니다.'}), 404
    db.session.delete(schedule)
    db.session.commit()
    return jsonify({'message': '일정이 삭제되었습니다.'})

# --- 맛집 API ---
@app.route('/restaurants', methods=['POST'])
def add_restaurant():
    data = request.get_json()
    lat, lon = geocode_address(data['address'])
    new_restaurant = Restaurant(
        name=data['name'],
        category=data['category'],
        address=data['address'],
        latitude=lat,
        longitude=lon
    )
    db.session.add(new_restaurant)
    db.session.commit()
    return jsonify({'message': '새로운 맛집이 등록되었습니다!', 'restaurant_id': new_restaurant.id}), 201

@app.route('/restaurants', methods=['GET'])
def get_restaurants():
    query = request.args.get('query', '')
    sort_by = request.args.get('sort_by', 'name')
    category_filter = request.args.get('category', None)
    lat = request.args.get('lat', None)
    lon = request.args.get('lon', None)
    radius = request.args.get('radius', 10)  # 기본 10km
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 50, type=int)  # 한 번에 50개씩

    q = Restaurant.query
    
    # 카테고리 필터
    if category_filter:
        q = q.filter(Restaurant.category == category_filter)  # type: ignore
    
    # 검색어 필터
    if query:
        q = q.filter(or_(Restaurant.name.ilike(f'%{query}%'), Restaurant.category.ilike(f'%{query}%')))  # type: ignore
    
    # 지역 필터 (위도/경도가 제공된 경우)
    if lat and lon:
        # 간단한 거리 계산 (대략적)
        lat = float(lat)
        lon = float(lon)
        radius = float(radius)
        
        print(f"지역 필터링: 중심점({lat}, {lon}), 반지름 {radius}km")
        
        # 위도 1도 ≈ 111km, 경도 1도 ≈ 88.9km (한반도 기준)
        lat_range = radius / 111.0
        lon_range = radius / 88.9
        
        print(f"위도 범위: {lat - lat_range} ~ {lat + lat_range}")
        print(f"경도 범위: {lon - lon_range} ~ {lon + lon_range}")
        
        # 좌표가 있는 식당만 필터링
        q = q.filter(
            Restaurant.latitude.isnot(None),
            Restaurant.longitude.isnot(None),
            Restaurant.latitude >= lat - lat_range,
            Restaurant.latitude <= lat + lat_range,
            Restaurant.longitude >= lon - lon_range,
            Restaurant.longitude <= lon + lon_range
        )
        
        # 필터링된 결과 수 확인
        filtered_count = q.count()
        print(f"지역 필터링 후 식당 수: {filtered_count}")
    
    # 정렬
    if sort_by == 'rating_desc':
        q = q.order_by(Restaurant.avg_rating.desc())
    elif sort_by == 'reviews_desc':
        q = q.order_by(Restaurant.review_count.desc())
    else:
        q = q.order_by(Restaurant.name)
    
    # 페이지네이션
    pagination = q.paginate(page=page, per_page=per_page, error_out=False)
    restaurants_q = pagination.items
    
    restaurants_list = [{
        'id': r.id, 
        'name': r.name, 
        'category': r.category, 
        'address': r.address, 
        'latitude': r.latitude, 
        'longitude': r.longitude, 
        'rating': round(r.avg_rating, 1), 
        'review_count': r.review_count
    } for r in restaurants_q]
    
    return jsonify({
        'restaurants': restaurants_list,
        'total': pagination.total,
        'pages': pagination.pages,
        'current_page': page,
        'per_page': per_page
    })

@app.route('/restaurants/<int:restaurant_id>', methods=['GET'])
def get_restaurant_detail(restaurant_id):
    restaurant = Restaurant.query.get(restaurant_id)
    if not restaurant: return jsonify({'message': '맛집을 찾을 수 없습니다.'}), 404
    keywords = extract_keywords_from_reviews(restaurant.reviews)
    return jsonify({
        'id': restaurant.id, 'name': restaurant.name, 'category': restaurant.category,
        'address': restaurant.address, 'latitude': restaurant.latitude, 'longitude': restaurant.longitude,
        'keywords': keywords
    })

@app.route('/restaurants/<int:restaurant_id>/reviews', methods=['GET'])
def get_reviews(restaurant_id):
    reviews = Review.query.filter_by(restaurant_id=restaurant_id).order_by(desc(Review.created_at)).all()
    return jsonify([{'id': r.id, 'nickname': r.nickname, 'rating': r.rating, 'comment': r.comment, 'created_at': r.created_at.strftime('%Y-%m-%d')} for r in reviews])

@app.route('/restaurants/<int:restaurant_id>/reviews', methods=['POST'])
def add_review(restaurant_id):
    data = request.get_json() or {}
    restaurant = Restaurant.query.get(restaurant_id)
    if not restaurant: return jsonify({'message': '맛집을 찾을 수 없습니다.'}), 404
    
    new_review = Review(
        restaurant_id=restaurant_id,
        user_id=data.get('user_id'),
        nickname=data.get('nickname'),
        rating=data.get('rating'),
        comment=data.get('comment'),
        photo_url=data.get('photo_url'),
        tags=data.get('tags')
    )
    db.session.add(new_review)
    db.session.commit()
    return jsonify({'message': '리뷰가 추가되었습니다.', 'id': new_review.id}), 201

@app.route('/restaurants/search', methods=['GET'])
def search_restaurants():
    """식당 검색 API - 드롭다운용"""
    query = request.args.get('query', '')
    limit = request.args.get('limit', 10, type=int)
    
    if not query:
        return jsonify([])
    
    # 검색 쿼리
    restaurants_query = Restaurant.query.filter(Restaurant.name.contains(query))  # type: ignore
    restaurants = restaurants_query.limit(limit).all()
    
    # 간단한 정보만 반환
    restaurants_data = []
    for restaurant in restaurants:
        restaurants_data.append({
            'id': restaurant.id,
            'name': restaurant.name,
            'category': restaurant.category,
            'address': restaurant.address
        })
    
    return jsonify(restaurants_data)

@app.route('/reviews/<int:review_id>/like', methods=['POST'])
def like_review(review_id):
    """리뷰 좋아요"""
    review = Review.query.get(review_id)
    if not review:
        return jsonify({'message': '리뷰를 찾을 수 없습니다.'}), 404
    
    review.likes += 1
    db.session.commit()
    
    return jsonify({'message': '좋아요가 추가되었습니다.', 'likes': review.likes})

@app.route('/reviews/tags', methods=['GET'])
def get_review_tags():
    """사용 가능한 리뷰 태그 목록"""
    tags = [
        '맛있어요', '깔끔해요', '친절해요', '분위기 좋아요',
        '가성비 좋아요', '양 많아요', '신선해요', '매운맛',
        '달콤해요', '고소해요', '담백해요', '진한맛'
    ]
    return jsonify({'tags': tags})

# --- 식당 신청 관련 API ---
@app.route('/restaurants/requests', methods=['POST'])
def create_restaurant_request():
    """식당 신청/수정/삭제 요청 생성"""
    data = request.get_json()
    
    # 일일 신청 제한 확인 (사용자당 5개)
    today = get_seoul_today()
    daily_requests = RestaurantRequest.query.filter(
        RestaurantRequest.requester_id == data['requester_id'],
        RestaurantRequest.created_at >= today
    ).count()
    
    if daily_requests >= 5:
        return jsonify({'error': '일일 신청 한도를 초과했습니다. (최대 5개)'}), 400
    
    # 중복 신청 확인
    existing_request = RestaurantRequest.query.filter(
        RestaurantRequest.requester_id == data['requester_id'],
        RestaurantRequest.request_type == data['request_type'],
        RestaurantRequest.restaurant_name == data.get('restaurant_name'),
        RestaurantRequest.status == 'pending'
    ).first()
    
    if existing_request:
        return jsonify({'error': '이미 동일한 신청이 대기 중입니다.'}), 400
    
    # 자동 승인 조건 확인
    auto_approve = False
    if data['request_type'] == 'add':
        # 특정 키워드가 포함된 경우 자동 승인
        keywords = ['씨유', 'CU', 'GS25', '세븐일레븐', '7-11', '이마트24', '미니스톱']
        restaurant_name = data.get('restaurant_name', '').lower()
        if any(keyword.lower() in restaurant_name for keyword in keywords):
            auto_approve = True
    
    request_obj = RestaurantRequest(
        request_type=data['request_type'],
        requester_id=data['requester_id'],
        requester_nickname=data['requester_nickname'],
        restaurant_name=data.get('restaurant_name'),
        restaurant_address=data.get('restaurant_address'),
        restaurant_id=data.get('restaurant_id'),
        reason=data.get('reason')
    )
    
    if auto_approve:
        request_obj.status = 'approved'
        request_obj.approved_at = datetime.utcnow()
        request_obj.approved_by = 'system'
        
        # 자동으로 식당 추가
        if data['request_type'] == 'add':
            lat, lon = geocode_address(data.get('restaurant_address', ''))
            restaurant = Restaurant(
                name=data['restaurant_name'],
                category='',
                address=data.get('restaurant_address'),
                latitude=lat,
                longitude=lon
            )
            db.session.add(restaurant)
    
    db.session.add(request_obj)
    db.session.commit()
    
    # 알림 생성
    if not auto_approve:
        create_notification(
            user_id='admin',  # 관리자에게 알림
            type='restaurant_request',
            title='새로운 식당 신청',
            message=f"{data['requester_nickname']}님이 식당을 신청했습니다.",
            related_id=request_obj.id
        )
    
    return jsonify({
        'message': '신청이 접수되었습니다.' + (' (자동 승인됨)' if auto_approve else ''),
        'auto_approved': auto_approve
    }), 201

@app.route('/restaurants/requests/my/<employee_id>', methods=['GET'])
def get_my_restaurant_requests(employee_id):
    """내 식당 신청 내역 조회"""
    requests = RestaurantRequest.query.filter_by(requester_id=employee_id)\
        .order_by(RestaurantRequest.created_at.desc()).all()
    
    return jsonify({
        'requests': [{
            'id': req.id,
            'request_type': req.request_type,
            'restaurant_name': req.restaurant_name,
            'restaurant_address': req.restaurant_address,
            'reason': req.reason,
            'status': req.status,
            'created_at': format_korean_time(req.created_at),
            'approved_at': format_korean_time(req.approved_at) if req.approved_at else None,
            'rejection_reason': req.rejection_reason
        } for req in requests]
    })

@app.route('/restaurants/requests/pending', methods=['GET'])
def get_pending_restaurant_requests():
    """관리자용 대기 중인 신청 목록"""
    requests = RestaurantRequest.query.filter_by(status='pending')\
        .order_by(RestaurantRequest.created_at.desc()).all()
    
    return jsonify({
        'requests': [{
            'id': req.id,
            'request_type': req.request_type,
            'restaurant_name': req.restaurant_name,
            'restaurant_address': req.restaurant_address,
            'reason': req.reason,
            'requester_id': req.requester_id,
            'requester_nickname': req.requester_nickname,
            'created_at': format_korean_time(req.created_at)
        } for req in requests]
    })

@app.route('/restaurants/requests/<int:request_id>/approve', methods=['PUT'])
def approve_restaurant_request(request_id):
    """식당 신청 승인"""
    data = request.get_json()
    request_obj = RestaurantRequest.query.get_or_404(request_id)
    
    if request_obj.status != 'pending':
        return jsonify({'error': '이미 처리된 신청입니다.'}), 400
    
    request_obj.status = 'approved'
    request_obj.approved_at = datetime.utcnow()
    request_obj.approved_by = data.get('admin_id', 'admin')
    
    # 신청 유형에 따른 처리
    if request_obj.request_type == 'add':
        # 새 식당 추가
        lat, lon = geocode_address(request_obj.restaurant_address or '')
        restaurant = Restaurant(
            name=request_obj.restaurant_name,
            category='',
            address=request_obj.restaurant_address,
            latitude=lat,
            longitude=lon
        )
        db.session.add(restaurant)
        
    elif request_obj.request_type == 'update':
        # 식당 정보 수정
        restaurant = Restaurant.query.get(request_obj.restaurant_id)
        if restaurant:
            if request_obj.restaurant_name:
                restaurant.name = request_obj.restaurant_name
            if request_obj.restaurant_address:
                restaurant.address = request_obj.restaurant_address
                lat, lon = geocode_address(request_obj.restaurant_address)
                restaurant.latitude = lat
                restaurant.longitude = lon
                
    elif request_obj.request_type == 'delete':
        # 식당 삭제
        restaurant = Restaurant.query.get(request_obj.restaurant_id)
        if restaurant:
            db.session.delete(restaurant)
    
    db.session.commit()
    
    # 신청자에게 승인 알림
    create_notification(
        user_id=request_obj.requester_id,
        type='restaurant_request_approved',
        title='식당 신청 승인',
        message=f'"{request_obj.restaurant_name}" 신청이 승인되었습니다.',
        related_id=request_obj.id
    )
    
    return jsonify({'message': '신청이 승인되었습니다.'})

@app.route('/restaurants/requests/<int:request_id>/reject', methods=['PUT'])
def reject_restaurant_request(request_id):
    """식당 신청 거절"""
    data = request.get_json()
    request_obj = RestaurantRequest.query.get_or_404(request_id)
    
    if request_obj.status != 'pending':
        return jsonify({'error': '이미 처리된 신청입니다.'}), 400
    
    request_obj.status = 'rejected'
    request_obj.rejection_reason = data.get('rejection_reason', '')
    
    db.session.commit()
    
    # 신청자에게 거절 알림
    create_notification(
        user_id=request_obj.requester_id,
        type='restaurant_request_rejected',
        title='식당 신청 거절',
        message=f'"{request_obj.restaurant_name}" 신청이 거절되었습니다.',
        related_id=request_obj.id
    )
    
    return jsonify({'message': '신청이 거절되었습니다.'})

# --- 데이터 분석 API ---
@app.route('/analytics/user/<employee_id>', methods=['GET'])
def get_user_analytics(employee_id):
    """사용자 분석 데이터 조회"""
    try:
        # 최근 30일 데이터
        end_date = datetime.now().date()
        start_date = end_date - timedelta(days=30)
        
        analytics = UserAnalytics.query.filter(
            UserAnalytics.user_id == employee_id,  # type: ignore
            UserAnalytics.date >= start_date,  # type: ignore
            UserAnalytics.date <= end_date  # type: ignore
        ).all()
        
        # 파티 참여 통계
        parties_joined = Party.query.filter(
            Party.members_employee_ids.contains(employee_id)  # type: ignore
        ).count()
        
        # 리뷰 작성 통계
        reviews_written = Review.query.filter_by(user_id=employee_id).count()
        
        # 친구 수 (일방적 관계)
        friendships = Friendship.query.filter_by(
            requester_id=employee_id,
            status='accepted'
        ).count()
        
        # 선호 카테고리 분석
        user_reviews = Review.query.filter_by(user_id=employee_id).all()
        category_counts = {}
        total_rating = 0
        
        for review in user_reviews:
            restaurant = Restaurant.query.get(review.restaurant_id)
            if restaurant:
                category = restaurant.category
                category_counts[category] = category_counts.get(category, 0) + 1
                total_rating += review.rating
        
        favorite_category = max(category_counts.items(), key=lambda x: x[1])[0] if category_counts else None
        avg_rating = total_rating / len(user_reviews) if user_reviews else 0
        
        return jsonify({
            'parties_joined': parties_joined,
            'reviews_written': reviews_written,
            'friends_count': friendships,
            'favorite_category': favorite_category,
            'average_rating': round(avg_rating, 1),
            'activity_trend': [a.total_parties_joined for a in analytics]
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/analytics/restaurant/<int:restaurant_id>', methods=['GET'])
def get_restaurant_analytics(restaurant_id):
    """식당 분석 데이터 조회"""
    try:
        restaurant = Restaurant.query.get(restaurant_id)
        if not restaurant:
            return jsonify({'error': '식당을 찾을 수 없습니다.'}), 404
        
        # 리뷰 통계
        reviews = Review.query.filter_by(restaurant_id=restaurant_id).all()
        total_reviews = len(reviews)
        total_likes = sum(review.likes for review in reviews)
        avg_rating = sum(review.rating for review in reviews) / total_reviews if reviews else 0
        
        # 인기 태그 분석
        tag_counts = {}
        for review in reviews:
            if review.tags:
                tags = review.tags.split(',')
                for tag in tags:
                    tag = tag.strip()
                    tag_counts[tag] = tag_counts.get(tag, 0) + 1
        
        popular_tags = sorted(tag_counts.items(), key=lambda x: x[1], reverse=True)[:5]
        
        # 방문 통계 (파티 참여 기준)
        visits = Party.query.filter_by(restaurant_name=restaurant.name).count()
        
        return jsonify({
            'restaurant_name': restaurant.name,
            'total_visits': visits,
            'total_reviews': total_reviews,
            'average_rating': round(avg_rating, 1),
            'total_likes': total_likes,
            'popular_tags': [{'tag': tag, 'count': count} for tag, count in popular_tags]
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/analytics/trends', methods=['GET'])
def get_trends():
    """전체 트렌드 분석"""
    try:
        # 인기 식당 카테고리
        restaurants = Restaurant.query.all()
        category_stats = {}
        
        for restaurant in restaurants:
            reviews = Review.query.filter_by(restaurant_id=restaurant.id).all()
            if reviews:
                avg_rating = sum(r.rating for r in reviews) / len(reviews)
                category_stats[restaurant.category] = category_stats.get(restaurant.category, {
                    'count': 0,
                    'total_rating': 0,
                    'total_reviews': 0
                })
                category_stats[restaurant.category]['count'] += 1
                category_stats[restaurant.category]['total_rating'] += avg_rating
                category_stats[restaurant.category]['total_reviews'] += len(reviews)
        
        # 평균 평점으로 정렬
        popular_categories = sorted(
            [(cat, stats) for cat, stats in category_stats.items()],
            key=lambda x: x[1]['total_rating'] / x[1]['count'],
            reverse=True
        )[:5]
        
        # 최근 활성 사용자
        recent_users = User.query.order_by(desc(User.id)).limit(10).all()
        
        return jsonify({
            'popular_categories': [
                {
                    'category': cat,
                    'average_rating': round(stats['total_rating'] / stats['count'], 1),
                    'total_reviews': stats['total_reviews']
                }
                for cat, stats in popular_categories
            ],
            'recent_active_users': [
                {
                    'employee_id': user.employee_id,
                    'nickname': user.nickname,
                    'lunch_preference': user.lunch_preference
                }
                for user in recent_users
            ]
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# --- 오프라인 데이터 API ---
@app.route('/offline/sync', methods=['POST'])
def sync_offline_data():
    """오프라인 데이터 동기화"""
    try:
        data = request.get_json()
        user_id = data.get('user_id')
        data_type = data.get('data_type')
        data_json = data.get('data_json')
        
        if not all([user_id, data_type, data_json]):
            return jsonify({'error': '필수 데이터가 누락되었습니다.'}), 400
        
        # 기존 데이터 업데이트 또는 새로 생성
        existing_data = OfflineData.query.filter_by(
            user_id=user_id,
            data_type=data_type
        ).first()
        
        if existing_data:
            existing_data.data_json = data_json
            existing_data.last_sync = datetime.utcnow()
        else:
            new_data = OfflineData(user_id, data_type, data_json)
            db.session.add(new_data)
        
        db.session.commit()
        return jsonify({'message': '오프라인 데이터가 동기화되었습니다.'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/offline/data/<employee_id>', methods=['GET'])
def get_offline_data(employee_id):
    """오프라인 데이터 조회"""
    try:
        data_types = request.args.getlist('types')  # 'restaurants', 'parties', 'reviews'
        
        if not data_types:
            return jsonify({'error': '데이터 타입을 지정해주세요.'}), 400
        
        offline_data = {}
        for data_type in data_types:
            data = OfflineData.query.filter_by(
                user_id=employee_id,
                data_type=data_type
            ).first()
            
            if data:
                offline_data[data_type] = {
                    'data': json.loads(data.data_json),
                    'last_sync': data.last_sync.strftime('%Y-%m-%d %H:%M:%S')
                }
        
        return jsonify(offline_data)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# --- 알림 API ---
@app.route('/notifications/<employee_id>', methods=['GET'])
def get_notifications(employee_id):
    """사용자의 알림 목록 조회"""
    notifications = Notification.query.filter_by(user_id=employee_id).order_by(desc(Notification.created_at)).all()
    return jsonify([{
        'id': n.id,
        'type': n.type,
        'title': n.title,
        'message': n.message,
        'related_id': n.related_id,
        'is_read': n.is_read,
        'created_at': n.created_at.strftime('%Y-%m-%d %H:%M')
    } for n in notifications])

@app.route('/notifications/<int:notification_id>/read', methods=['POST'])
def mark_notification_read(notification_id):
    """알림 읽음 처리"""
    notification = Notification.query.get(notification_id)
    if not notification:
        return jsonify({'message': '알림을 찾을 수 없습니다.'}), 404
    
    notification.is_read = True
    db.session.commit()
    return jsonify({'message': '알림이 읽음 처리되었습니다.'})

@app.route('/notifications/<employee_id>/read-all', methods=['POST'])
def mark_all_notifications_read(employee_id):
    """모든 알림 읽음 처리"""
    Notification.query.filter_by(user_id=employee_id, is_read=False).update({'is_read': True})
    db.session.commit()
    return jsonify({'message': '모든 알림이 읽음 처리되었습니다.'})

def create_notification(user_id, type, title, message, related_id=None):
    """알림 생성 헬퍼 함수"""
    notification = Notification(user_id, type, title, message, related_id)
    db.session.add(notification)
    db.session.commit()
    
    # 실시간 알림 전송
    socketio.emit('notification', {
        'type': type,
        'title': title,
        'message': message,
        'related_id': related_id
    }, room=user_id)  # type: ignore

@app.route('/notifications', methods=['POST'])
def create_notification_api():
    """알림 생성 API"""
    try:
        data = request.get_json()
        user_id = data.get('user_id')
        type = data.get('type')
        title = data.get('title')
        message = data.get('message')
        related_id = data.get('related_id')
        
        if not all([user_id, type, title, message]):
            return jsonify({'message': '필수 필드가 누락되었습니다.'}), 400
        
        create_notification(user_id, type, title, message, related_id)
        
        return jsonify({'message': '알림이 생성되었습니다.'}), 201
            
    except Exception as e:
        return jsonify({'message': f'알림 생성 중 오류가 발생했습니다: {str(e)}'}), 500

# --- 단골파티 API ---
@app.route('/dangolpots', methods=['POST'])
def create_dangolpot():
    data = request.get_json() or {}
    new_pot = DangolPot(
        name=data.get('name'),
        description=data.get('description'),
        tags=data.get('tags'),
        category=data.get('category'),
        host_id=data.get('host_id'),
        members=data.get('host_id')
    )
    db.session.add(new_pot)
    db.session.flush()  # ID를 얻기 위해 flush
    
    # 채팅방 자동 생성
    new_pot.create_chat_room()
    
    db.session.commit()
    return jsonify({'message': '새로운 단골파티가 생성되었습니다!', 'pot_id': new_pot.id}), 201

@app.route('/dangolpots', methods=['GET'])
def get_all_dangolpots():
    pots = DangolPot.query.order_by(desc(DangolPot.created_at)).all()
    return jsonify([{'id': p.id, 'name': p.name, 'description': p.description, 'tags': p.tags, 'category': p.category, 'member_count': p.member_count, 'created_at': p.created_at.strftime('%Y-%m-%d')} for p in pots])

@app.route('/dangolpots/<int:pot_id>', methods=['GET'])
def get_dangolpot_detail(pot_id):
    pot = DangolPot.query.get(pot_id)
    if not pot: return jsonify({'message': '단골파티를 찾을 수 없습니다.'}), 404
    member_ids = pot.members.split(',') if pot and pot.members else []
    members_details = [{'employee_id': u.employee_id, 'nickname': u.nickname} for u in User.query.filter(User.employee_id.in_(member_ids)).all()]  # type: ignore
    pot_data = {'id': pot.id, 'name': pot.name, 'description': pot.description, 'tags': pot.tags, 'category': pot.category, 'host_id': pot.host_id, 'members': members_details}
    return jsonify(pot_data)

@app.route('/dangolpots/<int:pot_id>/join', methods=['POST'])
def join_dangolpot(pot_id):
    pot = DangolPot.query.get(pot_id)
    data = request.get_json() or {}
    employee_id = data.get('employee_id')
    if not pot: return jsonify({'message': '단골파티를 찾을 수 없습니다.'}), 404
    
    member_ids = pot.members.split(',') if pot and pot.members else []
    if employee_id and employee_id not in member_ids:
        member_ids.append(employee_id)
        pot.members = ','.join(member_ids)
        db.session.commit()
    return jsonify({'message': '단골파티에 가입했습니다.'})

@app.route('/dangolpots/<int:pot_id>', methods=['DELETE'])
def delete_dangolpot(pot_id):
    pot = DangolPot.query.get(pot_id)
    if not pot:
        return jsonify({'message': '단골파티를 찾을 수 없습니다.'}), 404
    
    employee_id = request.args.get('employee_id')
    if not employee_id:
        return jsonify({'message': '사용자 ID가 필요합니다.'}), 400
    
    if pot.host_id != employee_id:
        return jsonify({'message': '파티장만 삭제할 수 있습니다.'}), 403
    
    db.session.delete(pot)
    db.session.commit()
    return jsonify({'message': '단골파티가 삭제되었습니다.'})

@app.route('/dangolpots/<int:pot_id>', methods=['PUT'])
def update_dangolpot(pot_id):
    pot = DangolPot.query.get(pot_id)
    if not pot:
        return jsonify({'message': '단골파티를 찾을 수 없습니다.'}), 404
    
    data = request.get_json()
    employee_id = data.get('employee_id')
    
    if not employee_id:
        return jsonify({'message': '사용자 ID가 필요합니다.'}), 400
    
    if pot.host_id != employee_id:
        return jsonify({'message': '파티장만 수정할 수 있습니다.'}), 403
    
    pot.name = data.get('name', pot.name)
    pot.description = data.get('description', pot.description)
    pot.tags = data.get('tags', pot.tags)
    pot.category = data.get('category', pot.category)
    
    db.session.commit()
    return jsonify({'message': '단골파티 정보가 수정되었습니다.'})

@app.route('/my_dangolpots/<employee_id>', methods=['GET'])
def get_my_dangolpots(employee_id):
    pots = DangolPot.query.all()
    my_pots = []
    for pot in pots:
        member_ids = pot.members.split(',') if pot and pot.members else []
        if employee_id in member_ids:
            my_pots.append(pot)
    return jsonify([
        {
            'id': p.id,
            'name': p.name,
            'description': p.description,
            'tags': p.tags,
            'category': p.category,
            'member_count': p.member_count,
            'created_at': p.created_at.strftime('%Y-%m-%d')
        } for p in my_pots
    ])

# --- 파티 API ---
@app.route('/parties', methods=['GET'])
def get_all_parties():
    employee_id = request.args.get('employee_id')
    is_from_match = request.args.get('is_from_match')
    
    if employee_id and is_from_match:
        # 특정 사용자의 랜덤런치 그룹 조회
        parties = Party.query.filter(
            Party.is_from_match == True,  # type: ignore
            Party.members_employee_ids.contains(employee_id)  # type: ignore
        ).order_by(desc(Party.id)).all()
    else:
        # 일반 파티 조회 (랜덤런치 제외)
        parties = Party.query.filter_by(is_from_match=False).order_by(desc(Party.id)).all()
    
    return jsonify([{
        'id': p.id, 
        'title': p.title, 
        'restaurant_name': p.restaurant_name, 
        'current_members': p.current_members, 
        'max_members': p.max_members, 
        'party_date': p.party_date, 
        'party_time': p.party_time,
        'is_from_match': p.is_from_match
    } for p in parties])

@app.route('/parties', methods=['POST'])
def create_party():
    data = request.get_json()
    # 필수 입력값 체크
    required_fields = [
        'host_employee_id', 'title', 'restaurant_name',
        'party_date', 'party_time', 'meeting_location', 'max_members'
    ]
    for field in required_fields:
        if not data.get(field):
            return jsonify({'message': f'필수 입력값이 누락되었습니다: {field}'}), 400

    # max_members 정수 변환 및 검증
    try:
        max_members = int(data['max_members'])
        if max_members < 1:
            return jsonify({'message': '최대 인원(max_members)은 1명 이상이어야 합니다.'}), 400
    except (ValueError, TypeError):
        return jsonify({'message': '최대 인원(max_members)은 숫자여야 합니다.'}), 400

    # 레스토랑 주소 가져오기
    restaurant = Restaurant.query.filter_by(name=data.get('restaurant_name')).first()  # type: ignore
    restaurant_address = restaurant.address if restaurant else None

    # 멤버 ID 처리 - 프론트엔드에서 전달된 값이 있으면 사용, 없으면 호스트만
    members_employee_ids = data.get('members_employee_ids', str(data['host_employee_id']))
    if isinstance(members_employee_ids, list):
        # 리스트인 경우 문자열로 변환
        members_employee_ids = ','.join(members_employee_ids)

    # Party 생성
    new_party = Party(
        host_employee_id=data['host_employee_id'],
        title=data['title'],
        restaurant_name=data['restaurant_name'],
        restaurant_address=restaurant_address,
        party_date=data['party_date'],
        party_time=data['party_time'],
        meeting_location=data['meeting_location'],
        max_members=max_members,
        members_employee_ids=members_employee_ids,
        is_from_match=data.get('is_from_match', False)
    )
    db.session.add(new_party)
    db.session.flush()  # ID를 얻기 위해 flush
    
    # 채팅방 자동 생성
    new_party.create_chat_room()
    
    db.session.commit()
    return jsonify({'message': '파티가 생성되었습니다.', 'party_id': new_party.id}), 201

@app.route('/parties/<int:party_id>', methods=['GET'])
def get_party(party_id):
    party = Party.query.get(party_id)
    if not party: return jsonify({'message': '파티를 찾을 수 없습니다.'}), 404
    member_ids = party.members_employee_ids.split(',') if party and party.members_employee_ids else []
    members_details = [{
        'employee_id': u.employee_id, 
        'nickname': u.nickname,
        'lunch_preference': u.lunch_preference,
        'main_dish_genre': u.main_dish_genre
    } for u in User.query.filter(User.employee_id.in_(member_ids)).all()]  # type: ignore
    party_data = {'id': party.id, 'host_employee_id': party.host_employee_id, 'title': party.title, 'restaurant_name': party.restaurant_name, 'restaurant_address': party.restaurant_address, 'party_date': party.party_date, 'party_time': party.party_time, 'meeting_location': party.meeting_location, 'max_members': party.max_members, 'current_members': party.current_members, 'members': members_details, 'is_from_match': party.is_from_match}
    return jsonify(party_data)

@app.route('/parties/<int:party_id>', methods=['PUT'])
def update_party(party_id):
    party = Party.query.get(party_id)
    data = request.get_json()
    if not party: return jsonify({'message': '파티를 찾을 수 없습니다.'}), 404
    if party.host_employee_id != data.get('employee_id'): return jsonify({'message': '파티장만 수정할 수 있습니다.'}), 403
    party.title = data.get('title', party.title)
    party.restaurant_name = data.get('restaurant_name', party.restaurant_name)
    party.party_date = data.get('party_date', party.party_date)
    party.party_time = data.get('party_time', party.party_time)
    party.meeting_location = data.get('meeting_location', party.meeting_location)
    party.max_members = data.get('max_members', party.max_members)
    db.session.commit()
    return jsonify({'message': '파티 정보가 수정되었습니다.'})

@app.route('/parties/<int:party_id>/join', methods=['POST'])
def join_party(party_id):
    party = Party.query.get(party_id)
    data = request.get_json() or {}
    employee_id = data.get('employee_id')
    if party and party.current_members >= party.max_members: return jsonify({'message': '파티 인원이 가득 찼습니다.'}), 400
    if party and employee_id and employee_id not in party.members_employee_ids.split(','):
        party.members_employee_ids += f',{employee_id}'; db.session.commit()
    return jsonify({'message': '파티에 참여했습니다.'})

@app.route('/parties/<int:party_id>/leave', methods=['POST'])
def leave_party(party_id):
    party = Party.query.get(party_id)
    if not party:
        return jsonify({'message': '파티를 찾을 수 없습니다.'}), 404
    
    data = request.get_json() or {}
    employee_id = data.get('employee_id')
    if not employee_id:
        return jsonify({'message': '사용자 ID가 필요합니다.'}), 400
    
    # 파티장은 나갈 수 없음 (파티 삭제를 사용해야 함)
    if party.host_employee_id == employee_id:
        return jsonify({'message': '파티장은 파티를 나갈 수 없습니다. 파티 삭제를 사용해주세요.'}), 400
    
    # 멤버 목록에서 제거
    if party.members_employee_ids:
        member_ids = party.members_employee_ids.split(',')
        if employee_id in member_ids:
            member_ids.remove(employee_id)
            party.members_employee_ids = ','.join(member_ids)
            db.session.commit()
            return jsonify({'message': '파티에서 나갔습니다.'})
        else:
            return jsonify({'message': '이미 파티에 참여하지 않습니다.'}), 400
    else:
        return jsonify({'message': '이미 파티에 참여하지 않습니다.'}), 400

@app.route('/my_parties/<employee_id>', methods=['GET'])
def get_my_parties(employee_id):
    # 내가 참여한 파티들 (호스트이거나 멤버인 경우)
    my_parties = Party.query.filter(
        or_(
            Party.host_employee_id == employee_id,  # type: ignore
            Party.members_employee_ids.contains(employee_id)  # type: ignore
        )
    ).all()
    
    parties_data = []
    for party in my_parties:
        member_ids = party.members_employee_ids.split(',') if party.members_employee_ids else []
        members_details = [{
            'employee_id': u.employee_id, 
            'nickname': u.nickname,
            'lunch_preference': u.lunch_preference,
            'main_dish_genre': u.main_dish_genre
        } for u in User.query.filter(User.employee_id.in_(member_ids)).all()]  # type: ignore
        
        party_data = {
            'id': party.id,
            'host_employee_id': party.host_employee_id,
            'title': party.title,
            'restaurant_name': party.restaurant_name,
            'restaurant_address': party.restaurant_address,
            'party_date': party.party_date,
            'party_time': party.party_time,
            'meeting_location': party.meeting_location,
            'max_members': party.max_members,
            'current_members': party.current_members,
            'members': members_details,
            'is_from_match': party.is_from_match
        }
        parties_data.append(party_data)
    
    return jsonify(parties_data)

@app.route('/my_regular_parties/<employee_id>', methods=['GET'])
def get_my_regular_parties(employee_id):
    # 내가 참여한 일반파티들만 (랜덤런치 제외)
    my_regular_parties = Party.query.filter(
        and_(
            Party.is_from_match == False,  # type: ignore
            or_(
                Party.host_employee_id == employee_id,  # type: ignore
                Party.members_employee_ids.contains(employee_id)  # type: ignore
            )
        )
    ).all()
    
    parties_data = []
    for party in my_regular_parties:
        member_ids = party.members_employee_ids.split(',') if party.members_employee_ids else []
        members_details = [{
            'employee_id': u.employee_id, 
            'nickname': u.nickname,
            'lunch_preference': u.lunch_preference,
            'main_dish_genre': u.main_dish_genre
        } for u in User.query.filter(User.employee_id.in_(member_ids)).all()]  # type: ignore
        
        party_data = {
            'id': party.id,
            'host_employee_id': party.host_employee_id,
            'title': party.title,
            'restaurant_name': party.restaurant_name,
            'restaurant_address': party.restaurant_address,
            'party_date': party.party_date,
            'party_time': party.party_time,
            'meeting_location': party.meeting_location,
            'max_members': party.max_members,
            'current_members': party.current_members,
            'members': members_details,
            'is_from_match': party.is_from_match
        }
        parties_data.append(party_data)
    
    return jsonify(parties_data)

@app.route('/parties/<int:party_id>', methods=['DELETE'])
def delete_party(party_id):
    party = Party.query.get(party_id)
    if not party:
        return jsonify({'message': '파티를 찾을 수 없습니다.'}), 404
    
    employee_id = request.args.get('employee_id')
    if not employee_id:
        return jsonify({'message': '사용자 ID가 필요합니다.'}), 400
    
    if party.host_employee_id != employee_id:
        return jsonify({'message': '파티장만 삭제할 수 있습니다.'}), 403
    
    db.session.delete(party)
    db.session.commit()
    return jsonify({'message': '파티가 삭제되었습니다.'})

# --- 랜덤런치, 사용자 프로필, 소통 API 등은 이전과 동일하게 유지 ---
@app.route('/match/status/<employee_id>', methods=['GET'])
def get_match_status(employee_id):
    user = User.query.filter_by(employee_id=employee_id).first()
    if not user: return jsonify({'message': '사용자를 찾을 수 없습니다.'}), 404
    user = reset_user_match_status_if_needed(user)
    response = {'status': user.matching_status}
    if user.matching_status == 'waiting':
        now = datetime.now()
        match_time = now.replace(hour=10, minute=0, second=0, microsecond=0)
        if now < match_time:
            response['countdown_target'] = match_time.isoformat()
    return jsonify(response)

@app.route('/match/request', methods=['POST'])
def request_match():
    data = request.get_json()
    employee_id = data['employee_id']
    
    user = User.query.filter_by(employee_id=employee_id).first()
    if not user: return jsonify({'message': '사용자를 찾을 수 없습니다.'}), 404
    
    now = datetime.now()
    today_10am = now.replace(hour=10, minute=0, second=0, microsecond=0)
    
    # 예약 매칭 (전일 14:00 ~ 당일 10:00)
    if now < today_10am:
        user.matching_status = 'waiting'
        user.match_request_time = now
        db.session.commit()
        return jsonify({'message': '오전 10시 매칭 대기열에 등록되었습니다.', 'status': 'waiting'})
    
    # 실시간 매칭 (당일 10:00 ~ 14:00)
    else:
        # 대기 중인 다른 사용자 찾기
        waiting_users = User.query.filter(
            User.matching_status == 'waiting',  # type: ignore
            User.employee_id != employee_id  # type: ignore
        ).all()  # type: ignore
        
        if waiting_users:
            # 스마트 매칭: 선호도 기반으로 최적의 파트너 찾기
            best_match = find_best_match(user, employee_id)
            
            if best_match:
                # 파티 생성
                new_party = Party(
                    host_employee_id=employee_id,
                    title='스마트 런치',
                    restaurant_name='스마트 매칭',
                    restaurant_address=None,
                    party_date=now.strftime('%Y-%m-%d'),
                    party_time='12:00',
                    meeting_location='KOICA 본사',
                    max_members=2,
                    members_employee_ids=f"{employee_id},{best_match.employee_id}",
                    is_from_match=True
                )
                db.session.add(new_party)
                
                # 두 사용자 모두 matched 상태로 변경
                user.matching_status = 'matched'
                best_match.matching_status = 'matched'
                db.session.commit()
                
                compatibility_score = calculate_compatibility_score(user, best_match)
                
                return jsonify({
                    'message': '스마트 매칭이 완료되었습니다!',
                    'status': 'matched',
                    'party_id': new_party.id,
                    'compatibility_score': round(compatibility_score, 2),
                    'partner': {
                        'employee_id': best_match.employee_id,
                        'nickname': best_match.nickname
                    }
                })
            else:
                # 호환성 높은 파트너가 없으면 대기
                user.matching_status = 'waiting'
                user.match_request_time = now
                db.session.commit()
                return jsonify({'message': '최적의 파트너를 기다리는 중입니다...', 'status': 'waiting'})
        else:
            # 대기 상태로 변경
            user.matching_status = 'waiting'
            user.match_request_time = now
            db.session.commit()
            return jsonify({'message': '매칭 대기 중입니다...', 'status': 'waiting'})

@app.route('/match/confirm', methods=['POST'])
def confirm_match():
    data = request.get_json()
    group_id = data['group_id']
    employee_id = data['employee_id']
    
    # 매칭 그룹 확인 및 파티 생성 로직
    # (실제 구현에서는 더 복잡한 매칭 로직이 필요)
    
    return jsonify({'message': '매칭이 확정되었습니다.', 'status': 'confirmed'})

@app.route('/match/cancel', methods=['POST'])
def cancel_match():
    data = request.get_json()
    employee_id = data['employee_id']
    
    user = User.query.filter_by(employee_id=employee_id).first()
    if not user:
        return jsonify({'message': '사용자를 찾을 수 없습니다.'}), 404
    
    if user.matching_status == 'waiting':
        user.matching_status = 'idle'
        user.match_request_time = None
        db.session.commit()
        return jsonify({'message': '매칭 대기가 취소되었습니다.', 'status': 'cancelled'})
    else:
        return jsonify({'message': '매칭 대기 상태가 아닙니다.'}), 400

@app.route('/match/reject', methods=['POST'])
def reject_match():
    data = request.get_json()
    employee_id = data['employee_id']
    
    user = User.query.filter_by(employee_id=employee_id).first()
    if user:
        user.matching_status = 'idle'
        user.match_request_time = None
        db.session.commit()
    
    return jsonify({'message': '매칭을 거절했습니다.', 'status': 'rejected'})

# --- 새로운 랜덤 런치 시스템 API ---
@app.route('/proposals/available-dates', methods=['GET'])
def get_available_dates():
    employee_id = request.args.get('employee_id')
    if not employee_id:
        return jsonify({'message': 'employee_id가 필요합니다.'}), 400
    
    today = get_seoul_today()
    available_dates = []
    
    for i in range(14):  # 오늘부터 14일 후까지
        check_date = today + timedelta(days=i)
        date_str = check_date.strftime('%Y-%m-%d')
        
        # 해당 날짜에 파티나 개인 일정이 있는지 확인
        # SQLAlchemy 쿼리 - 타입 힌팅 경고는 무시해도 됨
        party_query = Party.query.filter(
            Party.members_employee_ids.contains(employee_id),  # type: ignore
            Party.party_date == date_str  # type: ignore
        )
        has_party = party_query.first() is not None
        
        has_schedule = PersonalSchedule.query.filter_by(
            employee_id=employee_id,
            schedule_date=date_str
        ).first() is not None
        
        if not has_party and not has_schedule:
            available_dates.append(date_str)
    
    return jsonify(available_dates)

@app.route('/proposals/date-recommendations', methods=['GET'])
def get_date_recommendations():
    """특정 날짜의 추천 그룹을 가져오는 API"""
    employee_id = request.args.get('employee_id')
    selected_date = request.args.get('date')
    
    if not employee_id or not selected_date:
        return jsonify({'error': 'employee_id and date are required'}), 400

    try:
        # 해당 날짜의 기존 추천 그룹이 있는지 확인
        existing_recommendations = DailyRecommendation.query.filter_by(date=selected_date).all()
        
        if existing_recommendations:
            # 기존 추천 그룹이 있으면 반환
            recommendations = []
            for rec in existing_recommendations:
                group_members = json.loads(rec.group_members)
                recommendations.append({
                    "proposed_date": selected_date,
                    "recommended_group": group_members
                })
            return jsonify(recommendations)
        
        # 기존 추천 그룹이 없으면 빈 배열 반환 (매일 자정에만 생성됨)
        return jsonify([])
        
    except Exception as e:
        print(f"Error getting date recommendations: {e}")
        return jsonify({'error': 'Failed to get date recommendations'}), 500

@app.route('/proposals/suggest-groups', methods=['POST'])
def suggest_groups():
    data = request.get_json() or {}
    employee_id = data.get('employee_id')
    date = data.get('date')
    
    if not employee_id or not date:
        return jsonify({'message': 'employee_id와 date가 필요합니다.'}), 400
    
    # 해당 날짜에 약속이 없는 모든 유저 찾기
    busy_users = set()
    
    # 파티에 참여하는 유저들
    parties = Party.query.filter(Party.party_date == date).all()  # type: ignore
    for party in parties:
        if party.members_employee_ids:
            busy_users.update(party.members_employee_ids.split(','))
    
    # 개인 일정이 있는 유저들
    schedules = PersonalSchedule.query.filter_by(schedule_date=date).all()
    for schedule in schedules:
        busy_users.add(schedule.employee_id)
    
    # 요청자도 제외
    busy_users.add(employee_id)
    
    # 가능한 유저들
    available_users = User.query.filter(~User.employee_id.in_(busy_users)).all()  # type: ignore
    
    if not available_users:
        return jsonify([])
    
    # 요청자 정보 가져오기
    proposer = User.query.filter_by(employee_id=employee_id).first()
    if not proposer:
        return jsonify({'message': '사용자를 찾을 수 없습니다.'}), 404
    
    # 성향 매칭 점수 계산
    user_scores = []
    for user in available_users:
        score = 0
        
        # lunch_preference 매칭
        if proposer.lunch_preference and user.lunch_preference:
            proposer_prefs = set(proposer.lunch_preference.split(','))
            user_prefs = set(user.lunch_preference.split(','))
            score += len(proposer_prefs.intersection(user_prefs))
        
        # main_dish_genre 매칭
        if proposer.main_dish_genre and user.main_dish_genre:
            proposer_genres = set(proposer.main_dish_genre.split(','))
            user_genres = set(user.main_dish_genre.split(','))
            score += len(proposer_genres.intersection(user_genres))
        
        user_scores.append((user, score))
    
    # 점수순으로 정렬
    user_scores.sort(key=lambda x: x[1], reverse=True)
    
    # 중복 제거를 위한 함수
    def create_group_key(group_users):
        """그룹의 고유 키를 생성하는 함수"""
        user_ids = sorted([user.employee_id for user in group_users])
        return ','.join(user_ids)
    
    # 여러 그룹 생성 (최대 5개)
    groups = []
    used_users = set()
    seen_groups = set()  # 중복 제거를 위한 set
    
    for group_idx in range(min(5, len(user_scores) // 3 + 1)):
        group_users = []
        
        # 높은 점수 순으로 그룹에 추가
        for user, score in user_scores:
            if len(group_users) >= 3:
                break
            if user.employee_id not in used_users:
                group_users.append(user)
                used_users.add(user.employee_id)
        
        # 부족하면 랜덤으로 추가
        if len(group_users) < 3:
            remaining_users = [user for user, _ in user_scores if user.employee_id not in used_users]
            random.shuffle(remaining_users)
            for user in remaining_users[:3-len(group_users)]:
                group_users.append(user)
                used_users.add(user.employee_id)
        
        if group_users:
            # 중복 제거를 위한 그룹 키 생성
            group_key = create_group_key(group_users)
            
            # 중복되지 않은 그룹만 추가
            if group_key not in seen_groups:
                seen_groups.add(group_key)
                groups.append({
                    'group_id': len(groups) + 1,  # 중복 제거 후 실제 인덱스 사용
                    'users': [{
                        'employee_id': user.employee_id,
                        'nickname': user.nickname,
                        'lunch_preference': user.lunch_preference,
                        'main_dish_genre': user.main_dish_genre,
                        'gender': user.gender,
                        'age_group': user.age_group
                    } for user in group_users]
                })
    
    return jsonify(groups)

@app.route('/proposals', methods=['POST'])
def create_proposal():
    data = request.get_json() or {}
    proposer_id = data.get('proposer_id')
    recipient_ids = data.get('recipient_ids')  # 리스트 형태
    proposed_date = data.get('proposed_date')
    
    if not proposer_id or not recipient_ids or not proposed_date:
        return jsonify({'message': 'proposer_id, recipient_ids, proposed_date가 필요합니다.'}), 400
    
    # recipient_ids가 리스트인지 확인하고 문자열로 변환
    if isinstance(recipient_ids, list):
        recipient_ids_str = ','.join(recipient_ids)
    else:
        recipient_ids_str = str(recipient_ids)
    
    new_proposal = LunchProposal(
        proposer_id=proposer_id,
        recipient_ids=recipient_ids_str,
        proposed_date=proposed_date
    )
    
    db.session.add(new_proposal)
    db.session.commit()
    
    return jsonify({
        'id': new_proposal.id,
        'proposer_id': new_proposal.proposer_id,
        'recipient_ids': new_proposal.recipient_ids,
        'proposed_date': new_proposal.proposed_date,
        'status': new_proposal.status,
        'created_at': new_proposal.created_at.strftime('%Y-%m-%d %H:%M'),
        'expires_at': new_proposal.expires_at.strftime('%Y-%m-%d %H:%M')
    }), 201

@app.route('/proposals/mine', methods=['GET'])
def get_my_proposals():
    employee_id = request.args.get('employee_id')
    if not employee_id:
        return jsonify({'message': 'employee_id가 필요합니다.'}), 400
    
    # 내가 보낸 제안들
    sent_proposals = LunchProposal.query.filter_by(proposer_id=employee_id).order_by(desc(LunchProposal.created_at)).all()
    
    # 내가 받은 제안들
    received_proposals = LunchProposal.query.filter(
        LunchProposal.recipient_ids.contains(employee_id)  # type: ignore
    ).order_by(desc(LunchProposal.created_at)).all()
    
    def format_proposal(proposal):
        # 수락한 사람들의 닉네임 리스트
        acceptances = ProposalAcceptance.query.filter_by(proposal_id=proposal.id).all()
        accepted_user_ids = [acc.user_id for acc in acceptances]
        accepted_users = User.query.filter(User.employee_id.in_(accepted_user_ids)).all()  # type: ignore
        accepted_nicknames = [user.nickname for user in accepted_users]
        
        return {
            'id': proposal.id,
            'proposer_id': proposal.proposer_id,
            'recipient_ids': proposal.recipient_ids,
            'proposed_date': proposal.proposed_date,
            'status': proposal.status,
            'created_at': proposal.created_at.strftime('%Y-%m-%d %H:%M'),
            'expires_at': proposal.expires_at.strftime('%Y-%m-%d %H:%M'),
            'accepted_nicknames': accepted_nicknames
        }
    
    return jsonify({
        'sent_proposals': [format_proposal(p) for p in sent_proposals],
        'received_proposals': [format_proposal(p) for p in received_proposals]
    })

@app.route('/proposals/<int:proposal_id>/accept', methods=['POST'])
def accept_proposal(proposal_id):
    data = request.get_json() or {}
    user_id = data.get('user_id')
    
    if not user_id:
        return jsonify({'message': 'user_id가 필요합니다.'}), 400
    
    # 1단계: 유효성 검사
    proposal = LunchProposal.query.get(proposal_id)
    if not proposal:
        return jsonify({'message': '제안을 찾을 수 없습니다.'}), 404
    
    if proposal.status != 'pending':
        return jsonify({'message': '이미 처리된 제안입니다.'}), 400
    
    if datetime.utcnow() > proposal.expires_at:
        return jsonify({'message': '제안이 만료되었습니다.'}), 400
    
    # 요청한 user_id가 recipient_ids에 포함되는지 확인
    recipient_ids = proposal.recipient_ids.split(',') if proposal.recipient_ids else []
    if user_id not in recipient_ids:
        return jsonify({'message': '이 제안의 수신자가 아닙니다.'}), 403
    
    # 해당 유저가 이미 제안된 날짜에 다른 약속이 있는지 확인
    proposed_date = proposal.proposed_date
    
    # 파티 확인
    has_party = Party.query.filter(
        Party.members_employee_ids.contains(user_id),  # type: ignore
        Party.party_date == proposed_date  # type: ignore
    ).first() is not None
    
    # 개인 일정 확인
    has_schedule = PersonalSchedule.query.filter_by(
        employee_id=user_id,
        schedule_date=proposed_date
    ).first() is not None
    
    if has_party or has_schedule:
        return jsonify({'message': '이미 다른 약속이 있어 수락할 수 없습니다.'}), 409
    
    # 2단계: 수락 기록
    # 이미 수락했는지 확인
    existing_acceptance = ProposalAcceptance.query.filter_by(
        proposal_id=proposal_id,
        user_id=user_id
    ).first()
    
    if existing_acceptance:
        return jsonify({'message': '이미 수락한 제안입니다.'}), 400
    
    new_acceptance = ProposalAcceptance(proposal_id=proposal_id, user_id=user_id)
    db.session.add(new_acceptance)
    
    # 3단계: 성사 여부 확인
    all_members = [proposal.proposer_id] + recipient_ids
    accepted_count = ProposalAcceptance.query.filter_by(proposal_id=proposal_id).count() + 1  # +1은 현재 수락
    
    if accepted_count >= 2:
        # 4단계: 성사 프로세스
        proposal.status = 'confirmed'
        
        # 새로운 Party 생성
        new_party = Party(
            host_employee_id=proposal.proposer_id,
            title='랜덤 런치',
            restaurant_name='랜덤 매칭',
            restaurant_address=None,
            party_date=proposal.proposed_date,
            party_time='12:00',
            meeting_location='KOICA 본사',
            max_members=len(all_members),
            members_employee_ids=','.join(all_members),
            is_from_match=True
        )
        db.session.add(new_party)
        
        # 같은 날짜의 다른 pending 제안들을 cancelled로 변경
        other_pending_proposals = LunchProposal.query.filter(
            LunchProposal.status == 'pending',  # type: ignore
            LunchProposal.proposed_date == proposed_date,  # type: ignore
            LunchProposal.id != proposal_id
        ).all()
        
        for other_proposal in other_pending_proposals:
            other_members = [other_proposal.proposer_id] + other_proposal.recipient_ids.split(',')
            # 겹치는 멤버가 있는지 확인
            if any(member in all_members for member in other_members):
                other_proposal.status = 'cancelled'
        
        db.session.commit()
        return jsonify({'message': '매칭이 성사되었습니다!', 'status': 'confirmed', 'party_id': new_party.id})
    else:
        # 5단계: 단순 수락
        db.session.commit()
        return jsonify({'message': '수락이 기록되었습니다. 1명 이상 더 수락하면 매칭이 성사됩니다.', 'status': 'accepted'})

@app.route('/proposals/<int:proposal_id>/cancel', methods=['POST'])
def cancel_proposal(proposal_id):
    data = request.get_json() or {}
    user_id = data.get('user_id') or data.get('employee_id')
    
    if not user_id:
        return jsonify({'message': 'user_id 또는 employee_id가 필요합니다.'}), 400
    
    proposal = LunchProposal.query.get(proposal_id)
    if not proposal:
        return jsonify({'message': '제안을 찾을 수 없습니다.'}), 404
    
    if proposal.proposer_id != user_id:
        return jsonify({'message': '제안자만 취소할 수 있습니다.'}), 403
    
    if proposal.status != 'pending':
        return jsonify({'message': '이미 처리된 제안은 취소할 수 없습니다.'}), 400
    
    proposal.status = 'cancelled'
    db.session.commit()
    
    return jsonify({'message': '제안이 취소되었습니다.', 'status': 'cancelled'})

@app.route('/chats/<employee_id>', methods=['GET'])
def get_my_chats(employee_id):
    chat_list = []
    
    print(f"=== DEBUG: 채팅방 목록 조회 시작 (사용자: {employee_id}) ===")
    
    # 파티 채팅방들
    party_chat_list = []
    joined_parties = Party.query.filter(Party.members_employee_ids.contains(employee_id)).order_by(desc(Party.id)).all()  # type: ignore
    
    # 중복 제거를 위한 set
    seen_party_ids = set()
    
    for party in joined_parties:
        # 중복 체크
        if party.id in seen_party_ids:
            continue
        seen_party_ids.add(party.id)
        
        # 파티의 마지막 메시지 가져오기
        last_message = ChatMessage.query.filter_by(
            chat_type='party',
            chat_id=party.id
        ).order_by(desc(ChatMessage.created_at)).first()
        
        # 최근 메시지 미리보기 (최대 15글자)
        if last_message:
            message_preview = last_message.message
            if len(message_preview) > 15:
                message_preview = message_preview[:15] + '...'
        else:
            message_preview = f"{party.restaurant_name} | {party.current_members}/{party.max_members}명"
        
        party_chat_list.append({
            'id': party.id, 
            'type': 'party', 
            'title': party.title, 
            'subtitle': message_preview,
            'is_from_match': party.is_from_match,
            'last_message_time': last_message.created_at if last_message else None,
            'unread_count': 3 if party.id % 2 == 0 else 0  # 테스트용 안읽은 메시지 수
        })
    
    # 단골파티 채팅방들
    pot_chat_list = []
    joined_pots = DangolPot.query.filter(DangolPot.members.contains(employee_id)).order_by(desc(DangolPot.created_at)).all()  # type: ignore
    
    # 중복 제거를 위한 set
    seen_pot_ids = set()
    
    for pot in joined_pots:
        # 중복 체크
        if pot.id in seen_pot_ids:
            continue
        seen_pot_ids.add(pot.id)
        
        # 단골파티의 마지막 메시지 가져오기
        last_message = ChatMessage.query.filter_by(
            chat_type='dangolpot',
            chat_id=pot.id
        ).order_by(desc(ChatMessage.created_at)).first()
        
        # 최근 메시지 미리보기 (최대 15글자)
        if last_message:
            message_preview = last_message.message
            if len(message_preview) > 15:
                message_preview = message_preview[:15] + '...'
        else:
            message_preview = pot.tags
        
        pot_chat_list.append({
            'id': pot.id, 
            'type': 'dangolpot', 
            'title': pot.name, 
            'subtitle': message_preview,
            'last_message_time': last_message.created_at if last_message else None,
            'unread_count': 5 if pot.id % 3 == 0 else 0  # 테스트용 안읽은 메시지 수
        })
    
    # 일반 채팅방들 (투표로 생성된 채팅방 포함)
    user_participations = ChatParticipant.query.filter_by(user_id=employee_id).all()
    print(f"=== DEBUG: 사용자 참여 채팅방 수: {len(user_participations)} ===")
    
    custom_chat_list = []
    
    # 중복 제거를 위한 set
    seen_chat_room_ids = set()
    
    for participation in user_participations:
        chat_room = ChatRoom.query.get(participation.room_id)
        print(f"=== DEBUG: 채팅방 ID {participation.room_id} - 타입: {chat_room.type if chat_room else 'None'} - 이름: {chat_room.name if chat_room else 'None'} ===")
        
        # 중복 체크
        if chat_room and chat_room.id in seen_chat_room_ids:
            continue
        if chat_room:
            seen_chat_room_ids.add(chat_room.id)
        
        if chat_room and chat_room.type in ['group', 'friend']:
            # 마지막 메시지 가져오기 (투표로 생성된 채팅방의 경우 chat_type='custom' 사용)
            last_message = ChatMessage.query.filter_by(
                chat_type='custom', 
                chat_id=chat_room.id
            ).order_by(desc(ChatMessage.created_at)).first()
            
            print(f"=== DEBUG: chat_type='custom'으로 검색한 마지막 메시지: {last_message.message if last_message else 'None'} ===")
            
            # 마지막 메시지가 없으면 다른 chat_type으로도 시도
            if not last_message:
                last_message = ChatMessage.query.filter_by(
                    chat_id=chat_room.id
                ).order_by(desc(ChatMessage.created_at)).first()
                
                print(f"=== DEBUG: chat_id로만 검색한 마지막 메시지: {last_message.message if last_message else 'None'} ===")
            
            # 최근 메시지 미리보기 (최대 15글자)
            message_preview = last_message.message if last_message else '새로운 채팅방입니다'
            if len(message_preview) > 15:
                message_preview = message_preview[:15] + '...'
            
            custom_chat_list.append({
                'id': chat_room.id, 
                'type': 'custom', 
                'title': chat_room.name or '새로운 채팅방',
                'subtitle': message_preview,
                'last_message': last_message.message if last_message else None,
                'last_message_time': last_message.created_at if last_message else None,
                'unread_count': 2 if chat_room.id % 2 == 0 else 0  # 테스트용 안읽은 메시지 수
            })
    
    # 마지막 메시지 시간 기준으로 정렬 (최신 메시지가 있는 채팅방이 위로)
    custom_chat_list.sort(key=lambda x: x['last_message_time'] or datetime.min, reverse=True)
    
    # 파티 채팅방들도 마지막 메시지 시간 기준으로 정렬
    party_chat_list.sort(key=lambda x: x['last_message_time'] or datetime.min, reverse=True)
    
    # 단골파티 채팅방들도 마지막 메시지 시간 기준으로 정렬
    pot_chat_list.sort(key=lambda x: x['last_message_time'] or datetime.min, reverse=True)
    
    # 모든 채팅방을 하나의 리스트로 합치고 마지막 메시지 시간 기준으로 정렬
    all_chats = party_chat_list + pot_chat_list + custom_chat_list
    all_chats.sort(key=lambda x: x['last_message_time'] or datetime.min, reverse=True)
    
    # last_message_time 필드 제거하지 않음 (프론트엔드에서 사용)
    # 디버깅을 위한 로그 추가
    print(f"=== DEBUG: 최종 채팅방 목록 ===")
    for i, chat in enumerate(all_chats):
        print(f"채팅방 {i+1}: {chat['title']} - last_message_time: {chat.get('last_message_time')} - unread_count: {chat.get('unread_count')}")
    
    chat_list = all_chats
    
    print(f"=== DEBUG: 최종 채팅방 목록: {chat_list} ===")
    return jsonify(chat_list)

@app.route('/users/<employee_id>', methods=['GET'])
def get_user(employee_id):
    user = User.query.filter_by(employee_id=employee_id).first()
    if not user: return jsonify({'message': '사용자를 찾을 수 없습니다.'}), 404
    return jsonify({'nickname': user.nickname, 'lunch_preference': user.lunch_preference, 'gender': user.gender, 'age_group': user.age_group, 'main_dish_genre': user.main_dish_genre})

@app.route('/users/batch', methods=['POST'])
def get_users_batch():
    data = request.get_json() or {}
    user_ids = data.get('user_ids', [])
    
    if not user_ids:
        return jsonify({'message': 'user_ids가 필요합니다.'}), 400
    
    users = User.query.filter(User.employee_id.in_(user_ids)).all()  # type: ignore
    return jsonify([{
        'employee_id': user.employee_id,
        'nickname': user.nickname,
        'lunch_preference': user.lunch_preference,
        'main_dish_genre': user.main_dish_genre
    } for user in users])

@app.route('/users/<employee_id>', methods=['PUT'])
def update_user(employee_id):
    user = User.query.filter_by(employee_id=employee_id).first()
    if not user: return jsonify({'message': '사용자를 찾을 수 없습니다.'}), 404
    
    data = request.get_json()
    user.nickname = data.get('nickname', user.nickname)
    user.lunch_preference = data.get('lunch_preference', user.lunch_preference)
    user.gender = data.get('gender', user.gender)
    user.age_group = data.get('age_group', user.age_group)
    user.main_dish_genre = data.get('main_dish_genre', user.main_dish_genre)
    
    db.session.commit()
    return jsonify({'message': '프로필이 업데이트되었습니다.'})

@app.route('/users/<employee_id>/preferences', methods=['PUT'])
def update_user_preferences(employee_id):
    data = request.get_json()
    user = User.query.filter_by(employee_id=employee_id).first()
    if not user:
        return jsonify({'message': '사용자를 찾을 수 없습니다.'}), 404
    
    # 사용자 선호도 정보 업데이트
    if 'foodPreferences' in data:
        user.food_preferences = ','.join(data['foodPreferences'])
    if 'allergies' in data:
        user.allergies = ','.join(data['allergies'])
    if 'preferredTime' in data:
        user.preferred_time = data['preferredTime']
    if 'frequentAreas' in data:
        user.frequent_areas = ','.join(data['frequentAreas'])
    if 'notifications' in data:
        user.notification_settings = ','.join(data['notifications'])
    
    db.session.commit()
    return jsonify({'message': '사용자 선호도가 저장되었습니다.'})

@app.route('/users/<employee_id>/preferences', methods=['GET'])
def get_user_preferences(employee_id):
    user = User.query.filter_by(employee_id=employee_id).first()
    if not user:
        return jsonify({'message': '사용자를 찾을 수 없습니다.'}), 404
    
    preferences = {
        'foodPreferences': user.food_preferences.split(',') if user.food_preferences else [],
        'allergies': user.allergies.split(',') if user.allergies else [],
        'preferredTime': user.preferred_time or '',
        'frequentAreas': user.frequent_areas.split(',') if user.frequent_areas else [],
        'notifications': user.notification_settings.split(',') if user.notification_settings else []
    }
    
    return jsonify(preferences)

# --- 채팅 API ---
@app.route('/chat/messages/<chat_type>/<int:chat_id>', methods=['GET'])
def get_chat_messages(chat_type, chat_id):
    print(f"=== DEBUG: 채팅 메시지 조회 - chat_type: {chat_type}, chat_id: {chat_id} ===")
    
    messages = ChatMessage.query.filter_by(chat_type=chat_type, chat_id=chat_id).order_by(ChatMessage.created_at).all()
    print(f"=== DEBUG: 조회된 메시지 수: {len(messages)} ===")
    
    for msg in messages:
        print(f"=== DEBUG: 메시지 - ID: {msg.id}, 발신자: {msg.sender_nickname}, 내용: {msg.message[:50]}... ===")

    # 채팅방 참여자 목록 구하기
    if chat_type == 'party':
        party = Party.query.get(chat_id)
        if party and party.members_employee_ids:
            member_ids = [mid.strip() for mid in party.members_employee_ids.split(',') if mid.strip()]
        else:
            member_ids = []
    elif chat_type == 'dangolpot':
        pot = DangolPot.query.get(chat_id)
        if pot and pot.members:
            member_ids = [mid.strip() for mid in pot.members.split(',') if mid.strip()]
        else:
            member_ids = []
    elif chat_type == 'custom':
        # custom 채팅은 ChatRoom/ChatParticipant에서 조회 (투표로 생성된 채팅방 포함)
        room = ChatRoom.query.get(chat_id)
        if room:
            participants = ChatParticipant.query.filter_by(room_id=room.id).all()
            member_ids = [p.user_id for p in participants]
        else:
            member_ids = []
    else:
        member_ids = []

    result = []
    for msg in messages:
        read_count = ChatMessageRead.query.filter_by(message_id=msg.id).count()
        unread_count = max(0, len(member_ids) - read_count)
        
        message_data = {
            'id': msg.id,
            'sender_employee_id': msg.sender_employee_id,
            'sender_nickname': msg.sender_nickname,
            'message': msg.message,
            'created_at': format_korean_time(msg.created_at),
            'unread_count': unread_count
        }
        
        # 투표 알림 메시지인지 확인 (시스템 메시지 + 특정 패턴)
        if (msg.sender_employee_id == 'SYSTEM' and 
            '📊 새로운 투표가 시작되었습니다!' in msg.message and
            '이 메시지를 터치하여 투표에 참여하세요' in msg.message):
            message_data['message_type'] = 'voting_notification'
            
            # 해당 채팅방의 최신 투표 세션 ID 찾기
            latest_voting = VotingSession.query.filter_by(
                chat_room_id=chat_id,
                status='active'
            ).order_by(VotingSession.created_at.desc()).first()
            
            if latest_voting:
                message_data['voting_session_id'] = latest_voting.id
        
        # 투표 삭제 메시지인지 확인
        elif (msg.sender_employee_id == 'SYSTEM' and 
              '🚫' in msg.message and 
              '투표가 삭제되었습니다' in msg.message):
            message_data['message_type'] = 'voting_cancelled'
        
        # 투표 완료 메시지인지 확인
        elif (msg.sender_employee_id == 'SYSTEM' and 
              ('⏰' in msg.message and '투표가 마감되었습니다' in msg.message) or
              ('🎉' in msg.message and '투표가 완료되었습니다' in msg.message)):
            message_data['message_type'] = 'voting_completed'
            # 투표 완료 메시지에서 투표 세션 ID 찾기
            completed_voting = VotingSession.query.filter_by(
                chat_room_id=chat_id,
                status='completed'
            ).order_by(desc(VotingSession.confirmed_at)).first()
            if completed_voting:
                message_data['voting_session_id'] = completed_voting.id
        
        # 투표 정보 수정 메시지인지 확인
        elif (msg.sender_employee_id == 'SYSTEM' and 
              '📝' in msg.message and 
              '투표 정보가 수정되었습니다' in msg.message):
            message_data['message_type'] = 'voting_updated'
        
        result.append(message_data)
    return jsonify(result)

@app.route('/chat/messages', methods=['POST'])
def send_chat_message():
    data = request.get_json()
    chat_type = data.get('chat_type')
    chat_id = data.get('chat_id')
    sender_employee_id = data.get('sender_employee_id')
    message = data.get('message')
    
    if not all([chat_type, chat_id, sender_employee_id, message]):
        return jsonify({'message': '모든 필드가 필요합니다.'}), 400
    
    # 사용자 정보 조회
    user = User.query.filter_by(employee_id=sender_employee_id).first()
    if not user:
        return jsonify({'message': '사용자를 찾을 수 없습니다.'}), 404
    
    # 투표로 생성된 채팅방인지 확인 (ChatRoom이 group 타입이고 해당 chat_id를 가진 경우)
    chat_room = ChatRoom.query.get(chat_id)
    if chat_room and chat_room.type == 'group':
        # 투표로 생성된 채팅방의 경우 chat_type을 'custom'으로 강제 설정
        actual_chat_type = 'custom'
        print(f"=== DEBUG: 투표로 생성된 채팅방 감지 - chat_id: {chat_id}, 강제 chat_type: custom ===")
    else:
        actual_chat_type = chat_type
    
    print(f"=== DEBUG: 메시지 저장 - 원본 chat_type: {chat_type}, 실제 chat_type: {actual_chat_type}, chat_id: {chat_id}, sender: {sender_employee_id}, message: {message[:50]}... ===")
    
    # 메시지 저장
    new_message = ChatMessage()
    new_message.chat_type = actual_chat_type
    new_message.chat_id = chat_id
    new_message.sender_employee_id = sender_employee_id
    new_message.sender_nickname = user.nickname
    new_message.message = message
    
    try:
        db.session.add(new_message)
        db.session.commit()
        
        return jsonify({
            'id': new_message.id,
            'sender_employee_id': sender_employee_id,
            'sender_nickname': user.nickname,
            'message': message,
            'created_at': format_korean_time(new_message.created_at),
            'chat_type': actual_chat_type,
            'chat_id': chat_id
        }), 201
    except Exception as e:
        db.session.rollback()
        return jsonify({'message': '메시지 저장에 실패했습니다.'}), 500

@app.route('/chat/messages/read', methods=['POST'])
def mark_message_read():
    data = request.get_json()
    message_id = data.get('message_id')
    user_id = data.get('user_id')
    if not message_id or not user_id:
        return jsonify({'message': 'message_id와 user_id가 필요합니다.'}), 400

    # 이미 읽음 처리된 경우 중복 저장 방지
    existing = ChatMessageRead.query.filter_by(message_id=message_id, user_id=user_id).first()
    if existing:
        return jsonify({'message': '이미 읽음 처리됨.'}), 200

    read = ChatMessageRead(message_id=message_id, user_id=user_id)
    db.session.add(read)
    db.session.commit()
    return jsonify({'message': '읽음 처리 완료.'}), 201

@app.route('/chat/messages/search', methods=['GET'])
def search_messages():
    employee_id = request.args.get('employee_id')
    chat_type = request.args.get('chat_type')
    chat_id = request.args.get('chat_id')
    query = request.args.get('query')
    
    if not all([employee_id, chat_type, chat_id, query]):
        return jsonify({'message': '모든 파라미터가 필요합니다.'}), 400
    
    try:
        if chat_id is None:
            return jsonify({'message': 'chat_id가 필요합니다.'}), 400
        chat_id = int(chat_id)
    except ValueError:
        return jsonify({'message': 'chat_id는 숫자여야 합니다.'}), 400
    
    # 해당 채팅방의 메시지들 중에서 검색어가 포함된 메시지 찾기
    messages = ChatMessage.query.filter(
        ChatMessage.chat_type == chat_type,
        ChatMessage.chat_id == chat_id,
        ChatMessage.message.contains(query)
    ).order_by(ChatMessage.created_at.desc()).all()
    
    result = []
    for msg in messages:
        result.append({
            'id': msg.id,
            'sender_employee_id': msg.sender_employee_id,
            'sender_nickname': msg.sender_nickname,
            'message': msg.message,
            'created_at': format_korean_time(msg.created_at)
        })
    
    return jsonify(result)

@app.route('/chat/room/title', methods=['PUT'])
def update_chat_room_title():
    data = request.get_json()
    chat_type = data.get('chat_type')
    chat_id = data.get('chat_id')
    new_title = data.get('title')
    user_id = data.get('user_id')
    
    if not all([chat_type, chat_id, new_title, user_id]):
        return jsonify({'message': '모든 필드가 필요합니다.'}), 400
    
    try:
        if chat_type == 'party':
            party = Party.query.get(chat_id)
            if not party:
                return jsonify({'message': '파티를 찾을 수 없습니다.'}), 404
            if party.host_employee_id != user_id:
                return jsonify({'message': '파티 호스트만 제목을 변경할 수 있습니다.'}), 403
            party.title = new_title
        elif chat_type == 'dangolpot':
            pot = DangolPot.query.get(chat_id)
            if not pot:
                return jsonify({'message': '단골파티를 찾을 수 없습니다.'}), 404
            if pot.host_id != user_id:
                return jsonify({'message': '단골파티 호스트만 제목을 변경할 수 있습니다.'}), 403
            pot.name = new_title
        else:
            return jsonify({'message': '지원하지 않는 채팅 타입입니다.'}), 400
        
        db.session.commit()
        return jsonify({'message': '채팅방 제목이 변경되었습니다.', 'title': new_title}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({'message': '제목 변경에 실패했습니다.'}), 500

@app.route('/chat/room/members/<chat_type>/<int:chat_id>', methods=['GET'])
def get_chat_room_members(chat_type, chat_id):
    try:
        if chat_type == 'party':
            party = Party.query.get(chat_id)
            if not party:
                return jsonify({'message': '파티를 찾을 수 없습니다.'}), 404
            
            # 호스트 정보
            host = User.query.filter_by(employee_id=party.host_employee_id).first()
            members = [{
                'employee_id': party.host_employee_id,
                'nickname': host.nickname if host else '알 수 없음',
                'is_host': True
            }]
            
            # 멤버 정보 (호스트 제외)
            if party.members_employee_ids:
                member_ids = [mid.strip() for mid in party.members_employee_ids.split(',') if mid.strip()]
                for member_id in member_ids:
                    # 호스트는 이미 위에서 추가했으므로 중복 제외
                    if member_id != party.host_employee_id:
                        user = User.query.filter_by(employee_id=member_id).first()
                        if user:
                            members.append({
                                'employee_id': member_id,
                                'nickname': user.nickname,
                                'is_host': False
                            })
            
        elif chat_type == 'dangolpot':
            pot = DangolPot.query.get(chat_id)
            if not pot:
                return jsonify({'message': '단골파티를 찾을 수 없습니다.'}), 404
            
            # 호스트 정보
            host = User.query.filter_by(employee_id=pot.host_id).first()
            members = [{
                'employee_id': pot.host_id,
                'nickname': host.nickname if host else '알 수 없음',
                'is_host': True
            }]
            
            # 멤버 정보 (호스트 제외)
            if pot.members:
                member_ids = [mid.strip() for mid in pot.members.split(',') if mid.strip()]
                for member_id in member_ids:
                    # 호스트는 이미 위에서 추가했으므로 중복 제외
                    if member_id != pot.host_id:
                        user = User.query.filter_by(employee_id=member_id).first()
                        if user:
                            members.append({
                                'employee_id': member_id,
                                'nickname': user.nickname,
                                'is_host': False
                            })
            
        elif chat_type == 'custom':
            # 1:1 채팅의 경우
            room = ChatRoom.query.filter_by(type='friend', id=chat_id).first()
            if not room:
                return jsonify({'message': '채팅방을 찾을 수 없습니다.'}), 404
            
            participants = ChatParticipant.query.filter_by(room_id=room.id).all()
            members = []
            for participant in participants:
                user = User.query.filter_by(employee_id=participant.user_id).first()
                if user:
                    members.append({
                        'employee_id': participant.user_id,
                        'nickname': user.nickname,
                        'is_host': False
                    })
        else:
            return jsonify({'message': '지원하지 않는 채팅 타입입니다.'}), 400
        
        return jsonify(members)
    except Exception as e:
        return jsonify({'message': '멤버 목록 조회에 실패했습니다.'}), 500

@app.route('/chat/leave', methods=['POST'])
def leave_chat_room():
    """채팅방 나가기"""
    try:
        data = request.get_json()
        chat_type = data.get('chat_type')
        chat_id = data.get('chat_id')
        employee_id = data.get('employee_id')
        
        if not all([chat_type, chat_id, employee_id]):
            return jsonify({'error': '모든 필드가 필요합니다.'}), 400
        
        if chat_type == 'party':
            party = Party.query.get(chat_id)
            if not party:
                return jsonify({'error': '파티를 찾을 수 없습니다.'}), 404
            
            # 호스트는 나갈 수 없음
            if party.host_employee_id == employee_id:
                return jsonify({'error': '파티 호스트는 파티를 나갈 수 없습니다. 파티를 삭제해주세요.'}), 403
            
            # 멤버 목록에서 해당 사용자 제거
            if party.members_employee_ids:
                member_ids = [mid.strip() for mid in party.members_employee_ids.split(',') if mid.strip()]
                if employee_id in member_ids:
                    member_ids.remove(employee_id)
                    party.members_employee_ids = ','.join(member_ids)
                    db.session.commit()
                    return jsonify({'message': '파티에서 나갔습니다.'}), 200
                else:
                    return jsonify({'error': '해당 파티의 멤버가 아닙니다.'}), 404
            else:
                return jsonify({'error': '해당 파티의 멤버가 아닙니다.'}), 404
                
        elif chat_type == 'dangolpot':
            pot = DangolPot.query.get(chat_id)
            if not pot:
                return jsonify({'error': '단골파티를 찾을 수 없습니다.'}), 404
            
            # 호스트는 나갈 수 없음
            if pot.host_id == employee_id:
                return jsonify({'error': '단골파티 호스트는 단골파티를 나갈 수 없습니다. 단골파티를 삭제해주세요.'}), 403
            
            # 멤버 목록에서 해당 사용자 제거
            if pot.members:
                member_ids = [mid.strip() for mid in pot.members.split(',') if mid.strip()]
                if employee_id in member_ids:
                    member_ids.remove(employee_id)
                    pot.members = ','.join(member_ids)
                    db.session.commit()
                    return jsonify({'message': '단골파티에서 나갔습니다.'}), 200
                else:
                    return jsonify({'error': '해당 단골파티의 멤버가 아닙니다.'}), 404
            else:
                return jsonify({'error': '해당 단골파티의 멤버가 아닙니다.'}), 404
                
        elif chat_type == 'custom':
            # 1:1 채팅의 경우 ChatParticipant에서 제거
            room = ChatRoom.query.filter_by(type='friend', id=chat_id).first()
            if not room:
                return jsonify({'error': '채팅방을 찾을 수 없습니다.'}), 404
            
            participant = ChatParticipant.query.filter_by(room_id=room.id, user_id=employee_id).first()
            if not participant:
                return jsonify({'error': '해당 채팅방의 참여자가 아닙니다.'}), 404
            
            db.session.delete(participant)
            
            # 남은 참여자가 없으면 채팅방도 삭제
            remaining_participants = ChatParticipant.query.filter_by(room_id=room.id).count()
            if remaining_participants <= 1:  # 현재 사용자 제외하고 0명이면 채팅방 삭제
                db.session.delete(room)
            
            db.session.commit()
            return jsonify({'message': '채팅방에서 나갔습니다.'}), 200
            
        else:
            return jsonify({'error': '지원하지 않는 채팅 타입입니다.'}), 400
            
    except Exception as e:
        db.session.rollback()
        print(f"채팅방 나가기 오류: {e}")
        return jsonify({'error': '채팅방 나가기에 실패했습니다.'}), 500

# --- WebSocket 이벤트 ---
@socketio.on('connect')
def handle_connect():
    print('Client connected')

@socketio.on('disconnect')
def handle_disconnect():
    print('Client disconnected')

@socketio.on('join_chat')
def handle_join_chat(data):
    chat_type = data['chat_type']
    chat_id = data['chat_id']
    room = f"{chat_type}_{chat_id}"
    join_room(room)
    print(f'Client joined room: {room}')

@socketio.on('leave_chat')
def handle_leave_chat(data):
    chat_type = data['chat_type']
    chat_id = data['chat_id']
    room = f"{chat_type}_{chat_id}"
    leave_room(room)
    print(f'Client left room: {room}')

@socketio.on('send_message')
def handle_send_message(data):
    chat_type = data.get('chat_type')
    chat_id = data.get('chat_id')
    sender_employee_id = data.get('sender_employee_id')
    message = data.get('message')
    
    print(f'Send message event received: {data}')
    
    if not all([chat_type, chat_id, sender_employee_id, message]):
        print('Missing required fields in send_message event')
        return
    
    try:
        # 사용자 정보 조회
        user = User.query.filter_by(employee_id=sender_employee_id).first()
        if not user:
            print(f'User not found: {sender_employee_id}')
            return
        
        # 메시지 저장
        new_message = ChatMessage()
        new_message.chat_type = chat_type
        new_message.chat_id = chat_id
        new_message.sender_employee_id = sender_employee_id
        new_message.sender_nickname = user.nickname
        new_message.message = message
        db.session.add(new_message)
        db.session.commit()
        print(f'Message saved with ID: {new_message.id}')
        
        # 채팅방의 모든 사용자에게 메시지 전송
        room = f"{chat_type}_{chat_id}"
        message_data = {
            'id': new_message.id,
            'sender_employee_id': sender_employee_id,
            'sender_nickname': user.nickname,
            'message': message,
            'created_at': format_korean_time(new_message.created_at),
            'unread_count': 0
        }
        print(f'Emitting new_message to room {room}: {message_data}')
        emit('new_message', message_data, to=room)
        
    except Exception as e:
        print(f'Error in handle_send_message: {e}')
        import traceback
        traceback.print_exc()

@socketio.on('read_message')
def handle_read_message(data):
    message_id = data.get('message_id')
    user_id = data.get('user_id')
    chat_type = data.get('chat_type')
    chat_id = data.get('chat_id')
    
    print(f'Read message event received: {data}')
    
    if not message_id or not user_id or not chat_type or not chat_id:
        print('Missing required fields in read_message event')
        return
    
    try:
        # 이미 읽음 처리된 경우 중복 저장 방지
        existing = ChatMessageRead.query.filter_by(message_id=message_id, user_id=user_id).first()
        if not existing:
            read = ChatMessageRead(message_id=message_id, user_id=user_id)
            db.session.add(read)
            db.session.commit()
            print(f'Message {message_id} marked as read by {user_id}')
        
        # 채팅방 참여자 목록 구하기
        if chat_type == 'party':
            party = Party.query.get(chat_id)
            member_ids = [mid.strip() for mid in party.members_employee_ids.split(',') if mid.strip()] if party and party.members_employee_ids else []
        elif chat_type == 'dangolpot':
            pot = DangolPot.query.get(chat_id)
            member_ids = [mid.strip() for mid in pot.members.split(',') if mid.strip()] if pot and pot.members else []
        elif chat_type == 'custom':
            room = ChatRoom.query.filter_by(type='friend', id=chat_id).first()
            if room:
                participants = ChatParticipant.query.filter_by(room_id=room.id).all()
                member_ids = [p.user_id for p in participants]
            else:
                member_ids = []
        else:
            member_ids = []
        
        read_count = ChatMessageRead.query.filter_by(message_id=message_id).count()
        unread_count = max(0, len(member_ids) - read_count)
        
        room_name = f"{chat_type}_{chat_id}"
        print(f'Emitting message_read to room {room_name}: message_id={message_id}, unread_count={unread_count}')
        
        socketio.emit('message_read', {
            'message_id': message_id,
            'user_id': user_id,
            'unread_count': unread_count
        }, to=room_name)
        
    except Exception as e:
        print(f'Error in handle_read_message: {e}')
        import traceback
        traceback.print_exc()

# --- 친구 API ---
@app.route('/users/search', methods=['GET'])
def search_users():
    nickname = request.args.get('nickname')
    employee_id = request.args.get('employee_id')  # 검색하는 사용자 ID
    
    if not nickname:
        return jsonify({'message': '닉네임 파라미터가 필요합니다.'}), 400
    
    users = User.query.filter(User.nickname.contains(nickname)).all()  # type: ignore
    
    # 각 사용자에 대해 이미 친구인지 확인
    result = []
    for user in users:
        # 자기 자신은 제외
        if employee_id and user.employee_id == employee_id:
            continue
            
        is_friend = False
        if employee_id:
            # 일방적 친구 관계 확인
            friendship = Friendship.query.filter_by(
                requester_id=employee_id,
                receiver_id=user.employee_id,
                status='accepted'
            ).first()
            is_friend = friendship is not None
        
        result.append({
            'employee_id': user.employee_id,
            'nickname': user.nickname,
            'lunch_preference': user.lunch_preference,
            'main_dish_genre': user.main_dish_genre,
            'is_friend': is_friend,
            'allergies': user.allergies,
            'preferred_time': user.preferred_time
        })
    
    return jsonify(result)

@app.route('/friends/add', methods=['POST'])
def add_friend():
    data = request.get_json()
    user_id = data.get('user_id')
    friend_id = data.get('friend_id')
    
    if not user_id or not friend_id:
        return jsonify({'message': '사용자 ID와 친구 ID가 필요합니다.'}), 400
    
    if user_id == friend_id:
        return jsonify({'message': '자기 자신을 친구로 추가할 수 없습니다.'}), 400
    
    # 이미 친구인지 확인 (일방적이므로 user_id가 requester인 경우만 확인)
    existing_friendship = Friendship.query.filter_by(
        requester_id=user_id,
        receiver_id=friend_id,
        status='accepted'
    ).first()
    
    if existing_friendship:
        return jsonify({'message': '이미 친구로 추가되어 있습니다.'}), 400
    
    # 일방적 친구 추가
    new_friendship = Friendship(requester_id=user_id, receiver_id=friend_id)
    new_friendship.status = 'accepted'  # 바로 수락된 상태로 설정
    db.session.add(new_friendship)
    db.session.commit()
    
    return jsonify({'message': '친구가 추가되었습니다.'}), 201

@app.route('/friends/remove', methods=['POST'])
def remove_friend():
    data = request.get_json()
    user_id = data.get('user_id')
    friend_id = data.get('friend_id')
    
    if not user_id or not friend_id:
        return jsonify({'message': '사용자 ID와 친구 ID가 필요합니다.'}), 400
    
    # 친구 관계 찾기 (일방적이므로 user_id가 requester인 경우만)
    friendship = Friendship.query.filter_by(
        requester_id=user_id,
        receiver_id=friend_id,
        status='accepted'
    ).first()
    
    if not friendship:
        return jsonify({'message': '친구 관계를 찾을 수 없습니다.'}), 404
    
    # 친구 관계 삭제
    db.session.delete(friendship)
    db.session.commit()
    
    return jsonify({'message': '친구가 삭제되었습니다.'}), 200

# 친구 요청 시스템 제거 - 일방적 친구 추가로 변경
# @app.route('/friends/accept', methods=['POST'])
# @app.route('/friends/requests', methods=['GET'])

@app.route('/friends', methods=['GET'])
def get_friends():
    employee_id = request.args.get('employee_id')
    if not employee_id:
        return jsonify({'message': '사용자 ID가 필요합니다.'}), 400
    
    # 내가 추가한 친구들만 조회 (일방적 관계)
    friendships = Friendship.query.filter_by(
        requester_id=employee_id,
        status='accepted'
    ).all()
    
    friends_data = []
    today = get_seoul_today()
    
    for friendship in friendships:
        friend = User.query.filter_by(employee_id=friendship.receiver_id).first()
        
        if friend:
            # 마지막으로 함께 점심 먹은 날 계산 (dining_history 로직 참조)
            last_party = Party.query.filter(
                and_(
                    or_(
                        and_(Party.host_employee_id == employee_id, Party.members_employee_ids.contains(friend.employee_id)),
                        and_(Party.host_employee_id == friend.employee_id, Party.members_employee_ids.contains(employee_id))
                    ),
                    Party.party_date < today.strftime('%Y-%m-%d')
                )
            ).order_by(desc(Party.party_date)).first()
            
            # 마지막 점심 날짜 계산
            if last_party:
                last_party_date = datetime.strptime(last_party.party_date, '%Y-%m-%d').date()
                days_diff = (today - last_party_date).days
                
                if days_diff == 1:
                    last_lunch = "어제"
                elif days_diff <= 7:
                    last_lunch = f"{days_diff}일 전"
                elif days_diff <= 30:
                    last_lunch = f"{days_diff//7}주 전"
                else:
                    last_lunch = "1달 이상 전"
            else:
                last_lunch = "처음"
            
            friends_data.append({
                'employee_id': friend.employee_id,
                'nickname': friend.nickname,
                'lunch_preference': friend.lunch_preference,
                'main_dish_genre': friend.main_dish_genre,
                'last_lunch': last_lunch,
                'allergies': friend.allergies,
                'preferred_time': friend.preferred_time
            })
    
    return jsonify(friends_data)

@app.route('/friends/recommendations', methods=['GET'])
def get_friend_recommendations():
    """친구 추천 API - 랜덤런치 점수, 활동패턴, 상호친구 기반 추천"""
    employee_id = request.args.get('employee_id')
    if not employee_id:
        return jsonify({'message': '사용자 ID가 필요합니다.'}), 400
    
    # 현재 사용자 정보
    current_user = User.query.filter_by(employee_id=employee_id).first()
    if not current_user:
        return jsonify({'message': '사용자를 찾을 수 없습니다.'}), 404
    
    # 이미 친구인 사용자들 제외
    existing_friends = Friendship.query.filter_by(
        requester_id=employee_id,
        status='accepted'
    ).all()
    friend_ids = [f.receiver_id for f in existing_friends]
    friend_ids.append(employee_id)  # 본인도 제외
    
    # 모든 다른 사용자들 조회
    potential_friends = User.query.filter(~User.employee_id.in_(friend_ids)).all()
    
    recommendations = []
    
    for user in potential_friends:
        score = 0.0
        
        # 1. 랜덤런치 호환성 점수 (기존 calculate_compatibility_score 활용)
        compatibility_score = calculate_compatibility_score(current_user, user)
        score += compatibility_score * 0.4  # 40% 가중치
        
        # 2. 활동 패턴 분석
        # 사용자의 파티 참여 횟수
        user_parties = Party.query.filter(
            or_(
                Party.host_employee_id == user.employee_id,
                Party.members_employee_ids.contains(user.employee_id)
            )
        ).count()
        
        # 리뷰 작성 횟수  
        user_reviews = Review.query.filter_by(user_id=user.employee_id).count()
        
        # 활동성 점수 (정규화)
        activity_score = min((user_parties * 0.1 + user_reviews * 0.05), 1.0)
        score += activity_score * 0.3  # 30% 가중치
        
        # 3. 상호 친구 분석
        # 현재 사용자의 친구들과 해당 사용자가 공통으로 아는 사람 수
        current_user_friends = set(friend_ids[:-1])  # 본인 제외
        
        # 해당 사용자와 함께 파티에 참여했던 사람들
        user_party_members = set()
        user_hosted_parties = Party.query.filter_by(host_employee_id=user.employee_id).all()
        user_joined_parties = Party.query.filter(Party.members_employee_ids.contains(user.employee_id)).all()
        
        for party in user_hosted_parties + user_joined_parties:
            if party.members_employee_ids:
                members = party.members_employee_ids.split(',')
                user_party_members.update([m.strip() for m in members if m.strip() != user.employee_id])
        
        # 공통 연결점 계산
        mutual_connections = len(current_user_friends.intersection(user_party_members))
        mutual_score = min(mutual_connections * 0.2, 1.0)
        score += mutual_score * 0.3  # 30% 가중치
        
        # 4. 최근 활동도 (보너스)
        recent_activity = Party.query.filter(
            and_(
                or_(
                    Party.host_employee_id == user.employee_id,
                    Party.members_employee_ids.contains(user.employee_id)
                ),
                Party.party_date >= (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')
            )
        ).count()
        
        recent_score = min(recent_activity * 0.1, 0.5)
        score += recent_score
        
        recommendations.append({
            'employee_id': user.employee_id,
            'nickname': user.nickname,
            'lunch_preference': user.lunch_preference,
            'main_dish_genre': user.main_dish_genre,
            'recommendation_score': round(score, 3),
            'is_friend': False,
            'allergies': user.allergies,
            'preferred_time': user.preferred_time
        })
    
    # 점수순으로 정렬하고 상위 10명만 반환
    recommendations.sort(key=lambda x: x['recommendation_score'], reverse=True)
    return jsonify(recommendations[:10])

# --- 새로운 채팅 API ---
@app.route('/chats/friends', methods=['POST'])
def create_friend_chat():
    data = request.get_json()
    user_ids = data.get('user_ids', [])
    
    if len(user_ids) < 2:
        return jsonify({'message': '최소 2명의 사용자가 필요합니다.'}), 400
    
    # 기존 친구 채팅방이 있는지 확인
    existing_room = None
    for room in ChatRoom.query.filter_by(type='friend').all():
        participants = ChatParticipant.query.filter_by(room_id=room.id).all()
        participant_ids = [p.user_id for p in participants]
        
        if set(user_ids) == set(participant_ids):
            existing_room = room
            break
    
    if existing_room:
        return jsonify({
            'message': '이미 존재하는 채팅방입니다.',
            'room_id': existing_room.id
        }), 200
    
    # 새 채팅방 생성
    chat_room = ChatRoom(
        name=None,  # 1:1 채팅은 이름 없음
        type='friend'
    )
    db.session.add(chat_room)
    db.session.flush()
    
    # 참여자들 추가
    for user_id in user_ids:
        participant = ChatParticipant(room_id=chat_room.id, user_id=user_id)
        db.session.add(participant)
    
    db.session.commit()
    
    return jsonify({
        'message': '친구 채팅방이 생성되었습니다.',
        'room_id': chat_room.id
    }), 201

@app.route('/chat/create', methods=['POST'])
def create_chat_room():
    """일반 채팅방 생성 API"""
    data = request.get_json()
    title = data.get('title')
    creator_employee_id = data.get('creator_employee_id')
    participant_employee_ids = data.get('participant_employee_ids', [])
    
    if not title or not creator_employee_id:
        return jsonify({'message': '채팅방 제목과 생성자 ID가 필요합니다.'}), 400
    
    if not participant_employee_ids:
        return jsonify({'message': '최소 한 명의 참여자가 필요합니다.'}), 400
    
    # 생성자도 참여자 목록에 추가
    if creator_employee_id not in participant_employee_ids:
        participant_employee_ids.append(creator_employee_id)
    
    try:
        # 새 채팅방 생성
        chat_room = ChatRoom(
            name=title,
            type='group'  # 일반 그룹 채팅방
        )
        db.session.add(chat_room)
        db.session.flush()
        
        # 참여자들 추가
        for user_id in participant_employee_ids:
            participant = ChatParticipant(room_id=chat_room.id, user_id=user_id)
            db.session.add(participant)
        
        db.session.commit()
        
        return jsonify({
            'message': '채팅방이 생성되었습니다.',
            'chat_id': chat_room.id,
            'title': chat_room.name
        }), 201
        
    except Exception as e:
        db.session.rollback()
        print(f"Error creating chat room: {e}")
        return jsonify({'message': '채팅방 생성에 실패했습니다.'}), 500

@app.route('/chats/filtered', methods=['GET'])
def get_filtered_chats():
    employee_id = request.args.get('employee_id')
    chat_type = request.args.get('type')  # 'friend', 'group', 'dangolpot' 또는 None
    
    if not employee_id:
        return jsonify({'message': '사용자 ID가 필요합니다.'}), 400
    
    # 사용자가 참여한 채팅방들 조회
    user_participants = ChatParticipant.query.filter_by(user_id=employee_id).all()
    room_ids = [p.room_id for p in user_participants]
    
    # 채팅방 정보 조회
    if chat_type:
        rooms = ChatRoom.query.filter(
            ChatRoom.id.in_(room_ids),  # type: ignore
            ChatRoom.type == chat_type  # type: ignore
        ).all()
    else:
        rooms = ChatRoom.query.filter(ChatRoom.id.in_(room_ids)).all()  # type: ignore
    
    chats_data = []
    for room in rooms:
        # 참여자 정보 가져오기
        participants = ChatParticipant.query.filter_by(room_id=room.id).all()
        participant_users = []
        
        for participant in participants:
            user = User.query.filter_by(employee_id=participant.user_id).first()
            if user:
                participant_users.append({
                    'employee_id': user.employee_id,
                    'nickname': user.nickname
                })
        
        # 마지막 메시지 가져오기
        last_message = ChatMessage.query.filter_by(
            chat_type=room.type,
            chat_id=room.id
        ).order_by(desc(ChatMessage.created_at)).first()
        
        chat_data = {
            'id': room.id,
            'name': room.name or f"{len(participant_users)}명의 채팅방",
            'type': room.type,
            'participants': participant_users,
            'last_message': {
                'sender_nickname': last_message.sender_nickname,
                'message': last_message.message,
                'created_at': last_message.created_at.strftime('%Y-%m-%d %H:%M')
            } if last_message else None
        }
        
        chats_data.append(chat_data)
    
    return jsonify(chats_data)

def find_available_dates_for_participants(participant_ids, max_days=30):
    """참가자들의 공통 가능 날짜를 찾는 공통 함수"""
    today = get_seoul_today()
    available_dates = []
    alternative_dates = []
    
    for i in range(max_days):
        check_date = today + timedelta(days=i)
        date_str = check_date.strftime('%Y-%m-%d')
        
        # 각 참여자의 해당 날짜 약속 확인
        available_participants = []
        unavailable_participants = []
        
        for participant_id in participant_ids:
            # 파티 약속 확인
            has_party = Party.query.filter(
                Party.members_employee_ids.contains(participant_id),  # type: ignore
                Party.party_date == date_str  # type: ignore
            ).first() is not None
            
            # 개인 일정 확인
            has_schedule = PersonalSchedule.query.filter_by(
                employee_id=participant_id,
                schedule_date=date_str
            ).first() is not None
            
            if not has_party and not has_schedule:
                available_participants.append(participant_id)
            else:
                unavailable_participants.append(participant_id)
        
        date_info = {
            'date': date_str,
            'available_participants': available_participants,
            'unavailable_participants': unavailable_participants,
            'available_count': len(available_participants),
            'total_count': len(participant_ids)
        }
        
        # 모든 참여자가 가능한 경우
        if len(available_participants) == len(participant_ids):
            available_dates.append(date_info)
        # 1명만 빠지고 나머지가 가능한 경우 (3명 이상일 때)
        elif len(participant_ids) >= 3 and len(available_participants) == len(participant_ids) - 1:
            alternative_dates.append(date_info)
    
    return available_dates, alternative_dates

# --- 지능형 약속 잡기 API ---
@app.route('/intelligent/suggest-dates', methods=['POST'])
def intelligent_suggest_dates():
    """선택된 참가자들로 공통 가능 날짜 찾기 (2050년까지 확장)"""
    try:
        data = request.get_json()
        participant_ids = data.get('participant_ids', [])
        
        if len(participant_ids) < 2:
            return jsonify({'message': '최소 2명의 참여자가 필요합니다.'}), 400
        
        # 2050년까지 모든 참여자 가능 날짜 찾기 (성능을 위해 최대 3년)
        today = get_seoul_today()
        end_date = datetime(2050, 12, 31).date()
        max_days = (end_date - today).days + 1
        
        # 너무 큰 범위는 제한 (최대 3년)
        max_days = min(max_days, 365 * 3)
        
        available_dates_all, alternative_dates_all = find_available_dates_for_participants(
            participant_ids, max_days=max_days
        )
        
        return jsonify({
            'message': f'{len(available_dates_all)}개의 공통 가능 날짜를 찾았습니다.',
            'type': 'common',
            'period': 'extended',
            'dates': available_dates_all
        })
            
    except Exception as e:
        return jsonify({'message': f'날짜 제안 중 오류가 발생했습니다: {str(e)}'}), 500

@app.route('/chats/<int:room_id>/suggest-dates', methods=['POST'])
def suggest_dates(room_id):
    """채팅방 참여자들의 공통 가능 날짜 찾기 (개선된 버전)"""
    try:
        # 채팅방 정보 조회
        chat_room = ChatRoom.query.get(room_id)
        if not chat_room:
            return jsonify({'message': '채팅방을 찾을 수 없습니다.'}), 404
        
        # 채팅방 참여자들 조회
        participants = ChatParticipant.query.filter_by(room_id=room_id).all()
        participant_ids = [p.user_id for p in participants]
        
        if len(participant_ids) < 2:
            return jsonify({'message': '최소 2명의 참여자가 필요합니다.'}), 400
        
        # 1단계: 한 달 이내 모든 참여자 가능 날짜 찾기
        available_dates_month, alternative_dates_month = find_available_dates_for_participants(
            participant_ids, max_days=30
        )
        
        # 한 달 이내에 모든 참여자가 가능한 날짜가 있으면 반환
        if available_dates_month:
            return jsonify({
                'message': f'한 달 이내 {len(available_dates_month)}개의 공통 가능 날짜를 찾았습니다.',
                'type': 'common',
                'period': 'one_month',
                'dates': available_dates_month
            })
        
        # 2단계: 한 달 이내에 없으면 두 달 이내 검색
        available_dates_two_months, alternative_dates_two_months = find_available_dates_for_participants(
            participant_ids, max_days=60
        )
        
        # 결과 조합
        all_alternatives = alternative_dates_month + alternative_dates_two_months
        all_available = available_dates_two_months
        
        if all_available or all_alternatives:
            result = {
                'message': '한 달 이내 공통 날짜가 없어 대안을 제시합니다.',
                'type': 'mixed',
                'period': 'two_months'
            }
            
            if all_available:
                result['available_dates'] = {
                    'title': '두 달 이내 모든 참여자 가능 날짜',
                    'dates': all_available
                }
            
            if all_alternatives:
                result['alternative_dates'] = {
                    'title': '1명 빼고 가능한 날짜',
                    'dates': all_alternatives[:10]  # 최대 10개
                }
            
            return jsonify(result)
        else:
            return jsonify({
                'message': '두 달 이내에도 적절한 날짜를 찾을 수 없습니다.',
                'type': 'no_dates',
                'period': 'two_months'
            })
            
    except Exception as e:
        return jsonify({'message': f'날짜 제안 중 오류가 발생했습니다: {str(e)}'}), 500

# --- AI 제목 제안 API ---
@app.route('/ai/suggest-party-titles', methods=['POST'])
def suggest_party_titles():
    try:
        data = request.get_json()
        restaurant = data.get('restaurant', '')
        date = data.get('date', '')
        time = data.get('time', '')
        location = data.get('location', '')
        
        # 간단한 제목 제안 로직
        suggestions = []
        
        if restaurant:
            suggestions.append(f"🍽️ {restaurant} 점심 모임")
            suggestions.append(f"🥘 {restaurant}에서 함께 밥먹기")
            suggestions.append(f"👥 {restaurant} 런치타임")
        
        if date:
            date_obj = datetime.strptime(date, '%Y-%m-%d')
            day_name = ['월', '화', '수', '목', '금', '토', '일'][date_obj.weekday()]
            suggestions.append(f"📅 {day_name}요일 점심 모임")
            suggestions.append(f"🎉 {date} 점심 파티")
        
        if location:
            suggestions.append(f"📍 {location} 점심 모임")
        
        # 기본 제안들
        suggestions.extend([
            "🍕 맛있는 점심 시간",
            "🥗 건강한 점심 모임",
            "🍜 따뜻한 점심 타임",
            "🍖 고기 맛집 탐방",
            "🍱 도시락 친구들"
        ])
        
        # 중복 제거 및 최대 5개 반환
        unique_suggestions = list(dict.fromkeys(suggestions))[:5]
        
        return jsonify({
            'suggestions': unique_suggestions,
            'message': '제목 제안을 생성했습니다.'
        })
        
    except Exception as e:
        return jsonify({
            'message': f'제목 제안 생성 중 오류가 발생했습니다: {str(e)}'
        }), 500

# --- 위치 기반 서비스 ---
@app.route('/restaurants/nearby', methods=['GET'])
def get_nearby_restaurants():
    """현재 위치 기반 근처 식당 추천"""
    latitude = request.args.get('latitude', type=float)
    longitude = request.args.get('longitude', type=float)
    radius = request.args.get('radius', 1000, type=int)  # 기본 1km
    
    if not latitude or not longitude:
        return jsonify({'message': '위치 정보가 필요합니다.'}), 400
    
    # 간단한 거리 계산 (실제로는 Haversine 공식 사용)
    restaurants = Restaurant.query.filter(
        Restaurant.latitude.isnot(None),  # type: ignore
        Restaurant.longitude.isnot(None)  # type: ignore
    ).all()
    
    nearby_restaurants = []
    for restaurant in restaurants:
        # 간단한 유클리드 거리 계산 (실제로는 Haversine 공식 사용)
        distance = ((restaurant.latitude - latitude) ** 2 + 
                   (restaurant.longitude - longitude) ** 2) ** 0.5 * 111000  # 대략적인 km 변환
        
        if distance <= radius:
            nearby_restaurants.append({
                'id': restaurant.id,
                'name': restaurant.name,
                'category': restaurant.category,
                'address': restaurant.address,
                'distance': round(distance, 1),
                'avg_rating': restaurant.avg_rating,
                'review_count': restaurant.review_count
            })
    
    # 거리순으로 정렬
    nearby_restaurants.sort(key=lambda x: x['distance'])
    
    return jsonify({
        'restaurants': nearby_restaurants[:10],  # 최대 10개
        'user_location': {'latitude': latitude, 'longitude': longitude}
    })

@app.route('/users/nearby', methods=['GET'])
def get_nearby_users():
    """근처 사용자 찾기 (같은 건물/지역)"""
    employee_id = request.args.get('employee_id')
    building = request.args.get('building', 'KOICA 본사')  # 기본값
    
    if not employee_id:
        return jsonify({'message': '사용자 ID가 필요합니다.'}), 400
    
    # 같은 건물의 다른 사용자들 찾기
    nearby_users = User.query.filter(
        User.employee_id != employee_id  # type: ignore
    ).limit(20).all()
    
    # 실제로는 위치 기반 필터링이 필요
    users_data = []
    for user in nearby_users:
        users_data.append({
            'employee_id': user.employee_id,
            'nickname': user.nickname,
            'lunch_preference': user.lunch_preference,
            'main_dish_genre': user.main_dish_genre,
            'building': building
        })
    
    return jsonify({
        'nearby_users': users_data,
        'building': building
    })

# --- 식당 추천 API ---
@app.route('/restaurants/recommend', methods=['GET'])
def recommend_restaurants():
    employee_id = request.args.get('employee_id')
    if not employee_id:
        return jsonify({'message': '사용자 ID가 필요합니다.'}), 400
    
    user = User.query.filter_by(employee_id=employee_id).first()
    if not user:
        return jsonify({'message': '사용자를 찾을 수 없습니다.'}), 404
    
    # 사용자 선호도 기반 추천
    user_preferences = []
    if user.food_preferences:
        user_preferences = user.food_preferences.split(',')
    
            # 기본 추천 (사용자 선호도가 없으면 인기 식당)
        if user_preferences:
            recommended_restaurants = Restaurant.query.filter(
                Restaurant.category.in_(user_preferences)  # type: ignore
            ).limit(10).all()
        else:
            # 평점 높은 식당 추천
            recommended_restaurants = Restaurant.query.order_by(
                Restaurant.avg_rating.desc()  # type: ignore
            ).limit(10).all()
    
    # 친구들이 좋아하는 식당 추천
    friends = get_user_friends(employee_id)
    friend_favorites = []
    if friends:
        for friend in friends:
            friend_user = User.query.filter_by(employee_id=friend['employee_id']).first()
            if friend_user and friend_user.main_dish_genre:
                friend_favorites.append(friend_user.main_dish_genre)
    
    friend_recommendations = []
    if friend_favorites:
        friend_recommendations = Restaurant.query.filter(
            Restaurant.category.in_(friend_favorites)  # type: ignore
        ).limit(5).all()
    
    return jsonify({
        'personal_recommendations': [{
            'id': restaurant.id,
            'name': restaurant.name,
            'category': restaurant.category,
            'address': restaurant.address,
            'avg_rating': restaurant.avg_rating,
            'review_count': restaurant.review_count
        } for restaurant in recommended_restaurants],
        'friend_recommendations': [{
            'id': restaurant.id,
            'name': restaurant.name,
            'category': restaurant.category,
            'address': restaurant.address,
            'avg_rating': restaurant.avg_rating,
            'review_count': restaurant.review_count
        } for restaurant in friend_recommendations]
    })

def get_user_friends(employee_id):
    """사용자의 친구 목록을 반환하는 헬퍼 함수 (일방적 관계)"""
    friendships = Friendship.query.filter_by(
        requester_id=employee_id,
        status='accepted'
    ).all()
    
    friends = []
    for friendship in friendships:
        friend = User.query.filter_by(employee_id=friendship.receiver_id).first()
        if friend:
            friends.append({
                'employee_id': friend.employee_id,
                'nickname': friend.nickname
            })
    
    return friends

# --- 그룹 최적화 기능 ---
@app.route('/groups/aa-calculator', methods=['POST'])
def calculate_aa():
    """그룹 AA 계산기"""
    data = request.get_json()
    expenses = data.get('expenses', [])  # [{'user_id': 'id', 'amount': 1000}, ...]
    
    if not expenses:
        return jsonify({'message': '지출 정보가 필요합니다.'}), 400
    
    total_amount = sum(expense['amount'] for expense in expenses)
    average_amount = total_amount / len(expenses)
    
    # 각 사용자별 정산 금액 계산
    settlements = []
    for expense in expenses:
        user_id = expense['user_id']
        amount = expense['amount']
        difference = amount - average_amount
        
        settlements.append({
            'user_id': user_id,
            'paid_amount': amount,
            'should_pay': average_amount,
            'difference': difference,
            'status': 'receive' if difference > 0 else 'pay' if difference < 0 else 'settled'
        })
    
    return jsonify({
        'total_amount': total_amount,
        'average_amount': average_amount,
        'participant_count': len(expenses),
        'settlements': settlements
    })

@app.route('/groups/vote', methods=['POST'])
def create_vote():
    """그룹 투표 생성"""
    data = request.get_json()
    group_id = data.get('group_id')
    title = data.get('title')
    options = data.get('options', [])
    end_time = data.get('end_time')
    
    if not all([group_id, title, options]):
        return jsonify({'message': '필수 정보가 누락되었습니다.'}), 400
    
    # 실제로는 Vote 모델을 만들어야 함
    vote_data = {
        'id': len(votes) + 1,
        'group_id': group_id,
        'title': title,
        'options': options,
        'votes': {},
        'end_time': end_time,
        'created_at': datetime.utcnow().isoformat()
    }
    
    votes.append(vote_data)
    
    return jsonify({
        'message': '투표가 생성되었습니다.',
        'vote_id': vote_data['id']
    })

@app.route('/groups/vote/<int:vote_id>/vote', methods=['POST'])
def submit_vote():
    """투표 제출"""
    data = request.get_json()
    vote_id = data.get('vote_id')
    user_id = data.get('user_id')
    option = data.get('option')
    
    if not all([vote_id, user_id, option]):
        return jsonify({'message': '필수 정보가 누락되었습니다.'}), 400
    
    # 실제로는 데이터베이스에서 투표 정보를 가져와야 함
    vote = next((v for v in votes if v['id'] == vote_id), None)
    if not vote:
        return jsonify({'message': '투표를 찾을 수 없습니다.'}), 404
    
    if user_id in vote['votes']:
        return jsonify({'message': '이미 투표하셨습니다.'}), 400
    
    vote['votes'][user_id] = option
    
    return jsonify({'message': '투표가 제출되었습니다.'})

# 임시 투표 데이터 (실제로는 데이터베이스 사용)
votes = []

def find_best_match(user, employee_id):
    """선호도 기반으로 최적의 매칭 파트너를 찾습니다."""
    waiting_users = User.query.filter(
        and_(
            User.matching_status == 'waiting',  # type: ignore
            User.employee_id != employee_id  # type: ignore
        )
    ).all()
    
    if not waiting_users:
        return None
    
    # 각 대기 사용자와의 호환성 점수 계산
    best_match = None
    best_score = 0
    
    for candidate in waiting_users:
        score = calculate_compatibility_score(user, candidate)
        if score > best_score:
            best_score = score
            best_match = candidate
    
    # 최소 호환성 점수 이상인 경우에만 매칭
    return best_match if best_score >= 0.3 else None

def calculate_compatibility_score(user1, user2):
    """두 사용자 간의 호환성 점수를 계산합니다 (0-1)."""
    score = 0.0
    
    # 음식 선호도 비교
    if user1.food_preferences and user2.food_preferences:
        prefs1 = set(user1.food_preferences.split(','))
        prefs2 = set(user2.food_preferences.split(','))
        if prefs1 & prefs2:  # 공통 선호도가 있으면
            score += 0.3
    
    # 선호 시간대 비교
    if user1.preferred_time and user2.preferred_time:
        if user1.preferred_time == user2.preferred_time:
            score += 0.2
    
    # 자주 가는 지역 비교
    if user1.frequent_areas and user2.frequent_areas:
        areas1 = set(user1.frequent_areas.split(','))
        areas2 = set(user2.frequent_areas.split(','))
        if areas1 & areas2:  # 공통 지역이 있으면
            score += 0.2
    
    # 알레르기 호환성 (서로 다른 알레르기가 있으면 감점)
    if user1.allergies and user2.allergies:
        allergies1 = set(user1.allergies.split(','))
        allergies2 = set(user2.allergies.split(','))
        if not (allergies1 & allergies2):  # 공통 알레르기가 없으면
            score += 0.1
    
    # 기본 점수 (무작위 매칭보다는 나음)
    score += 0.2
    
    return min(score, 1.0)

# --- 스마트 랜덤 런치 API ---
SMART_LUNCH_CACHE = {}
SMART_LUNCH_CACHE_DATE = None

# 패턴 점수 계산 예시 함수
# (실제 서비스에서는 더 정교하게 구현 가능)
def get_last_dining_together(user1_id, user2_id):
    """두 사용자가 마지막으로 함께 점심을 먹은 시간을 계산하는 함수"""
    try:
        # 두 사용자가 함께 참여한 파티 중 가장 최근 것을 찾기
        latest_party = db.session.query(Party).filter(
            and_(
                or_(
                    and_(
                        getattr(Party, 'host_employee_id') == user1_id,
                        getattr(Party, 'members_employee_ids').contains(user2_id)
                    ),
                    and_(
                        getattr(Party, 'host_employee_id') == user2_id,
                        getattr(Party, 'members_employee_ids').contains(user1_id)
                    )
                ),
                getattr(Party, 'party_date') < get_seoul_today().strftime('%Y-%m-%d')
            )
        ).order_by(desc(Party.party_date)).first()
        
        if latest_party:
            party_date = datetime.strptime(latest_party.party_date, '%Y-%m-%d').date()
            today = get_seoul_today()
            days_diff = (today - party_date).days
            
            if days_diff == 0:
                return "오늘"
            elif days_diff == 1:
                return "어제"
            elif days_diff < 7:
                return f"{days_diff}일 전"
            elif days_diff < 30:
                weeks = days_diff // 7
                return f"{weeks}주 전"
            elif days_diff < 365:
                months = days_diff // 30
                return f"{months}개월 전"
            else:
                years = days_diff // 365
                return f"{years}년 전"
        else:
            return "처음 만나는 동료"
    except Exception as e:
        print(f"Error calculating last dining together: {e}")
        return "알 수 없음"

def calculate_pattern_score(requester, user):
    score = 0.0
    # 점심 시간대 선호 일치
    if requester.preferred_time and user.preferred_time:
        if requester.preferred_time == user.preferred_time:
            score += 0.5
    # 음식 취향 일치
    if requester.main_dish_genre and user.main_dish_genre:
        if requester.main_dish_genre == user.main_dish_genre:
            score += 0.3
    # 그룹 크기 선호(예시: 없음)
    # 기타 패턴 요소 추가 가능
    return min(score, 1.0)

@app.route('/proposals/smart-recommendations', methods=['GET'])
def get_smart_recommendations():
    employee_id = request.args.get('employee_id')
    # 여러 파라미터 이름 지원 (프론트엔드 호환성)
    selected_date = request.args.get('selected_date') or request.args.get('date') or request.args.get('target_date')
    
    # 디버깅을 위한 로그 추가
    print(f"DEBUG: Received request with employee_id={employee_id}, selected_date={selected_date}")
    print(f"DEBUG: All request args: {dict(request.args)}")
    
    if not employee_id:
        return jsonify({'error': 'employee_id is required'}), 400

    try:
        # 캐시가 없으면 먼저 생성
        if not RECOMMENDATION_CACHE:
            generate_recommendation_cache()
        
        # 기본 날짜 설정: 가장 가까운 영업일
        if not selected_date:
            today = get_seoul_today()
            # 오늘이 주말이면 다음 월요일로 설정
            if today.weekday() >= 5:  # 토요일(5) 또는 일요일(6)
                days_until_monday = (7 - today.weekday()) % 7
                if days_until_monday == 0:
                    days_until_monday = 7
                selected_date = (today + timedelta(days=days_until_monday)).strftime('%Y-%m-%d')
            else:
                selected_date = today.strftime('%Y-%m-%d')

        # 캐시에서 추천 그룹 조회
        cache_key = f"{employee_id}_{selected_date}"
        if cache_key in RECOMMENDATION_CACHE:
            print(f"DEBUG: Returning cached recommendations for {cache_key}")
            return jsonify(RECOMMENDATION_CACHE[cache_key])
        
        print(f"DEBUG: No cache found for {cache_key}, returning empty list")
        return jsonify([])
        
    except Exception as e:
        print(f"Error in smart recommendations: {e}")
        return jsonify({'error': 'Internal server error'}), 500
        


# --- 새로운 투표 시스템 API ---

@app.route('/voting-sessions', methods=['POST'])
def create_voting_session():
    """새로운 투표 세션 생성"""
    try:
        data = request.get_json()
        
        # 필수 필드 검증
        required_fields = ['chat_room_id', 'title', 'participants', 'created_by', 'expires_at']
        for field in required_fields:
            if not data.get(field):
                return jsonify({'error': f'{field}가 필요합니다.'}), 400
        
        # 정확한 만료 시간 파싱 (ISO 형식)
        try:
            expires_at_str = data['expires_at']
            if expires_at_str.endswith('Z'):
                expires_at_str = expires_at_str[:-1] + '+00:00'
            
            expires_at = datetime.fromisoformat(expires_at_str)
            
            # 타임존이 있으면 UTC로 변환 후 naive datetime으로 저장
            if expires_at.tzinfo:
                expires_at = expires_at.utctimetuple()
                expires_at = datetime(*expires_at[:6])
            
            print(f"Parsed expires_at: {expires_at}")  # 디버깅용
        except Exception as e:
            print(f"Error parsing expires_at: {e}")
            expires_at = datetime.utcnow() + timedelta(hours=24)  # 기본값 24시간
        
        # 참가자들의 가능한 날짜 계산
        participant_ids = data['participants']
        
        # 프론트엔드에서 전달한 선택된 날짜들 우선 사용
        if data.get('available_dates'):
            # 전달받은 날짜들이 실제로 모든 참가자가 가능한지 검증
            all_available_dates, _ = find_available_dates_for_participants(participant_ids, max_days=365*3)
            all_available_dates_set = set(date_info['date'] for date_info in all_available_dates)
            
            # 선택된 날짜 중 모든 참가자가 가능한 날짜만 필터링
            valid_dates = [date for date in data['available_dates'] if date in all_available_dates_set]
            
            if valid_dates:
                available_dates = [{'date': date, 'type': 'selected'} for date in valid_dates]
            else:
                # 선택된 날짜가 모두 불가능한 경우 일반 계산 사용
                available_dates, _ = find_available_dates_for_participants(participant_ids, max_days=30)
        else:
            # 기본 가능한 날짜 계산
            available_dates, alternative_dates = find_available_dates_for_participants(participant_ids, max_days=30)
        
        # 채팅방이 없는 경우 자동으로 생성
        chat_room_id = data['chat_room_id']
        print(f"=== DEBUG: 투표 세션 생성 - chat_room_id: {chat_room_id} ===")
        print(f"=== DEBUG: 전체 요청 데이터: {data} ===")
        
        if chat_room_id == -1:
            # 새 채팅방 생성
            chat_room = ChatRoom(
                name=data['title'],
                type='group'
            )
            db.session.add(chat_room)
            db.session.flush()
            chat_room_id = chat_room.id
            
            print(f"=== DEBUG: 새 채팅방 생성 - ID: {chat_room_id}, 이름: {data['title']}, 타입: group ===")
            
            # 참여자들 추가
            for user_id in participant_ids:
                participant = ChatParticipant(room_id=chat_room.id, user_id=user_id)
                db.session.add(participant)
                print(f"=== DEBUG: 참여자 추가 - user_id: {user_id} ===")
        else:
            # 기존 채팅방이 존재하는지 확인
            chat_room = ChatRoom.query.get(chat_room_id)
            print(f"=== DEBUG: ChatRoom.query.get({chat_room_id}) 결과: {chat_room} ===")
            
            if not chat_room:
                print(f"=== DEBUG: 채팅방을 찾을 수 없음 - ID: {chat_room_id}, 새로 생성 ===")
                # 채팅방이 존재하지 않으면 새로 생성
                chat_room = ChatRoom(
                    name=data['title'],
                    type='group'  # create_chat_room API와 일치하도록 'group'으로 변경
                )
                db.session.add(chat_room)
                db.session.flush()
                chat_room_id = chat_room.id
                print(f"=== DEBUG: 새로 생성된 채팅방 - ID: {chat_room_id}, 타입: {chat_room.type} ===")
                
                # 참여자들 추가
                for user_id in participant_ids:
                    participant = ChatParticipant(room_id=chat_room.id, user_id=user_id)
                    db.session.add(participant)
                    print(f"=== DEBUG: 참여자 추가 - user_id: {user_id} ===")
            else:
                print(f"=== DEBUG: 기존 채팅방 사용 - ID: {chat_room_id}, 이름: {chat_room.name}, 타입: {chat_room.type} ===")
        
        # 새로운 투표 세션 생성
        voting_session = VotingSession(
            chat_room_id=chat_room_id,
            title=data['title'],
            participants=json.dumps(participant_ids),
            created_by=data['created_by'],
            expires_at=expires_at,
            restaurant_name=data.get('restaurant_name'),
            restaurant_address=data.get('restaurant_address'),
            meeting_location=data.get('meeting_location'),
            meeting_time=data.get('meeting_time')
        )
        
        # 가능한 날짜 저장
        voting_session.available_dates = json.dumps([date_info['date'] for date_info in available_dates])
        
        db.session.add(voting_session)
        db.session.commit()
        
        # 채팅방에 투표 시작 시스템 메시지 추가
        # 한국 시간으로 변환해서 표시
        korean_expires_at = voting_session.expires_at + timedelta(hours=9)
        system_message = f"📊 새로운 투표가 시작되었습니다!\n'{voting_session.title}'\n마감: {korean_expires_at.strftime('%m월 %d일 %H:%M')}\n\n이 메시지를 터치하여 투표에 참여하세요 👆"
        
        # 채팅방 타입에 따라 chat_type 결정
        chat_type = chat_room.type  # 실제 채팅방 타입 사용
        print(f"=== DEBUG: 투표 메시지 생성 - chat_type: {chat_type}, chat_id: {chat_room_id} ===")
        
        chat_message = ChatMessage(
            chat_type=chat_type,
            chat_id=chat_room_id,
            sender_employee_id='SYSTEM',
            sender_nickname='시스템',
            message=system_message
        )
        chat_message.created_at = datetime.now()  # 한국 시간으로 설정
        db.session.add(chat_message)
        
        print(f"=== DEBUG: 투표 메시지 내용: {system_message[:100]}... ===")
        
        # WebSocket으로 실시간 알림
        room = f"{chat_type}_{chat_room_id}"
        print(f"=== DEBUG: WebSocket room: {room} ===")
        
        # 채팅 메시지 알림 (WebSocket을 통해 voting_session_id 전달)
        socketio.emit('new_message', {
            'id': chat_message.id,
            'sender_employee_id': 'SYSTEM',
            'sender_nickname': '시스템',
            'message': system_message,
            'created_at': chat_message.created_at.strftime('%Y-%m-%d %H:%M:%S'),
            'message_type': 'voting_notification',
            'voting_session_id': voting_session.id,
            'chat_type': chat_type,
            'chat_id': chat_room_id
        }, room=room)
        
        # 투표 세션 알림
        socketio.emit('new_voting_session', {
            'session_id': voting_session.id,
            'title': voting_session.title,
            'expires_at': voting_session.expires_at.strftime('%Y-%m-%d %H:%M'),
            'available_dates': available_dates
        }, room=room)
        
        # 참가자들에게 알림 생성 (투표 생성자도 포함) - 채팅방 여부와 상관없이 항상 생성
        active_participants = data.get('participants', [])
        for participant_id in active_participants:
            notification = Notification(
                user_id=participant_id,
                type='voting_started',
                title=f"새 투표: {voting_session.title}",
                message=f"'{voting_session.title}' 투표가 시작되었습니다. 원하는 날짜에 투표해주세요!",
                related_id=voting_session.id
            )
            db.session.add(notification)
        
        db.session.commit()
        
        print(f"=== DEBUG: 투표 세션 생성 완료 - ID: {voting_session.id}, 채팅방 ID: {chat_room_id} ===")
        
        return jsonify({
            'id': voting_session.id,
            'title': voting_session.title,
            'available_dates': available_dates,
            'expires_at': voting_session.expires_at.strftime('%Y-%m-%d %H:%M'),
            'status': voting_session.status,
            'chat_room_id': chat_room_id  # 생성된 채팅방 ID 반환
        }), 201
        
    except Exception as e:
        print(f"Error creating voting session: {e}")
        return jsonify({'error': '투표 세션 생성에 실패했습니다.'}), 500

@app.route('/voting-sessions/<int:session_id>', methods=['GET'])
def get_voting_session(session_id):
    """투표 세션 정보 조회"""
    try:
        session = VotingSession.query.get(session_id)
        if not session:
            return jsonify({'error': '투표 세션을 찾을 수 없습니다.'}), 404
        
        # 마감 시간 체크 및 자동 확정
        if session.status == 'active' and datetime.utcnow() > session.expires_at:
            # 투표 현황 조회
            votes = DateVote.query.filter_by(voting_session_id=session_id).all()
            vote_counts = {}
            
            for vote in votes:
                vote_counts[vote.voted_date] = vote_counts.get(vote.voted_date, 0) + 1
            
            if vote_counts:
                # 가장 많은 표를 받은 날짜 찾기
                max_votes = max(vote_counts.values())
                winning_dates = [date for date, count in vote_counts.items() if count == max_votes]
                winning_date = min(winning_dates)  # 동점 시 가장 빠른 날짜
                
                # 투표 세션 완료
                session.status = 'completed'
                session.confirmed_date = winning_date
                session.confirmed_at = datetime.utcnow()
                
                # 요일 계산
                weekday = datetime.strptime(winning_date, '%Y-%m-%d').weekday()
                weekday_name = ['월', '화', '수', '목', '금', '토', '일'][weekday]
                
                # 채팅방이 있는 경우에만 채팅방에 메시지 전송
                if session.chat_room_id != -1:
                    # 채팅방에 투표 마감 시스템 메시지 추가
                    completion_message = f"⏰ '{session.title}' 투표가 마감되었습니다!\n\n🎉 확정 날짜: {winning_date} ({weekday_name})"
                    if session.restaurant_name:
                        completion_message += f"\n🍽️ 식당: {session.restaurant_name}"
                    if session.meeting_time:
                        completion_message += f"\n🕐 시간: {session.meeting_time}"
                    if session.meeting_location:
                        completion_message += f"\n📍 장소: {session.meeting_location}"
                    completion_message += f"\n\n일정이 자동으로 저장되었습니다 📅"
                    
                    chat_message = ChatMessage(
                        chat_type='custom',
                        chat_id=session.chat_room_id,
                        sender_employee_id='SYSTEM',
                        sender_nickname='시스템',
                        message=completion_message
                    )
                    chat_message.created_at = datetime.now()
                    db.session.add(chat_message)
                    
                    # WebSocket으로 실시간 알림
                    room = f"custom_{session.chat_room_id}"
                    socketio.emit('new_message', {
                        'id': chat_message.id,
                        'sender_employee_id': 'SYSTEM',
                        'sender_nickname': '시스템',
                        'message': completion_message,
                        'created_at': chat_message.created_at.strftime('%Y-%m-%d %H:%M:%S'),
                        'message_type': 'voting_completed',
                        'voting_session_id': session.id,
                        'chat_type': 'custom',
                        'chat_id': session.chat_room_id
                    }, room=room)
                
                db.session.commit()
                
                # 개인 일정 자동 저장 (파티는 생성하지 않고 개인 일정만 생성)
                save_personal_schedules_from_voting(session)
            else:
                # 투표가 없으면 취소 처리
                session.status = 'cancelled'
                db.session.commit()
        
        # 투표 현황 조회
        votes = DateVote.query.filter_by(voting_session_id=session_id).all()
        vote_counts = {}
        voter_info = {}
        
        for vote in votes:
            date = vote.voted_date
            if date not in vote_counts:
                vote_counts[date] = 0
                voter_info[date] = []
            vote_counts[date] += 1
            
            # 투표자 정보
            voter = User.query.filter_by(employee_id=vote.voter_id).first()
            if voter:
                voter_info[date].append({
                    'employee_id': vote.voter_id,
                    'nickname': voter.nickname
                })
        
        # 참가자 목록
        participant_ids = json.loads(session.participants)
        participants = User.query.filter(User.employee_id.in_(participant_ids)).all()
        participant_list = [{
            'employee_id': p.employee_id,
            'nickname': p.nickname
        } for p in participants]
        
        # 투표율 계산
        voted_users = set(vote.voter_id for vote in votes)
        vote_rate = len(voted_users) / len(participant_ids) if participant_ids else 0
        
        return jsonify({
            'id': session.id,
            'title': session.title,
            'restaurant_name': session.restaurant_name,
            'meeting_location': session.meeting_location,
            'meeting_time': session.meeting_time,
            'participants': participant_list,
            'available_dates': json.loads(session.available_dates) if session.available_dates else [],
            'vote_counts': vote_counts,
            'voter_info': voter_info,
            'vote_rate': vote_rate,
            'voted_count': len(voted_users),
            'total_participants': len(participant_ids),
            'expires_at': format_korean_time(session.expires_at),
            'status': session.status,
            'confirmed_date': session.confirmed_date,
            'created_by': session.created_by  # 생성자 정보 추가
        })
        
    except Exception as e:
        print(f"Error getting voting session: {e}")
        return jsonify({'error': '투표 세션 조회에 실패했습니다.'}), 500

@app.route('/voting-sessions/<int:session_id>/vote', methods=['POST', 'DELETE'])
def vote_for_date(session_id):
    """날짜에 투표하기"""
    try:
        data = request.get_json()
        voter_id = data.get('voter_id')
        voted_date = data.get('voted_date')
        
        if not voter_id or not voted_date:
            return jsonify({'error': 'voter_id와 voted_date가 필요합니다.'}), 400
        
        # 투표 세션 확인
        session = VotingSession.query.get(session_id)
        if not session:
            return jsonify({'error': '투표 세션을 찾을 수 없습니다.'}), 404
        
        if session.status != 'active':
            return jsonify({'error': '종료된 투표입니다.'}), 400
        
        if datetime.utcnow() > session.expires_at:
            return jsonify({'error': '투표 기간이 만료되었습니다.'}), 400
        
        # 참가자 확인
        participant_ids = json.loads(session.participants)
        if voter_id not in participant_ids:
            return jsonify({'error': '투표 권한이 없습니다.'}), 403
        
        # DELETE 요청 처리 (명시적 투표 삭제)
        if request.method == 'DELETE':
            existing_vote = DateVote.query.filter_by(
                voting_session_id=session_id,
                voter_id=voter_id,
                voted_date=voted_date
            ).first()
            
            if existing_vote:
                db.session.delete(existing_vote)
                action = '투표가 삭제되었습니다.'
            else:
                return jsonify({'error': '삭제할 투표가 없습니다.'}), 404
        
        # POST 요청 처리 (새로운 투표만 추가)
        else:
            is_editing = data.get('is_editing', False)  # 편집 모드 여부 확인
            
            existing_vote = DateVote.query.filter_by(
                voting_session_id=session_id,
                voter_id=voter_id,
                voted_date=voted_date
            ).first()
            
            if is_editing:
                # 편집 모드: 무조건 새로운 투표 추가 (toggle 방식 사용 안함)
                if not existing_vote:  # 혹시 이미 있다면 패스
                    new_vote = DateVote(
                        voting_session_id=session_id,
                        voter_id=voter_id,
                        voted_date=voted_date
                    )
                    db.session.add(new_vote)
                action = '투표가 완료되었습니다.'
            else:
                # 일반 모드: 기존 toggle 방식 유지
                if existing_vote:
                    # 이미 투표한 날짜면 투표 취소
                    db.session.delete(existing_vote)
                    action = '투표가 취소되었습니다.'
                else:
                    # 새로운 투표 추가
                    new_vote = DateVote(
                        voting_session_id=session_id,
                        voter_id=voter_id,
                        voted_date=voted_date
                    )
                    db.session.add(new_vote)
                    action = '투표가 완료되었습니다.'
        
        db.session.commit()
        
        # 투표 결과 확인 (모든 참가자가 투표했는지)
        total_votes = DateVote.query.filter_by(voting_session_id=session_id).count()
        voted_users = set(vote.voter_id for vote in DateVote.query.filter_by(voting_session_id=session_id).all())
        
        # WebSocket으로 실시간 업데이트 (채팅방이 있는 경우에만)
        if session.chat_room_id != -1:
            room = f"custom_{session.chat_room_id}"
            socketio.emit('vote_updated', {
                'session_id': session_id,
                'voter_id': voter_id,
                'voted_date': voted_date,
                'total_votes': total_votes,
                'total_participants': len(participant_ids),
                'voted_users_count': len(voted_users)
            }, room=room)
        
        # 모든 참가자가 투표했으면 자동 확정
        if len(voted_users) >= len(participant_ids):
            # 가장 많은 표를 받은 날짜 찾기
            vote_counts = {}
            votes = DateVote.query.filter_by(voting_session_id=session_id).all()
            for vote in votes:
                vote_counts[vote.voted_date] = vote_counts.get(vote.voted_date, 0) + 1
            
            if vote_counts:
                winning_date = max(vote_counts.keys(), key=lambda x: vote_counts[x])
                winning_count = vote_counts[winning_date]
                
                # 동점 처리: 가장 가까운 날짜 선택
                max_votes = max(vote_counts.values())
                winning_dates = [date for date, count in vote_counts.items() if count == max_votes]
                winning_date = min(winning_dates)  # 가장 가까운 날짜
                
                # 투표 세션 완료
                session.status = 'completed'
                session.confirmed_date = winning_date
                session.confirmed_at = datetime.utcnow()
                
                # 요일 계산
                weekday = datetime.strptime(winning_date, '%Y-%m-%d').weekday()
                weekday_name = ['월', '화', '수', '목', '금', '토', '일'][weekday]
                
                # 채팅방에 투표 완료 시스템 메시지 추가
                completion_message = f"🎉 '{session.title}' 투표가 완료되었습니다!\n모든 참가자가 투표를 완료했습니다.\n\n✅ 확정 날짜: {winning_date} ({weekday_name})"
                if session.restaurant_name:
                    completion_message += f"\n🍽️ 식당: {session.restaurant_name}"
                if session.meeting_time:
                    completion_message += f"\n🕐 시간: {session.meeting_time}"
                if session.meeting_location:
                    completion_message += f"\n📍 장소: {session.meeting_location}"
                completion_message += f"\n\n일정이 자동으로 저장되었습니다 📅"
                
                chat_message = ChatMessage(
                    chat_type='custom',
                    chat_id=session.chat_room_id,
                    sender_employee_id='SYSTEM',
                    sender_nickname='시스템',
                    message=completion_message
                )
                chat_message.created_at = datetime.now()
                db.session.add(chat_message)
                
                # WebSocket으로 실시간 알림
                room = f"custom_{session.chat_room_id}"
                socketio.emit('new_message', {
                    'id': chat_message.id,
                    'sender_employee_id': 'SYSTEM',
                    'sender_nickname': '시스템',
                    'message': completion_message,
                    'created_at': chat_message.created_at.strftime('%Y-%m-%d %H:%M:%S'),
                    'message_type': 'voting_completed',
                    'voting_session_id': session.id,
                    'chat_type': 'custom',
                    'chat_id': session.chat_room_id
                }, room=room)
                
                db.session.commit()
                
                # 개인 일정 자동 저장 (파티는 생성하지 않고 개인 일정만 생성)
                save_personal_schedules_from_voting(session)
        
        return jsonify({
            'message': action,
            'voted_date': voted_date,
            'total_votes': total_votes,
            'total_participants': len(participant_ids)
        })
        
    except Exception as e:
        print(f"Error voting for date: {e}")
        return jsonify({'error': '투표에 실패했습니다.'}), 500

@app.route('/voting-sessions/<int:session_id>/cancel', methods=['POST'])
def cancel_voting_session(session_id):
    """투표 세션 취소"""
    try:
        data = request.get_json()
        user_id = data.get('user_id')
        
        session = VotingSession.query.get(session_id)
        if not session:
            return jsonify({'error': '투표 세션을 찾을 수 없습니다.'}), 404
        
        if session.created_by != user_id:
            return jsonify({'error': '투표를 생성한 사용자만 취소할 수 있습니다.'}), 403
        
        if session.status != 'active':
            return jsonify({'error': '이미 완료되거나 취소된 투표입니다.'}), 400
        
        # 투표 생성자 정보 조회
        creator = User.query.filter_by(employee_id=session.created_by).first()
        creator_name = creator.nickname if creator else session.created_by
        
        session.status = 'cancelled'
        
        # 채팅방이 있는 경우에만 채팅방에 메시지 전송
        if session.chat_room_id != -1:
            # 채팅방에 투표 취소 시스템 메시지 추가
            cancel_message = f"🚫 '{session.title}' 투표가 삭제되었습니다.\n삭제자: {creator_name}"
            
            chat_message = ChatMessage(
                chat_type='party',
                chat_id=session.chat_room_id,
                sender_employee_id='SYSTEM',
                sender_nickname='시스템',
                message=cancel_message
            )
            chat_message.created_at = datetime.now()  # 한국 시간으로 설정
            db.session.add(chat_message)
            
            # WebSocket으로 실시간 알림
            room = f"party_{session.chat_room_id}"
            
            # 채팅 메시지 알림
            socketio.emit('new_message', {
                'id': chat_message.id,
                'sender_employee_id': 'SYSTEM',
                'sender_nickname': '시스템',
                'message': cancel_message,
                'created_at': chat_message.created_at.strftime('%Y-%m-%d %H:%M:%S'),
                'message_type': 'voting_cancelled',
                'voting_session_id': session_id,
                'chat_type': 'party',
                'chat_id': session.chat_room_id
            }, room=room)
            
            # 투표 취소 알림
            socketio.emit('voting_cancelled', {
                'session_id': session_id,
                'message': '투표가 취소되었습니다.'
            }, room=room)
        
        db.session.commit()
        
        return jsonify({'message': '투표가 취소되었습니다.'})
        
    except Exception as e:
        print(f"Error cancelling voting session: {e}")
        return jsonify({'error': '투표 취소에 실패했습니다.'}), 500

@app.route('/voting-sessions/<int:session_id>/update', methods=['PUT'])
def update_voting_session(session_id):
    """투표 세션 정보 수정 (생성자만 가능)"""
    try:
        data = request.get_json()
        
        # 투표 세션 조회
        session = VotingSession.query.get(session_id)
        if not session:
            return jsonify({'error': '투표 세션을 찾을 수 없습니다.'}), 404
        
        # 활성 상태인지 확인
        if session.status != 'active':
            return jsonify({'error': '완료되거나 취소된 투표는 수정할 수 없습니다.'}), 400
        
        # 수정 가능한 필드들 업데이트
        if 'title' in data:
            session.title = data['title']
        
        if 'restaurant_name' in data:
            session.restaurant_name = data['restaurant_name']
        
        if 'meeting_time' in data:
            session.meeting_time = data['meeting_time']
        
        if 'meeting_location' in data:
            session.meeting_location = data['meeting_location']
        
        if 'expires_at' in data:
            # 새로운 마감시간 파싱
            try:
                expires_at_str = data['expires_at']
                if expires_at_str.endswith('Z'):
                    expires_at_str = expires_at_str[:-1] + '+00:00'
                
                new_expires_at = datetime.fromisoformat(expires_at_str)
                
                # 타임존이 있으면 UTC로 변환 후 naive datetime으로 저장
                if new_expires_at.tzinfo:
                    new_expires_at = new_expires_at.utctimetuple()
                    new_expires_at = datetime(*new_expires_at[:6])
                
                # 현재 시간보다 미래인지 확인
                if new_expires_at <= datetime.utcnow():
                    return jsonify({'error': '마감시간은 현재 시간보다 미래여야 합니다.'}), 400
                
                session.expires_at = new_expires_at
            except Exception as e:
                return jsonify({'error': '올바르지 않은 마감시간 형식입니다.'}), 400
        
        db.session.commit()
        
        # 채팅방이 있는 경우에만 채팅방에 메시지 전송
        if session.chat_room_id != -1:
            # 채팅방에 수정 알림 메시지 전송
            update_message = f"📝 '{session.title}' 투표 정보가 수정되었습니다."
            chat_message = ChatMessage(
                chat_type='party',
                chat_id=session.chat_room_id,
                sender_employee_id='SYSTEM',
                sender_nickname='시스템',
                message=update_message
            )
            chat_message.created_at = datetime.now()
            db.session.add(chat_message)
            db.session.commit()
            
            # WebSocket으로 실시간 알림
            room = f"party_{session.chat_room_id}"
            socketio.emit('new_message', {
                'id': chat_message.id,
                'sender_employee_id': 'SYSTEM',
                'sender_nickname': '시스템',
                'message': update_message,
                'created_at': chat_message.created_at.strftime('%Y-%m-%d %H:%M:%S'),
                'message_type': 'voting_updated',
                'voting_session_id': session.id,
                'chat_type': 'party',
                'chat_id': session.chat_room_id
            }, room=room)
        
        return jsonify({
            'message': '투표 정보가 수정되었습니다.',
            'session': {
                'id': session.id,
                'title': session.title,
                'restaurant_name': session.restaurant_name,
                'meeting_time': session.meeting_time,
                'meeting_location': session.meeting_location,
                'expires_at': format_korean_time(session.expires_at)
            }
        })
        
    except Exception as e:
        print(f"투표 정보 수정 오류: {e}")
        db.session.rollback()
        return jsonify({'error': '투표 정보 수정에 실패했습니다.'}), 500

@app.route('/voting-sessions/<int:session_id>/replace-votes', methods=['PUT'])
def replace_user_votes(session_id):
    """사용자의 모든 투표를 새로운 투표로 교체 (편집 모드 전용)"""
    try:
        data = request.get_json()
        voter_id = data.get('voter_id')
        new_voted_dates = data.get('new_voted_dates', [])
        
        if not voter_id:
            return jsonify({'error': 'voter_id가 필요합니다.'}), 400
        
        # 투표 세션 확인
        session = VotingSession.query.get(session_id)
        if not session:
            return jsonify({'error': '투표 세션을 찾을 수 없습니다.'}), 404
        
        if session.status != 'active':
            return jsonify({'error': '종료된 투표입니다.'}), 400
        
        if datetime.utcnow() > session.expires_at:
            return jsonify({'error': '투표 기간이 만료되었습니다.'}), 400
        
        # 참가자 확인
        participant_ids = json.loads(session.participants)
        if voter_id not in participant_ids:
            return jsonify({'error': '투표 권한이 없습니다.'}), 403
        
        # 트랜잭션으로 안전하게 처리
        try:
            # 1. 기존 투표 모두 삭제
            existing_votes = DateVote.query.filter_by(
                voting_session_id=session_id,
                voter_id=voter_id
            ).all()
            
            for vote in existing_votes:
                db.session.delete(vote)
            
            # 2. 새로운 투표 추가
            for date in new_voted_dates:
                # 투표 가능한 날짜인지 확인
                available_dates = json.loads(session.available_dates)
                if date in available_dates:
                    new_vote = DateVote(
                        voting_session_id=session_id,
                        voter_id=voter_id,
                        voted_date=date
                    )
                    db.session.add(new_vote)
            
            db.session.commit()
            
            return jsonify({
                'message': '투표가 성공적으로 변경되었습니다.',
                'voted_dates': new_voted_dates
            })
            
        except Exception as e:
            db.session.rollback()
            print(f"투표 교체 중 오류: {e}")
            return jsonify({'error': '투표 교체 중 오류가 발생했습니다.'}), 500
        
    except Exception as e:
        print(f"투표 교체 오류: {e}")
        return jsonify({'error': '투표 교체에 실패했습니다.'}), 500

def save_personal_schedules_from_voting(session):
    """투표 결과로 참가자들의 개인 일정 자동 저장"""
    try:
        if not session.confirmed_date:
            return
        
        participant_ids = json.loads(session.participants)
        
        # 일정 제목 생성
        schedule_title = session.title
        
        # 일정 설명 생성 (더 상세하게)
        description_parts = []
        description_parts.append(f"📅 모임명: {schedule_title}")
        description_parts.append(f"📆 날짜: {session.confirmed_date}")
        
        if session.restaurant_name:
            description_parts.append(f"🍽️ 식당: {session.restaurant_name}")
        else:
            description_parts.append(f"🍽️ 식당: 미정")
            
        if session.meeting_time:
            description_parts.append(f"🕐 모이는 시간: {session.meeting_time}")
        else:
            description_parts.append(f"🕐 모이는 시간: 12:00")
            
        if session.meeting_location:
            description_parts.append(f"📍 모이는 장소: {session.meeting_location}")
        else:
            description_parts.append(f"📍 모이는 장소: 1층 로비")
        
        # 참가자 목록 추가
        participants = User.query.filter(User.employee_id.in_(participant_ids)).all()
        participant_names = [p.nickname for p in participants]
        if participant_names:
            description_parts.append(f"👥 참석자: {', '.join(participant_names)} ({len(participant_names)}명)")
        
        description = '\n'.join(description_parts)
        
        # 각 참가자의 개인 일정에 저장
        for participant_id in participant_ids:
            # 이미 해당 날짜에 동일한 일정이 있는지 확인
            existing_schedule = PersonalSchedule.query.filter_by(
                employee_id=participant_id,
                schedule_date=session.confirmed_date,
                title=schedule_title
            ).first()
            
            if not existing_schedule:
                personal_schedule = PersonalSchedule(
                    employee_id=participant_id,
                    schedule_date=session.confirmed_date,
                    title=schedule_title,
                    description=description
                )
                db.session.add(personal_schedule)
        
        db.session.commit()
        print(f"개인 일정 저장 완료: {len(participant_ids)}명")
        
    except Exception as e:
        print(f"개인 일정 저장 실패: {e}")
        db.session.rollback()

def auto_create_party_from_voting(session):
    """투표 결과로 자동 파티 생성"""
    try:
        if not session.confirmed_date:
            return
        
        # 파티 생성
        new_party = Party(
            host_employee_id=session.created_by,
            title=session.title,
            restaurant_name=session.restaurant_name or '미정',
            restaurant_address=session.restaurant_address,
            party_date=session.confirmed_date,
            party_time=session.meeting_time or '12:00',
            meeting_location=session.meeting_location or '미정',
            max_members=len(json.loads(session.participants)),
            members_employee_ids=','.join(json.loads(session.participants)),
            is_from_match=False
        )
        
        db.session.add(new_party)
        db.session.flush()
        
        # 채팅방 생성
        new_party.create_chat_room()
        db.session.commit()
        
        # WebSocket으로 파티 생성 알림 (채팅방이 있는 경우에만)
        if session.chat_room_id != -1:
            room = f"custom_{session.chat_room_id}"
            socketio.emit('party_created_from_voting', {
                'party_id': new_party.id,
                'title': new_party.title,
                'date': new_party.party_date,
                'time': new_party.party_time,
                'restaurant': new_party.restaurant_name
            }, room=room)
        
    except Exception as e:
        print(f"Error auto creating party: {e}")

# --- 기존 함수들 ---

def generate_daily_recommendations():
    """매일 자정에 새로운 추천 그룹 생성"""
    try:
        today = get_seoul_today()
        today_str = today.strftime('%Y-%m-%d')
        
        # 오늘 날짜의 추천 그룹이 이미 있는지 확인
        existing = DailyRecommendation.query.filter_by(date=today_str).first()
        if existing:
            return  # 이미 생성되어 있으면 스킵
        
        # 모든 사용자 가져오기
        all_users = User.query.all()
        
        # 각 사용자별로 추천 그룹 생성 (최대 20개 그룹)
        group_count = 0
        for user in all_users:
            if group_count >= 20:
                break
                
            # 해당 사용자와 호환되는 다른 사용자들 찾기
            compatible_users = []
            for other_user in all_users:
                if other_user.employee_id != user.employee_id:
                    preference_score = calculate_compatibility_score(user, other_user)
                    pattern_score = calculate_pattern_score(user, other_user)
                    # 일관된 시드 사용
                    random.seed(hash(today_str + other_user.employee_id))
                    random_score = random.random()
                    total_score = preference_score * 0.6 + pattern_score * 0.3 + random_score * 0.1
                    compatible_users.append((other_user, total_score))
            
            # 점수순으로 정렬
            compatible_users.sort(key=lambda x: x[1], reverse=True)
            
            # 그룹 생성 (3명씩)
            for i in range(0, len(compatible_users), 3):
                if i + 3 <= len(compatible_users) and group_count < 20:
                    group_members = []
                    for other_user, score in compatible_users[i:i+3]:
                        last_dining = get_last_dining_together(user.employee_id, other_user.employee_id)
                        
                        group_members.append({
                            "nickname": other_user.nickname,
                            "lunch_preference": other_user.lunch_preference,
                            "employee_id": other_user.employee_id,
                            "compatibility_score": round(score, 2),
                            "last_dining_together": last_dining
                        })
                    
                    if group_members:
                        daily_rec = DailyRecommendation(today_str, json.dumps(group_members))
                        db.session.add(daily_rec)
                        group_count += 1
        
        db.session.commit()
        print(f"Generated {group_count} daily recommendations for {today_str}")
        
    except Exception as e:
        print(f"Error generating daily recommendations: {e}")
        db.session.rollback()

# 스케줄러 초기화
scheduler = BackgroundScheduler()
scheduler.add_job(
    func=generate_daily_recommendations,
    trigger=CronTrigger(hour=0, minute=0, timezone='Asia/Seoul'),
    id='daily_recommendations',
    name='Generate daily recommendations at midnight',
    replace_existing=True
)
scheduler.start()

@app.route('/proposals/generate-today', methods=['POST'])
def generate_today_recommendations():
    """오늘 날짜의 추천 그룹을 수동으로 생성하는 API (테스트용)"""
    try:
        generate_daily_recommendations()
        return jsonify({'message': 'Today\'s recommendations generated successfully'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=5000, debug=True)

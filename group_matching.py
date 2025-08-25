"""
그룹 매칭 공통 로직 모듈
개발/프로덕션 환경에서 공통으로 사용하는 그룹 생성 및 점수 계산 로직
"""

import random
from datetime import datetime

def calculate_group_score(members, users_data, date):
    """그룹 매칭 점수 계산 (실제 앱 로직과 동일)"""
    score = 0
    
    # 그룹 크기 점수 (2-4명만 허용, 3명이 최적)
    group_size = len(members)
    if group_size > 4:
        return 0  # 4명 초과 그룹은 제외
    
    if group_size == 3:
        score += 30
    elif group_size == 4:
        score += 25
    elif group_size == 2:
        score += 20
    else:
        score += 10
    
    # 사용자별 호환성 점수 계산
    for i in range(len(members)):
        for j in range(i + 1, len(members)):
            user1_id = members[i]
            user2_id = members[j]
            user1 = users_data[user1_id]
            user2 = users_data[user2_id]
            
            # 음식 선호도 호환성
            if user1.get('foodPreferences') and user2.get('foodPreferences'):
                common_prefs = set(user1['foodPreferences']) & set(user2['foodPreferences'])
                if common_prefs:
                    score += len(common_prefs) * 15
            
            # 점심 성향 호환성
            if user1.get('lunchStyle') and user2.get('lunchStyle'):
                common_styles = set(user1['lunchStyle']) & set(user2['lunchStyle'])
                if common_styles:
                    score += len(common_styles) * 20
            
            # 선호 시간 호환성
            if user1.get('preferredTime') == user2.get('preferredTime'):
                score += 15
            
            # 알러지 정보 호환성
            if user1.get('allergies') == user2.get('allergies'):
                score += 10
    
    # 날짜별 랜덤 점수 (0-15점) - 실제 앱과 동일
    date_seed = int(date.replace('-', ''))
    random_score = (date_seed * 9301 + 49297) % 233280
    random_score = (random_score / 233280) * 16
    
    score += int(random_score)
    
    return score

def generate_groups(available_users, target_date, current_user_id, num_groups=10):
    """그룹 생성 공통 로직"""
    groups = []
    
    for group_idx in range(num_groups):
        # 그룹 크기 (2-4명, 3명이 최적)
        group_size = random.choices([2, 3, 4], weights=[0.2, 0.6, 0.2])[0]
        
        # 사용 가능한 유저에서 그룹 크기만큼 선택
        available_user_ids = list(available_users.keys())
        if len(available_user_ids) >= group_size:
            group_members = random.sample(available_user_ids, group_size)
            
            # 그룹 점수 계산
            score = calculate_group_score(group_members, available_users, target_date)
            
            group_data = {
                'id': f'group_{target_date}_{group_idx}',
                'date': target_date,
                'members': group_members,
                'status': 'matched',
                'created_at': datetime.now().isoformat(),
                'score': score,
                'max_members': group_size + 1,  # 현재 사용자 포함 가능
                'current_members': group_size
            }
            groups.append(group_data)
    
    # 점수 순으로 정렬
    groups.sort(key=lambda x: x['score'], reverse=True)
    
    return groups

def get_virtual_users_data():
    """가상 사용자 데이터 반환"""
    return {
        '1': {'nickname': '김철수', 'foodPreferences': ['한식', '중식'], 'lunchStyle': ['맛집 탐방', '새로운 메뉴 도전'], 'allergies': ['없음'], 'preferredTime': '12:00'},
        '2': {'nickname': '이영희', 'foodPreferences': ['양식', '일식'], 'lunchStyle': ['건강한 음식', '다이어트'], 'allergies': ['없음'], 'preferredTime': '12:30'},
        '3': {'nickname': '박민수', 'foodPreferences': ['한식', '분식'], 'lunchStyle': ['빠른 식사', '가성비'], 'allergies': ['없음'], 'preferredTime': '12:00'},
        '4': {'nickname': '최지은', 'foodPreferences': ['양식', '한식'], 'lunchStyle': ['다양한 음식', '새로운 메뉴 도전'], 'allergies': ['없음'], 'preferredTime': '12:00'},
        '5': {'nickname': '정현우', 'foodPreferences': ['중식', '한식'], 'lunchStyle': ['맛집 탐방', '분위기 좋은 곳'], 'allergies': ['없음'], 'preferredTime': '12:00'},
        '6': {'nickname': '한소영', 'foodPreferences': ['일식', '양식'], 'lunchStyle': ['건강한 음식', '다이어트'], 'allergies': ['없음'], 'preferredTime': '12:30'},
        '7': {'nickname': '윤준호', 'foodPreferences': ['한식', '분식'], 'lunchStyle': ['빠른 식사', '가성비'], 'allergies': ['없음'], 'preferredTime': '12:00'},
        '8': {'nickname': '송미라', 'foodPreferences': ['양식', '일식'], 'lunchStyle': ['맛집 탐방', '새로운 메뉴 도전'], 'allergies': ['없음'], 'preferredTime': '12:00'},
        '9': {'nickname': '강동현', 'foodPreferences': ['중식', '한식'], 'lunchStyle': ['건강한 음식', '다이어트'], 'allergies': ['없음'], 'preferredTime': '12:30'},
        '10': {'nickname': '임서연', 'foodPreferences': ['한식', '분식'], 'lunchStyle': ['빠른 식사', '가성비'], 'allergies': ['없음'], 'preferredTime': '12:00'},
        '11': {'nickname': '오태호', 'foodPreferences': ['양식', '일식'], 'lunchStyle': ['맛집 탐방', '새로운 메뉴 도전'], 'allergies': ['없음'], 'preferredTime': '12:00'},
        '12': {'nickname': '신유진', 'foodPreferences': ['중식', '한식'], 'lunchStyle': ['건강한 음식', '다이어트'], 'allergies': ['없음'], 'preferredTime': '12:30'},
        '13': {'nickname': '조성민', 'foodPreferences': ['한식', '분식'], 'lunchStyle': ['빠른 식사', '가성비'], 'allergies': ['없음'], 'preferredTime': '12:00'},
        '14': {'nickname': '백하은', 'foodPreferences': ['양식', '일식'], 'lunchStyle': ['맛집 탐방', '새로운 메뉴 도전'], 'allergies': ['없음'], 'preferredTime': '12:00'},
        '15': {'nickname': '남준석', 'foodPreferences': ['중식', '한식'], 'lunchStyle': ['건강한 음식', '다이어트'], 'allergies': ['없음'], 'preferredTime': '12:30'},
        '16': {'nickname': '류지현', 'foodPreferences': ['일식', '양식'], 'lunchStyle': ['맛집 탐방', '분위기 좋은 곳'], 'allergies': ['없음'], 'preferredTime': '12:00'},
        '17': {'nickname': '차준호', 'foodPreferences': ['한식', '분식'], 'lunchStyle': ['건강한 식사', '빠른 식사'], 'allergies': ['없음'], 'preferredTime': '12:00'},
        '18': {'nickname': '구미영', 'foodPreferences': ['양식', '일식'], 'lunchStyle': ['맛집 탐방', '새로운 메뉴 도전'], 'allergies': ['없음'], 'preferredTime': '12:00'},
        '19': {'nickname': '홍성훈', 'foodPreferences': ['중식', '한식'], 'lunchStyle': ['건강한 음식', '다이어트'], 'allergies': ['없음'], 'preferredTime': '12:30'},
        '20': {'nickname': '전소연', 'foodPreferences': ['한식', '분식'], 'lunchStyle': ['빠른 식사', '가성비'], 'allergies': ['없음'], 'preferredTime': '12:00'}
    }

def get_virtual_friend_relationships():
    """가상 친구 관계 반환"""
    return {
        '1': ['2', '3', '4', '5'],
        '2': ['1', '3', '6', '7'],
        '3': ['1', '2', '4', '8'],
        '4': ['1', '3', '5', '9'],
        '5': ['1', '4', '6', '10'],
        '6': ['2', '5', '7', '11'],
        '7': ['2', '6', '8', '12'],
        '8': ['3', '7', '9', '13'],
        '9': ['4', '8', '10', '14'],
        '10': ['5', '9', '11', '15'],
        '11': ['6', '10', '12', '16'],
        '12': ['7', '11', '13', '17'],
        '13': ['8', '12', '14', '18'],
        '14': ['9', '13', '15', '19'],
        '15': ['10', '14', '16', '20'],
        '16': ['11', '15', '17', '1'],
        '17': ['12', '16', '18', '2'],
        '18': ['13', '17', '19', '3'],
        '19': ['14', '18', '20', '4'],
        '20': ['15', '19', '1', '5']
    }

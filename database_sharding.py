#!/usr/bin/env python3
"""
데이터베이스 샤딩 시스템
사용자 수 증가에 대비한 수평 확장성 확보
"""

import hashlib
import sqlite3
import os
from typing import Dict, List, Any, Optional
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

class DatabaseSharding:
    """데이터베이스 샤딩 관리 클래스"""
    
    def __init__(self, base_path: str = "lunch_app/instance", shard_count: int = 4):
        """
        샤딩 시스템 초기화
        
        Args:
            base_path: 데이터베이스 파일들이 저장될 기본 경로
            shard_count: 샤드 개수 (기본값: 4)
        """
        self.base_path = base_path
        self.shard_count = shard_count
        self.shard_connections = {}
        self.current_shard = 0
        
        # 샤드 데이터베이스 초기화
        self._initialize_shards()
    
    def _initialize_shards(self):
        """샤드 데이터베이스들 초기화"""
        os.makedirs(self.base_path, exist_ok=True)
        
        for i in range(self.shard_count):
            shard_path = os.path.join(self.base_path, f"site_shard_{i}.db")
            self._create_shard_database(shard_path, i)
    
    def _create_shard_database(self, shard_path: str, shard_id: int):
        """샤드 데이터베이스 생성 및 테이블 초기화"""
        try:
            conn = sqlite3.connect(shard_path)
            cursor = conn.cursor()
            
            # 기본 테이블 생성
            self._create_shard_tables(cursor, shard_id)
            
            conn.commit()
            conn.close()
            
            logger.info(f"샤드 {shard_id} 데이터베이스 초기화 완료: {shard_path}")
            
        except Exception as e:
            logger.error(f"샤드 {shard_id} 데이터베이스 초기화 실패: {e}")
    
    def _create_shard_tables(self, cursor: sqlite3.Cursor, shard_id: int):
        """샤드별 테이블 생성"""
        # 사용자 테이블 (샤드별로 분산)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS user (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                employee_id VARCHAR(50) UNIQUE NOT NULL,
                nickname VARCHAR(50),
                gender VARCHAR(10),
                age_group VARCHAR(20),
                main_dish_genre VARCHAR(100),
                total_points INTEGER DEFAULT 0,
                current_level INTEGER DEFAULT 1,
                current_badge VARCHAR(50),
                consecutive_login_days INTEGER DEFAULT 0,
                last_login_date DATE,
                shard_id INTEGER DEFAULT ?
            )
        ''', (shard_id,))
        
        # 사용자 선호도 테이블
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS user_preference (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id VARCHAR(50) NOT NULL,
                preference_type VARCHAR(50) NOT NULL,
                preference_value VARCHAR(100) NOT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                shard_id INTEGER DEFAULT ?
            )
        ''', (shard_id,))
        
        # 파티 테이블 (샤드별로 분산)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS party (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                host_employee_id VARCHAR(50) NOT NULL,
                title VARCHAR(100) NOT NULL,
                restaurant_name VARCHAR(100) NOT NULL,
                restaurant_address VARCHAR(200),
                party_date VARCHAR(20) NOT NULL,
                party_time VARCHAR(10) NOT NULL,
                meeting_location VARCHAR(200),
                max_members INTEGER NOT NULL DEFAULT 4,
                is_from_match BOOLEAN DEFAULT 0,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                shard_id INTEGER DEFAULT ?
            )
        ''', (shard_id,))
        
        # 파티 멤버 테이블
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS party_member (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                party_id INTEGER NOT NULL,
                employee_id VARCHAR(50) NOT NULL,
                joined_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                is_host BOOLEAN DEFAULT 0,
                shard_id INTEGER DEFAULT ?
            )
        ''', (shard_id,))
        
        # 인덱스 생성
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_user_employee_id ON user (employee_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_user_preference ON user_preference (user_id, preference_type)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_party_date ON party (party_date)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_party_member ON party_member (party_id, employee_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_shard_id ON user (shard_id)')
    
    def get_shard_for_user(self, user_id: str) -> int:
        """사용자 ID에 따른 샤드 결정"""
        # 해시 기반 샤드 결정
        hash_value = int(hashlib.md5(user_id.encode()).hexdigest(), 16)
        return hash_value % self.shard_count
    
    def get_shard_connection(self, shard_id: int) -> sqlite3.Connection:
        """특정 샤드의 데이터베이스 연결 반환"""
        if shard_id not in self.shard_connections:
            shard_path = os.path.join(self.base_path, f"site_shard_{shard_id}.db")
            self.shard_connections[shard_id] = sqlite3.connect(shard_path)
        
        return self.shard_connections[shard_id]
    
    def execute_on_shard(self, shard_id: int, query: str, params: tuple = ()) -> List[tuple]:
        """특정 샤드에서 쿼리 실행"""
        try:
            conn = self.get_shard_connection(shard_id)
            cursor = conn.cursor()
            cursor.execute(query, params)
            
            if query.strip().upper().startswith('SELECT'):
                result = cursor.fetchall()
            else:
                conn.commit()
                result = []
            
            return result
            
        except Exception as e:
            logger.error(f"샤드 {shard_id} 쿼리 실행 실패: {e}")
            raise
    
    def execute_on_all_shards(self, query: str, params: tuple = ()) -> Dict[int, List[tuple]]:
        """모든 샤드에서 쿼리 실행"""
        results = {}
        
        for shard_id in range(self.shard_count):
            try:
                result = self.execute_on_shard(shard_id, query, params)
                results[shard_id] = result
            except Exception as e:
                logger.error(f"샤드 {shard_id} 쿼리 실행 실패: {e}")
                results[shard_id] = []
        
        return results
    
    def get_user_data(self, user_id: str) -> Optional[Dict[str, Any]]:
        """사용자 데이터 조회"""
        shard_id = self.get_shard_for_user(user_id)
        
        query = '''
            SELECT employee_id, nickname, gender, age_group, main_dish_genre, 
                   total_points, current_level, current_badge, consecutive_login_days, last_login_date
            FROM user 
            WHERE employee_id = ?
        '''
        
        try:
            result = self.execute_on_shard(shard_id, query, (user_id,))
            if result:
                row = result[0]
                return {
                    'employee_id': row[0],
                    'nickname': row[1],
                    'gender': row[2],
                    'age_group': row[3],
                    'main_dish_genre': row[4],
                    'total_points': row[5],
                    'current_level': row[6],
                    'current_badge': row[7],
                    'consecutive_login_days': row[8],
                    'last_login_date': row[9],
                    'shard_id': shard_id
                }
        except Exception as e:
            logger.error(f"사용자 데이터 조회 실패: {e}")
        
        return None
    
    def create_user(self, user_data: Dict[str, Any]) -> bool:
        """사용자 생성"""
        user_id = user_data['employee_id']
        shard_id = self.get_shard_for_user(user_id)
        
        query = '''
            INSERT INTO user (employee_id, nickname, gender, age_group, main_dish_genre, shard_id)
            VALUES (?, ?, ?, ?, ?, ?)
        '''
        
        try:
            self.execute_on_shard(shard_id, query, (
                user_data['employee_id'],
                user_data.get('nickname'),
                user_data.get('gender'),
                user_data.get('age_group'),
                user_data.get('main_dish_genre'),
                shard_id
            ))
            
            # 사용자 선호도도 같은 샤드에 저장
            if 'preferences' in user_data:
                self._create_user_preferences(user_id, user_data['preferences'], shard_id)
            
            logger.info(f"사용자 {user_id} 생성 완료 (샤드 {shard_id})")
            return True
            
        except Exception as e:
            logger.error(f"사용자 생성 실패: {e}")
            return False
    
    def _create_user_preferences(self, user_id: str, preferences: Dict[str, List[str]], shard_id: int):
        """사용자 선호도 생성"""
        query = '''
            INSERT INTO user_preference (user_id, preference_type, preference_value, shard_id)
            VALUES (?, ?, ?, ?)
        '''
        
        for pref_type, pref_values in preferences.items():
            for pref_value in pref_values:
                self.execute_on_shard(shard_id, query, (user_id, pref_type, pref_value, shard_id))
    
    def get_user_parties(self, user_id: str) -> List[Dict[str, Any]]:
        """사용자가 참여한 파티 목록 조회"""
        shard_id = self.get_shard_for_user(user_id)
        
        query = '''
            SELECT p.id, p.title, p.restaurant_name, p.party_date, p.party_time, 
                   p.meeting_location, p.max_members, pm.is_host
            FROM party p
            JOIN party_member pm ON p.id = pm.party_id
            WHERE pm.employee_id = ?
            ORDER BY p.party_date DESC, p.party_time DESC
        '''
        
        try:
            result = self.execute_on_shard(shard_id, query, (user_id,))
            parties = []
            
            for row in result:
                parties.append({
                    'id': row[0],
                    'title': row[1],
                    'restaurant_name': row[2],
                    'party_date': row[3],
                    'party_time': row[4],
                    'meeting_location': row[5],
                    'max_members': row[6],
                    'is_host': bool(row[7])
                })
            
            return parties
            
        except Exception as e:
            logger.error(f"사용자 파티 목록 조회 실패: {e}")
            return []
    
    def search_users_across_shards(self, search_term: str, limit: int = 20) -> List[Dict[str, Any]]:
        """모든 샤드에서 사용자 검색"""
        query = '''
            SELECT employee_id, nickname, main_dish_genre, shard_id
            FROM user 
            WHERE nickname LIKE ? OR main_dish_genre LIKE ?
            LIMIT ?
        '''
        
        search_pattern = f"%{search_term}%"
        all_results = []
        
        for shard_id in range(self.shard_count):
            try:
                result = self.execute_on_shard(shard_id, query, (search_pattern, search_pattern, limit))
                for row in result:
                    all_results.append({
                        'employee_id': row[0],
                        'nickname': row[1],
                        'main_dish_genre': row[2],
                        'shard_id': row[3]
                    })
            except Exception as e:
                logger.error(f"샤드 {shard_id} 사용자 검색 실패: {e}")
        
        # 결과 정렬 및 제한
        all_results.sort(key=lambda x: x['nickname'])
        return all_results[:limit]
    
    def get_shard_statistics(self) -> Dict[str, Any]:
        """샤드별 통계 정보 조회"""
        stats = {
            'total_shards': self.shard_count,
            'shard_details': {}
        }
        
        for shard_id in range(self.shard_count):
            try:
                # 사용자 수
                user_count = self.execute_on_shard(shard_id, "SELECT COUNT(*) FROM user")[0][0]
                
                # 파티 수
                party_count = self.execute_on_shard(shard_id, "SELECT COUNT(*) FROM party")[0][0]
                
                # 데이터베이스 크기
                shard_path = os.path.join(self.base_path, f"site_shard_{shard_id}.db")
                file_size = os.path.getsize(shard_path) if os.path.exists(shard_path) else 0
                
                stats['shard_details'][shard_id] = {
                    'user_count': user_count,
                    'party_count': party_count,
                    'file_size_mb': round(file_size / (1024 * 1024), 2)
                }
                
            except Exception as e:
                logger.error(f"샤드 {shard_id} 통계 조회 실패: {e}")
                stats['shard_details'][shard_id] = {'error': str(e)}
        
        return stats
    
    def rebalance_shards(self) -> Dict[str, Any]:
        """샤드 재균형화 (데이터 분산 최적화)"""
        logger.info("샤드 재균형화 시작")
        
        # 현재 샤드별 사용자 수 확인
        current_distribution = {}
        for shard_id in range(self.shard_count):
            user_count = self.execute_on_shard(shard_id, "SELECT COUNT(*) FROM user")[0][0]
            current_distribution[shard_id] = user_count
        
        # 평균 사용자 수 계산
        total_users = sum(current_distribution.values())
        avg_users_per_shard = total_users / self.shard_count
        
        # 재균형화 계획 수립
        rebalance_plan = {}
        for shard_id, user_count in current_distribution.items():
            if user_count > avg_users_per_shard * 1.2:  # 20% 이상 많으면
                excess = int(user_count - avg_users_per_shard)
                rebalance_plan[shard_id] = {'action': 'move_out', 'count': excess}
            elif user_count < avg_users_per_shard * 0.8:  # 20% 이상 적으면
                deficit = int(avg_users_per_shard - user_count)
                rebalance_plan[shard_id] = {'action': 'move_in', 'count': deficit}
        
        logger.info(f"재균형화 계획: {rebalance_plan}")
        
        # 실제 재균형화는 복잡하므로 계획만 반환
        return {
            'current_distribution': current_distribution,
            'average_users_per_shard': avg_users_per_shard,
            'rebalance_plan': rebalance_plan,
            'status': 'plan_created'
        }
    
    def close_all_connections(self):
        """모든 샤드 연결 종료"""
        for shard_id, conn in self.shard_connections.items():
            try:
                conn.close()
            except Exception as e:
                logger.error(f"샤드 {shard_id} 연결 종료 실패: {e}")
        
        self.shard_connections.clear()
        logger.info("모든 샤드 연결 종료 완료")

# 전역 샤딩 인스턴스
sharding_system = DatabaseSharding()

# 편의 함수들
def get_user_shard(user_id: str) -> int:
    """사용자 ID에 따른 샤드 번호 반환"""
    return sharding_system.get_shard_for_user(user_id)

def get_user_data_sharded(user_id: str) -> Optional[Dict[str, Any]]:
    """샤딩된 시스템에서 사용자 데이터 조회"""
    return sharding_system.get_user_data(user_id)

def create_user_sharded(user_data: Dict[str, Any]) -> bool:
    """샤딩된 시스템에서 사용자 생성"""
    return sharding_system.create_user(user_data)

def search_users_sharded(search_term: str, limit: int = 20) -> List[Dict[str, Any]]:
    """샤딩된 시스템에서 사용자 검색"""
    return sharding_system.search_users_across_shards(search_term, limit)

def get_shard_stats() -> Dict[str, Any]:
    """샤드 통계 정보 조회"""
    return sharding_system.get_shard_statistics()

# 사용 예시
if __name__ == "__main__":
    # 샤딩 시스템 테스트
    print("🚀 데이터베이스 샤딩 시스템 테스트")
    
    # 샤드 통계 조회
    stats = get_shard_stats()
    print(f"샤드 통계: {stats}")
    
    # 테스트 사용자 생성
    test_users = [
        {
            'employee_id': 'TEST001',
            'nickname': '테스트사용자1',
            'gender': '남',
            'age_group': '20대',
            'main_dish_genre': '한식,분식',
            'preferences': {
                'lunch_preference': ['조용한 식사', '빠른 식사'],
                'food_preference': ['한식', '분식']
            }
        },
        {
            'employee_id': 'TEST002',
            'nickname': '테스트사용자2',
            'gender': '여',
            'age_group': '30대',
            'main_dish_genre': '양식,일식',
            'preferences': {
                'lunch_preference': ['대화 선호', '분위기 좋은 곳'],
                'food_preference': ['양식', '일식']
            }
        }
    ]
    
    for user_data in test_users:
        success = create_user_sharded(user_data)
        if success:
            print(f"✅ 사용자 {user_data['employee_id']} 생성 성공")
        else:
            print(f"❌ 사용자 {user_data['employee_id']} 생성 실패")
    
    # 사용자 데이터 조회 테스트
    for user_data in test_users:
        retrieved_data = get_user_data_sharded(user_data['employee_id'])
        if retrieved_data:
            print(f"📖 사용자 {user_data['employee_id']} 조회 성공: {retrieved_data['nickname']}")
        else:
            print(f"❌ 사용자 {user_data['employee_id']} 조회 실패")
    
    # 사용자 검색 테스트
    search_results = search_users_sharded('테스트')
    print(f"🔍 검색 결과: {len(search_results)}명 발견")
    
    # 샤드 재균형화 테스트
    rebalance_result = sharding_system.rebalance_shards()
    print(f"⚖️ 재균형화 결과: {rebalance_result['status']}")
    
    # 연결 종료
    sharding_system.close_all_connections()
    print("🔌 모든 샤드 연결 종료 완료")

#!/usr/bin/env python3
"""
사용자 관리 마이크로서비스
사용자 CRUD, 인증, 프로필 관리 담당
"""

from flask import Flask, request, jsonify
from flask_cors import CORS
import sqlite3
import hashlib
import jwt
import datetime
import logging
from typing import Dict, List, Any, Optional
import os

# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Flask 앱 생성
app = Flask(__name__)
CORS(app)

# 설정
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'your-secret-key-here')
app.config['DATABASE'] = os.environ.get('USER_DB_PATH', 'user_service.db')
app.config['JWT_EXPIRATION_HOURS'] = 24

class UserService:
    """사용자 서비스 클래스"""
    
    def __init__(self, db_path: str):
        self.db_path = db_path
        self.init_database()
    
    def init_database(self):
        """데이터베이스 초기화"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # 사용자 테이블
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    employee_id VARCHAR(50) UNIQUE NOT NULL,
                    nickname VARCHAR(50),
                    email VARCHAR(100),
                    password_hash VARCHAR(255),
                    gender VARCHAR(10),
                    age_group VARCHAR(20),
                    main_dish_genre VARCHAR(100),
                    total_points INTEGER DEFAULT 0,
                    current_level INTEGER DEFAULT 1,
                    current_badge VARCHAR(50),
                    consecutive_login_days INTEGER DEFAULT 0,
                    last_login_date DATE,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # 사용자 선호도 테이블
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS user_preferences (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id VARCHAR(50) NOT NULL,
                    preference_type VARCHAR(50) NOT NULL,
                    preference_value VARCHAR(100) NOT NULL,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # 인덱스 생성
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_user_employee_id ON users (employee_id)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_user_email ON users (email)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_user_preference ON user_preferences (user_id, preference_type)')
            
            conn.commit()
            conn.close()
            logger.info("사용자 서비스 데이터베이스 초기화 완료")
            
        except Exception as e:
            logger.error(f"데이터베이스 초기화 실패: {e}")
    
    def hash_password(self, password: str) -> str:
        """비밀번호 해싱"""
        return hashlib.sha256(password.encode()).hexdigest()
    
    def verify_password(self, password: str, hashed: str) -> bool:
        """비밀번호 검증"""
        return self.hash_password(password) == hashed
    
    def create_user(self, user_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """사용자 생성"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # 필수 필드 검증
            required_fields = ['employee_id', 'nickname', 'password']
            for field in required_fields:
                if field not in user_data or not user_data[field]:
                    return None
            
            # 비밀번호 해싱
            password_hash = self.hash_password(user_data['password'])
            
            # 사용자 생성
            cursor.execute('''
                INSERT INTO users (
                    employee_id, nickname, email, password_hash, gender, 
                    age_group, main_dish_genre
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (
                user_data['employee_id'],
                user_data['nickname'],
                user_data.get('email'),
                password_hash,
                user_data.get('gender'),
                user_data.get('age_group'),
                user_data.get('main_dish_genre')
            ))
            
            user_id = cursor.lastrowid
            
            # 선호도 추가
            if 'preferences' in user_data:
                for pref_type, pref_values in user_data['preferences'].items():
                    if isinstance(pref_values, list):
                        for value in pref_values:
                            cursor.execute('''
                                INSERT INTO user_preferences (user_id, preference_type, preference_value)
                                VALUES (?, ?, ?)
                            ''', (user_data['employee_id'], pref_type, value))
                    else:
                        cursor.execute('''
                            INSERT INTO user_preferences (user_id, preference_type, preference_value)
                            VALUES (?, ?, ?)
                        ''', (user_data['employee_id'], pref_type, pref_values))
            
            conn.commit()
            conn.close()
            
            # 생성된 사용자 정보 반환
            return self.get_user_by_employee_id(user_data['employee_id'])
            
        except Exception as e:
            logger.error(f"사용자 생성 실패: {e}")
            return None
    
    def get_user_by_employee_id(self, employee_id: str) -> Optional[Dict[str, Any]]:
        """사용자 ID로 사용자 조회"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT employee_id, nickname, email, gender, age_group, 
                       main_dish_genre, total_points, current_level, 
                       current_badge, consecutive_login_days, last_login_date,
                       created_at, updated_at
                FROM users 
                WHERE employee_id = ?
            ''', (employee_id,))
            
            row = cursor.fetchone()
            if not row:
                conn.close()
                return None
            
            # 선호도 조회
            cursor.execute('''
                SELECT preference_type, preference_value
                FROM user_preferences 
                WHERE user_id = ?
            ''', (employee_id,))
            
            preferences = {}
            for pref_row in cursor.fetchall():
                pref_type, pref_value = pref_row
                if pref_type not in preferences:
                    preferences[pref_type] = []
                preferences[pref_type].append(pref_value)
            
            conn.close()
            
            return {
                'employee_id': row[0],
                'nickname': row[1],
                'email': row[2],
                'gender': row[3],
                'age_group': row[4],
                'main_dish_genre': row[5],
                'total_points': row[6],
                'current_level': row[7],
                'current_badge': row[8],
                'consecutive_login_days': row[9],
                'last_login_date': row[10],
                'created_at': row[11],
                'updated_at': row[12],
                'preferences': preferences
            }
            
        except Exception as e:
            logger.error(f"사용자 조회 실패: {e}")
            return None
    
    def authenticate_user(self, employee_id: str, password: str) -> Optional[str]:
        """사용자 인증 및 JWT 토큰 반환"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # 사용자 조회
            cursor.execute('''
                SELECT nickname, password_hash
                FROM users 
                WHERE employee_id = ?
            ''', (employee_id,))
            
            row = cursor.fetchone()
            if not row:
                conn.close()
                return None
            
            nickname, stored_hash = row
            
            # 비밀번호 검증
            if not self.verify_password(password, stored_hash):
                conn.close()
                return None
            
            # 로그인 정보 업데이트
            cursor.execute('''
                UPDATE users 
                SET last_login_date = ?, consecutive_login_days = consecutive_login_days + 1
                WHERE employee_id = ?
            ''', (datetime.date.today().isoformat(), employee_id))
            
            conn.commit()
            conn.close()
            
            # JWT 토큰 생성
            token = jwt.encode({
                'employee_id': employee_id,
                'nickname': nickname,
                'exp': datetime.datetime.utcnow() + datetime.timedelta(hours=app.config['JWT_EXPIRATION_HOURS'])
            }, app.config['SECRET_KEY'], algorithm='HS256')
            
            return token
            
        except Exception as e:
            logger.error(f"사용자 인증 실패: {e}")
            return None
    
    def search_users(self, search_term: str, limit: int = 20) -> List[Dict[str, Any]]:
        """사용자 검색"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT employee_id, nickname, main_dish_genre, total_points, current_level
                FROM users 
                WHERE nickname LIKE ? OR main_dish_genre LIKE ?
                ORDER BY nickname
                LIMIT ?
            ''', (f"%{search_term}%", f"%{search_term}%", limit))
            
            users = []
            for row in cursor.fetchall():
                users.append({
                    'employee_id': row[0],
                    'nickname': row[1],
                    'main_dish_genre': row[2],
                    'total_points': row[3],
                    'current_level': row[4]
                })
            
            conn.close()
            return users
            
        except Exception as e:
            logger.error(f"사용자 검색 실패: {e}")
            return []
    
    def delete_user(self, employee_id: str) -> bool:
        """사용자 삭제"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # 선호도 먼저 삭제
            cursor.execute('DELETE FROM user_preferences WHERE user_id = ?', (employee_id,))
            
            # 사용자 삭제
            cursor.execute('DELETE FROM users WHERE employee_id = ?', (employee_id,))
            
            conn.commit()
            conn.close()
            
            logger.info(f"사용자 {employee_id} 삭제 완료")
            return True
            
        except Exception as e:
            logger.error(f"사용자 삭제 실패: {e}")
            return False

# 전역 서비스 인스턴스
user_service = UserService(app.config['DATABASE'])

# API 엔드포인트들

@app.route('/health', methods=['GET'])
def health_check():
    """서비스 상태 확인"""
    return jsonify({
        'service': 'user-service',
        'status': 'healthy',
        'timestamp': datetime.datetime.now().isoformat()
    })

@app.route('/users', methods=['POST'])
def create_user():
    """사용자 생성"""
    try:
        user_data = request.get_json()
        if not user_data:
            return jsonify({'error': '사용자 데이터가 필요합니다'}), 400
        
        user = user_service.create_user(user_data)
        if user:
            return jsonify({'message': '사용자 생성 성공', 'user': user}), 201
        else:
            return jsonify({'error': '사용자 생성 실패'}), 500
            
    except Exception as e:
        logger.error(f"사용자 생성 API 오류: {e}")
        return jsonify({'error': '서버 오류가 발생했습니다'}), 500

@app.route('/users/<employee_id>', methods=['GET'])
def get_user(employee_id: str):
    """사용자 조회"""
    try:
        user = user_service.get_user_by_employee_id(employee_id)
        if user:
            return jsonify(user)
        else:
            return jsonify({'error': '사용자를 찾을 수 없습니다'}), 404
            
    except Exception as e:
        logger.error(f"사용자 조회 API 오류: {e}")
        return jsonify({'error': '서버 오류가 발생했습니다'}), 500

@app.route('/auth/login', methods=['POST'])
def login():
    """사용자 로그인"""
    try:
        auth_data = request.get_json()
        if not auth_data or 'employee_id' not in auth_data or 'password' not in auth_data:
            return jsonify({'error': '사용자 ID와 비밀번호가 필요합니다'}), 400
        
        token = user_service.authenticate_user(auth_data['employee_id'], auth_data['password'])
        if token:
            return jsonify({
                'message': '로그인 성공',
                'token': token,
                'employee_id': auth_data['employee_id']
            })
        else:
            return jsonify({'error': '잘못된 사용자 ID 또는 비밀번호입니다'}), 401
            
    except Exception as e:
        logger.error(f"로그인 API 오류: {e}")
        return jsonify({'error': '서버 오류가 발생했습니다'}), 500

@app.route('/users/search', methods=['GET'])
def search_users():
    """사용자 검색"""
    try:
        search_term = request.args.get('q', '')
        limit = int(request.args.get('limit', 20))
        
        if not search_term:
            return jsonify({'error': '검색어가 필요합니다'}), 400
        
        users = user_service.search_users(search_term, limit)
        return jsonify({'users': users, 'count': len(users)})
        
    except Exception as e:
        logger.error(f"사용자 검색 API 오류: {e}")
        return jsonify({'error': '서버 오류가 발생했습니다'}), 500

@app.route('/users/<employee_id>', methods=['DELETE'])
def delete_user(employee_id: str):
    """사용자 삭제"""
    try:
        success = user_service.delete_user(employee_id)
        if success:
            return jsonify({'message': '사용자 삭제 성공'})
        else:
            return jsonify({'error': '사용자 삭제 실패'}), 500
            
    except Exception as e:
        logger.error(f"사용자 삭제 API 오류: {e}")
        return jsonify({'error': '서버 오류가 발생했습니다'}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5001, debug=True)

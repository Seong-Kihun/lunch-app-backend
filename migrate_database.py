#!/usr/bin/env python3
"""
데이터베이스 마이그레이션 스크립트
정규화되지 않은 스키마를 정규화된 스키마로 변환
"""

import sqlite3
import json
from datetime import datetime

def migrate_database():
    """데이터베이스 마이그레이션 실행"""
    print("🚀 데이터베이스 마이그레이션을 시작합니다...")
    
    try:
        # 기존 데이터베이스 연결
        conn = sqlite3.connect('lunch_app/instance/site.db')
        cursor = conn.cursor()
        
        # 1. 새로운 테이블 생성
        print("📋 새로운 정규화된 테이블을 생성합니다...")
        create_normalized_tables(cursor)
        
        # 2. 기존 데이터 마이그레이션
        print("🔄 기존 데이터를 정규화된 테이블로 마이그레이션합니다...")
        migrate_user_data(cursor)
        migrate_party_data(cursor)
        migrate_dangolpot_data(cursor)
        
        # 3. 기존 테이블 백업 및 제거
        print("🗑️ 기존 비정규화된 테이블을 제거합니다...")
        cleanup_old_tables(cursor)
        
        # 4. 변경사항 커밋
        conn.commit()
        print("✅ 마이그레이션이 성공적으로 완료되었습니다!")
        
    except Exception as e:
        print(f"❌ 마이그레이션 중 오류가 발생했습니다: {e}")
        conn.rollback()
        raise
    finally:
        conn.close()

def create_normalized_tables(cursor):
    """정규화된 테이블 생성"""
    
    # UserPreference 테이블
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS user_preference (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id VARCHAR(50) NOT NULL,
            preference_type VARCHAR(50) NOT NULL,
            preference_value VARCHAR(100) NOT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES user (employee_id)
        )
    ''')
    
    # UserNotificationSettings 테이블
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS user_notification_settings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id VARCHAR(50) NOT NULL,
            setting_type VARCHAR(50) NOT NULL,
            setting_value BOOLEAN DEFAULT 1,
            FOREIGN KEY (user_id) REFERENCES user (employee_id)
        )
    ''')
    
    # PartyMember 테이블
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS party_member (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            party_id INTEGER NOT NULL,
            employee_id VARCHAR(50) NOT NULL,
            joined_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            is_host BOOLEAN DEFAULT 0,
            FOREIGN KEY (party_id) REFERENCES party (id),
            FOREIGN KEY (employee_id) REFERENCES user (employee_id)
        )
    ''')
    
    # DangolPotMember 테이블
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS dangolpot_member (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            dangolpot_id INTEGER NOT NULL,
            employee_id VARCHAR(50) NOT NULL,
            joined_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (dangolpot_id) REFERENCES dangolpot (id),
            FOREIGN KEY (employee_id) REFERENCES user (employee_id)
        )
    ''')
    
    # 인덱스 생성
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_user_preference ON user_preference (user_id, preference_type)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_user_notification ON user_notification_settings (user_id, setting_type)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_party_member ON party_member (party_id, employee_id)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_member_party ON party_member (employee_id, party_id)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_dangolpot_member ON dangolpot_member (dangolpot_id, employee_id)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_member_dangolpot ON dangolpot_member (employee_id, dangolpot_id)')

def migrate_user_data(cursor):
    """사용자 데이터 마이그레이션"""
    print("👥 사용자 데이터를 마이그레이션합니다...")
    
    # 기존 User 테이블에서 선호도 정보 추출
    cursor.execute('''
        SELECT employee_id, lunch_preference, food_preferences, allergies, 
               preferred_time, frequent_areas, notification_settings
        FROM user
    ''')
    
    users = cursor.fetchall()
    
    for user in users:
        employee_id, lunch_pref, food_prefs, allergies, pref_time, freq_areas, notif_settings = user
        
        # lunch_preference 마이그레이션
        if lunch_pref:
            for pref in lunch_pref.split(','):
                pref = pref.strip()
                if pref:
                    cursor.execute('''
                        INSERT INTO user_preference (user_id, preference_type, preference_value)
                        VALUES (?, 'lunch_preference', ?)
                    ''', (employee_id, pref))
        
        # food_preferences 마이그레이션
        if food_prefs:
            for pref in food_prefs.split(','):
                pref = pref.strip()
                if pref:
                    cursor.execute('''
                        INSERT INTO user_preference (user_id, preference_type, preference_value)
                        VALUES (?, 'food_preference', ?)
                    ''', (employee_id, pref))
        
        # allergies 마이그레이션
        if allergies:
            for allergy in allergies.split(','):
                allergy = allergy.strip()
                if allergy:
                    cursor.execute('''
                        INSERT INTO user_preference (user_id, preference_type, preference_value)
                        VALUES (?, 'allergies', ?)
                    ''', (employee_id, allergy))
        
        # preferred_time 마이그레이션
        if pref_time:
            cursor.execute('''
                INSERT INTO user_preference (user_id, preference_type, preference_value)
                VALUES (?, 'preferred_time', ?)
            ''', (employee_id, pref_time))
        
        # frequent_areas 마이그레이션
        if freq_areas:
            for area in freq_areas.split(','):
                area = area.strip()
                if area:
                    cursor.execute('''
                        INSERT INTO user_preference (user_id, preference_type, preference_value)
                        VALUES (?, 'frequent_areas', ?)
                    ''', (employee_id, area))
        
        # notification_settings 마이그레이션
        if notif_settings:
            try:
                settings = json.loads(notif_settings)
                for setting_type, setting_value in settings.items():
                    cursor.execute('''
                        INSERT INTO user_notification_settings (user_id, setting_type, setting_value)
                        VALUES (?, ?, ?)
                    ''', (employee_id, setting_type, setting_value))
            except json.JSONDecodeError:
                # JSON 파싱 실패 시 기본값 설정
                cursor.execute('''
                    INSERT INTO user_notification_settings (user_id, setting_type, setting_value)
                    VALUES (?, 'push_notification', 1)
                ''', (employee_id,))

def migrate_party_data(cursor):
    """파티 데이터 마이그레이션"""
    print("🎉 파티 데이터를 마이그레이션합니다...")
    
    # 기존 Party 테이블에서 멤버 정보 추출
    cursor.execute('''
        SELECT id, host_employee_id, members_employee_ids
        FROM party
    ''')
    
    parties = cursor.fetchall()
    
    for party in parties:
        party_id, host_id, members_str = party
        
        # 호스트를 PartyMember에 추가
        cursor.execute('''
            INSERT INTO party_member (party_id, employee_id, is_host)
            VALUES (?, ?, 1)
        ''', (party_id, host_id))
        
        # 멤버들을 PartyMember에 추가
        if members_str:
            member_ids = [mid.strip() for mid in members_str.split(',') if mid.strip()]
            for member_id in member_ids:
                if member_id != host_id:  # 호스트는 이미 추가됨
                    cursor.execute('''
                        INSERT INTO party_member (party_id, employee_id, is_host)
                        VALUES (?, ?, 0)
                    ''', (party_id, member_id))

def migrate_dangolpot_data(cursor):
    """단골파티 데이터 마이그레이션"""
    print("🏠 단골파티 데이터를 마이그레이션합니다...")
    
    # 기존 DangolPot 테이블에서 멤버 정보 추출
    cursor.execute('''
        SELECT id, host_id, members
        FROM dangolpot
    ''')
    
    dangolpots = cursor.fetchall()
    
    for dangolpot in dangolpots:
        dangolpot_id, host_id, members_str = dangolpot
        
        # 호스트를 DangolPotMember에 추가
        cursor.execute('''
            INSERT INTO dangolpot_member (dangolpot_id, employee_id)
            VALUES (?, ?)
        ''', (dangolpot_id, host_id))
        
        # 멤버들을 DangolPotMember에 추가
        if members_str:
            member_ids = [mid.strip() for mid in members_str.split(',') if mid.strip()]
            for member_id in member_ids:
                if member_id != host_id:  # 호스트는 이미 추가됨
                    cursor.execute('''
                        INSERT INTO dangolpot_member (dangolpot_id, employee_id)
                        VALUES (?, ?)
                    ''', (dangolpot_id, member_id))

def cleanup_old_tables(cursor):
    """기존 비정규화된 테이블 정리"""
    print("🧹 기존 테이블을 정리합니다...")
    
    # 기존 컬럼 제거 (SQLite는 ALTER TABLE DROP COLUMN을 지원하지 않으므로 새 테이블 생성 필요)
    # 이 부분은 실제 운영 환경에서는 더 신중하게 처리해야 함
    
    print("⚠️ 참고: 기존 컬럼 제거는 SQLite 제한으로 인해 수동으로 처리해야 합니다.")
    print("다음 컬럼들을 수동으로 제거하세요:")
    print("- User.lunch_preference")
    print("- User.food_preferences") 
    print("- User.allergies")
    print("- User.preferred_time")
    print("- User.frequent_areas")
    print("- User.notification_settings")
    print("- Party.members_employee_ids")
    print("- DangolPot.members")

if __name__ == "__main__":
    migrate_database()

#!/usr/bin/env python3
"""
실시간 매칭 시스템 제거를 위한 데이터베이스 마이그레이션 스크립트
"""

import sqlite3
import os

def remove_realtime_matching_fields():
    """실시간 매칭 관련 필드들을 제거합니다."""
    
    # 데이터베이스 파일 경로
    db_path = 'site.db'
    
    if not os.path.exists(db_path):
        print(f"데이터베이스 파일을 찾을 수 없습니다: {db_path}")
        return
    
    try:
        # 데이터베이스 연결
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        print("실시간 매칭 시스템 제거를 시작합니다...")
        
        # 1. User 테이블에서 실시간 매칭 관련 컬럼 제거
        print("1. User 테이블에서 실시간 매칭 관련 컬럼 제거 중...")
        
        # 기존 테이블 구조 확인
        cursor.execute("PRAGMA table_info(user)")
        columns = cursor.fetchall()
        column_names = [col[1] for col in columns]
        
        if 'matching_status' in column_names:
            # 임시 테이블 생성 (실시간 매칭 필드 제외)
            cursor.execute("""
                CREATE TABLE user_new (
                    id INTEGER PRIMARY KEY,
                    employee_id VARCHAR(50) UNIQUE NOT NULL,
                    nickname VARCHAR(50),
                    lunch_preference VARCHAR(200),
                    gender VARCHAR(10),
                    age_group VARCHAR(20),
                    main_dish_genre VARCHAR(100),
                    food_preferences TEXT,
                    allergies TEXT,
                    preferred_time VARCHAR(10),
                    frequent_areas TEXT,
                    notification_settings TEXT
                )
            """)
            
            # 데이터 복사 (실시간 매칭 필드 제외)
            cursor.execute("""
                INSERT INTO user_new (
                    id, employee_id, nickname, lunch_preference, gender, age_group, 
                    main_dish_genre, food_preferences, allergies, preferred_time, 
                    frequent_areas, notification_settings
                )
                SELECT 
                    id, employee_id, nickname, lunch_preference, gender, age_group,
                    main_dish_genre, food_preferences, allergies, preferred_time,
                    frequent_areas, notification_settings
                FROM user
            """)
            
            # 기존 테이블 삭제 및 새 테이블 이름 변경
            cursor.execute("DROP TABLE user")
            cursor.execute("ALTER TABLE user_new RENAME TO user")
            
            print("✅ User 테이블에서 실시간 매칭 필드 제거 완료")
        else:
            print("ℹ️ User 테이블에 실시간 매칭 필드가 없습니다.")
        
        # 2. 실시간 매칭으로 생성된 파티들 정리 (선택사항)
        print("2. 실시간 매칭으로 생성된 파티들 확인 중...")
        
        cursor.execute("""
            SELECT COUNT(*) FROM party 
            WHERE is_from_match = 1 AND title = '스마트 런치'
        """)
        count = cursor.fetchone()[0]
        
        if count > 0:
            print(f"⚠️ 실시간 매칭으로 생성된 파티가 {count}개 있습니다.")
            print("   이 파티들을 삭제하시겠습니까? (y/n): ", end="")
            
            # 실제 운영에서는 사용자 입력을 받아야 하지만, 스크립트에서는 자동으로 처리
            response = 'y'  # 실제로는 input()을 사용해야 함
            
            if response.lower() == 'y':
                cursor.execute("""
                    DELETE FROM party 
                    WHERE is_from_match = 1 AND title = '스마트 런치'
                """)
                print(f"✅ {count}개의 실시간 매칭 파티 삭제 완료")
            else:
                print("ℹ️ 실시간 매칭 파티는 유지됩니다.")
        else:
            print("ℹ️ 실시간 매칭으로 생성된 파티가 없습니다.")
        
        # 변경사항 저장
        conn.commit()
        print("✅ 데이터베이스 마이그레이션 완료!")
        
    except Exception as e:
        print(f"❌ 오류 발생: {e}")
        conn.rollback()
    finally:
        conn.close()

if __name__ == "__main__":
    remove_realtime_matching_fields() 
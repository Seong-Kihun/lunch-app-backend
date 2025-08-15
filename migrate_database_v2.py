#!/usr/bin/env python3
"""
데이터베이스 마이그레이션 스크립트 v2
- Party 모델의 members_employee_ids 필드 제거
- 데이터 정규화 및 무결성 검사
- 기존 데이터 보존
"""

import sqlite3
import os
import sys
from datetime import datetime

def backup_database(db_path):
    """데이터베이스 백업"""
    backup_path = f"{db_path}.backup.{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    
    try:
        with open(db_path, 'rb') as source:
            with open(backup_path, 'wb') as target:
                target.write(source.read())
        print(f"✅ 데이터베이스 백업 완료: {backup_path}")
        return backup_path
    except Exception as e:
        print(f"❌ 데이터베이스 백업 실패: {e}")
        return None

def check_database_integrity(db_path):
    """데이터베이스 무결성 검사"""
    print("🔍 데이터베이스 무결성 검사 중...")
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # 테이블 존재 여부 확인
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [row[0] for row in cursor.fetchall()]
        
        required_tables = ['users', 'parties', 'party_members', 'chat_rooms', 'chat_participants']
        missing_tables = [table for table in required_tables if table not in tables]
        
        if missing_tables:
            print(f"❌ 누락된 테이블: {missing_tables}")
            return False
        
        # 데이터 개수 확인
        for table in required_tables:
            cursor.execute(f"SELECT COUNT(*) FROM {table}")
            count = cursor.fetchone()[0]
            print(f"  📊 {table}: {count}개 레코드")
        
        conn.close()
        print("✅ 데이터베이스 무결성 검사 완료")
        return True
        
    except Exception as e:
        print(f"❌ 데이터베이스 무결성 검사 실패: {e}")
        return False

def migrate_party_members_data(db_path):
    """Party 멤버 데이터 마이그레이션"""
    print("🔄 Party 멤버 데이터 마이그레이션 중...")
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # 기존 members_employee_ids 데이터 확인
        cursor.execute("""
            SELECT id, members_employee_ids 
            FROM parties 
            WHERE members_employee_ids IS NOT NULL 
            AND members_employee_ids != ''
        """)
        
        parties_with_members = cursor.fetchall()
        print(f"  📊 마이그레이션 대상 파티: {len(parties_with_members)}개")
        
        migrated_count = 0
        
        for party_id, members_str in parties_with_members:
            if not members_str:
                continue
                
            # 쉼표로 구분된 멤버 ID 파싱
            member_ids = [mid.strip() for mid in members_str.split(',') if mid.strip()]
            
            # 각 멤버를 party_members 테이블에 추가
            for member_id in member_ids:
                try:
                    # 이미 존재하는지 확인
                    cursor.execute("""
                        SELECT id FROM party_members 
                        WHERE party_id = ? AND employee_id = ?
                    """, (party_id, member_id))
                    
                    if not cursor.fetchone():
                        cursor.execute("""
                            INSERT INTO party_members (party_id, employee_id, joined_at)
                            VALUES (?, ?, ?)
                        """, (party_id, member_id, datetime.now().isoformat()))
                        migrated_count += 1
                        
                except Exception as e:
                    print(f"  ⚠️ 멤버 {member_id} 추가 실패: {e}")
                    continue
        
        conn.commit()
        conn.close()
        
        print(f"✅ 마이그레이션 완료: {migrated_count}개 멤버 추가됨")
        return True
        
    except Exception as e:
        print(f"❌ 마이그레이션 실패: {e}")
        return False

def remove_members_employee_ids_column(db_path):
    """members_employee_ids 컬럼 제거"""
    print("🗑️ members_employee_ids 컬럼 제거 중...")
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # 임시 테이블 생성 (기존 구조에서 members_employee_ids 제외)
        cursor.execute("""
            CREATE TABLE parties_new (
                id INTEGER PRIMARY KEY,
                host_employee_id VARCHAR(50) NOT NULL,
                title VARCHAR(100) NOT NULL,
                restaurant_name VARCHAR(100) NOT NULL,
                restaurant_address VARCHAR(200),
                party_date VARCHAR(20) NOT NULL,
                party_time VARCHAR(10) NOT NULL,
                meeting_location VARCHAR(200),
                max_members INTEGER NOT NULL DEFAULT 4,
                is_from_match BOOLEAN DEFAULT 0,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # 데이터 복사
        cursor.execute("""
            INSERT INTO parties_new 
            SELECT id, host_employee_id, title, restaurant_name, restaurant_address,
                   party_date, party_time, meeting_location, max_members, is_from_match, created_at
            FROM parties
        """)
        
        # 기존 테이블 삭제
        cursor.execute("DROP TABLE parties")
        
        # 새 테이블 이름 변경
        cursor.execute("ALTER TABLE parties_new RENAME TO parties")
        
        # 인덱스 재생성
        cursor.execute("CREATE INDEX idx_parties_host ON parties(host_employee_id)")
        cursor.execute("CREATE INDEX idx_parties_date ON parties(party_date)")
        
        conn.commit()
        conn.close()
        
        print("✅ members_employee_ids 컬럼 제거 완료")
        return True
        
    except Exception as e:
        print(f"❌ 컬럼 제거 실패: {e}")
        return False

def verify_migration(db_path):
    """마이그레이션 검증"""
    print("🔍 마이그레이션 검증 중...")
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # parties 테이블 스키마 확인
        cursor.execute("PRAGMA table_info(parties)")
        columns = [row[1] for row in cursor.fetchall()]
        
        if 'members_employee_ids' in columns:
            print("❌ members_employee_ids 컬럼이 여전히 존재합니다")
            return False
        
        # party_members 테이블 데이터 확인
        cursor.execute("SELECT COUNT(*) FROM party_members")
        member_count = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM parties")
        party_count = cursor.fetchone()[0]
        
        print(f"  📊 파티 수: {party_count}")
        print(f"  📊 파티 멤버 수: {member_count}")
        
        # 데이터 무결성 확인
        cursor.execute("""
            SELECT p.id, p.title, COUNT(pm.id) as member_count
            FROM parties p
            LEFT JOIN party_members pm ON p.id = pm.party_id
            GROUP BY p.id
            ORDER BY p.id
        """)
        
        parties = cursor.fetchall()
        print("  📋 파티별 멤버 수:")
        for party_id, title, member_count in parties[:5]:  # 처음 5개만 표시
            print(f"    - {title}: {member_count}명")
        
        if len(parties) > 5:
            print(f"    ... 및 {len(parties) - 5}개 더")
        
        conn.close()
        print("✅ 마이그레이션 검증 완료")
        return True
        
    except Exception as e:
        print(f"❌ 마이그레이션 검증 실패: {e}")
        return False

def main():
    """메인 마이그레이션 함수"""
    print("🚀 데이터베이스 마이그레이션 v2 시작")
    print("=" * 50)
    
    # 데이터베이스 경로 확인
    db_path = 'site.db'
    if not os.path.exists(db_path):
        print(f"❌ 데이터베이스 파일을 찾을 수 없습니다: {db_path}")
        sys.exit(1)
    
    print(f"📁 대상 데이터베이스: {db_path}")
    
    # 1단계: 백업
    backup_path = backup_database(db_path)
    if not backup_path:
        print("❌ 백업 실패로 마이그레이션을 중단합니다")
        sys.exit(1)
    
    # 2단계: 무결성 검사
    if not check_database_integrity(db_path):
        print("❌ 데이터베이스 무결성 검사 실패")
        sys.exit(1)
    
    # 3단계: 데이터 마이그레이션
    if not migrate_party_members_data(db_path):
        print("❌ 데이터 마이그레이션 실패")
        sys.exit(1)
    
    # 4단계: 컬럼 제거
    if not remove_members_employee_ids_column(db_path):
        print("❌ 컬럼 제거 실패")
        sys.exit(1)
    
    # 5단계: 검증
    if not verify_migration(db_path):
        print("❌ 마이그레이션 검증 실패")
        sys.exit(1)
    
    print("=" * 50)
    print("🎉 마이그레이션 완료!")
    print(f"📁 백업 파일: {backup_path}")
    print("💡 이제 앱을 실행할 수 있습니다")

if __name__ == "__main__":
    main()

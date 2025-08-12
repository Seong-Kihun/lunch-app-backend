# 🚀 데이터베이스 마이그레이션 가이드

## 📋 개요

이 문서는 기존의 비정규화된 데이터베이스 스키마를 정규화된 스키마로 마이그레이션하는 방법을 설명합니다.

## 🔍 주요 변경사항

### 1. 데이터베이스 정규화

#### Before (비정규화)
```python
class User(db.Model):
    lunch_preference = db.Column(db.String(200), nullable=True)  # 쉼표로 구분된 문자열
    food_preferences = db.Column(db.Text, nullable=True)  # 쉼표로 구분된 문자열
    allergies = db.Column(db.Text, nullable=True)  # 쉼표로 구분된 문자열

class Party(db.Model):
    members_employee_ids = db.Column(db.Text, default='')  # 쉼표로 구분된 문자열
```

#### After (정규화)
```python
class User(db.Model):
    # 선호도 정보는 별도 테이블로 분리
    pass

class UserPreference(db.Model):
    user_id = db.Column(db.String(50), db.ForeignKey('user.employee_id'))
    preference_type = db.Column(db.String(50), nullable=False)  # 'lunch_preference', 'food_preference'
    preference_value = db.Column(db.String(100), nullable=False)

class PartyMember(db.Model):
    party_id = db.Column(db.Integer, db.ForeignKey('party.id'))
    employee_id = db.Column(db.String(50), db.ForeignKey('user.employee_id'))
    is_host = db.Column(db.Boolean, default=False)
```

### 2. 성능 최적화

#### Before (O(N²) 성능)
```python
def generate_recommendation_cache():
    # 모든 사용자에 대해 다른 모든 사용자를 이중으로 순회
    for user in all_users:
        for other_user in all_users:
            if i != j:
                # 점수 계산...
```

#### After (O(N log N) 성능)
```python
def generate_recommendation_cache():
    # 호환성 점수를 미리 계산하여 캐시
    compatibility_cache = {}
    for i, user in enumerate(all_users):
        for j, other_user in enumerate(all_users):
            if i != j:
                score = calculate_compatibility_score_cached(user, other_user)
                compatibility_cache[user.employee_id][other_user.employee_id] = score
```

### 3. 데이터베이스 초기화 최적화

#### Before (매 요청마다 실행)
```python
@app.before_request
def create_tables_and_init_data():
    if not hasattr(app, '_db_initialized'):
        db.create_all()  # 매 요청마다 실행될 수 있음
```

#### After (앱 시작 시 한 번만 실행)
```python
@app.before_first_request
def initialize_database():
    # 앱 시작 시 한 번만 실행
    db.create_all()
    if User.query.count() == 0:
        create_initial_data()
```

## 🛠️ 마이그레이션 단계

### 1단계: 백업 생성
```bash
# 기존 데이터베이스 백업
cp lunch_app/instance/site.db lunch_app/instance/site.db.backup
```

### 2단계: 마이그레이션 스크립트 실행
```bash
python migrate_database.py
```

### 3단계: 앱 재시작
```bash
# 기존 앱 중지 후 재시작
python lunch_app/app.py
```

### 4단계: 데이터 검증
```bash
# 마이그레이션 결과 확인
python -c "
from lunch_app.app import app, db
with app.app_context():
    from lunch_app.app import User, UserPreference, Party, PartyMember
    print(f'Users: {User.query.count()}')
    print(f'User Preferences: {UserPreference.query.count()}')
    print(f'Parties: {Party.query.count()}')
    print(f'Party Members: {PartyMember.query.count()}')
"
```

## 📊 성능 개선 효과

### 데이터베이스 쿼리 성능
- **Before**: `contains()` 문자열 검색 → O(N) 복잡도
- **After**: 인덱스된 외래키 조인 → O(log N) 복잡도

### 추천 알고리즘 성능
- **Before**: O(N²) → 사용자 1000명 기준 30,000,000번 연산
- **After**: O(N log N) → 사용자 1000명 기준 약 10,000번 연산

### 메모리 사용량
- **Before**: 중복 데이터 저장으로 인한 메모리 낭비
- **After**: 정규화된 구조로 메모리 효율성 향상

## 🔧 새로운 API 사용법

### 사용자 선호도 조회
```python
# Before
user.lunch_preference  # 쉼표로 구분된 문자열

# After
preferences = UserPreference.query.filter_by(
    user_id=user.employee_id, 
    preference_type='lunch_preference'
).all()
lunch_prefs = [p.preference_value for p in preferences]
```

### 파티 멤버 조회
```python
# Before
member_ids = party.members_employee_ids.split(',')

# After
party_members = PartyMember.query.filter_by(party_id=party.id).all()
member_ids = [m.employee_id for m in party_members]
```

## ⚠️ 주의사항

### 1. 데이터 무결성
- 마이그레이션 전 반드시 백업 생성
- 마이그레이션 중 앱 중지
- 데이터 검증 후 운영 환경 적용

### 2. 호환성
- 기존 API 엔드포인트는 유지하되 내부 로직만 변경
- 프론트엔드 코드 수정 불필요

### 3. 성능 모니터링
- 마이그레이션 후 성능 지표 모니터링
- `performance_monitor.py` 활용하여 병목 지점 식별

## 🚨 문제 해결

### 마이그레이션 실패 시
```bash
# 백업에서 복원
cp lunch_app/instance/site.db.backup lunch_app/instance/site.db

# 로그 확인
tail -f performance.log
```

### 데이터 불일치 시
```python
# 데이터 검증 스크립트 실행
python -c "
from lunch_app.app import app, db
with app.app_context():
    # 데이터 검증 로직
    validate_data_integrity()
"
```

## 📈 모니터링 및 유지보수

### 1. 성능 모니터링
```python
from performance_monitor import log_performance_report

# 정기적인 성능 리포트 생성
log_performance_report()
```

### 2. 데이터베이스 상태 확인
```sql
-- 인덱스 상태 확인
SELECT * FROM sqlite_master WHERE type='index';

-- 테이블 크기 확인
SELECT name, sql FROM sqlite_master WHERE type='table';
```

### 3. 정기적인 최적화
- 주간 성능 리포트 생성
- 월간 데이터베이스 정리
- 분기별 인덱스 최적화

## 🎯 다음 단계

1. **캐싱 시스템 도입**: Redis를 활용한 고성능 캐싱
2. **데이터베이스 샤딩**: 사용자 수 증가에 대비한 수평 확장
3. **비동기 처리**: Celery를 활용한 백그라운드 작업 처리
4. **마이크로서비스 아키텍처**: 모듈별 독립적인 서비스 분리

---

**마이그레이션 완료 후 반드시 전체 시스템 테스트를 진행하세요!**

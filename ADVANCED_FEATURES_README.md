# 🚀 고급 기능 구현 가이드

이 문서는 런치 앱의 고급 기능들을 구현하고 실행하는 방법을 설명합니다.

## 📋 구현된 고급 기능들

### 1. Redis 캐싱 시스템 🗄️
- **목적**: 응답 시간 단축 및 데이터베이스 부하 감소
- **파일**: `redis_cache.py`
- **주요 기능**:
  - 자동 캐싱/캐시 무효화
  - 사용자별 캐싱
  - 패턴 기반 캐시 정리
  - 성능 통계 모니터링

### 2. Celery 비동기 작업 처리 🔄
- **목적**: 백그라운드에서 무거운 작업 처리
- **파일**: `celery_tasks.py`
- **주요 기능**:
  - 추천 그룹 캐시 생성
  - 사용자 분석 데이터 처리
  - 만료된 데이터 정리
  - 대량 알림 전송
  - 정기 작업 스케줄링

### 3. 데이터베이스 샤딩 시스템 🗃️
- **목적**: 수평 확장성 확보
- **파일**: `database_sharding.py`
- **주요 기능**:
  - 해시 기반 샤드 분산
  - 샤드별 데이터 관리
  - 크로스 샤드 검색
  - 샤드 재균형화

### 4. 마이크로서비스 아키텍처 🏗️
- **목적**: 모듈별 독립적인 서비스 분리
- **디렉토리**: `microservices/`
- **구현된 서비스**:
  - 사용자 관리 서비스 (포트 5001)
  - 파티 관리 서비스 (포트 5002)
  - 추천 시스템 서비스 (포트 5003)

## 🚀 실행 방법

### 1. 환경 설정

#### 필요한 패키지 설치
```bash
pip install -r requirements.txt
```

#### 환경 변수 설정
```bash
# .env 파일 생성
export REDIS_URL=redis://localhost:6379/0
export CELERY_BROKER_URL=redis://localhost:6379/1
export CELERY_RESULT_BACKEND=redis://localhost:6379/2
export SECRET_KEY=your-secret-key-here
```

### 2. Redis 서버 시작
```bash
# Redis 서버 시작
redis-server

# 또는 Docker 사용
docker run -d -p 6379:6379 redis:7-alpine
```

### 3. Celery 워커 시작
```bash
# 터미널 1: Celery 워커
celery -A celery_tasks worker --loglevel=info

# 터미널 2: Celery Beat (정기 작업 스케줄러)
celery -A celery_tasks beat --loglevel=info
```

### 4. 마이크로서비스 시작
```bash
# 터미널 3: 사용자 서비스
python microservices/user_service.py

# 터미널 4: 파티 서비스
python microservices/party_service.py

# 터미널 5: 추천 서비스
python microservices/recommendation_service.py
```

### 5. 메인 애플리케이션 시작
```bash
# 터미널 6: 메인 Flask 앱
python lunch_app/app.py
```

## 🐳 Docker Compose로 한 번에 실행

### 전체 시스템 실행
```bash
# 모든 서비스 시작
docker-compose up -d

# 로그 확인
docker-compose logs -f

# 특정 서비스 로그 확인
docker-compose logs -f main_app
docker-compose logs -f celery_worker
docker-compose logs -f user_service
```

### 서비스별 상태 확인
```bash
# 실행 중인 컨테이너 확인
docker-compose ps

# 서비스 상태 확인
docker-compose exec redis redis-cli ping
docker-compose exec main_app curl http://localhost:5000/health
docker-compose exec user_service curl http://localhost:5001/health
```

## 📊 모니터링 및 관리

### Redis 모니터링
```bash
# Redis CLI 접속
redis-cli

# 통계 정보 확인
INFO

# 메모리 사용량 확인
INFO memory

# 키 개수 확인
DBSIZE
```

### Celery 모니터링
```bash
# 작업 상태 확인
celery -A celery_tasks inspect active

# 워커 상태 확인
celery -A celery_tasks inspect stats

# 정기 작업 확인
celery -A celery_tasks inspect scheduled
```

### 샤딩 시스템 모니터링
```python
from database_sharding import get_shard_stats

# 샤드별 통계 확인
stats = get_shard_stats()
print(f"샤드 통계: {stats}")

# 샤드 재균형화 계획 확인
from database_sharding import sharding_system
rebalance_plan = sharding_system.rebalance_shards()
print(f"재균형화 계획: {rebalance_plan}")
```

## 🔧 API 사용 예시

### Redis 캐싱 사용
```python
from redis_cache import redis_cache, cache_result, cache_user_result

# 직접 캐싱
redis_cache.set("user:profile:123", user_data, expire=3600)
cached_data = redis_cache.get("user:profile:123")

# 데코레이터로 자동 캐싱
@cache_result(expire=1800)
def get_expensive_data():
    # 무거운 계산 작업
    return calculated_data

@cache_user_result(expire=3600)
def get_user_profile(user_id):
    # 사용자별로 캐싱
    return user_profile_data
```

### Celery 작업 실행
```python
from celery_tasks import (
    generate_recommendation_cache_async,
    process_user_analytics_async,
    cleanup_expired_data_async
)

# 비동기 작업 실행
task = generate_recommendation_cache_async.delay()
print(f"작업 ID: {task.id}")

# 작업 상태 확인
from celery_tasks import get_task_status
status = get_task_status(task.id)
print(f"작업 상태: {status}")
```

### 샤딩 시스템 사용
```python
from database_sharding import (
    get_user_shard,
    get_user_data_sharded,
    create_user_sharded,
    search_users_sharded
)

# 사용자 샤드 확인
shard_id = get_user_shard("KOICA001")
print(f"사용자 KOICA001은 샤드 {shard_id}에 위치")

# 샤딩된 시스템에서 사용자 생성
user_data = {
    'employee_id': 'KOICA999',
    'nickname': '새사용자',
    'gender': '남',
    'age_group': '20대',
    'main_dish_genre': '한식,분식'
}
success = create_user_sharded(user_data)

# 크로스 샤드 검색
search_results = search_users_sharded('한식', limit=10)
```

## 🧪 테스트 방법

### Redis 연결 테스트
```bash
python redis_cache.py
```

### Celery 작업 테스트
```bash
python celery_tasks.py
```

### 샤딩 시스템 테스트
```bash
python database_sharding.py
```

### 마이크로서비스 테스트
```bash
# 사용자 서비스 테스트
curl -X POST http://localhost:5001/users \
  -H "Content-Type: application/json" \
  -d '{"employee_id":"TEST001","nickname":"테스트사용자"}'

# 사용자 조회 테스트
curl http://localhost:5001/users/TEST001
```

## 📈 성능 최적화 팁

### 1. Redis 캐싱 최적화
- 적절한 TTL 설정 (너무 짧으면 캐시 미스, 너무 길면 메모리 낭비)
- 패턴 기반 캐시 무효화로 일관성 유지
- 메모리 사용량 모니터링

### 2. Celery 최적화
- 워커 수를 CPU 코어 수에 맞게 조정
- 작업 큐 분리 (우선순위별)
- 작업 타임아웃 설정

### 3. 샤딩 최적화
- 샤드 개수를 데이터 크기에 맞게 조정
- 샤드별 인덱스 최적화
- 정기적인 샤드 재균형화

### 4. 마이크로서비스 최적화
- 서비스 간 통신 최소화
- 적절한 서비스 분리 경계 설정
- 공통 라이브러리 공유

## 🚨 문제 해결

### Redis 연결 실패
```bash
# Redis 서버 상태 확인
redis-cli ping

# 포트 확인
netstat -an | grep 6379

# Redis 로그 확인
tail -f /var/log/redis/redis-server.log
```

### Celery 워커 시작 실패
```bash
# Redis 연결 확인
redis-cli ping

# 환경 변수 확인
echo $CELERY_BROKER_URL

# Celery 설정 확인
celery -A celery_tasks inspect ping
```

### 샤딩 시스템 오류
```python
# 샤드 연결 상태 확인
from database_sharding import sharding_system
for shard_id in range(sharding_system.shard_count):
    try:
        conn = sharding_system.get_shard_connection(shard_id)
        print(f"샤드 {shard_id} 연결 성공")
    except Exception as e:
        print(f"샤드 {shard_id} 연결 실패: {e}")
```

## 🔮 향후 개선 계획

### 1. 고급 캐싱 전략
- Redis Cluster 구현
- 캐시 계층화 (L1: 메모리, L2: Redis, L3: 데이터베이스)
- 지능형 캐시 미스 예측

### 2. 고급 샤딩
- 동적 샤드 추가/제거
- 샤드 간 데이터 마이그레이션
- 샤드별 백업 및 복구

### 3. 서비스 메시
- Istio 또는 Linkerd 도입
- 서비스 디스커버리 자동화
- 서킷 브레이커 패턴 구현

### 4. 모니터링 강화
- APM (Application Performance Monitoring) 도입
- 로그 집계 및 분석
- 알림 시스템 구축

## 📚 참고 자료

- [Redis 공식 문서](https://redis.io/documentation)
- [Celery 공식 문서](https://docs.celeryproject.org/)
- [Flask 마이크로서비스 가이드](https://flask.palletsprojects.com/en/2.3.x/patterns/appfactories/)
- [데이터베이스 샤딩 패턴](https://en.wikipedia.org/wiki/Shard_(database_architecture))
- [Docker Compose 가이드](https://docs.docker.com/compose/)

---

이 가이드를 통해 런치 앱의 고급 기능들을 성공적으로 구현하고 운영할 수 있습니다. 
문제가 발생하거나 추가 도움이 필요하면 개발팀에 문의하세요! 🚀

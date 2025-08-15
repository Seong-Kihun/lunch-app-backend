# 🚀 런치 앱 설치 및 설정 가이드

## 📋 사전 요구사항

- Python 3.8+
- Node.js 16+
- Redis (선택사항)
- SQLite (기본)

## 🔧 1단계: 백엔드 설정

### 1.1 의존성 설치
```bash
cd lunch_app
pip install -r requirements.txt
```

### 1.2 환경변수 설정
```bash
# .env 파일 생성
cp env_example.txt .env

# .env 파일 편집하여 실제 값 입력
nano .env
```

**필수 환경변수:**
```bash
# 보안 설정 (프로덕션에서는 반드시 변경!)
JWT_SECRET_KEY=your-super-secret-jwt-key-change-in-production
SECRET_KEY=your-super-secret-flask-key-change-in-production

# 데이터베이스 설정
DATABASE_URL=sqlite:///site.db

# Redis 설정 (선택사항)
REDIS_URL=redis://localhost:6379/0
CELERY_BROKER_URL=redis://localhost:6379/1
CELERY_RESULT_BACKEND=redis://localhost:6379/2
```

### 1.3 데이터베이스 초기화
```bash
python app.py
```

## 🔧 2단계: 프론트엔드 설정

### 2.1 의존성 설치
```bash
cd lunch_app_frontend
npm install
```

### 2.2 환경 설정
```bash
# config.js에서 서버 URL 확인
export const RENDER_SERVER_URL = __DEV__ 
  ? 'http://172.30.1.40:5000'  # 로컬 개발 서버
  : 'https://lunch-app-backend-ra12.onrender.com';  # 프로덕션 서버
```

### 2.3 앱 실행
```bash
# Expo 개발 서버 시작
npm start

# Android 에뮬레이터에서 실행
npm run android

# iOS 시뮬레이터에서 실행
npm run ios
```

## 🔧 3단계: 고급 기능 설정 (선택사항)

### 3.1 Redis 설정
```bash
# Redis 서버 설치 및 시작
sudo apt-get install redis-server  # Ubuntu/Debian
brew install redis && brew services start redis  # macOS

# 또는 Docker 사용
docker run -d -p 6379:6379 redis:7-alpine
```

### 3.2 Celery 설정
```bash
# Celery 워커 시작
celery -A celery_tasks worker --loglevel=info

# Celery Beat (정기 작업 스케줄러)
celery -A celery_tasks beat --loglevel=info
```

### 3.3 마이크로서비스 실행
```bash
# 사용자 서비스
python microservices/user_service.py

# 파티 서비스
python microservices/party_service.py
```

## 🔧 4단계: Docker로 한 번에 실행

### 4.1 Docker Compose 실행
```bash
docker-compose up -d
```

### 4.2 서비스 상태 확인
```bash
docker-compose ps
docker-compose logs -f
```

## 🔧 5단계: 개발 환경 설정

### 5.1 개발 모드 활성화
```bash
export FLASK_ENV=development
export ENV=development
```

### 5.2 디버그 모드 활성화
```bash
export FLASK_DEBUG=1
```

## 🔧 6단계: 프로덕션 배포

### 6.1 환경변수 설정
```bash
# 프로덕션 환경변수 설정
export FLASK_ENV=production
export JWT_SECRET_KEY=your-production-jwt-secret
export SECRET_KEY=your-production-flask-secret
```

### 6.2 보안 확인사항
- [ ] JWT_SECRET_KEY가 기본값이 아님
- [ ] SECRET_KEY가 기본값이 아님
- [ ] 데이터베이스 연결 문자열이 안전함
- [ ] HTTPS가 활성화됨

## 🔧 7단계: 문제 해결

### 7.1 일반적인 문제들

#### 인증 시스템 오류
```bash
# 로그 확인
tail -f app.log

# 데이터베이스 연결 확인
python -c "from app import db; print('DB 연결 성공')"
```

#### 프론트엔드 연결 오류
```bash
# 백엔드 서버 상태 확인
curl http://localhost:5000/health

# CORS 설정 확인
curl -H "Origin: http://localhost:3000" http://localhost:5000/health
```

### 7.2 로그 확인
```bash
# 백엔드 로그
tail -f lunch_app/app.log

# 프론트엔드 로그 (Expo)
expo logs
```

## 🔧 8단계: 성능 최적화

### 8.1 데이터베이스 인덱스
```sql
-- 자주 사용되는 쿼리에 인덱스 추가
CREATE INDEX idx_user_employee_id ON users(employee_id);
CREATE INDEX idx_party_date ON parties(party_date);
CREATE INDEX idx_party_member ON party_members(party_id, employee_id);
```

### 8.2 캐시 설정
```bash
# Redis 캐시 활성화
export REDIS_CACHE_ENABLED=true
export REDIS_CACHE_TTL=3600
```

## 📞 지원 및 문의

문제가 발생하거나 추가 도움이 필요한 경우:
1. 로그 파일 확인
2. 환경변수 설정 확인
3. 의존성 버전 호환성 확인
4. GitHub Issues에 문제 보고

## 🔒 보안 주의사항

- **절대** 기본 보안 키를 프로덕션에서 사용하지 마세요
- 환경변수 파일(.env)을 버전 관리에 포함하지 마세요
- 정기적으로 보안 키를 변경하세요
- 프로덕션 환경에서는 HTTPS를 사용하세요

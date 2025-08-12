#!/usr/bin/env python3
"""
Celery 비동기 작업 처리 시스템
백그라운드에서 무거운 작업을 처리하여 응답 시간 단축
"""

from celery import Celery
from celery.schedules import crontab
from datetime import datetime, timedelta
import logging
from typing import List, Dict, Any
import time

# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Celery 앱 초기화
celery_app = Celery(
    'lunch_app',
    broker='redis://localhost:6379/1',
    backend='redis://localhost:6379/2',
    include=['celery_tasks']
)

# Celery 설정
celery_app.conf.update(
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='Asia/Seoul',
    enable_utc=True,
    task_track_started=True,
    task_time_limit=30 * 60,  # 30분
    task_soft_time_limit=25 * 60,  # 25분
    worker_prefetch_multiplier=1,
    worker_max_tasks_per_child=1000,
)

# 작업 상태 추적
@celery_app.task(bind=True)
def generate_recommendation_cache_async(self, user_id: str = None):
    """비동기로 추천 그룹 캐시 생성"""
    try:
        logger.info(f"추천 그룹 캐시 생성 시작 - 사용자: {user_id}")
        
        # 작업 진행률 업데이트
        self.update_state(
            state='PROGRESS',
            meta={'current': 0, 'total': 100, 'status': '캐시 생성 중...'}
        )
        
        # 실제 캐시 생성 로직 (기존 함수 호출)
        from lunch_app.app import generate_recommendation_cache
        generate_recommendation_cache()
        
        # 작업 완료
        self.update_state(
            state='SUCCESS',
            meta={'current': 100, 'total': 100, 'status': '캐시 생성 완료'}
        )
        
        logger.info(f"추천 그룹 캐시 생성 완료 - 사용자: {user_id}")
        return {'status': 'success', 'message': '캐시 생성 완료'}
        
    except Exception as e:
        logger.error(f"추천 그룹 캐시 생성 실패: {e}")
        self.update_state(
            state='FAILURE',
            meta={'error': str(e)}
        )
        raise

@celery_app.task(bind=True)
def process_user_analytics_async(self, user_id: str):
    """비동기로 사용자 분석 데이터 처리"""
    try:
        logger.info(f"사용자 분석 데이터 처리 시작: {user_id}")
        
        # 작업 진행률 업데이트
        self.update_state(
            state='PROGRESS',
            meta={'current': 0, 'total': 100, 'status': '분석 데이터 처리 중...'}
        )
        
        # 사용자 활동 분석
        from lunch_app.app import db, User, Party, PartyMember, Review
        
        # 파티 참여 통계
        party_count = PartyMember.query.filter_by(employee_id=user_id).count()
        self.update_state(
            state='PROGRESS',
            meta={'current': 30, 'total': 100, 'status': '파티 통계 분석 중...'}
        )
        
        # 리뷰 작성 통계
        review_count = Review.query.filter_by(user_id=user_id).count()
        self.update_state(
            state='PROGRESS',
            meta={'current': 60, 'total': 100, 'status': '리뷰 통계 분석 중...'}
        )
        
        # 선호도 분석
        from lunch_app.app import UserPreference
        preferences = UserPreference.query.filter_by(user_id=user_id).all()
        preference_data = {}
        for pref in preferences:
            if pref.preference_type not in preference_data:
                preference_data[pref.preference_type] = []
            preference_data[pref.preference_type].append(pref.preference_value)
        
        self.update_state(
            state='PROGRESS',
            meta={'current': 90, 'total': 100, 'status': '선호도 분석 중...'}
        )
        
        # 분석 결과를 Redis에 캐싱
        from redis_cache import redis_cache
        analytics_key = f"analytics:user:{user_id}:{datetime.now().strftime('%Y-%m-%d')}"
        analytics_data = {
            'party_count': party_count,
            'review_count': review_count,
            'preferences': preference_data,
            'last_updated': datetime.now().isoformat()
        }
        redis_cache.set(analytics_key, analytics_data, expire=86400)  # 24시간
        
        # 작업 완료
        self.update_state(
            state='SUCCESS',
            meta={'current': 100, 'total': 100, 'status': '분석 완료'}
        )
        
        logger.info(f"사용자 분석 데이터 처리 완료: {user_id}")
        return analytics_data
        
    except Exception as e:
        logger.error(f"사용자 분석 데이터 처리 실패: {e}")
        self.update_state(
            state='FAILURE',
            meta={'error': str(e)}
        )
        raise

@celery_app.task(bind=True)
def cleanup_expired_data_async(self):
    """비동기로 만료된 데이터 정리"""
    try:
        logger.info("만료된 데이터 정리 시작")
        
        # 작업 진행률 업데이트
        self.update_state(
            state='PROGRESS',
            meta={'current': 0, 'total': 100, 'status': '데이터 정리 중...'}
        )
        
        from lunch_app.app import db, Party, ChatRoom, Notification
        
        # 만료된 파티 정리 (7일 이상 된 파티)
        expired_date = datetime.now() - timedelta(days=7)
        expired_parties = Party.query.filter(
            Party.party_date < expired_date.strftime('%Y-%m-%d')
        ).all()
        
        expired_party_count = len(expired_parties)
        for party in expired_parties:
            db.session.delete(party)
        
        self.update_state(
            state='PROGRESS',
            meta={'current': 30, 'total': 100, 'status': f'만료된 파티 {expired_party_count}개 정리 중...'}
        )
        
        # 만료된 알림 정리 (30일 이상 된 알림)
        expired_notification_date = datetime.now() - timedelta(days=30)
        expired_notifications = Notification.query.filter(
            Notification.created_at < expired_notification_date
        ).all()
        
        expired_notification_count = len(expired_notifications)
        for notification in expired_notifications:
            db.session.delete(notification)
        
        self.update_state(
            state='PROGRESS',
            meta={'current': 60, 'total': 100, 'status': f'만료된 알림 {expired_notification_count}개 정리 중...'}
        )
        
        # Redis 캐시 정리
        from redis_cache import redis_cache
        if redis_cache.is_connected():
            # 7일 이상 된 캐시 키 정리
            expired_patterns = [
                "recommendation:*",
                "analytics:*",
                "party:*"
            ]
            
            total_cleared = 0
            for pattern in expired_patterns:
                cleared = redis_cache.clear_pattern(pattern)
                total_cleared += cleared
            
            logger.info(f"Redis 캐시 정리 완료: {total_cleared}개 키 삭제")
        
        self.update_state(
            state='PROGRESS',
            meta={'current': 90, 'total': 100, 'status': '캐시 정리 중...'}
        )
        
        # 변경사항 커밋
        db.session.commit()
        
        # 작업 완료
        self.update_state(
            state='SUCCESS',
            meta={'current': 100, 'total': 100, 'status': '정리 완료'}
        )
        
        cleanup_summary = {
            'expired_parties': expired_party_count,
            'expired_notifications': expired_notification_count,
            'total_cleared': expired_party_count + expired_notification_count
        }
        
        logger.info(f"만료된 데이터 정리 완료: {cleanup_summary}")
        return cleanup_summary
        
    except Exception as e:
        logger.error(f"만료된 데이터 정리 실패: {e}")
        self.update_state(
            state='FAILURE',
            meta={'error': str(e)}
        )
        raise

@celery_app.task(bind=True)
def send_bulk_notifications_async(self, user_ids: List[str], notification_data: Dict[str, Any]):
    """비동기로 대량 알림 전송"""
    try:
        logger.info(f"대량 알림 전송 시작: {len(user_ids)}명")
        
        # 작업 진행률 업데이트
        self.update_state(
            state='PROGRESS',
            meta={'current': 0, 'total': len(user_ids), 'status': '알림 전송 중...'}
        )
        
        from lunch_app.app import db, Notification
        
        success_count = 0
        failed_count = 0
        
        for i, user_id in enumerate(user_ids):
            try:
                # 알림 생성
                notification = Notification(
                    user_id=user_id,
                    notification_type=notification_data.get('type', 'general'),
                    title=notification_data.get('title', '알림'),
                    message=notification_data.get('message', '새로운 알림이 있습니다.'),
                    related_id=notification_data.get('related_id'),
                    related_type=notification_data.get('related_type')
                )
                db.session.add(notification)
                success_count += 1
                
            except Exception as e:
                logger.error(f"사용자 {user_id} 알림 생성 실패: {e}")
                failed_count += 1
            
            # 진행률 업데이트
            if i % 10 == 0:  # 10명마다 진행률 업데이트
                self.update_state(
                    state='PROGRESS',
                    meta={
                        'current': i + 1,
                        'total': len(user_ids),
                        'status': f'알림 전송 중... ({i + 1}/{len(user_ids)})'
                    }
                )
        
        # 변경사항 커밋
        db.session.commit()
        
        # 작업 완료
        self.update_state(
            state='SUCCESS',
            meta={'current': len(user_ids), 'total': len(user_ids), 'status': '알림 전송 완료'}
        )
        
        result = {
            'total_users': len(user_ids),
            'success_count': success_count,
            'failed_count': failed_count,
            'success_rate': (success_count / len(user_ids)) * 100 if user_ids else 0
        }
        
        logger.info(f"대량 알림 전송 완료: {result}")
        return result
        
    except Exception as e:
        logger.error(f"대량 알림 전송 실패: {e}")
        self.update_state(
            state='FAILURE',
            meta={'error': str(e)}
        )
        raise

# 정기 작업 스케줄링
@celery_app.on_after_configure.connect
def setup_periodic_tasks(sender, **kwargs):
    """정기 작업 스케줄 설정"""
    
    # 매일 자정에 추천 그룹 캐시 생성
    sender.add_periodic_task(
        crontab(hour=0, minute=0),
        generate_recommendation_cache_async.s(),
        name='daily-recommendation-cache'
    )
    
    # 매주 일요일 새벽 2시에 만료된 데이터 정리
    sender.add_periodic_task(
        crontab(day_of_week=0, hour=2, minute=0),
        cleanup_expired_data_async.s(),
        name='weekly-data-cleanup'
    )
    
    # 매일 오후 6시에 사용자 활동 분석
    sender.add_periodic_task(
        crontab(hour=18, minute=0),
        process_user_analytics_async.s('all'),
        name='daily-user-analytics'
    )

# 작업 상태 조회 헬퍼 함수
def get_task_status(task_id: str) -> Dict[str, Any]:
    """작업 상태 조회"""
    try:
        task_result = celery_app.AsyncResult(task_id)
        return {
            'task_id': task_id,
            'status': task_result.status,
            'result': task_result.result,
            'info': task_result.info
        }
    except Exception as e:
        logger.error(f"작업 상태 조회 실패: {e}")
        return {'error': str(e)}

def cancel_task(task_id: str) -> bool:
    """작업 취소"""
    try:
        celery_app.control.revoke(task_id, terminate=True)
        return True
    except Exception as e:
        logger.error(f"작업 취소 실패: {e}")
        return False

# 작업 모니터링
def get_active_tasks() -> List[Dict[str, Any]]:
    """활성 작업 목록 조회"""
    try:
        active_tasks = celery_app.control.inspect().active()
        if not active_tasks:
            return []
        
        tasks = []
        for worker, worker_tasks in active_tasks.items():
            for task in worker_tasks:
                tasks.append({
                    'worker': worker,
                    'task_id': task['id'],
                    'name': task['name'],
                    'args': task['args'],
                    'kwargs': task['kwargs'],
                    'time_start': task['time_start']
                })
        return tasks
    except Exception as e:
        logger.error(f"활성 작업 조회 실패: {e}")
        return []

def get_worker_stats() -> Dict[str, Any]:
    """워커 통계 정보 조회"""
    try:
        stats = celery_app.control.inspect().stats()
        if not stats:
            return {}
        
        total_stats = {
            'total_workers': len(stats),
            'total_tasks_processed': 0,
            'total_tasks_active': 0,
            'total_tasks_reserved': 0
        }
        
        for worker, worker_stats in stats.items():
            total_stats['total_tasks_processed'] += worker_stats.get('total', {}).get('total', 0)
            total_stats['total_tasks_active'] += len(worker_stats.get('active', []))
            total_stats['total_tasks_reserved'] += len(worker_stats.get('reserved', []))
        
        return total_stats
    except Exception as e:
        logger.error(f"워커 통계 조회 실패: {e}")
        return {}

# 사용 예시
if __name__ == "__main__":
    # Celery 워커 시작 (별도 터미널에서 실행)
    print("Celery 워커를 시작하려면 다음 명령어를 실행하세요:")
    print("celery -A celery_tasks worker --loglevel=info")
    
    # 정기 작업 스케줄러 시작 (별도 터미널에서 실행)
    print("정기 작업 스케줄러를 시작하려면 다음 명령어를 실행하세요:")
    print("celery -A celery_tasks beat --loglevel=info")
    
    # 테스트 작업 실행
    print("\n테스트 작업 실행 중...")
    
    # 추천 그룹 캐시 생성 작업
    task = generate_recommendation_cache_async.delay()
    print(f"추천 그룹 캐시 생성 작업 시작: {task.id}")
    
    # 작업 상태 확인
    import time
    time.sleep(2)
    status = get_task_status(task.id)
    print(f"작업 상태: {status}")

#!/usr/bin/env python3
"""
Redis 캐싱 시스템
고성능 캐싱을 통한 응답 시간 단축
"""

import redis
import json
import pickle
import hashlib
from datetime import datetime, timedelta
from typing import Any, Optional, Union
import logging

logger = logging.getLogger(__name__)

class RedisCache:
    """Redis 캐싱 클래스"""
    
    def __init__(self, host='localhost', port=6379, db=0, password=None, decode_responses=False):
        """Redis 연결 초기화"""
        try:
            self.redis_client = redis.Redis(
                host=host,
                port=port,
                db=db,
                password=password,
                decode_responses=decode_responses,
                socket_connect_timeout=5,
                socket_timeout=5,
                retry_on_timeout=True
            )
            # 연결 테스트
            self.redis_client.ping()
            logger.info(f"Redis 연결 성공: {host}:{port}")
        except Exception as e:
            logger.error(f"Redis 연결 실패: {e}")
            self.redis_client = None
    
    def is_connected(self) -> bool:
        """Redis 연결 상태 확인"""
        if not self.redis_client:
            return False
        try:
            self.redis_client.ping()
            return True
        except:
            return False
    
    def set(self, key: str, value: Any, expire: Optional[int] = None) -> bool:
        """캐시에 데이터 저장"""
        if not self.is_connected():
            return False
        
        try:
            # 복잡한 객체는 pickle로 직렬화
            if isinstance(value, (dict, list, tuple, set)):
                serialized_value = pickle.dumps(value)
            else:
                serialized_value = str(value).encode('utf-8')
            
            if expire:
                return self.redis_client.setex(key, expire, serialized_value)
            else:
                return self.redis_client.set(key, serialized_value)
        except Exception as e:
            logger.error(f"캐시 저장 실패 - key: {key}, error: {e}")
            return False
    
    def get(self, key: str, default: Any = None) -> Any:
        """캐시에서 데이터 조회"""
        if not self.is_connected():
            return default
        
        try:
            value = self.redis_client.get(key)
            if value is None:
                return default
            
            # pickle로 직렬화된 데이터 복원 시도
            try:
                return pickle.loads(value)
            except:
                # 일반 문자열로 처리
                return value.decode('utf-8') if isinstance(value, bytes) else value
        except Exception as e:
            logger.error(f"캐시 조회 실패 - key: {key}, error: {e}")
            return default
    
    def delete(self, key: str) -> bool:
        """캐시에서 데이터 삭제"""
        if not self.is_connected():
            return False
        
        try:
            return bool(self.redis_client.delete(key))
        except Exception as e:
            logger.error(f"캐시 삭제 실패 - key: {key}, error: {e}")
            return False
    
    def exists(self, key: str) -> bool:
        """키 존재 여부 확인"""
        if not self.is_connected():
            return False
        
        try:
            return bool(self.redis_client.exists(key))
        except Exception as e:
            logger.error(f"키 존재 확인 실패 - key: {key}, error: {e}")
            return False
    
    def expire(self, key: str, seconds: int) -> bool:
        """키 만료 시간 설정"""
        if not self.is_connected():
            return False
        
        try:
            return bool(self.redis_client.expire(key, seconds))
        except Exception as e:
            logger.error(f"만료 시간 설정 실패 - key: {key}, error: {e}")
            return False
    
    def ttl(self, key: str) -> int:
        """키의 남은 만료 시간 조회 (초)"""
        if not self.is_connected():
            return -1
        
        try:
            return self.redis_client.ttl(key)
        except Exception as e:
            logger.error(f"TTL 조회 실패 - key: {key}, error: {e}")
            return -1
    
    def clear_pattern(self, pattern: str) -> int:
        """패턴에 맞는 키들을 일괄 삭제"""
        if not self.is_connected():
            return 0
        
        try:
            keys = self.redis_client.keys(pattern)
            if keys:
                return self.redis_client.delete(*keys)
            return 0
        except Exception as e:
            logger.error(f"패턴 삭제 실패 - pattern: {pattern}, error: {e}")
            return 0
    
    def get_or_set(self, key: str, callback: callable, expire: Optional[int] = None) -> Any:
        """캐시에서 조회하고 없으면 콜백 실행하여 저장"""
        if not self.is_connected():
            return callback()
        
        # 캐시에서 조회
        cached_value = self.get(key)
        if cached_value is not None:
            logger.debug(f"캐시 히트: {key}")
            return cached_value
        
        # 콜백 실행하여 값 생성
        logger.debug(f"캐시 미스: {key}")
        value = callback()
        
        # 캐시에 저장
        if value is not None:
            self.set(key, value, expire)
        
        return value
    
    def invalidate_user_cache(self, user_id: str) -> bool:
        """사용자 관련 캐시 무효화"""
        patterns = [
            f"user:{user_id}:*",
            f"party:*:user:{user_id}:*",
            f"recommendation:*:user:{user_id}:*",
            f"preference:*:user:{user_id}:*"
        ]
        
        total_deleted = 0
        for pattern in patterns:
            deleted = self.clear_pattern(pattern)
            total_deleted += deleted
        
        logger.info(f"사용자 {user_id} 캐시 무효화 완료: {total_deleted}개 키 삭제")
        return total_deleted > 0
    
    def get_stats(self) -> dict:
        """Redis 통계 정보 조회"""
        if not self.is_connected():
            return {}
        
        try:
            info = self.redis_client.info()
            return {
                'connected_clients': info.get('connected_clients', 0),
                'used_memory_human': info.get('used_memory_human', '0B'),
                'total_commands_processed': info.get('total_commands_processed', 0),
                'keyspace_hits': info.get('keyspace_hits', 0),
                'keyspace_misses': info.get('keyspace_misses', 0),
                'uptime_in_seconds': info.get('uptime_in_seconds', 0)
            }
        except Exception as e:
            logger.error(f"통계 정보 조회 실패: {e}")
            return {}

# 전역 Redis 캐시 인스턴스
redis_cache = RedisCache()

# 캐싱 데코레이터
def cache_result(expire: int = 3600, key_prefix: str = ""):
    """함수 결과를 캐싱하는 데코레이터"""
    def decorator(func):
        def wrapper(*args, **kwargs):
            if not redis_cache.is_connected():
                return func(*args, **kwargs)
            
            # 캐시 키 생성
            func_name = func.__name__
            args_str = str(args) + str(sorted(kwargs.items()))
            cache_key = f"{key_prefix}:{func_name}:{hashlib.md5(args_str.encode()).hexdigest()}"
            
            # 캐시에서 조회
            cached_result = redis_cache.get(cache_key)
            if cached_result is not None:
                return cached_result
            
            # 함수 실행
            result = func(*args, **kwargs)
            
            # 결과 캐싱
            if result is not None:
                redis_cache.set(cache_key, result, expire)
            
            return result
        return wrapper
    return decorator

# 사용자별 캐싱 데코레이터
def cache_user_result(expire: int = 3600, key_prefix: str = ""):
    """사용자별로 결과를 캐싱하는 데코레이터"""
    def decorator(func):
        def wrapper(*args, **kwargs):
            if not redis_cache.is_connected():
                return func(*args, **kwargs)
            
            # 첫 번째 인자가 user_id인지 확인
            user_id = None
            if args and isinstance(args[0], str):
                user_id = args[0]
            elif 'user_id' in kwargs:
                user_id = kwargs['user_id']
            elif 'employee_id' in kwargs:
                user_id = kwargs['employee_id']
            
            if not user_id:
                return func(*args, **kwargs)
            
            # 캐시 키 생성
            func_name = func.__name__
            args_str = str(args) + str(sorted(kwargs.items()))
            cache_key = f"{key_prefix}:{func_name}:user:{user_id}:{hashlib.md5(args_str.encode()).hexdigest()}"
            
            # 캐시에서 조회
            cached_result = redis_cache.get(cache_key)
            if cached_result is not None:
                return cached_result
            
            # 함수 실행
            result = func(*args, **kwargs)
            
            # 결과 캐싱
            if result is not None:
                redis_cache.set(cache_key, result, expire)
            
            return result
        return wrapper
    return decorator

# 캐시 무효화 헬퍼 함수
def invalidate_cache_pattern(pattern: str) -> int:
    """패턴에 맞는 캐시 무효화"""
    return redis_cache.clear_pattern(pattern)

def invalidate_user_cache(user_id: str) -> bool:
    """사용자 관련 캐시 무효화"""
    return redis_cache.invalidate_user_cache(user_id)

# 사용 예시
if __name__ == "__main__":
    # Redis 연결 테스트
    if redis_cache.is_connected():
        print("✅ Redis 연결 성공")
        
        # 기본 캐싱 테스트
        redis_cache.set("test:key", "test_value", 60)
        value = redis_cache.get("test:key")
        print(f"캐시 테스트: {value}")
        
        # 통계 정보 조회
        stats = redis_cache.get_stats()
        print(f"Redis 통계: {stats}")
    else:
        print("❌ Redis 연결 실패")

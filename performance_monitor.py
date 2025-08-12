#!/usr/bin/env python3
"""
성능 모니터링 및 로깅 시스템
앱의 성능을 추적하고 병목 지점을 식별
"""

import time
import logging
import functools
from datetime import datetime
from collections import defaultdict, deque
import threading

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('performance.log'),
        logging.StreamHandler()
    ]
)

class PerformanceMonitor:
    """성능 모니터링 클래스"""
    
    def __init__(self):
        self.metrics = defaultdict(lambda: {
            'count': 0,
            'total_time': 0.0,
            'min_time': float('inf'),
            'max_time': 0.0,
            'recent_times': deque(maxlen=100)
        })
        self.lock = threading.Lock()
        
    def monitor(self, operation_name):
        """함수 성능 모니터링 데코레이터"""
        def decorator(func):
            @functools.wraps(func)
            def wrapper(*args, **kwargs):
                start_time = time.time()
                try:
                    result = func(*args, **kwargs)
                    return result
                finally:
                    execution_time = time.time() - start_time
                    self.record_metric(operation_name, execution_time)
            return wrapper
        return decorator
    
    def record_metric(self, operation_name, execution_time):
        """성능 메트릭 기록"""
        with self.lock:
            metric = self.metrics[operation_name]
            metric['count'] += 1
            metric['total_time'] += execution_time
            metric['min_time'] = min(metric['min_time'], execution_time)
            metric['max_time'] = max(metric['max_time'], execution_time)
            metric['recent_times'].append(execution_time)
    
    def get_metrics(self, operation_name=None):
        """성능 메트릭 조회"""
        with self.lock:
            if operation_name:
                if operation_name in self.metrics:
                    metric = self.metrics[operation_name]
                    return {
                        'operation': operation_name,
                        'count': metric['count'],
                        'avg_time': metric['total_time'] / metric['count'] if metric['count'] > 0 else 0,
                        'min_time': metric['min_time'] if metric['min_time'] != float('inf') else 0,
                        'max_time': metric['max_time'],
                        'recent_avg': sum(metric['recent_times']) / len(metric['recent_times']) if metric['recent_times'] else 0
                    }
                return None
            else:
                return {name: self.get_metrics(name) for name in self.metrics.keys()}
    
    def get_slow_operations(self, threshold=1.0):
        """느린 작업 식별 (threshold 초 이상)"""
        slow_ops = []
        with self.lock:
            for op_name, metric in self.metrics.items():
                if metric['recent_times']:
                    recent_avg = sum(metric['recent_times']) / len(metric['recent_times'])
                    if recent_avg > threshold:
                        slow_ops.append({
                            'operation': op_name,
                            'recent_avg': recent_avg,
                            'count': metric['count']
                        })
        
        return sorted(slow_ops, key=lambda x: x['recent_avg'], reverse=True)
    
    def generate_report(self):
        """성능 리포트 생성"""
        report = {
            'timestamp': datetime.now().isoformat(),
            'summary': {},
            'slow_operations': self.get_slow_operations(),
            'detailed_metrics': self.get_metrics()
        }
        
        # 전체 요약 통계
        total_operations = sum(metric['count'] for metric in self.metrics.values())
        total_time = sum(metric['total_time'] for metric in self.metrics.values())
        
        report['summary'] = {
            'total_operations': total_operations,
            'total_time': total_time,
            'overall_avg_time': total_time / total_operations if total_operations > 0 else 0,
            'unique_operations': len(self.metrics)
        }
        
        return report
    
    def log_performance_report(self):
        """성능 리포트를 로그에 기록"""
        report = self.generate_report()
        
        logging.info("=== 성능 모니터링 리포트 ===")
        logging.info(f"전체 작업 수: {report['summary']['total_operations']}")
        logging.info(f"전체 실행 시간: {report['summary']['total_time']:.2f}초")
        logging.info(f"전체 평균 실행 시간: {report['summary']['overall_avg_time']:.4f}초")
        logging.info(f"고유 작업 수: {report['summary']['unique_operations']}")
        
        if report['slow_operations']:
            logging.warning("=== 느린 작업 목록 ===")
            for op in report['slow_operations']:
                logging.warning(f"{op['operation']}: {op['recent_avg']:.4f}초 (총 {op['count']}회)")
        else:
            logging.info("느린 작업이 없습니다.")
        
        logging.info("=== 상세 메트릭 ===")
        for op_name, metric in report['detailed_metrics'].items():
            if metric:
                logging.info(f"{op_name}: {metric['avg_time']:.4f}초 (최소: {metric['min_time']:.4f}, 최대: {metric['max_time']:.4f})")

# 전역 성능 모니터 인스턴스
performance_monitor = PerformanceMonitor()

# 편의 함수들
def monitor_performance(operation_name):
    """성능 모니터링 데코레이터"""
    return performance_monitor.monitor(operation_name)

def get_performance_metrics(operation_name=None):
    """성능 메트릭 조회"""
    return performance_monitor.get_metrics(operation_name)

def get_slow_operations(threshold=1.0):
    """느린 작업 식별"""
    return performance_monitor.get_slow_operations(threshold)

def generate_performance_report():
    """성능 리포트 생성"""
    return performance_monitor.generate_report()

def log_performance_report():
    """성능 리포트를 로그에 기록"""
    performance_monitor.log_performance_report()

# 데이터베이스 쿼리 성능 모니터링
class DatabaseQueryMonitor:
    """데이터베이스 쿼리 성능 모니터링"""
    
    def __init__(self):
        self.query_metrics = defaultdict(lambda: {
            'count': 0,
            'total_time': 0.0,
            'slow_queries': deque(maxlen=50)
        })
        self.lock = threading.Lock()
    
    def monitor_query(self, query_type, query_string=None):
        """쿼리 성능 모니터링 데코레이터"""
        def decorator(func):
            @functools.wraps(func)
            def wrapper(*args, **kwargs):
                start_time = time.time()
                try:
                    result = func(*args, **kwargs)
                    return result
                finally:
                    execution_time = time.time() - start_time
                    self.record_query_metric(query_type, execution_time, query_string)
            return wrapper
        return decorator
    
    def record_query_metric(self, query_type, execution_time, query_string=None):
        """쿼리 메트릭 기록"""
        with self.lock:
            metric = self.query_metrics[query_type]
            metric['count'] += 1
            metric['total_time'] += execution_time
            
            # 느린 쿼리 기록 (1초 이상)
            if execution_time > 1.0:
                slow_query = {
                    'query_type': query_type,
                    'execution_time': execution_time,
                    'timestamp': datetime.now().isoformat(),
                    'query_string': query_string
                }
                metric['slow_queries'].append(slow_query)
    
    def get_query_metrics(self):
        """쿼리 메트릭 조회"""
        with self.lock:
            return dict(self.query_metrics)
    
    def get_slow_queries(self, threshold=1.0):
        """느린 쿼리 목록 조회"""
        slow_queries = []
        with self.lock:
            for query_type, metric in self.query_metrics.items():
                for slow_query in metric['slow_queries']:
                    if slow_query['execution_time'] > threshold:
                        slow_queries.append(slow_query)
        
        return sorted(slow_queries, key=lambda x: x['execution_time'], reverse=True)

# 전역 쿼리 모니터 인스턴스
query_monitor = DatabaseQueryMonitor()

def monitor_database_query(query_type, query_string=None):
    """데이터베이스 쿼리 성능 모니터링 데코레이터"""
    return query_monitor.monitor_query(query_type, query_string)

# 사용 예시
if __name__ == "__main__":
    # 성능 모니터링 테스트
    @monitor_performance("test_operation")
    def test_function():
        time.sleep(0.1)
        return "test"
    
    # 여러 번 실행
    for _ in range(10):
        test_function()
    
    # 성능 리포트 생성
    log_performance_report()

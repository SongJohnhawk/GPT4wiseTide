#!/usr/bin/env python3
"""
Memory Management Integration Example
실제 tideWise 프로그램에서 메모리 관리 시스템을 사용하는 예제
"""

# 메모리 관리 시스템 사용 예제

def example_usage_in_main_program():
    """메인 프로그램에서의 사용 예제"""
    
    # 1. 프로그램 시작시 - 메모리 추적기 생성
    from support.memory_utils import get_memory_tracker, print_memory_status
    
    print("=== tideWise 메모리 관리 시스템 통합 예제 ===")
    
    # 메모리 추적기 생성 (모듈별로)
    stock_tracker = get_memory_tracker('stock_data')
    api_tracker = get_memory_tracker('api_responses')
    algorithm_tracker = get_memory_tracker('algorithms')
    
    print("메모리 추적기 생성 완료")
    
    # 2. 데이터 수집시 - 캐시 등록
    def collect_stock_data():
        """주식 데이터 수집 예제"""
        stock_data_cache = {}
        price_cache = []
        
        # 캐시를 메모리 관리 시스템에 등록
        stock_tracker.add_cache('stock_data', stock_data_cache)
        stock_tracker.add_cache('price_history', price_cache)
        
        print("주식 데이터 캐시 등록 완료")
        return stock_data_cache, price_cache
    
    # 3. API 호출시 - 응답 캐시 등록
    def api_call_example():
        """API 호출 예제"""
        api_response_cache = {}
        
        # API 응답을 캐시로 등록
        api_tracker.add_cache('responses', api_response_cache)
        
        print("API 응답 캐시 등록 완료")
        return api_response_cache
    
    # 4. 알고리즘 실행시 - 계산 결과 캐시
    def algorithm_example():
        """알고리즘 실행 예제"""
        calculation_cache = {}
        indicator_cache = {}
        
        # 계산 결과 캐시 등록
        algorithm_tracker.add_cache('calculations', calculation_cache)
        algorithm_tracker.add_cache('indicators', indicator_cache)
        
        print("알고리즘 캐시 등록 완료")
        return calculation_cache, indicator_cache
    
    # 실제 사용 시뮬레이션
    stock_data, price_data = collect_stock_data()
    api_cache = api_call_example()
    calc_cache, indicator_cache = algorithm_example()
    
    # 현재 메모리 상태 확인
    print("\n=== 현재 메모리 상태 ===")
    print_memory_status()
    
    # 수동 메모리 정리 (필요시)
    from support.memory_utils import force_cleanup
    print("\n=== 수동 메모리 정리 테스트 ===")
    result = force_cleanup()
    if result and result.get('success'):
        print(f"메모리 정리 완료: {result.get('freed_memory_mb', 0):.1f}MB 해제")
    
    print("\n백그라운드에서 30분마다 자동 메모리 정리가 실행됩니다.")

def example_integration_with_existing_code():
    """기존 코드와의 통합 예제"""
    
    print("\n=== 기존 코드 통합 예제 ===")
    
    # 기존 코드 스타일
    class StockDataCollector:
        def __init__(self):
            self.data_cache = {}
            self.price_history = []
            
            # 메모리 관리 시스템과 연동
            from support.memory_utils import register_cache
            register_cache(self.data_cache, 'StockDataCollector_data')
            register_cache(self.price_history, 'StockDataCollector_history')
            
            print("StockDataCollector 메모리 관리 연동 완료")
        
        def collect_data(self):
            # 실제 데이터 수집 로직
            self.data_cache['sample'] = list(range(100))
            self.price_history.extend(list(range(50, 150)))
            print("데이터 수집 완료")
        
        def cleanup_old_data(self):
            """수동으로 오래된 데이터 정리"""
            from support.memory_utils import get_memory_tracker
            tracker = get_memory_tracker('stock_collector')
            tracker.clear_all_caches()
            print("오래된 데이터 정리 완료")
    
    # 사용 예제
    collector = StockDataCollector()
    collector.collect_data()
    
    # 메모리 사용량 체크 후 정리
    from support.memory_utils import cleanup_if_needed
    cleanup_if_needed(threshold_mb=50.0)  # 50MB 이상이면 정리
    
    print("기존 코드 통합 완료")

def example_decorator_usage():
    """데코레이터 사용 예제"""
    
    print("\n=== 데코레이터 사용 예제 ===")
    
    from support.memory_utils import auto_cache
    
    @auto_cache('fibonacci_cache')
    def calculate_fibonacci(n):
        """피보나치 수열 계산 (결과가 자동으로 캐시 등록됨)"""
        if n <= 1:
            return [0, 1][:n+1]
        
        result = [0, 1]
        for i in range(2, n + 1):
            result.append(result[i-1] + result[i-2])
        
        return result
    
    # 함수 실행시 결과가 자동으로 메모리 관리 시스템에 등록됨
    fib_result = calculate_fibonacci(20)
    print(f"피보나치 수열 계산 완료: 길이 {len(fib_result)}")
    
    print("데코레이터 사용 완료")

def show_monitoring_commands():
    """모니터링 명령어 예제"""
    
    print("\n=== 모니터링 및 관리 명령어 ===")
    
    commands = """
    # 현재 메모리 상태 확인
    from support.memory_utils import print_memory_status
    print_memory_status()
    
    # 즉시 메모리 정리
    from support.memory_utils import force_cleanup
    force_cleanup()
    
    # 메모리 사용량이 높을 때 자동 정리
    from support.memory_utils import cleanup_if_needed
    cleanup_if_needed(threshold_mb=100.0)
    
    # 시스템 메모리 부족시 자동 정리
    from support.memory_utils import cleanup_on_low_memory
    cleanup_on_low_memory(threshold_percent=85.0)
    
    # 새로운 캐시 수동 등록
    from support.memory_utils import register_cache
    my_cache = {}
    register_cache(my_cache, 'my_custom_cache')
    """
    
    print(commands)

if __name__ == "__main__":
    # 전체 예제 실행
    try:
        example_usage_in_main_program()
        example_integration_with_existing_code()
        example_decorator_usage()
        show_monitoring_commands()
        
        print("\n=== 모든 예제 완료 ===")
        print("이제 tideWise 프로그램에서 자동 메모리 관리를 사용할 수 있습니다!")
        
    except Exception as e:
        print(f"예제 실행 중 오류: {e}")
        import traceback
        traceback.print_exc()
"""
토큰 최적화 시스템 - CLAUDE.md 지침 자동 적용
Trigger: Output >200chars → temp file + summary
Format: [OK] Result + [STATS] Metrics + [WARN] Notes
Effect: 80% token reduction
"""

import os
import time
from datetime import datetime
from typing import Tuple, Optional

class TokenOptimizer:
    def __init__(self, base_dir: str = "C:\\tideWise"):
        self.base_dir = base_dir
        self.logs_dir = os.path.join(base_dir, "logs")
        self.temp_threshold = 200  # characters
        
        # logs 디렉토리 생성
        os.makedirs(self.logs_dir, exist_ok=True)
    
    def should_optimize(self, content: str) -> bool:
        """200자 초과 여부 확인"""
        return len(content) > self.temp_threshold
    
    def create_temp_file(self, content: str, task_description: str = "output") -> str:
        """임시 파일 생성 및 경로 반환"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"temp_output_{timestamp}.txt"
        filepath = os.path.join(self.logs_dir, filename)
        
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(f"Task: {task_description}\n")
            f.write(f"Timestamp: {timestamp}\n")
            f.write(f"Original Length: {len(content)} chars\n")
            f.write("-" * 50 + "\n")
            f.write(content)
        
        return filepath
    
    def generate_summary(self, content: str, task_description: str = "output") -> str:
        """요약 생성 - [OK/STATS/WARN] 포맷"""
        lines = content.split('\n')
        total_lines = len(lines)
        
        # 주요 정보 추출
        success_indicators = ['완료', '성공', 'OK', 'SUCCESS', '✅']
        warnings = ['주의', '경고', 'WARN', '⚠️', '문제']
        
        success_count = sum(1 for line in lines for indicator in success_indicators if indicator in line)
        warning_count = sum(1 for line in lines for indicator in warnings if indicator in line)
        
        # 요약 생성
        summary_parts = []
        
        # [OK] 부분
        if success_count > 0:
            summary_parts.append(f"[OK] {task_description} 완료 ({success_count}개 성공 항목)")
        else:
            summary_parts.append(f"[OK] {task_description} 처리됨")
        
        # [STATS] 부분
        original_length = len(content)
        summary_parts.append(f"[STATS] 원본:{original_length}자, 줄:{total_lines}개")
        
        # [WARN] 부분
        if warning_count > 0:
            summary_parts.append(f"[WARN] {warning_count}개 주의사항 확인 필요")
        else:
            summary_parts.append("[WARN] 특이사항 없음")
        
        return " | ".join(summary_parts)
    
    def process_output(self, content: str, task_description: str = "작업 결과") -> Tuple[str, Optional[str]]:
        """메인 처리 함수 - 내용 분석 후 최적화 적용"""
        if not self.should_optimize(content):
            return content, None
        
        # 임시 파일 생성
        temp_filepath = self.create_temp_file(content, task_description)
        
        # 요약 생성
        summary = self.generate_summary(content, task_description)
        
        # 자동 삭제 예약 (5분 후)
        self._schedule_cleanup(temp_filepath, 300)
        
        return summary, temp_filepath
    
    def _schedule_cleanup(self, filepath: str, delay_seconds: int):
        """파일 자동 삭제 예약 (간단한 구현)"""
        # 실제 운영 환경에서는 백그라운드 태스크나 스케줄러 사용
        import threading
        
        def cleanup():
            time.sleep(delay_seconds)
            try:
                if os.path.exists(filepath):
                    os.remove(filepath)
                    print(f"[AUTO-CLEANUP] 임시 파일 삭제됨: {os.path.basename(filepath)}")
            except Exception:
                pass  # 삭제 실패 시 무시
        
        cleanup_thread = threading.Thread(target=cleanup, daemon=True)
        cleanup_thread.start()
    
    def get_optimization_percentage(self, original_length: int, summary_length: int) -> int:
        """토큰 최적화 비율 계산"""
        if original_length == 0:
            return 0
        
        reduction = ((original_length - summary_length) / original_length) * 100
        return min(int(reduction), 100)  # 최대 100%

# 전역 최적화기 인스턴스
_optimizer = None

def get_token_optimizer() -> TokenOptimizer:
    """토큰 최적화기 싱글톤 인스턴스 반환"""
    global _optimizer
    if _optimizer is None:
        _optimizer = TokenOptimizer()
    return _optimizer

def optimize_if_needed(content: str, task_description: str = "작업 결과") -> Tuple[str, int]:
    """편의 함수 - 필요시 자동 최적화 적용"""
    optimizer = get_token_optimizer()
    original_length = len(content)
    
    optimized_content, temp_file = optimizer.process_output(content, task_description)
    
    # 최적화 비율 계산
    optimization_percentage = optimizer.get_optimization_percentage(
        original_length, len(optimized_content)
    )
    
    if temp_file:
        print(f"[TOKEN-OPT] 임시 파일: {os.path.basename(temp_file)} | 최적화: {optimization_percentage}%")
    
    return optimized_content, optimization_percentage

# 사용 예시
if __name__ == "__main__":
    # 테스트
    test_content = """
    이것은 200자를 초과하는 긴 텍스트입니다. 
    토큰 최적화 시스템이 정상 동작하는지 테스트합니다.
    완료된 작업: 1. 파일 생성 완료 2. 설정 완료 3. 테스트 성공
    주의사항: 설정 파일 확인 필요
    전체 시스템이 정상적으로 작동하고 있으며 모든 기능이 구현되었습니다.
    """
    
    result, opt_percentage = optimize_if_needed(test_content, "토큰 최적화 테스트")
    print(f"결과: {result}")
    print(f"최적화율: {opt_percentage}%")
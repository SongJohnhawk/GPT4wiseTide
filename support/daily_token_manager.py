#!/usr/bin/env python3
"""
Daily Token Manager - 일일 토큰 관리 시스템
- 매일 00:05에 새 토큰 발급
- 매일 23:58에 토큰 삭제
- 전날 토큰 자동 감지 및 재발급
"""

import json
import requests
import threading
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, Dict, Any
import logging

# 로거 설정
logger = logging.getLogger(__name__)

# 메모리 정리 시스템 임포트
try:
    from memory_cleanup_manager import get_memory_cleanup_manager
    MEMORY_CLEANUP_AVAILABLE = True
except ImportError:
    MEMORY_CLEANUP_AVAILABLE = False
    logger.warning("Memory Cleanup Manager를 찾을 수 없습니다")

class DailyTokenManager:
    """일일 토큰 관리자"""
    
    def __init__(self):
        self.project_root = Path(__file__).parent.parent
        self.token_cache_file = Path(__file__).parent / "token_cache.json"
        self.tokens = {}  # 메모리에 저장된 토큰
        self._lock = threading.Lock()
        self._background_thread = None
        self._stop_flag = threading.Event()
        
        # 메모리 정리 관리자 연동
        self.memory_manager = None
        if MEMORY_CLEANUP_AVAILABLE:
            try:
                self.memory_manager = get_memory_cleanup_manager()
                # 토큰 캐시를 정리 대상으로 등록
                self.memory_manager.register_cache(self.tokens, 'token_cache')
                logger.info("메모리 정리 시스템과 연동됨")
            except Exception as e:
                logger.warning(f"메모리 정리 시스템 연동 실패: {e}")
                self.memory_manager = None
        
        # 시작시 토큰 로드
        self.load_or_refresh_tokens()
        
        # 백그라운드 스레드 시작
        self.start_background_manager()
    
    def load_or_refresh_tokens(self):
        """토큰 로드 또는 새로고침"""
        with self._lock:
            try:
                # 캐시 파일이 있으면 로드
                if self.token_cache_file.exists():
                    with open(self.token_cache_file, 'r', encoding='utf-8') as f:
                        cache_data = json.load(f)
                    
                    # 각 토큰 확인
                    for account_type in ['real', 'mock']:
                        if account_type in cache_data:
                            token_data = cache_data[account_type]
                            
                            # 토큰 생성 시간 확인
                            generated_at_str = token_data.get('generated_at_kst', '')
                            if generated_at_str:
                                generated_at = datetime.fromisoformat(generated_at_str.replace('+09:00', ''))
                                
                                # 전날 토큰인지 확인 (날짜가 다르면 전날 토큰)
                                if generated_at.date() < datetime.now().date():
                                    logger.info(f"{account_type} 토큰이 전날 토큰입니다. 재발급 필요")
                                    self._request_new_token(account_type)
                                else:
                                    # 오늘 토큰이면 메모리에 저장
                                    logger.info(f"{account_type} 토큰은 오늘 발급된 유효한 토큰입니다")
                                    self.tokens[account_type] = token_data
                            else:
                                # 생성 시간이 없으면 재발급
                                logger.info(f"{account_type} 토큰 생성 시간 정보 없음. 재발급 필요")
                                self._request_new_token(account_type)
                        else:
                            # 토큰이 없으면 발급
                            logger.info(f"{account_type} 토큰이 없습니다. 새로 발급")
                            self._request_new_token(account_type)
                else:
                    # 캐시 파일이 없으면 모든 토큰 발급
                    logger.info("토큰 캐시 파일이 없습니다. 모든 토큰 새로 발급")
                    self._request_new_token('real')
                    self._request_new_token('mock')
                    
            except Exception as e:
                logger.error(f"토큰 로드/갱신 실패: {e}")
    
    def _request_new_token(self, account_type: str):
        """새 토큰 발급 (실제 KIS API 호출)"""
        try:
            # Register_Key.md에서 설정 로드
            import sys
            import os
            current_dir = os.path.dirname(os.path.abspath(__file__))
            if current_dir not in sys.path:
                sys.path.insert(0, current_dir)
            
            from authoritative_register_key_loader import get_authoritative_loader
            loader = get_authoritative_loader()
            
            if account_type.lower() == 'real':
                config = loader.get_fresh_config('REAL')
                urls = loader.get_fresh_urls()
                base_url = urls.get('real_rest', 'https://openapi.koreainvestment.com:9443')
            else:
                config = loader.get_fresh_config('MOCK')
                urls = loader.get_fresh_urls()
                base_url = urls.get('mock_rest', 'https://openapivts.koreainvestment.com:29443')
            
            # 토큰 발급 API 호출
            url = f"{base_url}/oauth2/tokenP"
            headers = {'Content-Type': 'application/json'}
            body = {
                "grant_type": "client_credentials",
                "appkey": config.get("app_key") or config.get("APP_KEY"),
                "appsecret": config.get("app_secret") or config.get("APP_SECRET")
            }
            
            response = requests.post(url, headers=headers, json=body, timeout=10)
            
            if response.status_code == 200:
                token_data = response.json()
                
                # 토큰 정보 저장
                now = datetime.now()
                expires_at = now + timedelta(seconds=86400)  # 24시간
                
                token_info = {
                    "access_token": token_data.get("access_token"),
                    "expires_at_kst": expires_at.isoformat() + "+09:00",
                    "account_type": account_type,
                    "generated_at_kst": now.isoformat() + "+09:00",
                    "approval_key": token_data.get("approval_key", "")
                }
                
                # 메모리에 저장
                self.tokens[account_type] = token_info
                
                # 파일에 저장
                self._save_tokens_to_file()
                
                logger.info(f"{account_type} 토큰 발급 성공")
                return True
            else:
                logger.error(f"{account_type} 토큰 발급 실패: {response.status_code}")
                return False
                
        except Exception as e:
            logger.error(f"{account_type} 토큰 발급 오류: {e}")
            return False
    
    def _save_tokens_to_file(self):
        """메모리의 토큰을 파일에 저장"""
        try:
            with open(self.token_cache_file, 'w', encoding='utf-8') as f:
                json.dump(self.tokens, f, indent=2, ensure_ascii=False)
            logger.debug("토큰 캐시 파일 저장 완료")
        except Exception as e:
            logger.error(f"토큰 캐시 파일 저장 실패: {e}")
    
    def _delete_all_tokens(self):
        """모든 토큰 삭제 (23:58에 실행)"""
        with self._lock:
            self.tokens.clear()
            
            # 캐시 파일도 삭제
            if self.token_cache_file.exists():
                self.token_cache_file.unlink()
                logger.info("23:58 - 모든 토큰 삭제 완료")
    
    def _refresh_all_tokens(self):
        """모든 토큰 갱신 (00:05에 실행)"""
        with self._lock:
            logger.info("00:05 - 모든 토큰 갱신 시작")
            self._request_new_token('real')
            self._request_new_token('mock')
            logger.info("00:05 - 모든 토큰 갱신 완료")
    
    def start_background_manager(self):
        """백그라운드 토큰 관리 스레드 시작"""
        if self._background_thread is None or not self._background_thread.is_alive():
            self._background_thread = threading.Thread(target=self._background_loop, daemon=True)
            self._background_thread.start()
            logger.info("백그라운드 토큰 관리자 시작됨")
    
    def _background_loop(self):
        """백그라운드 루프 (토큰 관리 + 메모리 정리)"""
        last_memory_cleanup = datetime.now()
        memory_cleanup_interval = 30 * 60  # 30분
        
        while not self._stop_flag.is_set():
            try:
                now = datetime.now()
                current_time = now.strftime("%H:%M")
                
                # 00:05에 토큰 발급
                if current_time == "00:05":
                    self._refresh_all_tokens()
                    time.sleep(60)  # 1분 대기 (중복 실행 방지)
                
                # 23:58에 토큰 삭제
                elif current_time == "23:58":
                    self._delete_all_tokens()
                    time.sleep(60)  # 1분 대기 (중복 실행 방지)
                
                # 30분마다 메모리 정리
                if (now - last_memory_cleanup).total_seconds() >= memory_cleanup_interval:
                    if self.memory_manager:
                        try:
                            logger.info("30분 간격 메모리 정리 시작")
                            cleanup_result = self.memory_manager.perform_cleanup()
                            if cleanup_result.get('success', False):
                                freed_mb = cleanup_result.get('freed_memory_mb', 0)
                                logger.info(f"메모리 정리 완료: {freed_mb:.1f}MB 해제")
                            last_memory_cleanup = now
                        except Exception as e:
                            logger.error(f"메모리 정리 오류: {e}")
                            last_memory_cleanup = now  # 실패해도 다음 주기로 넘어감
                
                # 30초마다 체크
                time.sleep(30)
                
            except Exception as e:
                logger.error(f"백그라운드 관리 오류: {e}")
                time.sleep(60)
    
    def get_token(self, account_type: str) -> Optional[str]:
        """토큰 가져오기 (전날 토큰 체크 포함)"""
        with self._lock:
            account_key = account_type.lower()
            
            # 메모리에 토큰이 있는지 확인
            if account_key in self.tokens:
                token_data = self.tokens[account_key]
                
                # 토큰 생성 날짜 확인
                generated_at_str = token_data.get('generated_at_kst', '')
                if generated_at_str:
                    generated_at = datetime.fromisoformat(generated_at_str.replace('+09:00', ''))
                    
                    # 전날 토큰이면 재발급
                    if generated_at.date() < datetime.now().date():
                        logger.info(f"{account_type} 토큰이 전날 토큰입니다. 재발급합니다")
                        if self._request_new_token(account_type):
                            return self.tokens[account_key].get('access_token')
                        return None
                    else:
                        # 오늘 토큰이면 반환
                        return token_data.get('access_token')
            
            # 토큰이 없으면 발급 시도
            logger.info(f"{account_type} 토큰이 없습니다. 새로 발급합니다")
            if self._request_new_token(account_type):
                return self.tokens[account_key].get('access_token')
            
            return None
    
    def force_memory_cleanup(self) -> Optional[Dict[str, Any]]:
        """즉시 메모리 정리 수행"""
        if self.memory_manager:
            try:
                logger.info("수동 메모리 정리 시작")
                result = self.memory_manager.force_cleanup()
                return result
            except Exception as e:
                logger.error(f"수동 메모리 정리 실패: {e}")
                return None
        else:
            logger.warning("메모리 정리 관리자가 사용할 수 없습니다")
            return None
    
    def get_memory_status(self) -> Optional[Dict[str, Any]]:
        """현재 메모리 상태 반환"""
        if self.memory_manager:
            try:
                return self.memory_manager.get_status()
            except Exception as e:
                logger.error(f"메모리 상태 조회 실패: {e}")
                return None
        return None
    
    def register_cache_for_cleanup(self, cache_object, name: str):
        """새로운 캐시를 정리 대상으로 등록"""
        if self.memory_manager:
            try:
                self.memory_manager.register_cache(cache_object, name)
                logger.debug(f"캐시 등록: {name}")
            except Exception as e:
                logger.warning(f"캐시 등록 실패 {name}: {e}")
    
    def stop(self):
        """백그라운드 스레드 종료"""
        self._stop_flag.set()
        if self._background_thread:
            self._background_thread.join(timeout=2)
        
        # 메모리 정리 관리자도 종료
        if self.memory_manager:
            try:
                self.memory_manager.stop()
            except Exception as e:
                logger.warning(f"메모리 정리 관리자 종료 실패: {e}")
        
        logger.info("백그라운드 토큰 관리자 종료됨")

# 싱글톤 인스턴스
_daily_token_manager = None

def get_daily_token_manager() -> DailyTokenManager:
    """일일 토큰 관리자 싱글톤 인스턴스 반환"""
    global _daily_token_manager
    if _daily_token_manager is None:
        _daily_token_manager = DailyTokenManager()
    return _daily_token_manager

# 편의 함수들
def force_memory_cleanup():
    """즉시 메모리 정리 실행"""
    manager = get_daily_token_manager()
    return manager.force_memory_cleanup()

def get_memory_status():
    """메모리 상태 조회"""
    manager = get_daily_token_manager()
    return manager.get_memory_status()

def register_cache_for_cleanup(cache_object, name: str):
    """캐시를 정리 대상으로 등록"""
    manager = get_daily_token_manager()
    manager.register_cache_for_cleanup(cache_object, name)

# 테스트 함수
def test_daily_token_manager():
    """일일 토큰 관리자 테스트"""
    print("=== Daily Token Manager + Memory Cleanup 테스트 ===")
    
    manager = get_daily_token_manager()
    
    # 실전 토큰 테스트
    real_token = manager.get_token('real')
    if real_token:
        print(f"실전 토큰: {real_token[:30]}...")
    else:
        print("실전 토큰 획득 실패")
    
    # 모의 토큰 테스트
    mock_token = manager.get_token('mock')
    if mock_token:
        print(f"모의 토큰: {mock_token[:30]}...")
    else:
        print("모의 토큰 획득 실패")
    
    # 메모리 상태 확인
    memory_status = manager.get_memory_status()
    if memory_status:
        current_memory = memory_status['current_memory']
        print(f"\n현재 메모리 사용량: {current_memory['rss_mb']:.1f}MB ({current_memory['percent']:.1f}%)")
        print(f"등록된 캐시: {memory_status['registered_caches']}개")
        
        # 테스트용 메모리 정리
        print("\n메모리 정리 테스트...")
        cleanup_result = manager.force_memory_cleanup()
        if cleanup_result and cleanup_result.get('success'):
            freed_mb = cleanup_result.get('freed_memory_mb', 0)
            print(f"메모리 정리 완료: {freed_mb:.1f}MB 해제")
        else:
            print("메모리 정리 실패 또는 정리할 내용 없음")
    
    print("\n백그라운드 관리자가 실행 중입니다")
    print("- 00:05에 자동으로 새 토큰 발급")
    print("- 23:58에 자동으로 토큰 삭제")
    print("- 30분마다 자동으로 메모리 정리")

if __name__ == "__main__":
    # 로깅 설정
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
    
    test_daily_token_manager()
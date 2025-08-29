#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
토큰 시스템 통합 테스트
실제 환경과 유사한 조건에서 4개 매매 모드 토큰 발급 검증
"""

import sys
import os
import json
import asyncio
import tempfile
import unittest
from pathlib import Path
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock, AsyncMock
import pytz

# 프로젝트 루트를 Python 경로에 추가
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from support.token_auto_refresher import (
    TokenAutoRefresher, 
    get_token_refresher, 
    initialize_token_system,
    get_valid_token
)
from support.authoritative_register_key_loader import (
    AuthoritativeRegisterKeyLoader,
    get_authoritative_loader
)


class TestTokenSystemIntegration(unittest.TestCase):
    """토큰 시스템 통합 테스트"""
    
    def setUp(self):
        """각 테스트 전 초기화"""
        self.temp_dir = Path(tempfile.mkdtemp())
        self.register_key_path = self.temp_dir / "Policy" / "Register_Key" / "Register_Key.md"
        self.register_key_path.parent.mkdir(parents=True, exist_ok=True)
        
        # 완전한 Register_Key.md 내용
        self.complete_register_content = """
# 한국투자증권 OPEN API 연결정보

## 계좌 정보

### 실전투자 계좌 정보
```
계좌번호: [12345678901]
계좌 비밀번호: [1234]
APP KEY: [PSAKEY1234567890ABCDEF]
APP Secret KEY: [SECRET1234567890ABCDEF]
```

### 모의투자 계좌 정보
```
계좌번호: [50000000001]
계좌 비밀번호: [0000]
APP KEY: [PSAMOCKKEY1234567890]
APP Secret KEY: [MOCKSECRET1234567890]
```

## API URL 정보

### API 호출 URL 정보
```
실전투자 REST URL: https://openapi.koreainvestment.com:9443
실전투자 Websocket URL: ws://ops.koreainvestment.com:21000
모의투자 REST URL: https://openapivts.koreainvestment.com:29443
모의투자 Websocket URL: ws://openvts.koreainvestment.com:25000
```

## 알림 설정

### 연동 토큰
```
Bot Token: 1234567890:ABCDEF1234567890ABCDEF1234567890
Chat ID: 1234567890
```
"""
    
    def tearDown(self):
        """각 테스트 후 정리"""
        import shutil
        if self.temp_dir.exists():
            shutil.rmtree(self.temp_dir)
    
    async def test_four_token_issuance_success(self):
        """4개 토큰 발급 성공 시나리오 통합 테스트"""
        # Register_Key.md 파일 생성
        with open(self.register_key_path, 'w', encoding='utf-8') as f:
            f.write(self.complete_register_content)
        
        # Mock HTTP 응답 설정
        mock_responses = {
            'access_token': 'mock_access_token_12345',
            'approval_key': 'mock_approval_key_67890'
        }
        
        with patch('support.token_auto_refresher.Path') as mock_path, \
             patch('aiohttp.ClientSession') as mock_session:
            
            # Path mock 설정
            mock_path.return_value.parent.parent = self.temp_dir
            
            # HTTP 응답 Mock 설정
            mock_response = AsyncMock()
            mock_response.status = 200
            mock_response.json = AsyncMock(return_value=mock_responses)
            
            mock_session_instance = AsyncMock()
            mock_session_instance.post.return_value.__aenter__.return_value = mock_response
            mock_session.return_value.__aenter__.return_value = mock_session_instance
            
            # TokenAutoRefresher 초기화
            refresher = TokenAutoRefresher()
            refresher.token_cache_path = self.temp_dir / "token_cache.json"
            refresher.api_urls = {
                'real': 'https://openapi.koreainvestment.com:9443',
                'mock': 'https://openapivts.koreainvestment.com:29443'
            }
            
            # 4개 토큰 갱신 실행
            success = await refresher.refresh_all_tokens()
            
            # 결과 검증
            self.assertTrue(success, "4개 토큰 갱신이 실패했습니다")
            
            # 시스템 준비 상태 확인
            readiness = refresher.validate_system_readiness()
            self.assertTrue(readiness['ready'], f"시스템 준비 실패: {readiness}")
            self.assertEqual(readiness['total_valid'], 4)
            self.assertEqual(len(readiness['missing_tokens']), 0)
    
    async def test_partial_token_failure_handling(self):
        """부분 토큰 실패 처리 테스트"""
        # Register_Key.md 파일 생성
        with open(self.register_key_path, 'w', encoding='utf-8') as f:
            f.write(self.complete_register_content)
        
        with patch('support.token_auto_refresher.Path') as mock_path, \
             patch('aiohttp.ClientSession') as mock_session:
            
            mock_path.return_value.parent.parent = self.temp_dir
            
            # HTTP 응답 Mock - 실전투자는 성공, 모의투자는 실패
            call_count = 0
            async def mock_post(*args, **kwargs):
                nonlocal call_count
                call_count += 1
                
                mock_response = AsyncMock()
                if call_count <= 2:  # 실전투자 토큰 (성공)
                    mock_response.status = 200
                    mock_response.json = AsyncMock(return_value={
                        'access_token': 'real_token_success',
                        'approval_key': 'real_approval_success'
                    })
                else:  # 모의투자 토큰 (실패)
                    mock_response.status = 401
                    mock_response.text = AsyncMock(return_value='Authentication failed')
                
                return mock_response
            
            mock_session_instance = AsyncMock()
            mock_session_instance.post = mock_post
            mock_session.return_value.__aenter__.return_value = mock_session_instance
            
            refresher = TokenAutoRefresher()
            refresher.token_cache_path = self.temp_dir / "token_cache.json"
            refresher.api_urls = {
                'real': 'https://openapi.koreainvestment.com:9443',
                'mock': 'https://openapivts.koreainvestment.com:29443'
            }
            
            # 부분 실패 토큰 갱신 실행
            success = await refresher.refresh_all_tokens()
            
            # 부분 실패는 전체 실패로 간주
            self.assertFalse(success, "부분 실패가 성공으로 처리되었습니다")
            
            # 시스템 준비 상태 확인
            readiness = refresher.validate_system_readiness()
            self.assertFalse(readiness['ready'], "부분 실패 시 시스템이 준비됨으로 표시되었습니다")
            self.assertLess(readiness['total_valid'], 4)
            self.assertGreater(len(readiness['missing_tokens']), 0)
    
    async def test_kst_timezone_integration(self):
        """KST 시간대 통합 테스트"""
        with patch('support.token_auto_refresher.Path') as mock_path:
            mock_path.return_value.parent.parent = self.temp_dir
            
            refresher = TokenAutoRefresher()
            kst_timezone = pytz.timezone('Asia/Seoul')
            
            # KST 시간 확인
            current_kst = refresher._get_kst_time()
            self.assertEqual(current_kst.tzinfo, kst_timezone)
            
            # 토큰 생명주기 시나리오 테스트
            token_info = {
                'access_token': 'test_token',
                'expires_at_kst': (current_kst + timedelta(hours=24)).isoformat(),
                'generated_at_kst': current_kst.isoformat()
            }
            
            # 다양한 시간대에서 재사용 가능 여부 테스트
            test_times = [
                (15, 0, True),   # 15:00 - 재사용 가능
                (23, 54, True),  # 23:54 - 재사용 가능
                (23, 56, False), # 23:56 - 무효화
                (23, 59, False), # 23:59 - 무효화
            ]
            
            for hour, minute, expected in test_times:
                with patch.object(refresher, '_get_kst_time') as mock_time:
                    mock_time.return_value = current_kst.replace(hour=hour, minute=minute)
                    
                    result = refresher.should_reuse_token(token_info)
                    self.assertEqual(result, expected, 
                                   f"시간 {hour:02d}:{minute:02d}에서 예상과 다른 결과: {result}")
    
    def test_authoritative_loader_integration(self):
        """AuthoritativeRegisterKeyLoader 통합 테스트"""
        # Register_Key.md 파일 생성
        with open(self.register_key_path, 'w', encoding='utf-8') as f:
            f.write(self.complete_register_content)
        
        # 로더 생성
        loader = AuthoritativeRegisterKeyLoader(self.temp_dir)
        
        # load_register_keys() 메서드 테스트
        all_data = loader.load_register_keys()
        self.assertIn('kis_real', all_data)
        self.assertIn('kis_mock', all_data)
        
        # 개별 설정 로드 테스트
        real_config = loader.get_fresh_config('REAL')
        mock_config = loader.get_fresh_config('MOCK')
        
        # 필수 필드 확인
        required_fields = ['account_number', 'app_key', 'app_secret', 'account_password']
        for field in required_fields:
            self.assertIn(field, real_config, f"실전투자 설정에 {field} 누락")
            self.assertIn(field, mock_config, f"모의투자 설정에 {field} 누락")
        
        # URL 설정 확인
        urls = loader.get_fresh_urls()
        expected_urls = ['real_rest', 'real_websocket', 'mock_rest', 'mock_websocket']
        for url_type in expected_urls:
            self.assertIn(url_type, urls, f"URL 설정에 {url_type} 누락")
    
    async def test_token_system_initialization_flow(self):
        """토큰 시스템 초기화 플로우 통합 테스트"""
        # Register_Key.md 파일 생성
        with open(self.register_key_path, 'w', encoding='utf-8') as f:
            f.write(self.complete_register_content)
        
        with patch('support.token_auto_refresher.Path') as mock_path, \
             patch('aiohttp.ClientSession') as mock_session, \
             patch('support.token_auto_refresher._token_refresher', None):
            
            mock_path.return_value.parent.parent = self.temp_dir
            
            # 성공적인 HTTP 응답 Mock
            mock_response = AsyncMock()
            mock_response.status = 200
            mock_response.json = AsyncMock(return_value={
                'access_token': 'init_test_token',
                'approval_key': 'init_test_approval'
            })
            
            mock_session_instance = AsyncMock()
            mock_session_instance.post.return_value.__aenter__.return_value = mock_response
            mock_session.return_value.__aenter__.return_value = mock_session_instance
            
            # 토큰 시스템 초기화
            refresher = await initialize_token_system()
            
            # 초기화 결과 확인
            self.assertIsNotNone(refresher)
            self.assertTrue(hasattr(refresher, 'token_cache_path'))
            self.assertTrue(hasattr(refresher, 'validate_system_readiness'))
    
    async def test_valid_token_retrieval(self):
        """유효한 토큰 조회 통합 테스트"""
        with patch('support.token_auto_refresher.Path') as mock_path, \
             patch('support.token_auto_refresher._token_refresher', None):
            
            mock_path.return_value.parent.parent = self.temp_dir
            
            # Mock TokenAutoRefresher 설정
            mock_refresher = MagicMock()
            current_kst = datetime.now(pytz.timezone('Asia/Seoul'))
            
            # 유효한 토큰 정보
            valid_token_info = {
                'access_token': 'valid_test_token_12345',
                'expires_at_kst': (current_kst + timedelta(hours=12)).isoformat(),
                'generated_at_kst': current_kst.isoformat()
            }
            
            mock_refresher.get_cached_token.return_value = valid_token_info
            
            with patch('support.token_auto_refresher.get_token_refresher', return_value=mock_refresher):
                token = await get_valid_token('real')
                
                self.assertEqual(token, 'valid_test_token_12345')
                mock_refresher.get_cached_token.assert_called_with('real')


class TestFourTradingModesTokenValidation(unittest.TestCase):
    """4개 매매 모드 토큰 검증 테스트"""
    
    def setUp(self):
        """테스트 초기화"""
        self.trading_modes = {
            'automated_real': {'account_type': 'real', 'mode': 'automated'},
            'automated_mock': {'account_type': 'mock', 'mode': 'automated'},
            'day_trading_real': {'account_type': 'real', 'mode': 'day_trading'},
            'day_trading_mock': {'account_type': 'mock', 'mode': 'day_trading'}
        }
    
    async def test_all_trading_modes_token_requirements(self):
        """모든 매매 모드의 토큰 요구사항 테스트"""
        temp_dir = Path(tempfile.mkdtemp())
        
        try:
            with patch('support.token_auto_refresher.Path') as mock_path:
                mock_path.return_value.parent.parent = temp_dir
                
                refresher = TokenAutoRefresher()
                refresher.token_cache_path = temp_dir / "token_cache.json"
                
                # 4개 토큰 모두 설정
                current_kst = refresher._get_kst_time()
                expires_kst = current_kst + timedelta(hours=24)
                
                refresher.tokens = {
                    'real': {
                        'access_token': 'real_access_token_for_trading',
                        'approval_key': 'real_approval_key_for_trading',
                        'expires_at_kst': expires_kst.isoformat(),
                        'generated_at_kst': current_kst.isoformat()
                    },
                    'mock': {
                        'access_token': 'mock_access_token_for_trading',
                        'approval_key': 'mock_approval_key_for_trading',
                        'expires_at_kst': expires_kst.isoformat(),
                        'generated_at_kst': current_kst.isoformat()
                    }
                }
                
                # 각 매매 모드별 토큰 검증
                for mode_name, mode_config in self.trading_modes.items():
                    account_type = mode_config['account_type']
                    
                    # 해당 계정 타입의 토큰 조회
                    with patch.object(refresher, '_get_kst_time') as mock_time:
                        # 정상 시간대로 설정 (재사용 가능)
                        mock_time.return_value = current_kst.replace(hour=15, minute=0)
                        
                        token_info = refresher.get_cached_token(account_type)
                        
                        self.assertIsNotNone(token_info, 
                                           f"{mode_name} 모드에서 {account_type} 토큰을 찾을 수 없습니다")
                        self.assertIn('access_token', token_info, 
                                    f"{mode_name} 모드에서 access_token이 없습니다")
                        self.assertIn('approval_key', token_info, 
                                    f"{mode_name} 모드에서 approval_key가 없습니다")
                
                # 전체 시스템 준비 상태 확인
                with patch.object(refresher, '_get_kst_time') as mock_time:
                    mock_time.return_value = current_kst.replace(hour=15, minute=0)
                    
                    readiness = refresher.validate_system_readiness()
                    self.assertTrue(readiness['ready'], 
                                  f"모든 매매 모드를 지원하기 위한 시스템이 준비되지 않았습니다: {readiness}")
        
        finally:
            import shutil
            if temp_dir.exists():
                shutil.rmtree(temp_dir)


def run_integration_tests():
    """통합 테스트 실행"""
    # 환경 설정
    os.environ['TZ'] = 'Asia/Seoul'
    
    # 비동기 테스트를 위한 이벤트 루프 설정
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    try:
        # 테스트 스위트 생성
        loader = unittest.TestLoader()
        test_suite = unittest.TestSuite()
        
        # 동기 테스트 추가
        test_suite.addTest(loader.loadTestsFromTestCase(TestFourTradingModesTokenValidation))
        
        # 비동기 테스트는 개별 실행
        async_test_class = TestTokenSystemIntegration()
        
        print("토큰 시스템 통합 테스트 시작")
        print("=" * 70)
        
        # 비동기 테스트 실행
        async def run_async_tests():
            test_methods = [
                'test_four_token_issuance_success',
                'test_partial_token_failure_handling', 
                'test_kst_timezone_integration',
                'test_token_system_initialization_flow',
                'test_valid_token_retrieval'
            ]
            
            results = []
            for method_name in test_methods:
                try:
                    print(f"실행 중: {method_name}")
                    method = getattr(async_test_class, method_name)
                    async_test_class.setUp()
                    await method()
                    async_test_class.tearDown()
                    results.append((method_name, True, None))
                    print(f"✓ {method_name} 성공")
                except Exception as e:
                    results.append((method_name, False, str(e)))
                    print(f"✗ {method_name} 실패: {e}")
            
            return results
        
        # 비동기 테스트 실행
        async_results = loop.run_until_complete(run_async_tests())
        
        # 동기 테스트 실행
        runner = unittest.TextTestRunner(verbosity=2)
        sync_result = runner.run(test_suite)
        
        # 결과 통합
        total_tests = len(async_results) + sync_result.testsRun
        total_failures = len([r for r in async_results if not r[1]]) + len(sync_result.failures)
        total_errors = sync_result.errors
        
        print("=" * 70)
        print(f"통합 테스트 완료 - 실행: {total_tests}, 실패: {total_failures}, 오류: {len(total_errors)}")
        
        # 실패한 비동기 테스트 출력
        failed_async = [r for r in async_results if not r[1]]
        if failed_async:
            print("\n실패한 비동기 테스트:")
            for test_name, success, error in failed_async:
                print(f"- {test_name}: {error}")
        
        if sync_result.failures:
            print("\n실패한 동기 테스트:")
            for test, traceback in sync_result.failures:
                print(f"- {test}: {traceback}")
        
        return total_failures == 0 and len(total_errors) == 0
        
    finally:
        loop.close()


if __name__ == "__main__":
    success = run_integration_tests()
    sys.exit(0 if success else 1)
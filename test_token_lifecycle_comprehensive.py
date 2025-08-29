#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
토큰 생명주기 및 로깅 신뢰성 아키텍처 종합 테스트

KST 기반 토큰 생명주기, AuthoritativeRegisterKeyLoader, 성공 상태 게이팅 테스트
"""

import sys
import os
import json
import tempfile
import unittest
from pathlib import Path
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock, mock_open
import pytz

# 프로젝트 루트를 Python 경로에 추가
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from support.token_auto_refresher import TokenAutoRefresher, get_token_refresher, initialize_token_system
from support.authoritative_register_key_loader import (
    AuthoritativeRegisterKeyLoader, 
    get_authoritative_loader,
    APIConfigurationError,
    ValidationError
)


class TestAuthoritativeRegisterKeyLoader(unittest.TestCase):
    """AuthoritativeRegisterKeyLoader 단위 테스트"""
    
    def setUp(self):
        """각 테스트 전 초기화"""
        self.temp_dir = Path(tempfile.mkdtemp())
        self.register_key_path = self.temp_dir / "Policy" / "Register_Key" / "Register_Key.md"
        self.register_key_path.parent.mkdir(parents=True, exist_ok=True)
        
        # 유효한 Register_Key.md 샘플 내용
        self.valid_register_content = """
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

### API 호출 URL 정보
```
실전투자 REST URL: https://openapi.koreainvestment.com:9443
실전투자 Websocket URL: ws://ops.koreainvestment.com:21000
모의투자 REST URL: https://openapivts.koreainvestment.com:29443  
모의투자 Websocket URL: ws://openvts.koreainvestment.com:25000
```

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
    
    def test_loader_init_missing_file(self):
        """파일이 없을 때 초기화 실패 테스트"""
        with self.assertRaises(APIConfigurationError) as context:
            AuthoritativeRegisterKeyLoader(self.temp_dir)
        
        self.assertIn("Register_Key.md 파일이 존재하지 않습니다", str(context.exception))
    
    def test_load_register_keys_success(self):
        """load_register_keys() 메서드 성공 테스트"""
        # 유효한 파일 생성
        with open(self.register_key_path, 'w', encoding='utf-8') as f:
            f.write(self.valid_register_content)
        
        loader = AuthoritativeRegisterKeyLoader(self.temp_dir)
        result = loader.load_register_keys()
        
        # 필수 섹션 존재 확인
        self.assertIn('kis_real', result)
        self.assertIn('kis_mock', result)
        self.assertIn('kis_urls', result)
        self.assertIn('telegram', result)
        
        # 실전투자 데이터 확인
        real_config = result['kis_real']
        self.assertEqual(real_config['account_number'], '12345678901')
        self.assertEqual(real_config['app_key'], 'PSAKEY1234567890ABCDEF')
        
        # 모의투자 데이터 확인
        mock_config = result['kis_mock']
        self.assertEqual(mock_config['account_number'], '50000000001')
        self.assertEqual(mock_config['app_key'], 'PSAMOCKKEY1234567890')
    
    def test_get_fresh_config_real(self):
        """실전투자 설정 로드 테스트"""
        with open(self.register_key_path, 'w', encoding='utf-8') as f:
            f.write(self.valid_register_content)
        
        loader = AuthoritativeRegisterKeyLoader(self.temp_dir)
        config = loader.get_fresh_config("REAL")
        
        self.assertEqual(config['account_number'], '12345678901')
        self.assertEqual(config['app_key'], 'PSAKEY1234567890ABCDEF')
        self.assertEqual(config['app_secret'], 'SECRET1234567890ABCDEF')
    
    def test_get_fresh_config_mock(self):
        """모의투자 설정 로드 테스트"""
        with open(self.register_key_path, 'w', encoding='utf-8') as f:
            f.write(self.valid_register_content)
        
        loader = AuthoritativeRegisterKeyLoader(self.temp_dir)
        config = loader.get_fresh_config("MOCK")
        
        self.assertEqual(config['account_number'], '50000000001')
        self.assertEqual(config['app_key'], 'PSAMOCKKEY1234567890')
        self.assertEqual(config['app_secret'], 'MOCKSECRET1234567890')
    
    def test_file_change_detection(self):
        """파일 변경 감지 테스트"""
        # 초기 파일 생성
        with open(self.register_key_path, 'w', encoding='utf-8') as f:
            f.write(self.valid_register_content)
        
        loader = AuthoritativeRegisterKeyLoader(self.temp_dir)
        
        # 첫 번째 로드
        config1 = loader.get_fresh_config("REAL")
        self.assertEqual(config1['account_number'], '12345678901')
        
        # 파일 수정
        modified_content = self.valid_register_content.replace('12345678901', '98765432101')
        with open(self.register_key_path, 'w', encoding='utf-8') as f:
            f.write(modified_content)
        
        # 변경 감지 후 다시 로드
        config2 = loader.get_fresh_config("REAL")
        self.assertEqual(config2['account_number'], '98765432101')


class TestTokenAutoRefresher(unittest.TestCase):
    """TokenAutoRefresher 단위 테스트"""
    
    def setUp(self):
        """각 테스트 전 초기화"""
        self.temp_dir = Path(tempfile.mkdtemp())
        self.kst_timezone = pytz.timezone('Asia/Seoul')
        
        # Mock TokenAutoRefresher 생성
        with patch('support.token_auto_refresher.Path') as mock_path:
            mock_path.return_value.parent.parent = self.temp_dir
            self.refresher = TokenAutoRefresher()
            self.refresher.token_cache_path = self.temp_dir / "token_cache.json"
    
    def tearDown(self):
        """각 테스트 후 정리"""
        import shutil
        if self.temp_dir.exists():
            shutil.rmtree(self.temp_dir)
    
    def test_token_cache_path_exists(self):
        """token_cache_path 속성 존재 확인"""
        self.assertTrue(hasattr(self.refresher, 'token_cache_path'))
        self.assertIsNotNone(self.refresher.token_cache_path)
    
    def test_kst_time_methods(self):
        """KST 시간 관련 메서드 테스트"""
        current_kst = self.refresher._get_kst_time()
        self.assertIsInstance(current_kst, datetime)
        self.assertEqual(current_kst.tzinfo, self.kst_timezone)
    
    def test_should_reuse_token_before_2355(self):
        """23:55 이전 토큰 재사용 가능성 테스트"""
        # 유효한 토큰 정보 생성 (내일까지 유효)
        current_kst = self.refresher._get_kst_time()
        expires_kst = current_kst + timedelta(hours=24)
        
        token_info = {
            "access_token": "test_token",
            "expires_at_kst": expires_kst.isoformat(),
            "generated_at_kst": current_kst.isoformat()
        }
        
        # 23:55 이전 시간으로 Mock
        with patch.object(self.refresher, '_get_kst_time') as mock_time:
            mock_time.return_value = current_kst.replace(hour=23, minute=54)
            
            should_reuse = self.refresher.should_reuse_token(token_info)
            self.assertTrue(should_reuse)
    
    def test_should_invalidate_at_2356(self):
        """23:56 이후 토큰 무효화 테스트"""
        current_kst = self.refresher._get_kst_time()
        
        # 23:56으로 Mock
        with patch.object(self.refresher, '_get_kst_time') as mock_time:
            mock_time.return_value = current_kst.replace(hour=23, minute=56)
            
            should_invalidate = self.refresher.should_invalidate_at_2356()
            self.assertTrue(should_invalidate)
    
    def test_post_midnight_renewal_needed(self):
        """자정 이후 갱신 필요 여부 테스트"""
        current_kst = self.refresher._get_kst_time()
        yesterday = current_kst - timedelta(days=1)
        
        # 어제 발급된 토큰 정보
        self.refresher.tokens = {
            'real': {
                'generated_at_kst': yesterday.isoformat()
            }
        }
        
        # 오전 6시로 Mock
        with patch.object(self.refresher, '_get_kst_time') as mock_time:
            mock_time.return_value = current_kst.replace(hour=6, minute=0)
            
            needs_renewal = self.refresher.is_post_midnight_renewal_needed()
            self.assertTrue(needs_renewal)
    
    def test_atomic_token_save(self):
        """원자적 토큰 저장 테스트"""
        self.refresher.tokens = {
            'real': {
                'access_token': 'test_token_123',
                'expires_at_kst': (self.refresher._get_kst_time() + timedelta(hours=24)).isoformat()
            }
        }
        
        # 저장 실행
        self.refresher.save_token_cache()
        
        # 파일 존재 확인
        self.assertTrue(self.refresher.token_cache_path.exists())
        
        # 내용 확인
        with open(self.refresher.token_cache_path, 'r', encoding='utf-8') as f:
            saved_data = json.load(f)
        
        self.assertEqual(saved_data['real']['access_token'], 'test_token_123')
    
    def test_validate_system_readiness(self):
        """시스템 준비 상태 검증 테스트"""
        # 4개 토큰 모두 유효한 상태로 설정
        current_kst = self.refresher._get_kst_time()
        expires_kst = current_kst + timedelta(hours=24)
        
        self.refresher.tokens = {
            'real': {
                'access_token': 'real_access_token',
                'approval_key': 'real_approval_key',
                'expires_at_kst': expires_kst.isoformat(),
                'generated_at_kst': current_kst.isoformat()
            },
            'mock': {
                'access_token': 'mock_access_token', 
                'approval_key': 'mock_approval_key',
                'expires_at_kst': expires_kst.isoformat(),
                'generated_at_kst': current_kst.isoformat()
            }
        }
        
        # 23:50으로 Mock (재사용 가능 시간)
        with patch.object(self.refresher, '_get_kst_time') as mock_time:
            mock_time.return_value = current_kst.replace(hour=23, minute=50)
            
            readiness = self.refresher.validate_system_readiness()
            
            self.assertTrue(readiness['ready'])
            self.assertEqual(readiness['total_valid'], 4)
            self.assertEqual(readiness['readiness_ratio'], '4/4')
            self.assertEqual(len(readiness['missing_tokens']), 0)


class TestKSTTokenLifecycle(unittest.TestCase):
    """KST 기반 토큰 생명주기 통합 테스트"""
    
    def setUp(self):
        """각 테스트 전 초기화"""
        self.temp_dir = Path(tempfile.mkdtemp())
        self.kst_timezone = pytz.timezone('Asia/Seoul')
    
    def tearDown(self):
        """각 테스트 후 정리"""
        import shutil
        if self.temp_dir.exists():
            shutil.rmtree(self.temp_dir)
    
    def test_kst_token_lifecycle_simulation(self):
        """KST 토큰 생명주기 시뮬레이션 테스트"""
        with patch('support.token_auto_refresher.Path') as mock_path:
            mock_path.return_value.parent.parent = self.temp_dir
            refresher = TokenAutoRefresher()
            refresher.token_cache_path = self.temp_dir / "token_cache.json"
        
        current_kst = refresher._get_kst_time()
        
        # 시나리오 1: 15:00 - 정상 토큰 발급 및 재사용
        token_info = {
            'access_token': 'valid_token',
            'expires_at_kst': (current_kst + timedelta(hours=8)).isoformat(),
            'generated_at_kst': current_kst.isoformat()
        }
        
        with patch.object(refresher, '_get_kst_time') as mock_time:
            # 15:00 - 재사용 가능
            mock_time.return_value = current_kst.replace(hour=15, minute=0)
            self.assertTrue(refresher.should_reuse_token(token_info))
            
            # 23:54 - 아직 재사용 가능
            mock_time.return_value = current_kst.replace(hour=23, minute=54)
            self.assertTrue(refresher.should_reuse_token(token_info))
            
            # 23:56 - 무효화
            mock_time.return_value = current_kst.replace(hour=23, minute=56)
            self.assertFalse(refresher.should_reuse_token(token_info))
            self.assertTrue(refresher.should_invalidate_at_2356())
        
        # 시나리오 2: 자정 이후 갱신 필요
        yesterday_token = {
            'access_token': 'yesterday_token',
            'expires_at_kst': (current_kst + timedelta(hours=12)).isoformat(),
            'generated_at_kst': (current_kst - timedelta(days=1)).isoformat()
        }
        
        refresher.tokens = {'real': yesterday_token}
        
        with patch.object(refresher, '_get_kst_time') as mock_time:
            # 06:00 다음날 - 갱신 필요
            mock_time.return_value = current_kst.replace(hour=6, minute=0)
            self.assertTrue(refresher.is_post_midnight_renewal_needed())


class TestSystemReadinessGating(unittest.TestCase):
    """시스템 준비 상태 게이팅 테스트"""
    
    @patch('support.token_auto_refresher.get_token_refresher')
    async def test_initialize_token_system_success(self, mock_get_refresher):
        """토큰 시스템 초기화 성공 시나리오"""
        mock_refresher = MagicMock()
        mock_get_refresher.return_value = mock_refresher
        
        # 성공적인 토큰 갱신 Mock
        mock_refresher.load_token_cache.return_value = None
        mock_refresher.is_file_changed.return_value = True
        mock_refresher.tokens = {}
        mock_refresher.refresh_all_tokens.return_value = True
        mock_refresher.validate_system_readiness.return_value = {
            'ready': True,
            'total_valid': 4,
            'missing_tokens': []
        }
        
        result = await initialize_token_system()
        
        # 호출 검증
        mock_refresher.load_token_cache.assert_called_once()
        mock_refresher.start_file_monitoring.assert_called_once()
        mock_refresher.refresh_all_tokens.assert_called_once()
        mock_refresher.validate_system_readiness.assert_called_once()
        
        self.assertEqual(result, mock_refresher)
    
    @patch('support.token_auto_refresher.get_token_refresher')
    async def test_initialize_token_system_failure(self, mock_get_refresher):
        """토큰 시스템 초기화 실패 시나리오"""
        mock_refresher = MagicMock()
        mock_get_refresher.return_value = mock_refresher
        
        # 실패한 토큰 갱신 Mock
        mock_refresher.load_token_cache.return_value = None
        mock_refresher.is_file_changed.return_value = True
        mock_refresher.tokens = {}
        mock_refresher.refresh_all_tokens.return_value = False  # 실패
        mock_refresher.validate_system_readiness.return_value = {
            'ready': False,
            'total_valid': 0,
            'missing_tokens': ['real_access', 'real_approval', 'mock_access', 'mock_approval']
        }
        
        result = await initialize_token_system()
        
        # 실패해도 refresher는 반환됨 (추후 재시도 가능)
        self.assertEqual(result, mock_refresher)


class TestLoggingSanitization(unittest.TestCase):
    """로깅 정리 및 민감정보 마스킹 테스트"""
    
    def test_log_message_format(self):
        """로그 메시지 형식 테스트"""
        with patch('support.token_auto_refresher.Path') as mock_path:
            mock_path.return_value.parent.parent = Path(tempfile.mkdtemp())
            refresher = TokenAutoRefresher()
        
        # 로그 메시지에 이모지가 없는지 확인
        with patch('support.token_auto_refresher.logger') as mock_logger:
            # 테스트용 토큰 설정
            refresher.tokens = {
                'real': {'access_token': 'token1', 'approval_key': 'key1'},
                'mock': {'access_token': 'token2', 'approval_key': 'key2'}
            }
            
            readiness = refresher.validate_system_readiness()
            
            # 로그 호출 확인
            mock_logger.info.assert_called()
            
            # 호출된 로그 메시지 검증
            call_args = mock_logger.info.call_args_list
            log_messages = [str(call[0][0]) for call in call_args]
            
            # 이모지가 없는지 확인
            emoji_chars = ['🎉', '💥', '✅', '❌', '⚠️', '🔄', '🔔']
            for message in log_messages:
                for emoji in emoji_chars:
                    self.assertNotIn(emoji, message, f"이모지 '{emoji}'가 로그 메시지에 포함됨: {message}")


def run_windows_tests():
    """Windows 환경에서 테스트 실행"""
    # 환경 설정
    os.environ['TZ'] = 'Asia/Seoul'
    
    # 테스트 스위트 생성
    loader = unittest.TestLoader()
    test_suite = unittest.TestSuite()
    
    # 테스트 케이스 추가
    test_suite.addTest(loader.loadTestsFromTestCase(TestAuthoritativeRegisterKeyLoader))
    test_suite.addTest(loader.loadTestsFromTestCase(TestTokenAutoRefresher))
    test_suite.addTest(loader.loadTestsFromTestCase(TestKSTTokenLifecycle))
    test_suite.addTest(loader.loadTestsFromTestCase(TestSystemReadinessGating))
    test_suite.addTest(loader.loadTestsFromTestCase(TestLoggingSanitization))
    
    # 테스트 실행
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(test_suite)
    
    return result


if __name__ == "__main__":
    print("토큰 생명주기 및 로깅 신뢰성 아키텍처 종합 테스트 시작")
    print("=" * 70)
    
    result = run_windows_tests()
    
    print("=" * 70)
    print(f"테스트 완료 - 실행: {result.testsRun}, 실패: {len(result.failures)}, 오류: {len(result.errors)}")
    
    if result.failures:
        print("\n실패한 테스트:")
        for test, traceback in result.failures:
            print(f"- {test}: {traceback}")
    
    if result.errors:
        print("\n오류가 발생한 테스트:")
        for test, traceback in result.errors:
            print(f"- {test}: {traceback}")
    
    # 성공 여부 반환
    sys.exit(0 if result.wasSuccessful() else 1)
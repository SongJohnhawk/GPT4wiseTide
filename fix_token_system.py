#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
API 토큰 시스템 수정 및 검증 스크립트
Tree of Thoughts 방식으로 다중 접근법 시도
"""

import sys
import json
import logging
import asyncio
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, Any, Optional

# Add project root to path
PROJECT_ROOT = Path(__file__).parent
sys.path.insert(0, str(PROJECT_ROOT))

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class TokenSystemFixer:
    """토큰 시스템 수정기 - Tree of Thoughts 방식"""
    
    def __init__(self):
        self.api_keys = self._load_api_keys()
        self.test_results = {}
        
    def _load_api_keys(self) -> Dict[str, Any]:
        """API 키 로드"""
        try:
            register_key_path = PROJECT_ROOT / "Policy" / "Register_Key" / "Register_Key.md"
            
            if not register_key_path.exists():
                logger.error("Register_Key.md 파일이 없습니다")
                return {}
            
            content = register_key_path.read_text(encoding='utf-8')
            
            # Tree of Thoughts: 여러 방식으로 키 추출
            keys = {}
            
            # 방법 A: 정규식으로 추출
            import re
            
            # 실전투자 키 추출
            real_app_key_match = re.search(r'실전투자.*?APP KEY: \[([^\]]+)\]', content, re.DOTALL)
            real_secret_match = re.search(r'실전투자.*?APP Secret KEY: \[([^\]]+)\]', content, re.DOTALL)
            
            # 모의투자 키 추출
            mock_app_key_match = re.search(r'모의투자.*?APP KEY: \[([^\]]+)\]', content, re.DOTALL)
            mock_secret_match = re.search(r'모의투자.*?APP Secret KEY: \[([^\]]+)\]', content, re.DOTALL)
            
            if real_app_key_match:
                keys['real_app_key'] = real_app_key_match.group(1)
            if real_secret_match:
                keys['real_secret_key'] = real_secret_match.group(1)
            if mock_app_key_match:
                keys['mock_app_key'] = mock_app_key_match.group(1)
            if mock_secret_match:
                keys['mock_secret_key'] = mock_secret_match.group(1)
            
            # URL 추출
            real_url_match = re.search(r'실전투자 REST URL: ([^\s]+)', content)
            mock_url_match = re.search(r'모의투자 REST URL: ([^\s]+)', content)
            
            if real_url_match:
                keys['real_url'] = real_url_match.group(1)
            if mock_url_match:
                keys['mock_url'] = mock_url_match.group(1)
            
            logger.info(f"API 키 로드 완료: {len(keys)}개 항목")
            return keys
            
        except Exception as e:
            logger.error(f"API 키 로드 실패: {e}")
            return {}
    
    async def fix_token_system(self):
        """토큰 시스템 수정"""
        logger.info("=== API 토큰 시스템 수정 시작 ===")
        
        fix_methods = [
            ("직접 토큰 발급", self.method_direct_token),
            ("기존 토큰 시스템 수정", self.method_fix_existing_system),
            ("새로운 토큰 매니저 생성", self.method_create_new_manager),
            ("토큰 캐시 초기화", self.method_reset_token_cache)
        ]
        
        for method_name, method_func in fix_methods:
            logger.info(f">>> {method_name} 시도 중...")
            
            try:
                if asyncio.iscoroutinefunction(method_func):
                    result = await method_func()
                else:
                    result = method_func()
                
                if result:
                    logger.info(f"✅ {method_name} 성공")
                    self.test_results[method_name] = "성공"
                    break  # 하나 성공하면 중단
                else:
                    logger.warning(f"⚠️ {method_name} 실패")
                    self.test_results[method_name] = "실패"
                    
            except Exception as e:
                logger.error(f"❌ {method_name} 오류: {str(e)}")
                self.test_results[method_name] = f"오류: {str(e)}"
        
        # 수정 후 검증
        return await self.verify_token_system()
    
    def method_direct_token(self) -> bool:
        """방법 1: 직접 토큰 발급"""
        try:
            import requests
            
            if not self.api_keys.get('mock_app_key') or not self.api_keys.get('mock_secret_key'):
                logger.error("   - 모의투자 API 키가 없습니다")
                return False
            
            # 모의투자 토큰 발급 시도
            url = "https://openapivts.koreainvestment.com:29443/oauth2/tokenP"
            
            headers = {
                "content-type": "application/json; charset=utf-8"
            }
            
            data = {
                "grant_type": "client_credentials",
                "appkey": self.api_keys['mock_app_key'],
                "appsecret": self.api_keys['mock_secret_key']
            }
            
            logger.info("   - 모의투자 토큰 발급 요청 중...")
            response = requests.post(url, headers=headers, json=data, timeout=10)
            
            if response.status_code == 200:
                token_data = response.json()
                if 'access_token' in token_data:
                    logger.info(f"   - 토큰 발급 성공: {token_data['access_token'][:50]}...")
                    
                    # 토큰 저장
                    self._save_token(token_data['access_token'], 'mock')
                    return True
                else:
                    logger.error(f"   - 응답에 access_token 없음: {token_data}")
                    return False
            else:
                logger.error(f"   - HTTP 오류: {response.status_code}, {response.text}")
                return False
                
        except Exception as e:
            logger.error(f"   - 직접 토큰 발급 실패: {e}")
            return False
    
    def method_fix_existing_system(self) -> bool:
        """방법 2: 기존 토큰 시스템 수정"""
        try:
            # 토큰 캐시 파일 확인 및 수정
            cache_file = PROJECT_ROOT / "support" / "token_cache.json"
            
            if cache_file.exists():
                cache_data = json.loads(cache_file.read_text(encoding='utf-8'))
                logger.info(f"   - 기존 캐시 발견: {len(cache_data)} 항목")
                
                # 만료된 토큰 제거
                current_time = datetime.now().timestamp()
                updated_cache = {}
                
                for key, token_info in cache_data.items():
                    if isinstance(token_info, dict) and 'expires_at' in token_info:
                        if token_info['expires_at'] > current_time:
                            updated_cache[key] = token_info
                        else:
                            logger.info(f"   - 만료된 토큰 제거: {key}")
                    else:
                        updated_cache[key] = token_info
                
                # 캐시 업데이트
                cache_file.write_text(json.dumps(updated_cache, indent=2, ensure_ascii=False), encoding='utf-8')
                logger.info("   - 토큰 캐시 정리 완료")
                return True
                
            else:
                logger.info("   - 토큰 캐시 파일 생성")
                cache_file.parent.mkdir(exist_ok=True)
                cache_file.write_text('{}', encoding='utf-8')
                return True
                
        except Exception as e:
            logger.error(f"   - 기존 시스템 수정 실패: {e}")
            return False
    
    def method_create_new_manager(self) -> bool:
        """방법 3: 새로운 토큰 매니저 생성"""
        try:
            # 간단한 토큰 매니저 생성
            token_manager_code = '''#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Simple Token Manager - 간단한 토큰 관리자
"""

import json
import requests
from datetime import datetime, timedelta, timedelta
from pathlib import Path

class SimpleTokenManager:
    def __init__(self):
        self.cache_file = Path(__file__).parent / "simple_token_cache.json"
        
    def get_mock_token(self, app_key: str, secret_key: str) -> str:
        """모의투자 토큰 발급"""
        url = "https://openapivts.koreainvestment.com:29443/oauth2/tokenP"
        
        headers = {"content-type": "application/json; charset=utf-8"}
        data = {
            "grant_type": "client_credentials",
            "appkey": app_key,
            "appsecret": secret_key
        }
        
        response = requests.post(url, headers=headers, json=data, timeout=10)
        if response.status_code == 200:
            token_data = response.json()
            return token_data.get('access_token', '')
        return ''
        
    def save_token(self, token: str, token_type: str):
        """토큰 저장"""
        cache_data = {}
        if self.cache_file.exists():
            cache_data = json.loads(self.cache_file.read_text())
        
        cache_data[token_type] = {
            'token': token,
            'created_at': datetime.now().isoformat(),
            'expires_at': (datetime.now() + timedelta(hours=12)).isoformat()
        }
        
        self.cache_file.write_text(json.dumps(cache_data, indent=2))
        
if __name__ == "__main__":
    print("Simple Token Manager")
'''
            
            simple_manager_path = PROJECT_ROOT / "support" / "simple_token_manager.py"
            simple_manager_path.write_text(token_manager_code, encoding='utf-8')
            
            logger.info("   - 새로운 토큰 매니저 생성 완료")
            return True
            
        except Exception as e:
            logger.error(f"   - 새로운 매니저 생성 실패: {e}")
            return False
    
    def method_reset_token_cache(self) -> bool:
        """방법 4: 토큰 캐시 초기화"""
        try:
            cache_files = [
                PROJECT_ROOT / "support" / "token_cache.json",
                PROJECT_ROOT / "support" / "simple_token_cache.json",
            ]
            
            for cache_file in cache_files:
                if cache_file.exists():
                    # 백업 생성
                    backup_file = cache_file.with_suffix(f'.backup_{datetime.now().strftime("%Y%m%d_%H%M%S")}.json')
                    backup_file.write_text(cache_file.read_text(encoding='utf-8'), encoding='utf-8')
                    
                    # 캐시 초기화
                    cache_file.write_text('{}', encoding='utf-8')
                    logger.info(f"   - 캐시 초기화 완료: {cache_file.name}")
                else:
                    cache_file.parent.mkdir(exist_ok=True)
                    cache_file.write_text('{}', encoding='utf-8')
                    logger.info(f"   - 새 캐시 생성: {cache_file.name}")
            
            return True
            
        except Exception as e:
            logger.error(f"   - 캐시 초기화 실패: {e}")
            return False
    
    def _save_token(self, token: str, token_type: str):
        """토큰 저장"""
        try:
            cache_file = PROJECT_ROOT / "support" / "fixed_token_cache.json"
            cache_file.parent.mkdir(exist_ok=True)
            
            cache_data = {}
            if cache_file.exists():
                cache_data = json.loads(cache_file.read_text(encoding='utf-8'))
            
            cache_data[f"{token_type}_access_token"] = {
                'token': token,
                'created_at': datetime.now().isoformat(),
                'expires_at': (datetime.now() + timedelta(hours=12)).isoformat()
            }
            
            cache_file.write_text(json.dumps(cache_data, indent=2, ensure_ascii=False), encoding='utf-8')
            logger.info(f"   - 토큰 저장 완료: {token_type}")
            
        except Exception as e:
            logger.error(f"   - 토큰 저장 실패: {e}")
    
    async def verify_token_system(self) -> bool:
        """토큰 시스템 검증"""
        logger.info("\n=== 토큰 시스템 검증 ===")
        
        try:
            # 직접 발급 토큰으로 API 호출 테스트
            cache_file = PROJECT_ROOT / "support" / "fixed_token_cache.json"
            
            if cache_file.exists():
                cache_data = json.loads(cache_file.read_text(encoding='utf-8'))
                
                if 'mock_access_token' in cache_data:
                    token_info = cache_data['mock_access_token']
                    token = token_info['token']
                    
                    # 간단한 API 호출 테스트
                    if await self._test_api_with_token(token):
                        logger.info("✅ 토큰 시스템 검증 성공")
                        return True
                    else:
                        logger.error("❌ 토큰은 있지만 API 호출 실패")
                        return False
                else:
                    logger.error("❌ 저장된 토큰이 없습니다")
                    return False
            else:
                logger.error("❌ 토큰 캐시 파일이 없습니다")
                return False
                
        except Exception as e:
            logger.error(f"토큰 시스템 검증 실패: {e}")
            return False
    
    async def _test_api_with_token(self, token: str) -> bool:
        """토큰으로 API 테스트"""
        try:
            import requests
            
            # 모의투자 계좌 잔고 조회 API 테스트
            url = "https://openapivts.koreainvestment.com:29443/uapi/domestic-stock/v1/trading/inquire-balance"
            
            headers = {
                "Content-Type": "application/json; charset=utf-8",
                "authorization": f"Bearer {token}",
                "appkey": self.api_keys.get('mock_app_key', ''),
                "appsecret": self.api_keys.get('mock_secret_key', ''),
                "tr_id": "TTTC8434R",
                "custtype": "P"
            }
            
            params = {
                "CANO": "50146480",  # 모의투자 계좌번호
                "ACNT_PRDT_CD": "01",
                "AFHR_FLPR_YN": "N",
                "OFL_YN": "",
                "INQR_DVSN": "02",
                "UNPR_DVSN": "01",
                "FUND_STTL_ICLD_YN": "N",
                "FNCG_AMT_AUTO_RDPT_YN": "N",
                "PRCS_DVSN": "01",
                "CTX_AREA_FK100": "",
                "CTX_AREA_NK100": ""
            }
            
            logger.info("   - API 호출 테스트 중...")
            response = requests.get(url, headers=headers, params=params, timeout=10)
            
            if response.status_code == 200:
                result = response.json()
                if result.get('rt_cd') == '0':
                    logger.info(f"   - API 호출 성공: {result.get('msg1', 'OK')}")
                    return True
                else:
                    logger.error(f"   - API 응답 에러: {result}")
                    return False
            else:
                logger.error(f"   - HTTP 오류: {response.status_code}")
                return False
                
        except Exception as e:
            logger.error(f"   - API 테스트 실패: {e}")
            return False


async def main():
    """메인 실행"""
    fixer = TokenSystemFixer()
    
    if not fixer.api_keys:
        print("❌ API 키를 로드할 수 없습니다. Register_Key.md 파일을 확인하세요.")
        return 1
    
    try:
        success = await fixer.fix_token_system()
        
        if success:
            print("\n🎉 토큰 시스템 수정 및 검증 성공!")
            return 0
        else:
            print(f"\n⚠️ 토큰 시스템 수정 실패")
            return 1
            
    except Exception as e:
        logger.error(f"토큰 시스템 수정 중 치명적 오류: {e}")
        return 2


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    print(f"\n종료 코드: {exit_code}")
    sys.exit(exit_code)
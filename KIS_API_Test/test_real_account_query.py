#!/usr/bin/env python3
"""
실제 KIS API 계좌 조회 테스트
- Enhanced Token Manager 사용
- 실제 API 호출 및 응답 확인
- 성능 측정
"""

import asyncio
import json
import logging
import time
import sys
import requests
from pathlib import Path
from datetime import datetime

# 현재 폴더를 Python path에 추가
current_dir = Path(__file__).parent
sys.path.insert(0, str(current_dir))

from register_key_loader import get_api_config, validate_register_key
from enhanced_token_manager import create_enhanced_token_manager

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class RealAPITester:
    """실제 API 호출 테스트"""
    
    def __init__(self):
        self.test_start_time = None
        self.test_results = {}
        self.api_config = None
        self.token_manager = None
        
    async def run_complete_test(self):
        """전체 테스트 실행"""
        print("=== 실제 KIS API 계좌 조회 테스트 ===")
        print(f"테스트 시작 시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("=" * 50)
        
        self.test_start_time = time.time()
        
        try:
            # 1단계: 설정 로드 및 검증
            await self.test_config_loading()
            
            # 2단계: Enhanced Token Manager 초기화
            await self.test_token_manager_init()
            
            # 3단계: 실제 토큰 발급
            await self.test_real_token_request()
            
            # 4단계: 계좌 조회 API 호출
            await self.test_account_query()
            
            # 결과 요약
            await self.show_test_summary()
            
        except Exception as e:
            logger.error(f"테스트 실행 중 오류: {e}")
            print(f"[ERROR] 테스트 실행 실패: {e}")
            return False
        
        return True
    
    async def test_config_loading(self):
        """설정 로드 테스트"""
        print("[STEP 1] Register_Key.md 설정 로드 및 검증...")
        
        try:
            # 설정 유효성 검증
            if not validate_register_key():
                raise ValueError("Register_Key.md 설정이 유효하지 않습니다")
            
            # 모의투자 설정 로드 (실제 API 호출용)
            self.api_config = get_api_config("MOCK")  # 모의투자로 안전하게 테스트
            
            print(f"[OK] 설정 로드 성공")
            print(f"   - 계좌번호: {self.api_config['ACCOUNT_NUM']}")
            print(f"   - APP_KEY: {self.api_config['APP_KEY'][:12]}...")
            print(f"   - REST_URL: {self.api_config['REST_URL']}")
            
            self.test_results['config_loading'] = True
            
        except Exception as e:
            logger.error(f"설정 로드 실패: {e}")
            self.test_results['config_loading'] = False
            raise
    
    async def test_token_manager_init(self):
        """토큰 매니저 초기화 테스트"""
        print("\n[STEP 2] Enhanced Token Manager 초기화...")
        
        try:
            # Enhanced Token Manager 생성
            self.token_manager = create_enhanced_token_manager("MOCK")
            
            # 초기 상태 확인
            health = self.token_manager.get_health_status()
            config_info = health['configuration']
            
            print(f"[OK] 토큰 매니저 초기화 성공")
            print(f"   - 계좌 타입: {config_info['account_type']}")
            print(f"   - 최대 재시도: {config_info['max_retries']}회")
            print(f"   - 자동 갱신: {config_info['preemptive_refresh_minutes']}분 전")
            
            self.test_results['token_manager_init'] = True
            
        except Exception as e:
            logger.error(f"토큰 매니저 초기화 실패: {e}")
            self.test_results['token_manager_init'] = False
            raise
    
    async def test_real_token_request(self):
        """실제 토큰 발급 테스트"""
        print("\n[STEP 3] 실제 KIS API 토큰 발급...")
        
        try:
            token_start = time.time()
            
            # Enhanced Token Manager를 통한 토큰 요청
            access_token = await self.token_manager.get_valid_token_async()
            
            token_end = time.time()
            token_time = token_end - token_start
            
            if access_token:
                print(f"[OK] 토큰 발급 성공")
                print(f"   - 토큰: {access_token[:20]}...")
                print(f"   - 소요시간: {token_time:.3f}초")
                
                # 토큰 매니저 통계 확인
                health = self.token_manager.get_health_status()
                stats = health['performance_stats']
                
                print(f"   - 성공률: {stats['success_rate']}")
                print(f"   - 총 요청: {stats['total_requests']}")
                
                self.test_results['token_request'] = {
                    'success': True,
                    'token': access_token,
                    'response_time': token_time
                }
                
            else:
                print(f"[FAIL] 토큰 발급 실패")
                self.test_results['token_request'] = {
                    'success': False,
                    'error': "토큰 발급 실패"
                }
                raise ValueError("토큰 발급 실패")
                
        except Exception as e:
            logger.error(f"토큰 발급 실패: {e}")
            self.test_results['token_request'] = {
                'success': False,
                'error': str(e)
            }
            raise
    
    async def test_account_query(self):
        """계좌 조회 API 호출 테스트"""
        print("\n[STEP 4] 계좌 조회 API 호출...")
        
        try:
            account_start = time.time()
            
            # 토큰 가져오기
            access_token = self.test_results['token_request']['token']
            
            # 계좌 조회 API 호출
            account_info = await self._call_account_balance_api(access_token)
            
            account_end = time.time()
            account_time = account_end - account_start
            
            if account_info:
                print(f"[OK] 계좌 조회 성공")
                print(f"   - 응답 시간: {account_time:.3f}초")
                
                # 응답 데이터 요약 표시
                if 'output1' in account_info:
                    output1 = account_info['output1'][0] if account_info['output1'] else {}
                    print(f"   - 총 평가금액: {output1.get('tot_evlu_amt', 'N/A')}원")
                    print(f"   - 예수금: {output1.get('dnca_tot_amt', 'N/A')}원")
                    print(f"   - 총 손익: {output1.get('evlu_pfls_smtl_amt', 'N/A')}원")
                
                if 'output2' in account_info and account_info['output2']:
                    print(f"   - 보유 종목 수: {len(account_info['output2'])}개")
                    
                    # 보유 종목 상위 3개만 표시
                    for i, stock in enumerate(account_info['output2'][:3]):
                        stock_name = stock.get('prdt_name', 'N/A')
                        quantity = stock.get('hldg_qty', 'N/A')
                        current_price = stock.get('prpr', 'N/A')
                        print(f"      {i+1}. {stock_name}: {quantity}주, {current_price}원")
                
                self.test_results['account_query'] = {
                    'success': True,
                    'response_time': account_time,
                    'data': account_info
                }
                
            else:
                print(f"[FAIL] 계좌 조회 실패")
                self.test_results['account_query'] = {
                    'success': False,
                    'error': "계좌 조회 API 응답 없음"
                }
                
        except Exception as e:
            logger.error(f"계좌 조회 실패: {e}")
            self.test_results['account_query'] = {
                'success': False,
                'error': str(e)
            }
            raise
    
    async def _call_account_balance_api(self, access_token: str) -> dict:
        """계좌 잔고 조회 API 호출"""
        try:
            # API 엔드포인트 및 헤더 설정
            url = f"{self.api_config['REST_URL']}/uapi/domestic-stock/v1/trading/inquire-balance"
            
            headers = {
                "Content-Type": "application/json",
                "authorization": f"Bearer {access_token}",
                "appkey": self.api_config['APP_KEY'],
                "appsecret": self.api_config['APP_SECRET'],
                "tr_id": "TTTC8434R",  # 모의투자 계좌잔고조회
            }
            
            # 요청 파라미터
            params = {
                "CANO": self.api_config['ACCOUNT_NUM'][:8],   # 계좌번호 앞 8자리
                "ACNT_PRDT_CD": self.api_config['ACCOUNT_NUM'][8:],  # 계좌번호 뒤 2자리
                "AFHR_FLPR_YN": "N",    # 시간외단일가여부
                "OFL_YN": "",           # 오프라인여부
                "INQR_DVSN": "02",      # 조회구분(01:대출일별, 02:종목별)
                "UNPR_DVSN": "01",      # 단가구분
                "FUND_STTL_ICLD_YN": "N",  # 펀드결제분포함여부
                "FNCG_AMT_AUTO_RDPT_YN": "N",  # 융자금액자동상환여부
                "PRCS_DVSN": "00",      # 처리구분
                "CTX_AREA_FK100": "",   # 연속조회검색조건100
                "CTX_AREA_NK100": ""    # 연속조회키100
            }
            
            # API 호출
            response = requests.get(url, headers=headers, params=params, timeout=30)
            
            print(f"[DEBUG] API 호출 - 상태코드: {response.status_code}")
            
            if response.status_code == 200:
                return response.json()
            else:
                error_msg = f"API 호출 실패: HTTP {response.status_code}"
                try:
                    error_detail = response.json()
                    error_msg += f" - {error_detail}"
                except:
                    error_msg += f" - {response.text}"
                
                logger.error(error_msg)
                return None
                
        except Exception as e:
            logger.error(f"계좌 조회 API 호출 오류: {e}")
            return None
    
    async def show_test_summary(self):
        """테스트 결과 요약"""
        total_time = time.time() - self.test_start_time
        
        print("\n" + "=" * 50)
        print("[SUMMARY] 실제 API 테스트 결과 요약")
        print("=" * 50)
        
        # 전체 결과 통계
        total_tests = len(self.test_results)
        passed_tests = sum(1 for result in self.test_results.values() 
                          if (isinstance(result, bool) and result) or 
                             (isinstance(result, dict) and result.get('success', False)))
        
        success_rate = (passed_tests / total_tests * 100) if total_tests > 0 else 0
        
        print(f"전체 테스트: {total_tests}개")
        print(f"통과 테스트: {passed_tests}개")
        print(f"성공률: {success_rate:.1f}%")
        print(f"총 소요시간: {total_time:.3f}초")
        
        # 단계별 결과
        print(f"\n[DETAIL] 단계별 결과:")
        
        steps = [
            ('config_loading', '설정 로드'),
            ('token_manager_init', '토큰 매니저 초기화'),
            ('token_request', '토큰 발급'),
            ('account_query', '계좌 조회')
        ]
        
        for key, name in steps:
            if key in self.test_results:
                result = self.test_results[key]
                if isinstance(result, bool):
                    status = "[OK]" if result else "[FAIL]"
                elif isinstance(result, dict):
                    status = "[OK]" if result.get('success', False) else "[FAIL]"
                    if 'response_time' in result:
                        status += f" ({result['response_time']:.3f}초)"
                else:
                    status = "[UNKNOWN]"
                
                print(f"   - {name}: {status}")
        
        # 성능 개선 효과
        if 'token_request' in self.test_results and self.test_results['token_request'].get('success'):
            token_time = self.test_results['token_request']['response_time']
            print(f"\n[PERFORMANCE] 성능 측정 결과:")
            print(f"   - 토큰 발급 시간: {token_time:.3f}초")
            
            if 'account_query' in self.test_results and self.test_results['account_query'].get('success'):
                account_time = self.test_results['account_query']['response_time']
                print(f"   - 계좌 조회 시간: {account_time:.3f}초")
                print(f"   - 총 API 응답시간: {token_time + account_time:.3f}초")
        
        # 최종 결론
        if success_rate >= 80:
            print(f"\n[SUCCESS] Enhanced Token Manager 실제 API 테스트 성공!")
            print(f"모든 주요 기능이 정상적으로 작동합니다.")
        else:
            print(f"\n[WARNING] 일부 테스트 실패")
            print(f"실패한 단계를 확인하고 수정이 필요합니다.")


async def main():
    """메인 테스트 실행"""
    tester = RealAPITester()
    
    try:
        result = await tester.run_complete_test()
        return result
    except Exception as e:
        logger.error(f"메인 테스트 실행 오류: {e}")
        print(f"\n[ERROR] 테스트 실행 중 오류 발생: {e}")
        return False


if __name__ == "__main__":
    print("Enhanced Token Manager 실제 API 테스트를 시작합니다...")
    
    result = asyncio.run(main())
    
    if result:
        print("\n[COMPLETE] 실제 API 테스트 완료!")
    else:
        print("\n[FAILED] 실제 API 테스트 실패!")
        sys.exit(1)
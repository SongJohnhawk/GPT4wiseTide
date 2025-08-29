#!/usr/bin/env python3
"""
토큰 발급만 테스트 (간소화 버전)
"""

import requests
import json
import time
import sys
from pathlib import Path

# 현재 폴더를 Python path에 추가
current_dir = Path(__file__).parent
sys.path.insert(0, str(current_dir))

from register_key_loader import get_api_config

def test_direct_token_request():
    """직접 토큰 요청 테스트"""
    try:
        print("=== 직접 토큰 발급 테스트 ===")
        
        # 설정 로드
        print("[STEP 1] 설정 로드...")
        config = get_api_config("MOCK")
        print(f"[OK] APP_KEY: {config['APP_KEY'][:12]}...")
        print(f"[OK] REST_URL: {config['REST_URL']}")
        
        # 토큰 발급 요청
        print("\n[STEP 2] 토큰 발급 요청...")
        
        url = f"{config['REST_URL']}/oauth2/tokenP"
        
        headers = {
            "Content-Type": "application/json"
        }
        
        data = {
            "grant_type": "client_credentials",
            "appkey": config['APP_KEY'],
            "appsecret": config['APP_SECRET']
        }
        
        print("[INFO] API 요청 시작...")
        start_time = time.time()
        
        response = requests.post(url, headers=headers, json=data, timeout=30)
        
        end_time = time.time()
        response_time = end_time - start_time
        
        print(f"[INFO] 응답 시간: {response_time:.3f}초")
        print(f"[INFO] 상태 코드: {response.status_code}")
        
        if response.status_code == 200:
            token_data = response.json()
            
            print("[SUCCESS] 토큰 발급 성공!")
            print(f"   - access_token: {token_data.get('access_token', 'N/A')[:30]}...")
            print(f"   - token_type: {token_data.get('token_type', 'N/A')}")
            print(f"   - expires_in: {token_data.get('expires_in', 'N/A')}초")
            
            return token_data
        else:
            print(f"[ERROR] 토큰 발급 실패: HTTP {response.status_code}")
            try:
                error_data = response.json()
                print(f"[ERROR] 상세 오류: {json.dumps(error_data, indent=2, ensure_ascii=False)}")
            except:
                print(f"[ERROR] 응답 내용: {response.text}")
            return None
            
    except Exception as e:
        print(f"[ERROR] 토큰 발급 중 오류: {e}")
        return None

def test_account_balance(access_token):
    """계좌 잔고 조회 테스트"""
    try:
        print("\n=== 계좌 잔고 조회 테스트 ===")
        
        config = get_api_config("MOCK")
        
        url = f"{config['REST_URL']}/uapi/domestic-stock/v1/trading/inquire-balance"
        
        headers = {
            "Content-Type": "application/json",
            "authorization": f"Bearer {access_token}",
            "appkey": config['APP_KEY'],
            "appsecret": config['APP_SECRET'],
            "tr_id": "VTTC8434R"  # 모의투자 계좌잔고조회 (가상거래)
        }
        
        params = {
            "CANO": config['ACCOUNT_NUM'][:8],
            "ACNT_PRDT_CD": config['ACCOUNT_NUM'][8:],
            "AFHR_FLPR_YN": "N",
            "OFL_YN": "",
            "INQR_DVSN": "02",
            "UNPR_DVSN": "01",
            "FUND_STTL_ICLD_YN": "N",
            "FNCG_AMT_AUTO_RDPT_YN": "N",
            "PRCS_DVSN": "00",
            "CTX_AREA_FK100": "",
            "CTX_AREA_NK100": ""
        }
        
        print("[INFO] 계좌 조회 요청 시작...")
        start_time = time.time()
        
        response = requests.get(url, headers=headers, params=params, timeout=30)
        
        end_time = time.time()
        response_time = end_time - start_time
        
        print(f"[INFO] 응답 시간: {response_time:.3f}초")
        print(f"[INFO] 상태 코드: {response.status_code}")
        
        if response.status_code == 200:
            account_data = response.json()
            
            print("[SUCCESS] 계좌 조회 성공!")
            
            # rt_cd 확인
            if account_data.get('rt_cd') == '0':
                print("[OK] 정상 응답 (rt_cd: 0)")
                
                # 계좌 요약 정보
                if 'output1' in account_data and account_data['output1']:
                    output1 = account_data['output1'][0]
                    print(f"   - 총 평가금액: {output1.get('tot_evlu_amt', 'N/A')}원")
                    print(f"   - 예수금: {output1.get('dnca_tot_amt', 'N/A')}원")
                    print(f"   - 총 손익: {output1.get('evlu_pfls_smtl_amt', 'N/A')}원")
                
                # 보유 종목
                if 'output2' in account_data and account_data['output2']:
                    print(f"   - 보유 종목 수: {len(account_data['output2'])}개")
                    
                    for i, stock in enumerate(account_data['output2'][:3]):
                        name = stock.get('prdt_name', 'N/A')
                        qty = stock.get('hldg_qty', 'N/A')
                        price = stock.get('prpr', 'N/A')
                        print(f"      {i+1}. {name}: {qty}주, {price}원")
                else:
                    print("   - 보유 종목 없음")
            else:
                print(f"[WARNING] 응답 코드: {account_data.get('rt_cd')} - {account_data.get('msg1', 'N/A')}")
            
            return account_data
            
        else:
            print(f"[ERROR] 계좌 조회 실패: HTTP {response.status_code}")
            try:
                error_data = response.json()
                print(f"[ERROR] 상세 오류: {json.dumps(error_data, indent=2, ensure_ascii=False)}")
            except:
                print(f"[ERROR] 응답 내용: {response.text}")
            return None
            
    except Exception as e:
        print(f"[ERROR] 계좌 조회 중 오류: {e}")
        return None

def main():
    """메인 테스트 실행"""
    print("KIS API 직접 호출 테스트 시작...")
    
    # 1단계: 토큰 발급
    token_data = test_direct_token_request()
    if not token_data:
        print("\n[FAILED] 토큰 발급 실패로 테스트 중단")
        return False
    
    # 2단계: 계좌 조회
    access_token = token_data.get('access_token')
    if access_token:
        account_data = test_account_balance(access_token)
        if account_data:
            print("\n[SUCCESS] 모든 API 호출 성공!")
            return True
        else:
            print("\n[FAILED] 계좌 조회 실패")
            return False
    else:
        print("\n[FAILED] 유효한 토큰 없음")
        return False

if __name__ == "__main__":
    result = main()
    if result:
        print("\n=== 테스트 완료 ===")
        print("Enhanced Token Manager의 기반이 되는 API 연결이 정상 작동합니다!")
    else:
        print("\n=== 테스트 실패 ===")
        print("API 연결에 문제가 있습니다.")
        sys.exit(1)
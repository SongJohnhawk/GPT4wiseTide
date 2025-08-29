#!/usr/bin/env python3
"""
KIS API 직접 토큰 요청 테스트
공식 API 스펙에 맞춰 직접 HTTP 요청으로 토큰 발급 테스트
"""

import sys
import requests
import json
from pathlib import Path

# 프로젝트 루트를 Python path에 추가
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

def test_direct_token_request():
    """직접 HTTP 요청으로 토큰 발급 테스트"""
    print("=== KIS API 직접 토큰 요청 테스트 ===")
    
    try:
        # Register_Key.md에서 설정 로드
        from KIS_API_Test.register_key_loader import get_api_config
        
        print("[STEP 1] Register_Key.md에서 설정 로드...")
        config = get_api_config("MOCK")
        
        print(f"[OK] 설정 로드 성공")
        print(f"   - APP_KEY: {config['APP_KEY'][:12]}...")
        print(f"   - REST_URL: {config['REST_URL']}")
        
        print("\n[STEP 2] KIS API 직접 토큰 요청...")
        
        # 공식 API 스펙에 맞는 요청
        url = f"{config['REST_URL']}/oauth2/tokenP"
        
        headers = {
            "Content-Type": "application/json"
        }
        
        data = {
            "grant_type": "client_credentials",
            "appkey": config["APP_KEY"],
            "appsecret": config["APP_SECRET"]
        }
        
        print(f"[INFO] 요청 URL: {url}")
        print(f"[INFO] 요청 데이터: grant_type={data['grant_type']}, appkey={data['appkey'][:12]}...")
        
        # API 호출
        print("[INFO] API 호출 시작...")
        try:
            response = requests.post(url, headers=headers, json=data, timeout=30)
            
            print(f"[INFO] 응답 상태 코드: {response.status_code}")
            print(f"[INFO] 응답 헤더: {dict(response.headers)}")
            
            if response.status_code == 200:
                token_data = response.json()
                print(f"[SUCCESS] 토큰 발급 성공!")
                print(f"   - access_token: {token_data.get('access_token', 'N/A')[:30]}...")
                print(f"   - token_type: {token_data.get('token_type', 'N/A')}")
                print(f"   - expires_in: {token_data.get('expires_in', 'N/A')}")
                
                # 전체 응답 데이터 표시
                print(f"\n[DEBUG] 전체 응답 데이터:")
                for key, value in token_data.items():
                    if key == 'access_token' and value:
                        print(f"   - {key}: {value[:30]}... (길이: {len(value)})")
                    else:
                        print(f"   - {key}: {value}")
                
                return True
            else:
                print(f"[FAILED] 토큰 발급 실패: HTTP {response.status_code}")
                try:
                    error_data = response.json()
                    print(f"[ERROR] 응답 데이터: {json.dumps(error_data, indent=2, ensure_ascii=False)}")
                except:
                    print(f"[ERROR] 응답 텍스트: {response.text}")
                return False
                
        except requests.RequestException as req_error:
            print(f"[FAILED] 네트워크 오류: {req_error}")
            return False
        except Exception as api_error:
            print(f"[FAILED] API 호출 오류: {api_error}")
            return False
            
    except ImportError as import_error:
        print(f"[FAILED] 모듈 import 실패: {import_error}")
        return False
    except Exception as e:
        print(f"[FAILED] 설정 로드 실패: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """메인 테스트 실행"""
    try:
        result = test_direct_token_request()
        
        print("\n" + "="*60)
        if result:
            print("[SUCCESS] KIS API 직접 토큰 요청 테스트 성공!")
            print("API 연결과 토큰 발급이 정상적으로 작동합니다.")
            sys.exit(0)
        else:
            print("[FAILED] KIS API 직접 토큰 요청 테스트 실패!")
            print("API 연결이나 설정에 문제가 있습니다.")
            sys.exit(1)
            
    except KeyboardInterrupt:
        print("\n사용자에 의해 테스트가 중단되었습니다.")
        sys.exit(1)
    except Exception as e:
        print(f"테스트 실행 오류: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
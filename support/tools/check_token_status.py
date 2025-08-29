#!/usr/bin/env python3
"""
메인 프로그램의 토큰 관리자 상태 확인
"""

import sys
from pathlib import Path
# 프로젝트 루트를 Python 경로에 추가
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

def check_token_status():
    """토큰 관리자 상태 확인"""
    print("=" * 60)
    print("tideWise 토큰 관리자 상태 확인")
    print("=" * 60)
    
    try:
        from support.token_manager import TokenManagerFactory
        from support.authoritative_register_key_loader import get_authoritative_loader
        
        # 설정 파일 로드 (Register_Key.md 우선)
        try:
            reader = get_authoritative_loader()
            real_config_data = reader.get_fresh_config("REAL")
            mock_config_data = reader.get_fresh_config("MOCK")
            url_config_data = reader.get_fresh_urls()
            
            # 실전투자 설정 구성
            real_config = {
                'CANO': real_config_data.get('account_number', ''),
                'ACNT_PRDT_CD': '01',
                'ACNT_PASS_WD': real_config_data.get('account_password', ''),
                'APP_KEY': real_config_data.get('app_key', ''),
                'APP_SECRET': real_config_data.get('app_secret', '')
            }
            
            # 모의투자 설정 구성
            mock_config = {
                'CANO': mock_config_data.get('account_number', ''),
                'ACNT_PRDT_CD': '01',
                'ACNT_PASS_WD': mock_config_data.get('account_password', ''),
                'APP_KEY': mock_config_data.get('app_key', ''),
                'APP_SECRET': mock_config_data.get('app_secret', '')
            }
            
            # URL 설정 - Register_Key.md에서만 로드, 백업 없음
            real_base_url = url_config_data.get('real_rest')
            mock_base_url = url_config_data.get('mock_rest')
            
            if not real_base_url or not mock_base_url:
                raise Exception("Register_Key.md에서 URL 정보를 찾을 수 없습니다")
            
            print("Register_Key.md에서 설정 로드 완료")
            
        except Exception as register_error:
            print(f"Register_Key.md 로드 실패: {register_error}")
            print("기존 YAML 파일로 백업...")
            
            # Register_Key.md에서 설정 로드 (백업)
            register_key_path = Path(__file__).parent.parent.parent / "Policy" / "Register_Key" / "Register_Key.md"
            if not register_key_path.exists():
                raise FileNotFoundError("Register_Key.md 파일을 찾을 수 없습니다")
            
            # Register_Key.md 파싱하여 설정 로드
            with open(register_key_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # 실전투자 정보 추출
            real_lines = []
            mock_lines = []
            in_real_section = False
            in_mock_section = False
            
            for line in content.split('\n'):
                if '실전투자 계좌 정보' in line:
                    in_real_section = True
                    in_mock_section = False
                elif '모의투자 계좌 정보' in line:
                    in_mock_section = True
                    in_real_section = False
                elif line.startswith('###') or line.startswith('##'):
                    in_real_section = False
                    in_mock_section = False
                elif in_real_section and line.strip() and not line.startswith('#'):
                    real_lines.append(line.strip())
                elif in_mock_section and line.strip() and not line.startswith('#'):
                    mock_lines.append(line.strip())
            
            # 설정 파싱
            def parse_account_info(lines):
                config = {}
                for line in lines:
                    if '계좌번호:' in line:
                        config['CANO'] = line.split(':')[1].strip()
                    elif '계좌 비밀번호:' in line:
                        config['ACNT_PASS_WD'] = line.split(':')[1].strip()
                        config['ACNT_PRDT_CD'] = '01'
                    elif 'APP KEY:' in line:
                        config['APP_KEY'] = line.split(':')[1].strip()
                    elif 'APP Secret KEY:' in line:
                        config['APP_SECRET'] = line.split(':')[1].strip()
                return config
            
            real_config = parse_account_info(real_lines)
            mock_config = parse_account_info(mock_lines)
            
            # Register_Key.md 백업 실패 시 즉시 종료
            raise Exception("Register_Key.md 파일이 필요합니다. 하드코딩된 백업은 제거되었습니다.")
        
        # 실전투자 토큰 관리자 확인
        print("\n1. 실전투자 토큰 관리자")
        print("-" * 40)
        
        real_token_manager = TokenManagerFactory.get_token_manager(
            account_type="REAL",
            api_config=real_config,
            base_url=real_base_url
        )
        
        real_token_info = real_token_manager.get_token_info()
        if real_token_info:
            print(f"계좌 타입: {real_token_info['account_type']}")
            print(f"발급 시간: {real_token_info['issued_at'].strftime('%Y-%m-%d %H:%M:%S')}")
            print(f"만료 시간: {real_token_info['expires_at'].strftime('%Y-%m-%d %H:%M:%S')}")
            print(f"만료 여부: {'만료됨' if real_token_info['is_expired'] else '유효함'}")
            print(f"만료 임박: {'예 (30분 내)' if real_token_info['is_near_expiry'] else '아니오'}")
            print(f"자정 경과: {'예' if real_token_info['is_midnight_passed'] else '아니오'}")
            
            # 토큰 테스트
            token = real_token_manager.get_valid_token()
            print(f"토큰 획득: {'성공' if token else '실패'}")
            if token:
                print(f"토큰 길이: {len(token)} 문자")
        else:
            print("저장된 토큰 없음")
        
        # 모의투자 토큰 관리자 확인
        print("\n2. 모의투자 토큰 관리자")
        print("-" * 40)
        
        mock_token_manager = TokenManagerFactory.get_token_manager(
            account_type="MOCK",
            api_config=mock_config,
            base_url=mock_base_url
        )
        
        mock_token_info = mock_token_manager.get_token_info()
        if mock_token_info:
            print(f"계좌 타입: {mock_token_info['account_type']}")
            print(f"발급 시간: {mock_token_info['issued_at'].strftime('%Y-%m-%d %H:%M:%S')}")
            print(f"만료 시간: {mock_token_info['expires_at'].strftime('%Y-%m-%d %H:%M:%S')}")
            print(f"만료 여부: {'만료됨' if mock_token_info['is_expired'] else '유효함'}")
            print(f"만료 임박: {'예 (30분 내)' if mock_token_info['is_near_expiry'] else '아니오'}")
            print(f"자정 경과: {'예' if mock_token_info['is_midnight_passed'] else '아니오'}")
            
            # 토큰 테스트
            token = mock_token_manager.get_valid_token()
            print(f"토큰 획득: {'성공' if token else '실패'}")
            if token:
                print(f"토큰 길이: {len(token)} 문자")
        else:
            print("저장된 토큰 없음")
        
        # 토큰 파일 확인
        print("\n3. 토큰 파일 상태")
        print("-" * 40)
        
        token_dir = Path(".token_cache")
        if token_dir.exists():
            token_files = list(token_dir.glob("*.json"))
            print(f"토큰 파일 개수: {len(token_files)}개")
            
            for token_file in sorted(token_files):
                file_stat = token_file.stat()
                mod_time = file_stat.st_mtime
                from datetime import datetime
                mod_datetime = datetime.fromtimestamp(mod_time)
                print(f"  {token_file.name} (수정: {mod_datetime.strftime('%Y-%m-%d %H:%M:%S')})")
        else:
            print("토큰 캐시 디렉토리 없음")
        
        # API 커넥터 테스트
        print("\n4. API 커넥터 테스트")
        print("-" * 40)
        
        try:
            from support.api_connector import KISAPIConnector
            
            # 실전투자 API 커넥터
            print("실전투자 API 커넥터 테스트...")
            real_api = KISAPIConnector(is_mock=False)
            real_token = real_api.get_access_token()
            print(f"  실전투자 토큰 획득: {'성공' if real_token else '실패'}")
            
            # 모의투자 API 커넥터
            print("모의투자 API 커넥터 테스트...")
            mock_api = KISAPIConnector(is_mock=True)
            mock_token = mock_api.get_access_token()
            print(f"  모의투자 토큰 획득: {'성공' if mock_token else '실패'}")
            
        except Exception as e:
            print(f"  API 커넥터 테스트 실패: {e}")
        
        print("\n" + "=" * 60)
        print("토큰 관리자 상태 확인 완료")
        print("=" * 60)
        
        print("\n토큰 관리 원칙:")
        print("- 기존 토큰 재사용 (새 토큰 발급 최소화)")
        print("- 자정 후 최초 접속 시에만 재발급")
        print("- 밤 11시 55분까지 사용")
        print("- 만료 30분 전 자동 갱신")
        
    except Exception as e:
        print(f"오류 발생: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    check_token_status()
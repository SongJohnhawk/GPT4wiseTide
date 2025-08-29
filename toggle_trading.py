#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
tideWise 매수/매도 실행 토글 스크립트
매수/매도 실행을 활성화/비활성화하는 편리한 도구
"""

import json
import sys
from pathlib import Path

# UTF-8 인코딩 설정
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8')

def load_config():
    """설정 파일 로드"""
    config_path = Path("support/trading_config.json")
    if not config_path.exists():
        print("[ERROR] trading_config.json 파일을 찾을 수 없습니다!")
        return None
    
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print(f"[ERROR] 설정 파일 로드 실패: {e}")
        return None

def save_config(config):
    """설정 파일 저장"""
    config_path = Path("support/trading_config.json")
    try:
        with open(config_path, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=2, ensure_ascii=False)
        return True
    except Exception as e:
        print(f"[ERROR] 설정 파일 저장 실패: {e}")
        return False

def show_current_status(config):
    """현재 상태 표시"""
    trading_exec = config.get('trading_execution', {})
    buy_enabled = trading_exec.get('enable_buy_orders', True)
    sell_enabled = trading_exec.get('enable_sell_orders', True)
    simulation = trading_exec.get('simulation_mode', False)
    
    print("\n" + "="*50)
    print("[STATUS] 현재 매매 실행 상태")
    print("="*50)
    print(f"매수 실행: {'활성화' if buy_enabled else '비활성화'}")
    print(f"매도 실행: {'활성화' if sell_enabled else '비활성화'}")
    print(f"시뮬레이션 모드: {'켜짐' if simulation else '꺼짐'}")
    print("="*50)

def toggle_trading(config, buy_status=None, sell_status=None):
    """매매 실행 상태 토글"""
    if 'trading_execution' not in config:
        config['trading_execution'] = {}
    
    trading_exec = config['trading_execution']
    
    if buy_status is not None:
        trading_exec['enable_buy_orders'] = buy_status
        print(f"매수 실행: {'활성화' if buy_status else '비활성화'}로 변경")
    
    if sell_status is not None:
        trading_exec['enable_sell_orders'] = sell_status
        print(f"매도 실행: {'활성화' if sell_status else '비활성화'}로 변경")
    
    # 시뮬레이션 모드 자동 설정
    both_disabled = not trading_exec.get('enable_buy_orders', True) and not trading_exec.get('enable_sell_orders', True)
    trading_exec['simulation_mode'] = both_disabled
    trading_exec['log_simulated_trades'] = both_disabled
    
    if both_disabled:
        trading_exec['comment'] = "매수/매도 비활성화 - 시뮬레이션만 수행"
        print("[INFO] 시뮬레이션 모드로 자동 설정됨")
    else:
        trading_exec['comment'] = "매수/매도 실행 활성화"
        print("[INFO] 실제 매매 실행 모드")

def main():
    """메인 실행 함수"""
    config = load_config()
    if not config:
        return
    
    show_current_status(config)
    
    if len(sys.argv) == 1:
        # 인터랙티브 모드
        print("\n[MENU] 매매 실행 설정 변경")
        print("1. 매수/매도 모두 활성화")
        print("2. 매수/매도 모두 비활성화 (현재 설정)")
        print("3. 매수만 활성화")
        print("4. 매도만 활성화")
        print("5. 현재 상태 유지")
        
        try:
            choice = input("\n선택 (1-5): ").strip()
            
            if choice == "1":
                toggle_trading(config, buy_status=True, sell_status=True)
            elif choice == "2":
                toggle_trading(config, buy_status=False, sell_status=False)
            elif choice == "3":
                toggle_trading(config, buy_status=True, sell_status=False)
            elif choice == "4":
                toggle_trading(config, buy_status=False, sell_status=True)
            elif choice == "5":
                print("[INFO] 현재 상태를 유지합니다.")
                return
            else:
                print("[ERROR] 잘못된 선택입니다.")
                return
                
        except KeyboardInterrupt:
            print("\n\n[STOP] 취소되었습니다.")
            return
    else:
        # 명령줄 모드
        if len(sys.argv) >= 2:
            command = sys.argv[1].lower()
            
            if command == "enable":
                toggle_trading(config, buy_status=True, sell_status=True)
            elif command == "disable":
                toggle_trading(config, buy_status=False, sell_status=False)
            elif command == "status":
                return  # 이미 상태를 표시했음
            else:
                print("[ERROR] 사용법: python toggle_trading.py [enable|disable|status]")
                return
    
    # 설정 저장
    if save_config(config):
        print("\n[SUCCESS] 설정이 저장되었습니다!")
        print("[INFO] tideWise를 재시작하면 새 설정이 적용됩니다.")
        show_current_status(config)
    else:
        print("\n[ERROR] 설정 저장 실패!")

if __name__ == "__main__":
    print("tideWise 매매 실행 토글 도구")
    main()
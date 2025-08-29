#!/usr/bin/env python3
"""
SetupManager - tideWise 설정 관리 클래스
run.py에서 분리된 설정 관련 기능들을 통합 관리
"""

import subprocess
from pathlib import Path
from typing import Optional


class SetupManager:
    """설정 파일 편집 및 관리를 담당하는 클래스"""
    
    def __init__(self, project_root: Path):
        """
        SetupManager 초기화
        
        Args:
            project_root: 프로젝트 루트 디렉토리 경로
        """
        self.project_root = Path(project_root)
    
    async def show_setup_menu(self):
        """Setup 메뉴 - 실제 설정 파일 편집 기능"""
        while True:
            print("\n[ Setup - 설정 파일 편집 ]")
            print("-" * 50)
            print("1. Register_Key (통합 연동정보 관리)")
            print("2. 지정테마 설정")
            print("3. 지정종목 설정")
            print("4. 장마감 체크 설정")
            print("0. 메인 메뉴로 돌아가기")
            print("-" * 50)
            
            try:
                choice = input("\n선택하세요: ").strip()
                
                if choice == '0':
                    break
                elif choice == '1':
                    await self.edit_register_key_settings()
                elif choice == '2':
                    await self.edit_theme_settings()
                elif choice == '3':
                    await self.edit_stock_settings()
                elif choice == '4':
                    await self.edit_market_close_settings()
                else:
                    print("\n잘못된 선택입니다.")
                    
            except (KeyboardInterrupt, EOFError):
                print("\n메인 메뉴로 돌아갑니다.")
                break
    
    async def edit_register_key_settings(self):
        """Register_Key 통합 연동정보 설정 (암호화/복호화 지원)"""
        print("\n[ Register_Key - 통합 연동정보 관리 ]")
        print("모든 API 키, 계좌 정보, 연동 토큰을 한 곳에서 관리합니다.")
        print("📝 파일은 일반 텍스트로 저장됩니다.")
        print("-" * 60)
        
        try:
            register_key_file = self.project_root / "Policy" / "Register_Key" / "Register_Key.md"
            
            # 1. 일반 텍스트 파일 읽기
            print("📄 Register_Key.md 파일 읽기 중...")
            try:
                with open(register_key_file, 'r', encoding='utf-8', errors='ignore') as f:
                    plaintext_content = f.read().strip()
            except FileNotFoundError:
                plaintext_content = None
            
            if not plaintext_content:
                print("❌ Register_Key.md 파일이 존재하지 않거나 비어있습니다.")
                print(f"파일 위치: {register_key_file}")
                print("\n템플릿 파일을 생성하시겠습니까? (y/n): ", end="")
                
                create_template = input().strip().lower()
                if create_template == 'y':
                    plaintext_content = self._create_register_key_template()
                else:
                    return
            
            # 2. 임시 파일에 복호화된 내용 저장
            temp_file = register_key_file.parent / "Register_Key_TEMP.md"
            
            with open(temp_file, 'w', encoding='utf-8') as f:
                f.write(plaintext_content)
            
            print(f"📝 임시 편집 파일 생성: {temp_file}")
            print("\n포함된 연동 정보:")
            print("• 한국투자증권 실전투자 계좌 (APP KEY, 계좌번호, 비밀번호)")
            print("• 한국투자증권 모의투자 계좌 (APP KEY, 계좌번호, 비밀번호)")
            print("• API 호출 URL (실전/모의투자 REST, Websocket)")
            print("• KRX OPEN API 인증키")  
            print("• 텔레그램 봇 토큰 및 채팅 ID")
            print("-" * 60)
            print("⚠️  주의: 편집 완료 후 반드시 저장하고 메모장을 닫아주세요!")
            
            # 3. 메모장으로 임시 파일 열기
            try:
                subprocess.run(['notepad.exe', str(temp_file)], check=False)
                
                while True:
                    print("\n편집을 완료하셨습니까?")
                    print("1. 저장하고 암호화")
                    print("2. 취소 (변경사항 무시)")
                    choice = input("선택 (1/2): ").strip()
                    
                    if choice == '1':
                        # 4. 편집된 내용 읽기
                        try:
                            with open(temp_file, 'r', encoding='utf-8') as f:
                                edited_content = f.read()
                            
                            # 5. 일반 텍스트 파일로 저장
                            print("📄 편집된 내용을 저장 중...")
                            try:
                                with open(register_key_file, 'w', encoding='utf-8') as f:
                                    f.write(edited_content)
                                print("✅ Register_Key.md 파일이 저장되었습니다.")
                                print("✅ 연동정보가 성공적으로 업데이트되었습니다.")
                                print("\n프로그램을 재시작해야 변경한 연동정보가 적용됩니다.")
                                print("tideWise를 종료하고 다시 시작해 주세요.")
                            except Exception as save_error:
                                print("❌ 파일 인코딩 저장 실패")
                        except Exception as e:
                            print(f"❌ 편집된 파일 읽기 실패: {e}")
                        break
                        
                    elif choice == '2':
                        print("편집이 취소되었습니다.")
                        break
                    else:
                        print("잘못된 선택입니다.")
                
                # 6. 임시 파일 정리
                try:
                    if temp_file.exists():
                        temp_file.unlink()
                        print("🧹 임시 편집 파일이 안전하게 삭제되었습니다.")
                except Exception:
                    pass
                    
            except Exception as e:
                print(f"[ERROR] 메모장 실행 실패: {e}")
                print(f"직접 파일을 열어서 편집하세요: {temp_file}")
                print("[주의] 편집 완료 후 이 메뉴를 다시 선택하여 암호화 저장하세요.")
                
        except Exception as e:
            print(f"[ERROR] Register_Key 편집 시스템 오류: {e}")
    
    def _create_register_key_template(self) -> str:
        """Register_Key.md 템플릿 생성"""
        template = '''# tideWise 통합 연동 정보 관리

이 파일은 tideWise 시스템의 모든 API 키, 계좌 정보, 연동 토큰을 통합 관리하는 파일입니다.

> **[주의] 보안 주의사항**
> - 이 파일은 민감한 정보를 포함하고 있습니다.
> - 절대 외부에 공유하거나 공개 저장소에 업로드하지 마세요.
> - 수정 후 반드시 tideWise를 재시작해야 변경사항이 적용됩니다.

---

## 한국투자증권 연동 정보

### 실전투자 계좌
```
APP KEY: [여기에 실전투자 APP KEY 입력]
APP SECRET: [여기에 실전투자 APP SECRET 입력]  
계좌번호: [여기에 실전투자 계좌번호 입력]
계좌비밀번호: [여기에 실전투자 계좌비밀번호 입력]
```

### 모의투자 계좌  
```
APP KEY: [여기에 모의투자 APP KEY 입력]
APP SECRET: [여기에 모의투자 APP SECRET 입력]
계좌번호: [여기에 모의투자 계좌번호 입력] 
계좌비밀번호: [여기에 모의투자 계좌비밀번호 입력]
```

### API 호출 URL
```
실전투자 REST API: https://openapi.koreainvestment.com:9443
모의투자 REST API: https://openapivts.koreainvestment.com:29443  
실전투자 웹소켓: ws://ops.koreainvestment.com:21000
모의투자 웹소켓: ws://ops.koreainvestment.com:31000
```

---

## KRX OPEN API 연동 정보

### KRX 인증키
```
인증키: [여기에 KRX OPEN API 인증키 입력]
```

---

## 텔레그램 연동 정보

### 봇 정보
```
Bot URL: t.me/KAutotrading_Bot
```

### 연동 토큰
```
Bot Token: [여기에 텔레그램 봇 토큰 입력]
Chat ID: [여기에 텔레그램 채팅 ID 입력]
```

### 텔레그램 기능
- 자동매매 시작/종료 알림
- 매매 신호 실시간 알림
- 수익/손실 현황 알림
- 시스템 오류 알림

---

**설정 방법**:
1. 위의 템플릿에서 `[여기에...]` 부분을 실제 정보로 교체하세요.
2. 한국투자증권에서 발급받은 실제 API 키와 계좌 정보를 입력하세요.
3. KRX에서 발급받은 실제 API 키를 입력하세요.
4. 텔레그램 봇을 생성하고 실제 토큰 정보를 입력하세요.

**마지막 업데이트**: 2024-12-19
**다음 점검 예정**: 2025-01-19'''
        return template
    
    async def edit_theme_settings(self):
        """지정테마 설정 (사용자정의 테마설정)"""
        print("\n[ 지정테마 설정 ]")
        
        theme_file = Path(__file__).parent / "user_theme_config.json"
        
        if theme_file.exists():
            print(f"테마 파일 위치: {theme_file}")
            print("메모장으로 테마 파일을 열어서 편집합니다...")
            
            # 윈도우 메모장으로 파일 열기
            try:
                subprocess.run(['notepad.exe', str(theme_file)], check=False)
                input("\n테마 편집을 완료하셨다면 Enter를 누르세요...")
                print("\n설정이 완료되었습니다. tideWise를 종료하고 다시 시작하면 새 설정이 적용됩니다.")
            except Exception as e:
                print(f"메모장 실행 실패: {e}")
                print(f"직접 파일을 열어서 편집하세요: {theme_file}")
        else:
            print("user_theme_config.json 파일이 없습니다.")
            print(f"파일 위치: {theme_file}")
            print("파일을 먼저 생성해야 합니다.")
    
    async def edit_stock_settings(self):
        """지정종목 설정 (사용자지정 종목관리)"""
        print("\n[ 지정종목 설정 ]")
        
        # 실제 사용되는 사용자 지정종목 파일
        stock_file = self.project_root / "support" / "menual_StokBuyList.md"
        
        if stock_file.exists():
            print(f"종목 파일 위치: {stock_file}")
            print("메모장으로 종목 파일을 열어서 편집합니다...")
            
            # 윈도우 메모장으로 파일 열기
            try:
                subprocess.run(['notepad.exe', str(stock_file)], check=False)
                input("\n종목 편집을 완료하셨다면 Enter를 누르세요...")
                print("\n설정이 완료되었습니다. tideWise를 종료하고 다시 시작하면 새 설정이 적용됩니다.")
            except Exception as e:
                print(f"메모장 실행 실패: {e}")
                print(f"직접 파일을 열어서 편집하세요: {stock_file}")
        else:
            print("menual_StokBuyList.md 파일이 없습니다.")
            print(f"파일 위치: {stock_file}")
            print("파일을 먼저 생성해야 합니다.")
    
    async def edit_market_close_settings(self):
        """장마감 체크 설정 - On/Off 토글"""
        from support.market_close_controller import get_market_close_controller
        
        print("\n[ 장마감 체크 설정 ]")
        print("-" * 50)
        
        controller = get_market_close_controller()
        current_status = "ON" if controller.is_market_close_check_enabled() else "OFF"
        
        print(f"현재 설정: {current_status}")
        print(f"장마감 시간: {controller.market_close_time.strftime('%H:%M')}")
        print(f"가드 윈도우: {controller.guard_minutes}분 전부터 신규 진입 금지")
        print("-" * 50)
        print("1. ON - 14:55에 자동매매/단타매매 자동 종료")
        print("2. OFF - 장시간과 관계없이 계속 실행")
        print("0. 돌아가기")
        print("-" * 50)
        
        try:
            choice = input("\n선택하세요: ").strip()
            
            if choice == '0':
                return
            elif choice == '1':
                if controller.enable_market_close_check():
                    print("\n[OK] 장마감 체크 기능이 활성화되었습니다.")
                    print("     14:55에 자동매매와 단타매매가 자동 종료됩니다.")
                    print("     종료 시 매매 기록이 report 폴더에 저장됩니다.")
                else:
                    print("\n[ERROR] 장마감 체크 활성화에 실패했습니다.")
            elif choice == '2':
                if controller.disable_market_close_check():
                    print("\n[OK] 장마감 체크 기능이 비활성화되었습니다.")
                    print("     자동매매와 단타매매가 계속 실행됩니다.")
                    print("     수동으로 중단하거나 stop 파일로 종료해야 합니다.")
                else:
                    print("\n[ERROR] 장마감 체크 비활성화에 실패했습니다.")
            else:
                print("\n잘못된 선택입니다.")
                
            input("\nEnter를 눌러 계속...")
            
        except (KeyboardInterrupt, EOFError):
            print("\n설정을 취소합니다.")
    
    async def edit_api_key_settings(self):
        """OPEN_API_Key 정보설정, 갱신 (Register_Key.md 사용)"""
        print("\n[ OPEN_API_Key 정보설정 ]")
        print("⚠️  현재 시스템은 Register_Key.md 파일을 사용합니다!")
        
        register_key_file = self.project_root / "Policy" / "Register_Key" / "Register_Key.md"
        
        if register_key_file.exists():
            print(f"API 키 파일 위치: {register_key_file}")
            print("메모장으로 Register_Key.md 파일을 열어서 편집합니다...")
            
            # 윈도우 메모장으로 파일 열기
            try:
                subprocess.run(['notepad.exe', str(register_key_file)], check=False)
                input("\nAPI 키 편집을 완료하셨다면 Enter를 누르세요...")
                print("\n설정이 완료되었습니다. 설정은 즉시 반영됩니다.")
            except Exception as e:
                print(f"메모장 실행 실패: {e}")
                print(f"직접 파일을 열어서 편집하세요: {register_key_file}")
        else:
            print("Register_Key.md 파일이 없습니다.")
            print(f"파일 위치: {register_key_file}")
            print("파일을 먼저 생성해야 합니다.")
    
    async def edit_telegram_settings(self):
        """텔레그램 봇 설정 (레거시 함수)"""
        print("\n[ 텔레그램 봇 설정 ]")
        
        telegram_file = self.project_root / "Policy" / "Telegram_Bot-Key.txt"
        
        if telegram_file.exists():
            print(f"텔레그램 키 파일 위치: {telegram_file}")
            print("메모장으로 텔레그램 키 파일을 열어서 편집합니다...")
            
            # 윈도우 메모장으로 파일 열기
            try:
                subprocess.run(['notepad.exe', str(telegram_file)], check=False)
                input("\n텔레그램 키 편집을 완료하셨다면 Enter를 누르세요...")
                print("\n설정이 완료되었습니다. tideWise를 종료하고 다시 시작하면 새 설정이 적용됩니다.")
            except Exception as e:
                print(f"메모장 실행 실패: {e}")
                print(f"직접 파일을 열어서 편집하세요: {telegram_file}")
        else:
            print("Telegram_Bot-Key.txt 파일이 없습니다.")
            print(f"파일 위치: {telegram_file}")
            print("파일을 먼저 생성해야 합니다.")


def get_setup_manager(project_root: Path) -> SetupManager:
    """SetupManager 인스턴스를 생성하여 반환"""
    return SetupManager(project_root)
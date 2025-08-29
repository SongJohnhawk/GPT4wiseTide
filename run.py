#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
tideWise 메인 실행 파일 (리팩토링 버전) - Claude Control Ready
한국투자증권 OpenAPI를 활용한 자동매매 시스템
"""

import sys
import asyncio
import logging
from pathlib import Path

# 토큰 자동 갱신 시스템 초기화
from support.token_auto_refresher import initialize_token_system

# UTF-8 인코딩 설정
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8')

# 프로젝트 루트 설정
PROJECT_ROOT = Path(__file__).parent
sys.path.insert(0, str(PROJECT_ROOT))

# 토큰 최적화 시스템
from token_optimizer import optimize_if_needed

# 고급 에러 핸들러
from support.enhanced_error_handler import get_error_handler, log_error, log_info, log_warning

# 깔끔한 콘솔 출력 시스템
from support.clean_console_logger import (
    get_clean_logger, Phase, start_phase, end_phase, 
    log as clean_log, set_verbose
)




# 전역 자동 매매 상태 플래그
_auto_start_cancelled = False
auto_start_task = None

def _is_debug_mode() -> bool:
    """디버그 모드 확인"""
    import os
    return os.environ.get('K_AUTOTRADE_DEBUG', '').lower() in ['true', '1', 'yes']








async def main():
    """메인 함수 - 리팩토링된 버전"""
    from support.menu_manager import get_menu_manager
    from support.algorithm_selector import get_algorithm_selector
    from support.setup_manager import get_setup_manager
    from support.system_manager import get_system_manager
    
    # 시스템 초기화 시작
    start_phase(Phase.INIT, "tideWise 자동매매 시스템 시작")
    
    # 고급 에러 핸들러 초기화
    error_handler = get_error_handler(PROJECT_ROOT)
    clean_log("시스템 핸들러 초기화 완료", "SUCCESS")
    
    # 시스템 관리자 초기화
    system_manager = get_system_manager(PROJECT_ROOT)
    
    # 프로세스 정리 핸들러 등록 (프로그램 종료 시 자동 실행)
    try:
        from support.process_cleanup_manager import register_cleanup_on_exit
        register_cleanup_on_exit()
    except Exception:
        pass
    
    # 시스템 시작 시 임시 파일 자동 정리 (백그라운드에서 조용히)
    try:
        system_manager.cleanup_temp_files(silent=True)
    except Exception as cleanup_error:
        # 임시 파일 정리 실패는 프로그램 시작을 막지 않음
        pass
    
    # 시스템 요구사항 체크
    clean_log("시스템 요구사항 확인 중...", "INFO")
    if not system_manager.check_system_requirements():
        clean_log("시스템 요구사항을 만족하지 않습니다", "ERROR")
        end_phase(Phase.INIT, False)
        return
    clean_log("시스템 요구사항 확인 완료", "SUCCESS")
    
    # 알고리즘 선택자 초기화
    clean_log("알고리즘 시스템 로딩 중...", "INFO")
    algorithm_selector = get_algorithm_selector(PROJECT_ROOT)
    algorithm_selector.load_algorithm_state()
    clean_log("알고리즘 시스템 로딩 완료", "SUCCESS")
    
    # 메뉴 관리자 초기화
    menu_manager = get_menu_manager(algorithm_selector.get_selected_algorithm())
    
    # 설정 관리자 초기화
    setup_manager = get_setup_manager(PROJECT_ROOT)
    
    # 초기화 완료
    end_phase(Phase.INIT, True)
    
    # 배너 출력
    menu_manager.print_banner()
    
    # 사용자 지정종목 초기 로딩
    loading_results = []
    try:
        from support.user_designated_stocks import get_user_designated_stock_manager
        
        # Mock API 생성하여 종목 정보만 로드
        class InitAPI:
            def __init__(self):
                self.is_mock = True
            def get_stock_price(self, code):
                return {'rt_cd': '0', 'output': {'hts_kor_isnm': f'종목_{code}'}}
            def get_stock_info(self, code):
                return {'rt_cd': '0', 'output': {'hts_kor_isnm': f'종목_{code}'}}
        
        init_api = InitAPI()
        user_manager = get_user_designated_stock_manager(init_api)
        stock_count = len(user_manager.designated_stocks)
        
        if stock_count > 0:
            loading_results.append(f"OK 사용자 지정종목 로딩 완료: {stock_count}개 종목")
        else:
            loading_results.append("INFO 사용자 지정종목이 설정되지 않았습니다.")
            loading_results.append("     자동매매는 일반 모드로 동작합니다.")
            loading_results.append("     종목을 추가하려면 support/menual_StokBuyList.md 파일을 편집하세요.")
    except Exception as e:
        loading_results.append(f"WARN 사용자 지정종목 로딩 중 오류 발생: {e}")
        loading_results.append("     일반 자동매매 모드로 계속 실행됩니다.")
        loading_results.append("     문제가 지속되면 support/menual_StokBuyList.md 파일을 확인하세요.")
    
    try:
        while True:
            try:
                # 메뉴 표시
                menu_manager.show_main_menu(loading_results)
                
                choice = system_manager.safe_input("\n선택: ")
                
                if choice == 'quit' or choice == '0':
                    print("\n프로그램을 종료합니다.")
                    break
                elif choice == '1':
                    # 단타매매 서브메뉴
                    await menu_manager.handle_scalping_submenu()
                elif choice == '2':
                    # 단타매매 알고리즘 선택
                    algorithm_selector.select_day_trade_algorithm()
                    menu_manager.update_selected_algorithm(algorithm_selector.get_selected_algorithm())
                elif choice == '3':
                    # Setup 메뉴
                    await setup_manager.show_setup_menu()
                else:
                    print("\n잘못된 선택입니다.")
                
                # 첫 번째 메뉴 표시 후에는 loading_results를 초기화
                loading_results = None
                    
            except (KeyboardInterrupt, asyncio.CancelledError):
                print("\n\n사용자에 의해 중단되었습니다. 메인 메뉴로 돌아갑니다.")
            except EOFError:
                if _is_debug_mode():
                    print("\n\n프로그램을 종료합니다.")
                break
            except Exception as e:
                print(f"\n오류 발생: {e}")
                import traceback
                traceback.print_exc()
                
            if choice in ['2', '3']:
                try:
                    input("\nEnter를 눌러 계속...")
                except (KeyboardInterrupt, EOFError):
                    print("\n프로그램을 종료합니다.")
                    break
    
    finally:
        # 프로그램 종료 시 정리 작업
        try:
            if _is_debug_mode():
                print("시스템 정리 중...")
            
            # tideWise 관련 모든 프로세스 정리 (중복 실행 방지)
            try:
                from support.process_cleanup_manager import get_cleanup_manager
                cleanup_manager = get_cleanup_manager()
                
                # 이미 정리가 진행 중이거나 완료된 경우 중복 실행 방지
                if not (cleanup_manager._cleanup_in_progress or cleanup_manager._cleanup_completed):
                    if _is_debug_mode():
                        print("\n백그라운드 프로세스 정리 중...")
                    cleanup_result = cleanup_manager.cleanup_all_processes(include_self=False)
                    if cleanup_result.get('interrupted', False):
                        if _is_debug_mode():
                            print("[WARNING] 정리 작업이 중단되었습니다")
                    elif cleanup_result['terminated_processes'] > 0 and _is_debug_mode():
                        print(f"[OK] {cleanup_result['terminated_processes']}개의 백그라운드 프로세스 종료됨")
                elif _is_debug_mode():
                    print("\n프로세스 정리가 이미 수행되었습니다")
            except KeyboardInterrupt:
                # KeyboardInterrupt는 조용히 처리
                pass
            except Exception as cleanup_error:
                if _is_debug_mode():
                    print(f"프로세스 정리 오류: {cleanup_error}")
            
            # 백그라운드 태스크 정리
            global auto_start_task
            if auto_start_task and not auto_start_task.done():
                try:
                    auto_start_task.cancel()
                    try:
                        await asyncio.wait_for(auto_start_task, timeout=1.0)
                    except asyncio.TimeoutError:
                        pass
                except (asyncio.CancelledError, Exception):
                    pass
            
            # 최종 비동기 작업 정리
            try:
                await system_manager.cleanup_pending_tasks()
            except Exception:
                pass
            
            # 임시 파일 정리
            try:
                system_manager.cleanup_temp_files(silent=True)
            except Exception:
                pass
            
            if _is_debug_mode():
                print("시스템 정리 완료")
        except Exception:
            # 정리 작업 중 오류는 무시
            pass


async def initialize_system():
    """시스템 초기화 (토큰 자동 갱신 포함)"""
    from support.step_display_utils import SystemLoadingContext
    import asyncio
    import time
    
    with SystemLoadingContext(capture_logs=True) as loading:
        loading.log("tideWise 시스템 초기화 중...")
        
        try:
            # 토큰 자동 갱신 시스템 초기화
            await initialize_token_system()
            loading.success_msg("토큰 자동 갱신 시스템 활성화")
            
            # ProcessCleanupManager 초기화 대기 (로그 캡처)
            await asyncio.sleep(0.5)
            
            # 알고리즘 초기화 대기 (로그 캡처)
            await asyncio.sleep(0.5)
            
            return True
        except Exception as e:
            loading.error(f"토큰 자동 갱신 시스템 초기화 실패: {e}")
            loading.log("기존 토큰 관리 시스템으로 실행됩니다.")
            return True  # 실패해도 계속 실행

if __name__ == "__main__":
    """프로그램 진입점"""
    import signal
    
    # 전역 종료 플래그
    exit_requested = False
    force_exit_count = 0
    
    def signal_handler(signum, frame):
        global exit_requested, force_exit_count
        
        force_exit_count += 1
        
        if force_exit_count == 1:
            exit_requested = True
            if _is_debug_mode():
                print("\n중단 요청 수신 - 안전한 종료를 진행합니다...")
            
            # ProcessCleanupManager와 협조하여 정리 작업 수행
            try:
                from support.process_cleanup_manager import get_cleanup_manager
                cleanup_manager = get_cleanup_manager()
                
                # 이미 정리가 진행 중이거나 완료된 경우 중복 실행 방지
                if not (cleanup_manager._cleanup_in_progress or cleanup_manager._cleanup_completed):
                    print("백그라운드 프로세스 정리 중...")
                    cleanup_result = cleanup_manager.cleanup_all_processes(include_self=False)
                    if cleanup_result.get('interrupted', False):
                        print("[WARNING] 정리 작업이 중단되었습니다")
                    elif cleanup_result['terminated_processes'] > 0:
                        print(f"[OK] {cleanup_result['terminated_processes']}개의 백그라운드 프로세스 종료됨")
            except Exception:
                # 정리 작업 중 오류는 조용히 처리
                pass
            
        elif force_exit_count >= 2:
            print("강제 종료 요청 - 즉시 프로그램을 종료합니다...")
            import sys
            sys.exit(1)
            
    # Windows에서 Ctrl+C 시그널 핸들러 등록
    signal.signal(signal.SIGINT, signal_handler)
    
    loop = None
    try:
        # 토큰 시스템 초기화
        asyncio.run(initialize_system())
        
        # 새로운 이벤트 루프 생성 및 설정
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        # 메인 코루틴 실행
        loop.run_until_complete(main())
        
    except (KeyboardInterrupt, asyncio.CancelledError):
        # Ctrl+C 또는 비동기 취소 처리 (조용히)
        if _is_debug_mode():
            print("\n사용자에 의한 중단 요청...")
    except Exception as e:
        print(f"시스템 오류: {e}")
    finally:
        # 이벤트 루프가 존재할 경우 정리 작업 수행
        if loop and not loop.is_closed():
            try:
                # 남은 태스크들을 안전하게 정리
                try:
                    pending_tasks = [task for task in asyncio.all_tasks(loop) if not task.done()]
                    if pending_tasks:
                        print(f"남은 태스크 {len(pending_tasks)}개를 정리 중...")
                        
                        # 모든 태스크 취소
                        for task in pending_tasks:
                            if not task.done() and not task.cancelled():
                                task.cancel()
                        
                        # 취소 완료까지 안전하게 대기
                        import time
                        max_wait = 1.0 if exit_requested else 3.0
                        start_time = time.time()
                        
                        while pending_tasks and (time.time() - start_time) < max_wait:
                            if exit_requested:
                                print("종료 신호 감지 - 태스크 정리 중단")
                                break
                                
                            pending_tasks = [task for task in pending_tasks if not task.done()]
                            if pending_tasks:
                                try:
                                    wait_time = 0.05 if exit_requested else 0.1
                                    time.sleep(wait_time)  
                                except KeyboardInterrupt:
                                    print("태스크 대기 중 중단 신호 감지 - 강제 종료")
                                    break
                        
                        remaining = len([task for task in pending_tasks if not task.done()])
                        if remaining > 0:
                            print(f"강제 종료: {remaining}개 태스크가 완료되지 않았습니다.")
                        else:
                            print("모든 태스크 정리 완료")
                            
                except KeyboardInterrupt:
                    print("태스크 정리 중 중단 신호 감지 - 즉시 종료")
                except Exception as cleanup_error:
                    print(f"태스크 정리 중 오류 무시: {cleanup_error}")
                        
            except KeyboardInterrupt:
                print("이벤트 루프 정리 중 중단 신호 감지 - 즉시 종료")
            except Exception as loop_cleanup_error:
                print(f"이벤트 루프 정리 중 오류 무시: {loop_cleanup_error}")
            finally:
                try:
                    if hasattr(loop, '_selector') and loop._selector:
                        try:
                            loop._selector.close()
                        except Exception:
                            pass
                    
                    loop.close()
                except KeyboardInterrupt:
                    pass
                except Exception as close_error:
                    print(f"루프 종료 오류 무시: {close_error}")
                    pass
        
        # 가비지 컬렉션
        import gc
        import time
        try:
            gc.collect()
            time.sleep(0.1)
        except KeyboardInterrupt:
            pass
        finally:
            if _is_debug_mode():
                print("\ntideWise 시스템이 안전하게 종료되었습니다.")
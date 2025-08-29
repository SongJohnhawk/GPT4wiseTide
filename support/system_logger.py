"""
tideWise System Logging Manager
- JSON format log storage
- English language logging system
- Temporary file management
- Auto cleanup on program exit
- No separate monitor window
"""

import atexit
import json
import os
import threading
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional


class SystemLogger:
    """시스템 로깅 관리자 (모니터링 창 제거 버전)"""

    def __init__(self, log_dir: str = "systemlog"):
        """로깅 시스템 초기화"""
        self.log_dir = Path(log_dir)
        self.log_file_path = None
        self.log_buffer: List[Dict] = []
        self.buffer_lock = threading.Lock()
        self.session_id = datetime.now().strftime("%Y%m%d_%H%M%S")

        # 로그 디렉토리 생성
        self.log_dir.mkdir(exist_ok=True)

        # 임시 로그 파일 생성
        self.create_temp_log_file()

        # 프로그램 종료 시 정리 함수 등록
        atexit.register(self.cleanup)

        # Start logging
        self.log(
            "SYSTEM",
            "tideWise system logging started",
            {"session_id": self.session_id},
        )

    def create_temp_log_file(self):
        """임시 로그 파일 생성"""
        try:
            temp_name = f"k_autotrade_log_{self.session_id}.json"
            self.log_file_path = self.log_dir / temp_name

            initial_data = {
                "session_info": {
                    "session_id": self.session_id,
                    "start_time": datetime.now().isoformat(),
                    "system": "tideWise",
                    "version": "2.0.0",
                },
                "logs": [],
            }

            with open(self.log_file_path, "w", encoding="utf-8") as f:
                json.dump(initial_data, f, ensure_ascii=False, indent=2)

        except Exception as e:
            print(f"ERROR: Log file creation failed: {str(e)}")

    def log(self, level: str, message: str, data: Optional[Dict] = None):
        """로그 메시지 기록"""
        try:
            log_entry = {
                "timestamp": datetime.now().isoformat(),
                "level": level,
                "message": message,
                "session_id": self.session_id,
                "data": data or {},
            }

            # 버퍼에 추가 (스레드 안전)
            with self.buffer_lock:
                self.log_buffer.append(log_entry)

            # 로그 파일에 즉시 기록
            self.write_to_file()

            # 콘솔에도 출력
            self.print_log_console(log_entry)

        except Exception as e:
            print(f"ERROR: Log recording failed: {str(e)}")

    def write_to_file(self):
        """로그 버퍼를 파일에 기록"""
        try:
            if not self.log_file_path or not self.log_buffer:
                return

            # 기존 로그 파일 읽기
            with open(self.log_file_path, "r", encoding="utf-8") as f:
                log_data = json.load(f)

            # 새 로그 추가
            with self.buffer_lock:
                log_data["logs"].extend(self.log_buffer)
                self.log_buffer.clear()

            # 업데이트된 로그 파일 저장 (파일 완전히 다시 쓰기)
            with open(self.log_file_path, "w", encoding="utf-8") as f:
                json.dump(log_data, f, ensure_ascii=False, indent=2)
                f.flush()  # 버퍼 강제 플러시
                os.fsync(f.fileno())  # OS 레벨에서 디스크에 쓰기

        except Exception as e:
            print(f"ERROR: Log file write failed: {str(e)}")

    def print_log_console(self, log_entry: Dict):
        """콘솔에 로그 출력"""
        try:
            timestamp = datetime.fromisoformat(
                log_entry["timestamp"]
            ).strftime("%H:%M:%S")
            level = log_entry["level"]
            message = log_entry["message"]

            # 로그 레벨에 따른 표시
            if level == "BUY_CANDIDATE":
                print(f"[SEARCH] [{timestamp}] {message}")
            elif level == "BUY_ORDER":
                print(f"[BUY] [{timestamp}] {message}")
            elif level == "SELL_ORDER":
                print(f"[SELL] [{timestamp}] {message}")
            elif level == "SYSTEM_START":
                print(f"[START] [{timestamp}] {message}")
            else:
                print(f"[{level}] [{timestamp}] {message}")

        except Exception as e:
            print(f"ERROR: Console log output failed: {str(e)}")

    def log_trade(
        self,
        action: str,
        symbol: str,
        quantity: int,
        price: float,
        success: bool = True,
        error_msg: str = "",
    ):
        """거래 로그 전용"""
        data = {
            "action": action,
            "symbol": symbol,
            "quantity": quantity,
            "price": price,
            "success": success,
            "total_amount": quantity * price,
        }

        if not success:
            data["error"] = error_msg

        level = "TRADE" if success else "ERROR"
        message = f"{action} {symbol} {quantity}주 @{price:,}원"

        if not success:
            message += f" 실패: {error_msg}"

        self.log(level, message, data)

    def log_account_info(
        self,
        account_type: str,
        account_number: str,
        total_assets: int,
        available_cash: int,
    ):
        """계좌 정보 로그"""
        data = {
            "account_type": account_type,
            "account_number": account_number,
            "total_assets": total_assets,
            "available_cash": available_cash,
        }

        message = (
            f"계좌 정보: {account_type} ({account_number}) "
            f"총자산 {total_assets:,}원"
        )
        self.log("INFO", message, data)

    def log_system_status(self, status: str, details: Dict = None):
        """시스템 상태 로그"""
        self.log("SYSTEM", f"시스템 상태: {status}", details or {})

    def log_error(self, error_msg: str, exception: Exception = None):
        """에러 로그"""
        data = {"error_type": type(exception).__name__} if exception else {}
        self.log("ERROR", error_msg, data)

    def get_log_stats(self) -> Dict:
        """로그 통계 반환"""
        try:
            if not self.log_file_path.exists():
                return {}

            with open(self.log_file_path, "r", encoding="utf-8") as f:
                log_data = json.load(f)

            logs = log_data.get("logs", [])

            # 레벨별 통계
            level_counts = {}
            for log in logs:
                level = log.get("level", "UNKNOWN")
                level_counts[level] = level_counts.get(level, 0) + 1

            return {
                "total_logs": len(logs),
                "session_id": self.session_id,
                "start_time": log_data.get("session_info", {}).get(
                    "start_time"
                ),
                "level_counts": level_counts,
            }

        except Exception as e:
            print(f"ERR 로그 통계 조회 실패: {str(e)}")
            return {}

    def cleanup(self):
        """정리 작업 (프로그램 종료시 자동 실행) - KeyboardInterrupt 안전 처리"""
        try:
            # 종료 로그 기록 (빠른 종료를 위해 간단하게)
            try:
                self.log(
                    "SYSTEM",
                    "tideWise 시스템 종료",
                    {"end_time": datetime.now().isoformat()},
                )
                # 마지막 로그 파일 기록
                self.write_to_file()
            except (KeyboardInterrupt, SystemExit):
                # 종료 중이면 로깅 생략
                pass
            except Exception:
                # 로깅 실패도 무시
                pass

            # 로그 통계 출력 (빠르게 처리)
            try:
                stats = self.get_log_stats()
                if stats:
                    print(f"\n세션 {self.session_id} 로그 통계:")
                    print(f"   총 로그: {stats['total_logs']}개")
                    for level, count in stats.get("level_counts", {}).items():
                        print(f"   {level}: {count}개")
            except (KeyboardInterrupt, SystemExit):
                # 종료 중이면 통계 출력 생략
                pass
            except Exception:
                # 통계 실패도 무시
                pass

            # 임시 파일들 삭제
            try:
                self.delete_temp_files()
                print("SUCCESS: 로깅 시스템 정리 완료")
            except (KeyboardInterrupt, SystemExit):
                # 종료 중이면 자리엄수 생략
                pass
            except Exception:
                # 정리 실패도 조용히 무시
                pass

        except (KeyboardInterrupt, SystemExit):
            # 전체 cleanup에서 KeyboardInterrupt 발생 시 조용히 종료
            pass
        except Exception:
            # 기타 오류도 조용히 무시 (종료 중에 에러 메시지 출력 방지)
            pass

    def delete_temp_files(self):
        """임시 파일들 삭제"""
        try:
            # 로그 파일 삭제
            if self.log_file_path and self.log_file_path.exists():
                self.log_file_path.unlink()
                print(f"CLEANUP: 로그 파일 삭제: {self.log_file_path}")

            # 빈 디렉토리 삭제 시도
            if self.log_dir.exists() and not any(self.log_dir.iterdir()):
                self.log_dir.rmdir()
                print(f"CLEANUP: 빈 로그 디렉토리 삭제: {self.log_dir}")

        except Exception as e:
            print(f"ERROR: 임시 파일 삭제 실패: {str(e)}")


# 전역 로거 인스턴스
_system_logger = None


def get_logger() -> SystemLogger:
    """전역 로거 인스턴스 반환"""
    global _system_logger
    if _system_logger is None:
        _system_logger = SystemLogger()
    return _system_logger


def log_info(message: str, data: Dict = None):
    """정보 로그 단축함수"""
    get_logger().log("INFO", message, data)


def log_error(message: str, exception: Exception = None):
    """에러 로그 단축함수"""
    get_logger().log_error(message, exception)


def log_trade(
    action: str,
    symbol: str,
    quantity: int,
    price: float,
    success: bool = True,
    error_msg: str = "",
):
    """거래 로그 단축함수"""
    get_logger().log_trade(action, symbol, quantity, price, success, error_msg)


def log_system(message: str, data: Dict = None):
    """시스템 로그 단축함수"""
    get_logger().log("SYSTEM", message, data)
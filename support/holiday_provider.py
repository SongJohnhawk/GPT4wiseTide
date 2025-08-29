"""
tideWise 한국거래소(KRX) 휴장일 제공자
독립적인 휴장일 관리 및 거래일 계산 모듈
"""
import json
import requests
from datetime import datetime, date, timedelta
from pathlib import Path
import pytz
from typing import List, Optional
import logging

class HolidayProvider:
    """한국거래소 휴장일 정보 제공 및 거래일 계산"""
    
    def __init__(self):
        self.cache_file = Path("support/krx_holidays_cache.json")
        self.seoul_tz = pytz.timezone('Asia/Seoul')
        self.holidays = {}
        self.last_update = None
        self.logger = logging.getLogger(__name__)
        
    def _load_cache(self) -> bool:
        """캐시된 휴장일 정보 로드"""
        try:
            if self.cache_file.exists():
                with open(self.cache_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.holidays = data.get('holidays', {})
                    self.last_update = data.get('last_update')
                    return True
        except Exception as e:
            self.logger.error(f"휴장일 캐시 로드 실패: {e}")
        return False
    
    def _save_cache(self):
        """휴장일 정보 캐시 저장"""
        try:
            data = {
                'holidays': self.holidays,
                'last_update': self.last_update
            }
            with open(self.cache_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            self.logger.error(f"휴장일 캐시 저장 실패: {e}")
    
    def _fetch_krx_holidays(self, year: int) -> List[str]:
        """KRX OTP 플로우를 통한 휴장일 정보 가져오기"""
        try:
            # KRX 휴장일 조회 URL (OTP 방식)
            otp_url = "http://data.krx.co.kr/comm/fileDn/GenerateOTP/generate.cmd"
            
            # OTP 생성 요청
            otp_params = {
                'mktId': 'ALL',
                'trdDd': f'{year}',
                'money': '1',
                'csvxls_isNo': 'false',
                'name': 'fileDown',
                'url': 'dbms/MDC/STAT/standard/MDCSTAT01901'
            }
            
            response = requests.post(otp_url, data=otp_params, timeout=10)
            response.raise_for_status()
            
            otp_code = response.text.strip()
            
            # 실제 데이터 다운로드
            download_url = "http://data.krx.co.kr/comm/fileDn/download_csv/download.cmd"
            download_params = {'code': otp_code}
            
            data_response = requests.post(download_url, data=download_params, timeout=30)
            data_response.raise_for_status()
            
            # CSV 데이터 파싱 (휴장일 추출)
            holidays = []
            lines = data_response.text.strip().split('\n')
            
            for line in lines[1:]:  # 헤더 제외
                columns = line.split(',')
                if len(columns) >= 2 and columns[1].strip():
                    # 날짜 형식 변환 (YYYY/MM/DD -> YYYY-MM-DD)
                    date_str = columns[1].strip().replace('/', '-')
                    if self._is_valid_date(date_str):
                        holidays.append(date_str)
            
            return holidays
            
        except Exception as e:
            self.logger.error(f"KRX 휴장일 조회 실패 (year={year}): {e}")
            # KRX 조회 실패시 기본 공휴일만 반환
            base_holidays = [
                f"{year}-01-01",  # 신정
                f"{year}-03-01",  # 삼일절
                f"{year}-05-05",  # 어린이날
                f"{year}-06-06",  # 현충일
                f"{year}-08-15",  # 광복절
                f"{year}-10-03",  # 개천절
                f"{year}-10-09",  # 한글날
                f"{year}-12-25",  # 크리스마스
            ]
            return base_holidays
    
    def _is_valid_date(self, date_str: str) -> bool:
        """날짜 문자열 유효성 검사"""
        try:
            datetime.strptime(date_str, '%Y-%m-%d')
            return True
        except ValueError:
            return False
    
    def _need_update(self, year: int) -> bool:
        """휴장일 정보 업데이트 필요 여부 확인"""
        if str(year) not in self.holidays:
            return True
            
        if not self.last_update:
            return True
            
        # 매월 첫 실행시 업데이트
        last_update_date = datetime.fromisoformat(self.last_update).date()
        today = datetime.now(self.seoul_tz).date()
        
        return (today.year != last_update_date.year or 
                today.month != last_update_date.month)
    
    def update_holidays(self, year: int) -> bool:
        """지정된 연도의 휴장일 정보 업데이트"""
        try:
            holidays = self._fetch_krx_holidays(year)
            self.holidays[str(year)] = holidays
            self.last_update = datetime.now(self.seoul_tz).isoformat()
            self._save_cache()
            
            self.logger.info(f"{year}년 휴장일 정보 업데이트 완료: {len(holidays)}개")
            return True
            
        except Exception as e:
            self.logger.error(f"휴장일 정보 업데이트 실패: {e}")
            return False
    
    def is_holiday(self, target_date: date) -> bool:
        """지정된 날짜가 휴장일인지 확인"""
        # 캐시 로드
        if not self.holidays:
            self._load_cache()
        
        year = target_date.year
        
        # 필요시 업데이트
        if self._need_update(year):
            self.update_holidays(year)
        
        # 휴장일 확인
        year_holidays = self.holidays.get(str(year), [])
        date_str = target_date.strftime('%Y-%m-%d')
        
        # 주말 확인
        if target_date.weekday() >= 5:
            return True
            
        # 공휴일 확인
        return date_str in year_holidays
    
    def last_trading_day_of_iso_week(self, any_date_in_week: date) -> date:
        """ISO 주 기준 마지막 거래일 반환 (일반적으로 금요일)"""
        # ISO 주의 시작 (월요일) 찾기
        days_since_monday = any_date_in_week.weekday()
        monday = any_date_in_week - timedelta(days=days_since_monday)
        
        # 금요일부터 역순으로 거래일 찾기
        friday = monday + timedelta(days=4)
        
        for i in range(7):  # 최대 1주일 범위에서 검색
            check_date = friday - timedelta(days=i)
            if check_date >= monday and not self.is_holiday(check_date):
                return check_date
        
        # 모든 날이 휴장일인 경우 금요일 반환 (예외 상황)
        return friday
    
    def last_trading_day_of_month(self, year: int, month: int) -> date:
        """월 기준 마지막 거래일 반환"""
        # 월의 마지막 날 계산
        if month == 12:
            last_day = date(year + 1, 1, 1) - timedelta(days=1)
        else:
            last_day = date(year, month + 1, 1) - timedelta(days=1)
        
        # 마지막 날부터 역순으로 거래일 찾기
        for i in range(31):  # 최대 31일 범위에서 검색
            check_date = last_day - timedelta(days=i)
            if check_date.month == month and not self.is_holiday(check_date):
                return check_date
        
        # 모든 날이 휴장일인 경우 마지막 날 반환 (예외 상황)
        return last_day


# 전역 인스턴스
holiday_provider = HolidayProvider()
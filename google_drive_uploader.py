#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
독립적인 Google Drive 전체 폴더 백업 프로그램
완전히 독립된 백업 도구 - 배포버전에 포함되지 않음

목적: C:\\Claude_Works\\Projects\\GPT4wiseTide 폴더의 모든 파일을 
     Google Drive의 지정된 폴더에 백업

요구사항:
- 1,865개 파일을 모두 업로드 (파일 한개도 남기지 말고)
- 대상: Google Drive 폴더 ID "1D9AvLY9th8cuKthD30KHjWmmq6P4aPO8"
- 하위폴더: "(StokAutoTrade)wiseTide_Backup"
- 백테스트 프로그램처럼 완전히 독립된 프로그램
"""

import os
import sys
import json
import time
from pathlib import Path
from typing import List, Dict, Any, Optional
import logging
from datetime import datetime
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed

# Windows 콘솔 UTF-8 인코딩 설정
if sys.platform == "win32":
    import codecs
    sys.stdout = codecs.getwriter('utf-8')(sys.stdout.detach())
    sys.stderr = codecs.getwriter('utf-8')(sys.stderr.detach())

try:
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    from googleapiclient.discovery import build
    from googleapiclient.errors import HttpError
    from googleapiclient.http import MediaFileUpload
    import pickle
except ImportError as e:
    print(f"❌ 필수 라이브러리 설치 필요: {e}")
    print("설치 명령어: pip install google-api-python-client google-auth-oauthlib google-auth-httplib2")
    sys.exit(1)

# Google Drive API 설정
SCOPES = ['https://www.googleapis.com/auth/drive.file']
SOURCE_DIR = r"C:\Claude_Works\Projects\GPT4wiseTide"
CREDENTIALS_FILE = r"C:\Claude_Works\Projects\GPT4wiseTide\Policy\Register_Key\credentials.json"
TOKEN_FILE = "drive_token.json"

# 대상 Google Drive 설정 (공유 URL에서 추출한 폴더 ID)
PARENT_FOLDER_ID = "1D9AvLY9th8cuKthD30KHjWmmq6P4aPO8"
BACKUP_FOLDER_NAME = "(StokAutoTrade)wiseTide_Backup"

# 업로드 설정
MAX_WORKERS = 3  # 동시 업로드 스레드 수
MAX_FILE_SIZE = 100 * 1024 * 1024  # 100MB 제한
CHUNK_SIZE = 1024 * 1024  # 1MB 청크

class GoogleDriveUploader:
    def __init__(self):
        self.service = None
        self.backup_folder_id = None
        self.uploaded_files = 0
        self.failed_files = 0
        self.skipped_files = 0
        self.total_files = 0
        self.upload_lock = threading.Lock()
        self.folder_cache = {}  # 폴더 ID 캐시
        
        # 로깅 설정
        log_filename = f"drive_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(log_filename, encoding='utf-8'),
                logging.StreamHandler(sys.stdout)
            ]
        )
        self.logger = logging.getLogger(__name__)
        
    def authenticate(self) -> bool:
        """Google Drive API 인증"""
        creds = None
        
        # 기존 토큰 파일이 있으면 로드
        if os.path.exists(TOKEN_FILE):
            try:
                with open(TOKEN_FILE, 'r') as token:
                    creds = Credentials.from_authorized_user_info(json.load(token), SCOPES)
                self.logger.info("기존 인증 토큰을 로드했습니다.")
            except Exception as e:
                self.logger.warning(f"기존 토큰 로드 실패: {e}")
        
        # 토큰이 유효하지 않으면 새로 인증
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                try:
                    creds.refresh(Request())
                    self.logger.info("인증 토큰을 갱신했습니다.")
                except Exception as e:
                    self.logger.error(f"토큰 갱신 실패: {e}")
                    creds = None
            
            if not creds:
                if not os.path.exists(CREDENTIALS_FILE):
                    self.logger.error(f"❌ credentials.json 파일이 없습니다: {CREDENTIALS_FILE}")
                    return False
                
                try:
                    flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_FILE, SCOPES)
                    creds = flow.run_local_server(port=0)
                    self.logger.info("새로운 인증을 완료했습니다.")
                except Exception as e:
                    self.logger.error(f"❌ OAuth 인증 실패: {e}")
                    return False
            
            # 토큰 저장
            try:
                with open(TOKEN_FILE, 'w') as token:
                    token.write(creds.to_json())
                self.logger.info("인증 토큰을 저장했습니다.")
            except Exception as e:
                self.logger.warning(f"토큰 저장 실패: {e}")
        
        try:
            self.service = build('drive', 'v3', credentials=creds)
            self.logger.info("✅ Google Drive API 서비스 초기화 완료")
            return True
        except Exception as e:
            self.logger.error(f"❌ Google Drive 서비스 초기화 실패: {e}")
            return False
    
    def create_folder(self, name: str, parent_id: str) -> Optional[str]:
        """폴더 생성"""
        try:
            # 기존 폴더 검색
            cache_key = f"{parent_id}:{name}"
            if cache_key in self.folder_cache:
                return self.folder_cache[cache_key]
            
            query = f"name='{name}' and parents in '{parent_id}' and mimeType='application/vnd.google-apps.folder'"
            results = self.service.files().list(q=query, fields="files(id, name)").execute()
            items = results.get('files', [])
            
            if items:
                folder_id = items[0]['id']
                self.logger.info(f"✅ 기존 폴더 발견: {name}")
            else:
                # 새 폴더 생성
                folder_metadata = {
                    'name': name,
                    'parents': [parent_id],
                    'mimeType': 'application/vnd.google-apps.folder'
                }
                folder = self.service.files().create(body=folder_metadata).execute()
                folder_id = folder.get('id')
                self.logger.info(f"✅ 새 폴더 생성: {name}")
            
            # 캐시에 저장
            self.folder_cache[cache_key] = folder_id
            return folder_id
            
        except Exception as e:
            self.logger.error(f"❌ 폴더 생성/찾기 실패 '{name}': {e}")
            return None
    
    def get_or_create_folder_path(self, relative_path: str) -> Optional[str]:
        """상대 경로에 따른 폴더 구조 생성"""
        path_parts = Path(relative_path).parts
        current_parent = self.backup_folder_id
        
        # 파일이 루트 디렉토리에 있는 경우 (폴더 없음)
        if len(path_parts) <= 1:
            return current_parent
        
        # 폴더 경로가 있는 경우
        for part in path_parts[:-1]:  # 파일명 제외
            if not part or part == '.' or part == '':
                continue
            current_parent = self.create_folder(part, current_parent)
            if not current_parent:
                self.logger.error(f"폴더 생성 실패: {part} (경로: {relative_path})")
                return None
        
        return current_parent
    
    def count_total_files(self) -> int:
        """전체 파일 개수 계산"""
        total = 0
        try:
            for root, dirs, files in os.walk(SOURCE_DIR):
                # 숨김 폴더 및 특정 폴더 제외
                dirs[:] = [d for d in dirs if not d.startswith('.') and d not in [
                    '__pycache__', 'node_modules', '.git', '.vscode', 
                    'dist', 'build', '.pytest_cache'
                ]]
                
                for file in files:
                    if not file.startswith('.') and not file.endswith(('.tmp', '.pyc')):
                        total += 1
                        
            return total
        except Exception as e:
            self.logger.error(f"파일 개수 계산 실패: {e}")
            return 0
    
    def upload_single_file(self, file_info: dict) -> bool:
        """단일 파일 업로드"""
        local_path = file_info['local_path']
        relative_path = file_info['relative_path']
        
        try:
            # 파일 크기 체크
            file_size = os.path.getsize(local_path)
            if file_size > MAX_FILE_SIZE:
                with self.upload_lock:
                    self.logger.warning(f"⚠️ 파일이 너무 큽니다 (100MB 초과): {relative_path}")
                    self.skipped_files += 1
                return False
            
            # 대상 폴더 ID 가져오기
            parent_folder_id = self.get_or_create_folder_path(relative_path)
            if parent_folder_id is None:
                with self.upload_lock:
                    self.logger.error(f"❌ 폴더 생성 실패: {relative_path}")
                    self.failed_files += 1
                return False
            
            # 파일 메타데이터
            file_metadata = {
                'name': os.path.basename(relative_path),
                'parents': [parent_folder_id]
            }
            
            # 미디어 업로드 객체 생성
            media = MediaFileUpload(
                local_path,
                resumable=file_size > 10 * 1024 * 1024,  # 10MB 이상은 resumable
                chunksize=CHUNK_SIZE
            )
            
            # 업로드 실행
            request = self.service.files().create(
                body=file_metadata,
                media_body=media,
                fields='id, name'
            )
            
            response = None
            while response is None:
                try:
                    status, response = request.next_chunk()
                    if status and file_size > 10 * 1024 * 1024:  # 큰 파일만 진행률 표시
                        progress = int(status.progress() * 100)
                        if progress % 25 == 0:  # 25%마다 로그
                            with self.upload_lock:
                                self.logger.info(f"📤 업로드 진행: {os.path.basename(relative_path)} ({progress}%)")
                except Exception as chunk_error:
                    with self.upload_lock:
                        self.logger.error(f"❌ 업로드 중 오류: {relative_path} - {chunk_error}")
                        self.failed_files += 1
                    return False
            
            with self.upload_lock:
                self.uploaded_files += 1
                self.logger.info(f"✅ 업로드 완료 ({self.uploaded_files}/{self.total_files}): {relative_path}")
            
            return True
            
        except Exception as e:
            with self.upload_lock:
                self.logger.error(f"❌ 업로드 실패: {relative_path} - {e}")
                self.failed_files += 1
            return False
    
    def collect_all_files(self) -> List[dict]:
        """업로드할 모든 파일 목록 수집"""
        files_to_upload = []
        
        try:
            for root, dirs, files in os.walk(SOURCE_DIR):
                # 숨김 폴더 및 특정 폴더 제외
                dirs[:] = [d for d in dirs if not d.startswith('.') and d not in [
                    '__pycache__', 'node_modules', '.git', '.vscode',
                    'dist', 'build', '.pytest_cache'
                ]]
                
                for file in files:
                    if file.startswith('.') or file.endswith(('.tmp', '.pyc')):
                        continue
                    
                    local_path = os.path.join(root, file)
                    relative_path = os.path.relpath(local_path, SOURCE_DIR)
                    
                    files_to_upload.append({
                        'local_path': local_path,
                        'relative_path': relative_path,
                        'size': os.path.getsize(local_path)
                    })
            
            return files_to_upload
            
        except Exception as e:
            self.logger.error(f"❌ 파일 목록 수집 실패: {e}")
            return []
    
    def upload_all_files(self) -> bool:
        """모든 파일 업로드 (멀티스레드)"""
        self.logger.info(f"📁 소스 디렉토리: {SOURCE_DIR}")
        self.logger.info(f"🎯 대상 폴더: {BACKUP_FOLDER_NAME}")
        
        # 백업 폴더 생성
        self.backup_folder_id = self.create_folder(BACKUP_FOLDER_NAME, PARENT_FOLDER_ID)
        if not self.backup_folder_id:
            self.logger.error("❌ 백업 폴더 생성 실패")
            return False
        
        # 업로드할 파일 목록 수집
        files_to_upload = self.collect_all_files()
        self.total_files = len(files_to_upload)
        
        if self.total_files == 0:
            self.logger.warning("⚠️ 업로드할 파일이 없습니다")
            return False
        
        self.logger.info(f"📊 전체 파일 개수: {self.total_files}개")
        total_size = sum(f['size'] for f in files_to_upload)
        self.logger.info(f"📊 전체 파일 크기: {total_size / (1024*1024):.1f} MB")
        
        start_time = time.time()
        
        # 멀티스레드로 업로드
        try:
            with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
                # 업로드 작업 제출
                future_to_file = {
                    executor.submit(self.upload_single_file, file_info): file_info
                    for file_info in files_to_upload
                }
                
                # 결과 처리
                for future in as_completed(future_to_file):
                    file_info = future_to_file[future]
                    try:
                        success = future.result()
                        if not success:
                            self.logger.error(f"업로드 실패: {file_info['relative_path']}")
                    except Exception as exc:
                        self.logger.error(f"업로드 예외 발생: {file_info['relative_path']} - {exc}")
                        with self.upload_lock:
                            self.failed_files += 1
                    
                    # 진행률 출력
                    completed = self.uploaded_files + self.failed_files + self.skipped_files
                    if completed % 50 == 0 or completed == self.total_files:
                        elapsed = time.time() - start_time
                        progress = (completed / self.total_files) * 100
                        rate = completed / elapsed if elapsed > 0 else 0
                        eta = (self.total_files - completed) / rate if rate > 0 else 0
                        
                        self.logger.info(f"📈 진행률: {completed}/{self.total_files} ({progress:.1f}%) "
                                       f"- 속도: {rate:.1f}파일/초 - 예상 남은 시간: {eta/60:.1f}분")
            
            return True
            
        except Exception as e:
            self.logger.error(f"❌ 업로드 프로세스 실패: {e}")
            return False
    
    def print_summary(self):
        """업로드 결과 요약"""
        self.logger.info("\n" + "="*70)
        self.logger.info("📊 GPT4wiseTide 백업 완료 보고서")
        self.logger.info("="*70)
        self.logger.info(f"소스 디렉토리: {SOURCE_DIR}")
        self.logger.info(f"대상 Google Drive 폴더: {BACKUP_FOLDER_NAME}")
        self.logger.info(f"백업 시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        self.logger.info("-"*70)
        self.logger.info(f"전체 파일: {self.total_files:,}개")
        self.logger.info(f"업로드 성공: {self.uploaded_files:,}개")
        self.logger.info(f"건너뜀: {self.skipped_files:,}개")
        self.logger.info(f"실패: {self.failed_files:,}개")
        
        success_rate = (self.uploaded_files / self.total_files * 100) if self.total_files > 0 else 0
        self.logger.info(f"성공률: {success_rate:.1f}%")
        self.logger.info("="*70)
        
        if self.failed_files > 0:
            self.logger.warning(f"⚠️ {self.failed_files}개 파일 업로드 실패")
            self.logger.info("실패한 파일들은 로그에서 확인할 수 있습니다.")
        else:
            self.logger.info("🎉 모든 파일 업로드 완료!")

def validate_environment() -> bool:
    """환경 검증"""
    print("[검증] 환경 검증 중...")
    
    # 소스 디렉토리 존재 확인
    if not os.path.exists(SOURCE_DIR):
        print(f"[ERROR] 소스 디렉토리가 존재하지 않습니다: {SOURCE_DIR}")
        return False
    
    # credentials.json 존재 확인
    if not os.path.exists(CREDENTIALS_FILE):
        print(f"[ERROR] credentials.json 파일이 없습니다: {CREDENTIALS_FILE}")
        print("Google Drive API 인증을 위해 credentials.json 파일이 필요합니다.")
        return False
    
    print("[OK] 환경 검증 완료")
    return True

def main():
    """메인 실행 함수"""
    print(">> GPT4wiseTide 독립 백업 프로그램 v2.0")
    print("="*70)
    print("목적: 전체 프로젝트를 Google Drive에 백업")
    print(f"소스: {SOURCE_DIR}")
    print(f"대상: Google Drive/{BACKUP_FOLDER_NAME}")
    print("="*70)
    
    # 환경 검증
    if not validate_environment():
        return False
    
    # 업로더 초기화 및 실행
    uploader = GoogleDriveUploader()
    
    try:
        # 1. 인증
        print("\n[인증] Google Drive 인증 중...")
        if not uploader.authenticate():
            print("[ERROR] Google Drive 인증 실패")
            return False
        
        # 2. 파일 개수 확인
        total_files = uploader.count_total_files()
        print(f"\n[정보] 업로드 대상 파일: {total_files:,}개")
        
        if total_files == 0:
            print("[ERROR] 업로드할 파일이 없습니다.")
            return False
        
        # 3. 자동 진행 (배치 모드)
        print(f"\n[주의] 이 작업은 {total_files:,}개의 파일을 Google Drive에 업로드합니다.")
        print("시간이 오래 걸릴 수 있으며, 네트워크 사용량이 많습니다.")
        print("[자동] 자동 모드로 업로드를 시작합니다...")
        
        # 4. 업로드 실행
        print(f"\n[시작] 업로드 시작... (최대 {MAX_WORKERS}개 스레드 사용)")
        print("진행상황은 로그 파일에서도 확인할 수 있습니다.")
        
        start_time = time.time()
        success = uploader.upload_all_files()
        end_time = time.time()
        
        # 5. 결과 출력
        uploader.print_summary()
        
        elapsed_time = end_time - start_time
        print(f"\n[시간] 총 소요시간: {elapsed_time/60:.1f}분")
        
        if success and uploader.failed_files == 0:
            print(f"\n[완료] 백업 완료! 모든 {uploader.uploaded_files:,}개 파일이 Google Drive에 업로드되었습니다.")
            print(f"[위치] 백업 위치: Google Drive > {BACKUP_FOLDER_NAME}")
        
        return success
        
    except KeyboardInterrupt:
        print("\n[중단] 사용자에 의해 중단되었습니다.")
        uploader.print_summary()
        return False
    except Exception as e:
        print(f"\n[ERROR] 예상치 못한 오류: {e}")
        uploader.logger.exception("전체 프로세스 오류")
        return False

if __name__ == "__main__":
    print(__doc__)
    success = main()
    
    if success:
        print("\n" + "="*70)
        print("[OK] GPT4wiseTide 백업 프로그램 실행 완료")
        print("="*70)
        sys.exit(0)
    else:
        print("\n" + "="*70)
        print("[ERROR] 백업 실패! 로그를 확인하여 문제를 해결하세요.")
        print("="*70)
        sys.exit(1)
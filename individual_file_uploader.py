#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
개별 파일 덮어쓰기 Google Drive 업로드 프로그램
완전히 독립된 백업 도구 - 배포버전에 포함되지 않음

기능:
- drive_status_report.json에서 누락된 파일 목록 읽기
- 누락된 파일만 선택적으로 업로드
- 기존 파일 덮어쓰기 기능
- 업로드 진행률 실시간 표시
"""

import os
import sys
import json
import time
from datetime import datetime
import pickle

# Windows 콘솔 UTF-8 인코딩 설정
sys.stdout.reconfigure(encoding='utf-8') if hasattr(sys.stdout, 'reconfigure') else None

try:
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    from googleapiclient.discovery import build
    from googleapiclient.errors import HttpError
    from googleapiclient.http import MediaFileUpload
except ImportError as e:
    print(f"[ERROR] 필수 라이브러리 설치 필요: {e}")
    print("설치 명령어: pip install google-api-python-client google-auth-oauthlib google-auth-httplib2")
    sys.exit(1)

# Google Drive API 설정
SCOPES = ['https://www.googleapis.com/auth/drive.file']
SOURCE_DIR = r"C:\Claude_Works\Projects\GPT4wiseTide"
CREDENTIALS_FILE = r"C:\Claude_Works\Projects\GPT4wiseTide\Policy\Register_Key\credentials.json"
TOKEN_FILE = "Policy/Register_Key/token.pickle"
BACKUP_FOLDER_ID = "1D9AvLY9th8cuKthD30KHjWmmq6P4aPO8"
BACKUP_FOLDER_NAME = "(StokAutoTrade)wiseTide_Backup"
STATUS_REPORT_FILE = "drive_status_report.json"

class IndividualFileUploader:
    def __init__(self):
        self.service = None
        self.backup_folder_id = None
        self.uploaded = 0
        self.failed = 0
        self.skipped = 0
        self.overwritten = 0
        self.missing_files = []
        self.uploaded_files = {}
        
    def authenticate(self):
        """Google Drive API 인증"""
        creds = None
        
        # 기존 토큰 파일이 있으면 로드
        if os.path.exists(TOKEN_FILE):
            try:
                with open(TOKEN_FILE, 'rb') as token:
                    creds = pickle.load(token)
                print("[OK] 기존 인증 토큰 로드")
            except Exception as e:
                print(f"[WARNING] 토큰 로드 실패: {e}")
        
        # 토큰이 유효하지 않으면 새로 인증
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                try:
                    creds.refresh(Request())
                    print("[OK] 토큰 갱신")
                except Exception as e:
                    print(f"[ERROR] 토큰 갱신 실패: {e}")
                    creds = None
            
            if not creds:
                if not os.path.exists(CREDENTIALS_FILE):
                    print(f"[ERROR] credentials.json 없음: {CREDENTIALS_FILE}")
                    return False
                
                try:
                    flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_FILE, SCOPES)
                    creds = flow.run_local_server(port=0)
                    print("[OK] 새 인증 완료")
                except Exception as e:
                    print(f"[ERROR] OAuth 인증 실패: {e}")
                    return False
            
            # 토큰 저장
            try:
                os.makedirs(os.path.dirname(TOKEN_FILE), exist_ok=True)
                with open(TOKEN_FILE, 'wb') as token:
                    pickle.dump(creds, token)
                print("[OK] 토큰 저장")
            except Exception as e:
                print(f"[WARNING] 토큰 저장 실패: {e}")
        
        try:
            self.service = build('drive', 'v3', credentials=creds)
            print("[OK] Google Drive API 초기화")
            return True
        except Exception as e:
            print(f"[ERROR] API 초기화 실패: {e}")
            return False
    
    def find_backup_folder(self):
        """백업 폴더 찾기"""
        try:
            query = f"name='{BACKUP_FOLDER_NAME}' and parents in '{BACKUP_FOLDER_ID}' and mimeType='application/vnd.google-apps.folder'"
            results = self.service.files().list(q=query).execute()
            items = results.get('files', [])
            
            if items:
                self.backup_folder_id = items[0]['id']
                print(f"[OK] 백업 폴더 찾음: {BACKUP_FOLDER_NAME}")
                return True
            else:
                print(f"[ERROR] 백업 폴더 없음: {BACKUP_FOLDER_NAME}")
                return False
                
        except Exception as e:
            print(f"[ERROR] 폴더 찾기 실패: {e}")
            return False
    
    def load_status_report(self):
        """상태 리포트에서 누락된 파일 목록 로드"""
        if not os.path.exists(STATUS_REPORT_FILE):
            print(f"[ERROR] 상태 리포트 없음: {STATUS_REPORT_FILE}")
            return False
            
        try:
            with open(STATUS_REPORT_FILE, 'r', encoding='utf-8') as f:
                report = json.load(f)
            
            self.missing_files = report.get('missing_files', [])
            self.uploaded_files = report.get('uploaded_files', {})
            
            print(f"[OK] 상태 리포트 로드: {len(self.missing_files)}개 누락 파일")
            return len(self.missing_files) > 0
            
        except Exception as e:
            print(f"[ERROR] 상태 리포트 로드 실패: {e}")
            return False
    
    def check_file_exists(self, filename):
        """Google Drive에 파일이 존재하는지 확인"""
        try:
            query = f"name='{filename}' and parents in '{self.backup_folder_id}'"
            results = self.service.files().list(q=query).execute()
            items = results.get('files', [])
            
            if items:
                return items[0]['id']  # 파일 ID 반환
            return None
            
        except Exception as e:
            print(f"[WARNING] 파일 존재 확인 실패 {filename}: {e}")
            return None
    
    def upload_single_file(self, filename, file_path):
        """단일 파일 업로드 (덮어쓰기 지원)"""
        try:
            # 파일 크기 확인
            file_size = os.path.getsize(file_path)
            if file_size > 100 * 1024 * 1024:  # 100MB 제한
                print(f"[SKIP] 파일이 너무 큽니다 (100MB 초과): {filename}")
                self.skipped += 1
                return True
            
            # 기존 파일 확인
            existing_file_id = self.check_file_exists(filename)
            
            if existing_file_id:
                # 기존 파일 덮어쓰기
                try:
                    media = MediaFileUpload(file_path, resumable=False)
                    updated_file = self.service.files().update(
                        fileId=existing_file_id,
                        media_body=media
                    ).execute()
                    
                    self.overwritten += 1
                    print(f"[OVERWRITE] {filename}")
                    return True
                    
                except Exception as e:
                    print(f"[ERROR] 덮어쓰기 실패 {filename}: {e}")
                    # 덮어쓰기 실패시 새 파일로 업로드 시도
                    pass
            
            # 새 파일 업로드
            file_metadata = {
                'name': filename,
                'parents': [self.backup_folder_id]
            }
            
            media = MediaFileUpload(file_path, resumable=False)
            result = self.service.files().create(
                body=file_metadata,
                media_body=media,
                fields='id, name'
            ).execute()
            
            self.uploaded += 1
            print(f"[NEW] {filename}")
            
            # API 제한 방지를 위한 짧은 대기
            time.sleep(0.1)
            
            return True
            
        except Exception as e:
            print(f"[ERROR] 업로드 실패 {filename}: {e}")
            self.failed += 1
            return False
    
    def upload_missing_files(self):
        """누락된 파일들을 업로드"""
        total_files = len(self.missing_files)
        print(f"\n[시작] {total_files}개 누락 파일 업로드 시작")
        
        start_time = time.time()
        
        for i, filename in enumerate(self.missing_files, 1):
            # 로컬 파일 경로 찾기
            file_found = False
            for root, dirs, files in os.walk(SOURCE_DIR):
                if filename in files:
                    file_path = os.path.join(root, filename)
                    file_found = True
                    break
            
            if not file_found:
                print(f"[ERROR] 로컬 파일 없음: {filename}")
                self.failed += 1
                continue
            
            # 진행률 표시
            progress = (i / total_files) * 100
            processed = self.uploaded + self.failed + self.skipped + self.overwritten
            
            if processed > 0 and processed % 50 == 0:
                elapsed = time.time() - start_time
                rate = processed / elapsed if elapsed > 0 else 0
                remaining = total_files - processed
                eta = remaining / rate if rate > 0 else 0
                
                print(f"\n[진행률] {processed}/{total_files} ({progress:.1f}%)")
                print(f"[상태] 새업로드:{self.uploaded}, 덮어쓰기:{self.overwritten}, 실패:{self.failed}, 건너뜀:{self.skipped}")
                print(f"[예상] 남은 시간: {eta/60:.1f}분\n")
            
            # 파일 업로드
            self.upload_single_file(filename, file_path)
        
        return True
    
    def print_summary(self):
        """업로드 결과 요약"""
        total_processed = self.uploaded + self.overwritten + self.failed + self.skipped
        
        print("\n" + "="*60)
        print("개별 파일 업로드 완료 보고서")
        print("="*60)
        print(f"처리된 파일: {total_processed}개")
        print(f"새 업로드: {self.uploaded}개")
        print(f"덮어쓰기: {self.overwritten}개")
        print(f"건너뜀: {self.skipped}개")
        print(f"실패: {self.failed}개")
        
        if total_processed > 0:
            success_rate = ((self.uploaded + self.overwritten) / total_processed) * 100
            print(f"성공률: {success_rate:.1f}%")
        
        print(f"업로드 시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("="*60)
        
        if self.failed > 0:
            print(f"[WARNING] {self.failed}개 파일 업로드 실패")
        else:
            print("[OK] 모든 누락 파일 업로드 완료!")

def main():
    """메인 함수"""
    print(">> 개별 파일 Google Drive 업로드 프로그램")
    print("="*60)
    
    # 소스 디렉토리 확인
    if not os.path.exists(SOURCE_DIR):
        print(f"[ERROR] 소스 디렉토리 없음: {SOURCE_DIR}")
        return False
    
    # credentials.json 확인
    if not os.path.exists(CREDENTIALS_FILE):
        print(f"[ERROR] credentials.json 없음: {CREDENTIALS_FILE}")
        return False
    
    # 업로드 실행
    uploader = IndividualFileUploader()
    
    try:
        # 1. 인증
        print("\n[1단계] Google Drive 인증...")
        if not uploader.authenticate():
            return False
        
        # 2. 백업 폴더 찾기
        print("\n[2단계] 백업 폴더 찾기...")
        if not uploader.find_backup_folder():
            return False
        
        # 3. 상태 리포트 로드
        print("\n[3단계] 상태 리포트 로드...")
        if not uploader.load_status_report():
            print("[INFO] 누락된 파일이 없거나 상태 리포트를 찾을 수 없습니다.")
            return False
        
        # 4. 누락 파일 업로드
        print("\n[4단계] 누락 파일 업로드 시작...")
        success = uploader.upload_missing_files()
        
        # 5. 결과 출력
        uploader.print_summary()
        
        return success
        
    except KeyboardInterrupt:
        print("\n[중단] 사용자에 의해 중단됨")
        uploader.print_summary()
        return False
    except Exception as e:
        print(f"\n[ERROR] 예상치 못한 오류: {e}")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Google Drive 폴더 상태 확인 프로그램
현재 업로드된 파일 목록과 누락된 파일들을 확인
"""

import os
import sys
import pickle
import json
from pathlib import Path

try:
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    from googleapiclient.discovery import build
    from googleapiclient.errors import HttpError
except ImportError as e:
    print(f"[ERROR] Required libraries missing: {e}")
    sys.exit(1)

# Configuration
SCOPES = ['https://www.googleapis.com/auth/drive.file']
SOURCE_DIR = r"C:\Claude_Works\Projects\GPT4wiseTide"
CREDENTIALS_FILE = r"C:\Claude_Works\Projects\GPT4wiseTide\Policy\Register_Key\credentials.json"
TOKEN_FILE = "Policy/Register_Key/token.pickle"
PARENT_FOLDER_ID = "1D9AvLY9th8cuKthD30KHjWmmq6P4aPO8"
BACKUP_FOLDER_NAME = "(StokAutoTrade)wiseTide_Backup"

class DriveStatusChecker:
    def __init__(self):
        self.service = None
        self.backup_folder_id = None
        
    def authenticate_with_credentials(self, email, password):
        """사용자 계정으로 직접 인증 시도"""
        print(f"[AUTH] Attempting authentication for {email}...")
        # 참고: Google API는 보안상 직접 비밀번호 인증을 지원하지 않음
        # OAuth2 플로우를 사용해야 함
        print("[INFO] Google API requires OAuth2 authentication, not direct password")
        return self.authenticate_oauth()
    
    def authenticate_oauth(self):
        """OAuth2 인증"""
        print("[AUTH] Starting OAuth authentication...")
        creds = None
        
        if os.path.exists(TOKEN_FILE):
            print("[AUTH] Loading existing token...")
            with open(TOKEN_FILE, 'rb') as token:
                creds = pickle.load(token)
        
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                print("[AUTH] Refreshing token...")
                try:
                    creds.refresh(Request())
                except Exception as e:
                    print(f"[ERROR] Token refresh failed: {e}")
                    creds = None
            
            if not creds:
                print("[AUTH] Creating new token...")
                if not os.path.exists(CREDENTIALS_FILE):
                    print(f"[ERROR] Credentials file not found: {CREDENTIALS_FILE}")
                    return False
                
                try:
                    flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_FILE, SCOPES)
                    creds = flow.run_local_server(port=0)
                except Exception as e:
                    print(f"[ERROR] OAuth flow failed: {e}")
                    return False
            
            print("[AUTH] Saving token...")
            os.makedirs(os.path.dirname(TOKEN_FILE), exist_ok=True)
            with open(TOKEN_FILE, 'wb') as token:
                pickle.dump(creds, token)
        
        try:
            self.service = build('drive', 'v3', credentials=creds)
            print("[OK] Authentication successful")
            return True
        except Exception as e:
            print(f"[ERROR] Service creation failed: {e}")
            return False
    
    def find_backup_folder(self):
        """백업 폴더 찾기"""
        print("[FOLDER] Looking for backup folder...")
        
        try:
            query = f"name='{BACKUP_FOLDER_NAME}' and parents in '{PARENT_FOLDER_ID}' and mimeType='application/vnd.google-apps.folder'"
            results = self.service.files().list(q=query).execute()
            items = results.get('files', [])
            
            if items:
                self.backup_folder_id = items[0]['id']
                print(f"[OK] Found backup folder: {BACKUP_FOLDER_NAME}")
                return True
            else:
                print(f"[ERROR] Backup folder not found: {BACKUP_FOLDER_NAME}")
                return False
                
        except Exception as e:
            print(f"[ERROR] Failed to find backup folder: {e}")
            return False
    
    def get_uploaded_files(self):
        """업로드된 파일 목록 가져오기"""
        print("[CHECK] Getting uploaded files list...")
        uploaded_files = {}
        
        try:
            page_token = None
            while True:
                query = f"parents in '{self.backup_folder_id}'"
                results = self.service.files().list(
                    q=query,
                    pageSize=1000,
                    fields="nextPageToken, files(id, name, size, modifiedTime)",
                    pageToken=page_token
                ).execute()
                
                items = results.get('files', [])
                for item in items:
                    uploaded_files[item['name']] = {
                        'id': item['id'],
                        'size': item.get('size', 0),
                        'modified': item.get('modifiedTime', '')
                    }
                
                page_token = results.get('nextPageToken')
                if not page_token:
                    break
            
            print(f"[OK] Found {len(uploaded_files)} files in Google Drive")
            return uploaded_files
            
        except Exception as e:
            print(f"[ERROR] Failed to get uploaded files: {e}")
            return {}
    
    def get_local_files(self):
        """로컬 파일 목록 가져오기"""
        print("[CHECK] Getting local files list...")
        local_files = {}
        
        try:
            for root, dirs, files in os.walk(SOURCE_DIR):
                # Skip hidden directories
                dirs[:] = [d for d in dirs if not d.startswith('.') and d not in ['__pycache__', 'node_modules']]
                
                for file in files:
                    if file.startswith('.') or file.endswith(('.tmp', '.pyc')):
                        continue
                    
                    file_path = os.path.join(root, file)
                    try:
                        stat = os.stat(file_path)
                        relative_path = os.path.relpath(file_path, SOURCE_DIR)
                        local_files[file] = {
                            'path': file_path,
                            'relative_path': relative_path,
                            'size': stat.st_size,
                            'modified': stat.st_mtime
                        }
                    except OSError:
                        pass  # Skip inaccessible files
            
            print(f"[OK] Found {len(local_files)} local files")
            return local_files
            
        except Exception as e:
            print(f"[ERROR] Failed to get local files: {e}")
            return {}
    
    def compare_files(self, uploaded_files, local_files):
        """파일 비교 및 상태 분석"""
        print("[COMPARE] Comparing local and uploaded files...")
        
        # 업로드된 파일들
        uploaded_names = set(uploaded_files.keys())
        local_names = set(local_files.keys())
        
        # 통계
        uploaded_count = len(uploaded_names)
        local_count = len(local_names)
        missing_count = len(local_names - uploaded_names)
        extra_count = len(uploaded_names - local_names)
        
        print("\n" + "="*60)
        print("FILE COMPARISON REPORT")
        print("="*60)
        print(f"Local files: {local_count}")
        print(f"Uploaded files: {uploaded_count}")
        print(f"Missing from Drive: {missing_count}")
        print(f"Extra in Drive: {extra_count}")
        print("-"*60)
        
        # 누락된 파일들
        missing_files = local_names - uploaded_names
        if missing_files:
            print(f"\nMISSING FILES ({len(missing_files)}):")
            for filename in sorted(missing_files):
                local_info = local_files[filename]
                size_mb = local_info['size'] / (1024*1024)
                print(f"  - {filename} ({size_mb:.2f} MB) - {local_info['relative_path']}")
        
        # 추가로 있는 파일들
        extra_files = uploaded_names - local_names
        if extra_files:
            print(f"\nEXTRA FILES IN DRIVE ({len(extra_files)}):")
            for filename in sorted(extra_files):
                print(f"  - {filename}")
        
        print("="*60)
        
        # 결과를 JSON 파일로 저장
        result = {
            'timestamp': str(datetime.now()),
            'local_count': local_count,
            'uploaded_count': uploaded_count,
            'missing_count': missing_count,
            'extra_count': extra_count,
            'missing_files': list(missing_files),
            'extra_files': list(extra_files),
            'uploaded_files': uploaded_files,
            'local_files': {k: {**v, 'path': str(v['path'])} for k, v in local_files.items()}
        }
        
        with open('drive_status_report.json', 'w', encoding='utf-8') as f:
            json.dump(result, f, indent=2, ensure_ascii=False)
        
        print(f"[OK] Detailed report saved to: drive_status_report.json")
        
        return missing_files, extra_files

def main():
    """메인 함수"""
    print("Google Drive Backup Status Checker")
    print("="*60)
    
    # 인증 정보
    email = "songhawk@gmail.com"
    password = "!Genesis118"
    
    checker = DriveStatusChecker()
    
    try:
        # Step 1: 인증
        print("\n[STEP 1] Authentication")
        if not checker.authenticate_with_credentials(email, password):
            print("[ERROR] Authentication failed")
            return False
        
        # Step 2: 백업 폴더 찾기
        print("\n[STEP 2] Finding backup folder")
        if not checker.find_backup_folder():
            print("[ERROR] Backup folder not found")
            return False
        
        # Step 3: 업로드된 파일 목록 가져오기
        print("\n[STEP 3] Getting uploaded files")
        uploaded_files = checker.get_uploaded_files()
        if not uploaded_files:
            print("[WARNING] No uploaded files found or failed to retrieve")
        
        # Step 4: 로컬 파일 목록 가져오기
        print("\n[STEP 4] Getting local files")
        local_files = checker.get_local_files()
        if not local_files:
            print("[ERROR] No local files found")
            return False
        
        # Step 5: 파일 비교
        print("\n[STEP 5] Comparing files")
        missing_files, extra_files = checker.compare_files(uploaded_files, local_files)
        
        # 결과 요약
        print(f"\n[SUMMARY] Upload status check completed")
        print(f"[SUMMARY] Missing files: {len(missing_files)}")
        print(f"[SUMMARY] Report saved to: drive_status_report.json")
        
        return True
        
    except Exception as e:
        print(f"\n[ERROR] Unexpected error: {e}")
        return False

if __name__ == "__main__":
    from datetime import datetime
    success = main()
    sys.exit(0 if success else 1)
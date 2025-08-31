#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
간단하고 안정적인 Google Drive 전체 백업 프로그램
완전히 독립된 백업 도구 - 배포버전에 포함되지 않음

목적: C:\\Claude_Works\\Projects\\GPT4wiseTide 폴더의 모든 파일을 
     Google Drive의 지정된 폴더에 백업
"""

import os
import sys
import json
import time
from pathlib import Path
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

# 대상 Google Drive 설정
PARENT_FOLDER_ID = "1D9AvLY9th8cuKthD30KHjWmmq6P4aPO8"
BACKUP_FOLDER_NAME = "(StokAutoTrade)wiseTide_Backup"

class SimpleBackup:
    def __init__(self):
        self.service = None
        self.backup_folder_id = None
        self.uploaded = 0
        self.failed = 0
        self.skipped = 0
        self.total = 0
        
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
    
    def create_backup_folder(self):
        """백업 폴더 생성 또는 찾기"""
        try:
            # 기존 폴더 검색
            query = f"name='{BACKUP_FOLDER_NAME}' and parents in '{PARENT_FOLDER_ID}' and mimeType='application/vnd.google-apps.folder'"
            results = self.service.files().list(q=query).execute()
            items = results.get('files', [])
            
            if items:
                self.backup_folder_id = items[0]['id']
                print(f"[OK] 기존 폴더 사용: {BACKUP_FOLDER_NAME}")
            else:
                # 새 폴더 생성
                folder_metadata = {
                    'name': BACKUP_FOLDER_NAME,
                    'parents': [PARENT_FOLDER_ID],
                    'mimeType': 'application/vnd.google-apps.folder'
                }
                folder = self.service.files().create(body=folder_metadata).execute()
                self.backup_folder_id = folder.get('id')
                print(f"[OK] 새 폴더 생성: {BACKUP_FOLDER_NAME}")
            
            return True
        except Exception as e:
            print(f"[ERROR] 폴더 생성/찾기 실패: {e}")
            return False
    
    def count_files(self):
        """업로드할 파일 개수 계산"""
        total = 0
        try:
            for root, dirs, files in os.walk(SOURCE_DIR):
                # 숨김 폴더 제외
                dirs[:] = [d for d in dirs if not d.startswith('.') and d not in ['__pycache__', 'node_modules']]
                
                for file in files:
                    if not file.startswith('.') and not file.endswith(('.tmp', '.pyc')):
                        total += 1
                        
            return total
        except Exception as e:
            print(f"[ERROR] 파일 개수 계산 실패: {e}")
            return 0
    
    def upload_single_file(self, file_path, relative_path):
        """단일 파일 업로드"""
        try:
            # 파일 크기 확인
            file_size = os.path.getsize(file_path)
            if file_size > 100 * 1024 * 1024:  # 100MB 제한
                print(f"[SKIP] 파일이 너무 큽니다 (100MB 초과): {relative_path}")
                self.skipped += 1
                return True
            
            # 파일 메타데이터
            file_metadata = {
                'name': os.path.basename(relative_path),
                'parents': [self.backup_folder_id]
            }
            
            # 미디어 업로드 객체 생성 (간단한 방식)
            media = MediaFileUpload(file_path, resumable=False)
            
            # 업로드 실행
            result = self.service.files().create(
                body=file_metadata,
                media_body=media,
                fields='id, name'
            ).execute()
            
            self.uploaded += 1
            print(f"[OK] ({self.uploaded}/{self.total}) {relative_path}")
            
            # API 제한 방지를 위한 짧은 대기
            time.sleep(0.1)
            
            return True
            
        except Exception as e:
            print(f"[ERROR] 업로드 실패 {relative_path}: {e}")
            self.failed += 1
            return False
    
    def backup_all_files(self):
        """모든 파일 백업"""
        print(f"[정보] 소스: {SOURCE_DIR}")
        print(f"[정보] 대상: Google Drive/{BACKUP_FOLDER_NAME}")
        
        # 파일 개수 계산
        self.total = self.count_files()
        print(f"[정보] 총 파일: {self.total}개")
        
        if self.total == 0:
            print("[ERROR] 백업할 파일이 없습니다")
            return False
        
        start_time = time.time()
        
        try:
            for root, dirs, files in os.walk(SOURCE_DIR):
                # 숨김 폴더 제외
                dirs[:] = [d for d in dirs if not d.startswith('.') and d not in ['__pycache__', 'node_modules']]
                
                for file in files:
                    if file.startswith('.') or file.endswith(('.tmp', '.pyc')):
                        continue
                    
                    file_path = os.path.join(root, file)
                    relative_path = os.path.relpath(file_path, SOURCE_DIR)
                    
                    # 진행률 표시 (50개마다)
                    processed = self.uploaded + self.failed + self.skipped
                    if processed > 0 and processed % 50 == 0:
                        elapsed = time.time() - start_time
                        rate = processed / elapsed
                        remaining = self.total - processed
                        eta = remaining / rate if rate > 0 else 0
                        progress = (processed / self.total) * 100
                        print(f"[진행률] {processed}/{self.total} ({progress:.1f}%) - 예상 남은 시간: {eta/60:.1f}분")
                    
                    # 파일 업로드
                    self.upload_single_file(file_path, relative_path)
            
            return True
            
        except Exception as e:
            print(f"[ERROR] 백업 프로세스 실패: {e}")
            return False
    
    def print_summary(self):
        """백업 결과 요약"""
        print("\n" + "="*60)
        print("GPT4wiseTide 백업 완료 보고서")
        print("="*60)
        print(f"전체 파일: {self.total}개")
        print(f"업로드 성공: {self.uploaded}개")
        print(f"건너뜀: {self.skipped}개")
        print(f"실패: {self.failed}개")
        
        if self.total > 0:
            success_rate = (self.uploaded / self.total) * 100
            print(f"성공률: {success_rate:.1f}%")
        
        print(f"백업 시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("="*60)
        
        if self.failed > 0:
            print(f"[WARNING] {self.failed}개 파일 업로드 실패")
        else:
            print("[OK] 모든 파일 백업 완료!")

def main():
    """메인 함수"""
    print(">> GPT4wiseTide 간단 백업 프로그램")
    print("="*60)
    
    # 소스 디렉토리 확인
    if not os.path.exists(SOURCE_DIR):
        print(f"[ERROR] 소스 디렉토리 없음: {SOURCE_DIR}")
        return False
    
    # credentials.json 확인
    if not os.path.exists(CREDENTIALS_FILE):
        print(f"[ERROR] credentials.json 없음: {CREDENTIALS_FILE}")
        return False
    
    # 백업 실행
    backup = SimpleBackup()
    
    try:
        # 1. 인증
        print("\n[1단계] Google Drive 인증...")
        if not backup.authenticate():
            return False
        
        # 2. 백업 폴더 생성
        print("\n[2단계] 백업 폴더 준비...")
        if not backup.create_backup_folder():
            return False
        
        # 3. 백업 실행
        print("\n[3단계] 파일 백업 시작...")
        success = backup.backup_all_files()
        
        # 4. 결과 출력
        backup.print_summary()
        
        return success
        
    except KeyboardInterrupt:
        print("\n[중단] 사용자에 의해 중단됨")
        backup.print_summary()
        return False
    except Exception as e:
        print(f"\n[ERROR] 예상치 못한 오류: {e}")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
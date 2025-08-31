#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Google Drive API 간단 테스트
"""

import os
import sys
import json
from pathlib import Path

# 한글 출력 설정
sys.stdout.reconfigure(encoding='utf-8')

# Google API 라이브러리
try:
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    from google.auth.transport.requests import Request
    from googleapiclient.discovery import build
    from googleapiclient.http import MediaFileUpload
    import pickle
    print("Google API 라이브러리 로드 성공")
except ImportError as e:
    print(f"라이브러리 오류: {e}")
    sys.exit(1)

# OAuth 설정
SCOPES = ['https://www.googleapis.com/auth/drive.file']
CREDENTIALS_FILE = "Policy/Register_Key/credentials.json"
TOKEN_FILE = "Policy/Register_Key/token.pickle"

def authenticate_google_drive():
    """Google Drive 인증"""
    creds = None
    
    # 기존 토큰 확인
    if os.path.exists(TOKEN_FILE):
        with open(TOKEN_FILE, 'rb') as token:
            creds = pickle.load(token)
    
    # 토큰 갱신 또는 새 인증
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                CREDENTIALS_FILE, SCOPES)
            creds = flow.run_local_server(port=0)
        
        # 토큰 저장
        with open(TOKEN_FILE, 'wb') as token:
            pickle.dump(creds, token)
    
    return build('drive', 'v3', credentials=creds)

def upload_test_file():
    """테스트 파일 업로드"""
    try:
        print("=== Google Drive 업로드 테스트 ===")
        
        # 인증
        service = authenticate_google_drive()
        print("인증 성공")
        
        # 업로드할 파일 확인
        test_file = "sample_upload_test.txt"
        if not os.path.exists(test_file):
            print(f"테스트 파일 없음: {test_file}")
            return False
        
        # 폴더 ID (URL에서 추출)
        folder_id = "1D9AvLY9th8cuKthD30KHjWmmq6P4aPO8"
        
        # 파일 메타데이터
        file_metadata = {
            'name': 'claude_upload_test.txt',
            'parents': [folder_id]
        }
        
        # 파일 업로드
        media = MediaFileUpload(test_file, resumable=True)
        
        print("파일 업로드 시작...")
        file = service.files().create(
            body=file_metadata,
            media_body=media,
            fields='id,name,webViewLink'
        ).execute()
        
        print("업로드 성공!")
        print(f"파일 ID: {file.get('id')}")
        print(f"파일명: {file.get('name')}")
        print(f"링크: {file.get('webViewLink')}")
        
        return True
        
    except Exception as e:
        print(f"업로드 실패: {e}")
        return False

if __name__ == "__main__":
    success = upload_test_file()
    if success:
        print("테스트 완료!")
    else:
        print("테스트 실패!")
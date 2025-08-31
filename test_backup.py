#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
테스트용 간단한 백업 프로그램
"""

import os
import sys

try:
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    from googleapiclient.discovery import build
    from googleapiclient.http import MediaFileUpload
    import pickle
    
    print("API libraries loaded successfully")
except ImportError as e:
    print(f"Import error: {e}")
    sys.exit(1)

# Settings
SCOPES = ['https://www.googleapis.com/auth/drive.file']
SOURCE_DIR = r"C:\Claude_Works\Projects\GPT4wiseTide"
CREDENTIALS_FILE = r"C:\Claude_Works\Projects\GPT4wiseTide\Policy\Register_Key\credentials.json"
TOKEN_FILE = "Policy/Register_Key/token.pickle"
PARENT_FOLDER_ID = "1D9AvLY9th8cuKthD30KHjWmmq6P4aPO8"
BACKUP_FOLDER_NAME = "(StokAutoTrade)wiseTide_Backup"

def authenticate():
    print("Starting authentication...")
    creds = None
    
    if os.path.exists(TOKEN_FILE):
        print("Loading existing token...")
        with open(TOKEN_FILE, 'rb') as token:
            creds = pickle.load(token)
    
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            print("Refreshing token...")
            creds.refresh(Request())
        else:
            print("Creating new token...")
            flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_FILE, SCOPES)
            creds = flow.run_local_server(port=0)
        
        print("Saving token...")
        os.makedirs(os.path.dirname(TOKEN_FILE), exist_ok=True)
        with open(TOKEN_FILE, 'wb') as token:
            pickle.dump(creds, token)
    
    print("Building service...")
    service = build('drive', 'v3', credentials=creds)
    print("Authentication successful")
    return service

def main():
    print("Starting backup program...")
    
    # Check source directory
    if not os.path.exists(SOURCE_DIR):
        print(f"Source directory not found: {SOURCE_DIR}")
        return False
    
    # Check credentials file
    if not os.path.exists(CREDENTIALS_FILE):
        print(f"Credentials file not found: {CREDENTIALS_FILE}")
        return False
    
    print("Files exist, attempting authentication...")
    
    try:
        service = authenticate()
        print("Service created successfully")
        
        # Count files
        file_count = 0
        for root, dirs, files in os.walk(SOURCE_DIR):
            dirs[:] = [d for d in dirs if not d.startswith('.')]
            file_count += len([f for f in files if not f.startswith('.')])
        
        print(f"Found {file_count} files to backup")
        
        # Create backup folder
        query = f"name='{BACKUP_FOLDER_NAME}' and parents in '{PARENT_FOLDER_ID}' and mimeType='application/vnd.google-apps.folder'"
        results = service.files().list(q=query).execute()
        items = results.get('files', [])
        
        if items:
            backup_folder_id = items[0]['id']
            print("Found existing backup folder")
        else:
            folder_metadata = {
                'name': BACKUP_FOLDER_NAME,
                'parents': [PARENT_FOLDER_ID],
                'mimeType': 'application/vnd.google-apps.folder'
            }
            folder = service.files().create(body=folder_metadata).execute()
            backup_folder_id = folder.get('id')
            print("Created new backup folder")
        
        # Upload first 10 files as test
        uploaded = 0
        for root, dirs, files in os.walk(SOURCE_DIR):
            dirs[:] = [d for d in dirs if not d.startswith('.')]
            
            for file in files:
                if file.startswith('.') or uploaded >= 10:
                    continue
                
                file_path = os.path.join(root, file)
                try:
                    file_metadata = {
                        'name': file,
                        'parents': [backup_folder_id]
                    }
                    
                    media = MediaFileUpload(file_path, resumable=False)
                    result = service.files().create(
                        body=file_metadata,
                        media_body=media,
                        fields='id'
                    ).execute()
                    
                    uploaded += 1
                    print(f"Uploaded {uploaded}/10: {file}")
                    
                except Exception as e:
                    print(f"Failed to upload {file}: {e}")
                
                if uploaded >= 10:
                    break
            
            if uploaded >= 10:
                break
        
        print(f"Test upload completed: {uploaded} files")
        return True
        
    except Exception as e:
        print(f"Error: {e}")
        return False

if __name__ == "__main__":
    success = main()
    if success:
        print("Test completed successfully")
    else:
        print("Test failed")
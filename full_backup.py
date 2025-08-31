#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
GPT4wiseTide 전체 파일 백업 프로그램 (안정화 버전)
완전히 독립된 백업 도구 - 배포버전에 포함되지 않음
"""

import os
import sys
import time
from datetime import datetime
import pickle

try:
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    from googleapiclient.discovery import build
    from googleapiclient.http import MediaFileUpload
    from googleapiclient.errors import HttpError
except ImportError as e:
    print(f"[ERROR] Required libraries missing: {e}")
    print("Install command: pip install google-api-python-client google-auth-oauthlib google-auth-httplib2")
    sys.exit(1)

# Configuration
SCOPES = ['https://www.googleapis.com/auth/drive.file']
SOURCE_DIR = r"C:\Claude_Works\Projects\GPT4wiseTide"
CREDENTIALS_FILE = r"C:\Claude_Works\Projects\GPT4wiseTide\Policy\Register_Key\credentials.json"
TOKEN_FILE = "Policy/Register_Key/token.pickle"
PARENT_FOLDER_ID = "1D9AvLY9th8cuKthD30KHjWmmq6P4aPO8"
BACKUP_FOLDER_NAME = "(StokAutoTrade)wiseTide_Backup"
MAX_FILE_SIZE = 100 * 1024 * 1024  # 100MB limit

class FullBackup:
    def __init__(self):
        self.service = None
        self.backup_folder_id = None
        self.uploaded = 0
        self.failed = 0
        self.skipped = 0
        self.total = 0
        self.start_time = None
        
    def authenticate(self):
        """Authenticate with Google Drive API"""
        print("[AUTH] Starting authentication...")
        creds = None
        
        if os.path.exists(TOKEN_FILE):
            print("[AUTH] Loading existing token...")
            with open(TOKEN_FILE, 'rb') as token:
                creds = pickle.load(token)
        
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                print("[AUTH] Refreshing token...")
                creds.refresh(Request())
            else:
                print("[AUTH] Creating new token...")
                if not os.path.exists(CREDENTIALS_FILE):
                    print(f"[ERROR] Credentials file not found: {CREDENTIALS_FILE}")
                    return False
                
                flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_FILE, SCOPES)
                creds = flow.run_local_server(port=0)
            
            print("[AUTH] Saving token...")
            os.makedirs(os.path.dirname(TOKEN_FILE), exist_ok=True)
            with open(TOKEN_FILE, 'wb') as token:
                pickle.dump(creds, token)
        
        print("[AUTH] Building service...")
        self.service = build('drive', 'v3', credentials=creds)
        print("[OK] Authentication successful")
        return True
    
    def setup_backup_folder(self):
        """Create or find backup folder"""
        print("[FOLDER] Setting up backup folder...")
        
        try:
            # Search for existing folder
            query = f"name='{BACKUP_FOLDER_NAME}' and parents in '{PARENT_FOLDER_ID}' and mimeType='application/vnd.google-apps.folder'"
            results = self.service.files().list(q=query).execute()
            items = results.get('files', [])
            
            if items:
                self.backup_folder_id = items[0]['id']
                print(f"[OK] Using existing backup folder: {BACKUP_FOLDER_NAME}")
            else:
                # Create new folder
                folder_metadata = {
                    'name': BACKUP_FOLDER_NAME,
                    'parents': [PARENT_FOLDER_ID],
                    'mimeType': 'application/vnd.google-apps.folder'
                }
                folder = self.service.files().create(body=folder_metadata).execute()
                self.backup_folder_id = folder.get('id')
                print(f"[OK] Created new backup folder: {BACKUP_FOLDER_NAME}")
            
            return True
            
        except Exception as e:
            print(f"[ERROR] Failed to setup backup folder: {e}")
            return False
    
    def count_files(self):
        """Count total files to backup"""
        print("[COUNT] Counting files...")
        total = 0
        
        for root, dirs, files in os.walk(SOURCE_DIR):
            # Skip hidden directories
            dirs[:] = [d for d in dirs if not d.startswith('.') and d not in ['__pycache__', 'node_modules']]
            
            for file in files:
                if not file.startswith('.') and not file.endswith(('.tmp', '.pyc')):
                    file_path = os.path.join(root, file)
                    try:
                        size = os.path.getsize(file_path)
                        if size <= MAX_FILE_SIZE:
                            total += 1
                    except OSError:
                        pass  # Skip files we can't access
        
        self.total = total
        print(f"[OK] Found {total} files to backup")
        return total
    
    def upload_file(self, file_path, filename):
        """Upload a single file"""
        try:
            # Check file size
            file_size = os.path.getsize(file_path)
            if file_size > MAX_FILE_SIZE:
                print(f"[SKIP] File too large (>100MB): {filename}")
                self.skipped += 1
                return True
            
            # File metadata
            file_metadata = {
                'name': filename,
                'parents': [self.backup_folder_id]
            }
            
            # Upload file
            media = MediaFileUpload(file_path, resumable=False)
            result = self.service.files().create(
                body=file_metadata,
                media_body=media,
                fields='id'
            ).execute()
            
            self.uploaded += 1
            
            # Progress update
            if self.uploaded % 50 == 0 or self.uploaded == self.total:
                self.print_progress()
            
            # Rate limiting
            time.sleep(0.1)
            
            return True
            
        except HttpError as e:
            print(f"[ERROR] HTTP error uploading {filename}: {e}")
            self.failed += 1
            return False
        except Exception as e:
            print(f"[ERROR] Failed to upload {filename}: {e}")
            self.failed += 1
            return False
    
    def print_progress(self):
        """Print progress information"""
        processed = self.uploaded + self.failed + self.skipped
        if self.total > 0:
            progress = (processed / self.total) * 100
            
            if self.start_time:
                elapsed = time.time() - self.start_time
                rate = processed / elapsed if elapsed > 0 else 0
                remaining = self.total - processed
                eta = remaining / rate if rate > 0 else 0
                
                print(f"[PROGRESS] {processed}/{self.total} ({progress:.1f}%) - "
                      f"Upload: {self.uploaded}, Failed: {self.failed}, Skipped: {self.skipped} - "
                      f"Rate: {rate:.1f} files/sec - ETA: {eta/60:.1f} min")
    
    def backup_all_files(self):
        """Backup all files"""
        print(f"[BACKUP] Starting full backup...")
        print(f"[BACKUP] Source: {SOURCE_DIR}")
        print(f"[BACKUP] Target: Google Drive/{BACKUP_FOLDER_NAME}")
        print(f"[BACKUP] Total files: {self.total}")
        
        self.start_time = time.time()
        
        for root, dirs, files in os.walk(SOURCE_DIR):
            # Skip hidden directories
            dirs[:] = [d for d in dirs if not d.startswith('.') and d not in ['__pycache__', 'node_modules']]
            
            for file in files:
                if file.startswith('.') or file.endswith(('.tmp', '.pyc')):
                    continue
                
                file_path = os.path.join(root, file)
                
                # Upload file
                self.upload_file(file_path, file)
                
                # Check if we should continue
                if self.uploaded + self.failed + self.skipped >= self.total:
                    break
            
            if self.uploaded + self.failed + self.skipped >= self.total:
                break
        
        return True
    
    def print_final_summary(self):
        """Print final backup summary"""
        elapsed = time.time() - self.start_time if self.start_time else 0
        
        print("\n" + "="*70)
        print("GPT4wiseTide BACKUP COMPLETION REPORT")
        print("="*70)
        print(f"Source Directory: {SOURCE_DIR}")
        print(f"Target: Google Drive/{BACKUP_FOLDER_NAME}")
        print(f"Backup Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"Duration: {elapsed/60:.1f} minutes")
        print("-"*70)
        print(f"Total Files: {self.total}")
        print(f"Successfully Uploaded: {self.uploaded}")
        print(f"Failed: {self.failed}")
        print(f"Skipped (too large): {self.skipped}")
        
        if self.total > 0:
            success_rate = (self.uploaded / self.total) * 100
            print(f"Success Rate: {success_rate:.1f}%")
        
        if elapsed > 0:
            avg_rate = (self.uploaded + self.failed + self.skipped) / elapsed
            print(f"Average Rate: {avg_rate:.1f} files/second")
        
        print("="*70)
        
        if self.failed > 0:
            print(f"[WARNING] {self.failed} files failed to upload")
        elif self.uploaded == self.total:
            print("[SUCCESS] ALL FILES BACKED UP SUCCESSFULLY!")
        else:
            print("[INFO] Backup completed with some files skipped")

def main():
    """Main function"""
    print("GPT4wiseTide Complete Backup Program")
    print("="*70)
    
    # Verify prerequisites
    if not os.path.exists(SOURCE_DIR):
        print(f"[ERROR] Source directory not found: {SOURCE_DIR}")
        return False
    
    if not os.path.exists(CREDENTIALS_FILE):
        print(f"[ERROR] Credentials file not found: {CREDENTIALS_FILE}")
        return False
    
    # Initialize backup
    backup = FullBackup()
    
    try:
        # Step 1: Authenticate
        if not backup.authenticate():
            return False
        
        # Step 2: Setup backup folder
        if not backup.setup_backup_folder():
            return False
        
        # Step 3: Count files
        if backup.count_files() == 0:
            print("[ERROR] No files found to backup")
            return False
        
        # Step 4: Confirm backup
        print(f"\n[CONFIRM] About to backup {backup.total} files to Google Drive")
        print(f"[CONFIRM] This will take approximately {backup.total * 0.5 / 60:.0f} minutes")
        print("[CONFIRM] Starting automatic backup in 3 seconds...")
        time.sleep(3)
        
        # Step 5: Execute backup
        success = backup.backup_all_files()
        
        # Step 6: Print summary
        backup.print_final_summary()
        
        return success and backup.failed == 0
        
    except KeyboardInterrupt:
        print("\n[INTERRUPTED] Backup interrupted by user")
        backup.print_final_summary()
        return False
    except Exception as e:
        print(f"\n[ERROR] Unexpected error: {e}")
        return False

if __name__ == "__main__":
    success = main()
    print(f"\n[EXIT] Program completed with status: {'SUCCESS' if success else 'FAILURE'}")
    sys.exit(0 if success else 1)
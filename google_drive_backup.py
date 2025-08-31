#!/usr/bin/env python3
"""
독립적인 Google Drive 백업 유틸리티
- tideWise 프로젝트 백업 전용 독립 프로그램
- credentials.json을 사용한 Google Drive API 연동
- 지정된 Google Drive 폴더에 업로드/삭제 기능
"""

import os
import json
import sys
from pathlib import Path
from typing import Optional, List, Dict, Any
from datetime import datetime
import zipfile
import shutil

# Google Drive API 라이브러리
try:
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    from googleapiclient.discovery import build
    from googleapiclient.http import MediaFileUpload
    from googleapiclient.errors import HttpError
    GOOGLE_LIBS_AVAILABLE = True
except ImportError:
    GOOGLE_LIBS_AVAILABLE = False
    print("Google Drive API 라이브러리가 설치되지 않았습니다.")
    print("설치 명령: pip install google-auth google-auth-oauthlib google-auth-httplib2 google-api-python-client")


class GoogleDriveBackupUtility:
    """Google Drive 백업 전용 독립 유틸리티"""
    
    SCOPES = ['https://www.googleapis.com/auth/drive.file']
    TARGET_FOLDER_ID = '1D9AvLY9th8cuKthD30KHjWmmq6P4aPO8'
    
    def __init__(self, project_root: str = None):
        """
        백업 유틸리티 초기화
        
        Args:
            project_root: 프로젝트 루트 경로
        """
        if project_root is None:
            self.project_root = Path(__file__).parent
        else:
            self.project_root = Path(project_root)
            
        self.credentials_path = self.project_root / "Policy" / "Register_Key" / "credentials.json"
        self.token_path = self.project_root / "token.json"
        self.service = None
        
        print(f"Google Drive 백업 유틸리티 초기화")
        print(f"프로젝트 경로: {self.project_root}")
        print(f"인증 파일: {self.credentials_path}")
        
    def authenticate(self) -> bool:
        """Google Drive API 인증"""
        if not GOOGLE_LIBS_AVAILABLE:
            print("❌ Google Drive API 라이브러리가 필요합니다.")
            return False
            
        if not self.credentials_path.exists():
            print(f"❌ credentials.json 파일이 없습니다: {self.credentials_path}")
            return False
            
        creds = None
        
        # 기존 토큰 파일이 있으면 로드
        if self.token_path.exists():
            try:
                creds = Credentials.from_authorized_user_file(str(self.token_path), self.SCOPES)
            except Exception as e:
                print(f"기존 토큰 로드 실패: {e}")
                
        # 토큰이 유효하지 않거나 만료된 경우 새로 인증
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                try:
                    creds.refresh(Request())
                    print("토큰 갱신 완료")
                except Exception as e:
                    print(f"토큰 갱신 실패: {e}")
                    creds = None
            
            if not creds:
                try:
                    flow = InstalledAppFlow.from_client_secrets_file(
                        str(self.credentials_path), self.SCOPES
                    )
                    creds = flow.run_local_server(port=0)
                    print("새로운 인증 완료")
                except Exception as e:
                    print(f"인증 실패: {e}")
                    return False
                    
        # 토큰 저장
        try:
            with open(self.token_path, 'w') as token_file:
                token_file.write(creds.to_json())
        except Exception as e:
            print(f"토큰 저장 실패: {e}")
            
        # Google Drive 서비스 초기화
        try:
            self.service = build('drive', 'v3', credentials=creds)
            print("✅ Google Drive 연동 성공")
            return True
        except Exception as e:
            print(f"❌ Google Drive 서비스 초기화 실패: {e}")
            return False
            
    def create_project_backup(self) -> Optional[str]:
        """프로젝트 전체 백업 ZIP 파일 생성"""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_filename = f"tideWise_backup_{timestamp}.zip"
        backup_path = self.project_root / backup_filename
        
        print(f"프로젝트 백업 생성 중: {backup_filename}")
        
        # 제외할 디렉토리/파일 목록
        exclude_patterns = {
            '__pycache__',
            '.git',
            'logs',
            '*.log',
            'token.json',
            'node_modules',
            '.env',
            '*.pyc',
            'temp',
            'tmp'
        }
        
        try:
            with zipfile.ZipFile(backup_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                for root, dirs, files in os.walk(self.project_root):
                    # 제외 디렉토리 필터링
                    dirs[:] = [d for d in dirs if d not in exclude_patterns]
                    
                    for file in files:
                        file_path = Path(root) / file
                        
                        # 제외 패턴 확인
                        should_exclude = False
                        for pattern in exclude_patterns:
                            if pattern.startswith('*'):
                                if file.endswith(pattern[1:]):
                                    should_exclude = True
                                    break
                            elif pattern in file or pattern in str(file_path):
                                should_exclude = True
                                break
                                
                        if not should_exclude:
                            # ZIP 내 경로 계산
                            arcname = file_path.relative_to(self.project_root)
                            zipf.write(file_path, arcname)
                            
            print(f"✅ 백업 파일 생성 완료: {backup_path}")
            print(f"파일 크기: {backup_path.stat().st_size / (1024*1024):.1f} MB")
            return str(backup_path)
            
        except Exception as e:
            print(f"❌ 백업 파일 생성 실패: {e}")
            if backup_path.exists():
                backup_path.unlink()
            return None
            
    def upload_to_drive(self, file_path: str) -> bool:
        """파일을 Google Drive에 업로드"""
        if not self.service:
            print("❌ Google Drive 서비스가 초기화되지 않았습니다.")
            return False
            
        file_path = Path(file_path)
        if not file_path.exists():
            print(f"❌ 업로드할 파일이 없습니다: {file_path}")
            return False
            
        try:
            print(f"Google Drive 업로드 시작: {file_path.name}")
            
            # 파일 메타데이터
            file_metadata = {
                'name': file_path.name,
                'parents': [self.TARGET_FOLDER_ID]
            }
            
            # 미디어 업로드
            media = MediaFileUpload(
                str(file_path),
                resumable=True,
                chunksize=1024*1024  # 1MB 청크
            )
            
            # 업로드 실행
            request = self.service.files().create(
                body=file_metadata,
                media_body=media,
                fields='id'
            )
            
            response = None
            while response is None:
                status, response = request.next_chunk()
                if status:
                    progress = int(status.progress() * 100)
                    print(f"업로드 진행률: {progress}%")
                    
            file_id = response.get('id')
            print(f"✅ 업로드 완료! 파일 ID: {file_id}")
            
            # 업로드 후 로컬 백업 파일 삭제
            try:
                file_path.unlink()
                print(f"로컬 백업 파일 삭제: {file_path.name}")
            except Exception as e:
                print(f"로컬 파일 삭제 실패: {e}")
                
            return True
            
        except HttpError as error:
            print(f"❌ Google Drive 업로드 실패: {error}")
            return False
        except Exception as e:
            print(f"❌ 업로드 중 오류: {e}")
            return False
            
    def list_backup_files(self) -> List[Dict[str, Any]]:
        """Google Drive의 백업 파일 목록 조회"""
        if not self.service:
            print("❌ Google Drive 서비스가 초기화되지 않았습니다.")
            return []
            
        try:
            results = self.service.files().list(
                q=f"parents in '{self.TARGET_FOLDER_ID}' and name contains 'tideWise_backup'",
                fields="files(id, name, size, createdTime, modifiedTime)"
            ).execute()
            
            files = results.get('files', [])
            
            if files:
                print(f"\n백업 파일 목록 ({len(files)}개):")
                print("-" * 80)
                for i, file in enumerate(files, 1):
                    created = file.get('createdTime', 'Unknown')[:19].replace('T', ' ')
                    size_mb = int(file.get('size', 0)) / (1024*1024) if file.get('size') else 0
                    print(f"{i:2d}. {file['name']}")
                    print(f"     생성일: {created} | 크기: {size_mb:.1f} MB")
                print("-" * 80)
            else:
                print("백업 파일이 없습니다.")
                
            return files
            
        except HttpError as error:
            print(f"❌ 파일 목록 조회 실패: {error}")
            return []
        except Exception as e:
            print(f"❌ 목록 조회 중 오류: {e}")
            return []
            
    def delete_backup_file(self, file_id: str, file_name: str) -> bool:
        """Google Drive의 백업 파일 삭제"""
        if not self.service:
            print("❌ Google Drive 서비스가 초기화되지 않았습니다.")
            return False
            
        try:
            print(f"삭제 중: {file_name}")
            self.service.files().delete(fileId=file_id).execute()
            print(f"✅ 삭제 완료: {file_name}")
            return True
            
        except HttpError as error:
            print(f"❌ 파일 삭제 실패: {error}")
            return False
        except Exception as e:
            print(f"❌ 삭제 중 오류: {e}")
            return False
            
    def cleanup_old_backups(self, keep_count: int = 5) -> bool:
        """오래된 백업 파일 정리 (최신 N개만 보관)"""
        files = self.list_backup_files()
        if not files:
            return True
            
        # 생성 시간 기준 정렬 (최신순)
        files.sort(key=lambda x: x.get('createdTime', ''), reverse=True)
        
        files_to_delete = files[keep_count:]
        if not files_to_delete:
            print(f"정리할 파일이 없습니다. (현재 {len(files)}개, 보관 설정 {keep_count}개)")
            return True
            
        print(f"\n오래된 백업 파일 {len(files_to_delete)}개 정리 중...")
        
        deleted_count = 0
        for file in files_to_delete:
            if self.delete_backup_file(file['id'], file['name']):
                deleted_count += 1
                
        print(f"✅ {deleted_count}개 파일 정리 완료")
        return deleted_count == len(files_to_delete)
        
    def run_interactive_menu(self):
        """대화형 메뉴 실행"""
        print("\n" + "="*60)
        print("         tideWise Google Drive 백업 유틸리티")
        print("="*60)
        
        if not self.authenticate():
            print("❌ Google Drive 인증에 실패했습니다.")
            return
            
        while True:
            print("\n메뉴:")
            print("1. 프로젝트 전체 백업")
            print("2. 백업 파일 목록 보기")
            print("3. 오래된 백업 정리 (최신 5개만 보관)")
            print("4. 백업 파일 삭제")
            print("0. 종료")
            print("-" * 40)
            
            try:
                choice = input("선택하세요 (0-4): ").strip()
                
                if choice == '0':
                    print("백업 유틸리티를 종료합니다.")
                    break
                elif choice == '1':
                    print("\n프로젝트 백업을 시작합니다...")
                    backup_file = self.create_project_backup()
                    if backup_file:
                        if self.upload_to_drive(backup_file):
                            print("✅ 백업 완료!")
                        else:
                            print("❌ 백업 업로드 실패")
                    else:
                        print("❌ 백업 생성 실패")
                        
                elif choice == '2':
                    self.list_backup_files()
                    
                elif choice == '3':
                    self.cleanup_old_backups()
                    
                elif choice == '4':
                    files = self.list_backup_files()
                    if files:
                        try:
                            file_num = int(input("삭제할 파일 번호: ")) - 1
                            if 0 <= file_num < len(files):
                                file = files[file_num]
                                confirm = input(f"정말 삭제하시겠습니까? '{file['name']}' (y/N): ")
                                if confirm.lower() == 'y':
                                    self.delete_backup_file(file['id'], file['name'])
                            else:
                                print("잘못된 파일 번호입니다.")
                        except ValueError:
                            print("올바른 숫자를 입력하세요.")
                            
                else:
                    print("잘못된 선택입니다.")
                    
                if choice in ['1', '2', '3', '4']:
                    input("\nEnter를 눌러 계속...")
                    
            except (KeyboardInterrupt, EOFError):
                print("\n백업 유틸리티를 종료합니다.")
                break
            except Exception as e:
                print(f"오류 발생: {e}")


def main():
    """메인 실행 함수"""
    print("tideWise Google Drive 백업 유틸리티")
    
    # 프로젝트 루트 경로 확인
    project_root = Path(__file__).parent
    print(f"프로젝트 경로: {project_root}")
    
    # 백업 유틸리티 실행
    backup_utility = GoogleDriveBackupUtility(str(project_root))
    backup_utility.run_interactive_menu()


if __name__ == "__main__":
    main()
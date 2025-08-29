#!/usr/bin/env python3
"""
Register_Key.md 암호화 유틸리티
기존 평문 Register_Key.md 파일을 암호화된 버전으로 변환

사용법:
    python utils/encrypt_register_key.py

주의사항:
- 실행 전 TIDEWISE_SECRET_KEY 환경 변수를 설정해야 합니다
- 원본 파일은 자동으로 백업됩니다 (.backup 확장자)
- 암호화 후에는 복호화 테스트를 수행합니다
"""

import os
import sys
import logging
from pathlib import Path
from datetime import datetime

# 프로젝트 루트 경로 추가
project_root = Path(__file__).parent.parent
sys.path.append(str(project_root))

from support.secure_key_handler import SecureKeyHandler

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('utils/encrypt_register_key.log')
    ]
)
logger = logging.getLogger(__name__)

class RegisterKeyEncryptor:
    """Register_Key.md 파일 암호화 도구"""
    
    def __init__(self):
        """암호화 도구 초기화"""
        self.project_root = Path(__file__).parent.parent
        self.register_key_paths = [
            self.project_root / "Policy" / "Register_Key" / "Register_Key.md",
            self.project_root / "KIS_API_Test" / "Register_Key.md",
            self.project_root / "KIS_API_Test" / "Policy" / "Register_Key" / "Register_Key.md"
        ]
        
        logger.info("Register_Key.md 암호화 도구 초기화")
        logger.info(f"프로젝트 루트: {self.project_root}")
    
    def find_register_key_files(self) -> list:
        """Register_Key.md 파일들을 찾아서 반환"""
        found_files = []
        
        for path in self.register_key_paths:
            if path.exists():
                found_files.append(path)
                logger.info(f"Register_Key.md 파일 발견: {path}")
        
        if not found_files:
            logger.warning("Register_Key.md 파일을 찾을 수 없습니다.")
            logger.info("다음 경로들을 확인했습니다:")
            for path in self.register_key_paths:
                logger.info(f"  - {path}")
        
        return found_files
    
    def backup_file(self, file_path: Path) -> Path:
        """파일 백업 생성"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = file_path.with_suffix(f".backup_{timestamp}")
        
        try:
            # 원본 파일을 백업으로 복사
            import shutil
            shutil.copy2(file_path, backup_path)
            
            logger.info(f"백업 파일 생성: {backup_path}")
            return backup_path
            
        except Exception as e:
            logger.error(f"백업 파일 생성 실패: {e}")
            raise
    
    def is_file_encrypted(self, file_path: Path) -> bool:
        """파일이 이미 암호화되어 있는지 확인"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read().strip()
            
            # Base64 형태인지 간단히 확인
            import base64
            try:
                decoded = base64.b64decode(content)
                # 최소 길이 확인 (salt + nonce + 최소 암호문)
                if len(decoded) >= 32:
                    logger.info(f"파일이 이미 암호화되어 있습니다: {file_path}")
                    return True
            except:
                pass
            
            # 평문 마크다운 형식인지 확인
            if content.startswith('#') or '### 실전투자 계좌 정보' in content:
                logger.info(f"평문 파일 확인: {file_path}")
                return False
            
            logger.warning(f"파일 형식을 확인할 수 없습니다: {file_path}")
            return False
            
        except Exception as e:
            logger.error(f"파일 암호화 상태 확인 실패: {e}")
            return False
    
    def encrypt_file(self, file_path: Path) -> bool:
        """Register_Key.md 파일 암호화"""
        try:
            logger.info(f"파일 암호화 시작: {file_path}")
            
            # 1. 파일이 이미 암호화되어 있는지 확인
            if self.is_file_encrypted(file_path):
                logger.warning(f"파일이 이미 암호화되어 있습니다. 건너뜁니다: {file_path}")
                return True
            
            # 2. SecureKeyHandler 초기화
            handler = SecureKeyHandler()
            
            # 3. 원본 파일 읽기
            with open(file_path, 'r', encoding='utf-8') as f:
                plaintext_content = f.read()
            
            if not plaintext_content.strip():
                logger.error(f"파일이 비어있습니다: {file_path}")
                return False
            
            logger.info(f"원본 파일 읽기 완료 (크기: {len(plaintext_content)} 문자)")
            
            # 4. 백업 생성
            backup_path = self.backup_file(file_path)
            
            # 5. 암호화 수행
            encrypted_content = handler.encrypt(plaintext_content)
            logger.info(f"암호화 완료 (암호문 크기: {len(encrypted_content)} 문자)")
            
            # 6. 암호화된 내용을 원본 파일에 저장
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(encrypted_content)
            
            logger.info(f"암호화된 파일 저장 완료: {file_path}")
            
            # 7. 복호화 테스트
            if self.test_decryption(file_path, plaintext_content):
                logger.info(f"✅ 파일 암호화 성공: {file_path}")
                logger.info(f"📁 백업 파일: {backup_path}")
                return True
            else:
                logger.error(f"❌ 복호화 테스트 실패. 백업에서 복원합니다.")
                # 백업에서 복원
                import shutil
                shutil.copy2(backup_path, file_path)
                return False
                
        except ValueError as e:
            if "마스터 키" in str(e) or "TIDEWISE_SECRET_KEY" in str(e):
                logger.error(f"마스터 키 오류: {e}")
                logger.error("TIDEWISE_SECRET_KEY 환경 변수를 설정해주세요.")
            else:
                logger.error(f"값 오류: {e}")
            return False
        except Exception as e:
            logger.error(f"파일 암호화 실패: {e}")
            return False
    
    def test_decryption(self, file_path: Path, original_content: str) -> bool:
        """암호화된 파일의 복호화 테스트"""
        try:
            logger.info("복호화 테스트 시작...")
            
            handler = SecureKeyHandler()
            
            # 암호화된 파일 읽기
            with open(file_path, 'r', encoding='utf-8') as f:
                encrypted_content = f.read().strip()
            
            # 복호화 수행
            decrypted_content = handler.decrypt(encrypted_content)
            
            # 원본과 비교
            if decrypted_content == original_content:
                logger.info("✅ 복호화 테스트 성공 - 원본과 일치")
                return True
            else:
                logger.error("❌ 복호화 테스트 실패 - 원본과 불일치")
                logger.error(f"원본 길이: {len(original_content)}, 복호화 길이: {len(decrypted_content)}")
                return False
                
        except Exception as e:
            logger.error(f"복호화 테스트 실패: {e}")
            return False
    
    def encrypt_all_files(self) -> dict:
        """모든 Register_Key.md 파일 암호화"""
        logger.info("=== Register_Key.md 파일 암호화 시작 ===")
        
        # 환경 변수 확인
        if not os.environ.get('TIDEWISE_SECRET_KEY'):
            logger.error("❌ TIDEWISE_SECRET_KEY 환경 변수가 설정되지 않았습니다.")
            logger.error("다음 명령어로 환경 변수를 설정해주세요:")
            logger.error("  Windows: set TIDEWISE_SECRET_KEY=your-super-secret-and-long-key-here")
            logger.error("  Linux/Mac: export TIDEWISE_SECRET_KEY='your-super-secret-and-long-key-here'")
            return {"success": False, "error": "환경 변수 미설정"}
        
        # 파일 찾기
        files_to_encrypt = self.find_register_key_files()
        if not files_to_encrypt:
            return {"success": False, "error": "암호화할 파일을 찾을 수 없습니다"}
        
        # 암호화 수행
        results = {
            "success": True,
            "total_files": len(files_to_encrypt),
            "encrypted_files": [],
            "failed_files": [],
            "skipped_files": []
        }
        
        for file_path in files_to_encrypt:
            logger.info(f"\n--- 파일 처리 중: {file_path} ---")
            
            if self.is_file_encrypted(file_path):
                results["skipped_files"].append(str(file_path))
                logger.info(f"⏭️  건너뜀 (이미 암호화됨): {file_path}")
                continue
            
            if self.encrypt_file(file_path):
                results["encrypted_files"].append(str(file_path))
                logger.info(f"✅ 암호화 성공: {file_path}")
            else:
                results["failed_files"].append(str(file_path))
                results["success"] = False
                logger.error(f"❌ 암호화 실패: {file_path}")
        
        # 결과 요약
        logger.info("\n=== 암호화 작업 완료 ===")
        logger.info(f"총 파일 수: {results['total_files']}")
        logger.info(f"암호화 성공: {len(results['encrypted_files'])}")
        logger.info(f"건너뜀 (이미 암호화됨): {len(results['skipped_files'])}")
        logger.info(f"실패: {len(results['failed_files'])}")
        
        if results["failed_files"]:
            logger.error("실패한 파일들:")
            for failed_file in results["failed_files"]:
                logger.error(f"  - {failed_file}")
        
        return results
    
    def verify_master_key(self) -> bool:
        """마스터 키 유효성 검증"""
        try:
            logger.info("마스터 키 유효성 검증 중...")
            handler = SecureKeyHandler()
            
            # 간단한 암호화/복호화 테스트로 마스터 키 검증
            test_data = "test_verification_string"
            encrypted = handler.encrypt(test_data)
            decrypted = handler.decrypt(encrypted)
            
            if decrypted == test_data:
                logger.info("✅ 마스터 키 검증 성공")
                logger.info("보안 설정 정보:")
                logger.info("  - 알고리즘: AES-256-GCM")
                logger.info("  - 키 유도: PBKDF2-SHA256")
                logger.info("  - 반복 횟수: 100,000")
                return True
            else:
                logger.error("❌ 마스터 키 검증 실패")
                return False
                
        except ValueError as e:
            if "마스터 키" in str(e) or "TIDEWISE_SECRET_KEY" in str(e):
                logger.error(f"❌ 마스터 키 오류: {e}")
            else:
                logger.error(f"❌ 값 오류: {e}")
            return False
        except Exception as e:
            logger.error(f"❌ 마스터 키 검증 중 오류: {e}")
            return False


def main():
    """메인 함수"""
    print("🔐 Register_Key.md 암호화 유틸리티")
    print("=" * 50)
    
    try:
        encryptor = RegisterKeyEncryptor()
        
        # 1. 마스터 키 검증
        if not encryptor.verify_master_key():
            print("\n❌ 마스터 키 검증에 실패했습니다.")
            print("TIDEWISE_SECRET_KEY 환경 변수를 확인해주세요.")
            return 1
        
        # 2. 사용자 확인
        print(f"\n📁 프로젝트 루트: {encryptor.project_root}")
        files_to_process = encryptor.find_register_key_files()
        
        if not files_to_process:
            print("\n❌ 암호화할 Register_Key.md 파일을 찾을 수 없습니다.")
            return 1
        
        print(f"\n📋 발견된 파일 ({len(files_to_process)}개):")
        for file_path in files_to_process:
            status = "암호화됨" if encryptor.is_file_encrypted(file_path) else "평문"
            print(f"  - {file_path} ({status})")
        
        # 사용자 확인
        response = input(f"\n계속 진행하시겠습니까? (y/N): ").strip().lower()
        if response not in ['y', 'yes']:
            print("작업이 취소되었습니다.")
            return 0
        
        # 3. 암호화 수행
        results = encryptor.encrypt_all_files()
        
        # 4. 결과 출력
        if results["success"]:
            print(f"\n✅ 암호화 작업이 성공적으로 완료되었습니다!")
            print(f"   암호화된 파일: {len(results['encrypted_files'])}개")
            if results["skipped_files"]:
                print(f"   건너뛴 파일: {len(results['skipped_files'])}개 (이미 암호화됨)")
        else:
            print(f"\n❌ 일부 파일 암호화에 실패했습니다.")
            print(f"   실패한 파일: {len(results['failed_files'])}개")
            return 1
        
        print(f"\n📝 로그 파일: utils/encrypt_register_key.log")
        print("\n⚠️  중요 안내:")
        print("   - 원본 파일은 .backup_YYYYMMDD_HHMMSS 형태로 백업되었습니다")
        print("   - 환경 변수 TIDEWISE_SECRET_KEY를 안전하게 보관하세요")
        print("   - 이제 애플리케이션을 재시작하면 암호화된 키를 사용합니다")
        
        return 0
        
    except KeyboardInterrupt:
        print("\n\n작업이 사용자에 의해 중단되었습니다.")
        return 1
    except Exception as e:
        logger.error(f"예상치 못한 오류: {e}")
        print(f"\n❌ 예상치 못한 오류가 발생했습니다: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
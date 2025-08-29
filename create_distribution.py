#!/usr/bin/env python3
"""
tideWise 배포용 압축파일 생성기
전체 폴더를 tideWise-Distribution.zip으로 압축
"""

import os
import zipfile
import time
from pathlib import Path

def create_distribution_zip():
    """tideWise 배포용 압축파일 생성"""
    print("=" * 60)
    print("=== tideWise 배포용 압축파일 생성 ===")
    print("=" * 60)
    
    # 기본 경로 설정
    source_dir = Path("C:/Distribute_tideWise")
    output_zip = source_dir / "tideWise-Distribution.zip"
    
    # 기존 압축파일 삭제
    if output_zip.exists():
        output_zip.unlink()
        print(f"기존 압축파일 삭제: {output_zip.name}")
    
    print(f"\n소스 폴더: {source_dir}")
    print(f"배포 압축파일: {output_zip}")
    print("\n압축 시작...")
    
    start_time = time.time()
    file_count = 0
    
    try:
        with zipfile.ZipFile(output_zip, 'w', zipfile.ZIP_DEFLATED) as zipf:
            # 모든 파일과 폴더를 재귀적으로 압축
            for root, dirs, files in os.walk(source_dir):
                # 출력 zip 파일 자체는 제외
                if output_zip.name in files:
                    files.remove(output_zip.name)
                
                for file in files:
                    file_path = Path(root) / file
                    # 상대 경로로 압축 (Distribute_tideWise/ 루트로 시작)
                    arcname = file_path.relative_to(source_dir.parent)
                    
                    zipf.write(file_path, arcname)
                    file_count += 1
                    
                    # 진행상황 표시 (100개 파일마다)
                    if file_count % 100 == 0:
                        print(f"  압축 중... {file_count}개 파일 처리됨")
        
        end_time = time.time()
        elapsed = end_time - start_time
        
        # 압축파일 크기 확인
        zip_size = output_zip.stat().st_size
        zip_size_mb = zip_size / (1024 * 1024)
        
        print("\n" + "=" * 60)
        print("=== 압축 완료! ===")
        print(f"압축된 파일 수: {file_count:,}개")
        print(f"압축파일 크기: {zip_size_mb:.2f} MB")
        print(f"소요 시간: {elapsed:.2f}초")
        print(f"생성된 파일: {output_zip}")
        
        # 주요 파일들이 포함되었는지 확인
        print(f"\n=== 주요 파일 포함 확인 ===")
        
        key_files = [
            "Distribute_tideWise/run.py",
            "Distribute_tideWise/Policy/Register_Key/Register_Key.md",
            "Distribute_tideWise/support/api_connector.py",
            "Distribute_tideWise/support/minimal_day_trader.py",
            "Distribute_tideWise/KIS_API_Test/fast_token_manager.py",
            "Distribute_tideWise/support/trading_config.json"
        ]
        
        with zipfile.ZipFile(output_zip, 'r') as zipf:
            zip_contents = zipf.namelist()
            
            for key_file in key_files:
                if key_file in zip_contents:
                    print(f"[OK] {key_file}")
                else:
                    print(f"[MISSING] {key_file}")
        
        print(f"\n배포용 압축파일이 성공적으로 생성되었습니다!")
        print(f"위치: {output_zip}")
        
        return True
        
    except Exception as e:
        print(f"\n[ERROR] 압축파일 생성 실패: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """메인 실행"""
    try:
        success = create_distribution_zip()
        
        if success:
            print("\n" + "=" * 60)
            print("[SUCCESS] tideWise 배포용 압축파일 생성 성공!")
            print("압축파일을 다른 컴퓨터에 복사하여 tideWise를 배포할 수 있습니다.")
            exit(0)
        else:
            print("\n" + "=" * 60)
            print("[FAIL] 압축파일 생성 실패!")
            exit(1)
            
    except KeyboardInterrupt:
        print("\n사용자에 의해 중단되었습니다.")
        exit(1)
    except Exception as e:
        print(f"실행 오류: {e}")
        exit(1)

if __name__ == "__main__":
    main()

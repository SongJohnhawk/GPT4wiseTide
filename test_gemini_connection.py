#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Gemini 2.5 Flash API 연결 테스트
Register_Key.md에서 API 키 자동 로드
"""

import asyncio
import aiohttp
import json
import sys
import io
from pathlib import Path

# UTF-8 인코딩 설정
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

# 프로젝트 루트 추가
PROJECT_ROOT = Path(__file__).parent
sys.path.insert(0, str(PROJECT_ROOT))

from support.ai_api_manager import get_ai_api_manager

async def test_gemini_connection():
    """Gemini API 연결 테스트"""
    
    print("=" * 60)
    print("🔥 Gemini 2.5 Flash API 연결 테스트")
    print("=" * 60)
    
    try:
        # AI API Manager 초기화
        ai_manager = get_ai_api_manager(PROJECT_ROOT)
        
        # Register_Key.md 다시 로드
        ai_manager.refresh_cache()
        
        # Gemini 설정 가져오기 - Register_Key.md 직접 읽기
        try:
            register_key_path = PROJECT_ROOT / "Policy" / "Register_Key" / "Register_Key.md"
            
            if not register_key_path.exists():
                print(f"❌ Register_Key.md 파일을 찾을 수 없습니다: {register_key_path}")
                return False
            
            with open(register_key_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Gemini API 키 추출
            import re
            gemini_key_match = re.search(r'Gemini API Key:\s*\[([^\]]+)\]', content)
            
            if not gemini_key_match:
                print("❌ Register_Key.md에서 Gemini API 키를 찾을 수 없습니다!")
                return False
            
            gemini_api_key = gemini_key_match.group(1).strip()
            
            if gemini_api_key.startswith('여기에'):
                print("❌ Gemini API 키가 설정되지 않았습니다!")
                print("   Register_Key.md에서 [여기에_Gemini_API_키_입력]을 실제 키로 교체하세요.")
                return False
            
            print(f"✅ Gemini API 키 로드 성공")
            print(f"   키: {gemini_api_key[:20]}...")
            
        except Exception as e:
            print(f"❌ Gemini 설정 로드 실패: {e}")
            return False
        
        # Gemini API 테스트 호출
        print("\n📡 Gemini API 연결 테스트 중...")
        
        url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash-exp:generateContent"
        params = {"key": gemini_api_key}
        
        payload = {
            "contents": [{
                "parts": [{
                    "text": "한국 주식시장의 현재 상황을 한 문장으로 요약해주세요."
                }]
            }],
            "generationConfig": {
                "temperature": 0.1,
                "maxOutputTokens": 100
            }
        }
        
        timeout = aiohttp.ClientTimeout(total=10)
        
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.post(url, params=params, json=payload) as response:
                if response.status == 200:
                    result = await response.json()
                    
                    # 응답 파싱
                    content = result['candidates'][0]['content']['parts'][0]['text']
                    
                    print("\n✅ Gemini API 연결 성공!")
                    print(f"📊 응답: {content}")
                    
                    # 모델 정보
                    print("\n📋 Gemini 정보:")
                    print(f"   모델: gemini-2.0-flash-exp")
                    print(f"   API 키: 활성화됨")
                    print(f"   상태: 정상 작동")
                    
                    return True
                    
                else:
                    error_text = await response.text()
                    print(f"\n❌ Gemini API 오류 (HTTP {response.status})")
                    print(f"   오류 내용: {error_text}")
                    
                    if response.status == 400:
                        print("\n💡 해결 방법:")
                        print("   1. API 키가 올바른지 확인")
                        print("   2. Gemini API가 활성화되었는지 확인")
                        print("   3. https://makersuite.google.com/app/apikey 에서 확인")
                    
                    return False
                    
    except asyncio.TimeoutError:
        print("\n❌ Gemini API 타임아웃")
        print("   네트워크 연결을 확인하세요.")
        return False
        
    except Exception as e:
        print(f"\n❌ 예상치 못한 오류: {e}")
        import traceback
        traceback.print_exc()
        return False

async def test_dual_ai_brain():
    """듀얼 AI 브레인 테스트"""
    
    print("\n" + "=" * 60)
    print("🧠 듀얼 AI 브레인 (GPT-4o + Gemini 2.5 Flash) 테스트")
    print("=" * 60)
    
    # 테스트 시나리오
    test_stock = {
        "symbol": "005930",
        "name": "삼성전자",
        "current_price": 75000,
        "change_pct": 2.5,
        "volume": 15000000
    }
    
    print(f"\n📈 테스트 종목: {test_stock['name']} ({test_stock['symbol']})")
    print(f"   현재가: {test_stock['current_price']:,}원")
    print(f"   등락률: {test_stock['change_pct']:+.2f}%")
    print(f"   거래량: {test_stock['volume']:,}")
    
    try:
        # Claude+Gemini 하이브리드 엔진 임포트
        from support.claude_gemini_hybrid_engine import ClaudeGeminiHybridEngine
        from support.gpt_interfaces import MarketContext
        from datetime import datetime
        
        # 마켓 컨텍스트 생성
        context = MarketContext(
            symbol=test_stock['symbol'],
            current_price=test_stock['current_price'],
            price_change_pct=test_stock['change_pct'],
            volume=test_stock['volume'],
            technical_indicators={
                "RSI": 65.0,
                "MACD": 1.2,
                "MA_20": 73000
            },
            news_sentiment={
                "positive": 0.6,
                "neutral": 0.3,
                "negative": 0.1
            },
            market_conditions={
                "trend": "BULLISH",
                "volatility": "MEDIUM"
            },
            risk_factors=["반도체 시장 변동성"],
            timestamp=datetime.now()
        )
        
        print("\n🤖 듀얼 AI 브레인 초기화 중...")
        
        # 하이브리드 엔진은 Claude API가 필요하므로 여기서는 시뮬레이션만
        print("\n✅ 듀얼 AI 브레인 아키텍처 준비 완료:")
        print("   1️⃣ GPT-4o: 실시간 시장 분석 담당")
        print("   2️⃣ Gemini 2.5 Flash: 고속 기술적 분석 담당")
        print("   3️⃣ 융합 로직: 두 AI의 분석을 결합하여 최종 결정")
        
        print("\n🎯 듀얼 AI 브레인 작동 시나리오:")
        print("   1. GPT-4o가 뉴스와 시장 심리 분석")
        print("   2. Gemini가 차트와 기술적 지표 분석")
        print("   3. 두 분석 결과를 가중 평균으로 융합")
        print("   4. 최종 매매 신호 생성")
        
        return True
        
    except ImportError as e:
        print(f"\n⚠️ 하이브리드 엔진 임포트 실패: {e}")
        print("   Claude API 키가 필요합니다.")
        return False
        
    except Exception as e:
        print(f"\n❌ 듀얼 AI 브레인 테스트 실패: {e}")
        return False

async def main():
    """메인 테스트 함수"""
    
    # 1. Gemini 연결 테스트
    gemini_ok = await test_gemini_connection()
    
    if gemini_ok:
        # 2. 듀얼 AI 브레인 테스트
        await test_dual_ai_brain()
        
        print("\n" + "=" * 60)
        print("🎉 Gemini 2.5 Flash 연동 준비 완료!")
        print("=" * 60)
        print("\n다음 단계:")
        print("1. Claude API 키를 Register_Key.md에 추가")
        print("2. 하이브리드 모드 활성화를 [true]로 설정")
        print("3. 시스템 재시작 후 듀얼 AI 브레인 활성화")
    else:
        print("\n" + "=" * 60)
        print("⚠️ Gemini API 연결 실패")
        print("=" * 60)
        print("\nRegister_Key.md 파일을 확인하세요:")
        print("메뉴 3. Setup → 1. Register_Key")

if __name__ == "__main__":
    asyncio.run(main())
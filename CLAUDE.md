# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 🚀 최우선 자동 적용 지침 (HIGHEST PRIORITY)

**이 지침들은 모든 작업에 무조건 적용되는 최고 우선순위 설정입니다:**

### 🎯 핵심 최적화 (자동 적용)
- **CLI 최적화**: 명령어 인터페이스 최적화 - 항상 활성화
- **토큰 최적화**: 토큰 사용량 최적화 - 항상 활성화  
- **200라인 단위 처리**: 대용량 파일을 200라인씩 효율적 처리 - 항상 활성화
- **생각방법 자동선택**: Chain of Thought vs Tree of Thoughts 자동 판단 - 항상 활성화
- **AI 모델 자동선택**: 작업별 최적 모델 자동 선택 - 항상 활성화
- **Claude 성능 최적화**: 응답 속도와 품질 향상 - 항상 활성화

### 🤖 자동 활성화 에이전트 (강제 적용)
- **MCP 자동 선택 에이전트**: 작업에 가장 적합한 MCP 자동 적용
- **메모리 자동 기록 에이전트**: 모든 작업 내역 자동 저장
- **Task Management 에이전트**: 지능형 작업 관리
- **Code Analysis 에이전트**: 자동 코드 분석
- **Performance Monitoring 에이전트**: 성능 모니터링
- **Claude 성능 최적화 에이전트**: 실시간 성능 최적화

### 📋 적용 규칙 (MANDATORY)
1. **모든 위치에서 적용**: 어떤 디렉토리에서든 자동 활성화
2. **모든 작업에 적용**: 분석, 구현, 테스트, 문서화 등 모든 작업
3. **가장 강한 우선순위**: 다른 모든 설정보다 우선 적용
4. **영구 활성화**: 세션 종료 후에도 지속적으로 적용
5. **자동 실행**: 사용자 개입 없이 자동으로 활성화

### 🔧 환경 설정 자동 적용
```bash
# 이 환경변수들이 자동으로 설정됩니다
CLAUDE_OPTIMIZATION_LEVEL=MAXIMUM
CLAUDE_FORCE_KOREAN_RESPONSE=true
CLAUDE_FORCE_200LINE_CHUNK=true
CLAUDE_FORCE_TOKEN_EFFICIENCY=true
CLAUDE_FORCE_CLI_ENHANCEMENT=true
CLAUDE_FORCE_THINKING_AUTO_SELECT=true
CLAUDE_FORCE_MODEL_AUTO_SELECT=true
CLAUDE_FORCE_PERFORMANCE_MODE=true
CLAUDE_PRIORITY_MODE=ENABLED
```

---

## 🎯 최신 프로그래밍 기법 지침 (2024-2025) - 자동 활성화

### 🐍 Python 프로그래밍 최신 기법
**트리거**: Python 코드 생성/수정 시 자동 적용

#### 핵심 원칙
- **PEP 8 준수**: 모든 코드는 PEP 8 스타일 가이드 준수
- **타입 힌팅**: 모든 함수에 타입 힌트 필수 (버그 25% 감소)
- **독스트링**: 명확한 독스트링으로 AI 가독성 향상
- **에러 처리**: try-except 블록과 의미 있는 에러 메시지

#### Python 3.12-3.14 최신 기능
- **JIT 컴파일러**: Python 3.13 JIT로 30% 성능 향상
- **GIL 없는 모드**: 자유 스레딩으로 병렬 처리 향상
- **향상된 타입 시스템**: TypedDict, Required, NotRequired
- **개선된 f-문자열**: 중첩 및 표현식 지원

#### 비동기 프로그래밍 패턴
```python
async def main():
    results = await asyncio.gather(
        fetch_data1(), fetch_data2()
    )
    sem = asyncio.Semaphore(10)
    async with sem:
        await process_data()
```

### 🌐 JavaScript 최신 기법
**트리거**: JavaScript/TypeScript 코드 생성/수정 시 자동 적용

#### ES2025+ 핵심 기능
- **이터레이터 헬퍼**: 함수형 프로그래밍 강화
- **명시적 리소스 관리**: using 선언으로 리소스 누수 방지
- **Promise.try()**: 비동기 에러 처리 개선
- **Set 메서드**: 교집합, 합집합, 차집합 네이티브 지원

#### React 19 & Next.js 15
- **서버 컴포넌트**: 클라이언트 JS 감소, SEO 향상
- **Actions**: 데이터 변이 단순화
- **use() API**: Promise/Context 유연한 처리

### 🎨 CSS 최신 기법
**트리거**: CSS/SCSS 코드 생성/수정 시 자동 적용

#### 반응형 디자인
- **컨테이너 쿼리**: 부모 크기 기반 반응형
- **뷰포트 단위**: vw, vh, vmin, vmax 활용
- **CSS Grid & Flexbox**: 유동적 레이아웃

### 📈 PineScript 지침
**트리거**: PineScript 코드 생성/수정 시 자동 적용

#### 핵심 원칙
- **v5 문법**: 최신 기능 활용
- **리페인팅 방지**: lookahead=barmerge.lookahead_off
- **리스크 관리**: ATR 기반 스탑로스/테이크프로핏

### 🧪 테스트 코드 최신 기법
**트리거**: 테스트 코드 작성/디버깅 시 자동 적용

#### AI 기반 테스트
- **다양한 케이스**: 경계값, 엣지 케이스, 일반 플로우
- **높은 커버리지**: 구문, 분기, 경로 커버리지
- **자동 버그 수정**: 패턴 기반 자동 수정

### 🔒 웹 보안 코딩
**트리거**: 웹 애플리케이션 개발 시 자동 적용

#### 보안 원칙
- **입력 검증**: 모든 사용자 입력 검증
- **출력 인코딩**: XSS 방지 HTML 엔티티 변환
- **HTTPS 강제**: 모든 통신 암호화
- **최소 권한**: 필요한 최소 권한만 부여

---

## Project Overview

tideWise is an automated trading system for Korean stocks using the Korea Investment & Securities (KIS) OpenAPI. The system supports both real and mock trading with dynamic algorithm loading and risk management.

## Key Commands

### GitHub 푸시를 위해 다음의 정보를 사용
```
# Git Hub의 Personal Access Token:
[GITHUB_TOKEN]

# Git Hub의 Username:
SongJohnhawk

#GitHub 주소:
https://github.com/SongJohnhawk/tideWise
https://github.com/SongJohnhawk/GPT4wiseTide

#Git Hub의 Repository 이름:
tideWise

# Primary instruction:
“Before pushing to the remote, increase the HTTP buffer size and push in smaller chunks. If a push fails, create a new commit that contains only a small subset of changes and push that.”

# More explicit, step‑wise version:
“Before pushing, increase the HTTP POST buffer size. Then push changes in small batches. If any push fails, create a new commit with only a minimal subset of changes and push that commit.”

# With actionable hints for Git:
“Increase the HTTP buffer size, then push in smaller batches. On error, split the changes, create a new commit with only a small subset, and push that commit first.”
```
### GitHub 관리 자동화 지침
```
# If the .git directory does not exist, initialize a Git repository (git init).
# When creating or modifying files, run git add and git commit after the changes.
# When deleting files, run git rm followed by git commit.
```

### Testing & Validation
```bash
# All test files are located in the tests/ directory
cd tests

# Test individual components
python test_account_manager.py
python test_integration.py
python test_minimal_day_trader.py
python test_stock_collection.py
python test_surge_integration.py
python test_main_program.py
python test_real_data_collection.py

# Run all trading system tests
python test_all_trading_systems.py

# Or run from project root
python tests/test_all_trading_systems.py
```

**Important**: All new test files must be created in the `tests/` directory with proper import path setup:
```python
# Standard test file header for tests directory
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
```

### 백테스팅 시스템
```bash
# 백테스팅 시스템 실행
python backtesting/start_Backtest.py

# 백테스팅용 데이터 수집
python backtesting/enhanced_data_collector.py

# 모든 알고리즘 백테스팅 (필수: Algorithm 폴더의 모든 알고리즘)
python backtest_all_algorithms.py
```

### Utility Commands
```bash
# Toggle trading modes
python toggle_trading.py

# Clean up temporary files
python support/universal_temp_cleaner.py

# Token optimization
python token_optimizer.py

# Remove sensitive data (for distribution)
python remove_sensitive_data.py
```

## Architecture Overview

### Core System Components

**Main Entry Points:**
- `run.py` - Primary system launcher with production trading capabilities
- `run_debug.py` - Debug mode with testing and validation menus
- `auto_setup.py` - Automated system setup and dependency installation

**Trading Engine Architecture:**
- `support/production_auto_trader.py` - Main production trading engine
- `support/simple_auto_trader.py` - Legacy trading implementation
- `support/minimal_auto_trader.py` - Lightweight trading system
- `support/minimal_day_trader.py` - Day trading specific engine

**Algorithm System:**
- `support/algorithm_loader.py` - Dynamic algorithm loading and validation
- `support/algorithm_selector.py` - Algorithm selection and management
- `support/universal_algorithm_interface.py` - Standardized algorithm interface
- `Algorithm/` - Directory containing trading algorithms (.py, .pine, .js, .txt, .json)

**API & Data Management:**
- `support/api_connector.py` - KIS OpenAPI integration
- `support/api_key_manager.py` - API key management and security
- `stock_data_collector.py` - Real-time stock data collection
- `support/trading_stock_collector.py` - Trading-specific data collection

**Risk & Position Management:**
- `support/trading_rules.py` - Risk management and trading rules
- `support/previous_day_balance_handler.py` - Previous day position handling
- `support/balance_cleanup_manager.py` - Balance cleanup operations
- `support/holding_stock_manager.py` - Position management

### Supporting Systems

**Market Analysis:**
- `support/surge_stock_buyer.py` - Surge stock detection and trading
- `support/surge_stock_providers.py` - Surge stock data providers
- `support/advanced_surge_analyzer.py` - Advanced surge analysis
- `support/market_regime_detector.py` - Market condition detection
- `support/advanced_indicators.py` - Technical analysis indicators

**System Management:**
- `support/system_manager.py` - System lifecycle management
- `support/system_logger.py` - Centralized logging system
- `support/menu_manager.py` - Interactive menu system
- `support/setup_manager.py` - System configuration management
- `support/unified_cycle_manager.py` - Trading cycle coordination

**External Integrations:**
- `support/telegram_notifier.py` - Telegram notification system
- `support/enhanced_theme_stocks.py` - Theme stock management
- `support/user_designated_stocks.py` - User-defined stock lists

## 설정 파일 구조

### 핵심 설정
- `Policy/Trading_Rule.md` - 매매 규칙 및 리스크 관리 설정
- `Policy/Register_Key/Register_Key.md` - API 키 및 텔레그램 설정 (필수)
- `support/trading_rules.json` - JSON 형태 매매 설정
- `support/trading_config.json` - 시스템 전체 설정

### 알고리즘 및 사용자 설정
- `support/selected_algorithm.json` - 현재 선택된 알고리즘
- `support/user_theme_config.json` - 사용자 테마 설정
- `support/menual_StokBuyList.md` - 수동 매수 종목 리스트

### 시장 및 시간 관리
- `support/market_time_config.json` - 시장 시간 설정
- `support/claude_performance_config.json` - 성능 최적화 설정

## Key Trading Rules & Settings

### Position & Risk Management
- **Position Size**: 7% of available funds per position (`POSITION_SIZE_BUDGET_RATIO = "0.07"`)
- **Maximum Positions**: 5 concurrent positions (`MAX_POSITIONS = "5"`)
- **Daily Loss Limit**: 5% (`DAILY_LOSS_LIMIT = "0.05"`)
- **Profit Target**: 7% automatic profit taking (`PROFIT_TARGET = "0.07"`)
- **Stop Loss**: 3% (`STOP_LOSS = "0.03"`)

### Market Hours & Timing
- **Market Open**: 09:05 KST
- **Market Close**: 15:30 KST
- **Auto Stop**: 15:20 KST
- **Pre-market Liquidation**: 09:05-09:06 KST
- **Trading Intervals**: 3 minutes (180 seconds)

### Price-Based Quantity Rules
- **Low Price Stocks** (≤30,000 KRW): Minimum 10 shares
- **High Price Stocks** (≥200,000 KRW): Maximum 5 shares  
- **Ultra High Price** (≥300,000 KRW): Maximum 2 shares (small accounts)

## Algorithm Development

### Algorithm Interface Requirements
All algorithms must implement:
```python
def analyze(data) -> dict:
    """Analyze stock data and return trading signal"""
    
def get_name() -> str:
    """Return algorithm name"""
    
def get_version() -> str:
    """Return algorithm version"""
    
def get_description() -> str:
    """Return algorithm description"""
```

### Algorithm Types Supported
- **Python (.py)**: Primary algorithm format
- **Pine Script (.pine)**: TradingView script format
- **JavaScript (.js)**: Node.js compatible algorithms
- **Text/JSON (.txt, .json)**: Configuration-based algorithms

### Testing Algorithms
Use the debug menu (`python run_debug.py`) option 4 to test algorithm loading before production use.

## Backtesting System

### Backtesting Rules (BACKTEST_RULE.md)
- **Mandatory**: All algorithms in Algorithm/ folder must be backtested
- **Initial Capital**: 10,000,000 KRW
- **Test Period**: 1 year (252 trading days)
- **Position Size**: 95% of available capital per position

### Performance Metrics
- **Total Return (%)**: (Final Capital - Initial Capital) / Initial Capital × 100
- **Win Rate (%)**: Profitable Trades / Total Trades × 100
- **Sharpe Ratio**: Risk-adjusted return metric
- **Maximum Drawdown (%)**: Largest peak-to-trough decline

### Backtesting Output
Results saved to `backtest_results/`:
- `[algorithm]_[timestamp].json` - Structured data
- `[algorithm]_[timestamp].html` - Visual report
- `summary_[timestamp].json/html` - Comparative analysis

## Development Workflow

### System Startup Sequence
1. System requirements check
2. Algorithm selector initialization  
3. Stock data pre-collection
4. User-designated stocks loading
5. Trading engine initialization
6. Market time monitoring

### Testing & Validation
1. **Component Tests**: Individual module testing (in `tests/` directory)
2. **Integration Tests**: Full system testing (in `tests/` directory)
3. **API Connection Tests**: KIS OpenAPI connectivity
4. **Algorithm Tests**: Algorithm loading and validation
5. **Data Collection Tests**: Real-time data pipeline

**Test File Organization**:
- All test files must be placed in the `tests/` directory
- Test files should start with `test_` prefix
- Use `PROJECT_ROOT = Path(__file__).parent.parent` for proper imports
- Run tests from either the `tests/` directory or project root

### Error Handling & Recovery
- **Graceful Degradation**: System continues with cached data on API failures
- **Automatic Retry**: 3 attempts for failed operations
- **Telegram Alerts**: Real-time error notifications
- **Comprehensive Logging**: All operations logged to `logs/` directory

## Dependencies

### Core Requirements (requirements.txt)
- **HTTP Clients**: aiohttp, requests
- **Data Processing**: pandas, numpy, numba
- **Async Processing**: asyncio support
- **Web Scraping**: beautifulsoup4, lxml
- **Security**: cryptography
- **System Monitoring**: psutil
- **UI Enhancement**: colorama, tqdm

### Python Version
- **Minimum**: Python 3.8+
- **Recommended**: Python 3.10+

## Security Considerations

### API Key Management
- API keys stored in `Policy/API_key.json` (excluded from repository)
- Separate keys for real and mock trading
- Key validation on startup

### Data Protection
- `remove_sensitive_data.py` script for safe distribution
- No hardcoded credentials in source code
- Encrypted communication with KIS OpenAPI

## Performance Optimization

### Token Optimization
- `token_optimizer.py` for efficient API usage
- `claude_performance_config.json` for AI optimization settings
- Memory management for large datasets

### Caching Strategy
- `stock_data_cache.json` for persistent data storage
- In-memory caching for frequently accessed data
- Automatic cache invalidation

## Troubleshooting

### Common Issues
1. **API Connection Failures**: Check `Policy/API_key.json` configuration
2. **Algorithm Loading Errors**: Verify algorithm interface implementation
3. **Market Time Errors**: Ensure system time synchronization
4. **Memory Issues**: Use cleanup utilities in `support/` directory

### Debug Resources
- **Debug Mode**: `python run_debug.py` for comprehensive testing
- **Log Analysis**: Check `logs/` directory for detailed execution logs
- **System Validation**: Menu option 6 in debug mode for full system diagnosis

### Support Tools
- `help/` directory contains user guides and troubleshooting documentation
- `Policy/` directory contains configuration templates and examples

## Claude CLI Speed Optimization Guidelines

### Core Speed Enhancement Techniques

1. Context File Optimization
    - Keep CLAUDE.md in project root with only core terms, coding style, and design
summary
    - Remove repetitive descriptions for faster response times
    - Remove repetitive descriptions for faster response times
2.
Aggressive Use of /compact Command
   claude-code /compact --level 2 --remove-comments
- Compress context data and remove unnecessary parts (comments, whitespace,
duplications)
- Adjust compression levels (1-3) based on situation
- Use --analyze --show-savings to check reduction metrics
- Achieves average 30-43% token usage reduction

3. Selective Context Inclusion
    - Include only relevant files/functions, not entire project
    - Use options like --files, --lines 10-30 to limit scope
    - Exclude unnecessary tests, docs via .clauderc auto-exclusion
    - Extract only essential text from attachments/images
    - Extract only essential text from attachments/images
4.
Large Folder and File Exclusion
    - Add node_modules, dist, .git to .clauderc exclude rules
    - Significantly improves initial indexing/loading speed
5.
Context Clearing Strategy
    - Don't accumulate too many tasks in one session
    - Use /clear periodically to reset conversation history
    - Start new sessions when context accumulation becomes excessive
6.
Prompt Optimization
    - Make questions and commands clear and concise, not overly verbose
    - Example: "Refactor this code for readability, performance, and memory"
    - → "optimize: performance, memory, readability"
7.
MCP Server Integration
    - Connect with Serena, Breeze MCP servers for semantic search
    - Only pass essential files to Claude through context optimization
    - Improves perceived response speed and token costs by 3-5x
8.
Breeze MCP Configuration
    - LanceDB vector indexing with Async I/O structure for fast file search
9.
Sub-agent Parallel Processing
    - Split tasks into steps for multiple Sub-agents to handle testing, refactoring
in parallel
    - Reduces total processing time by up to 10x
10.
SPARC Automation
    - Automate entire Specification → Pseudocode → Architecture → Refinement →
Completion workflow
    - Reduces intermediate wait times

11. Model Routing Strategy
    - Haiku for short summaries/log analysis
    - Sonnet for complex code understanding
    - Opus for long-term reasoning
    - Optimize speed and cost through routing

12. Environment Variables and Index Range Limiting
    - Set CLAUDE_CONTEXT_PATHS=/src:/tests to specify core paths only
    - Reduces indexing time

13. Prompt Caching Utilization
    - Use AWS Bedrock Prompt Cache to drastically reduce token costs and latency for
repeated analysis

14. Network Latency Minimization
    - Use closer cloud regions or local proxy to minimize response delays

15. Persistent Session Maintenance
    - Run claude daemon to skip session authentication and initial context exchange
    - Reduces response time by 1-2 seconds

16. LangChain + Bedrock Optimization Example
    - Response time improved from 95-120 seconds to 3-10 seconds (10-30x performance
boost)

17. Community Experience Sharing
    - Specific task division, clear rule setting, memory tags significantly improve
development speed

18. 43% Context Token Reduction Implementation
    - Use /compact command to compress and remove unnecessary parts from messages
    - Selectively include only essential files, functions, code portions in context
    - Exclude unnecessary tests, docs, images; deliver only text
    - Use /clear periodically to reset sessions and suppress accumulated tokens
    - Keep prompts (questions, commands) concise to prevent token waste
    - Prevent context overload with context-window, include-patterns option limits
    - Use additional system prompts and features (analysis, etc.) only when needed

## Advanced File Processing and Token Optimization Policies

### 200-Line Chunk Reading Strategy [MANDATORY]
Purpose: Optimal file processing for large codebases with minimal token usage
Method: 200-line sequential reading with analysis between chunks
Implementation:
  - Read file in 200-line segments using offset/limit parameters
  - Analyze each chunk completely before proceeding to next
  - Maintain context continuity between chunks
  - Skip irrelevant sections based on analysis
  - Summarize findings after each chunk processing
#### File Processing Workflow
def process_large_file(file_path: str, target_analysis: str):
    """
    Process large files in 200-line chunks for token efficiency
    """
    chunk_size = 200
    offset = 0
    analysis_results = []

    while True:
        # Read 200-line chunk
        chunk_content = read_file_chunk(file_path, offset, chunk_size)
        if not chunk_content:
            break

        # Analyze chunk for relevance
        if is_relevant_to_analysis(chunk_content, target_analysis):
            # Process and extract key information
            chunk_analysis = analyze_chunk(chunk_content, offset)
            analysis_results.append(chunk_analysis)
        else:
            # Skip irrelevant chunks to save tokens
            analysis_results.append(f"Lines {offset}-{offset+chunk_size}: Skipped (not
relevant)")

        offset += chunk_size

    return consolidate_analysis_results(analysis_results)
### Token Minimization Strategies [CORE POLICY]
Principle: Minimize token usage while maximizing information value
Strategies:
  1. Content-Based Filtering:
     - Skip comments unless specifically needed for analysis
     - Ignore test files unless testing-related task
     - Filter out generated code, build artifacts
     - Focus on core business logic and architecture

  2. Summarization Techniques:
     - Extract function signatures instead of full implementations
     - Summarize class structures without method bodies
     - Create condensed architectural overviews
     - Use bullet points instead of verbose descriptions

  3. Progressive Analysis:
     - Start with high-level structure analysis
     - Drill down only into relevant sections
     - Stop analysis early if target information found
     - Use binary search approach for specific content

  4. Context Preservation:
     - Maintain essential context between chunks
     - Preserve critical dependencies and relationships
     - Keep track of important patterns and structures
     - Document key findings for reference
### Smart File Reading Rules [IMPLEMENTATION]
Pre-Analysis Phase:
  - Check file extensions and skip binary/irrelevant files
  - Scan first 50 lines for file type and structure identification
  - Estimate file relevance score before full processing
  - Skip files with relevance score < 0.3

During-Analysis Phase:
  - Monitor token usage per chunk
  - Adjust chunk size based on content density
  - Apply compression techniques for verbose content
  - Use abbreviated notation for repetitive patterns

Post-Analysis Phase:
  - Consolidate findings into concise summary
  - Remove redundant information
  - Create actionable insights list
  - Estimate total token savings achieved
### Automated Token Budget Management [ADVANCED]
Budget-Allocation:
  - 30% for file reading and initial analysis
  - 40% for core processing and problem solving
  - 20% for response generation and formatting
  - 10% buffer for unexpected complexity

Budget-Monitoring:
  - Track token usage per operation
  - Alert when approaching budget limits
  - Automatically switch to summary mode if needed
  - Prioritize most important tasks within budget

Optimization-Triggers:
  - If usage > 70% of budget: Enable aggressive compression
  - If usage > 85% of budget: Switch to essential-only mode
  - If usage > 95% of budget: Emergency summary mode
### File Type Specific Processing [EFFICIENCY]
Python-Files:
  - Extract class definitions, method signatures
  - Identify imports and dependencies
  - Skip docstrings unless documentation task
  - Focus on business logic over boilerplate

JavaScript/TypeScript-Files:
  - Extract component structures
  - Identify API endpoints and data flow
  - Skip node_modules and build files
  - Focus on core application logic

Configuration-Files:
  - Extract key settings and parameters
  - Identify environment-specific configurations
  - Skip default/example configurations
  - Focus on custom and critical settings

Documentation-Files:
  - Extract headings and key concepts
  - Identify main topics and structures
  - Skip detailed examples unless needed
  - Focus on architectural decisions and patterns
## Advanced Workflow Engineering [CORE METHODOLOGY]

### 3-Stage Thinking Process [MANDATORY]
Stage-1: Problem Analysis & Research
  - Always request thorough problem analysis first
  - Research existing patterns and solutions
  - Identify potential challenges and constraints
  - Document all requirements and edge cases

Stage-2: Concrete Planning
  - Create detailed step-by-step implementation plan
  - Define clear success criteria and validation points
  - Establish rollback procedures for each step
  - Map dependencies and potential conflicts

Stage-3: Execution & Iterative Improvement
  - Implement according to plan with validation checkpoints
  - Test each component before proceeding to next
  - Apply continuous feedback and improvement
  - Document lessons learned for future reference

Performance: 40-60% increase in first-attempt success rate
### Think of Thought vs Tree of Thoughts Application [COGNITIVE STRATEGY]
Think-of-Thought-Applications:
  - General procedural tasks and workflow creation
  - Step-by-step process planning and documentation
  - Sequential task execution and method design
  - Standard development workflows and procedures
  - Code review and maintenance tasks

Tree-of-Thoughts-Applications:
  - Complex algorithmic problems requiring multiple solution paths
  - System architecture decisions with multiple trade-offs
  - Bug fixing that affects multiple interconnected components
  - Performance optimization requiring comprehensive analysis
  - Integration tasks that impact existing functionality
  - Critical system modifications with high risk factors

Decision-Criteria:
  - Task-Complexity > 0.6: Automatically trigger Tree of Thoughts
  - Multi-component impact: Use Tree of Thoughts approach
  - Single-path solutions: Use Think of Thought approach
  - Risk-level = Critical: Mandatory Tree of Thoughts analysis
### Parallel Processing Strategies [ADVANCED]
Git-Worktrees-Strategy:
  - Create separate worktrees for independent features
  - Run multiple Claude sessions on different features
  - Command: git worktree add ../project-feature-a feature-a
  - Benefit: Eliminate context switching overhead

Multi-Session-Coordination:
  - Session-1: Core functionality development
  - Session-2: Testing and validation
  - Session-3: Documentation and deployment
  - Session-4: Performance monitoring and optimization

Parallel-Development-Rules:
  - Ensure feature independence before parallel work
  - Use shared documentation for coordination
  - Regular synchronization checkpoints
  - Merge conflict resolution protocols
### Context Management Optimization [EFFICIENCY]
Claude-MD-Strategy:
  - Document personal coding guidelines in project CLAUDE.md
  - Specify recurring mistake prevention rules
  - Store project-specific conventions and patterns
  - Include performance benchmarks and targets

Session-Management-Rules:
  - Use /clear command frequently to prevent token waste
  - Initialize context at start of each new task
  - Separate complex tasks into individual sessions
  - Archive completed work summaries for reference

Context-Preservation-Techniques:
  - Save key decisions and rationale in project files
  - Maintain architectural decision records (ADRs)
  - Document API contracts and interfaces
  - Keep dependency maps and system diagrams updated
### Command Optimization [PRODUCTIVITY]
Custom-Slash-Commands:
  - /pr: Automated pull request generation with templates
  - /lint: Code linting and automatic fixes
  - /test: Test execution and result validation
  - /deploy: Deployment pipeline execution
  - /perf: Performance analysis and optimization
  - /security: Security scan and vulnerability assessment

Headless-Mode-Integration:
  - Command: claude -p for programmatic integration
  - Batch processing for multiple files
  - Automated workflow execution
  - CI/CD pipeline integration

Permission-Optimization:
  - Use --dangerously-skip-permissions for trusted environments
  - Configure persistent permissions for development workflows
  - Automate repetitive permission grants
  - Balance security with productivity
### Test-Driven Development Acceleration [TDD]
TDD-Workflow-Optimization:
  1. Request expected input/output based test creation
  2. Verify test failures confirm requirements
  3. Implement minimal code to pass tests
  4. Refactor and optimize while maintaining tests
  5. Repeat cycle with next feature

Claude-TDD-Benefits:
  - Rapid test case generation from specifications
  - Automatic mock creation for dependencies
  - Edge case identification and test coverage
  - Refactoring safety through comprehensive test suites

TDD-Performance-Metrics:
  - 60% faster development cycles
  - 80% reduction in post-deployment bugs
  - 50% improvement in code maintainability
  - 40% faster onboarding for new team members
### Performance Monitoring Integration [METRICS]
Data-Driven-Optimization:
  - Bundle size analysis and optimization targets
  - Database query performance bottleneck identification
  - API response time measurement and improvement
  - Memory usage profiling and optimization

Before-After-Comparison:
  - Establish baseline metrics before changes
  - Define improvement targets and thresholds
  - Measure actual improvements post-implementation
  - Document performance gains and lessons learned

Automated-Performance-Testing:
  - Integration with CI/CD for performance regression detection
  - Automated alerts for performance threshold violations
  - Regular performance benchmarking and reporting
  - Performance budget enforcement in development workflow
### File Processing Efficiency [ADVANCED]
Large-File-Handling:
  - Shift + Drag for quick file references
  - Control + V for image and content pasting
  - Timeout settings adjustment for large file operations
  - Chunked processing for files > 10,000 lines

Multi-File-Operations:
  - Batch file processing commands
  - Directory-wide search and replace
  - Simultaneous multi-file editing
  - Cross-file dependency analysis and updates
## Intelligent Task Routing and Execution Framework [CORE SYSTEM]

### Automated Task Complexity Classification and Workflow Routing [MANDATORY]
FUNCTION handle_coding_request(request, codebase):
    // 1. 작업 복잡도 분석 및 라우팅
    task_type = classify_task_complexity(request, codebase)

    IF task_type == "SIMPLE_GENERATION":
        // 1A. 단순 작업: CoT 워크플로우 실행
        result = execute_cot_workflow(request)
    ELSE: // task_type == "COMPLEX_MODIFICATION"
        // 1B. 복합 작업: ToT 워크플로우 실행
        result = execute_tot_workflow(request, codebase)
    END IF

    RETURN result
### Task Complexity Classification Function [INTELLIGENT ROUTING]
FUNCTION classify_task_complexity(request, codebase):
    // LLM을 라우터로 활용하여 지능적으로 분류
    prompt = f"""
        당신은 전문가 AI 라우터입니다.
        사용자 요청: "{request}"
        코드베이스 상태: {summarize_codebase(codebase)}

        이 작업은 '단순 코드 생성(SIMPLE_GENERATION)'에 가깝습니까,
        아니면 '복합 코드 수정(COMPLEX_MODIFICATION)'에 가깝습니까?
        판단 근거와 함께 둘 중 하나의 타입으로만 답변하세요.
    """
    // LLM 호출하여 "SIMPLE_GENERATION" 또는 "COMPLEX_MODIFICATION" 반환
    RETURN get_llm_response(prompt)
### Chain of Thought Workflow for Simple Tasks [COT IMPLEMENTATION]
FUNCTION execute_cot_workflow(request):
    // Step 1: 구조화된 의사코드(SCoT) 생성
    scot_prompt = f"'{request}'를 해결하기 위한 단계별 의사코드를 작성해줘."
    structured_plan = get_llm_response(scot_prompt)

    // Step 2: 의사코드를 기반으로 코드 생성
    code_gen_prompt = f"다음 계획에 따라 코드를 작성해줘:\n{structured_plan}"
    generated_code = get_llm_response(code_gen_prompt)

    // Step 3: 기본적인 자체 검증
    review_prompt = f"다음 코드에 명백한 오류나 문제가 있는지 검토해줘:
\n{generated_code}"
    review_result = get_llm_response(review_prompt)

    IF review_result contains "문제 없음":
        RETURN generated_code
    ELSE:
        // 발견된 문제를 바탕으로 코드 수정 (1-pass correction)
        RETURN fix_code(generated_code, review_result)
    END IF
### Tree of Thoughts Workflow for Complex Tasks [TOT IMPLEMENTATION]
FUNCTION execute_tot_workflow(request, codebase):
    // Step 1: 사전 분석 (Pre-Analysis)
    analysis_report = perform_pre_analysis(codebase, request.target_area)
    // report 내용: 의존성 그래프, 영향받는 파일 목록, 관련 테스트 케이스 등

    // Step 2: 다양한 해결책 후보 생성 (Thought Generation)
    generation_prompt = f"""
        요청: '{request}'
        사전 분석 보고서: {analysis_report}

        이 문제를 해결하기 위한 3가지 서로 다른 접근 방식의 코드 수정안을 제안해줘.
        보고서에 언급된 잠재적 부작용을 반드시 고려해야 해.
    """
    candidate_solutions = get_llm_response(generation_prompt, n=3) // 3개의 후보 생성

    // Step 3: 각 해결책 후보 평가 (Thought Evaluation)
    evaluated_solutions = []
    FOR each solution IN candidate_solutions:
        score, feedback = evaluate_solution(solution, codebase, analysis_report)
        evaluated_solutions.append({solution: solution, score: score, feedback:
feedback})
    END FOR

    // Step 4: 최적의 해결책 선택 및 적용 (Search & Selection)
    best_solution = find_best(evaluated_solutions)

    IF best_solution.score > THRESHOLD:
        RETURN best_solution.solution
    ELSE:
        RETURN "안전한 해결책을 찾지 못했습니다. 피드백: " + best_solution.feedback
    END IF
### ToT Workflow Support Functions [ADVANCED ANALYSIS]
FUNCTION perform_pre_analysis(codebase, target_area):
    // 외부 정적 분석 도구(예: pyan, ast) 실행
    dependency_graph = run_static_analyzer(codebase)
    // 분석 결과를 LLM이 이해하기 쉬운 자연어로 요약
    RETURN format_analysis_for_llm(dependency_graph, target_area)

FUNCTION evaluate_solution(solution, codebase, analysis_report):
    // 평가 기준: 테스트 통과 여부, 새로운 정적 분석 오류, LLM 자체 평가
    temp_codebase = apply_patch(codebase, solution)
    test_results = run_tests(temp_codebase, analysis_report.related_tests)
    static_analysis_results = run_static_analyzer(temp_codebase)

    self_critique_prompt = f"""
        수정안: {solution}
        테스트 결과: {test_results}
        정적 분석 결과: {static_analysis_results}

        이 수정안의 종합 점수(0-100)와 그 이유를 다음 항목에 근거하여 평가해줘:
        1. 문제 해결 정확성 2. 잠재적 부작용(안전성) 3. 코드 품질 및 가독성
    """
    evaluation = get_llm_response(self_critique_prompt)
    RETURN evaluation.score, evaluation.feedback
### Implementation Guidelines for AI Agents [EXECUTION RULES]
Simple-Generation-Triggers:
  - New function or class creation from scratch
  - Straightforward API implementations
  - Basic CRUD operations
  - Simple data transformations
  - Isolated utility functions

Complex-Modification-Triggers:
  - Refactoring existing large codebases
  - Multi-file architectural changes
  - Performance optimization across systems
  - Integration with external dependencies
  - Bug fixes affecting multiple components

Safety-Thresholds:
  - Minimum evaluation score: 75/100
  - Required test pass rate: 95%
  - Maximum static analysis warnings: 2
  - Mandatory human review for scores < 85

Execution-Monitoring:
  - Track task routing accuracy over time
  - Monitor CoT vs ToT success rates
  - Adjust complexity thresholds based on outcomes
  - Document edge cases for classification improvement
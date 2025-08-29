# tideWise AI Agent Development Guidelines

## 🚀 SuperClaude Framework Integration (자동 활성화)

### 🎯 최우선 자동 적용 지침 (HIGHEST PRIORITY)

**이 지침들은 모든 작업에 무조건 적용되는 최고 우선순위 설정입니다:**

#### 🤖 자동 활성화 에이전트 (강제 적용)
- **MCP 자동 선택 에이전트**: 작업에 가장 적합한 MCP 자동 적용
- **메모리 자동 기록 에이전트**: 모든 작업 내역 자동 저장
- **Task Management 에이전트**: 지능형 작업 관리
- **Code Analysis 에이전트**: 자동 코드 분석
- **Performance Monitoring 에이전트**: 성능 모니터링
- **Claude 성능 최적화 에이전트**: 실시간 성능 최적화

#### 🔌 강제 활성화 MCP 서버 (항상 작동)
- **shrimp-task-manager** ✅ 지능형 작업 관리 - 항상 활성화
- **code-analysis** 🔄 코드 품질 분석 - 강제 활성화 시도
- **langfuse** 🔄 성능 메트릭 추적 - 강제 활성화 시도
- **windows-mcp** 🔄 Windows 시스템 제어 - 강제 활성화 시도

#### 🎭 강제 활성화 Persona Agents (항상 작동)
- **architect** 🏗️ 시스템 아키텍처 전문 - 모든 구조적 작업에 자동 활성화
- **analyzer** 🔍 근본원인 분석 전문 - 모든 분석 작업에 자동 활성화
- **frontend** 🎨 UI/UX 전문 - 모든 프론트엔드 작업에 자동 활성화
- **backend** ⚙️ 서버사이드 전문 - 모든 백엔드 작업에 자동 활성화
- **security** 🛡️ 보안 전문 - 모든 보안 관련 작업에 자동 활성화
- **performance** ⚡ 성능 최적화 전문 - 모든 성능 작업에 자동 활성화
- **qa** ✅ 품질보증 전문 - 모든 테스팅 작업에 자동 활성화
- **refactorer** 🔧 코드품질 전문 - 모든 리팩토링 작업에 자동 활성화
- **devops** 🚀 인프라 전문 - 모든 배포 작업에 자동 활성화
- **mentor** 👨‍🏫 교육 전문 - 모든 설명 작업에 자동 활성화
- **scribe** 📝 문서화 전문 - 모든 문서 작업에 자동 활성화

#### 🔔 Agent 활성화 상태 표시 규칙 (MANDATORY)
**모든 응답 시작 시 반드시 표시:**
```
🤖 **[AGENT ACTIVATED]** [활성화된_에이전트_목록] → [작업_유형] 수행 중
```

**예시:**
- `🤖 **[AGENT ACTIVATED]** analyzer, security → 보안 취약점 분석 수행 중`
- `🤖 **[AGENT ACTIVATED]** frontend, performance → UI 성능 최적화 수행 중`  
- `🤖 **[AGENT ACTIVATED]** architect, backend → API 아키텍처 설계 수행 중`

#### 🎯 핵심 최적화 (자동 적용)
- **CLI 최적화**: 명령어 인터페이스 최적화 - 항상 활성화
- **토큰 최적화**: 토큰 사용량 최적화 - 항상 활성화  
- **200라인 단위 처리**: 대용량 파일을 200라인씩 효율적 처리 - 항상 활성화
- **생각방법 자동선택**: Chain of Thought vs Tree of Thoughts 자동 판단 - 항상 활성화
- **AI 모델 자동선택**: 작업별 최적 모델 자동 선택 - 항상 활성화
- **Claude 성능 최적화**: 응답 속도와 품질 향상 - 항상 활성화

#### 🎯 핵심 운영 원칙 (Core Principles)
**Primary Directive**: "Evidence > assumptions | Code > documentation | Efficiency > verbosity"

- **Structured Responses**: Use unified symbol system for clarity and token efficiency
- **Minimal Output**: Answer directly, avoid unnecessary preambles/postambles
- **Evidence-Based Reasoning**: All claims must be verifiable through testing, metrics, or documentation
- **Context Awareness**: Maintain project understanding across sessions and commands
- **Task-First Approach**: Structure before execution - understand, plan, execute, validate
- **Parallel Thinking**: Maximize efficiency through intelligent batching and parallel operations

#### 🚀 슈퍼 클로드 명령어 시스템

**Wave Orchestration Engine**: Multi-stage command execution with compound intelligence. Auto-activates on complexity ≥0.7 + files >20 + operation_types >2.

**Wave-Enabled Commands**:
- **Tier 1**: `/analyze`, `/build`, `/implement`, `/improve`
- **Tier 2**: `/design`, `/task`

**핵심 명령어**:
- **`/build $ARGUMENTS`** - Project builder with framework detection
- **`/implement $ARGUMENTS`** - Feature and code implementation
- **`/analyze $ARGUMENTS`** - Multi-dimensional code and system analysis
- **`/improve [target] [flags]`** - Evidence-based code enhancement

#### 🔧 플래그 시스템

**Planning & Analysis Flags**:
- `--plan`: Display execution plan before operations
- `--think`: Multi-file analysis (~4K tokens)
- `--think-hard`: Deep architectural analysis (~10K tokens)  
- `--ultrathink`: Critical system redesign analysis (~32K tokens)

**Compression & Efficiency Flags**:
- `--uc` / `--ultracompressed`: 30-50% token reduction using symbols
- `--answer-only`: Direct response without task creation
- `--validate`: Pre-operation validation and risk assessment
- `--safe-mode`: Maximum validation with conservative execution

**MCP Server Control Flags**:
- `--c7` / `--context7`: Enable Context7 for library documentation
- `--seq` / `--sequential`: Enable Sequential for complex analysis
- `--magic`: Enable Magic for UI component generation
- `--play` / `--playwright`: Enable Playwright for testing

#### 💡 토큰 효율성 모드

**심볼 시스템**:
| Symbol | Meaning | Example |
|--------|---------|----------|
| → | leads to, implies | `auth.js:45 → security risk` |
| ⇒ | transforms to | `input ⇒ validated_output` |
| & | and, combine | `security & performance` |
| ✅ | completed, passed | None |
| ❌ | failed, error | Immediate |
| ⚠️ | warning | Review |
| 🔄 | in progress | Monitor |

#### 📋 작업 관리 시스템

**작업 상태 관리**:
- **pending** 📋: Ready for execution
- **in_progress** 🔄: Currently active (ONE per session)
- **completed** ✅: Successfully finished
- **blocked** 🚧: Waiting on dependency

**8단계 품질 검증 주기**:
1. **Syntax Validation**: Language parsers, Context7 validation
2. **Type Checking**: Sequential analysis, type compatibility  
3. **Lint Validation**: Context7 rules, quality analysis
4. **Security Scan**: Sequential analysis, vulnerability assessment
5. **Test Coverage**: Playwright E2E, coverage analysis (≥80% unit, ≥70% integration)
6. **Performance**: Sequential analysis, benchmarking
7. **Documentation**: Context7 patterns, completeness validation
8. **Integration**: Playwright testing, deployment validation

---

## Parallel Processing Rules

### Tree-of-Thought Review Protocol
- **MANDATORY**: Before starting any task, run a tree-of-thought review to determine whether parallel execution is safe and worthwhile
- **IF SAFE AND WORTHWHILE**: Use 10 parallel sub-agents for independent research and processing, then merge results as fast as possible
- **EVALUATION CRITERIA**:
  - File interdependencies (parallel unsafe if files modify each other)
  - Sequential requirements (parallel unsafe if order matters)
  - API call dependencies (parallel unsafe if calls must be sequential)
  - Resource conflicts (parallel unsafe if same resources accessed)

## Security Rules

### API Key Management
- **NEVER**: Hardcode API keys, tokens, or credentials in any .py file
- **ONLY**: Store API keys in `Policy/Register_Key/Register_Key.md`
- **ALWAYS**: Use `APIConnector` class for all KIS API calls
- **CHECK**: Validate API key files exist before any trading operations

### Sensitive Data Protection
- **NEVER**: Commit files containing real account numbers or trading keys
- **ALWAYS**: Use `remove_sensitive_data.py` before distribution
- **MANDATORY**: Exclude `Policy/API_key.json` from version control

## Data Integrity Rules

### Hardcoded Value Prohibition
- **NEVER**: Use hardcoded default values like `'0'` in `.get()` calls
- **ALWAYS**: Validate required API response fields exist before use
- **PATTERN**: 
  ```python
  # PROHIBITED:
  cash = float(data.get('dnca_tot_amt', '0'))
  
  # REQUIRED:
  if 'dnca_tot_amt' not in data:
      raise Exception("API 응답에 예수금 정보가 없습니다")
  cash = float(data['dnca_tot_amt'])
  ```
- **APPLY TO**: All account balance, stock data, and API response parsing

### Exception Handling
- **MANDATORY**: Raise descriptive exceptions when API data missing
- **FORMAT**: `"API 응답에 [필드명] 정보가 없습니다"`
- **NO FALLBACKS**: Never use default values for critical financial data

## Backup Rules

### Backup Location
- **MANDATORY LOCATION**: `D:\(인공지능 주식자동매매)\K-AutoTrade Package-Backup`
- **NEVER**: Create backups in root directory or other folders
- **NEVER**: Use C:\Claude_Works or project folders for backups
- **FORMAT**: Use timestamp in backup folder name: `tideWise_backup_YYYY-MM-DD_HH-MM-SS`
- **COMMAND PATTERN**: 
  ```bash
  # REQUIRED backup command pattern:
  xcopy /E /I /Y "source" "D:\(인공지능 주식자동매매)\K-AutoTrade Package-Backup\tideWise_backup_$(date)"
  ```

### Backup Triggers
- **WHEN USER SAYS**: "백업", "backup", "백업해", "백업하라"
- **ALWAYS**: Use the designated backup location without asking
- **INCLUDE**: All project files except .git folder
- **VERIFY**: Backup completion and report size/file count

## File Structure Rules

### Test File Creation
- **ONLY**: Create test files in `tests/` directory
- **NEVER**: Create test files in `support/`, root, or other directories
- **NAMING**: Prefix all test files with `test_`
- **IMPORTS**: Use `PROJECT_ROOT = Path(__file__).parent.parent` pattern

### Algorithm Development
- **LOCATION**: Place all algorithms in `Algorithm/` directory
- **FORMATS**: Support .py, .pine, .js, .txt, .json files
- **MANDATORY**: Implement standard interface (analyze, get_name, get_version, get_description)
- **BACKTESTING**: Run `backtest_all_algorithms.py` for all new algorithms

### Configuration Files
- **STRUCTURE**: 
  - `Policy/Trading_Rule.md` - Trading rules and risk management
  - `Policy/Register_Key/Register_Key.md` - API keys and Telegram settings
  - `support/trading_config.json` - System configuration
  - `support/selected_algorithm.json` - Current algorithm selection

## Trading Operation Rules

### Mode Distinction
- **STRICT**: Maintain clear separation between real (`is_mock=False`) and mock (`is_mock=True`) trading
- **VALIDATION**: Always verify trading mode before executing orders
- **API ENDPOINTS**: Use correct TR_ID for each mode (TTTC vs VTTC prefixes)

### Market Hours
- **TRADING WINDOW**: 09:05-15:30 KST only
- **PRE-MARKET**: 09:05-09:06 KST for position liquidation
- **AUTO STOP**: 15:20 KST (10 minutes before market close)
- **VALIDATION**: Check market hours before any trading operations

### Risk Management
- **POSITION SIZE**: Maximum 7% of available funds per position
- **MAX POSITIONS**: 5 concurrent positions maximum
- **DAILY LOSS LIMIT**: 5% of account value
- **STOP LOSS**: 3% per position
- **PROFIT TARGET**: 7% automatic profit taking

## Multi-File Coordination Rules

### API Connector Dependencies
- **WHEN MODIFYING**: `support/api_connector.py`
- **MUST CHECK**: All files importing APIConnector for compatibility
- **AFFECTED FILES**: 
  - `support/minimal_day_trader.py`
  - `support/day_trading_runner.py`
  - `support/production_auto_trader.py`

### Account Information Files
- **WHEN MODIFYING**: Account balance or position parsing logic
- **MUST UPDATE SIMULTANEOUSLY**:
  - `support/account_info_manager.py`
  - `support/day_trading_account_manager.py`
  - `support/holding_stock_manager.py`
  - `support/menu_manager.py`

### Configuration Changes
- **WHEN MODIFYING**: `Policy/Trading_Rule.md`
- **MUST UPDATE**: `support/trading_rules.json` to match
- **WHEN MODIFYING**: API settings in `Policy/Register_Key/Register_Key.md`
- **MUST TEST**: Connection with both real and mock modes

## Prohibited Actions

### File Operations
- **NEVER**: Create files outside designated directories
- **NEVER**: Modify files in `Policy/Register_Key/` without explicit user request
- **NEVER**: Delete algorithm files without backup
- **NEVER**: Create duplicate test files outside `tests/` directory

### Trading Operations
- **NEVER**: Execute real trades without user confirmation in debug mode
- **NEVER**: Ignore market hours restrictions
- **NEVER**: Override risk management limits
- **NEVER**: Use hardcoded account numbers or stock codes

### Code Modifications
- **NEVER**: Remove exception handling from API calls
- **NEVER**: Add hardcoded fallback values for missing API data
- **NEVER**: Disable logging or error reporting
- **NEVER**: Bypass token refresh mechanisms

## Decision Trees for Common Scenarios

### API Error Handling
1. **IF** API returns no data → Raise exception with specific field name
2. **IF** API returns partial data → Validate required fields, raise exception for missing
3. **IF** API connection fails → Retry with exponential backoff, max 5 attempts
4. **IF** Token expires → Auto-refresh token, retry operation

### Algorithm Loading
1. **IF** Algorithm file exists → Validate interface, load if valid
2. **IF** Interface invalid → Log error, skip algorithm
3. **IF** Algorithm crashes → Catch exception, continue with next algorithm
4. **IF** No algorithms available → Use default algorithm, log warning

### File Modification Priority
1. **SECURITY** issues → Immediate fix required
2. **DATA INTEGRITY** issues → High priority fix
3. **PERFORMANCE** issues → Medium priority
4. **FEATURE** additions → Low priority

## Quality Assurance

### Before Committing
- **RUN**: All tests in `tests/` directory
- **VERIFY**: No hardcoded sensitive data
- **CHECK**: All API calls have proper error handling
- **VALIDATE**: Trading mode consistency

### Testing Requirements
- **UNIT TESTS**: For all new functions in `support/` directory
- **INTEGRATION TESTS**: For API connector changes
- **BACKTESTING**: For all new algorithms
- **MANUAL TESTING**: For trading logic changes in debug mode
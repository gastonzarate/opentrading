# 🦈 Opentrading - Autonomous Cryptocurrency Trading Agent

An AI-powered autonomous trading bot for Binance Futures that uses Claude AI to analyze market data, execute trades, and manage risk in real-time.

![Python](https://img.shields.io/badge/python-3.12-blue.svg)
![Django](https://img.shields.io/badge/django-5.2-green.svg)
![License](https://img.shields.io/badge/license-MIT-blue.svg)

## 🎯 What is Opentrading?

OpenTrading is a sophisticated autonomous cryptocurrency trading system that combines advanced AI reasoning with professional risk management. It continuously monitors multiple cryptocurrency markets, performs technical analysis, and executes trades on Binance Futures (USDT-M) with strict risk controls.

### Key Features

- **🤖 AI-Powered Decision Making**: Uses Claude via AWS Bedrock for intelligent market analysis
- **📊 Multi-Currency Trading**: Supports BTC, ETH, SOL, BNB, XRP, and DOGE
- **⚡ Real-time Technical Analysis**: RSI, MACD, EMA, ATR, Volume analysis, and Open Interest tracking
- **🛡️ Professional Risk Management**: Configurable position sizing, stop-loss requirements, and leverage limits
- **🔄 Autonomous Operation**: Automated scheduling with configurable execution intervals
- **📈 Performance Tracking**: Daily PnL, win rate, and trade history monitoring
- **🎛️ Django Admin Dashboard**: Full control and monitoring through web interface
- **🔍 Observability**: Integrated with Langfuse for AI workflow tracing and monitoring
- **📰 News Aggregation**: Integrated TrendRadar for real-time crypto news from 35+ platforms
- **🐳 Docker Support**: Easy deployment with Docker Compose

## 🏗️ Architecture

The bot uses a workflow-based architecture built with LlamaIndex:

1. **Balance Check**: Validates account balance and trading capability
2. **Market Data Collection**: Concurrent data gathering for all configured currencies
3. **Position Aggregation**: Consolidates open positions, orders, and daily performance
4. **AI Analysis & Execution**: Claude AI analyzes market conditions and executes trades
5. **Result Storage**: Saves execution results, strategy, and performance metrics

### System Architecture Diagram

```mermaid
graph TB
    subgraph SCHEDULERS["⏰ SCHEDULERS"]
        APScheduler["APScheduler<br/>(Ejecuta cada minuto)"]
    end

    subgraph WORKFLOW["🔄 TRADING FUTURES WORKFLOW"]
        Start["Inicio"]
        CheckBalance["1. Check Balance<br/>(Verifica fondos USDT)"]
        CollectData["2. Collect Market Data<br/>(Concurrente para todas las monedas)"]
        AggregatePositions["3. Aggregate Positions<br/>(Consolida datos + posiciones abiertas)"]
        ExecuteAgent["4. Execute Trading Agent<br/>(Claude AI toma decisiones)"]
        SaveResults["5. Save Results<br/>(Guarda en DB)"]
    end

    subgraph AGENT["🤖 AI AGENT - Claude 4.5 Sonnet"]
        SystemPrompt["System Prompt<br/>(Estrategia + Risk Management)"]
        AgentTools["Agent Tools"]
        ReasoningEngine["Reasoning Engine<br/>(Claude via AWS Bedrock)"]
    end

    subgraph TOOLS["🛠️ HERRAMIENTAS DEL AGENTE"]
        BinanceTools["Binance Tools"]
        PythonTools["Python Tools"]
        TrendRadarTools["TrendRadar Tools (MCP)"]

        subgraph BinanceToolsList["Binance Trading Functions"]
            OpenLong["open_long_position<br/>📈 Abre posición larga"]
            OpenShort["open_short_position<br/>📉 Abre posición corta"]
            ClosePosition["close_position<br/>🔒 Cierra posición"]
        end

        subgraph PythonToolsList["Python Code Execution"]
            ExecutePython["execute_python_code<br/>🧮 Cálculos matemáticos"]
        end

        subgraph TrendRadarToolsList["News Aggregation"]
            GetNews["get_news<br/>📰 Noticias de 35+ plataformas"]
        end
    end

    subgraph BINANCE["🔗 BINANCE CLIENT"]
        BinanceAPI["Binance Futures API"]
        MarketData["Market Data<br/>(Precio, RSI, MACD, EMA, ATR)"] 
        OrderExecution["Order Execution"]
        AccountInfo["Account Info"]
    end

    subgraph DATABASE["💾 DATABASE (PostgreSQL)"]
        TradingExecutions["TradingWorkflowExecution"]
        TradingOperations["TradingOperation"]
    end

    subgraph NEWS["📰 NEWS AGGREGATION"]
        TrendRadar["TrendRadar<br/>(35+ plataformas chinas)"]
        NewsDB["SQLite DB"]
    end

    subgraph MONITORING["📊 OBSERVABILITY"]
        Langfuse["Langfuse<br/>(AI workflow tracing)"]
        DjangoAdmin["Django Admin<br/>(Dashboard)"]
    end

    %% Flujo principal
    APScheduler -->|"Trigger cada minuto"| Start
    Start --> CheckBalance
    CheckBalance -->|"Balance OK"| CollectData
    CollectData -->|"BTC, ETH, SOL, BNB, XRP, DOGE"| AggregatePositions
    AggregatePositions -->|"Datos agregados"| ExecuteAgent

    ExecuteAgent --> SystemPrompt
    SystemPrompt --> ReasoningEngine
    ReasoningEngine <-->|"Usa herramientas"| AgentTools

    AgentTools --> BinanceTools
    AgentTools --> PythonTools
    AgentTools --> TrendRadarTools

    BinanceTools --> OpenLong
    BinanceTools --> OpenShort
    BinanceTools --> ClosePosition

    PythonTools --> ExecutePython

    TrendRadarTools --> GetNews
    GetNews -->|"Lee noticias"| NewsDB

    OpenLong -->|"Ejecuta orden"| BinanceAPI
    OpenShort -->|"Ejecuta orden"| BinanceAPI
    ClosePosition -->|"Ejecuta orden"| BinanceAPI

    ExecuteAgent -->|"Decisión tomada"| SaveResults
    SaveResults --> TradingExecutions

    BinanceAPI --> MarketData
    BinanceAPI --> OrderExecution
    BinanceAPI --> AccountInfo

    MarketData -->|"Datos técnicos"| CollectData
    AccountInfo -->|"Balance + Posiciones"| CheckBalance
    OrderExecution -->|"Registra operación"| TradingOperations

    TrendRadar -->|"Noticias cripto"| NewsDB
    NewsDB -.->|"Contexto adicional"| SystemPrompt

    ExecuteAgent -.->|"Trace de workflow"| Langfuse
    TradingExecutions -.->|"Visualiza"| DjangoAdmin
    TradingOperations -.->|"Visualiza"| DjangoAdmin
```

## 🚀 Getting Started

### Prerequisites

- Python 3.12+
- Docker & Docker Compose (recommended)
- Binance account with Futures trading enabled
- AWS account with Bedrock access (Claude)
- Langfuse account (for monitoring)

### Installation

1. **Clone the repository**

   ```bash
   git clone https://github.com/gastonzarate/opentrading.git
   cd trading
   ```

2. **Copy environment configuration**

   ```bash
   cp env.local .env
   ```

3. **Configure environment variables**

   Edit `.env` with your credentials:

   ```bash
   # AWS Configuration (for Claude AI via Bedrock)
   AWS_ACCESS_KEY_ID=your_aws_key
   AWS_SECRET_ACCESS_KEY=your_aws_secret
   AWS_DEFAULT_REGION=us-east-1

   # Langfuse (AI Observability)
   LANGFUSE_PUBLIC_KEY=your_langfuse_public_key
   LANGFUSE_SECRET_KEY=your_langfuse_secret_key
   LANGFUSE_HOST=https://us.cloud.langfuse.com

   # Binance Trading Configuration
   BINANCE_API_KEY=your_binance_api_key
   BINANCE_API_SECRET=your_binance_api_secret

   # Database
   POSTGRES_USER=postgres_user
   POSTGRES_PASSWORD=postgres_password
   POSTGRES_DB=app_db
   ```

4. **Start with Docker Compose** (Recommended)

   ```bash
   docker-compose up -d
   ```

   The API will be available at `http://localhost:8099`

5. **Or run locally**

   ```bash
   # Install dependencies
   pip install -r requirements/base.txt

   # Run migrations
   python manage.py migrate

   # Create superuser for admin access
   python manage.py createsuperuser

   # Start the server
   python manage.py runserver
   ```

### TrendRadar Integration (News Aggregation)

Opentrading integrates with [TrendRadar](https://github.com/sansan0/TrendRadar), a news aggregation tool that monitors 35+ platforms for crypto and trading-related news.

**What it provides:**
- Real-time news aggregation from Chinese platforms (Weibo, Douyin, Baidu, etc.)
- Keyword filtering for crypto/trading topics (BTC, ETH, SOL, etc.)
- SQLite database storage for news data
- Web interface at `http://localhost:8080`
- Optional AI analysis via MCP server

**Included Services:**
- `trend-radar`: Main news crawler service
- `trend-radar-mcp`: AI analysis service (optional)

**Configuration:**
- Keywords: Edit `trendradar/config/frequency_words.txt`
- Settings: Edit `trendradar/config/config.yaml`
- Data storage: `trendradar/output/` (SQLite, TXT, HTML)

**Accessing News Data:**

From your Python code, you can read the SQLite database:

```python
import sqlite3
from pathlib import Path

# Find the latest database file
output_dir = Path("trendradar/output")
db_files = list(output_dir.glob("**/*.db"))
latest_db = max(db_files, key=lambda p: p.stat().st_mtime)

# Connect and query
conn = sqlite3.connect(latest_db)
cursor = conn.cursor()
cursor.execute("SELECT * FROM news WHERE created_at > datetime('now', '-1 hour')")
recent_news = cursor.fetchall()


## 📖 Usage

### Starting the Trading Bot

The bot can be run in two ways:

#### 1. Manual Execution (for testing)

```bash
python main.py
```

This will run a single trading cycle and exit.

#### 2. Automated Scheduling (for production)

The bot includes an APScheduler that runs the trading workflow at configured intervals:

```python
# In your Django app startup (apps/tradings/apps.py)
from apps.tradings.scheduler import start_scheduler

start_scheduler()
```

The scheduler is automatically started when Django loads the `tradings` app.

### Accessing the Admin Dashboard

1. Navigate to `http://localhost:8099/admin`
2. Log in with your superuser credentials
3. You can view:
   - **Trading Workflow Executions**: Full history of all bot runs
   - **Trading Operations**: Individual trade records (open/close positions)
   - **Market data and analysis**: Agent reasoning and decisions

### Viewing the Dashboard

Access the HTML dashboard at `http://localhost:8099/` (or view `index.html`) to see:

- Real-time balance and PnL
- Win rate and trade statistics
- Market data with technical indicators
- Open positions
- AI agent analysis and reasoning

### Customizing the AI Prompt

The trading strategy is defined in `apps/genflows/prompts/trading_futures/trad.txt`. You can customize:

- Risk parameters
- Technical indicators
- Trading rules
- Decision-making framework

The system prompt is rendered from templates in `apps/genflows/prompts/`.

## 📊 Monitoring & Observability

### Langfuse Integration

All AI workflow executions are traced in Langfuse, providing:

- Complete conversation history
- Token usage and costs
- Agent reasoning chains
- Tool usage tracking
- Performance metrics

Access your Langfuse dashboard to monitor AI performance.

### Django Admin

The admin interface provides:

- Execution history with full market data snapshots
- Trade logs with entry/exit prices and PnL
- Agent responses and strategies
- Error logs and debugging information

### Risk Warnings

⚠️ **IMPORTANT DISCLAIMERS**:

- Cryptocurrency trading carries substantial risk
- Past performance does not guarantee future results
- Use at your own risk - this is experimental software
- Never trade with money you can't afford to lose
- The bot can make mistakes - always monitor it
- Market conditions can change rapidly

## 🛠️ Development

### Project Structure

```
opentrading/
├── apps/
│   ├── tradings/          # Trading models, admin, scheduler
│   ├── genflows/          # AI workflows and agents
│   │   └── trading_futures/  # Trading workflow implementation
│   └── accounts/          # User management
├── config/                # Django configuration
├── services/              # External service integrations
│   └── binance_client.py  # Binance API wrapper
├── requirements/          # Python dependencies
├── docker-compose.yml     # Docker setup
├── Dockerfile            # Container definition
└── main.py               # Standalone execution script
```

### Key Components

- **`TradingFuturesWorkflow`**: Main workflow orchestrator
- **`BinanceClient`**: Binance API integration with error handling
- **`BinanceTools`**: MCP tools for AI agent to execute trades
- **`Agent`**: AI agent configuration and prompt rendering
- **`TradingWorkflowExecution`**: Django model for execution storage

### Code Quality

The project uses:

- `flake8` for linting
- `pre-commit` hooks for code quality
- Django best practices

## 🤝 Contributing

Contributions are welcome! Please:

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## 📝 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- Built with [LlamaIndex](https://www.llamaindex.ai/) for AI workflows
- Uses [Claude](https://www.anthropic.com/claude) via AWS Bedrock
- Powered by [Binance API](https://binance-docs.github.io/apidocs/)
- Monitored with [Langfuse](https://langfuse.com/)
- Uses [python-binance](https://github.com/sammchardy/python-binance) SDK

## 📧 Contact & Support

- **Issues**: Please use GitHub Issues for bug reports or feature requests
- **Discussions**: Use GitHub Discussions for questions and ideas

---

**⚠️ Disclaimer**: This software is for educational and research purposes. Cryptocurrency trading is risky and you could lose all your invested capital. Always do your own research and never invest more than you can afford to lose. The authors and contributors are not responsible for any financial losses incurred from using this software.



Que cuando hable te hable de los ultimos registros

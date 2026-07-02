import re
import os
from dataclasses import dataclass
from datetime import datetime

from asgiref.sync import sync_to_async
from llama_index.core.agent.workflow import FunctionAgent
from llama_index.core.agent.workflow.workflow_events import AgentStream
from llama_index.core.workflow import Context, Event, StartEvent, StopEvent, Workflow, step
from llama_index.tools.mcp import BasicMCPClient, McpToolSpec
from tradings.models import TradingWorkflowExecution

from services.binance_client import BinanceClient

from apps.genflows.agent import Agent, LLMModel
from apps.genflows.trading_futures.binance_tools import BinanceTools
from apps.genflows.trading_futures.python_tools import PythonTools


class CollectMarketDataEvent(Event):
    """Event for collecting market data for a specific currency."""

    currency: str


class AggregateDataEvent(Event):
    """Event containing market data for a single currency."""

    currency: str
    market_data: dict


class ExecuteTradeEvent(Event):
    """Event with all aggregated data ready for trading agent."""

    currencies: list[str]
    balance_info: dict
    market_data: dict
    open_positions: list
    daily_pnl: dict


@dataclass
class TradingResult:
    """Result of the trading workflow."""

    currencies: list[str]
    balance_info: dict
    market_data: dict
    open_positions: list
    daily_pnl: dict
    agent_response: str
    agent_streaming_output: str = ""  # Full streaming output from agent
    strategy_for_next_execution: str = ""  # Extracted strategy for next execution
    system_prompt: str = ""  # Complete system prompt provided to agent


class TradingFuturesWorkflow(Workflow):
    """
    Workflow for automated futures trading with professional risk management.

    This workflow:
    1. Checks futures account balance
    2. Collects market data concurrently for multiple currencies
    3. Aggregates open positions
    4. Executes trading agent with all collected information
    """

    def __init__(self, *args, **kwargs):
        """
        Initialize the trading workflow.

        Args:
            binance_client: Optional BinanceClient instance. If not provided, creates a new one.
        """
        super().__init__(*args, **kwargs)
        from apps.genflows.trading_futures.strategy_config import STRATEGY

        # Wire the deterministic risk guardrails into the client so the LLM
        # cannot exceed them, regardless of what the prompt talks it into.
        self.binance_client = BinanceClient(
            max_daily_loss_pct=STRATEGY.max_daily_loss_pct,
            max_leverage=STRATEGY.max_leverage,
            risk_per_trade_pct=STRATEGY.risk_per_trade_pct,
            max_portfolio_risk_pct=STRATEGY.max_portfolio_risk_pct,
            max_concurrent_positions=STRATEGY.max_concurrent_positions,
        )

    @step
    async def check_futures_balance(self, ctx: Context, ev: StartEvent) -> CollectMarketDataEvent | StopEvent:
        """
        Check futures account balance and validate trading capability.

        Args:
            ctx: Workflow context
            ev: StartEvent containing list of currencies

        Returns:
            CollectMarketDataEvent if balance exists, StopEvent if no balance
        """
        currencies = ev.get("currencies", [])
        if not currencies:
            return StopEvent(result={"error": "No currencies provided"})

        await ctx.store.set("currencies", currencies)

        # Get futures balance
        balance_info = self.binance_client.get_futures_balance()

        # Check if there's any balance
        if balance_info["total_wallet_balance"] <= 0:
            return StopEvent(
                result={"error": "No balance available in futures account. Please deposit funds before trading."}
            )

        await ctx.store.set("balance_info", balance_info)

        print(f"\n✓ Balance check passed: ${balance_info['total_wallet_balance']:.2f} available")
        print(f"📊 Collecting market data for {len(currencies)} currencies...")

        # Send market data collection events for each currency
        for currency in currencies:
            ctx.send_event(CollectMarketDataEvent(currency=currency))

    @step(num_workers=4)
    async def collect_market_data(self, ctx: Context, ev: CollectMarketDataEvent) -> AggregateDataEvent:
        """
        Collect market data for a specific currency (runs concurrently).

        Args:
            ctx: Workflow context
            ev: CollectMarketDataEvent with currency to analyze

        Returns:
            AggregateDataEvent with market data
        """
        currency = ev.currency
        print(f"  → Fetching market data for {currency}...")

        try:
            market_data = self.binance_client.get_market_data(currency)
            print(f"  ✓ {currency} data collected (Price: ${market_data['current_price']:.2f})")
            return AggregateDataEvent(currency=currency, market_data=market_data)
        except Exception as e:
            print(f"  ✗ Error collecting data for {currency}: {e}")
            # Return empty data on error
            return AggregateDataEvent(currency=currency, market_data={})

    @step
    async def aggregate_positions(self, ctx: Context, ev: AggregateDataEvent) -> ExecuteTradeEvent | None:
        """
        Aggregate all market data and fetch open positions.

        Args:
            ctx: Workflow context
            ev: AggregateDataEvent from market data collection

        Returns:
            ExecuteTradeEvent when all data is collected, None otherwise
        """
        currencies = await ctx.store.get("currencies")

        # Collect all market data events
        result = ctx.collect_events(ev, [AggregateDataEvent] * len(currencies))
        if result is None:
            return None

        # Aggregate market data into a dictionary
        market_data = {}
        for event in result:
            if event.market_data:  # Only include successful data collection
                market_data[event.currency] = event.market_data

        await ctx.store.set("market_data", market_data)

        print(f"\n✓ Market data aggregated for {len(market_data)} currencies")
        print("📈 Fetching open positions and daily performance...")

        # Get all open positions (now includes associated orders)
        open_positions = self.binance_client.get_all_open_positions()
        await ctx.store.set("open_positions", open_positions)

        # Get daily performance metrics
        daily_pnl = self.binance_client.get_daily_pnl()
        await ctx.store.set("daily_pnl", daily_pnl)

        print(f"✓ Found {len(open_positions)} open position(s)")
        print(
            f"✓ Daily PnL: ${daily_pnl['total_daily_pnl']:.2f} "
            f"(Realized: ${daily_pnl['daily_realized_pnl']:.2f}, "
            f"Unrealized: ${daily_pnl['unrealized_pnl']:.2f}, "
            f"{daily_pnl['trade_count']} trades, {daily_pnl['win_rate']:.1f}% win rate)"
        )


        balance_info = await ctx.store.get("balance_info")

        return ExecuteTradeEvent(
            currencies=currencies,
            balance_info=balance_info,
            market_data=market_data,
            open_positions=open_positions,
            daily_pnl=daily_pnl,
        )

    @step
    async def execute_trading_agent(self, ctx: Context, ev: ExecuteTradeEvent) -> StopEvent:
        """
        Execute trading agent with all collected information.

        Args:
            ctx: Workflow context
            ev: ExecuteTradeEvent with all aggregated data

        Returns:
            StopEvent with trading results and agent response
        """

        print("\n🤖 Initializing trading agent...")

        # Retrieve the most recent execution to get previous strategy
        # Use sync_to_async to safely access Django ORM from async context

        @sync_to_async
        def get_previous_execution():
            return TradingWorkflowExecution.objects.filter(status=TradingWorkflowExecution.Status.SUCCESS).first()

        previous_execution = await get_previous_execution()

        previous_execution_strategy = ""
        last_execution_time = None

        if previous_execution:
            previous_execution_strategy = previous_execution.strategy_for_next_execution
            last_execution_time = previous_execution.created_at.strftime("%Y-%m-%d %H:%M:%S")

        # Create agent and render prompt
        # Low temperature: real-money decisions should be as deterministic as
        # possible so identical market data yields consistent actions (audit fix #19).
        agent = Agent(
            prompt_name="trading_futures",
            model=LLMModel.BEDROCK_CLAUDE_4_5_SONNET,
            temperature=0.1,
        )

        # Prepare context for prompt rendering
        from apps.tradings.scheduler import EXECUTION_INTERVAL_MINUTES
        from apps.genflows.trading_futures.strategy_config import STRATEGY

        prompt_context = {
            "currencies": ev.currencies,
            "balance_info": ev.balance_info,
            "market_data": ev.market_data,
            "open_positions": ev.open_positions,
            "daily_pnl": ev.daily_pnl,
            "current_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "last_execution_time": last_execution_time,
            "previous_execution_strategy": previous_execution_strategy,
            "execution_interval_minutes": EXECUTION_INTERVAL_MINUTES,
            "config": STRATEGY,
        }

        # Render the prompt
        prompt_system = await agent.render_prompt(context=prompt_context)

        # Create tools
        mcp_client = BasicMCPClient(
            os.getenv("MCP_TRENDRADAR_URL")
        )
        mcp_tool_spec = McpToolSpec(
            client=mcp_client,
        )
        tools = await mcp_tool_spec.to_tool_list_async()

        binance_tools = BinanceTools(self.binance_client)
        tools += binance_tools.list_tools()

        python_tools = PythonTools()
        tools += python_tools.list_tools()

        print(f"✓ Agent initialized with {len(tools)} trading tools")
        if previous_execution_strategy:
            print(f"✓ Loaded previous execution strategy ({len(previous_execution_strategy)} chars)")
        print("\n" + "=" * 80)
        print("🎯 TRADING AGENT ANALYSIS")
        print("=" * 80 + "\n")

        # Create function agent
        function_agent = FunctionAgent(
            llm=agent.llm,
            tools=tools,
            system_prompt=prompt_system,
        )
        handler = function_agent.run(
            user_msg="Analyze the current market conditions and execute trades if appropriate.",
            max_iterations=40,
        )

        # Capture streaming output
        streaming_response = []
        async for event in handler.stream_events():
            if isinstance(event, AgentStream):
                # Send each chunk via WebSocket
                chunk = event.delta or ""
                if chunk:
                    streaming_response.append(chunk)
                    print(chunk, end="", flush=True)

        # Get final result
        final_result = await handler
        agent_response = final_result.response.content

        # Combine streaming chunks into full response
        full_streaming_output = "".join(streaming_response)

        # Extract "Strategy for Next Execution" section from agent response
        strategy_for_next_execution = ""
        # Try to find the strategy section in the response
        strategy_pattern = r"## Strategy for Next Execution.*?(?=\n##|\Z)"
        strategy_match = re.search(strategy_pattern, agent_response, re.DOTALL | re.IGNORECASE)
        if strategy_match:
            strategy_for_next_execution = strategy_match.group(0).strip()
            print(f"\n\n✓ Extracted strategy for next execution ({len(strategy_for_next_execution)} chars)")
        else:
            print("\n\n⚠️  Warning: Agent did not provide 'Strategy for Next Execution' section")

        print("\n" + "=" * 80)
        print("✓ Trading agent execution completed")
        print("=" * 80 + "\n")

        return StopEvent(
            result=TradingResult(
                currencies=ev.currencies,
                balance_info=ev.balance_info,
                market_data=ev.market_data,
                open_positions=ev.open_positions,
                daily_pnl=ev.daily_pnl,
                agent_response=agent_response,
                agent_streaming_output=full_streaming_output,
                strategy_for_next_execution=strategy_for_next_execution,
                system_prompt=prompt_system,
            )
        )

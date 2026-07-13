import asyncio
from datetime import datetime

from genflows.trading.workflow import TradingWorkflow
from langfuse import get_client
from openinference.instrumentation.llama_index import LlamaIndexInstrumentor


async def run_workflow():
    # Langfuse configuration
    LlamaIndexInstrumentor().instrument()
    langfuse = get_client()
    trace_id = langfuse.create_trace_id()
    # pylint: disable=not-context-manager
    with langfuse.start_as_current_span(
        name="opentrading-workflow", input=f"Execution {datetime.now().isoformat()}", trace_context={"trace_id": trace_id}
    ):
        langfuse.update_current_trace(user_id="elgastu", session_id=1)

        # Run workflow
        workflow = TradingWorkflow(timeout=180)
        result = await workflow.run()

        langfuse.update_current_trace(
            output=result,
        )
        print(f"✅ Result: {result.assistant}")

    langfuse.flush()


if __name__ == "__main__":
    asyncio.run(run_workflow())

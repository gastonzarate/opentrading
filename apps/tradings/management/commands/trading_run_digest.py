"""
Readable digest of a trading-bot run, for iterating on the agent.

Turns the persisted executions + operations of a demo (or live) run into a
scannable report so "conclusions" come from data, not vibes. Focuses on
behaviour and operations — NOT PnL as a verdict (a 1-2 day, few-symbol,
regime-gated run is far too small a sample to judge edge; that's the backtest's
job). Read it as: did the loop run reliably, did the guardrails fire, did the
LLM decide sensibly, was the cadence sane.

Usage:
    python manage.py trading_run_digest                 # last 48h
    python manage.py trading_run_digest --hours 24
    python manage.py trading_run_digest --last 20       # last N executions
    python manage.py trading_run_digest --details       # + reasoning excerpts
"""
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from tradings.models import TradingOperation, TradingWorkflowExecution


def _fmt_dt(dt):
    if not dt:
        return "—"
    # Project may run with USE_TZ=False (naive datetimes); localtime() only
    # applies to aware ones.
    if timezone.is_aware(dt):
        dt = timezone.localtime(dt)
    return dt.strftime("%m-%d %H:%M")


def _regimes(market_data):
    """{'BTC': 'TREND', ...} from an execution's market_data JSON."""
    out = {}
    if isinstance(market_data, dict):
        for cur, md in market_data.items():
            if isinstance(md, dict) and md.get("regime"):
                out[cur] = md["regime"]
    return out


class Command(BaseCommand):
    help = "Print a readable digest of recent trading-bot executions for iteration."

    def add_arguments(self, parser):
        parser.add_argument("--hours", type=int, default=48, help="Look back this many hours (default 48).")
        parser.add_argument("--last", type=int, default=None, help="Instead of --hours, take the last N executions.")
        parser.add_argument("--details", action="store_true", help="Include per-execution reasoning excerpts.")

    def handle(self, *args, **opts):
        qs = TradingWorkflowExecution.objects.order_by("created_at")
        if opts["last"]:
            ids = list(
                TradingWorkflowExecution.objects.order_by("-created_at")
                .values_list("id", flat=True)[: opts["last"]]
            )
            qs = qs.filter(id__in=ids)
            window_label = f"last {opts['last']} executions"
        else:
            since = timezone.now() - timedelta(hours=opts["hours"])
            qs = qs.filter(created_at__gte=since)
            window_label = f"last {opts['hours']}h"

        execs = list(qs)
        if not execs:
            self.stdout.write(self.style.WARNING(f"No executions found ({window_label})."))
            return

        w = self.stdout.write
        line = "=" * 78

        # ---- Summary --------------------------------------------------------
        n = len(execs)
        by_status = {}
        for e in execs:
            by_status[e.status] = by_status.get(e.status, 0) + 1

        ops = list(TradingOperation.objects.filter(workflow_execution__in=execs).order_by("created_at"))
        ops_by_type = {}
        ops_errors = 0
        blocks = 0
        for op in ops:
            ops_by_type[op.operation_type] = ops_by_type.get(op.operation_type, 0) + 1
            if op.status == TradingOperation.Status.ERROR:
                ops_errors += 1
            if isinstance(op.result_data, dict) and op.result_data.get("blocked"):
                blocks += 1

        errored_execs = [e for e in execs if e.status == TradingWorkflowExecution.Status.ERROR]

        # cadence: actual gaps vs the agent-chosen next_run_minutes
        gaps = []
        for a, b in zip(execs, execs[1:]):
            gaps.append((b.created_at - a.created_at).total_seconds() / 60.0)
        nexts = [e.next_run_minutes for e in execs if e.next_run_minutes is not None]

        first_pnl = (execs[0].daily_pnl or {}).get("total_daily_pnl")
        last_pnl = (execs[-1].daily_pnl or {}).get("total_daily_pnl")

        w(line)
        w(f" RUN DIGEST — {window_label}   ({_fmt_dt(execs[0].created_at)} → {_fmt_dt(execs[-1].created_at)})")
        w(line)
        w(f" Executions: {n}   " + "  ".join(f"{k}={v}" for k, v in sorted(by_status.items())))
        w(f" Operations: {len(ops)}   " + ("  ".join(f"{k}={v}" for k, v in sorted(ops_by_type.items())) or "none"))
        w(f" Guardrail blocks: {blocks}   Operation errors: {ops_errors}   Errored executions: {len(errored_execs)}")
        if gaps:
            w(f" Cadence (min between runs): avg={sum(gaps)/len(gaps):.1f}  min={min(gaps):.1f}  max={max(gaps):.1f}")
        if nexts:
            w(f" next_run_minutes (agent-chosen): avg={sum(nexts)/len(nexts):.1f}  min={min(nexts)}  max={max(nexts)}")
        if first_pnl is not None and last_pnl is not None:
            w(f" Daily PnL first→last: {first_pnl:+.2f} → {last_pnl:+.2f}   (sample too small for an edge verdict)")

        # ---- Per-execution --------------------------------------------------
        w("")
        w(" TIMELINE")
        w("-" * 78)
        for e in execs:
            regimes = _regimes(e.market_data)
            reg = " ".join(f"{c}:{r[:4]}" for c, r in regimes.items()) or "—"
            eops = [op for op in ops if op.workflow_execution_id == e.id]
            act = ", ".join(f"{op.operation_type}/{op.currency}" for op in eops) or "no-op"
            flag = "✗" if e.status == TradingWorkflowExecution.Status.ERROR else " "
            nr = f"{e.next_run_minutes}m" if e.next_run_minutes is not None else "—"
            w(f" {flag} {_fmt_dt(e.created_at)}  [{e.status[:4]}]  next={nr:>4}  {reg}")
            w(f"      action: {act}")
            if e.error_message:
                w(self.style.ERROR(f"      error: {e.error_message.strip()[:160]}"))
            for op in eops:
                if isinstance(op.result_data, dict) and op.result_data.get("blocked"):
                    reason = op.result_data.get("reason") or op.result_data.get("error") or "blocked"
                    w(self.style.WARNING(f"      guardrail block: {op.operation_type}/{op.currency} — {str(reason)[:120]}"))
            if opts["details"] and e.agent_response:
                excerpt = e.agent_response.strip().replace("\n", " ")
                w(f"      reasoning: {excerpt[:280]}…")

        # ---- Issues bucket --------------------------------------------------
        if errored_execs or ops_errors:
            w("")
            w(" ISSUES")
            w("-" * 78)
            for e in errored_execs:
                w(self.style.ERROR(f" {_fmt_dt(e.created_at)}  {(e.error_message or '').strip()[:200]}"))
            for op in ops:
                if op.status == TradingOperation.Status.ERROR:
                    w(self.style.ERROR(f" {_fmt_dt(op.created_at)}  op {op.operation_type}/{op.currency}: {(op.error_message or '').strip()[:160]}"))

        w("")
        w(self.style.SUCCESS(" Digest complete. Review buckets: bugs · prompt/strategy · risk-config · model · ops."))
        w(" Reminder: change ONE lever per iteration so you can attribute the effect.")

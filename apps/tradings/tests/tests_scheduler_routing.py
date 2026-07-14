import importlib


def test_active_workflow_defaults_to_trading_futures(monkeypatch):
    monkeypatch.delenv("ACTIVE_WORKFLOW", raising=False)
    sched = importlib.import_module("apps.tradings.scheduler")
    assert sched.active_workflow() == "trading_futures"


def test_active_workflow_reads_env(monkeypatch):
    monkeypatch.setenv("ACTIVE_WORKFLOW", "exploit_6")
    sched = importlib.import_module("apps.tradings.scheduler")
    assert sched.active_workflow() == "exploit_6"

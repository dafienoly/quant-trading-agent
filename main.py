"""量化交易 Agent 启动入口

启动方式:
    python main.py api          # 启动 API 服务
    python main.py dashboard    # 启动 Streamlit 面板
    python main.py signal       # 运行一次信号生成
"""
import sys


def start_api():
    """启动 FastAPI 服务"""
    import uvicorn
    from src.api.app import create_app
    from src.config.settings import MAX_TRADING_LEVEL
    from src.execution_engine.broker_adapter import PaperBroker
    from src.execution_engine.execution_service import ExecutionService
    from src.risk_engine.runtime import RuntimeRiskEngine

    risk_engine = RuntimeRiskEngine()
    broker = PaperBroker()
    execution_service = ExecutionService(
        risk_engine=risk_engine,
        broker=broker,
        trading_mode=MAX_TRADING_LEVEL,
    )
    app = create_app(risk_engine=risk_engine, execution_service=execution_service)
    uvicorn.run(app, host="0.0.0.0", port=8000)


def start_dashboard():
    """启动 Streamlit 面板"""
    import subprocess
    subprocess.run([
        sys.executable, "-m", "streamlit", "run",
        "src/ui_report/dashboard.py",
        "--server.port", "8501",
    ])


def run_signal_once():
    """运行一次信号生成"""
    from src.agent_orchestrator.signal_service import SignalService
    from src.risk_engine.runtime import RuntimeRiskEngine

    risk_engine = RuntimeRiskEngine()
    service = SignalService(risk_engine=risk_engine)
    result = service.run_once()
    if result:
        print(f"信号生成完成: {len(result.get('signals', []))} 个信号")
    else:
        print("信号生成完成: 无信号")


def main():
    if len(sys.argv) < 2:
        print("用法: python main.py [api|dashboard|signal]")
        print("  api       - 启动 FastAPI 服务 (端口 8000)")
        print("  dashboard - 启动 Streamlit 面板 (端口 8501)")
        print("  signal    - 运行一次信号生成")
        sys.exit(1)

    command = sys.argv[1].lower()
    if command == "api":
        start_api()
    elif command == "dashboard":
        start_dashboard()
    elif command == "signal":
        run_signal_once()
    else:
        print(f"未知命令: {command}")
        print("可用命令: api, dashboard, signal")
        sys.exit(1)


if __name__ == "__main__":
    main()

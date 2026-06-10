"""Bug 文件监控看门狗

监控 feedback/bugs/open/ 目录，当发现新的 Bug 报告时自动触发回调（通常为 BugFixAgent）。
支持 watchdog 库实时监控，若 watchdog 未安装则回退到轮询模式。
"""
from __future__ import annotations

import json
import threading
import time
from pathlib import Path
from typing import Callable, Optional

from loguru import logger


class BugWatchdog:
    """Bug 文件监控看门狗

    监控 feedback/bugs/open/ 目录中的 .json 文件变化，
    当检测到新的 Bug 报告时调用回调函数通知 BugFixAgent 进行自动分析。
    """

    def __init__(self, on_new_bug_callback: Optional[Callable[[str, dict], None]] = None) -> None:
        """初始化 BugWatchdog

        参数:
            on_new_bug_callback: 新 Bug 检测回调，签名为 (bug_id: str, bug_report: dict) -> None
        """
        self._on_new_bug_callback = on_new_bug_callback
        self._observer = None
        self._watch_path: Path = Path(__file__).resolve().parent.parent.parent / "feedback" / "bugs" / "open"
        self._processed_ids: set[str] = set()
        # 轮询回退相关
        self._poller_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        # 防抖：记录最近处理的文件路径及时间
        self._recent_events: dict[str, float] = {}
        self._DEBOUNCE_SECONDS = 2.0
        self._POLL_INTERVAL = 30

    def start(self) -> None:
        """启动监控

        优先使用 watchdog 库进行实时文件系统监控；
        若 watchdog 未安装则回退到 30 秒间隔的轮询模式。
        """
        # 确保目录存在
        self._watch_path.mkdir(parents=True, exist_ok=True)

        # 先处理已有的 Bug 文件
        self.process_existing_bugs()

        try:
            from watchdog.events import FileSystemEventHandler
            from watchdog.observers import Observer

            watchdog_instance = self

            class _BugFileHandler(FileSystemEventHandler):
                """Bug 文件事件处理器"""

                def on_created(self, event) -> None:  # type: ignore[override]
                    watchdog_instance._handle_file_event(event.src_path)

                def on_modified(self, event) -> None:  # type: ignore[override]
                    watchdog_instance._handle_file_event(event.src_path)

            handler = _BugFileHandler()
            self._observer = Observer()
            self._observer.schedule(handler, str(self._watch_path), recursive=False)
            self._observer.start()
            logger.info(f"BugWatchdog started, monitoring: {self._watch_path}")

        except ImportError:
            logger.warning("watchdog 库未安装，回退到轮询模式（每 30 秒检查一次）")
            self._start_polling()
            logger.info(f"BugWatchdog started (polling mode), monitoring: {self._watch_path}")

    def stop(self) -> None:
        """停止监控"""
        # 停止 watchdog observer
        if self._observer is not None and self._observer.is_alive():
            self._observer.stop()
            self._observer.join(timeout=5)
            self._observer = None

        # 停止轮询线程
        self._stop_event.set()
        if self._poller_thread is not None and self._poller_thread.is_alive():
            self._poller_thread.join(timeout=5)
            self._poller_thread = None

        logger.info("BugWatchdog stopped")

    def is_running(self) -> bool:
        """检查监控是否正在运行

        返回:
            True 如果 watchdog observer 或轮询线程正在运行
        """
        if self._observer is not None and self._observer.is_alive():
            return True
        if self._poller_thread is not None and self._poller_thread.is_alive():
            return True
        return False

    def process_existing_bugs(self) -> None:
        """扫描并处理目录中已有的 Bug 文件

        在启动时调用，处理 watchdog 未运行期间创建的 Bug 报告。
        """
        if not self._watch_path.exists():
            return

        count = 0
        for json_file in self._watch_path.glob("*.json"):
            try:
                with open(json_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                bug_id = data.get("bug_id", "")
                if not bug_id or bug_id in self._processed_ids:
                    continue
                self._processed_ids.add(bug_id)
                count += 1
                self._invoke_callback(bug_id, data)
            except (json.JSONDecodeError, OSError) as e:
                logger.warning(f"读取已有 Bug 文件失败 {json_file.name}: {e}")

        if count > 0:
            logger.info(f"BugWatchdog 发现 {count} 个已有 Bug 报告")

    # ----------------------------------------------------------
    # 内部方法
    # ----------------------------------------------------------

    def _handle_file_event(self, src_path: str) -> None:
        """处理文件系统事件

        参数:
            src_path: 事件对应的文件路径
        """
        path = Path(src_path)

        # 仅处理 .json 文件
        if path.suffix.lower() != ".json":
            return

        # 防抖：跳过 2 秒内刚处理过的文件
        now = time.time()
        last_time = self._recent_events.get(src_path, 0.0)
        if now - last_time < self._DEBOUNCE_SECONDS:
            return
        self._recent_events[src_path] = now

        # 清理过期的防抖记录
        expired = [k for k, v in self._recent_events.items() if now - v > self._DEBOUNCE_SECONDS * 2]
        for k in expired:
            del self._recent_events[k]

        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            bug_id = data.get("bug_id", "")
            if not bug_id:
                logger.warning(f"Bug 文件缺少 bug_id: {path.name}")
                return
            if bug_id in self._processed_ids:
                return
            self._processed_ids.add(bug_id)
            self._invoke_callback(bug_id, data)
        except (json.JSONDecodeError, OSError) as e:
            logger.warning(f"读取 Bug 文件失败 {path.name}: {e}")

    def _invoke_callback(self, bug_id: str, bug_report: dict) -> None:
        """调用回调函数

        参数:
            bug_id: Bug 唯一标识
            bug_report: Bug 报告字典
        """
        if self._on_new_bug_callback is not None:
            try:
                self._on_new_bug_callback(bug_id, bug_report)
            except Exception as e:
                logger.error(f"BugWatchdog 回调执行失败 (bug_id={bug_id}): {e}")

    def _start_polling(self) -> None:
        """启动轮询线程作为 watchdog 的回退方案"""
        self._stop_event.clear()

        def _poll_loop() -> None:
            while not self._stop_event.is_set():
                try:
                    if self._watch_path.exists():
                        for json_file in self._watch_path.glob("*.json"):
                            try:
                                with open(json_file, "r", encoding="utf-8") as f:
                                    data = json.load(f)
                                bug_id = data.get("bug_id", "")
                                if not bug_id or bug_id in self._processed_ids:
                                    continue
                                self._processed_ids.add(bug_id)
                                self._invoke_callback(bug_id, data)
                            except (json.JSONDecodeError, OSError) as e:
                                logger.warning(f"轮询读取 Bug 文件失败 {json_file.name}: {e}")
                except Exception as e:
                    logger.error(f"BugWatchdog 轮询异常: {e}")

                self._stop_event.wait(timeout=self._POLL_INTERVAL)

        self._poller_thread = threading.Thread(target=_poll_loop, daemon=True)
        self._poller_thread.start()

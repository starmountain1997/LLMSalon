import os
import signal
import subprocess
import sys
import time

from loguru import logger
from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer

from config import SETTING_PATH
from utils import PROJECT_ROOT

GRADIO_COMMAND = [sys.executable, "interface.py"]

current_process = None


def start_gradio_process():
    """启动 Gradio 进程"""
    global current_process
    logger.info(f"尝试启动 Gradio: {' '.join(GRADIO_COMMAND)}")
    try:
        preexec_fn = None
        creationflags = 0
        if os.name == "posix":  # Linux/macOS
            preexec_fn = os.setsid
        elif os.name == "nt":  # Windows
            creationflags = subprocess.CREATE_NEW_PROCESS_GROUP

        current_process = subprocess.Popen(
            GRADIO_COMMAND,
            preexec_fn=preexec_fn,
            creationflags=creationflags,
            cwd=os.path.join(PROJECT_ROOT, "src"),
        )
        logger.info(f"Gradio 进程已启动，PID: {current_process.pid}")
    except Exception as e:
        logger.error(f"启动 Gradio 失败: {e}")
        current_process = None


def stop_gradio_process():
    """停止当前的 Gradio 进程"""
    global current_process
    if current_process and current_process.poll() is None:  # 检查进程是否仍在运行
        logger.info(f"尝试停止 Gradio 进程 PID: {current_process.pid}")
        try:
            # 尝试优雅地终止
            if os.name == "posix":
                # 发送 SIGTERM 到整个进程组
                os.killpg(os.getpgid(current_process.pid), signal.SIGTERM)
            elif os.name == "nt":
                # 发送 CTRL_BREAK_EVENT 到进程组
                current_process.send_signal(signal.CTRL_BREAK_EVENT)

            current_process.wait(timeout=5)  # 等待最多5秒
            logger.info(f"Gradio 进程 {current_process.pid} 已终止。")
        except subprocess.TimeoutExpired:
            logger.error(f"进程 {current_process.pid} 未能在5秒内终止，强制终止。")
            # 如果优雅终止失败，强制杀死
            if os.name == "posix":
                os.killpg(os.getpgid(current_process.pid), signal.SIGKILL)
            elif os.name == "nt":
                current_process.kill()  # 在Windows上，kill() 是 terminate() 的别名，可能不够强制
                # 更强制的方法是用 taskkill
                # subprocess.run(['taskkill', '/F', '/T', '/PID', str(current_process.pid)], check=True)

            current_process.wait()  # 等待强制终止完成
            logger.info(f"Gradio 进程 {current_process.pid} 已被强制终止。")
        except Exception as e:
            logger.info(f"停止 Gradio 进程 {current_process.pid} 时出错: {e}")
        finally:
            current_process = None  # 确保重置
    elif current_process:
        logger.info(f"Gradio 进程 {current_process.pid} 似乎已经停止了。")
        current_process = None
    else:
        logger.info("没有正在运行的 Gradio 进程可以停止。")


class YamlChangeHandler(FileSystemEventHandler):
    """处理文件系统事件的类"""

    def __init__(self, filename):
        self.filename = os.path.basename(filename)
        self._last_event_time = 0
        self._debounce_time = 1  # 1 秒去抖动时间

    def on_modified(self, event):
        # 检查事件是否针对我们关心的文件，并且不是目录
        if not event.is_directory and os.path.basename(event.src_path) == self.filename:
            current_time = time.time()
            # 简单的去抖动，防止编辑器保存时触发多次
            if current_time - self._last_event_time > self._debounce_time:
                print(f"\n检测到文件更改: {event.src_path}")
                print("正在重新启动 Gradio 应用...")
                stop_gradio_process()
                # 短暂暂停确保端口已释放（如果需要）
                time.sleep(1)
                start_gradio_process()
                self._last_event_time = current_time

    def on_created(self, event):
        # 如果文件被删除后又重新创建，也触发重启
        if not event.is_directory and os.path.basename(event.src_path) == self.filename:
            current_time = time.time()
            if current_time - self._last_event_time > self._debounce_time:
                print(f"\n检测到文件创建: {event.src_path}")
                print("正在重新启动 Gradio 应用...")
                stop_gradio_process()
                time.sleep(1)
                start_gradio_process()
                self._last_event_time = current_time


# --- 主程序 ---
if __name__ == "__main__":
    yaml_dir = os.path.dirname(SETTING_PATH)
    yaml_filename = os.path.basename(SETTING_PATH)

    # 检查 Gradio 命令中的文件是否存在（如果它是 Python 文件）
    if len(GRADIO_COMMAND) > 2 and GRADIO_COMMAND[-1].endswith(".py"):
        interface_file = GRADIO_COMMAND[-1]
        if not os.path.exists(interface_file):
            print(f"警告: Gradio 脚本 '{interface_file}' 未找到。请确保路径正确。")

    # 检查 YAML 文件是否存在，如果不存在，提示但继续监控（可能稍后创建）
    if not os.path.exists(SETTING_PATH):
        raise Exception(f"警告: YAML 文件 '{SETTING_PATH}' 当前不存在")

    # 创建事件处理器和观察者
    event_handler = YamlChangeHandler(SETTING_PATH)
    observer = Observer()
    # 监控 YAML 文件所在的目录
    observer.schedule(event_handler, yaml_dir, recursive=False)
    observer.start()
    logger.info("文件监控器已启动。")

    start_gradio_process()

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        logger.info("\n检测到 Ctrl+C，正在停止...")
        observer.stop()
        logger.info("文件监控器已停止")
        stop_gradio_process()  # 确保最后一次运行的进程被停止
    except Exception as e:
        logger.error(f"发生意外错误: {e}")
        observer.stop()
        stop_gradio_process()
    finally:
        observer.join()  # 等待观察者线程完全结束
        logger.info("文件监控器已停止")

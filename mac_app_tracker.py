import os
import sys
import time
import json
import psutil
import threading
import datetime
import subprocess
import pystray
from PIL import Image, ImageDraw
import atexit
from pathlib import Path

# 尝试导入 macOS 特定的库
try:
    from AppKit import NSWorkspace, NSApplication
    from Quartz import (
        CGEventSourceSecondsSinceLastEventType,
        kCGEventSourceStateHIDSystemState,
        kCGAnyInputEventType
    )
    MACOS_AVAILABLE = True
except ImportError:
    MACOS_AVAILABLE = False
    print("警告: 未安装 macOS 所需的库。请运行: pip install pyobjc-framework-Quartz pyobjc-framework-AppKit")

# --- 配置路径 ---
# BASE_DIR 设置为脚本所在目录
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "Data")
CONFIG_FILE = os.path.join(BASE_DIR, "statistics.configuration.json")

# 确保目录存在
if not os.path.exists(BASE_DIR):
    os.makedirs(BASE_DIR)
if not os.path.exists(DATA_DIR):
    os.makedirs(DATA_DIR)

# --- 全局变量 ---
running = True
current_date_str = datetime.datetime.now().strftime("%Y%m%d")
data_lock = threading.Lock()
is_idle_status = False  # 记录当前是否处于闲置状态

# 数据结构初始化
stats_data = {
    "sessions": [],  # 记录 [{"start": "...", "end": "..."}, ...]
    "idle_seconds": 0,
    "apps": {}  # { "app_name": { "total": 0, "titles": { "title_name": seconds } } }
}

# 当前Session开始时间
current_session_start = time.time()

# --- macOS API 定义 (用于检测闲置和获取窗口信息) ---


def get_idle_duration():
    """获取系统闲置时间（秒）"""
    if not MACOS_AVAILABLE:
        return 0
    try:
        idle_time = CGEventSourceSecondsSinceLastEventType(
            kCGEventSourceStateHIDSystemState,
            kCGAnyInputEventType
        )
        return idle_time if idle_time is not None else 0
    except Exception:
        return 0


def get_active_window_info():
    """获取当前活动窗口的应用名称和窗口标题"""
    if not MACOS_AVAILABLE:
        return None, None
    
    try:
        workspace = NSWorkspace.sharedWorkspace()
        frontmost_app = workspace.frontmostApplication()
        
        if not frontmost_app:
            return None, None
        
        # 获取应用名称（通常是 .app 的包名，需要提取）
        app_name = frontmost_app.localizedName()
        if not app_name:
            app_name = frontmost_app.bundleIdentifier()
            # 从 bundle identifier 提取名称（例如：com.google.Chrome -> Chrome）
            if app_name and '.' in app_name:
                app_name = app_name.split('.')[-1]
        
        # 在 macOS 上，获取窗口标题比较复杂
        # 使用 AppleScript 来获取当前窗口标题
        try:
            script = '''
            tell application "System Events"
                set frontApp to first application process whose frontmost is true
                set appName to name of frontApp
                try
                    set windowTitle to name of first window of frontApp
                on error
                    set windowTitle to ""
                end try
                return windowTitle
            end tell
            '''
            result = subprocess.run(
                ['osascript', '-e', script],
                capture_output=True,
                text=True,
                timeout=1
            )
            title = result.stdout.strip() if result.returncode == 0 else ""
        except Exception:
            title = ""
        
        # 处理空标题的情况
        if not title or not title.strip():
            title = "Unknown Title"
        
        # macOS 应用名称通常不带 .app 后缀，但我们需要统一格式
        # 将其转换为类似 Windows 的格式（例如：Chrome.app）
        if app_name and not app_name.endswith('.app'):
            app_name = f"{app_name}.app"
        
        return app_name, title
    except Exception as e:
        # 如果获取失败，尝试使用 psutil 作为备用方案
        try:
            # 获取当前活动进程
            current_process = psutil.Process().parent()
            for proc in psutil.process_iter(['pid', 'name']):
                try:
                    if proc.info['name']:
                        # 简单的备用方案：返回进程名
                        return proc.info['name'], "Unknown Title"
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    pass
        except Exception:
            pass
        return None, None

# --- 日志与文件操作 ---


def get_file_paths(date_str=None):
    if not date_str:
        date_str = datetime.datetime.now().strftime("%Y%m%d")
    
    # 根据日期计算子目录：YYYYMMDD -> YYYY.mm
    year = date_str[:4]
    month = date_str[4:6]
    subdir = f"{year}.{month}"
    subdir_path = os.path.join(DATA_DIR, subdir)
    
    # 确保子目录存在
    if not os.path.exists(subdir_path):
        os.makedirs(subdir_path)
    
    return {
        "json": os.path.join(subdir_path, f"{date_str}.data.json"),
        "report": os.path.join(subdir_path, f"{date_str}.report.txt"),
        "log": os.path.join(subdir_path, f"{date_str}.log.txt")
    }


def write_log(message):
    """写入日志"""
    paths = get_file_paths()
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(paths["log"], "a", encoding="utf-8") as f:
        f.write(f"[{timestamp}] {message}\n")


def load_config():
    """读取白名单配置"""
    # macOS 默认白名单应用（注意 macOS 应用名称格式不同）
    default_exempt = [
        "VLC.app",
        "Google Chrome.app",
        "Safari.app",
        "Spotify.app",
        "Music.app",
        "TV.app",
        "QuickTime Player.app"
    ]
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                config = json.load(f)
                exempt_list = config.get("idleExempt", [])
                # 如果配置文件中是 Windows 格式，尝试转换
                # 或者直接使用配置的值
                return exempt_list if exempt_list else default_exempt
        except:
            pass
    return default_exempt


def load_data():
    """程序启动时读取当天的JSON数据"""
    global stats_data
    paths = get_file_paths()
    if os.path.exists(paths["json"]):
        try:
            with open(paths["json"], "r", encoding="utf-8") as f:
                stats_data = json.load(f)
                # 确保 session 列表存在
                if "sessions" not in stats_data:
                    stats_data["sessions"] = []
        except Exception as e:
            write_log(f"Error loading json: {e}")


def save_data():
    """保存数据到JSON"""
    paths = get_file_paths()
    with data_lock:
        # 更新当前session的结束时间为当前时间
        # 转换为可读的日期时间字符串格式
        current_session_entry = {
            "start": datetime.datetime.fromtimestamp(current_session_start).strftime("%Y-%m-%d %H:%M:%S"),
            "end": datetime.datetime.fromtimestamp(time.time()).strftime("%Y-%m-%d %H:%M:%S")
        }

        # 复制一份数据用于保存，避免修改原始结构
        data_to_save = stats_data.copy()

        # 转换现有 sessions 为可读格式（如果还是旧格式）
        readable_sessions = []
        for session in data_to_save["sessions"]:
            if isinstance(session, list) and len(session) == 2:
                # 旧格式：[timestamp, timestamp]
                readable_sessions.append({
                    "start": datetime.datetime.fromtimestamp(session[0]).strftime("%Y-%m-%d %H:%M:%S"),
                    "end": datetime.datetime.fromtimestamp(session[1]).strftime("%Y-%m-%d %H:%M:%S")
                })
            elif isinstance(session, dict) and "start" in session and "end" in session:
                # 已经是新格式
                readable_sessions.append(session)

        readable_sessions.append(current_session_entry)
        data_to_save["sessions"] = readable_sessions

        try:
            with open(paths["json"], "w", encoding="utf-8") as f:
                json.dump(data_to_save, f, ensure_ascii=False, indent=4)
        except Exception as e:
            print(f"Save failed: {e}")


def format_duration(seconds):
    """格式化时间 H:M:S"""
    m, s = divmod(int(seconds), 60)
    h, m = divmod(m, 60)
    return f"{h}:{m}:{s}"


def generate_report():
    """生成汇总报告"""
    paths = get_file_paths()

    # 整合当前 session，转换为时间戳用于计算
    all_sessions_ts = []
    for session in stats_data["sessions"]:
        if isinstance(session, list) and len(session) == 2:
            # 旧格式：[timestamp, timestamp]
            all_sessions_ts.append(session)
        elif isinstance(session, dict) and "start" in session and "end" in session:
            # 新格式：{"start": "...", "end": "..."}
            start_ts = datetime.datetime.strptime(session["start"], "%Y-%m-%d %H:%M:%S").timestamp()
            end_ts = datetime.datetime.strptime(session["end"], "%Y-%m-%d %H:%M:%S").timestamp()
            all_sessions_ts.append([start_ts, end_ts])
    
    # 添加当前正在进行的 session
    all_sessions_ts.append([current_session_start, time.time()])

    if not all_sessions_ts:
        return

    # 1. 计算开机时间 (最早的 session start)
    first_boot_ts = min(s[0] for s in all_sessions_ts)
    first_boot_str = datetime.datetime.fromtimestamp(first_boot_ts).strftime("%Y-%m-%d %H:%M:%S")

    # 2. 计算关机时间 (最晚的 session end)
    last_shutdown_ts = max(s[1] for s in all_sessions_ts)
    last_shutdown_str = datetime.datetime.fromtimestamp(last_shutdown_ts).strftime("%Y-%m-%d %H:%M:%S")

    # 3. 共使用 (所有 session 差值之和)
    total_used_sec = sum(s[1] - s[0] for s in all_sessions_ts)

    # 4. 闲置
    idle_sec = stats_data["idle_seconds"]

    lines = []
    lines.append(f"开机时间:{first_boot_str}")
    lines.append(f"关机时间:{last_shutdown_str}")
    lines.append(f"共使用: {format_duration(total_used_sec)}")
    lines.append(f"闲置: {format_duration(idle_sec)}")
    lines.append("-" * 30)
    lines.append("应用程序使用详情 (按时长倒序):")

    # 5. 排序应用
    apps_list = []
    for app_name, app_info in stats_data["apps"].items():
        # 重新计算该APP总时长，确保数据一致性
        total_time = sum(app_info["titles"].values())
        apps_list.append((app_name, total_time, app_info["titles"]))

    # 倒序排列
    apps_list.sort(key=lambda x: x[1], reverse=True)

    for app_name, total_time, titles in apps_list:
        lines.append(f"{app_name} {format_duration(total_time)}")
        # 排序子节点 (Title)
        sorted_titles = sorted(titles.items(), key=lambda item: item[1], reverse=True)
        for title, t_time in sorted_titles:
            lines.append(f"    {title} {format_duration(t_time)}")

    try:
        with open(paths["report"], "w", encoding="utf-8") as f:
            f.write("\n".join(lines))
    except Exception as e:
        write_log(f"Error generating report: {e}")

# --- 核心监控逻辑 ---


def monitor_loop():
    global is_idle_status, current_date_str

    write_log("Service Started")

    while running:
        # 日期变更检查
        now_date = datetime.datetime.now().strftime("%Y%m%d")
        if now_date != current_date_str:
            save_data()
            generate_report()
            # 重置
            current_date_str = now_date
            stats_data["sessions"] = []
            stats_data["idle_seconds"] = 0
            stats_data["apps"] = {}
            # 更新全局session start
            global current_session_start
            current_session_start = time.time()
            write_log(f"Date changed to {now_date}, resetting stats.")

        # 获取白名单
        exempt_list = load_config()

        # 检测闲置
        idle_duration = get_idle_duration()
        app_name, title = get_active_window_info()

        # 判定逻辑：
        # 1. 如果闲置 > 60秒
        # 2. 检查当前活动应用是否在白名单
        # 3. 如果在白名单 -> 视为使用中 (不闲置)
        # 4. 如果不在白名单 -> 视为闲置

        is_app_exempt = False
        if app_name:
            # 检查应用名称是否在白名单中（支持部分匹配）
            for exempt_app in exempt_list:
                if exempt_app.lower() in app_name.lower() or app_name.lower() in exempt_app.lower():
                    is_app_exempt = True
                    break

        real_idle = False
        if idle_duration > 60 and not is_app_exempt:
            real_idle = True

        with data_lock:
            if real_idle:
                # 进入闲置或保持闲置
                if not is_idle_status:
                    write_log("Idle Start")
                    is_idle_status = True

                stats_data["idle_seconds"] += 1
            else:
                # 活动状态
                if is_idle_status:
                    write_log("Idle End")
                    is_idle_status = False

                # 记录应用时长
                if app_name and title:
                    if app_name not in stats_data["apps"]:
                        stats_data["apps"][app_name] = {"total": 0, "titles": {}}

                    if title not in stats_data["apps"][app_name]["titles"]:
                        stats_data["apps"][app_name]["titles"][title] = 0

                    # 增加 1秒 (采样间隔)
                    stats_data["apps"][app_name]["titles"][title] += 1
                    stats_data["apps"][app_name]["total"] += 1

        # 每隔 30 秒自动保存一次数据，防止崩坏
        if int(time.time()) % 30 == 0:
            save_data()

        time.sleep(1)

# --- 托盘图标 ---


def create_image():
    image = None
    # 优先尝试使用已有的自定义图标文件
    icon_candidates = [
        "statistics.ico",
        "statistics.png",
        "statistics.icns"  # macOS 图标格式
    ]
    base_path = Path(__file__).resolve()

    for candidate in icon_candidates:
        icon_path = base_path.with_name(candidate)
        if not icon_path.exists():
            continue
        try:
            loaded = Image.open(str(icon_path))
            if loaded.mode != "RGBA":
                loaded = loaded.convert("RGBA")
            image = loaded.resize((64, 64), Image.LANCZOS)
            break
        except Exception as e:
            image = None
            continue

    if image is None:
        image = Image.new('RGBA', (64, 64), (255, 255, 255, 0))
        dc = ImageDraw.Draw(image)
        dc.ellipse((8, 8, 56, 56), fill='#e74c3c', outline='white')
        dc.rectangle((26, 20, 38, 30), fill='#2ecc71')  # 叶子
    return image


def on_quit(icon, item):
    global running
    running = False
    icon.stop()

    # 退出处理
    write_log("Service Stopping (User Quit)")
    save_data()
    generate_report()
    sys.exit(0)


def open_stats_folder():
    """打开数据文件夹（macOS 版本）"""
    try:
        # macOS 使用 open 命令打开文件夹
        subprocess.run(['open', BASE_DIR], check=False)
    except Exception:
        pass


def setup_tray():
    image = create_image()
    menu = pystray.Menu(
        pystray.MenuItem("Open Stats Folder", lambda: open_stats_folder()),
        pystray.MenuItem("Exit", on_quit)
    )
    icon = pystray.Icon("AppTracker", image, "Usage Tracker", menu)
    icon.run()

# --- 主入口 ---


if __name__ == "__main__":
    # 检查 macOS 库是否可用
    if not MACOS_AVAILABLE:
        print("错误: 请先安装 macOS 所需的库：")
        print("  pip install pyobjc-framework-Quartz pyobjc-framework-AppKit")
        sys.exit(1)
    
    # 加载已有数据
    load_data()

    # 启动监控线程
    monitor_thread = threading.Thread(target=monitor_loop, daemon=True)
    monitor_thread.start()

    # 注册退出钩子 (处理关机等情况)
    def exit_handler():
        if running:
            write_log("System Shutdown or Process Terminated")
            save_data()
            generate_report()

    atexit.register(exit_handler)

    # 启动托盘 (阻塞主线程)
    setup_tray()


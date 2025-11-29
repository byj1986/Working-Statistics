import os
import sys
import time
import json
import psutil
import ctypes
import threading
import datetime
import win32gui
import win32process
import pystray
from PIL import Image, ImageDraw
import atexit
from pathlib import Path

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
    "sessions": [],  # 记录 [[start, end], [start, end]]
    "idle_seconds": 0,
    "apps": {}  # { "exe_name": { "total": 0, "titles": { "title_name": seconds } } }
}

# 当前Session开始时间
current_session_start = time.time()

# --- Windows API 定义 (用于检测闲置) ---


class LASTINPUTINFO(ctypes.Structure):
    _fields_ = [("cbSize", ctypes.c_uint), ("dwTime", ctypes.c_uint)]


def get_idle_duration():
    """获取系统闲置时间（秒）"""
    lii = LASTINPUTINFO()
    lii.cbSize = ctypes.sizeof(LASTINPUTINFO)
    if ctypes.windll.user32.GetLastInputInfo(ctypes.byref(lii)):
        millis = ctypes.windll.kernel32.GetTickCount() - lii.dwTime
        return millis / 1000.0
    return 0


def get_active_window_info():
    """获取当前活动窗口的 exe 名称和标题"""
    try:
        hwnd = win32gui.GetForegroundWindow()
        if not hwnd:
            return None, None

        _, pid = win32process.GetWindowThreadProcessId(hwnd)
        process = psutil.Process(pid)
        exe_name = process.name()
        title = win32gui.GetWindowText(hwnd)

        # 处理空标题的情况
        if not title.strip():
            title = "Unknown Title"

        return exe_name, title
    except Exception:
        return None, None

# --- 日志与文件操作 ---


def get_file_paths(date_str=None):
    if not date_str:
        date_str = datetime.datetime.now().strftime("%Y%m%d")
    return {
        "json": os.path.join(DATA_DIR, f"{date_str}.data.json"),
        "report": os.path.join(DATA_DIR, f"{date_str}.report.txt"),
        "log": os.path.join(DATA_DIR, f"{date_str}.log.txt")
    }


def write_log(message):
    """写入日志"""
    paths = get_file_paths()
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(paths["log"], "a", encoding="utf-8") as f:
        f.write(f"[{timestamp}] {message}\n")


def load_config():
    """读取白名单配置"""
    default_exempt = ["vlc.exe", "chrome.exe", "msedge.exe", "QQMusic.exe", "xmp.exe", "哔哩哔哩.exe"]
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                config = json.load(f)
                return config.get("idleExempt", default_exempt)
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
                # 确保 session 列表存在 (兼容旧数据)
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
    # 计算每个app的总时长（虽然json里有total，但为了保险重新sum一下或者直接用total）
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
        # 日期变更检查 (如果跨天了，需要重置数据或切换文件)
        # 这里简单处理：如果日期变了，保存旧报告，清空内存数据开始新的一天
        now_date = datetime.datetime.now().strftime("%Y%m%d")
        if now_date != current_date_str:
            save_data()
            generate_report()
            # 重置
            current_date_str = now_date
            stats_data["sessions"] = []
            stats_data["idle_seconds"] = 0
            stats_data["apps"] = {}
            # 更新全局session start，防止跨天统计混乱
            global current_session_start
            current_session_start = time.time()
            write_log(f"Date changed to {now_date}, resetting stats.")

        # 获取白名单
        exempt_list = load_config()

        # 检测闲置
        idle_duration = get_idle_duration()
        exe_name, title = get_active_window_info()

        # 判定逻辑：
        # 1. 如果闲置 > 60秒
        # 2. 检查当前活动窗口是否在白名单
        # 3. 如果在白名单 -> 视为使用中 (不闲置)
        # 4. 如果不在白名单 -> 视为闲置

        is_app_exempt = False
        if exe_name:
            # 简单匹配，比如 chrome.exe 在 list 中
            if exe_name in exempt_list:
                is_app_exempt = True

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
                if exe_name and title:
                    if exe_name not in stats_data["apps"]:
                        stats_data["apps"][exe_name] = {"total": 0, "titles": {}}

                    if title not in stats_data["apps"][exe_name]["titles"]:
                        stats_data["apps"][exe_name]["titles"][title] = 0

                    # 增加 1秒 (采样间隔)
                    stats_data["apps"][exe_name]["titles"][title] += 1
                    stats_data["apps"][exe_name]["total"] += 1

        # 每隔 30 秒自动保存一次数据，防止崩坏
        if int(time.time()) % 30 == 0:
            save_data()

        time.sleep(1)

# --- 托盘图标 ---


# --- 托盘 GUI ---
def create_image():
    image = None
    # 优先尝试使用已有的自定义图标文件
    icon_candidates = [
        "statistics.ico"
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


def setup_tray():
    image = create_image()
    menu = pystray.Menu(
        pystray.MenuItem("Open Stats Folder", lambda: os.startfile(BASE_DIR)),
        pystray.MenuItem("Exit", on_quit)
    )
    icon = pystray.Icon("AppTracker", image, "Usage Tracker", menu)
    icon.run()

# --- 主入口 ---


if __name__ == "__main__":
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

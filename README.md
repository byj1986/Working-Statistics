# Statistics - Windows 应用程序使用统计工具

一个基于 Python 的 Windows 应用程序使用情况追踪和统计分析工具，可以帮助你了解自己的电脑使用习惯。

## 📋 功能特性

- **实时监控**: 持续监控系统前台应用程序的使用情况
- **闲置检测**: 智能检测系统闲置状态（支持白名单应用）
- **数据可视化**: 
  - 每日使用统计（饼图、应用列表）
  - 过去7天使用趋势（柱状图、应用占比）
- **Web 界面**: 通过浏览器查看美观的统计报告
- **自动保存**: 每30秒自动保存数据，防止数据丢失
- **系统托盘**: 后台运行，不占用任务栏空间
- **开机自启**: 支持开机自动启动

## 🛠️ 技术栈

- **后端**: Python 3
- **前端**: HTML + Chart.js
- **Windows API**: 用于窗口监控和闲置检测
- **数据存储**: JSON 格式

## 📦 依赖库

```bash
pip install psutil pystray pillow pywin32
```

### 依赖说明

- `psutil`: 进程和系统信息
- `pystray`: 系统托盘图标
- `pillow`: 图像处理（托盘图标）
- `pywin32`: Windows API 调用

## 🚀 快速开始

### 1. 安装依赖

```bash
pip install psutil pystray pillow pywin32
```

### 2. 配置说明

程序会自动使用脚本所在目录作为工作目录，无需手动配置路径：
- `app_tracker.py` 会自动使用脚本所在目录
- `auto_start.bat` 会自动使用批处理文件所在目录
- 数据文件会自动保存在 `Data` 子目录下

### 3. 启动监控服务

```bash
pythonw app_tracker.py
```

或者双击 `auto_start.bat`（会以后台方式启动）

### 4. 启动 Web 服务器

```bash
python server.py
```

或者双击 `start_server.bat`

### 5. 访问 Web 界面

在浏览器中打开：
- **每日统计**: http://localhost:8000/daily.html
- **每周统计**: http://localhost:8000/weekly.html

## 📁 项目结构

```
Statistics/
├── app_tracker.py              # 主监控程序
├── server.py                   # Web 服务器
├── daily.html                  # 每日统计页面
├── weekly.html                 # 每周统计页面
├── statistics.configuration.json  # 配置文件（闲置白名单）
├── statistics.ico              # 托盘图标
├── auto_start.bat              # 自动启动脚本
├── start_server.bat            # 服务器启动脚本
├── README.md                   # 项目说明文档
└── Data/                       # 数据目录
    ├── YYYYMMDD.data.json      # 每日数据文件
    ├── YYYYMMDD.log.txt        # 每日日志文件
    └── YYYYMMDD.report.txt     # 每日报告文件（文本格式）
```

## ⚙️ 配置说明

### 闲置检测白名单

编辑 `statistics.configuration.json`：

```json
{
    "idleExempt": [
        "vlc.exe",
        "chrome.exe",
        "msedge.exe",
        "QQMusic.exe",
        "xmp.exe",
        "哔哩哔哩.exe"
    ]
}
```

在白名单中的应用即使系统闲置超过60秒，也不会被计入闲置时间。例如，看视频或听音乐时不会被认为是闲置。

## 📊 数据格式

### Sessions 格式

```json
{
    "sessions": [
        {
            "start": "2025-11-29 21:03:54",
            "end": "2025-11-29 22:10:49"
        }
    ],
    "idle_seconds": 123,
    "apps": {
        "chrome.exe": {
            "total": 3600,
            "titles": {
                "新标签页 - Google Chrome": 1800,
                "GitHub - Google Chrome": 1800
            }
        }
    }
}
```

## 🌐 API 接口

### 获取所有可用日期

```
GET /api/dates
```

返回：`["20251129", "20251128", ...]` （倒序，最新在前）

### 获取指定日期的数据

```
GET /api/data/YYYYMMDD
```

示例：`GET /api/data/20251129`

返回：指定日期的统计数据 JSON，如果日期不存在则返回空数据。

## 🎯 功能说明

### 监控逻辑

1. **采样频率**: 每秒检查一次当前活动窗口
2. **闲置判定**: 
   - 系统闲置超过 60 秒
   - 且当前活动应用不在白名单中
3. **数据保存**: 
   - 每 30 秒自动保存
   - 程序退出时保存
   - 日期变更时保存并生成报告

### 统计数据

- **系统运行时长**: 所有 session 的总时长
- **有效使用时间**: 运行时长 - 闲置时长
- **闲置时长**: 检测到的闲置时间总和
- **应用使用详情**: 每个应用的总使用时长和窗口标题列表

## 🔧 开机自启动设置

### 方法一：使用启动文件夹

1. 按 `Win + R`，输入 `shell:startup`，回车
2. 将 `auto_start.bat` 的快捷方式放入启动文件夹
3. **无需修改路径**：`auto_start.bat` 会自动使用其所在目录

### 方法二：任务计划程序

1. 打开"任务计划程序"
2. 创建基本任务
3. 触发器：当计算机启动时
4. 操作：启动程序 `pythonw`，参数：`app_tracker.py` 的完整路径
5. 起始于：项目目录路径

## 📝 使用说明

### 查看每日统计

1. 启动服务器：`python server.py`
2. 访问：http://localhost:8000/daily.html
3. 使用日期选择器选择要查看的日期
4. 查看：
   - 系统运行时长
   - 有效使用时间
   - 闲置时长
   - 应用程序使用列表
   - 时间分配饼图

### 查看每周统计

1. 访问：http://localhost:8000/weekly.html
2. 选择结束日期（默认最新日期）
3. 查看过去7天的：
   - 总开机时长
   - 总有效使用时间
   - 总闲置时间
   - 每日趋势图
   - 应用使用占比

### 系统托盘

- 右键点击系统托盘图标
- 选择 "Open Stats Folder" 打开数据文件夹
- 选择 "Exit" 退出程序

## ⚠️ 注意事项

1. **数据文件**: 数据文件存储在 `Data` 目录下，以日期命名（YYYYMMDD），每天一个文件
2. **直接访问**: 不允许直接访问 `.data.json` 文件，必须通过 API 接口
3. **端口占用**: 默认使用 8000 端口，如果被占用请修改 `server.py` 中的 `PORT` 变量
4. **性能影响**: 程序资源占用极低，适合长期运行
5. **Windows 专用**: 本程序仅支持 Windows 系统

## 🐛 故障排除

### 服务器无法启动

- 检查端口是否被占用：`netstat -ano | findstr :8000`
- 停止占用进程或修改端口号

### 无法访问网页

- 确认服务器已启动
- 检查防火墙设置
- 尝试使用 `127.0.0.1` 而不是 `localhost`

### 数据未更新

- 检查 `app_tracker.py` 是否正在运行
- 查看日志文件了解错误信息
- 确认程序有写入权限

### 显示 NaN 小时 NaN 分

- 检查数据文件格式是否正确
- 确保 sessions 使用新的对象格式

## 📄 许可证

本项目仅供个人使用和学习。

## 🤝 贡献

欢迎提交 Issue 和 Pull Request！

## 📧 联系方式

如有问题或建议，请提交 Issue。

---

**提示**: 定期备份 `Data` 目录下的 `*.data.json` 文件以保留历史数据。


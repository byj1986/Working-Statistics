import http.server
import socketserver
import json
import os
import re
import sys
import socket
from urllib.parse import urlparse, parse_qs

PORT = 8000
DIRECTORY = "."  # 将在 main 中更新为 Data 目录

class StatsHandler(http.server.SimpleHTTPRequestHandler):
    def end_headers(self):
        # 添加 CORS 头，允许跨域访问
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        super().end_headers()
    
    def do_OPTIONS(self):
        # 处理预检请求
        self.send_response(200)
        self.end_headers()
    
    def log_message(self, format, *args):
        # 自定义日志格式，输出到控制台
        print(f"[{self.address_string()}] {format % args}")
    
    def do_GET(self):
        try:
            # 解析路径和查询参数
            parsed_path = urlparse(self.path)
            path = parsed_path.path
            query_params = parse_qs(parsed_path.query)
            
            # API: 获取所有 .data.json 文件的日期列表
            if path == '/api/dates':
                try:
                    files = [f for f in os.listdir(DIRECTORY) if f.endswith('.data.json')]
                    # 提取 YYYYMMDD
                    dates = []
                    for f in files:
                        m = re.match(r"(\d{8})\.data\.json", f)
                        if m:
                            dates.append(m.group(1))
                    dates.sort(reverse=True) # 最近的日期在前
                    
                    self.send_response(200)
                    self.send_header('Content-type', 'application/json; charset=utf-8')
                    self.end_headers()
                    self.wfile.write(json.dumps(dates, ensure_ascii=False).encode('utf-8'))
                    return
                except Exception as e:
                    print(f"Error in /api/dates: {e}", file=sys.stderr)
                    self.send_response(500)
                    self.send_header('Content-type', 'application/json; charset=utf-8')
                    self.end_headers()
                    self.wfile.write(json.dumps({"error": str(e)}, ensure_ascii=False).encode('utf-8'))
                    return
            
            # API: 获取指定日期的数据
            elif path.startswith('/api/data/'):
                date_str = path.replace('/api/data/', '').rstrip('/')
                # 验证日期格式 (YYYYMMDD)
                if not re.match(r'^\d{8}$', date_str):
                    self.send_response(400)
                    self.send_header('Content-type', 'application/json; charset=utf-8')
                    self.end_headers()
                    self.wfile.write(json.dumps({"error": "Invalid date format. Use YYYYMMDD"}, ensure_ascii=False).encode('utf-8'))
                    return
                
                file_path = os.path.join(DIRECTORY, f"{date_str}.data.json")
                if os.path.exists(file_path):
                    try:
                        with open(file_path, 'r', encoding='utf-8') as f:
                            data = json.load(f)
                        self.send_response(200)
                        self.send_header('Content-type', 'application/json; charset=utf-8')
                        self.end_headers()
                        self.wfile.write(json.dumps(data, ensure_ascii=False).encode('utf-8'))
                        return
                    except Exception as e:
                        print(f"Error reading {file_path}: {e}", file=sys.stderr)
                        self.send_response(500)
                        self.send_header('Content-type', 'application/json; charset=utf-8')
                        self.end_headers()
                        self.wfile.write(json.dumps({"error": str(e)}, ensure_ascii=False).encode('utf-8'))
                        return
                else:
                    # 日期不存在，返回空数据而不是错误
                    self.send_response(200)
                    self.send_header('Content-type', 'application/json; charset=utf-8')
                    self.end_headers()
                    empty_data = {"sessions": [], "idle_seconds": 0, "apps": {}}
                    self.wfile.write(json.dumps(empty_data, ensure_ascii=False).encode('utf-8'))
                    return
            
            # 阻止直接访问 .data.json 文件
            if path.endswith('.data.json'):
                self.send_response(403)
                self.send_header('Content-type', 'application/json; charset=utf-8')
                self.end_headers()
                self.wfile.write(json.dumps({"error": "直接访问数据文件已被禁用，请使用 /api/data/YYYYMMDD 接口"}, ensure_ascii=False).encode('utf-8'))
                return
            
            # 默认行为：提供静态文件 (HTML, JSON)
            # 处理根路径，重定向到 daily.html
            if path == '/' or path == '/index.html':
                self.path = '/daily.html'
            
            # 调用父类方法处理静态文件
            super().do_GET()
            
        except Exception as e:
            print(f"Unexpected error in do_GET: {e}", file=sys.stderr)
            import traceback
            traceback.print_exc()
            self.send_response(500)
            self.end_headers()
            self.wfile.write(f"Internal Server Error: {str(e)}".encode('utf-8'))

if __name__ == "__main__":
    # 切换到脚本所在目录
    script_dir = os.path.dirname(os.path.abspath(__file__))
    os.chdir(script_dir)
    # 数据文件在 Data 目录下
    DATA_DIR = os.path.join(script_dir, "Data")
    DIRECTORY = DATA_DIR
    # 确保 Data 目录存在
    if not os.path.exists(DATA_DIR):
        os.makedirs(DATA_DIR)
    
    # 允许复用端口，防止重启时报错
    socketserver.TCPServer.allow_reuse_address = True
    
    try:
        # 使用 0.0.0.0 绑定所有网络接口，这样可以从局域网访问
        with socketserver.TCPServer(("0.0.0.0", PORT), StatsHandler) as httpd:
            host = "localhost"
            print("=" * 60)
            print(f"服务器已启动！")
            print(f"本地访问: http://localhost:{PORT}")
            print(f"      或: http://127.0.0.1:{PORT}")
            print(f"局域网访问: http://{socket.gethostbyname(socket.gethostname())}:{PORT}")
            print(f"\n访问页面:")
            print(f"  - http://localhost:{PORT}/daily.html")
            print(f"  - http://localhost:{PORT}/week.html")
            print(f"\nAPI 接口:")
            print(f"  - http://localhost:{PORT}/api/dates")
            print(f"  - http://localhost:{PORT}/api/data/YYYYMMDD")
            print("=" * 60)
            print("按 Ctrl+C 停止服务器")
            httpd.serve_forever()
    except OSError as e:
        if "Address already in use" in str(e) or "只允许使用一次" in str(e):
            print(f"错误: 端口 {PORT} 已被占用！")
            print("请关闭占用该端口的程序，或修改 PORT 变量使用其他端口。")
            print("\n检查占用端口的进程:")
            print(f"  Windows: netstat -ano | findstr :{PORT}")
            print(f"  然后使用: taskkill /PID <进程ID> /F")
        else:
            print(f"启动服务器时出错: {e}")
        sys.exit(1)
    except KeyboardInterrupt:
        print("\n\n服务器已停止")
    except Exception as e:
        print(f"未预期的错误: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)
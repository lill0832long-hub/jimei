"""AI 财务系统 V5.1 — 后台启动器"""
import subprocess
import sys
import os
import time

PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
PYTHON = r"C:\Users\Administrator\AppData\Local\Programs\Python\Python312\python.exe"
APP = os.path.join(PROJECT_DIR, "app.py")
LOG = os.path.join(PROJECT_DIR, "server_output.log")

def main():
    """启动服务器并保持运行"""
    ts = time.strftime('%Y-%m-%d %H:%M:%S')
    with open(LOG, "w", encoding="utf-8") as log:
        log.write(f"Starting server at {ts}\n")
        log.flush()
        proc = subprocess.Popen(
            [PYTHON, APP],
            cwd=PROJECT_DIR,
            stdout=log,
            stderr=log,
        )
        log.write(f"Server PID: {proc.pid}\n")
        log.flush()
        try:
            proc.wait()
        except KeyboardInterrupt:
            proc.terminate()
        log.write(f"Server exited with code {proc.returncode}\n")

if __name__ == "__main__":
    main()

"""AI 财务系统 V5.1 — 启动脚本
自动修复数据库权限后启动服务器，防止只读崩溃。
"""
import subprocess
import sys
import os
import time

PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
PYTHON = sys.executable
APP = os.path.join(PROJECT_DIR, "app.py")
DB = os.path.join(PROJECT_DIR, "finance_v2.db")
PORT = 8090


def fix_db_permissions():
    """修复数据库文件权限（防止 readonly 崩溃）"""
    for suffix in ["", "-wal", "-shm"]:
        db_file = DB + suffix
        if os.path.exists(db_file):
            try:
                os.chmod(db_file, 0o666)
            except Exception:
                pass
    # Windows: use icacls
    try:
        subprocess.run(
            ["icacls", DB, "/grant", "Everyone:F", "/T"],
            capture_output=True, creationflags=0x08000000  # CREATE_NO_WINDOW
        )
    except Exception:
        pass


def kill_existing():
    """杀掉占用端口的旧进程"""
    try:
        result = subprocess.run(
            ["netstat", "-ano"], capture_output=True, text=True,
            creationflags=0x08000000
        )
        for line in result.stdout.split("\n"):
            if ":%d" % PORT in line and "LISTENING" in line:
                pid = line.strip().split()[-1]
                subprocess.run(["taskkill", "/F", "/PID", pid],
                               capture_output=True, creationflags=0x08000000)
                time.sleep(1)
    except Exception:
        pass


def main():
    print("=" * 50)
    print("  AI 财务系统 V5.1 启动器")
    print("=" * 50)

    print("[1/3] 修复数据库权限...")
    fix_db_permissions()
    print("  Done.")

    print("[2/3] 清理旧进程...")
    kill_existing()
    print("  Done.")

    print("[3/3] 启动服务器...")
    print("  地址: http://localhost:%d" % PORT)
    print("  按 Ctrl+C 停止服务器")
    print("=" * 50)

    proc = subprocess.Popen([PYTHON, APP], cwd=PROJECT_DIR)
    try:
        proc.wait()
    except KeyboardInterrupt:
        print("\n正在停止服务器...")
        proc.terminate()
        proc.wait(timeout=5)
        print("服务器已停止。")


if __name__ == "__main__":
    main()

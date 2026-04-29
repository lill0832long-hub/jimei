"""自动备份服务"""
import os, threading, logging, json as _json
from datetime import datetime
from database_v3 import get_ledgers, backup_ledger_to_json

_AUTO_BACKUP_ENABLED = True
_AUTO_BACKUP_INTERVAL_HOURS = 24
_AUTO_BACKUP_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "backups")
_BACKUP_LOCK = threading.Lock()
_backup_status = {"last_backup": None, "last_status": "未启动", "total_backups": 0, "errors": []}


def _auto_backup_worker():
    import time
    logger = logging.getLogger("auto_backup")
    logger.setLevel(logging.INFO)
    handler = logging.FileHandler(os.path.join(os.path.dirname(os.path.dirname(__file__)), "backup.log"))
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    logger.addHandler(handler)

    while _AUTO_BACKUP_ENABLED:
        try:
            with _BACKUP_LOCK:
                ledgers = get_ledgers()
                for ledger in ledgers:
                    try:
                        fpath = backup_ledger_to_json(ledger["id"], _AUTO_BACKUP_DIR)
                        logger.info(f"✅ 账套 {ledger['id']} 备份成功: {fpath}")
                    except Exception as e:
                        err_msg = f"账套 {ledger['id']} 备份失败: {e}"
                        logger.error(err_msg)
                        _backup_status["errors"].append({"time": datetime.now().isoformat(), "error": err_msg})
                        if len(_backup_status["errors"]) > 20:
                            _backup_status["errors"] = _backup_status["errors"][-20:]
                _backup_status["last_backup"] = datetime.now().isoformat()
                _backup_status["last_status"] = "成功"
                _backup_status["total_backups"] += len(ledgers)
        except Exception as e:
            _backup_status["last_status"] = f"失败: {e}"
            logger.error(f"备份异常: {e}")
        for _ in range(_AUTO_BACKUP_INTERVAL_HOURS * 3600):
            if not _AUTO_BACKUP_ENABLED:
                break
            time.sleep(1)


def start_auto_backup():
    t = threading.Thread(target=_auto_backup_worker, daemon=True, name="auto-backup")
    t.start()
    return t

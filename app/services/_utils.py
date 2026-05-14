"""服务层公共工具函数"""
import asyncio
import concurrent.futures


def run_async(coro):
    """统一的 async 桥接函数
    
    在同步上下文中运行异步协程。
    如果当前已有事件循环（如 NiceGUI 的 uvicorn），则使用线程池。
    """
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None
    if loop and loop.is_running():
        with concurrent.futures.ThreadPoolExecutor() as pool:
            return pool.submit(asyncio.run, coro).result()
    return asyncio.run(coro)


def to_dict(obj):
    """将 SQLAlchemy 模型实例转换为 dict
    
    支持单个对象、列表、字典透传。
    """
    if obj is None:
        return None
    if isinstance(obj, (list, tuple)):
        return [to_dict(item) for item in obj]
    if hasattr(obj, "__table__"):
        return {c.name: getattr(obj, c.name) for c in obj.__table__.columns}
    if isinstance(obj, dict):
        return obj
    return obj

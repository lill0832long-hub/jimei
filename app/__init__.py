# app package
# 注意：render_page 不能在此导入（循环依赖），由 app.py 启动时注入
# ui_helpers.py 通过 importlib 动态加载 app.py 获取 render_page

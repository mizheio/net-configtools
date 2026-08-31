"""模块包：每个模块 = 一个生成函数（纯净，不碰界面）+ 一个界面页（gui.py 里实现）

新增模块三步：
1. 在本目录新建 xxx.py，写 generate(params) -> str
2. 在 gui.py 里写 XxxPage 类（collect / validate / render）
3. 在 gui.py 的 App 里 add 进 Notebook
"""

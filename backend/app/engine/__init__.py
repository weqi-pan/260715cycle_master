"""图引擎模块。

负责从数据库加载故事图、条件求值、游戏状态推进和特殊路由处理。

Modules:
    graph          — GraphBundle / ChoiceData 运行时对象 + GraphLoader
    condition_eval — 条件表达式解析与求值
    engine         — GameEngine 核心（9 步 process_choice 流水线）
    special_router — 特殊路由（K 跃迁枢纽）
"""

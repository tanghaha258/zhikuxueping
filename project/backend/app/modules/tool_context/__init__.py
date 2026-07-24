"""工具上下文链接模块（Task 8）。

依据 spec 第 7 节与计划 Task 8：
- 独立工具（备课/资源/试卷/AI 产出等）关联到项目时，通过 ToolContextLink 建立一次引用，
  不复制业务资产本体。
- 项目模式必须提供 project_id 与 placement；独立模式不得伪造项目 ID。
- 跨校项目关联由 policy 在写入前校验并返回 403。
- 取消关联只删除引用，不删除资产或文件。

模块组成：
- ``policy``：上下文校验与跨校授权。
- ``repository``：ToolContextLink 持久化（不提交事务，由服务层控制）。
- ``service``：link_asset / unlink_asset / list_* 高层编排。
"""

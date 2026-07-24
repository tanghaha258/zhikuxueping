"""项目学情诊断授权（Task 6）。

复用项目读写授权策略（app.modules.projects.policy），确保所有查询和操作带
学校作用域：跨教师、跨学校访问由 ensure_can_read / ensure_can_manage 统一拒绝。
归档项目写操作（生成/确认诊断）由 ensure_not_archived 拒绝（409）。
"""
from __future__ import annotations

from app.modules.projects.policy import (  # noqa: F401 — re-export for service
    ensure_can_manage,
    ensure_can_read,
    ensure_not_archived,
)

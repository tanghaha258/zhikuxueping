"""项目校验门面。

将项目设计领域的完整性校验（核心学科、贡献说明、真实问题最终成果、
目标-指标-证据可追踪）以 `projects.validators` 的稳定路径对外暴露，
供 projects 模块内部及其他调用方使用，避免直接深入 `project_designs` 内部。

实际校验逻辑由 `app.modules.project_designs.validators` 实现，本模块只做转发。
"""
from __future__ import annotations

from app.modules.project_designs.validators import (
    ValidationIssue,
    ValidationResult,
    validate_activation,
    validate_contribution_uniqueness,
)

__all__ = [
    "ValidationIssue",
    "ValidationResult",
    "validate_activation",
    "validate_contribution_uniqueness",
]

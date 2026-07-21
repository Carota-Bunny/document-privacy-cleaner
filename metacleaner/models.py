# Copyright (C) 2026 Carota-Bunny
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path


class CleanMode(str, Enum):
    PERSONAL = "personal"
    ALL = "all"


@dataclass(frozen=True)
class MetadataItem:
    group: str
    name: str
    value: str
    personal: bool = True


@dataclass
class InspectionResult:
    path: Path
    category: str
    supported: bool
    items: list[MetadataItem] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    signed: bool = False
    encrypted: bool = False

    @property
    def personal_count(self) -> int:
        return sum(1 for item in self.items if item.personal)

    @property
    def summary(self) -> str:
        if not self.supported:
            return "不支持"
        if self.encrypted:
            return "已加密"
        if self.signed:
            return "含数字签名"
        if not self.items:
            return "未发现已知元数据"
        return f"{len(self.items)} 项（个人信息 {self.personal_count} 项）"


@dataclass
class CleanOptions:
    mode: CleanMode = CleanMode.PERSONAL
    anonymize_reviewers: bool = True
    remove_thumbnail: bool = True
    verify_after_clean: bool = True


@dataclass
class CleanResult:
    source: Path
    output: Path | None
    success: bool
    removed_count: int = 0
    residual_items: list[MetadataItem] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    error: str = ""

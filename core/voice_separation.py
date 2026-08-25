# -*- coding: utf-8 -*-
"""S5 双声部分离 — 编辑声部容器化（flag 门控，默认关）。

把散落正文的『风险提示：…』『数据说明：…』独立段落搬运至文末统一
『口径与风险说明』块，使分析师声部（判断/论证）与编辑声部（合规/口径）
结构分离——风格指纹的声部纯度措施。

红线：只搬整段（段落以标记开头），不改写任何句子。
"""

from __future__ import annotations

import re

_MARK = re.compile(r"^(?:风险提示|数据说明|口径说明)\s*[:：]\s*", re.M)


def separate_voices(text: str) -> str:
    if not text or "风险提示" not in text and "数据说明" not in text and "口径说明" not in text:
        return text
    paras = text.split("\n\n")
    keep, moved = [], []
    for p in paras:
        if _MARK.match(p.strip()):
            moved.append(p.strip())
        else:
            keep.append(p)
    if not moved:
        return text
    block = "\n\n".join(["## 口径与风险说明", ""] + moved)
    return "\n\n".join(keep).rstrip() + "\n\n" + block + "\n"

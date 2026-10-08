# -*- coding: utf-8 -*-
"""艾宾浩斯复习排期 + 宽松判定"""
import re
import sqlite3
import threading
from datetime import date, timedelta
from pathlib import Path

DICT_DB = Path(__file__).resolve().parent.parent / "data" / "ecdict.sqlite"
# 记忆间隔（天）：stage 0→1→2→3→4→5；stage>=5 视为长期掌握
INTERVALS = [1, 2, 4, 7, 15]

_tls = threading.local()


def _conn():
    conn = getattr(_tls, "conn", None)
    if conn is None:
        conn = sqlite3.connect(DICT_DB)
        conn.row_factory = sqlite3.Row
        _tls.conn = conn
    return conn


def lemma_of(form: str):
    try:
        row = _conn().execute("SELECT lemma FROM lemmas WHERE form=?",
                              (form.lower(),)).fetchone()
        return row["lemma"] if row else None
    except Exception:
        return None


def next_date(stage: int, result: str) -> str:
    """根据阶段与反馈计算下次复习日期"""
    today = date.today()
    if result == "forget":
        return (today + timedelta(days=1)).isoformat()
    if result == "fuzzy":
        # 模糊记得：短周期 1 天再巩固
        return (today + timedelta(days=1)).isoformat()
    # remember：按艾宾浩斯节奏递增
    idx = min(stage, len(INTERVALS) - 1)
    return (today + timedelta(days=INTERVALS[idx])).isoformat()


def schedule(stage: int, result: str):
    """返回 (new_stage, next_date_str, graduated_bool)；
    graduated=True 表示已达到长期掌握上限，应标记 mastered"""
    if result == "remember":
        new_stage = min(stage + 1, len(INTERVALS))
    elif result == "fuzzy":
        new_stage = stage
    else:
        new_stage = 0
    graduated = (result == "remember" and new_stage >= len(INTERVALS))
    return new_stage, next_date(stage, result), graduated


def _norm_word(w: str) -> str:
    return re.sub(r"[^a-z']", "", w.lower())


def word_matches(typed: str, target: str) -> bool:
    """单词宽松判定：忽略大小写/标点/常见词形变化"""
    t, g = _norm_word(typed), _norm_word(target)
    if not t:
        return False
    if t == g:
        return True
    # 词形还原比对
    if lemma_of(t) == g or lemma_of(g) == t:
        return True
    if t and g and lemma_of(t) and lemma_of(t) == lemma_of(g):
        return True
    # 简单后缀规则
    stems = {g, g[:-1] if g.endswith("e") else g, g + "e"}
    if t in stems:
        return True
    return False


def _tokens(s: str):
    return [_norm_word(t) for t in re.findall(r"[A-Za-z']+", s) if _norm_word(t)]


def sentence_matches(typed: str, target: str) -> float:
    """句子宽松判定：返回得分 0~1（逐词比对，忽略大小写/标点/词形变化）"""
    tt, tg = _tokens(typed), _tokens(target)
    if not tg:
        return 0.0
    if not tt:
        return 0.0
    # 贪心对齐：每个目标词在作答序列中找第一个匹配
    used = [False] * len(tt)
    hit = 0
    for g in tg:
        for i, t in enumerate(tt):
            if not used[i] and word_matches(t, g):
                used[i] = True
                hit += 1
                break
    return hit / len(tg)

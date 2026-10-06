# -*- coding: utf-8 -*-
"""词汇过滤：分词 → ECDICT 查询 → 考试标签过滤

过滤规则（用户需求）：
- 小学初中简单词（zk 标签）、代词/冠词/介词等功能词、普通日常物品词 → 不收录
- 仅收录 四级/六级/考研/雅思/托福 词汇
- 仅四级级别且词频过高（过于常见的日常词）→ 不收录
"""
import re
import sqlite3
import threading
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
DICT_DB = BASE / "data" / "ecdict.sqlite"

# 考试标签 → 中文
TAG_CN = {
    "cet4": "四级", "cet6": "六级", "ky": "考研",
    "ielts": "雅思", "toefl": "托福", "gre": "GRE",
    "gk": "高考", "zk": "中考",
}
EXAM_TAGS = {"cet4", "cet6", "ky", "ielts", "toefl"}
HIGH_EXAM = {"cet6", "ky", "ielts", "toefl", "gre"}

# 功能词停用表（代词/冠词/介词/助动词/系动词/连词/高频副词）
STOPWORDS = {
    "i", "you", "he", "she", "it", "we", "they", "me", "him", "her", "us",
    "them", "my", "your", "his", "its", "our", "their", "mine", "yours",
    "this", "that", "these", "those", "the", "a", "an", "of", "to", "in",
    "on", "at", "for", "with", "by", "from", "as", "into", "onto", "about",
    "is", "are", "was", "were", "be", "been", "being", "am", "do", "does",
    "did", "done", "doing", "have", "has", "had", "having", "will", "would",
    "shall", "should", "can", "could", "may", "might", "must", "not", "no",
    "nor", "so", "if", "than", "then", "and", "or", "but", "because",
    "though", "although", "while", "when", "where", "what", "which", "who",
    "whom", "whose", "how", "why", "there", "here", "all", "any", "some",
    "such", "own", "same", "s", "t", "ll", "re", "ve", "d", "m", "o",
    "up", "down", "out", "off", "over", "under", "again", "once", "only",
    "very", "just", "also", "too", "now", "ever", "never", "always",
}

_tls = threading.local()


def _dict_conn():
    conn = getattr(_tls, "conn", None)
    if conn is None:
        if not DICT_DB.exists():
            raise FileNotFoundError(
                f"词库未找到：{DICT_DB} 不存在"
            )
        conn = sqlite3.connect(DICT_DB)
        conn.row_factory = sqlite3.Row
        _tls.conn = conn
    return conn


def lookup(word: str):
    """查 ECDICT，返回 row 或 None"""
    try:
        return _dict_conn().execute(
            "SELECT word, phonetic, translation, tag, exchange, bnc, frq "
            "FROM dict WHERE word=?", (word.lower(),)
        ).fetchone()
    except Exception:
        return None


def lemma_of(token: str):
    """变形 → 原形"""
    try:
        row = _dict_conn().execute(
            "SELECT lemma FROM lemmas WHERE form=?", (token.lower(),)
        ).fetchone()
        return row["lemma"] if row else None
    except Exception:
        return None


def tokenize(text: str):
    """歌词分词，返回去重后的小写词表（保留出现顺序与行号信息另行处理）"""
    tokens = re.findall(r"[A-Za-z][A-Za-z'\-]*", text)
    return [t.lower().strip("'-") for t in tokens if len(t) > 1]


def word_sentences(lyrics: str):
    """每行拆句，返回 [(line_no, line_text, sentence)] 用于定位原句"""
    out = []
    for i, line in enumerate(lyrics.splitlines(), 1):
        line = line.strip()
        if not line:
            continue
        # 歌词行通常本身就是一句，粗粒度按行取
        out.append((i, line, line))
    return out


def _freq_rank(row) -> int:
    vals = []
    for k in ("bnc", "frq"):
        v = row[k] if k in row.keys() else None
        try:
            v = int(v)
            if v > 0:
                vals.append(v)
        except (TypeError, ValueError):
            pass
    return min(vals) if vals else 10**9


def _parse_exchange(exchange: str) -> str:
    """'p:went/d:gone/i:going/3:goes' → '过去式 went；过去分词 gone；现在分词 going；三单 goes'"""
    names = {"p": "过去式", "d": "过去分词", "i": "现在分词", "3": "三单",
             "r": "比较级", "t": "最高级", "s": "复数", "0": "原形"}
    if not exchange:
        return ""
    parts = []
    for item in exchange.split("/"):
        if ":" in item:
            k, v = item.split(":", 1)
            if k in names and v:
                parts.append(f"{names[k]} {v}")
    return "；".join(parts)


def classify(token: str) -> dict:
    """判定一个 token 是否收录，返回分类信息"""
    result = {
        "word": token, "lemma": token, "included": False, "reason": "",
        "scope": "", "translation": "", "phonetic": "", "exchange": "",
        "tags": [],
    }
    if token in STOPWORDS or len(token) < 2:
        result["reason"] = "功能词"
        return result

    row = lookup(token)
    word = token
    if row is None:
        lemma = lemma_of(token)
        if lemma and lemma != token:
            row = lookup(lemma)
            word = lemma
        elif lemma is None:
            # 兜底规则变形
            for cand in (token.rstrip("s"), token[:-3] + "ing"
                         if token.endswith("ing") else token,
                         token[:-2] if token.endswith("ed") else token):
                if cand and lookup(cand):
                    row, word = lookup(cand), cand
                    break
    if row is None:
        result["reason"] = "词库未收录"
        return result

    word = row["word"]
    result["word"] = word
    tags = (row["tag"] or "").split()
    result["tags"] = tags

    if "zk" in tags:
        result["reason"] = "初中及以下简单词"
        return result
    if token in STOPWORDS:
        result["reason"] = "功能词"
        return result

    exam = EXAM_TAGS & set(tags)
    if not exam:
        result["reason"] = "非备考范围词汇"
        return result

    # 仅四级/高考级别且过于常见（词频前2500）→ 跳过
    if not (HIGH_EXAM & set(tags)) and _freq_rank(row) < 2500:
        result["reason"] = "过于常见的日常词"
        return result

    scope = "/".join(TAG_CN[t] for t in tags if t in EXAM_TAGS)
    result.update({
        "included": True,
        "reason": "备考词汇",
        "scope": scope,
        "translation": (row["translation"] or "").split("\\n")[0][:80],
        "phonetic": row["phonetic"] or "",
        "exchange": _parse_exchange(row["exchange"]),
    })
    return result


def filter_lyrics(lyrics: str):
    """主入口：返回 (candidates, skipped_stats)

    candidates: [{word, scope, translation, phonetic, exchange, tags,
                  sentence, line_no}]（同词只留第一次出现）
    skipped_stats: {原因: 数量}
    """
    candidates, seen = [], {}
    stats: dict = {}
    for line_no, line, _sentence in word_sentences(lyrics):
        for token in tokenize(line):
            info = classify(token)
            if info["included"]:
                if info["word"] in seen:
                    continue
                seen[info["word"]] = True
                candidates.append({
                    "word": info["word"],
                    "scope": info["scope"],
                    "translation": info["translation"],
                    "phonetic": info["phonetic"],
                    "exchange": info["exchange"],
                    "tags": info["tags"],
                    "sentence": line,
                    "line_no": line_no,
                })
            else:
                stats[info["reason"]] = stats.get(info["reason"], 0) + 1
    return candidates, stats

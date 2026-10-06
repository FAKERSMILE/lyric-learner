# -*- coding: utf-8 -*-
"""歌词词级标注：分词定位 + ECDICT 考试标签 → 前端高亮数据"""
import re

from db import is_known
from vocab_filter import classify, lookup

TOKEN_RE = re.compile(r"[A-Za-z][A-Za-z'\-]*")


def annotate_lines(lyrics: str):
    """逐行标注，返回:
    lines: [{line_no, text, tokens:[{text, start, end, word, lemma, tags, scope,
                                     in_wordbook, known}]}]
    exam_words: 去重后的备考词列表（含首次出现行号）
    """
    lines_out, exam_seen = [], {}
    for i, line in enumerate(lyrics.splitlines(), 1):
        tokens = []
        for m in TOKEN_RE.finditer(line):
            raw = m.group(0)
            info = classify(raw.strip("'-").lower())
            word = info["word"] if info["included"] else raw.strip("'-").lower()
            row = lookup(word)
            lemma = word
            if info["included"]:
                lemma = word
            tok = {
                "text": raw,
                "start": m.start(),
                "end": m.end(),
                "word": word,
                "lemma": lemma,
                "exam": info["scope"] if info["included"] else "",
                "tags": info["tags"] if info["included"] else [],
                "phonetic": (row["phonetic"] if row else "") or "",
                "translation": (row["translation"].split("\\n")[0][:60] if row else "") or "",
            }
            tokens.append(tok)
            if info["included"] and info["word"] not in exam_seen:
                exam_seen[info["word"]] = {
                    "word": info["word"], "scope": info["scope"],
                    "translation": info["translation"], "phonetic": info["phonetic"],
                    "line_no": i,
                }
        lines_out.append({"line_no": i, "text": line, "tokens": tokens})
    # 补充收藏状态
    for ln in lines_out:
        for t in ln["tokens"]:
            t["known"] = is_known(t["word"])
    return lines_out, list(exam_seen.values())

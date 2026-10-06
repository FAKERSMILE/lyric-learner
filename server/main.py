# -*- coding: utf-8 -*-
"""歌词英语学习工具 — FastAPI 主服务"""
import threading
import traceback
import uuid
from datetime import date
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

import db
import review
from annotation import annotate_lines
from kimi_client import SECTION_KEYS, generate
from vocab_filter import filter_lyrics

BASE = Path(__file__).resolve().parent.parent
WEB_DIST = BASE / "web" / "dist"

app = FastAPI(title="歌词英语学习工具")
db.init()

# ---------- 简单任务管理（AI 分析异步执行） ----------
_jobs = {}
_jobs_lock = threading.Lock()


def _run_job(job_id: str, fn, *args):
    try:
        result = fn(*args)
        with _jobs_lock:
            _jobs[job_id] = {"status": "done", "result": result}
    except Exception as e:
        traceback.print_exc()
        with _jobs_lock:
            _jobs[job_id] = {"status": "error", "error": str(e)}


def _start_job(fn, *args) -> str:
    job_id = uuid.uuid4().hex[:12]
    with _jobs_lock:
        _jobs[job_id] = {"status": "running"}
    t = threading.Thread(target=_run_job, args=(job_id, fn, *args), daemon=True)
    t.start()
    return job_id


# ---------- models ----------
class SettingsIn(BaseModel):
    kimi_key: str = ""
    base_url: str = "https://api.moonshot.cn/v1"
    model: str = "auto"
    theme: str = "midnight"


class SongIn(BaseModel):
    title: str
    artist: str = ""
    lyrics: str
    source: str = "paste"
    sections: dict = {}


class AnalyzeIn(BaseModel):
    sections: dict


class SearchIn(BaseModel):
    query: str


class ImportIn(BaseModel):
    track_name: str
    artist_name: str = ""
    duration: float | None = None


class WordIn(BaseModel):
    word: str
    source_song_id: int | None = None
    source_line: str = ""


class SentenceIn(BaseModel):
    song_id: int
    line_no: int


class KnowledgeIn(BaseModel):
    kind: str
    title: str
    content: str = ""
    example_en: str = ""
    example_zh: str = ""
    source_song_id: int | None = None
    source_line: str = ""


class AnswerIn(BaseModel):
    card_type: str
    card_id: int
    result: str


class CheckIn(BaseModel):
    typed: str
    target: str
    mode: str = "word"


class RestoreIn(BaseModel):
    data: dict


# ---------- settings ----------
@app.get("/api/settings")
def get_settings():
    return {
        "kimi_key": db.get_setting("kimi_key"),
        "base_url": db.get_setting("base_url", "https://api.moonshot.cn/v1"),
        "model": db.get_setting("model", "auto"),
        "theme": db.get_setting("theme", "midnight"),
        "has_key": bool(db.get_setting("kimi_key")),
    }


@app.post("/api/settings")
def save_settings(s: SettingsIn):
    for k, v in s.model_dump().items():
        if k == "kimi_key" and v.startswith("sk-") is False and v != "":
            pass  # 允许自定义中转 key 原样保存
        db.set_setting(k, v)
    return {"ok": True}


# ---------- dict ----------
@app.get("/api/dict/{word}")
def dict_lookup(word: str):
    from vocab_filter import lookup, lemma_of
    w = word.lower().strip()
    row = lookup(w) or lookup(lemma_of(w) or "")
    if not row:
        raise HTTPException(404, "词库未收录")
    exchange = (row["exchange"] or "")
    parts = []
    names = {"p": "过去式", "d": "过去分词", "i": "现在分词", "3": "三单",
             "r": "比较级", "t": "最高级", "s": "复数"}
    for item in exchange.split("/"):
        if ":" in item:
            k, v = item.split(":", 1)
            if k in names and v:
                parts.append(f"{names[k]} {v}")
    return {
        "word": row["word"], "phonetic": row["phonetic"] or "",
        "translation": (row["translation"] or "").replace("\\n", "\n"),
        "exchange": "；".join(parts),
        "in_wordbook": bool(db.get_word(row["word"])),
        "known": db.is_known(row["word"]),
    }


# ---------- lyrics search / import ----------
@app.post("/api/lyrics/search")
def lyrics_search(s: SearchIn):
    from lyrics_fetch import search_tracks
    return {"tracks": search_tracks(s.query)}


@app.post("/api/lyrics/fetch")
def lyrics_fetch_api(i: ImportIn):
    from lyrics_fetch import fetch_lyrics
    text = fetch_lyrics(i.track_name, i.artist_name, i.duration)
    return {"lyrics": text or "", "found": bool(text)}


# ---------- songs ----------
def _do_analyze(song: dict, sections: dict):
    key = db.get_setting("kimi_key")
    if not key:
        raise RuntimeError("未配置 Kimi API Key，请先到设置页填写")
    candidates, _stats = filter_lyrics(song["lyrics"])
    result = generate(key, song["title"], song["artist"], song["lyrics"],
                      candidates, sections)
    if result.get("line_zh"):
        db.save_line_zh(song["id"], result.pop("line_zh"))
    done = [k for k in SECTION_KEYS if k in result]
    if done:
        db.save_sections(song["id"], {k: result[k] for k in done}, done)
    return {"sections_done": done}


@app.post("/api/songs")
def create_song(s: SongIn):
    if not s.lyrics.strip():
        raise HTTPException(400, "歌词为空")
    sid = db.add_song(s.title.strip() or "未命名", s.artist.strip(), s.lyrics,
                      s.source)
    job = _start_job(_do_analyze, {"id": sid, "title": s.title.strip() or "未命名",
                                   "artist": s.artist.strip(), "lyrics": s.lyrics},
                     s.sections)
    return {"id": sid, "job": job}


@app.post("/api/songs/{sid}/analyze")
def analyze_song(sid: int, a: AnalyzeIn):
    song = db.get_song(sid)
    if not song:
        raise HTTPException(404, "歌曲不存在")
    job = _start_job(_do_analyze, song, a.sections)
    return {"job": job}


@app.get("/api/jobs/{job_id}")
def job_status(job_id: str):
    with _jobs_lock:
        return _jobs.get(job_id, {"status": "unknown"})


@app.get("/api/songs")
def songs():
    return db.list_songs()


@app.get("/api/songs/{sid}")
def song_detail(sid: int):
    song = db.get_song(sid)
    if not song:
        raise HTTPException(404, "歌曲不存在")
    lines, exam_words = annotate_lines(song["lyrics"])
    wb_words = {w["word"] for w in db.list_wordbook(include_mastered=True)}
    for ln in lines:
        for t in ln["tokens"]:
            t["in_wordbook"] = t["word"] in wb_words
    mat = db.get_material(sid)
    return {"song": song, "lines": lines, "exam_words": exam_words,
            "material": mat or {"line_zh": [], "sections": {}, "sections_done": []}}


@app.delete("/api/songs/{sid}")
def del_song(sid: int):
    db.delete_song(sid)
    return {"ok": True}


# ---------- wordbook ----------
@app.get("/api/wordbook")
def wordbook(include_mastered: bool = False):
    return db.list_wordbook(include_mastered=include_mastered)


@app.post("/api/wordbook")
def add_to_wordbook(w: WordIn):
    from vocab_filter import classify
    info = classify(w.word.lower())
    ok = db.add_word(
        word=info["word"] if info["included"] else w.word.lower(),
        lemma=info["word"] if info["included"] else w.word.lower(),
        phonetic=info["phonetic"] or "",
        translation=info["translation"] or "",
        exam_scope=info["scope"] or "未分级",
        source_song_id=w.source_song_id,
        source_line=w.source_line[:200],
    )
    return {"ok": ok, "msg": "" if ok else "该词已在生词本中"}


def _line_text(lyrics: str, line_no: int) -> str:
    lines = lyrics.splitlines()
    return lines[line_no - 1] if 0 < line_no <= len(lines) else ""


@app.delete("/api/wordbook/{wid}")
def del_word(wid: int):
    db.delete_word(wid)
    return {"ok": True}


@app.post("/api/wordbook/{wid}/master")
def master_word(wid: int):
    db.set_word_status(wid, "mastered")
    return {"ok": True}


@app.post("/api/wordbook/{wid}/unmaster")
def unmaster_word(wid: int):
    c = db.conn()
    row = c.execute("SELECT word FROM wordbook WHERE id=?", (wid,)).fetchone()
    c.close()
    if row:
        db.unmark_known(row["word"])
    db.set_word_status(wid, "active")
    return {"ok": True}


@app.get("/api/known-words")
def known_words():
    return {"words": sorted(db.list_known_words())}


class KnownIn(BaseModel):
    word: str
    known: bool = True


@app.post("/api/known-words")
def mark_known(k: KnownIn):
    from vocab_filter import classify
    info = classify(k.word.lower())
    word = info["word"] if info["included"] else k.word.lower().strip()
    if k.known:
        c = db.conn()
        c.execute("INSERT OR IGNORE INTO known_words(word) VALUES(?)", (word,))
        # 若在生词本中也标记为已掌握
        c.execute("UPDATE wordbook SET status='mastered' WHERE word=?", (word,))
        c.commit()
        c.close()
    else:
        db.unmark_known(word)
        c = db.conn()
        c.execute("UPDATE wordbook SET status='active' WHERE word=? AND status='mastered'",
                  (word,))
        c.commit()
        c.close()
    return {"ok": True, "word": word}


# ---------- cards ----------
@app.get("/api/sentence-cards")
def sentence_cards():
    return db.list_sentence_cards()


@app.post("/api/sentence-cards")
def add_sentence_card_api(s: SentenceIn):
    song = db.get_song(s.song_id)
    if not song:
        raise HTTPException(404, "歌曲不存在")
    en = _line_text(song["lyrics"], s.line_no)
    if not en.strip():
        raise HTTPException(400, "该行无内容")
    zh = ""
    mat = db.get_material(s.song_id)
    if mat:
        for item in mat["line_zh"]:
            if item.get("line_no") == s.line_no:
                zh = item.get("zh", "")
                break
    cid = db.add_sentence_card(s.song_id, s.line_no, en, zh)
    return {"ok": cid is not None, "id": cid,
            "msg": "" if cid else "该句已收藏过"}


@app.delete("/api/sentence-cards/{cid}")
def del_sentence_card(cid: int):
    db.delete_sentence_card(cid)
    return {"ok": True}


@app.get("/api/knowledge-cards")
def knowledge_cards():
    return db.list_knowledge_cards()


@app.post("/api/knowledge-cards")
def add_knowledge_card_api(k: KnowledgeIn):
    kid = db.add_knowledge_card(k.kind, k.title, k.content, k.example_en,
                                k.example_zh, k.source_song_id, k.source_line)
    return {"id": kid}


@app.delete("/api/knowledge-cards/{kid}")
def del_knowledge_card(kid: int):
    db.delete_knowledge_card(kid)
    return {"ok": True}


# ---------- review ----------
@app.get("/api/review/today")
def review_today():
    today = date.today().isoformat()
    due = db.due_cards(today)
    total = sum(len(v) for v in due.values())
    return {"date": today, "total": total, **due}


@app.post("/api/review/check")
def review_check(c: CheckIn):
    if c.mode == "sentence":
        score = review.sentence_matches(c.typed, c.target)
        return {"score": round(score, 2), "pass": score >= 0.8}
    return {"pass": review.word_matches(c.typed, c.target)}


@app.post("/api/review/answer")
def review_answer(a: AnswerIn):
    table = {"word": "wordbook", "sentence": "sentence_cards",
             "knowledge": "knowledge_cards"}.get(a.card_type)
    if not table:
        raise HTTPException(400, "未知卡片类型")
    c = db.conn()
    row = c.execute(f"SELECT id, stage FROM {table} WHERE id=?", (a.card_id,)).fetchone()
    c.close()
    if not row:
        raise HTTPException(404, "卡片不存在")
    new_stage, nd = review.schedule(row["stage"], a.result)
    c = db.conn()
    c.execute(f"UPDATE {table} SET stage=?, next_date=? WHERE id=?",
              (new_stage, nd, a.card_id))
    c.commit()
    c.close()
    db.log_review(a.card_type, a.card_id, a.result, nd)
    return {"stage": new_stage, "next_date": nd}


# ---------- backup ----------
@app.get("/api/backup")
def backup():
    return db.backup_all()


@app.post("/api/backup/import")
def restore(r: RestoreIn):
    db.restore_all(r.data)
    return {"ok": True}


# ---------- 静态托管（前端构建产物） ----------
if WEB_DIST.exists():
    app.mount("/assets", StaticFiles(directory=WEB_DIST / "assets"), name="assets")

    @app.get("/{full_path:path}")
    def spa(full_path: str):
        fp = WEB_DIST / full_path
        if full_path and fp.is_file():
            return FileResponse(fp)
        return FileResponse(WEB_DIST / "index.html")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8765)

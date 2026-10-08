# -*- coding: utf-8 -*-
"""SQLite 数据层：歌曲/标注/生词本/句卡/知识点卡/复习记录/设置"""
import json
import sqlite3
from datetime import date, datetime
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
DATA = BASE / "data"
DB_PATH = DATA / "app.sqlite"

SCHEMA = """
CREATE TABLE IF NOT EXISTS settings (
  key TEXT PRIMARY KEY,
  value TEXT
);
CREATE TABLE IF NOT EXISTS songs (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  title TEXT NOT NULL,
  artist TEXT DEFAULT '',
  lyrics TEXT NOT NULL,
  source TEXT DEFAULT 'paste',
  created_at TEXT DEFAULT (datetime('now','localtime'))
);
CREATE TABLE IF NOT EXISTS materials (
  song_id INTEGER PRIMARY KEY,
  line_zh TEXT DEFAULT '[]',          -- [{line_no, zh, note}] 逐句翻译+行标注（基础层, AI）
  sections TEXT DEFAULT '{}',         -- {vocab:[...], sentences:[...], collocations:[...], writing:[...]}
  sections_done TEXT DEFAULT '[]',    -- 已生成的栏目名
  updated_at TEXT
);
CREATE TABLE IF NOT EXISTS wordbook (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  word TEXT UNIQUE NOT NULL,
  lemma TEXT DEFAULT '',
  phonetic TEXT DEFAULT '',
  translation TEXT DEFAULT '',
  exam_scope TEXT DEFAULT '',
  source_song_id INTEGER,
  source_line TEXT DEFAULT '',
  status TEXT DEFAULT 'active',       -- active | mastered
  stage INTEGER DEFAULT 0,
  next_date TEXT,
  added_at TEXT DEFAULT (datetime('now','localtime'))
);
CREATE TABLE IF NOT EXISTS sentence_cards (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  song_id INTEGER NOT NULL,
  line_no INTEGER,
  en TEXT NOT NULL,
  zh TEXT DEFAULT '',
  status TEXT DEFAULT 'active',
  stage INTEGER DEFAULT 0,
  next_date TEXT,
  added_at TEXT DEFAULT (datetime('now','localtime'))
);
CREATE TABLE IF NOT EXISTS knowledge_cards (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  kind TEXT NOT NULL,                 -- grammar | collocation
  title TEXT NOT NULL,
  content TEXT DEFAULT '',
  example_en TEXT DEFAULT '',
  example_zh TEXT DEFAULT '',
  source_song_id INTEGER,
  source_line TEXT DEFAULT '',
  status TEXT DEFAULT 'active',
  stage INTEGER DEFAULT 0,
  next_date TEXT,
  added_at TEXT DEFAULT (datetime('now','localtime'))
);
CREATE TABLE IF NOT EXISTS known_words (
  word TEXT PRIMARY KEY               -- “我会了”：全局不再高亮
);
CREATE TABLE IF NOT EXISTS review_log (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  card_type TEXT NOT NULL,            -- word | sentence | knowledge
  card_id INTEGER NOT NULL,
  result TEXT NOT NULL,               -- remember | fuzzy | forget
  reviewed_at TEXT DEFAULT (datetime('now','localtime'))
);
"""


def conn() -> sqlite3.Connection:
    DATA.mkdir(exist_ok=True)
    c = sqlite3.connect(DB_PATH)
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA journal_mode=WAL")
    c.execute("PRAGMA foreign_keys=ON")
    return c


def init():
    c = conn()
    c.executescript(SCHEMA)
    c.commit()
    c.close()


# ---------- settings ----------
def get_setting(key: str, default=""):
    c = conn()
    row = c.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
    c.close()
    return row["value"] if row else default


def set_setting(key: str, value: str):
    c = conn()
    c.execute("INSERT INTO settings(key,value) VALUES(?,?) "
              "ON CONFLICT(key) DO UPDATE SET value=excluded.value", (key, value))
    c.commit()
    c.close()


# ---------- songs ----------
def add_song(title: str, artist: str, lyrics: str, source="paste") -> int:
    c = conn()
    cur = c.execute(
        "INSERT INTO songs(title,artist,lyrics,source) VALUES(?,?,?,?)",
        (title, artist, lyrics, source))
    c.commit()
    sid = cur.lastrowid
    c.close()
    return sid


def list_songs():
    c = conn()
    rows = c.execute(
        "SELECT s.*, (SELECT count(*) FROM wordbook w WHERE w.source_song_id=s.id) wb_cnt "
        "FROM songs s ORDER BY s.id DESC").fetchall()
    c.close()
    return [dict(r) for r in rows]


def get_song(sid: int):
    c = conn()
    row = c.execute("SELECT * FROM songs WHERE id=?", (sid,)).fetchone()
    c.close()
    return dict(row) if row else None


def delete_song(sid: int):
    c = conn()
    # 先收集关联的卡片 ID，级联删 review_log
    wb_ids = [r[0] for r in c.execute(
        "SELECT id FROM wordbook WHERE source_song_id=?", (sid,)).fetchall()]
    sc_ids = [r[0] for r in c.execute(
        "SELECT id FROM sentence_cards WHERE song_id=?", (sid,)).fetchall()]
    for wid in wb_ids:
        c.execute("DELETE FROM review_log WHERE card_type='word' AND card_id=?", (wid,))
    for cid in sc_ids:
        c.execute("DELETE FROM review_log WHERE card_type='sentence' AND card_id=?", (cid,))
    # wordbook 不删除，只解除关联（用户可能想保留学过的词）
    c.execute("UPDATE wordbook SET source_song_id=NULL WHERE source_song_id=?", (sid,))
    for t in ("materials",):
        c.execute(f"DELETE FROM {t} WHERE song_id=?", (sid,))
    c.execute("DELETE FROM sentence_cards WHERE song_id=?", (sid,))
    c.execute("DELETE FROM songs WHERE id=?", (sid,))
    c.commit()
    c.close()


# ---------- materials ----------
def get_material(sid: int):
    c = conn()
    row = c.execute("SELECT * FROM materials WHERE song_id=?", (sid,)).fetchone()
    c.close()
    if not row:
        return None
    d = dict(row)
    d["line_zh"] = json.loads(d["line_zh"] or "[]")
    d["sections"] = json.loads(d["sections"] or "{}")
    d["sections_done"] = json.loads(d["sections_done"] or "[]")
    return d


def save_line_zh(sid: int, line_zh: list):
    c = conn()
    c.execute(
        "INSERT INTO materials(song_id,line_zh,updated_at) VALUES(?,?,datetime('now','localtime')) "
        "ON CONFLICT(song_id) DO UPDATE SET line_zh=excluded.line_zh,"
        "updated_at=excluded.updated_at",
        (sid, json.dumps(line_zh, ensure_ascii=False)))
    c.commit()
    c.close()


def save_sections(sid: int, sections: dict, done: list):
    c = conn()
    row = c.execute("SELECT sections FROM materials WHERE song_id=?", (sid,)).fetchone()
    merged = json.loads(row["sections"] or "{}") if row else {}
    merged.update(sections)
    old = set(json.loads(row["sections_done"] or "[]")) if row else set()
    done_all = sorted(old | set(done))
    c.execute(
        "INSERT INTO materials(song_id,sections,sections_done,updated_at) "
        "VALUES(?,?,?,datetime('now','localtime')) "
        "ON CONFLICT(song_id) DO UPDATE SET sections=excluded.sections,"
        "sections_done=excluded.sections_done,updated_at=excluded.updated_at",
        (sid, json.dumps(merged, ensure_ascii=False), json.dumps(done_all, ensure_ascii=False)))
    c.commit()
    c.close()


# ---------- wordbook ----------
def add_word(word, lemma, phonetic, translation, exam_scope,
             source_song_id=None, source_line=""):
    c = conn()
    try:
        c.execute(
            "INSERT INTO wordbook(word,lemma,phonetic,translation,exam_scope,"
            "source_song_id,source_line) VALUES(?,?,?,?,?,?,?)",
            (word, lemma, phonetic, translation, exam_scope, source_song_id, source_line))
        c.commit()
        return c.execute("SELECT id FROM wordbook WHERE word=?", (word,)).fetchone()[0]
    except sqlite3.IntegrityError:
        # 已存在：返回 False 让调用方知道没新建
        return False
    finally:
        c.close()


def list_wordbook(status="active", include_mastered=False):
    c = conn()
    if include_mastered:
        rows = c.execute("SELECT * FROM wordbook ORDER BY id DESC").fetchall()
    else:
        rows = c.execute("SELECT * FROM wordbook WHERE status=? ORDER BY id DESC",
                         (status,)).fetchall()
    c.close()
    return [dict(r) for r in rows]


def get_word(word: str):
    c = conn()
    row = c.execute("SELECT * FROM wordbook WHERE word=?", (word.lower(),)).fetchone()
    c.close()
    return dict(row) if row else None


def set_word_status(wid: int, status: str):
    c = conn()
    c.execute("UPDATE wordbook SET status=? WHERE id=?", (status, wid))
    if status == "mastered":
        row = c.execute("SELECT word FROM wordbook WHERE id=?", (wid,)).fetchone()
        if row:
            c.execute("INSERT OR IGNORE INTO known_words(word) VALUES(?)", (row["word"],))
    c.commit()
    c.close()


def delete_word(wid: int):
    c = conn()
    c.execute("DELETE FROM wordbook WHERE id=?", (wid,))
    c.commit()
    c.close()


def is_known(word: str) -> bool:
    c = conn()
    row = c.execute("SELECT 1 FROM known_words WHERE word=?", (word.lower(),)).fetchone()
    c.close()
    return bool(row)


def unmark_known(word: str):
    c = conn()
    c.execute("DELETE FROM known_words WHERE word=?", (word.lower(),))
    c.commit()
    c.close()


def list_known_words():
    c = conn()
    rows = c.execute("SELECT word FROM known_words").fetchall()
    c.close()
    return {r["word"] for r in rows}


# ---------- sentence cards ----------
def add_sentence_card(song_id, line_no, en, zh=""):
    c = conn()
    dup = c.execute("SELECT 1 FROM sentence_cards WHERE song_id=? AND line_no=?",
                    (song_id, line_no)).fetchone()
    if dup:
        c.close()
        return None
    cur = c.execute(
        "INSERT INTO sentence_cards(song_id,line_no,en,zh) VALUES(?,?,?,?)",
        (song_id, line_no, en, zh))
    c.commit()
    cid = cur.lastrowid
    c.close()
    return cid


def list_sentence_cards():
    c = conn()
    rows = c.execute(
        "SELECT sc.*, s.title song_title, s.artist song_artist "
        "FROM sentence_cards sc LEFT JOIN songs s ON s.id=sc.song_id "
        "ORDER BY sc.id DESC").fetchall()
    c.close()
    return [dict(r) for r in rows]


def delete_sentence_card(cid: int):
    c = conn()
    c.execute("DELETE FROM sentence_cards WHERE id=?", (cid,))
    c.commit()
    c.close()


# ---------- knowledge cards ----------
def add_knowledge_card(kind, title, content="", example_en="", example_zh="",
                       source_song_id=None, source_line=""):
    c = conn()
    cur = c.execute(
        "INSERT INTO knowledge_cards(kind,title,content,example_en,example_zh,"
        "source_song_id,source_line) VALUES(?,?,?,?,?,?,?)",
        (kind, title, content, example_en, example_zh, source_song_id, source_line))
    c.commit()
    kid = cur.lastrowid
    c.close()
    return kid


def list_knowledge_cards():
    c = conn()
    rows = c.execute("SELECT * FROM knowledge_cards ORDER BY id DESC").fetchall()
    c.close()
    return [dict(r) for r in rows]


def delete_knowledge_card(kid: int):
    c = conn()
    c.execute("DELETE FROM knowledge_cards WHERE id=?", (kid,))
    c.commit()
    c.close()


# ---------- review ----------
def due_cards(today: str):
    """返回今日到期卡片（word/sentence/knowledge 混合）"""
    c = conn()
    out = {"word": [], "sentence": [], "knowledge": []}
    rows = c.execute("SELECT * FROM wordbook WHERE status='active' AND "
                     "(next_date IS NULL OR next_date<=?)", (today,)).fetchall()
    out["word"] = [dict(r) for r in rows]
    rows = c.execute("SELECT sc.*, s.title song_title FROM sentence_cards sc "
                     "LEFT JOIN songs s ON s.id=sc.song_id "
                     "WHERE sc.status='active' AND (sc.next_date IS NULL OR sc.next_date<=?)",
                     (today,)).fetchall()
    out["sentence"] = [dict(r) for r in rows]
    rows = c.execute("SELECT * FROM knowledge_cards WHERE status='active' AND "
                     "(next_date IS NULL OR next_date<=?)", (today,)).fetchall()
    out["knowledge"] = [dict(r) for r in rows]
    c.close()
    return out


def log_review(card_type, card_id, result, next_date):
    """记录复习反馈（排期由调用方计算并直接更新卡片）"""
    c = conn()
    c.execute("INSERT INTO review_log(card_type,card_id,result) VALUES(?,?,?)",
              (card_type, card_id, result))
    c.commit()
    c.close()


def backup_all():
    c = conn()
    out = {}
    for t in ("songs", "materials", "wordbook", "sentence_cards",
              "knowledge_cards", "known_words", "settings"):
        rows = c.execute(f"SELECT * FROM {t}").fetchall()
        out[t] = [dict(r) for r in rows]
    c.close()
    out["_exported_at"] = datetime.now().isoformat(timespec="seconds")
    return out


def restore_all(data: dict):
    c = conn()
    for t in ("songs", "materials", "wordbook", "sentence_cards",
              "knowledge_cards", "known_words", "settings"):
        if t not in data:
            continue
        rows = data[t]
        if not isinstance(rows, list):
            continue
        for r in rows:
            r = {k: v for k, v in r.items() if k in _columns(c, t)}
            if not r:
                continue
            cols = ",".join(r.keys())
            ph = ",".join("?" for _ in r)
            c.execute(f"INSERT OR REPLACE INTO {t}({cols}) VALUES({ph})",
                      tuple(r.values()))
    c.commit()
    c.close()


def _columns(c, table):
    return {r[1] for r in c.execute(f"PRAGMA table_info({table})")}


# ---------- stats ----------
def get_stats():
    """学习统计总览：词汇量、复习次数、正确率、打卡日历、连续天数"""
    c = conn()
    today = date.today().isoformat()

    # 词汇量
    total_words = c.execute("SELECT COUNT(*) FROM wordbook").fetchone()[0]
    mastered_words = c.execute(
        "SELECT COUNT(*) FROM wordbook WHERE status='mastered'").fetchone()[0]
    active_words = total_words - mastered_words

    # 总复习次数 + 正确率
    total_reviews = c.execute("SELECT COUNT(*) FROM review_log").fetchone()[0]
    correct_reviews = c.execute(
        "SELECT COUNT(*) FROM review_log WHERE result='remember'").fetchone()[0]
    accuracy = round(correct_reviews / total_reviews * 100, 1) if total_reviews else 0

    # 打卡日历（近 30 天：某天有复习记录 = 打卡）
    cal_rows = c.execute(
        "SELECT substr(reviewed_at,1,10) d, COUNT(*) cnt "
        "FROM review_log WHERE reviewed_at >= date('now','-30 day') "
        "GROUP BY d ORDER BY d").fetchall()
    calendar = {r["d"]: r["cnt"] for r in cal_rows}

    # 连续打卡天数（从今天往前数）
    from datetime import timedelta
    all_dates = sorted(calendar.keys(), reverse=True)
    streak = 0
    for i, d in enumerate(all_dates):
        expected = (date.today() - timedelta(days=i)).isoformat()
        if d == expected:
            streak += 1
        else:
            break

    # 今日到期卡片数
    due_total = sum(len(v) for v in due_cards(today).values())

    # 歌曲数
    song_count = c.execute("SELECT COUNT(*) FROM songs").fetchone()[0]

    c.close()
    return {
        "today": today,
        "streak": streak,
        "due_today": due_total,
        "songs": song_count,
        "words": {"total": total_words, "active": active_words, "mastered": mastered_words},
        "reviews": {"total": total_reviews, "correct": correct_reviews, "accuracy_pct": accuracy},
        "calendar": calendar,
    }

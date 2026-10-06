# -*- coding: utf-8 -*-
"""LRCLIB 歌词抓取（免费、无需 Key）https://lrclib.net"""
import re
import time

import requests

API = "https://lrclib.net/api"
HEADERS = {"User-Agent": "song-english/0.1 (personal lyrics learner)"}
TIMEOUT = 15

# 最近一次搜索失败原因（供 UI 提示；None 表示没有网络错误）
last_error = None


def _clean_synced(synced: str) -> str:
    """去掉 [mm:ss.xx] 时间轴标记，只留文本"""
    return re.sub(r"\[[^\]]*\]\s*", "", synced or "").strip()


def _search_once(params: dict):
    """单次搜索请求；429 限流时等待重试一次。返回列表或 None（网络/HTTP 错误）"""
    for attempt in range(2):
        try:
            r = requests.get(f"{API}/search", params=params,
                             headers=HEADERS, timeout=TIMEOUT)
            if r.status_code == 429:
                time.sleep(1.5)
                continue
            if r.ok:
                return r.json()
            return None
        except Exception:
            return None
    return None


def search_tracks(query: str, limit: int = 6):
    """按关键词搜索歌曲，返回 [{track_name, artist_name, album_name, duration, instrumental, has_lyrics}]

    LRCLIB 的 q= 是严格全词匹配：词库里没有对应版本时（如歌手名拼错或小众歌手），
    整串查询会归零。因此做多级降级：完整 q -> track_name= -> 逐词截短 q。
    """
    global last_error
    last_error = None
    query = (query or "").strip()
    if not query:
        return []

    words = query.split()
    attempts = [{"q": query}]
    if len(words) >= 3:
        # 尝试把整串当歌名（LRCLIB 支持按歌名独立搜索）
        attempts.append({"track_name": query})
        # 逐词截短：去掉末尾的歌手词再试
        for n in range(len(words) - 1, 1, -1):
            attempts.append({"q": " ".join(words[:n])})

    data = None
    for params in attempts:
        data = _search_once(params)
        if data:  # 非空列表即成功
            break

    if data is None:
        last_error = "网络请求失败或被限流，请等几秒重试"
        return []
    if not data:
        return []

    # 带歌词的结果排前面（LRCLIB 字段为驼峰：trackName/artistName/albumName）
    data.sort(key=lambda t: bool(t.get("plainLyrics") or t.get("syncedLyrics")),
              reverse=True)
    seen, out = set(), []
    for t in data[:30]:
        key = (t.get("trackName"), t.get("artistName"))
        if key in seen:
            continue
        seen.add(key)
        out.append({
            "track_name": t.get("trackName", ""),
            "artist_name": t.get("artistName", ""),
            "album_name": t.get("albumName", ""),
            "duration": t.get("duration") or 0,
            "instrumental": t.get("instrumental", False),
            "has_lyrics": bool(t.get("plainLyrics") or t.get("syncedLyrics")),
        })
        if len(out) >= limit:
            break
    return out


def fetch_lyrics(track_name: str, artist_name: str = "", duration=None):
    """抓取歌词，返回纯文本歌词；失败返回 None"""
    def _text_from(payload):
        if not payload:
            return None
        plain = (payload.get("plainLyrics") or "").strip()
        synced = (payload.get("syncedLyrics") or "").strip()
        if plain:
            return plain
        if synced:
            return _clean_synced(synced)
        return None

    try:
        params = {"track_name": track_name, "artist_name": artist_name}
        if duration:
            params["duration"] = int(duration)
        r = requests.get(f"{API}/get", params=params,
                         headers=HEADERS, timeout=TIMEOUT)
        if r.ok:
            text = _text_from(r.json())
            if text:
                return text
    except Exception:
        pass

    # 兜底：全文搜索取第一条
    try:
        q = f"{track_name} {artist_name}".strip()
        r = requests.get(f"{API}/search", params={"q": q},
                         headers=HEADERS, timeout=TIMEOUT)
        r.raise_for_status()
        items = r.json()
        for item in items:
            text = _text_from(item)
            if text:
                return text
    except Exception:
        pass
    return None

# -*- coding: utf-8 -*-
"""Kimi (Moonshot) OpenAI 兼容客户端
- 基础层：逐句翻译 + 语法/搭配行标注（始终生成）
- 可选栏目：vocab(词汇汇总表) / sentences(长难句) / collocations(固定搭配) / writing(写作仿写)
"""
import json

from openai import OpenAI

BASE_URL = "https://api.moonshot.cn/v1"

SYSTEM_PROMPT = (
    "你是资深英语教研老师，为中国大学生（四六级/考研/雅思/托福备考）制作英文歌词学习资料。"
    "要求：1) 翻译贴合歌词本意、简洁口语化；2) 不做文学赏析、不写废话；"
    "3) 只依据给定信息作答，不编造词表以外的词；4) 全程中文说明+英文原句。"
)

SECTION_KEYS = ["vocab", "sentences", "collocations", "writing"]


def _pick_model(total_chars: int) -> str:
    # moonshot-v1-* 全系 2026-08-31 已下线，改用 kimi-k2.6
    # kimi-k2.6 性价比高（输入 $0.95/M 输出 $4.00/M），256K 上下文足够歌词场景
    return "kimi-k2.6"


def _client(api_key: str):
    return OpenAI(api_key=api_key, base_url=BASE_URL)


def _user_prompt(title, artist, lyrics, candidates, sections: dict):
    vocab_pack = [
        {"word": c["word"], "tags": c["scope"], "sentence": c["sentence"],
         "ec_translation": c["translation"], "exchange": c["exchange"]}
        for c in candidates
    ]
    lines = "\n".join(f"L{i}|{line}" for i, line in enumerate(lyrics.splitlines(), 1)
                      if line.strip())
    want = {k: bool(sections.get(k)) for k in SECTION_KEYS}
    js = {
        "line_zh": [{"line_no": 1, "zh": "该行简洁中文翻译",
                     "note": "该行语法点或固定搭配标注，没有则空字符串"}],
    }
    if want["vocab"]:
        js["vocab"] = [{"word": "", "scope": "如: 六级/考研", "sentence": "该词所在歌词原句",
                        "sentence_zh": "原句中文翻译", "meaning": "该词在此句中的释义(简洁)",
                        "root": "词根词缀分析", "derivatives": "常见变形与派生词"}]
    if want["sentences"]:
        js["sentences"] = [{"sentence": "长难句原句", "zh": "翻译",
                            "analysis": "主干/从句/时态拆解，用；分隔"}]
    if want["collocations"]:
        js["collocations"] = [{"phrase": "固定搭配", "zh": "含义",
                               "example": "可迁移英文例句"}]
    if want["writing"]:
        js["writing"] = [{"pattern": "可仿写句型", "example": "四六级或考研风格例句",
                          "zh": "例句翻译"}]

    rules = [
        "- line_zh 覆盖歌词每一行；note 标注该行时态/从句/非谓语/倒装/虚拟等语法点或固定搭配，没有就留空"
    ]
    if want["vocab"]:
        rules.append("- vocab.scope 只能取该词 tags 中出现的考试名（四级/六级/考研/雅思/托福）")
    if want["sentences"]:
        rules.append("- sentences 挑 3-6 句语法结构最值得讲的长难句，没有合适就给 2 句")
    if want["collocations"]:
        rules.append("- collocations 3-8 条（歌词中出现的短语/搭配），example 给可迁移表达")
    if want["writing"]:
        rules.append("- writing 给 3-5 条可直接仿写的四六级/考研例句")

    return f"""歌曲：{title} - {artist}

歌词（L行号|内容）：
{lines}

已过滤的备考词汇候选（vocab 若生成，只允许用这个列表里的词）：
{json.dumps(vocab_pack, ensure_ascii=False)}

请生成学习资料，严格输出如下 JSON（不要输出任何 JSON 以外的文字，未要求的栏目不要输出）：
{json.dumps(js, ensure_ascii=False, indent=1)}

要求：
{chr(10).join(rules)}"""


def generate(api_key: str, title: str, artist: str, lyrics: str,
             candidates: list, sections: dict) -> dict:
    """一次调用；sections 指定可选栏目，line_zh 始终生成"""
    prompt = _user_prompt(title, artist, lyrics, candidates, sections)
    model = _pick_model(len(prompt))
    client = _client(api_key)
    resp = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
        temperature=1,
        max_tokens=4000,
        response_format={"type": "json_object"},
    )
    content = resp.choices[0].message.content or "{}"
    data = json.loads(content)
    out = {"line_zh": data.get("line_zh") or []}
    for k in SECTION_KEYS:
        if sections.get(k):
            out[k] = data.get(k) or []
    return out

#!/usr/bin/env python3
"""binge-vocab 產生器：詞條 JSON -> Anki 牌組檔 .apkg（筆記類型、卡片、發音音檔打包成單一檔案）並更新 learned_vocab.md。

用法：
    python3 gen_deck.py DATA.json [DATA2.json ...] [--dry-run] [--no-audio] [--open] [--notes-dir DIR]

DATA.json 格式：
    {
      "show": "Stranger Things",
      "episode": "S02E10",
      "entries": [
        {"word": "under attack", "level": "B2",
         "def": "遭受攻擊", "sentence": "We're **under attack**.", "zh": "我們遭到攻擊了。"}
      ]
    }

- sentence 內目標詞用 ** 包起來（會轉成 <mark> 螢光標示）。
- 詞已在 learned_vocab.md 時預設報錯；確屬「新語境/新用法」才在該詞條加 "new_context": true。
- 硬性錯誤（重複詞、已學詞、缺 ** 標記、欄位缺漏、同一原句重複）會中止且不寫任何檔案。
- 軟性警告（C1 / 俚語超過上限、詞數偏離 words_per_episode）只提醒，仍會寫檔。
- --open：產生後用系統預設程式開啟 .apkg（Anki 會自動跳出匯入視窗）。
- 一次給多個 DATA.json（多集）：全部驗證通過才寫檔（後面的集數會把前面集數的詞視為已學、不可重複），
  並打包成單一 .apkg（每集一個子牌組），一次匯入。

依賴 genanki（與 gTTS）：skill 目錄之外的 venv，見 README；缺少時腳本會自動改用該 venv 的 python。
"""
import argparse
import datetime
import hashlib
import os
import re
import subprocess
import sys
import time
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parent
_VENV = Path.home() / ".local/share/binge-vocab/venv"
VENV_PY = Path(os.environ.get("BINGE_PYTHON") or _VENV / ("Scripts/python.exe" if sys.platform == "win32" else "bin/python"))
REQUIRED = ("word", "level", "def", "sentence", "zh")
FIELDS = ["Key", "Word", "Context", "FrontContext", "Back"]
MODEL_ID = 1760283519001  # 固定值：重複匯入時 Anki 認得是同一個筆記類型
MODEL_NAME = "BingeVocab"
# 依程度 / 俚語偏好換算每集上限（config.md 可用 c1_max_per_episode、slang_max_per_episode 直接覆寫）
LEVEL_C1_CAP = {"A2": 0, "B1": 2, "B2": 6, "C1": 99, "C2": 99}
SLANG_CAP = {"none": 0, "few": 3, "many": 8}


def ensure_deps(need_audio):
    """genanki / gTTS 不在目前的 python 時，改用 venv 的 python 重跑自己。"""
    try:
        import genanki  # noqa: F401
        if need_audio:
            import gtts  # noqa: F401
        return
    except ImportError:
        pass
    if os.environ.get("BINGE_REEXEC") != "1" and VENV_PY.exists():
        os.environ["BINGE_REEXEC"] = "1"
        os.execv(str(VENV_PY), [str(VENV_PY), "-W", "ignore", str(Path(__file__).resolve()), *sys.argv[1:]])
    sys.exit("缺少 genanki / gTTS。請執行：python3 setup.py\n"
             "（不需要音檔可加 --no-audio 安裝；也可用 BINGE_PYTHON 指定已裝好的 python）")


def read_config():
    cfg = {}
    p = SKILL_DIR / "config.md"
    if p.exists():
        for line in p.read_text(encoding="utf-8").splitlines():
            m = re.match(r"^([A-Za-z_]+):\s*(.*?)\s*$", line)
            if m:
                cfg[m.group(1)] = m.group(2)
    return cfg


def resolve_notes_dir(cfg, override):
    if override:
        return Path(override).expanduser()
    raw = cfg.get("notes_dir")
    if not raw:
        sys.exit("錯誤：config.md 找不到 notes_dir。請先 cp config.example.md config.md 並填入路徑。")
    return Path(raw).expanduser()


def slug(s):
    return re.sub(r"-+", "-", re.sub(r"[^a-z0-9]+", "-", s.lower())).strip("-")


def plain(s):
    return s.replace("**", "")


def mark(s):
    return re.sub(r"\*\*(.+?)\*\*", r"<mark>\1</mark>", s)


def load_learned(path):
    if not path.exists():
        return set(), []
    lines = path.read_text(encoding="utf-8").split("\n")
    return {l[2:].strip().lower() for l in lines if l.startswith("- ")}, lines


def validate(entries, learned, cfg):
    errors, warns = [], []
    seen_words, seen_sents = set(), {}
    for i, e in enumerate(entries, 1):
        miss = [k for k in REQUIRED if not str(e.get(k, "")).strip()]
        if miss:
            errors.append(f"#{i} {e.get('word', '?')}：缺少欄位 {miss}")
            continue
        w = e["word"].lower()
        if w in seen_words:
            errors.append(f"#{i} {e['word']}：本集內詞條重複")
        seen_words.add(w)
        if w in learned and not e.get("new_context"):
            errors.append(f"#{i} {e['word']}：已在 learned_vocab.md（確屬新語境才加 \"new_context\": true）")
        if "**" not in e["sentence"]:
            errors.append(f"#{i} {e['word']}：sentence 沒有用 ** 標出目標詞")
        s = plain(e["sentence"]).strip().lower()
        if s in seen_sents:
            errors.append(f"#{i} {e['word']}：原句與 #{seen_sents[s]} 重複（一句只收一條）")
        seen_sents[s] = i
    n = len(entries)
    c1 = sum(1 for e in entries if re.search(r"\bC[12]\b", e.get("level", "")))
    slang = sum(1 for e in entries if "俚語" in e.get("level", ""))
    tgt = int(cfg.get("words_per_episode", 30))
    c1_max = int(cfg["c1_max_per_episode"]) if "c1_max_per_episode" in cfg else LEVEL_C1_CAP.get(cfg.get("level", "").upper(), 3)
    slang_max = int(cfg["slang_max_per_episode"]) if "slang_max_per_episode" in cfg else SLANG_CAP.get(cfg.get("slang", "").lower(), 3)
    if c1 > c1_max:
        warns.append(f"C1 以上共 {c1} 個，超過上限 {c1_max}")
    if slang > slang_max:
        warns.append(f"俚語共 {slang} 個，超過上限 {slang_max}")
    if abs(n - tgt) > max(3, tgt // 5):
        warns.append(f"詞數 {n} 與 words_per_episode={tgt} 差距較大")
    return errors, warns, (n, c1, slang)


def audio_names(show, ep, word):
    base = f"{slug(show)}-{ep.lower()}-{slug(word)}"
    return f"{base}-w.mp3", f"{base}-s.mp3"


def tts(text, out):
    """用 gTTS（Google 美音）產 mp3；已存在就略過。被限流（429）自動退避重試，失敗回 False 不中斷整批。"""
    from gtts import gTTS
    if out.exists() and out.stat().st_size > 0:
        return True
    err = ""
    for wait in (0, 20, 60, 120):
        time.sleep(wait)
        try:
            gTTS(text, lang="en", tld="com").save(str(out))
            time.sleep(0.8)
            return True
        except Exception as ex:  # gTTSError、網路錯誤等
            out.unlink(missing_ok=True)
            err = str(ex)
            if "429" not in err:
                break
    print(f"音檔失敗：{text[:30]}（{err[-120:]}）")
    return False


def make_audio(show, ep, entries, media_dir):
    media_dir.mkdir(parents=True, exist_ok=True)
    ok = set()
    for e in entries:
        wf, sf = audio_names(show, ep, e["word"])
        if tts(e["word"], media_dir / wf) and tts(plain(e["sentence"]), media_dir / sf):
            ok.add(e["word"])
    return ok


def card_fields(show, ep, e, has_audio):
    word, lv, d, s, zh = (e[k] for k in REQUIRED)
    hl = mark(s)
    wf, sf = audio_names(show, ep, word)
    wsnd = f"[sound:{wf}]" if has_audio else ""
    ssnd = f'<div class="lookup-audio">[sound:{sf}]</div>' if has_audio else ""
    front = (f'<div class="card-front"><div class="context-container"><div class="target-word-front">{word}</div>'
             f'<div class="context-text">"{hl}"</div></div>{wsnd}</div>')
    back = (f'<div class="lookup-card"><div class="lookup-card-inner"><div class="lookup-header">'
            f'<div class="lookup-word">{word}</div></div>'
            f'<div class="lookup-meta"><span class="lookup-part-of-speech">{lv}</span></div>'
            f'<div class="lookup-definition">{d}</div><div class="lookup-context">'
            f'<div class="lookup-context-label">Context</div><div class="lookup-context-text">"{hl}"</div></div>'
            f'<div class="lookup-translation">{zh}</div>{ssnd}</div></div>')
    return [f"{slug(show)}-{ep.lower()}-{slug(word)}", word, plain(s), front, back]


def make_model():
    import genanki
    anki = SKILL_DIR / "anki"
    return genanki.Model(
        MODEL_ID, MODEL_NAME,
        fields=[{"name": n} for n in FIELDS],
        templates=[{"name": "Card 1",
                    "qfmt": (anki / "front.html").read_text(encoding="utf-8"),
                    "afmt": (anki / "back.html").read_text(encoding="utf-8")}],
        css=(anki / "style.css").read_text(encoding="utf-8"),
        sort_field_index=1,
    )


def build_deck(model, show, ep, entries, with_audio, media_dir):
    import genanki
    deck_name = f"追劇英語::{show}::{ep}"
    deck = genanki.Deck(int(hashlib.md5(deck_name.encode()).hexdigest()[:8], 16) + (1 << 30), deck_name)
    media = []
    for e in entries:
        f = card_fields(show, ep, e, e["word"] in with_audio)
        deck.add_note(genanki.Note(model=model, fields=f, guid=genanki.guid_for(f[0])))
        if e["word"] in with_audio:
            media += [str(media_dir / n) for n in audio_names(show, ep, e["word"])]
    return deck, media


def update_vocab(path, lines, learned, entries, today):
    words = {e["word"].lower() for e in entries}
    bullets = sorted(learned | words)
    if not lines:
        head = ["---", 'title: "已學詞彙庫"', f"updated: {today}", "tags: [english, series-vocab-index]", "---",
                "# 已學詞彙庫 (Learned Vocabulary)", "",
                "> 此檔案由 binge-vocab 自動維護，用於跨集智慧去重。", ""]
        text = "\n".join(head + [f"- {b}" for b in bullets]) + "\n"
    else:
        out, inserted = [], False
        for l in lines:
            if l.startswith("- "):
                if not inserted:
                    out.extend(f"- {b}" for b in bullets)
                    inserted = True
                continue
            out.append(re.sub(r"^updated:.*", f"updated: {today}", l))
        if not inserted:
            out.extend(f"- {b}" for b in bullets)
        text = "\n".join(out).rstrip("\n") + "\n"
    path.write_text(text, encoding="utf-8")
    return len(bullets)


def open_file(path):
    cmd = {"darwin": ["open"], "win32": ["cmd", "/c", "start", ""]}.get(sys.platform, ["xdg-open"])
    try:
        subprocess.run([*cmd, str(path)], check=True)
    except (OSError, subprocess.CalledProcessError):
        print(f"無法自動開啟，請手動雙擊：{path}")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("data", nargs="+", help="一個或多個詞條 JSON（多集會打包成同一個 .apkg）")
    ap.add_argument("--dry-run", action="store_true", help="只檢查，不寫任何檔案")
    ap.add_argument("--no-audio", action="store_true", help="不產生發音音檔")
    ap.add_argument("--open", action="store_true", help="產生後用系統預設程式開啟 .apkg（Anki 會跳出匯入視窗）")
    ap.add_argument("--notes-dir", help="覆寫 config.md 的 notes_dir")
    a = ap.parse_args()

    import json
    episodes = []
    for f in a.data:
        d = json.loads(Path(f).read_text(encoding="utf-8"))
        episodes.append((d["show"], d["episode"], d["entries"]))
    cfg = read_config()
    notes_dir = resolve_notes_dir(cfg, a.notes_dir)
    vocab_path = notes_dir / "learned_vocab.md"
    learned, vlines = load_learned(vocab_path)

    # 逐集驗證；前面集數的詞視為已學，後面集數不可重複
    all_errors, seen = [], set(learned)
    for show, ep, entries in episodes:
        errors, warns, (n, c1, slang) = validate(entries, seen, cfg)
        for w in warns:
            print(f"警告（{show} {ep}）：{w}")
        all_errors += [f"{show} {ep} {e}" for e in errors]
        seen |= {e["word"].lower() for e in entries if str(e.get("word", "")).strip()}
        print(f"{show} {ep}：{n} 個詞條（C1 以上 {c1}、俚語 {slang}）")
    if all_errors:
        for e in all_errors:
            print(f"錯誤：{e}")
        sys.exit(f"共 {len(all_errors)} 個錯誤，已中止，未寫入任何檔案。")
    print("檢查通過")
    if a.dry_run:
        print("dry-run：未寫入任何檔案")
        return

    ensure_deps(need_audio=not a.no_audio)
    import genanki
    today = datetime.date.today().isoformat()
    model = make_model()
    decks, media = [], []
    for show, ep, entries in episodes:
        media_dir = notes_dir / show / "Anki" / "media"
        with_audio = frozenset()
        if not a.no_audio:
            with_audio = make_audio(show, ep, entries, media_dir)
            print(f"音檔 {show} {ep}：{len(with_audio)}/{len(entries)} 個詞條完成")
        deck, m = build_deck(model, show, ep, entries, with_audio, media_dir)
        decks.append(deck)
        media += m
    if len(episodes) == 1:
        show, ep, _ = episodes[0]
        out_dir = notes_dir / show / "Anki"
        apkg = out_dir / f"{slug(show)}-{ep.lower()}.apkg"
    else:
        out_dir = notes_dir / "batch"
        apkg = out_dir / f"{datetime.datetime.now():%Y%m%d-%H%M%S}-{len(episodes)}eps.apkg"
    out_dir.mkdir(parents=True, exist_ok=True)
    pkg = genanki.Package(decks)
    pkg.media_files = media
    pkg.write_to_file(str(apkg))
    print(f"Anki 牌組檔：{apkg}（{len(decks)} 個牌組、{sum(len(e) for _, _, e in episodes)} 張卡）")
    all_entries = [e for _, _, entries in episodes for e in entries]
    total = update_vocab(vocab_path, vlines, learned, all_entries, today)
    print(f"歷史詞庫：{vocab_path}（現有 {total} 個）")
    if a.open:
        open_file(apkg)


if __name__ == "__main__":
    main()

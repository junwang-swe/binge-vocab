#!/usr/bin/env python3
"""binge-vocab 產生器：詞條 JSON -> Anki 匯入 CSV（含發音音檔）並更新 learned_vocab.md。

用法：
    python3 -I gen_csv.py DATA.json [--dry-run] [--notes-dir DIR]

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
"""
import argparse
import csv
import datetime
import io
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parent
REQUIRED = ("word", "level", "def", "sentence", "zh")
TTS_PY = Path(os.environ.get("BINGE_TTS_PYTHON") or Path.home() / ".local/share/binge-vocab/venv/bin/python")
ANKI_MEDIA_GLOBS = (
    "Library/Application Support/Anki2/*/collection.media",  # macOS
    ".local/share/Anki2/*/collection.media",  # Linux
    "AppData/Roaming/Anki2/*/collection.media",  # Windows
)


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
    c1_max = int(cfg.get("c1_max_per_episode", 3))
    slang_max = int(cfg.get("slang_max_per_episode", 3))
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
    """用 gTTS（Google 美音）產 mp3；已存在就略過。失敗回 False，不中斷整批。"""
    if out.exists() and out.stat().st_size > 0:
        return True
    if not TTS_PY.exists():
        sys.exit(f"找不到 gTTS 環境：{TTS_PY}。請 python3 -m venv ~/.local/share/binge-vocab/venv && "
                 "~/.local/share/binge-vocab/venv/bin/pip install gTTS，或用 BINGE_TTS_PYTHON 指定已裝 gTTS 的 python，或加 --no-audio")
    code = "import sys; from gtts import gTTS; gTTS(sys.argv[1], lang='en', tld='com').save(sys.argv[2])"
    for wait in (0, 20, 60, 120):
        time.sleep(wait)
        r = subprocess.run([str(TTS_PY), "-W", "ignore", "-c", code, text, str(out)], capture_output=True, text=True)
        if r.returncode == 0 and out.exists() and out.stat().st_size > 0:
            time.sleep(0.8)
            return True
        out.unlink(missing_ok=True)
        if "429" not in r.stderr:
            break
    print(f"音檔失敗：{text[:30]}（{r.stderr.strip()[-120:]}）")
    return False


def make_audio(show, ep, entries, media_dir):
    media_dir.mkdir(parents=True, exist_ok=True)
    ok = set()
    for e in entries:
        wf, sf = audio_names(show, ep, e["word"])
        if tts(e["word"], media_dir / wf) and tts(plain(e["sentence"]), media_dir / sf):
            ok.add(e["word"])
    return ok


def install_media(media_dir):
    """把 mp3 複製進 Anki 的 collection.media；找不到 profile 就提示手動複製。"""
    override = os.environ.get("BINGE_ANKI_MEDIA")
    dests = [Path(override)] if override else [d for g in ANKI_MEDIA_GLOBS for d in Path.home().glob(g)]
    if len(dests) != 1:
        print(f"未能唯一定位 Anki collection.media（找到 {len(dests)} 個），請手動把 {media_dir} 內的 mp3 複製進去")
        return
    n = 0
    for f in media_dir.glob("*.mp3"):
        shutil.copy2(f, dests[0] / f.name)
        n += 1
    print(f"已複製 {n} 個音檔到 {dests[0]}")


def build_csv(show, ep, entries, with_audio=frozenset()):
    buf = io.StringIO()
    buf.write("#separator:Comma\n#html:true\n#notetype:Wordwise\n"
              f"#deck:追劇英語::{show}::{ep}\n"
              "#columns:Key,Word,Context,FrontContext,Back,BackDefOnly,Reverse\n")
    w = csv.writer(buf, quoting=csv.QUOTE_ALL, lineterminator="\n")
    for e in entries:
        word, lv, d, s, zh = (e[k] for k in REQUIRED)
        hl = mark(s)
        wf, sf = audio_names(show, ep, word)
        wsnd = f"[sound:{wf}]" if word in with_audio else ""
        ssnd = f'<div class="lookup-audio">[sound:{sf}]</div>' if word in with_audio else ""
        front = (f'<div class="card-front"><div class="context-container"><div class="target-word-front">{word}</div>'
                 f'<div class="context-text">"{hl}"</div></div>{wsnd}</div>')
        back = (f'<div class="lookup-card"><div class="lookup-card-inner"><div class="lookup-header">'
                f'<div class="lookup-word">{word}</div></div>'
                f'<div class="lookup-meta"><span class="lookup-part-of-speech">{lv}</span></div>'
                f'<div class="lookup-definition">{d}</div><div class="lookup-context">'
                f'<div class="lookup-context-label">Context</div><div class="lookup-context-text">"{hl}"</div></div>'
                f'<div class="lookup-translation">{zh}</div>{ssnd}</div></div>')
        backdef = (f'<div class="lookup-card"><div class="lookup-card-inner"><div class="lookup-definition">{d}</div>'
                   f'<div class="lookup-translation">{zh}</div></div></div>')
        w.writerow([f"{slug(show)}-{ep.lower()}-{slug(word)}", word, plain(s), front, back, backdef, ""])
    return buf.getvalue()


def update_vocab(path, lines, learned, entries, today):
    words = {e["word"].lower() for e in entries}
    bullets = sorted(learned | words)
    if not lines:
        head = ["---", 'title: "已學詞彙庫"', f"updated: {today}", "tags: [english, series-vocab-index]", "---",
                "# 已學詞彙庫 (Learned Vocabulary)", "",
                "> 此檔案由「追劇學英語」Skill 自動維護，用於跨集智慧去重。", ""]
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


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("data")
    ap.add_argument("--dry-run", action="store_true", help="只檢查，不寫任何檔案")
    ap.add_argument("--no-audio", action="store_true", help="不產生發音音檔")
    ap.add_argument("--notes-dir", help="覆寫 config.md 的 notes_dir")
    a = ap.parse_args()

    import json
    data = json.loads(Path(a.data).read_text(encoding="utf-8"))
    show, ep, entries = data["show"], data["episode"], data["entries"]
    cfg = read_config()
    notes_dir = resolve_notes_dir(cfg, a.notes_dir)
    vocab_path = notes_dir / "learned_vocab.md"
    learned, vlines = load_learned(vocab_path)

    errors, warns, (n, c1, slang) = validate(entries, learned, cfg)
    for w in warns:
        print(f"警告：{w}")
    if errors:
        for e in errors:
            print(f"錯誤：{e}")
        sys.exit(f"共 {len(errors)} 個錯誤，已中止，未寫入任何檔案。")
    print(f"檢查通過：{n} 個詞條（C1 以上 {c1}、俚語 {slang}）")
    if a.dry_run:
        print("dry-run：未寫入任何檔案")
        return

    today = datetime.date.today().isoformat()
    anki_dir = notes_dir / show / "Anki"
    anki_dir.mkdir(parents=True, exist_ok=True)
    csv_path = anki_dir / f"anki-{slug(show)}-{ep.lower()}.csv"
    with_audio = frozenset()
    if not a.no_audio:
        media_dir = anki_dir / "media"
        with_audio = make_audio(show, ep, entries, media_dir)
        print(f"音檔：{len(with_audio)}/{len(entries)} 個詞條完成（{media_dir}）")
        install_media(media_dir)
    csv_path.write_text(build_csv(show, ep, entries, with_audio), encoding="utf-8")
    print(f"Anki CSV：{csv_path}")
    total = update_vocab(vocab_path, vlines, learned, entries, today)
    print(f"歷史詞庫：{vocab_path}（現有 {total} 個）")


if __name__ == "__main__":
    main()

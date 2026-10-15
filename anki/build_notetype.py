#!/usr/bin/env python3
"""產生 Wordwise 筆記類型的匯入檔 wordwise-notetype.apkg。

用法：
    python3 -m venv /tmp/v && /tmp/v/bin/pip install genanki
    /tmp/v/bin/python build_notetype.py

匯入該 .apkg 會在 Anki 建立 `Wordwise` 筆記類型與一張可刪除的範例卡。
"""
from pathlib import Path

import genanki

HERE = Path(__file__).resolve().parent
MODEL_ID = 1830462917  # 固定 ID：重複匯入時 Anki 會認得是同一個筆記類型
DECK_ID = 1830462918

FIELDS = ["Key", "Word", "Context", "FrontContext", "Back", "BackDefOnly", "Reverse"]

model = genanki.Model(
    MODEL_ID,
    "Wordwise",
    fields=[{"name": n} for n in FIELDS],
    templates=[{
        "name": "Card 1",
        "qfmt": (HERE / "front.html").read_text(encoding="utf-8"),
        "afmt": (HERE / "back.html").read_text(encoding="utf-8"),
    }],
    css=(HERE / "style.css").read_text(encoding="utf-8"),
)

sample = genanki.Note(
    model=model,
    guid=genanki.guid_for("wordwise-sample"),
    fields=[
        "sample-under-attack", "under attack", "We're under attack.",
        '<div class="card-front"><div class="context-container"><div class="target-word-front">under attack</div>'
        '<div class="context-text">"We\'re <mark>under attack</mark>."</div></div></div>',
        '<div class="lookup-card"><div class="lookup-card-inner"><div class="lookup-header"><div class="lookup-word">under attack</div></div>'
        '<div class="lookup-meta"><span class="lookup-part-of-speech">B2</span></div>'
        '<div class="lookup-definition">遭受攻擊</div><div class="lookup-context"><div class="lookup-context-label">Context</div>'
        '<div class="lookup-context-text">"We\'re <mark>under attack</mark>."</div></div>'
        '<div class="lookup-translation">我們遭到攻擊了。</div></div></div>',
        "", "",
    ],
)

deck = genanki.Deck(DECK_ID, "Wordwise 範例（可刪除）")
deck.add_note(sample)
out = HERE / "wordwise-notetype.apkg"
genanki.Package(deck).write_to_file(str(out))
print(f"已產生 {out}")

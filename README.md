# gbro-series-vocab · 追劇學英語

給劇名 + 集數，AI 自動找該集字幕，挑出約 30 個值得學的詞彙短語（短語動詞、習語、B1-B2 實用詞、少量俚語），產出可直接匯入 Anki 的 CSV，並附美音發音音檔。學過的詞會記進詞庫，跨集、跨劇自動去重。

適用於 Claude Code，或任何支援自訂 skill 的 AI agent。不需要 API key。

## 安裝

需要 Python 3、`curl`、[Anki](https://apps.ankiweb.net/)。

1. 下載到 skill 目錄：

   ```bash
   git clone <本 repo 網址> ~/.claude/skills/gbro-series-vocab
   cd ~/.claude/skills/gbro-series-vocab
   cp config.example.md config.md
   ```

2. 編輯 `config.md`，至少改 `notes_dir`（詞庫與 CSV 的存放位置）。

3. 發音音檔需要 gTTS（不想要音檔可跳過，產生時加 `--no-audio`）：

   ```bash
   python3 -m venv ~/.local/share/gbro-series-vocab/venv
   ~/.local/share/gbro-series-vocab/venv/bin/pip install gTTS
   ```

4. 在 Anki 匯入筆記類型：開 Anki → 檔案 → 匯入 → 選 `anki/wordwise-notetype.apkg`。
   會建立 `Wordwise` 筆記類型與一個可刪除的範例牌組。

## 使用方式

對 AI 說：

```
追劇學英語 Breaking Bad S02E03
```

或

```
series vocab The Pitt S01E02
```

AI 會依序：

1. 找該集字幕（Springfield Springfield → subslikescript → 全網搜尋，都找不到才請你貼劇本）
2. 挑約 30 個詞，並跳過詞庫裡已學過的
3. 執行 `gen_csv.py` 驗證並產生檔案

完成後的檔案在 `{notes_dir}` 底下：

```
{notes_dir}/
├── learned_vocab.md                 # 已學詞庫（跨集去重用）
└── {劇名}/Anki/
    ├── anki-{劇名}-{sxxexx}.csv     # 匯入 Anki 用
    └── media/                       # 發音音檔
```

### 匯入 Anki

Anki → 檔案 → 匯入 → 選該集 CSV → 匯入。牌組（`追劇英語::{劇名}::{SxxExx}`）與欄位對應已寫在檔頭，不用手動設定。
音檔會自動複製進 Anki 的 `collection.media`；若提示找不到，手動把 `media/` 內的 mp3 複製進去即可。

### 卡片長相

- 正面：單字 + 原句（目標詞螢光標示），自動播單字
- 背面：難度標籤、釋義、原句、譯文，自動播原句

## 設定（config.md）

| 欄位 | 預設 | 說明 |
|---|---|---|
| `notes_dir` | `~/Documents/series-vocab/` | 詞庫與 CSV 存放位置，Obsidian 用戶可填 vault 內路徑 |
| `native_language` | 繁體中文 | 釋義與譯文語言 |
| `words_per_episode` | 30 | 每集詞數 |
| `reading_level` / `listening_level` | A2-B1 / B1-B2 | 你的程度，選詞難度略高於此 |
| `c1_max_per_episode` | 3 | 每集 C1 以上詞數上限 |
| `slang_max_per_episode` | 3 | 每集俚語上限 |

## 常見問題

- **找不到字幕**：新劇有時搜不到，換劇名裡最獨特的一個字再試；或直接把劇本文字貼給 AI。
- **音檔失敗 / 被限流（429）**：腳本會自動重試；仍失敗的卡片退回無音檔，可稍後重跑。
- **想略過音檔**：對 AI 說「這次不要音檔」，或手動執行 `python3 -I gen_csv.py data.json --no-audio`。
- **自訂卡片外觀**：改 `anki/style.css`、`anki/front.html`、`anki/back.html`，再用 `anki/build_notetype.py` 重建 apkg（需 `pip install genanki`）。

## 隱私與版權

- 發音使用 gTTS，會把單字與原句文字送到 Google 的 TTS 服務。
- 字幕與劇本來自公開網頁，僅供個人學習；產出只保留選出的例句，不保存整集劇本。

## 與上游的差異

- 每集約 30 個詞（可設定），依程度過濾難度，C1 與俚語有上限，過時俚語不收
- 跨集、跨劇去重詞庫；多義詞僅在出現新語境時才再收
- `gen_csv.py` 負責驗證與產檔（重複詞、缺標記、重複原句會中止），不讓模型手寫 CSV
- 卡片放美音音檔，不放音標；每集一個 Anki 子牌組

## Credits & License

基於 [pyang5166/gbro-series-vocab](https://github.com/pyang5166/gbro-series-vocab)（MIT © 狗哥笔记）修改，新增去重詞庫、`gen_csv.py`、發音音檔與 Anki 筆記類型等功能。

MIT License，見 [LICENSE](LICENSE)。

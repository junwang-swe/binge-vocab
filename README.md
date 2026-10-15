# binge-vocab · 追劇學英語

給劇名 + 集數，AI 自動找該集字幕，挑出約 30 個值得學的詞彙短語（短語動詞、習語、B1-B2 實用詞、少量俚語），產出單一 `.apkg` 牌組檔（卡片、樣式、美音發音音檔全包在裡面），雙擊就匯入 Anki，不用另外設定筆記類型或搬音檔。學過的詞會記進詞庫，跨集、跨劇自動去重。

適用於 Claude Code，或任何支援自訂 skill 的 AI agent。不需要 API key。

## 安裝

需要 Python 3、`curl`、[Anki](https://apps.ankiweb.net/)。

```bash
git clone <本 repo 網址> ~/.claude/skills/binge-vocab
cd ~/.claude/skills/binge-vocab
cp config.example.md config.md        # 編輯 notes_dir（詞庫與牌組檔的存放位置）

python3 -m venv ~/.local/share/binge-vocab/venv
~/.local/share/binge-vocab/venv/bin/pip install genanki gTTS
```

就這樣。不需要手動建立 Anki 筆記類型，第一次匯入牌組檔時會自動建立 `BingeVocab`。
（只想要卡片、不要音檔：只裝 `genanki`，並對 AI 說「不要音檔」。）

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
3. 執行 `gen_deck.py` 驗證並產生牌組檔，最後自動開啟 Anki 的匯入視窗，你只要按「匯入」

完成後的檔案在 `{notes_dir}` 底下：

```
{notes_dir}/
├── learned_vocab.md                 # 已學詞庫（跨集去重用）
└── {劇名}/Anki/
    └── {劇名}-{sxxexx}.apkg         # 牌組檔（卡片 + 樣式 + 音檔）
```

重複匯入同一集不會產生重複卡片，會更新原有卡片並保留複習進度。

### 卡片長相

- 正面：單字 + 原句（目標詞螢光標示），自動播單字
- 背面：難度標籤、釋義、原句、譯文，自動播原句

## 選用：簡化評分按鈕

學詞彙不需要 Again / Hard / Good / Easy 四個按鈕，只要「記得 / 不記得」就夠。可以在 Anki 安裝第三方外掛 **PassFail 2**（外掛代碼 `876946123`，工具 → 外掛程式 → 取得外掛），把按鈕簡化成 Fail / Pass 兩個。
這是別人的外掛，與本專案無關，是否安裝由你決定。

## 設定（config.md）

| 欄位 | 預設 | 說明 |
|---|---|---|
| `notes_dir` | `~/Documents/series-vocab/` | 詞庫與牌組檔存放位置，Obsidian 用戶可填 vault 內路徑 |
| `native_language` | 繁體中文 | 釋義與譯文語言 |
| `words_per_episode` | 30 | 每集詞數 |
| `reading_level` / `listening_level` | A2-B1 / B1-B2 | 你的程度，選詞難度略高於此 |
| `c1_max_per_episode` | 3 | 每集 C1 以上詞數上限 |
| `slang_max_per_episode` | 3 | 每集俚語上限 |

## 常見問題

- **找不到字幕**：新劇有時搜不到，換劇名裡最獨特的一個字再試；或直接把劇本文字貼給 AI。
- **音檔失敗 / 被限流（429）**：腳本會自動重試；仍失敗的卡片退回無音檔，可稍後重跑。
- **想略過音檔**：對 AI 說「這次不要音檔」，或手動執行 `python3 -I gen_deck.py data.json --no-audio`。
- **Anki 沒有自動跳出匯入視窗**：手動雙擊 `.apkg` 檔，或 Anki → 檔案 → 匯入。
- **自訂卡片外觀**：改 `anki/style.css`、`anki/front.html`、`anki/back.html`，下次產生的牌組就會套用；已匯入的卡片要在 Anki 的「管理筆記類型」裡改。

## 隱私與版權

- 發音使用 gTTS，會把單字與原句文字送到 Google 的 TTS 服務。
- 字幕與劇本來自公開網頁，僅供個人學習；產出只保留選出的例句，不保存整集劇本。

## 與上游的差異

- 每集約 30 個詞（可設定），依程度過濾難度，C1 與俚語有上限，過時俚語不收
- 跨集、跨劇去重詞庫；多義詞僅在出現新語境時才再收
- `gen_deck.py` 負責驗證與打包（重複詞、缺標記、重複原句會中止），不讓模型手寫卡片檔
- 一個 `.apkg` 搞定：筆記類型、卡片、樣式、音檔全包，不用手動匯入兩次或搬 mp3
- 卡片放美音音檔，不放音標；每集一個 Anki 子牌組（`追劇英語::劇名::SxxExx`）

## Credits & License

基於 [pyang5166/gbro-series-vocab](https://github.com/pyang5166/gbro-series-vocab)（MIT © 狗哥笔记）修改，新增去重詞庫、`gen_deck.py`、發音音檔與 Anki 牌組打包等功能。

MIT License，見 [LICENSE](LICENSE)。

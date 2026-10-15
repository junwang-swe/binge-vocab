# binge-vocab · 追劇學英語

給劇名 + 集數，AI 自動找該集字幕，挑出約 30 個值得學的詞彙短語（短語動詞、習語、B1-B2 實用詞、少量俚語），產出單一 `.apkg` 牌組檔（卡片、樣式、美音發音音檔全包在裡面），雙擊就匯入 Anki，不用另外設定筆記類型或搬音檔。學過的詞會記進詞庫，跨集、跨劇自動去重。

適用於 Claude Code，或任何支援自訂 skill 的 AI agent。不需要 API key。

## 安裝（交給 AI 就好）

你需要：

- 一個在你電腦上執行的 AI agent（例如 [Claude Code](https://claude.com/claude-code) 桌面版或 CLI）
- [Anki](https://apps.ankiweb.net/)（用來背卡片，先下載安裝）

對你的 AI 貼上這段，它會安裝、問你幾個問題，然後直接帶你跑第一集，不用重開：

```
請幫我安裝並開始使用這個英文學習 skill：https://github.com/heartwar9420/binge-vocab
請照 README 的「給 AI 的安裝指引」做：先問我英文程度等設定，裝好後不要叫我重開，直接問我想學哪部劇的哪一集。
```

### 給 AI 的安裝指引

（以下是寫給 AI agent 的步驟，用戶不需要看。）

1. 把 repo clone 到 skills 目錄（Claude Code 為 `~/.claude/skills/binge-vocab`；其他 agent 放它的 skills 目錄）。
2. **先問用戶**（一次問完，每題附預設，用戶說「都用預設」就全用預設）：
   - 資料存哪個資料夾（預設 `~/Documents/series-vocab/`）
   - 釋義語言（預設繁體中文）
   - 目前英文程度（用白話選項，不要問 CEFR 代號）：剛入門 → `A2`；中級、看劇要靠字幕 → `B1`；中高級、多半聽得懂 → `B2`；進階 → `C1`；接近母語、想學罕見詞 → `C2`
   - 想不想學俚語：不要 `none` / 少量 `few` / 多一點 `many`
   - 每集想學幾個詞（預設 30）
3. 執行 `python3 setup.py --notes-dir <資料夾> --set native_language=<語言> --set level=<程度> --set slang=<偏好> --set words_per_episode=<數字>`（會建 venv、裝 genanki 與 gTTS、寫入 `config.md`）。
4. 提醒用戶先安裝 Anki。
5. **不要叫用戶重開 session**：若 skill 還沒被載入，直接讀 `SKILL.md`，照裡面的流程處理用戶接下來的第一次請求；問用戶「想學哪部劇的哪一集？」並直接開始。

<details>
<summary>想自己手動安裝</summary>

```bash
git clone https://github.com/heartwar9420/binge-vocab.git ~/.claude/skills/binge-vocab
cd ~/.claude/skills/binge-vocab
python3 setup.py --notes-dir ~/Documents/series-vocab/ --set level=B1 --set slang=few
```

`setup.py` 可重複執行；不要發音音檔可加 `--no-audio`。

</details>

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

### 一次處理多集

可以一次說「追劇學英語 Stranger Things S01E01–S01E10」，AI 會把每集的詞條一起交給 `gen_deck.py`，打包成**單一 `.apkg`**（每集一個子牌組），只匯入一次。
後面的集數會自動避開前面集數已選的詞；任何一集有錯誤，整批不會寫入。檔案在 `{notes_dir}/batch/`。音檔要逐個產生，10 集需要幾分鐘。

### 卡片長相

- 正面：單字 + 原句（目標詞螢光標示），自動播單字
- 背面：難度標籤、釋義、原句、譯文，自動播原句

## 建議的 Anki 設定：每日新卡張數

Anki 預設每天只出 **20 張**新卡，一集約 30 張就要分兩天才出完，一次匯入多集更會排很久。
這個 skill 的用法是「看劇前先把這集的詞過一遍」，所以建議把每日新卡張數調到**不小於每集詞數**（例如 50）：

牌組列表 → 牌組右邊的齒輪 → 選項 → **每日上限** → 「每日新卡片張數」。

注意這個設定屬於牌組選項的預設組，通常會同時影響你其他牌組；不想動它的話，可以替「追劇英語」牌組另外建立一個設定組再調整。這個專案不會自動改你的 Anki 設定。

## 選用：簡化評分按鈕

學詞彙不需要 Again / Hard / Good / Easy 四個按鈕，只要「記得 / 不記得」就夠。可以在 Anki 安裝第三方外掛 **PassFail 2**（外掛代碼 `876946123`，工具 → 外掛程式 → 取得外掛），把按鈕簡化成 Fail / Pass 兩個。
這是別人的外掛，與本專案無關，是否安裝由你決定。

## 設定（config.md）

| 欄位 | 預設 | 說明 |
|---|---|---|
| `notes_dir` | `~/Documents/series-vocab/` | 詞庫與牌組檔存放位置，Obsidian 用戶可填 vault 內路徑 |
| `native_language` | 繁體中文 | 釋義與譯文語言 |
| `level` | B1 | 你的英文程度：A2 入門 / B1 中級 / B2 中高級 / C1 進階 / C2 接近母語；選詞難度會略高於此 |
| `slang` | few | 俚語：`none` 不要 / `few` 少量 / `many` 多一點 |
| `words_per_episode` | 30 | 每集詞數 |

第一次使用時 AI 會用白話問你這些，之後隨時可以對它說「我程度變好了」「不要俚語」「每集改 20 個」，它會幫你改。進階用戶可在 `config.md` 加 `c1_max_per_episode`、`slang_max_per_episode` 直接覆寫換算結果。

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

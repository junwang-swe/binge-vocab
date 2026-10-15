---
name: gbro-series-vocab
description: 追劇學英語 / Learn English vocabulary from TV series. 用戶給出劇名+集數（如「追劇學英語 Breaking Bad S02E03」），自動找該集字幕/劇本，提取約 30 個詞彙短語（自動比對歷史筆記排除重複單字，僅在出現全新語境/多義詞時收錄），生成 Anki 導入 CSV。觸發詞：「追劇學英語」「劇學英語」「series vocab」「learn english from」+ 劇名集數。僅處理英美劇單集，不處理 YouTube 影片或一般翻譯請求。
---

# gbro-series-vocab · 追劇學英語（含跨集/跨劇智慧去重）

幫用戶從一集英美劇中高效提取詞彙，自動排除過去已學過的重複單字，輸出可直接匯入 Anki 的閃卡 CSV（含美音發音音檔）。

---

## 首次使用（配置）

skill 目錄下沒有 `config.md` 時，先確認以下配置並寫入 `config.md`：

1. **資料保存目錄**（`notes_dir`）：預設 `~/Documents/series-vocab/`；Obsidian 用戶可填 vault 內的路徑
2. **釋義語言**（`native_language`）：預設繁體中文

可直接複製範本：`cp config.example.md config.md`。格式：

```markdown
notes_dir: ~/Documents/series-vocab/
native_language: 繁體中文
words_per_episode: 30
reading_level: A2-B1
listening_level: B1-B2
c1_max_per_episode: 3
slang_max_per_episode: 3
```

程度與上限欄位為選填，缺少時以 B1-B2 為主、C1 與俚語各上限 3 個處理。

---

## 輸入解析

用戶會說類似：`追劇學英語 Breaking Bad S02E03`

提取：
- **劇名**：英文名（如 Breaking Bad）
- **集數**：SxxExx 格式 → 解析為 season=2, episode=3

---

## 第一步：找字幕/劇本

按順序嘗試，找到即停止。

### 方法 A：Springfield Springfield（老劇首選）

slug 規則：劇名轉小寫，空格換連字符，**去掉所有非字母數字和連字符的字符**（撇號、冒號、逗號、句點等），連續連字符合併為一個。例如 `Grey's Anatomy` → `greys-anatomy`，`It's Always Sunny in Philadelphia` → `its-always-sunny-in-philadelphia`。

```bash
SHOW_SLUG=$(echo "Grey's Anatomy" | tr '[:upper:]' '[:lower:]' | tr ' ' '-' | sed -E 's/[^a-z0-9-]//g; s/-+/-/g')
curl -sL "https://r.jina.ai/https://www.springfieldspringfield.co.uk/view_episode_scripts.php?tv-show=${SHOW_SLUG}&episode=s02e03"
```

**判斷成功（兩條必須同時滿足）**：
1. 頁面標題含劇名（找不到該劇時網站返回的錯誤頁標題只有集數沒有劇名，且正文只剩導航連結）
2. 正文含大量對話行（連續的口語句子），而非以 `[連結](url)` 為主的導航內容

**注意**：Springfield 已基本停更，2023 年後的新劇（如 The Pitt、Severance、White Lotus S3）都沒有收錄。方法 A 失敗一次就果斷轉方法 B，不要反覆試。

### 方法 B：subslikescript 站內搜尋（新劇首選）

subslikescript 持續收錄新劇，但直接 curl 會被 JS 驗證碼擋住，**每一步都必須經 r.jina.ai 抓取**。三步走：

```bash
# 1. 站內搜尋，拿劇集頁 URL（形如 /series/{Name}-{id}）
curl -sL "https://r.jina.ai/https://subslikescript.com/search?q={關鍵詞}"

# 2. 抓劇集頁，找目標集連結（形如 /series/{Name}-{id}/season-{s}/episode-{e}-{集標題}）
#    單集 URL 末尾帶集標題，無法直接拼出，必須從劇集頁拿
curl -sL "https://r.jina.ai/https://subslikescript.com/series/{Name}-{id}"

# 3. 抓單集正文
curl -sL "https://r.jina.ai/{單集URL}"
```

注意事項：
- 搜尋是按詞匹配的，全名可能搜不到：`The Pitt` 無結果，搜 `Pitt` 才命中。失敗時去掉 The/標點，用劇名裡最獨特的一個詞重搜
- 從 markdown 連結裡抽出的 URL 可能帶尾部空格，拼給 r.jina.ai 前先修剪
- 同名劇按年份區分，選年份對的那個

### 方法 C：通用 WebSearch

`"{劇名}" "S{xx}E{xx}" transcript script site:transcripts.foreverdreaming.org OR site:subslikescript.com OR site:springfieldspringfield.co.uk`

劇集的 Fandom Wiki transcript 頁也是可靠來源。

### 方法 D：直連兜底（r.jina.ai 不可用時，僅限 Springfield）

```bash
curl -sL "https://www.springfieldspringfield.co.uk/view_episode_scripts.php?tv-show=${SHOW_SLUG}&episode=s02e03" \
  | sed -n '/class="scrolling-script-container"/,/<\/div>/p' \
  | sed -E 's/<br>/\n/g; s/<[^>]+>//g' \
  | sed '/^[[:space:]]*$/d'
```

### 找不到時

告訴用戶：「未找到《{劇名}》第{season}季第{episode}集的字幕，請從網上複製劇本文字後發給我，我繼續處理。」

---

## 第二步：提取詞彙 — 約 30 個（含去重過濾）

### 1. 歷史詞庫檢索與去重機制

為了避免用戶在看不同集數或不同美劇時反覆刷到同一單字，在選詞前執行：

1. **讀取已學清單**：
   - 檢查 `{notes_dir}/learned_vocab.md` 是否存在。
   - 若存在，讀取所有以 `- ` 開頭的行提取單字列表。
   - 若不存在，視為尚無已學詞彙（第一次執行後由腳本建立）。
2. **去重與多義詞判定標準**：
   - **完全排除**：若該詞/短語已在 `learned_vocab.md` 中，且在當集中的語義、詞性與常見用法相同，**一律跳過，改挑其他詞彙**。
   - **多義詞例外收錄**：只有當該單字在當集中出現了**完全不同的核心語義、罕見詞性、或特殊的習語/短語動詞搭配**（例如先前學過名詞 *bank*（銀行），當集出現動詞 *bank on*（寄望於）；或先前學過 *run*（跑），當集出現 *run for office*（競選）），才允許再次收錄，並在釋義後方標註 `[新語境/新用法]`。
   - **單集內唯一**：相同單字/短語在該集只出現一次，相同英文原句只保留一條。

### 2. 提取標準（按優先級，總數 `words_per_episode`，預設 30）

1. **Phrasal verbs**：get away with、pull off、cut it out 這類動詞短語
2. **習語和固定搭配**：字面意思和實際意思不同的表達
3. **俚語/口語**：字典查不到準確語境的詞
4. **B1-B2 級實用詞彙**：跳過 hello、sorry 等基礎詞，但真實場景高頻出現

### 3. 難度與時效過濾（依 `config.md` 的程度設定）

目標程度取自 `config.md`（`reading_level` / `listening_level`）；詞彙難度以略高於用戶現有程度（i+1）為準。

- **難度比例**：以 B1-B2 為主（約八成）；A2 只收實用的短語動詞和習語；**C1 每集上限 `c1_max_per_episode`（預設 3）**，只收高頻詞；C2 一律不收。
- **過時俚語一律不收**：例如 80 年代用語（totally tubular、bitchin'）、老派戲謔語（ladies and germs）、過時或帶冒犯意味的說法（loony bin、spazzy）、地區性老說法（pollywog 這類有標準詞 tadpole 的）。判斷標準：現代母語者日常是否還會自然使用。
- **現代仍在用的粗話/俚語**：可收，每集上限 `slang_max_per_episode`（預設 3），標 `[Slang 俚語]`，用於「聽得懂」，不鼓勵主動使用。
- **數量補足**：被過濾後不足 `words_per_episode` 時，從 B1-B2 詞彙補滿，不要用 C1 湊數。
- **難度標籤是估計**：俚語/習語沒有官方 CEFR 分級，標籤為模型判斷，非字典正式分級。

每個詞條格式：
```
序號. 詞/短語 | CEFR難度標籤 | 釋義（用戶母語） | 原句（原句中的目標詞加粗） | 原句譯文（用戶母語）
```
- **難度標籤**：標註 CEFR 難度或類型，如 `[A2]`, `[B1]`, `[B2]`, `[C1]`, `[B2 習語]`, `[Slang 俚語]`。
- **原句規則**：直接從劇本中找原句，原句中的目標單字片語需以 `**` 加粗，以配合 Obsidian 螢光高亮樣式。

**例句規則**：直接從劇本中找原句，不要自己造句。

---

## 第三步：用腳本生成 Anki CSV 並更新詞庫（必走，禁止手寫 CSV）

CSV 的引號轉義、HTML 卡片排版、去重與詞庫更新全部交給 skill 目錄下的 `gen_csv.py`，不要自己手寫 CSV（容易寫壞引號導致 Anki 匯入失敗，格式也會在不同對話間漂移）。

1. 把選好的詞條寫成 JSON 暫存檔（放在 scratchpad / 系統暫存目錄，不放進 skill 或詞彙庫）：

```json
{
  "show": "Stranger Things",
  "episode": "S02E10",
  "entries": [
    {"word": "under attack", "level": "B2",
     "def": "遭受攻擊", "sentence": "We're **under attack**.", "zh": "我們遭到攻擊了。"}
  ]
}
```

- `sentence` 內目標詞用 `**` 包起來（腳本轉成 `<mark>` 螢光標示）；原句取自劇本，一句只收一條。
- `level` 用第二步的標籤（`B1`、`B2 習語`、`C1`、`Slang 俚語` 等）。
- 詞已在 `learned_vocab.md` 但確屬新語境/新用法時，才在該詞條加 `"new_context": true`。

2. 先檢查再寫入：

```bash
python3 -I {skill_dir}/gen_csv.py data.json --dry-run   # 只檢查
python3 -I {skill_dir}/gen_csv.py data.json             # 通過後寫入
```

腳本會：從 `config.md` 取 `{notes_dir}`；檢查重複詞、已學詞、缺 `**` 標記、同一原句重複（硬性錯誤，出錯就中止且不寫任何檔案）；對 C1 / 俚語超過上限、詞數偏離 `words_per_episode` 發出警告；產生美音發音音檔（gTTS，單字與原句各一個 mp3，存 `{notes_dir}/{劇名}/Anki/media/` 並複製進 Anki 的 `collection.media`；卡片不再放音標，正面自動播單字、背面自動播原句；個別音檔失敗只警告，該卡退回無音檔；`--no-audio` 可略過）；寫出 `{notes_dir}/{劇名}/Anki/anki-{劇名slug}-{SxxExx}.csv`（牌組檔頭為 `追劇英語::{劇名}::{SxxExx}`，欄位為 `Wordwise` 筆記類型的 7 欄，需先在 Anki 建立，見 README 的「安裝」）；把詞條（小寫）併入 `{notes_dir}/learned_vocab.md` 並更新 `updated:` 日期。

---

## 完成回覆格式

```
{劇名} {SxxExx} 詞彙提取完成

共提取 {N} 個詞條（已自動比對歷史詞庫排除重複詞）
Anki CSV：{notes_dir}/{劇名}/Anki/{csv文件名}
歷史詞庫：已更新至 {notes_dir}/learned_vocab.md

導入 Anki：File → Import → 選 CSV → Import 即可
（牌組「追劇英語::{劇名}::{SxxExx}」和正反面映射已在文件頭設好，無需手動調整）

建議：先花 10 分鐘過一遍詞彙，再看這集。
```

---

## 版權邊界

字幕/劇本內容來自公開網頁，僅供用戶個人學習使用；不要把整集劇本原文寫入產出檔案（CSV 裡只保留選出的例句）。

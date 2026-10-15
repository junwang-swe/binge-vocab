#!/usr/bin/env python3
"""binge-vocab 一鍵安裝（可重複執行）：建立 venv、安裝 genanki / gTTS、建立 config.md、檢查環境。

用法：
    python3 setup.py [--notes-dir DIR] [--no-audio] [--venv DIR]

- --notes-dir：詞庫與牌組檔的存放位置（寫進 config.md），預設 ~/Documents/series-vocab/
- --no-audio：只裝 genanki，不裝 gTTS（不要發音音檔時用）
- --set KEY=VALUE：寫入或更新 config.md 的欄位，可重複（例如 --set level=B2 --set slang=none）
- --venv：自訂 venv 位置（預設 ~/.local/share/binge-vocab/venv；自訂時要設環境變數 BINGE_PYTHON 指向該 python）
"""
import argparse
import re
import subprocess
import sys
import venv
from pathlib import Path

HERE = Path(__file__).resolve().parent
DEFAULT_VENV = Path.home() / ".local/share/binge-vocab/venv"


def venv_python(d):
    return d / ("Scripts/python.exe" if sys.platform == "win32" else "bin/python")


def run(cmd):
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        sys.exit(f"失敗：{' '.join(map(str, cmd))}\n{r.stderr.strip()[-600:]}")
    return r.stdout


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--notes-dir")
    ap.add_argument("--set", action="append", default=[], metavar="KEY=VALUE")
    ap.add_argument("--no-audio", action="store_true")
    ap.add_argument("--venv", default=str(DEFAULT_VENV))
    a = ap.parse_args()

    if sys.version_info < (3, 8):
        sys.exit(f"需要 Python 3.8 以上，目前是 {sys.version.split()[0]}")

    vdir = Path(a.venv).expanduser()
    py = venv_python(vdir)
    if not py.exists():
        print(f"建立 venv：{vdir}")
        venv.EnvBuilder(with_pip=True).create(vdir)
    pkgs = ["genanki"] + ([] if a.no_audio else ["gTTS"])
    print(f"安裝套件：{' '.join(pkgs)}")
    run([str(py), "-m", "pip", "install", "-q", *pkgs])

    cfg = HERE / "config.md"
    if not cfg.exists():
        cfg.write_text((HERE / "config.example.md").read_text(encoding="utf-8"), encoding="utf-8")
        print("已建立 config.md")
    if a.notes_dir:
        text = cfg.read_text(encoding="utf-8")
        text = re.sub(r"^notes_dir:.*$", lambda _: f"notes_dir: {a.notes_dir}", text, flags=re.M)
        cfg.write_text(text, encoding="utf-8")
    for kv in a.set:
        k, _, v = kv.partition("=")
        text = cfg.read_text(encoding="utf-8")
        if re.search(rf"^{re.escape(k)}:", text, re.M):
            text = re.sub(rf"^{re.escape(k)}:.*$", lambda _: f"{k}: {v}", text, flags=re.M)
        else:
            text = text.rstrip("\n") + f"\n{k}: {v}\n"
        cfg.write_text(text, encoding="utf-8")
    m = re.search(r"^notes_dir:\s*(.+?)\s*$", cfg.read_text(encoding="utf-8"), re.M)
    notes_dir = Path(m.group(1)).expanduser()
    notes_dir.mkdir(parents=True, exist_ok=True)

    mods = "genanki" + ("" if a.no_audio else ", gtts")
    run([str(py), "-W", "ignore", "-c", f"import {mods}"])
    print(f"\n安裝完成\n  資料目錄：{notes_dir}\n  設定檔：{cfg}")
    if vdir != DEFAULT_VENV:
        print(f"  注意：venv 不在預設位置，使用前請設定環境變數 BINGE_PYTHON={py}")
    configured = re.search(r"^level:", cfg.read_text(encoding="utf-8"), re.M)
    if not configured:
        print("\n【給 AI agent】config.md 還沒有 level（英文程度）。請先用白話問用戶程度、俚語偏好、每集詞數，"
              "再用 `python3 setup.py --set level=... --set slang=... --set words_per_episode=...` 寫入"
              "（問法見 SKILL.md「首次使用」）。")
    print("\n不需要重開 session：若 binge-vocab 尚未被載入，請直接讀取 SKILL.md 並照著處理用戶的第一次請求。")
    print("接著對 AI 說：追劇學英語 劇名 S01E01")


if __name__ == "__main__":
    main()

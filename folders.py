"""画像フォルダを選びやすくする。OS のフォルダ選択画面を開く、よくある画像フォルダの候補を出す。

サーバーは使う人と同じ PC で動くので、サーバー側から選択画面を開ける。
"""
import os
import shutil
import subprocess
import sys
from pathlib import Path

PICK_TITLE = "画像フォルダを選んでください"


def pick_folder() -> str | None:
    """OS のフォルダ選択画面を開き、選ばれたフォルダを返す。やめたら None。開けなければ RuntimeError。"""
    if sys.platform == "win32":
        # Windows に最初から入っている PowerShell と .NET の画面を使う(追加のインストール不要)
        ps = (
            "[Console]::OutputEncoding = [Text.Encoding]::UTF8;"
            "Add-Type -AssemblyName System.Windows.Forms;"
            "$f = New-Object System.Windows.Forms.FolderBrowserDialog;"
            f"$f.Description = '{PICK_TITLE}'; $f.ShowNewFolderButton = $false;"
            "$o = New-Object System.Windows.Forms.Form -Property @{TopMost = $true};"  # ブラウザの裏に隠れないように
            "if ($f.ShowDialog($o) -eq 'OK') { $f.SelectedPath }"
        )
        cmd = ["powershell", "-NoProfile", "-STA", "-Command", ps]
    elif sys.platform == "darwin":
        cmd = ["osascript", "-e", f'POSIX path of (choose folder with prompt "{PICK_TITLE}")']
    elif shutil.which("zenity"):
        cmd = ["zenity", "--file-selection", "--directory", f"--title={PICK_TITLE}"]
    elif shutil.which("kdialog"):
        cmd = ["kdialog", "--getexistingdirectory", str(Path.home()), "--title", PICK_TITLE]
    else:
        raise RuntimeError("フォルダ選択画面を開けません(zenity か kdialog を入れてください)")
    r = subprocess.run(cmd, capture_output=True)
    path = r.stdout.decode("utf-8", errors="replace").strip()
    return path or None


def suggestions() -> list[str]:
    """よくある画像フォルダのうち、実際にあるものを返す。"""
    home = Path.home()
    cands = []
    if sys.platform == "win32":
        prof = Path(os.environ.get("USERPROFILE", home))
        onedrive = os.environ.get("OneDrive")
        cands += [prof / "Pictures"]
        if onedrive:
            cands += [Path(onedrive) / "Pictures", Path(onedrive) / "画像"]
        cands += [prof / "Desktop", prof / "Downloads"]
    else:
        # Linux はフォルダ名が言語で変わる(例: ~/ピクチャ)ので、xdg-user-dir で調べる
        for key in ("PICTURES", "DESKTOP", "DOWNLOAD"):
            try:
                p = subprocess.run(["xdg-user-dir", key], capture_output=True, text=True, timeout=2).stdout.strip()
                if p and p != str(home):
                    cands.append(Path(p))
            except Exception:
                pass
        cands += [home / "Pictures", home / "画像", home / "Desktop", home / "Downloads"]
    seen, out = set(), []
    for p in cands:
        s = str(p)
        if s not in seen and p.is_dir():
            seen.add(s)
            out.append(s)
    return out

"""image_list を起動して、ブラウザで画面を開くランチャー。

    .venv\\Scripts\\python.exe launch.py             起動する
    .venv\\Scripts\\python.exe launch.py --shortcut  デスクトップにアイコンを作る (Windows)

run.bat / run.sh で起動する従来の方法はそのまま使える。このランチャーは run.bat と同じ
環境設定でサーバーを立ち上げ、待ち受けが始まったら既定のブラウザで画面を開く。

サーバーはこのプロセス自身の中で動かす (子プロセスを作らない) ので、
この窓を閉じるか Ctrl+C を押せば、それだけで完全に止まる。

設定は run.bat と同じ環境変数 (IMAGE_ROOTS、EMBED_THREADS、CUDA_VISIBLE_DEVICES など) で
変える。アイコンから起動すると環境変数を渡しにくいので、このフォルダの launch.env
(git 管理外) に KEY=VALUE の形で書いてもよい。
"""

from __future__ import annotations

import argparse
import os
import socket
import subprocess
import sys
import threading
import time
import webbrowser
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
LOCAL_ENV_FILE = BASE_DIR / "launch.env"

SHORTCUT_NAME = "画像検索"
SHORTCUT_DESCRIPTION = "image_list - PC内の画像を文章や画像で探す"
SHORTCUT_ICON = BASE_DIR / "icon.ico"


def load_local_env() -> None:
    """launch.env に書いた KEY=VALUE を環境変数として読み込む。既に設定済みの値が優先。"""
    if not LOCAL_ENV_FILE.exists():
        return
    for raw in LOCAL_ENV_FILE.read_text(encoding="utf-8-sig").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip("\"'"))


load_local_env()

PORT = int(os.environ.setdefault("PORT", "7870"))
URL = f"http://127.0.0.1:{PORT}/"

# torch を読み込む前に決めておく必要があるので、import より先に設定する (run.bat と同じ)。
if not os.environ.get("CUDA_VISIBLE_DEVICES"):
    # GPU を使うときは CUDA_VISIBLE_DEVICES=0 を設定する。
    os.environ["CUDA_VISIBLE_DEVICES"] = "-1"
os.environ.setdefault("PYTHONUTF8", "1")
os.environ.setdefault("EMBED_THREADS", "8")
os.environ.setdefault("OMP_NUM_THREADS", os.environ["EMBED_THREADS"])

STARTUP_TIMEOUT_SECONDS = float(os.getenv("STARTUP_TIMEOUT_SECONDS", "600"))


def port_is_open() -> bool:
    try:
        with socket.create_connection(("127.0.0.1", PORT), timeout=0.5):
            return True
    except OSError:
        return False


def open_browser_when_ready() -> None:
    deadline = time.monotonic() + STARTUP_TIMEOUT_SECONDS
    while time.monotonic() < deadline:
        if port_is_open():
            print(f"\nブラウザで {URL} を開きます。", flush=True)
            webbrowser.open(URL)
            return
        time.sleep(1.0)
    print(f"\n{STARTUP_TIMEOUT_SECONDS:.0f} 秒以内に {PORT} が開きませんでした。", flush=True)


def create_desktop_shortcut() -> int:
    """デスクトップに、このランチャーを起動するアイコンを作る (Windows のみ)。"""
    if sys.platform != "win32":
        print("デスクトップのアイコン作成は Windows だけに対応しています。")
        return 1

    venv_python = BASE_DIR / ".venv" / "Scripts" / "python.exe"
    target = venv_python if venv_python.exists() else Path(sys.executable)
    # 値は環境変数で渡す。PowerShell の引用符の扱いや、日本語の名前の文字化けを避けられる。
    script = (
        "[Console]::OutputEncoding = [Text.Encoding]::UTF8;"
        "$desktop = [Environment]::GetFolderPath('Desktop');"
        "$lnk = (New-Object -ComObject WScript.Shell).CreateShortcut((Join-Path $desktop $env:SC_NAME));"
        "$lnk.TargetPath = $env:SC_TARGET; $lnk.Arguments = $env:SC_ARGS;"
        "$lnk.WorkingDirectory = $env:SC_CWD; $lnk.IconLocation = $env:SC_ICON;"
        "$lnk.Description = $env:SC_DESC; $lnk.Save(); Write-Output $lnk.FullName"
    )
    env = dict(
        os.environ,
        SC_NAME=f"{SHORTCUT_NAME}.lnk",
        SC_TARGET=str(target),
        SC_ARGS=f'"{Path(__file__).resolve().relative_to(BASE_DIR)}"',
        SC_CWD=str(BASE_DIR),
        SC_ICON=f"{SHORTCUT_ICON},0",
        SC_DESC=SHORTCUT_DESCRIPTION,
    )
    result = subprocess.run(
        ["powershell", "-NoProfile", "-NonInteractive", "-Command", script],
        env=env,
        capture_output=True,
    )
    if result.returncode != 0:
        print("アイコンを作れませんでした。")
        print(result.stderr.decode("utf-8", errors="replace").strip())
        return 1
    print(f"デスクトップにアイコンを作りました: {result.stdout.decode('utf-8', errors='replace').strip()}")
    return 0


def run() -> int:
    if port_is_open():
        # 既に起動しているものがあれば、二重に立ち上げずに画面だけ開く。
        print(f"{PORT} は既に待受中です。ブラウザで {URL} を開きます。")
        webbrowser.open(URL)
        return 0

    os.chdir(BASE_DIR)
    sys.path.insert(0, str(BASE_DIR))

    device = "GPU" if os.environ["CUDA_VISIBLE_DEVICES"] != "-1" else "CPU"
    print("image_list を起動しています。")
    print(f"  実行: {device} / スレッド {os.environ['EMBED_THREADS']} / ポート {PORT}")
    print("  初回と索引の更新には時間がかかります。")
    print("  この窓を閉じると停止します。")
    print()

    threading.Thread(target=open_browser_when_ready, daemon=True).start()

    import uvicorn

    uvicorn.run("server:app", host="127.0.0.1", port=PORT)
    return 0


def main() -> int:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(errors="replace")
        except (AttributeError, ValueError):
            pass

    parser = argparse.ArgumentParser(description="image_list を起動してブラウザで開く")
    parser.add_argument("--shortcut", action="store_true", help="デスクトップに起動用のアイコンを作る (Windows)")
    args = parser.parse_args()
    if args.shortcut:
        return create_desktop_shortcut()
    return run()


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        sys.exit(0)
    except SystemExit:
        raise
    except BaseException:
        # アイコンから起動したときに、エラー表示ごと窓が一瞬で消えないようにする。
        import traceback

        traceback.print_exc()
        print()
        print("起動中にエラーが発生しました。Enter キーで終了します。")
        try:
            input()
        except EOFError:
            pass
        sys.exit(1)

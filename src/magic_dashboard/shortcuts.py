from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from .storage import Shortcut, app_data_dir


ICON_DIR = "icons"
ICON_SIZE = 48


def shortcut_name(path: str | Path) -> str:
    return Path(path).stem


def find_shortcuts(folder: str | Path) -> list[Path]:
    return sorted(Path(folder).rglob("*.lnk"), key=lambda item: str(item).lower())


def launch_shortcut(path: str) -> None:
    if sys.platform != "win32":
        raise RuntimeError("Launching Windows shortcuts is only supported on Windows.")
    os.startfile(path)  # type: ignore[attr-defined]


def build_shortcut(path: str | Path, group: str, order: int) -> Shortcut:
    shortcut_path = Path(path)
    return Shortcut(path=str(shortcut_path), name=shortcut_name(shortcut_path), group=group, order=order)


def cache_icon(shortcut: Shortcut) -> str | None:
    """Best-effort icon cache. The launcher works even when icon extraction fails."""
    if sys.platform != "win32":
        return None

    try:
        from win32com.client import Dispatch  # type: ignore
    except Exception:
        return None

    try:
        shell = Dispatch("WScript.Shell")
        link = shell.CreateShortcut(shortcut.path)
        icon_location = str(link.IconLocation or "").strip()
    except Exception:
        return None

    if not icon_location:
        return None

    icon_source, _, icon_index_text = icon_location.partition(",")
    icon_source = icon_source.strip().strip('"')
    if not icon_source:
        return None

    source_path = Path(os.path.expandvars(icon_source))
    if not source_path.exists():
        return None

    target_dir = app_data_dir() / ICON_DIR
    target_dir.mkdir(parents=True, exist_ok=True)
    target = target_dir / f"{shortcut.id}.png"

    if source_path.suffix.lower() == ".ico":
        return _convert_ico_to_png(source_path, target)

    try:
        icon_index = int(icon_index_text.strip() or "0")
    except ValueError:
        icon_index = 0
    return _extract_icon_to_png(source_path, icon_index, target)


def _convert_ico_to_png(source: Path, target: Path) -> str | None:
    try:
        from PIL import Image

        with Image.open(source) as image:
            image.thumbnail((ICON_SIZE, ICON_SIZE))
            image.save(target, "PNG")
    except Exception:
        return None
    return str(target)


def _extract_icon_to_png(source: Path, icon_index: int, target: Path) -> str | None:
    try:
        import win32con  # type: ignore
        import win32gui  # type: ignore
        import win32ui  # type: ignore
        from PIL import Image
    except Exception:
        return None

    large_icons: list[int] = []
    small_icons: list[int] = []
    try:
        large_icons, small_icons = win32gui.ExtractIconEx(str(source), icon_index)
        icons = large_icons or small_icons
        if not icons:
            return None
        hicon = icons[0]

        hdc = win32ui.CreateDCFromHandle(win32gui.GetDC(0))
        bitmap = win32ui.CreateBitmap()
        bitmap.CreateCompatibleBitmap(hdc, ICON_SIZE, ICON_SIZE)
        bitmap_dc = hdc.CreateCompatibleDC()
        bitmap_dc.SelectObject(bitmap)
        bitmap_dc.FillSolidRect((0, 0, ICON_SIZE, ICON_SIZE), win32gui.GetSysColor(win32con.COLOR_WINDOW))
        win32gui.DrawIconEx(bitmap_dc.GetSafeHdc(), 0, 0, hicon, ICON_SIZE, ICON_SIZE, 0, None, win32con.DI_NORMAL)

        info = bitmap.GetInfo()
        bits = bitmap.GetBitmapBits(True)
        image = Image.frombuffer("RGB", (info["bmWidth"], info["bmHeight"]), bits, "raw", "BGRX", 0, 1)
        image.save(target, "PNG")
        return str(target)
    except Exception:
        return None
    finally:
        for icon in large_icons + small_icons:
            try:
                win32gui.DestroyIcon(icon)
            except Exception:
                pass


def open_config_folder() -> None:
    folder = app_data_dir()
    folder.mkdir(parents=True, exist_ok=True)
    if sys.platform == "win32":
        os.startfile(folder)  # type: ignore[attr-defined]
    else:
        subprocess.Popen(["xdg-open", str(folder)])

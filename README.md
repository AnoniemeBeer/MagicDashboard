# MagicDashboard

MagicDashboard is a lightweight Windows shortcut dashboard. Add `.lnk` files once, keep them grouped in one fast launcher, and start them through the original shortcut so configured arguments, working directories, and environment behavior stay intact.

## Run from source

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python main.py
```

## Build an exe folder

```powershell
.\build.ps1
```

The executable is written to:

```text
dist\main.dist\MagicDashboard.exe
```

Important: this is a standalone app folder. Copy the whole `dist\main.dist` folder, not only `MagicDashboard.exe`, because the exe needs the DLLs and Tk files beside it.

## Build one movable exe

```powershell
.\build-onefile.ps1
```

The single executable is written to:

```text
dist\MagicDashboard.exe
```

This is easier to move around, but endpoint security tools are more likely to inspect or block one-file executables because they unpack themselves at startup.

## Persistence

Shortcuts and groups are stored per Windows user in:

```text
%APPDATA%\MagicDashboard\shortcuts.json
```

Use the `Config` button in the app to open this folder.

## Usage

- `Add shortcuts` imports selected `.lnk` files.
- `Import folder` recursively imports `.lnk` files from a folder.
- Groups are managed from the left sidebar.
- Click a shortcut card's `Open` button to launch it.
- Use `Select` on a shortcut card before `Move up`, `Move down`, or `Remove`.

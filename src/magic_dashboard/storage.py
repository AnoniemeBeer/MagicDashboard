from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any
from uuid import uuid4


APP_NAME = "MagicDashboard"
CONFIG_FILE = "shortcuts.json"


def app_data_dir() -> Path:
    base = os.environ.get("APPDATA")
    if base:
        return Path(base) / APP_NAME
    return Path.home() / f".{APP_NAME.lower()}"


@dataclass
class Shortcut:
    path: str
    name: str
    group: str = "General"
    order: int = 0
    id: str = field(default_factory=lambda: uuid4().hex)
    icon_path: str | None = None


@dataclass
class DashboardData:
    groups: list[str] = field(default_factory=lambda: ["General"])
    shortcuts: list[Shortcut] = field(default_factory=list)


class DashboardStore:
    def __init__(self, config_path: Path | None = None) -> None:
        self.config_path = config_path or app_data_dir() / CONFIG_FILE

    def load(self) -> DashboardData:
        if not self.config_path.exists():
            return DashboardData()

        try:
            raw = json.loads(self.config_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return DashboardData()

        groups = raw.get("groups") if isinstance(raw, dict) else None
        shortcuts = raw.get("shortcuts") if isinstance(raw, dict) else None

        data = DashboardData(
            groups=[str(group) for group in groups] if isinstance(groups, list) else ["General"],
            shortcuts=[],
        )

        if isinstance(shortcuts, list):
            for index, item in enumerate(shortcuts):
                if not isinstance(item, dict):
                    continue
                path = str(item.get("path", "")).strip()
                name = str(item.get("name", "")).strip()
                if not path or not name:
                    continue
                group = str(item.get("group", "General")).strip() or "General"
                if group not in data.groups:
                    data.groups.append(group)
                data.shortcuts.append(
                    Shortcut(
                        id=str(item.get("id") or uuid4().hex),
                        path=path,
                        name=name,
                        group=group,
                        order=int(item.get("order", index)),
                        icon_path=item.get("icon_path"),
                    )
                )

        if "General" not in data.groups:
            data.groups.insert(0, "General")
        data.shortcuts.sort(key=lambda shortcut: (data.groups.index(shortcut.group), shortcut.order, shortcut.name.lower()))
        return data

    def save(self, data: DashboardData) -> None:
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        payload: dict[str, Any] = {
            "groups": data.groups,
            "shortcuts": [asdict(shortcut) for shortcut in data.shortcuts],
        }
        self.config_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


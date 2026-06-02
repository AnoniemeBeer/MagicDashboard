from __future__ import annotations

import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, simpledialog, ttk

from .shortcuts import (
    build_shortcut,
    cache_icon,
    find_shortcuts,
    is_svn_working_copy,
    launch_shortcut,
    open_config_folder,
    open_folder,
    svn_update,
)
from .storage import DashboardData, DashboardStore, Shortcut


BG = "#f5f0e8"
PANEL = "#fffaf1"
INK = "#1f2a24"
MUTED = "#69746d"
ACCENT = "#245b47"
ACCENT_DARK = "#173b30"
LINE = "#ded5c6"
WARNING = "#a5402d"
CARD_LINE = "#e6dccd"


class MagicDashboard(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("MagicDashboard")
        self.geometry("1120x760")
        self.minsize(840, 560)
        self.configure(bg=BG)

        self.store = DashboardStore()
        self.data = self.store.load()
        self.selected_group = tk.StringVar(value=self.data.groups[0] if self.data.groups else "General")
        self.search_text = tk.StringVar()
        self.icon_images: dict[str, tk.PhotoImage] = {}
        self.selected_shortcut_id: str | None = None
        self.busy_shortcut_ids: set[str] = set()

        self._configure_style()
        self._build_layout()
        self._render_groups()
        self._render_shortcuts()

    def _configure_style(self) -> None:
        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure("TFrame", background=BG)
        style.configure("Panel.TFrame", background=PANEL)
        style.configure("TLabel", background=BG, foreground=INK, font=("Segoe UI", 10))
        style.configure("Title.TLabel", background=BG, foreground=INK, font=("Segoe UI Semibold", 24))
        style.configure("Muted.TLabel", background=BG, foreground=MUTED, font=("Segoe UI", 10))
        style.configure("TButton", font=("Segoe UI Semibold", 10), padding=(14, 9), borderwidth=0)
        style.map("TButton", background=[("active", "#e5dccd")])
        style.configure("Primary.TButton", background=ACCENT, foreground="#ffffff")
        style.map("Primary.TButton", background=[("active", ACCENT_DARK)])
        style.configure("Danger.TButton", background="#f2d4cd", foreground=WARNING)

    def _build_layout(self) -> None:
        header = ttk.Frame(self, padding=(24, 22, 24, 10))
        header.pack(fill="x")

        title_area = ttk.Frame(header)
        title_area.pack(side="left", fill="x", expand=True)
        ttk.Label(title_area, text="MagicDashboard", style="Title.TLabel").pack(anchor="w")
        ttk.Label(
            title_area,
            text="A fast local launcher for Windows shortcuts that need their original startup context.",
            style="Muted.TLabel",
        ).pack(anchor="w", pady=(3, 0))

        actions = ttk.Frame(header)
        actions.pack(side="right")
        ttk.Button(actions, text="Add shortcuts", style="Primary.TButton", command=self.add_shortcuts).pack(side="left", padx=4)
        ttk.Button(actions, text="Import folder", command=self.import_folder).pack(side="left", padx=4)
        ttk.Button(actions, text="Config", command=open_config_folder).pack(side="left", padx=4)

        body = ttk.Frame(self, padding=(24, 8, 24, 24))
        body.pack(fill="both", expand=True)

        sidebar = ttk.Frame(body, style="Panel.TFrame", padding=14)
        sidebar.pack(side="left", fill="y")
        ttk.Label(sidebar, text="Groups", background=PANEL, foreground=INK, font=("Segoe UI Semibold", 12)).pack(anchor="w")

        self.group_list = tk.Listbox(
            sidebar,
            width=24,
            height=18,
            borderwidth=0,
            highlightthickness=1,
            highlightbackground=LINE,
            selectbackground=ACCENT,
            selectforeground="#ffffff",
            bg=PANEL,
            fg=INK,
            font=("Segoe UI", 11),
            activestyle="none",
        )
        self.group_list.pack(fill="y", expand=True, pady=(10, 12))
        self.group_list.bind("<<ListboxSelect>>", self.on_group_select)

        ttk.Button(sidebar, text="New group", command=self.add_group).pack(fill="x", pady=3)
        ttk.Button(sidebar, text="Rename group", command=self.rename_group).pack(fill="x", pady=3)
        ttk.Button(sidebar, text="Delete group", style="Danger.TButton", command=self.delete_group).pack(fill="x", pady=3)

        main = ttk.Frame(body, padding=(18, 0, 0, 0))
        main.pack(side="left", fill="both", expand=True)

        toolbar = ttk.Frame(main)
        toolbar.pack(fill="x", pady=(0, 12))
        search = ttk.Entry(toolbar, textvariable=self.search_text, font=("Segoe UI", 12))
        search.pack(side="left", fill="x", expand=True)
        search.insert(0, "")
        self.search_text.trace_add("write", lambda *_: self._render_shortcuts())
        ttk.Button(toolbar, text="Move up", command=lambda: self.move_selected(-1)).pack(side="left", padx=(12, 4))
        ttk.Button(toolbar, text="Move down", command=lambda: self.move_selected(1)).pack(side="left", padx=4)
        ttk.Button(toolbar, text="Remove", style="Danger.TButton", command=self.remove_selected).pack(side="left", padx=4)

        self.canvas = tk.Canvas(main, bg=BG, highlightthickness=0)
        self.canvas.pack(side="left", fill="both", expand=True)
        scrollbar = ttk.Scrollbar(main, orient="vertical", command=self.canvas.yview)
        scrollbar.pack(side="right", fill="y")
        self.canvas.configure(yscrollcommand=scrollbar.set)

        self.grid_frame = ttk.Frame(self.canvas)
        self.canvas_window = self.canvas.create_window((0, 0), window=self.grid_frame, anchor="nw")
        self.grid_frame.bind("<Configure>", self._on_grid_configure)
        self.canvas.bind("<Configure>", self._on_canvas_configure)
        self.canvas.bind_all("<MouseWheel>", self._on_mousewheel)

    def _render_groups(self) -> None:
        self.group_list.delete(0, tk.END)
        for group in self.data.groups:
            count = sum(1 for shortcut in self.data.shortcuts if shortcut.group == group)
            self.group_list.insert(tk.END, f"{group}  ({count})")

        selected = self.selected_group.get()
        if selected not in self.data.groups:
            selected = self.data.groups[0] if self.data.groups else "General"
            self.selected_group.set(selected)
        if selected in self.data.groups:
            self.group_list.selection_set(self.data.groups.index(selected))

    def _render_shortcuts(self) -> None:
        for child in self.grid_frame.winfo_children():
            child.destroy()

        shortcuts = self._visible_shortcuts()
        if not shortcuts:
            empty = ttk.Frame(self.grid_frame, padding=40)
            empty.grid(row=0, column=0, sticky="nsew")
            ttk.Label(empty, text="No shortcuts here yet", font=("Segoe UI Semibold", 18), foreground=INK).pack()
            ttk.Label(empty, text="Add shortcuts or import a folder to build your launch dashboard.", style="Muted.TLabel").pack(pady=(8, 0))
            return

        for index, shortcut in enumerate(shortcuts):
            row, col = divmod(index, 3)
            card = ShortcutCard(
                self.grid_frame,
                shortcut,
                self._load_icon(shortcut),
                self.launch,
                self.select_card,
                self.show_card_menu,
                shortcut.id in self.busy_shortcut_ids,
            )
            card.grid(row=row, column=col, sticky="nsew", padx=8, pady=8)

        for col in range(3):
            self.grid_frame.columnconfigure(col, weight=1, uniform="cards")

    def _visible_shortcuts(self) -> list[Shortcut]:
        group = self.selected_group.get()
        term = self.search_text.get().strip().lower()
        shortcuts = [shortcut for shortcut in self.data.shortcuts if shortcut.group == group]
        if term:
            shortcuts = [shortcut for shortcut in shortcuts if term in shortcut.name.lower() or term in shortcut.path.lower()]
        return sorted(shortcuts, key=lambda shortcut: (shortcut.order, shortcut.name.lower()))

    def _load_icon(self, shortcut: Shortcut) -> tk.PhotoImage | None:
        if shortcut.icon_path and shortcut.icon_path in self.icon_images:
            return self.icon_images[shortcut.icon_path]

        icon_path = shortcut.icon_path
        if not icon_path or not Path(icon_path).exists():
            icon_path = cache_icon(shortcut)
            if icon_path:
                shortcut.icon_path = icon_path
                self._save()

        if not icon_path or not Path(icon_path).exists():
            return None

        try:
            image = tk.PhotoImage(file=icon_path)
        except tk.TclError:
            return None
        self.icon_images[icon_path] = image
        return image

    def add_shortcuts(self) -> None:
        files = filedialog.askopenfilenames(title="Select Windows shortcuts", filetypes=[("Windows shortcuts", "*.lnk")])
        if files:
            self._add_shortcut_paths(files)

    def import_folder(self) -> None:
        folder = filedialog.askdirectory(title="Select a folder containing shortcuts")
        if folder:
            self._add_shortcut_paths(find_shortcuts(folder))

    def _add_shortcut_paths(self, paths: list[str] | tuple[str, ...] | list[Path]) -> None:
        group = self.selected_group.get() or "General"
        existing = {str(Path(shortcut.path)).lower() for shortcut in self.data.shortcuts}
        order = self._next_order(group)
        added = 0
        for path in paths:
            shortcut_path = Path(path)
            if shortcut_path.suffix.lower() != ".lnk" or str(shortcut_path).lower() in existing:
                continue
            self.data.shortcuts.append(build_shortcut(shortcut_path, group, order))
            existing.add(str(shortcut_path).lower())
            order += 1
            added += 1

        if added:
            self._normalize_orders(group)
            self._save()
            self._render_groups()
            self._render_shortcuts()

    def add_group(self) -> None:
        name = self._ask_group_name("New group", "Group name:")
        if not name:
            return
        self.data.groups.append(name)
        self.selected_group.set(name)
        self._save()
        self._render_groups()
        self._render_shortcuts()

    def rename_group(self) -> None:
        old = self.selected_group.get()
        if old == "General":
            messagebox.showinfo("MagicDashboard", "The General group cannot be renamed.")
            return
        name = self._ask_group_name("Rename group", "New group name:", initialvalue=old)
        if not name or name == old:
            return
        self.data.groups[self.data.groups.index(old)] = name
        for shortcut in self.data.shortcuts:
            if shortcut.group == old:
                shortcut.group = name
        self.selected_group.set(name)
        self._save()
        self._render_groups()
        self._render_shortcuts()

    def delete_group(self) -> None:
        group = self.selected_group.get()
        if group == "General":
            messagebox.showinfo("MagicDashboard", "The General group cannot be deleted.")
            return
        if not messagebox.askyesno("Delete group", f"Move shortcuts from '{group}' to General and delete the group?"):
            return
        self.data.groups.remove(group)
        for shortcut in self.data.shortcuts:
            if shortcut.group == group:
                shortcut.group = "General"
        self.selected_group.set("General")
        self._normalize_orders("General")
        self._save()
        self._render_groups()
        self._render_shortcuts()

    def _ask_group_name(self, title: str, prompt: str, initialvalue: str = "") -> str | None:
        name = simpledialog.askstring(title, prompt, initialvalue=initialvalue, parent=self)
        if name is None:
            return None
        name = name.strip()
        if not name:
            return None
        if name in self.data.groups and name != initialvalue:
            messagebox.showerror("MagicDashboard", "That group already exists.")
            return None
        return name

    def on_group_select(self, _event: tk.Event) -> None:
        selection = self.group_list.curselection()
        if not selection:
            return
        self.selected_group.set(self.data.groups[selection[0]])
        self._render_shortcuts()

    def select_card(self, shortcut: Shortcut) -> None:
        self.selected_shortcut_id = shortcut.id

    def show_card_menu(self, shortcut: Shortcut, widget: tk.Widget) -> None:
        self.select_card(shortcut)
        menu = tk.Menu(self, tearoff=False)
        source_exists = bool(shortcut.source_path and Path(shortcut.source_path).exists())

        menu.add_command(
            label="Attach source folder" if not shortcut.source_path else "Change source folder",
            command=lambda: self.set_source_folder(shortcut),
        )
        menu.add_command(
            label="Open source folder",
            command=lambda: self.open_source_folder(shortcut),
            state=tk.NORMAL if source_exists else tk.DISABLED,
        )
        menu.add_command(
            label="SVN update",
            command=lambda: self.update_source_from_svn(shortcut),
            state=tk.NORMAL if shortcut.source_path and shortcut.id not in self.busy_shortcut_ids else tk.DISABLED,
        )
        menu.add_command(
            label="Clear source folder",
            command=lambda: self.clear_source_folder(shortcut),
            state=tk.NORMAL if shortcut.source_path else tk.DISABLED,
        )

        try:
            menu.tk_popup(widget.winfo_rootx(), widget.winfo_rooty() + widget.winfo_height())
        finally:
            menu.grab_release()

    def launch(self, shortcut: Shortcut) -> None:
        try:
            launch_shortcut(shortcut.path)
        except Exception as exc:
            messagebox.showerror("Launch failed", f"Could not launch shortcut:\n{shortcut.path}\n\n{exc}")

    def set_source_folder(self, shortcut: Shortcut) -> None:
        initial_dir = shortcut.source_path or str(Path(shortcut.path).parent)
        folder = filedialog.askdirectory(title=f"Select source folder for {shortcut.name}", initialdir=initial_dir)
        if not folder:
            return
        shortcut.source_path = str(Path(folder))
        self._save()
        self._render_shortcuts()

    def open_source_folder(self, shortcut: Shortcut) -> None:
        if not shortcut.source_path:
            messagebox.showinfo("MagicDashboard", "No source folder is linked to this shortcut yet.")
            return
        folder = Path(shortcut.source_path)
        if not folder.exists():
            messagebox.showerror("MagicDashboard", f"The linked source folder no longer exists:\n{folder}")
            return
        open_folder(folder)

    def clear_source_folder(self, shortcut: Shortcut) -> None:
        if not shortcut.source_path:
            return
        if not messagebox.askyesno("Clear source folder", f"Remove the linked source folder for '{shortcut.name}'?"):
            return
        shortcut.source_path = None
        self._save()
        self._render_shortcuts()

    def update_source_from_svn(self, shortcut: Shortcut) -> None:
        if not shortcut.source_path:
            messagebox.showinfo("MagicDashboard", "Link a source folder first.")
            return

        folder = Path(shortcut.source_path)
        if not folder.exists():
            messagebox.showerror("MagicDashboard", f"The linked source folder no longer exists:\n{folder}")
            return
        if not folder.is_dir():
            messagebox.showerror("MagicDashboard", f"The linked source path is not a folder:\n{folder}")
            return
        if not is_svn_working_copy(folder):
            messagebox.showerror(
                "SVN update failed",
                f"This folder is not an SVN working copy, or SVN is not available in PATH:\n{folder}",
            )
            return

        self.busy_shortcut_ids.add(shortcut.id)
        self._render_shortcuts()

        def run_update() -> None:
            try:
                result = svn_update(folder)
            except OSError as exc:
                self.after(0, lambda: self._finish_svn_update(shortcut, None, exc))
                return
            self.after(0, lambda: self._finish_svn_update(shortcut, result, None))

        threading.Thread(target=run_update, daemon=True).start()

    def _finish_svn_update(self, shortcut: Shortcut, result, error: OSError | None) -> None:
        self.busy_shortcut_ids.discard(shortcut.id)
        self._render_shortcuts()

        if error is not None:
            messagebox.showerror("SVN update failed", f"Could not start SVN update.\n\n{error}")
            return

        assert result is not None
        output = "\n".join(part.strip() for part in [result.stdout, result.stderr] if part.strip()).strip()
        if result.returncode == 0:
            messagebox.showinfo(
                "SVN update complete",
                output or f"SVN update completed successfully for:\n{shortcut.source_path}",
            )
            return

        messagebox.showerror(
            "SVN update failed",
            output or f"SVN update failed for:\n{shortcut.source_path}",
        )

    def remove_selected(self) -> None:
        shortcut = self._selected_shortcut()
        if shortcut is None:
            messagebox.showinfo("MagicDashboard", "Select a shortcut card first.")
            return
        self.data.shortcuts = [item for item in self.data.shortcuts if item.id != shortcut.id]
        self._normalize_orders(shortcut.group)
        self._save()
        self._render_groups()
        self._render_shortcuts()

    def move_selected(self, delta: int) -> None:
        shortcut = self._selected_shortcut()
        if shortcut is None:
            messagebox.showinfo("MagicDashboard", "Select a shortcut card first.")
            return
        group_items = self._visible_shortcuts()
        try:
            index = group_items.index(shortcut)
        except ValueError:
            return
        new_index = index + delta
        if new_index < 0 or new_index >= len(group_items):
            return
        group_items[index], group_items[new_index] = group_items[new_index], group_items[index]
        for order, item in enumerate(group_items):
            item.order = order
        self._save()
        self._render_shortcuts()

    def _selected_shortcut(self) -> Shortcut | None:
        shortcut_id = getattr(self, "selected_shortcut_id", None)
        for shortcut in self.data.shortcuts:
            if shortcut.id == shortcut_id:
                return shortcut
        return None

    def _next_order(self, group: str) -> int:
        orders = [shortcut.order for shortcut in self.data.shortcuts if shortcut.group == group]
        return max(orders, default=-1) + 1

    def _normalize_orders(self, group: str) -> None:
        items = sorted([shortcut for shortcut in self.data.shortcuts if shortcut.group == group], key=lambda item: (item.order, item.name.lower()))
        for order, shortcut in enumerate(items):
            shortcut.order = order

    def _save(self) -> None:
        self.store.save(self.data)

    def _on_grid_configure(self, _event: tk.Event) -> None:
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))

    def _on_canvas_configure(self, event: tk.Event) -> None:
        self.canvas.itemconfigure(self.canvas_window, width=event.width)

    def _on_mousewheel(self, event: tk.Event) -> None:
        self.canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")


class ShortcutCard(ttk.Frame):
    def __init__(
        self,
        parent: tk.Widget,
        shortcut: Shortcut,
        icon: tk.PhotoImage | None,
        launch_callback,
        select_callback,
        menu_callback,
        is_busy: bool,
    ) -> None:
        super().__init__(parent, style="Panel.TFrame", padding=16)
        self.shortcut = shortcut
        self.launch_callback = launch_callback
        self.select_callback = select_callback
        self.menu_callback = menu_callback

        self.configure(cursor="hand2")
        header = ttk.Frame(self, style="Panel.TFrame")
        header.pack(fill="x")

        icon_area = tk.Label(self, bg=PANEL, width=64, height=64)
        icon_area.pack(in_=header, side="left", anchor="nw")
        if icon:
            icon_area.configure(image=icon)
            icon_area.image = icon
        else:
            icon_area.configure(text="↗", fg=ACCENT, font=("Segoe UI Semibold", 30))

        menu_button = tk.Button(
            header,
            text="...",
            font=("Segoe UI Semibold", 11),
            bg=PANEL,
            fg=INK,
            activebackground="#f0e6d8",
            activeforeground=INK,
            relief="flat",
            bd=0,
            highlightthickness=1,
            highlightbackground=CARD_LINE,
            padx=10,
            pady=4,
            cursor="hand2",
            command=lambda: self.menu_callback(self.shortcut, menu_button),
        )
        menu_button.pack(side="right", anchor="ne")

        tk.Label(
            self,
            text=shortcut.name,
            bg=PANEL,
            fg=INK,
            font=("Segoe UI Semibold", 13),
            wraplength=240,
            justify="left",
        ).pack(anchor="w", pady=(12, 4))
        tk.Label(
            self,
            text=shortcut.path,
            bg=PANEL,
            fg=MUTED,
            font=("Segoe UI", 8),
            wraplength=260,
            justify="left",
        ).pack(anchor="w")

        source_text = shortcut.source_path or "No source folder linked"
        source_color = ACCENT if shortcut.source_path else MUTED
        tk.Label(
            self,
            text=f"Source: {source_text}",
            bg=PANEL,
            fg=source_color,
            font=("Segoe UI", 8),
            wraplength=260,
            justify="left",
        ).pack(anchor="w", pady=(8, 0))

        if is_busy:
            tk.Label(
                self,
                text="SVN update in progress...",
                bg=PANEL,
                fg=ACCENT,
                font=("Segoe UI Semibold", 8),
            ).pack(anchor="w", pady=(8, 0))

        buttons = ttk.Frame(self, style="Panel.TFrame")
        buttons.pack(fill="x", pady=(14, 0))
        ttk.Button(buttons, text="Open", style="Primary.TButton", command=lambda: self.launch_callback(self.shortcut)).pack(
            side="left", fill="x", expand=True
        )
        ttk.Button(buttons, text="Select", command=lambda: self.select_callback(self.shortcut)).pack(side="left", padx=(8, 0))

        self._bind_launch_targets()

    def _bind_launch_targets(self) -> None:
        self.bind("<Button-1>", self._launch)
        for child in self.winfo_children():
            self._bind_recursive(child)

    def _bind_recursive(self, widget: tk.Widget) -> None:
        if isinstance(widget, (tk.Button, ttk.Button)):
            return
        widget.bind("<Button-1>", self._launch)
        for child in widget.winfo_children():
            self._bind_recursive(child)

    def _launch(self, _event: tk.Event) -> None:
        self.launch_callback(self.shortcut)


def main() -> None:
    app = MagicDashboard()
    app.mainloop()

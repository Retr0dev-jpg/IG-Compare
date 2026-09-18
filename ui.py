from __future__ import annotations

import tkinter as tk
import webbrowser
from pathlib import Path
from tkinter import filedialog, ttk

from compare import (
    APP_DIR,
    CompareError,
    CompareResult,
    analyze,
    discover_sources,
    export_usernames,
)
from i18n import t

TAB_NOT_BACK = "not_back"
TAB_YOU_DONT = "you_dont"


class App(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title(t("app_title"))
        self.minsize(720, 520)
        self.geometry("780x580")

        self.source_paths = discover_sources()
        self.result: CompareResult | None = None
        self.search_var = tk.StringVar()
        self.search_var.trace_add("write", lambda *_: self._refresh_lists())

        self._build()
        self.after(80, self._auto_analyze)

    def _build(self) -> None:
        root = ttk.Frame(self, padding=12)
        root.pack(fill=tk.BOTH, expand=True)
        root.columnconfigure(0, weight=1)
        root.rowconfigure(2, weight=1)

        stats = ttk.Frame(root)
        stats.grid(row=0, column=0, sticky="ew", pady=(0, 8))
        self.stat_labels = {}
        for column, (key, caption) in enumerate(
            (
                ("following", t("stat_following")),
                ("followers", t("stat_followers")),
                ("mutual", t("stat_mutual")),
                ("not_back", t("stat_unfollowers")),
                ("you_dont", t("stat_not_following")),
            )
        ):
            box = ttk.LabelFrame(stats, text=caption, padding=(10, 4))
            box.grid(row=0, column=column, padx=(0 if column == 0 else 6, 0), sticky="ew")
            stats.columnconfigure(column, weight=1)
            value = ttk.Label(box, text="—", font=("Segoe UI", 16, "bold"))
            value.pack()
            self.stat_labels[key] = value

        toolbar = ttk.Frame(root)
        toolbar.grid(row=1, column=0, sticky="ew", pady=(0, 8))
        toolbar.columnconfigure(3, weight=1)

        ttk.Button(toolbar, text=t("load_export"), command=self._pick_sources).grid(
            row=0, column=0, padx=(0, 6)
        )
        ttk.Button(toolbar, text=t("analyze"), command=self._analyze).grid(row=0, column=1)
        ttk.Label(toolbar, text=t("search")).grid(row=0, column=3, sticky="e", padx=(12, 6))
        ttk.Entry(toolbar, textvariable=self.search_var, width=28).grid(row=0, column=4, sticky="e")
        ttk.Button(toolbar, text=t("export_txt"), command=self._export).grid(
            row=0, column=5, padx=(8, 0)
        )

        notebook = ttk.Notebook(root)
        notebook.grid(row=2, column=0, sticky="nsew")
        self.notebook = notebook
        self.trees: dict[str, ttk.Treeview] = {}

        self._add_tab(TAB_NOT_BACK, t("tab_unfollowers"))
        self._add_tab(TAB_YOU_DONT, t("tab_not_following"))

        self.status = ttk.Label(root, text=t("ready"), anchor="w")
        self.status.grid(row=3, column=0, sticky="ew", pady=(8, 0))

    def _add_tab(self, key: str, title: str) -> None:
        frame = ttk.Frame(self.notebook, padding=4)
        self.notebook.add(frame, text=title)
        frame.columnconfigure(0, weight=1)
        frame.rowconfigure(0, weight=1)

        tree = ttk.Treeview(frame, columns=("username",), show="headings", selectmode="browse")
        tree.heading("username", text=t("username"))
        tree.column("username", width=400, anchor="w")
        scroll = ttk.Scrollbar(frame, orient=tk.VERTICAL, command=tree.yview)
        tree.configure(yscrollcommand=scroll.set)
        tree.grid(row=0, column=0, sticky="nsew")
        scroll.grid(row=0, column=1, sticky="ns")
        tree.configure(cursor="hand2")
        tree.bind("<ButtonRelease-1>", self._open_profile)
        tree.bind("<Return>", self._open_profile)
        self.trees[key] = tree

    def _open_profile(self, event: tk.Event) -> None:
        tree = event.widget
        if not isinstance(tree, ttk.Treeview):
            return

        if event.keysym == "Return":
            row = tree.focus() or (tree.selection()[0] if tree.selection() else "")
        else:
            row = tree.identify_row(event.y)
        if not row:
            return

        values = tree.item(row, "values")
        if not values:
            return

        username = str(values[0]).lstrip("@").strip()
        if not username:
            return

        webbrowser.open(f"https://www.instagram.com/{username}/")
        self._set_status(t("opening_profile", username=username))

    def _auto_analyze(self) -> None:
        if self.source_paths:
            self._analyze()
        else:
            self._set_status(t("hint_load"))

    def _pick_sources(self) -> None:
        selected = filedialog.askopenfilenames(
            title=t("dialog_load_title"),
            initialdir=APP_DIR,
            filetypes=[
                (t("filetype_export"), "*.zip *.json *.html *.htm"),
                (t("filetype_zip"), "*.zip"),
                (t("filetype_json"), "*.json"),
                (t("filetype_html"), "*.html *.htm"),
                (t("filetype_all"), "*.*"),
            ],
        )
        if not selected:
            return
        self.source_paths = [Path(path) for path in selected]
        self._analyze()

    def _analyze(self) -> None:
        try:
            self.result = analyze(self.source_paths or None)
        except CompareError as exc:
            self.result = None
            self._clear_stats()
            self._refresh_lists()
            self._set_status(str(exc))
            return

        result = self.result
        self.stat_labels["following"].configure(text=str(len(result.following)))
        self.stat_labels["followers"].configure(text=str(len(result.followers)))
        self.stat_labels["mutual"].configure(text=str(result.mutual_count))
        self.stat_labels["not_back"].configure(text=str(len(result.not_following_back)))
        self.stat_labels["you_dont"].configure(text=str(len(result.you_dont_follow)))
        self._refresh_lists()

        skipped = result.skipped_followers + result.skipped_following
        extra = t("skipped", count=skipped) if skipped else ""
        self._set_status(
            t(
                "status_files",
                followers=", ".join(result.follower_files),
                following=result.following_file,
            )
            + extra
        )

    def _clear_stats(self) -> None:
        for label in self.stat_labels.values():
            label.configure(text="—")

    def _active_tab(self) -> str:
        index = self.notebook.index(self.notebook.select())
        return TAB_NOT_BACK if index == 0 else TAB_YOU_DONT

    def _usernames_for(self, tab: str) -> list[str]:
        if self.result is None:
            return []
        if tab == TAB_NOT_BACK:
            return self.result.not_following_back
        return self.result.you_dont_follow

    def _refresh_lists(self) -> None:
        query = self.search_var.get().strip().casefold()
        for key in (TAB_NOT_BACK, TAB_YOU_DONT):
            tree = self.trees[key]
            tree.delete(*tree.get_children())
            for username in self._usernames_for(key):
                if query and query not in username.casefold():
                    continue
                tree.insert("", tk.END, values=(f"@{username}",))

    def _export(self) -> None:
        if self.result is None:
            self._set_status(t("nothing_to_export"))
            return

        tab = self._active_tab()
        if tab == TAB_NOT_BACK:
            title = t("export_title_unfollowers")
            default_name = "unfollowers.txt"
            usernames = self.result.not_following_back
        else:
            title = t("export_title_not_following")
            default_name = "not_following.txt"
            usernames = self.result.you_dont_follow

        query = self.search_var.get().strip().casefold()
        if query:
            usernames = [name for name in usernames if query in name.casefold()]

        path = filedialog.asksaveasfilename(
            title=t("dialog_export_title"),
            initialdir=APP_DIR,
            initialfile=default_name,
            defaultextension=".txt",
            filetypes=[(t("filetype_text"), "*.txt"), (t("filetype_all"), "*.*")],
        )
        if not path:
            return

        try:
            export_usernames(Path(path), title, usernames)
        except CompareError as exc:
            self._set_status(str(exc))
            return

        self._set_status(t("saved", name=Path(path).name))

    def _set_status(self, text: str) -> None:
        self.status.configure(text=text)

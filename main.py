from __future__ import annotations


def _enable_windows_dpi() -> None:
    try:
        from ctypes import windll

        windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        return


def main() -> None:
    _enable_windows_dpi()
    from ui import App

    app = App()
    app.mainloop()


if __name__ == "__main__":
    main()

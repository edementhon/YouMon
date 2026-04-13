#!/usr/bin/env python3
"""YouMon - Kids' Monster Card Maker"""

import tkinter as tk
from ui.app_window import AppWindow


def main():
    root = tk.Tk()
    root.tk.call("tk", "scaling", 1.0)  # Consistent sizing across displays
    app = AppWindow(root)
    root.mainloop()


if __name__ == "__main__":
    main()

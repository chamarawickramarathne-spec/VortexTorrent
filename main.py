import sys
from tkinter import messagebox

from ui.main_window import MainWindow


def main():
    try:
        app = MainWindow()
        app.mainloop()
    except Exception as exc:
        messagebox.showerror("Vortex Torrent", "Failed to start:\n%s" % exc)
        sys.exit(1)


if __name__ == "__main__":
    main()

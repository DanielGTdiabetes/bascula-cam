"""Quick demo for the NeoGhostButton widget."""
from tkinter import Tk, ttk

from bascula.ui.theme_holo import apply_holo_theme
from bascula.ui.widgets import NeoGhostButton


def main() -> None:
    root = Tk()
    root.geometry("800x480")
    apply_holo_theme(root)

    frame = ttk.Frame(root)
    frame.pack(expand=True, fill="both")

    def ping() -> None:
        print("clicked")

    NeoGhostButton(frame, text="g/ml", command=ping, show_text=True).pack(padx=16, pady=16)
    NeoGhostButton(
        frame,
        icon_path="bascula/ui/assets/icons/camara.png",
        command=ping,
        tooltip="Abrir cámara",
    ).pack(padx=16, pady=16)

    root.mainloop()


if __name__ == "__main__":
    main()

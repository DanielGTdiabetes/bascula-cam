"""Modern Tk based app shell for Báscula."""
from __future__ import annotations

import os, sys, logging
import tkinter as tk
from tkinter import ttk
from typing import Callable, Dict, Iterable, Optional, TYPE_CHECKING

AUDIT = os.environ.get("BASCULA_UI_AUDIT") == "1"
AUD = logging.getLogger("ui.audit")
if AUDIT:
    AUD.setLevel(logging.DEBUG)
    if not AUD.handlers:
        h = logging.StreamHandler(sys.stdout)
        h.setFormatter(logging.Formatter("AUDIT %(message)s"))
        AUD.addHandler(h)
    AUD.propagate = False
    AUD.debug(f"app_shell={__file__}")

from .views.timer import TimerEvent, get_timer_controller

if TYPE_CHECKING:
    from .views.timer import TimerController, TimerDialog

from .theme_neo import COLORS, SPACING, font_sans
from .icon_loader import load_icon
from .theme_ctk import (
    COLORS as HOLO_COLORS,
    CTK_AVAILABLE,
    create_button as holo_button,
    create_frame as holo_frame,
    create_label as holo_label,
    create_root,
    font_tuple,
)
from .theme_holo import COLOR_PRIMARY, PALETTE, apply_holo_theme, paint_grid_background
from .toolbar import Toolbar

log = logging.getLogger(__name__)

_ICON_DEF = Iterable[tuple[str, str, str, str]]

SPEAKER_OFFSET_PX = 12  # ≈3–4 mm en pantallas 1024×600

ICON_CONFIG: _ICON_DEF = (
    ("wifi", "wifi", "📶", "Wi-Fi"),
    ("speaker", "speaker", "🔊", "Sonido"),
    ("bg", "bg", "🩸", "Glucosa"),
    ("timer", "alarm", "⏱", "Temporizador"),
    ("notif", "bell", "🔔", "Notificaciones"),
)


class AppShell:
    """Application shell responsible for creating the base layout."""

    CURSOR_HIDE_DELAY_MS = 5000

    def __init__(
        self,
        root: Optional[tk.Tk] = None,
        timer_controller: Optional[TimerController] = None,
    ):
        self._own_root = root is None
        self.root = root or create_root()
        apply_holo_theme(self.root)
        self._grid_canvas = paint_grid_background(self.root)
        self.root.withdraw()
        if CTK_AVAILABLE:
            try:
                self.root.configure(fg_color=HOLO_COLORS["bg"])
            except Exception:
                pass
        else:
            self.root.configure(bg=COLORS["bg"])
        self.root.title("Báscula Digital Pro")
        self.root.protocol("WM_DELETE_WINDOW", self.root.quit)

        self._cursor_job: Optional[str] = None
        self._cursor_hidden = False
        self._cursor_forced_visible = self._cursor_forced()

        self.icon_images: Dict[str, tk.PhotoImage] = {}
        self._icon_actions: Dict[str, Callable[[], None]] = {}
        self._icon_widgets: Dict[str, tk.Button] = {}
        self._notify_job: Optional[str] = None
        self._toolbar_hint_text = ""
        self._hint_job: Optional[str] = None
        self._timer_label: Optional[tk.Label] = None
        self._toolbar_timer_label: Optional[tk.Misc] = None
        self._toolbar_timer_default_color: Optional[str] = None
        self._timer_pack: Optional[dict] = None
        self._timer_blink_job: Optional[str] = None
        self._timer_blink_visible = True
        self._timer_blink_text: Optional[str] = None
        self._timer_display_text = ""
        self._timer_state_name = "idle"
        self._timer_seconds: Optional[int] = None
        self._timer_controller: Optional["TimerController"] = None
        self._timer_listener_logged = False
        self._notification_message = ""
        self._notification_default_color: Optional[str] = None
        self._notification_timer_color = COLOR_PRIMARY
        self._glucose_label: Optional[tk.Label] = None
        self._countdown_text = ""

        self._configure_window()
        self._build_layout()
        self._setup_cursor_timer()

        if timer_controller is None:
            try:
                timer_controller = get_timer_controller(self.root)
            except Exception:
                timer_controller = None

        self.attach_timer_controller(timer_controller)

        self.root.deiconify()
        self.root.bind_all("<Button-1>", self._hint_clear, add=True)
        if AUDIT:
            AUD.debug("root bind_all('<Button-1>') for hints")

    def _hint_show(self, text: str, duration_ms: int = 700) -> None:
        if self._hint_job is not None:
            try:
                self.root.after_cancel(self._hint_job)
            except Exception:
                pass
            self._hint_job = None
        self._toolbar_hint_text = text
        try:
            self.notification_label.configure(text=text)
            self.notification_label.update_idletasks()
        except Exception:
            pass
        if duration_ms <= 0:
            return
        try:
            self._hint_job = self.root.after(max(0, int(duration_ms)), self._hint_clear)
        except Exception:
            self._hint_clear()

    def _hint_clear(self, *_: object) -> None:
        if AUDIT:
            AUD.debug("hint clear (event)")
        if self._hint_job is not None:
            try:
                self.root.after_cancel(self._hint_job)
            except Exception:
                pass
            self._hint_job = None
        self._toolbar_hint_text = ""
        self._apply_notification_text()

    def _wrap_icon_command(
        self, tooltip: str, base_cmd: Callable[[], None]
    ) -> Callable[[], None]:
        def _cmd() -> None:
            if AUDIT:
                AUD.debug(f"icon press tooltip='{tooltip}'")
            if tooltip:
                self._hint_show(tooltip, duration_ms=700)
            base_cmd()
            if AUDIT:
                AUD.debug("icon action done")

        return _cmd

    def _px_3_4mm(self) -> int:
        try:
            return max(2, int(self.root.winfo_fpixels("1m") * 0.20))
        except Exception:
            return 8

    def _is_canvas_like(self, w) -> bool:
        return hasattr(w, "move") and hasattr(w, "find_all")

    def run(self) -> None:
        """Enter the Tk mainloop."""

        self.root.mainloop()

    # ------------------------------------------------------------------
    # Timer integration
    # ------------------------------------------------------------------
    def attach_timer_controller(
        self, controller: Optional["TimerController"]
    ) -> None:
        if controller is self._timer_controller:
            return
        if self._timer_controller is not None:
            try:
                self._timer_controller.remove_listener(self._on_timer_event)
            except Exception:
                pass
        self._timer_controller = controller
        if controller is None:
            return
        try:
            controller.add_listener(self._on_timer_event, fire=True)
            if AUDIT and not self._timer_listener_logged:
                AUD.debug("timer listener registered in AppShell")
                self._timer_listener_logged = True
        except Exception:
            pass

    def _on_timer_event(self, event: TimerEvent) -> None:
        def remaining_to_text(seconds: Optional[int]) -> str:
            total = 0 if seconds is None else max(0, int(seconds))
            hours, remainder = divmod(total, 3600)
            minutes, secs = divmod(remainder, 60)
            if hours:
                return f"{hours}:{minutes:02d}:{secs:02d}"
            return f"{minutes}:{secs:02d}"

        state_name_raw = getattr(event.state, "name", str(event.state))
        state_name = str(state_name_raw).lower()
        remaining_text = remaining_to_text(event.remaining)

        if AUDIT:
            AUD.debug(
                f"toolbar countdown update state={state_name_raw} remaining={remaining_text}"
            )

        display_text: Optional[str]
        if state_name == "running" and event.remaining is not None:
            display_text = f"⏱ {remaining_text}"
        elif state_name == "paused" and event.remaining is not None:
            display_text = f"⏱ Pausa {remaining_text}"
        else:
            display_text = None

        self.set_timer_state(display_text, state=state_name, seconds=event.remaining)

    # ------------------------------------------------------------------
    # Window configuration
    # ------------------------------------------------------------------
    def _configure_window(self) -> None:
        fullscreen_env = (os.environ.get("BASCULA_UI_FULLSCREEN") or "").strip().lower()
        enable_fullscreen = fullscreen_env in {"1", "true", "yes", "on"}

        current_fullscreen = False
        try:
            current_fullscreen = bool(self.root.attributes("-fullscreen"))
        except Exception:  # pragma: no cover - Tk feature availability
            pass

        if enable_fullscreen and not current_fullscreen:
            try:
                self.root.overrideredirect(True)
            except Exception as exc:  # pragma: no cover - Tk feature availability
                log.debug("overrideredirect no soportado: %s", exc)
            try:
                self.root.attributes("-fullscreen", True)
            except Exception:  # pragma: no cover - Tk feature availability
                pass

        if not current_fullscreen:
            self.root.geometry("1024x600+0+0")
        self.root.minsize(1024, 600)

    # ------------------------------------------------------------------
    # Layout
    # ------------------------------------------------------------------
    def _build_layout(self) -> None:
        if CTK_AVAILABLE:
            self.top_bar = holo_frame(
                self.root,
                fg_color=HOLO_COLORS["surface"],
            )
            self.top_bar.configure(height=56)
            self.top_bar.pack(fill="x", side="top", padx=0, pady=0)
            self.top_bar.pack_propagate(False)
            bar_container = holo_frame(
                self.top_bar,
                fg_color=HOLO_COLORS["surface"],
            )
            bar_container.pack(fill="both", expand=True, padx=SPACING["md"], pady=SPACING["xs"])

            self._build_status_icons(bar_container)

            right_container = holo_frame(
                bar_container,
                fg_color=HOLO_COLORS["surface"],
            )
            right_container.pack(side="right", fill="y")

            self._toolbar_timer_label = holo_label(
                right_container,
                text="",
                text_color=HOLO_COLORS["text_muted"],
                font=font_tuple(16, "bold"),
                anchor="e",
                justify="right",
                padx=SPACING["xs"],
            )
            self._toolbar_timer_label.pack(side="right", padx=(SPACING["sm"], 0))
            try:
                self._toolbar_timer_default_color = self._toolbar_timer_label.cget("text_color")
            except Exception:
                self._toolbar_timer_default_color = None
            if not self._toolbar_timer_default_color:
                self._toolbar_timer_default_color = HOLO_COLORS["text_muted"]

            self.notification_label = holo_label(
                right_container,
                text="",
                text_color=HOLO_COLORS["text_muted"],
                font=font_tuple(14),
                anchor="e",
                justify="right",
                wraplength=300,
            )
            self._notification_default_color = HOLO_COLORS["text_muted"]
            self.notification_label.pack(side="right", padx=(SPACING["md"], 0))

            self.content = holo_frame(self.root, fg_color=HOLO_COLORS["bg"])
            self.content.pack(fill="both", expand=True)
            self.container = self.content
        else:
            self.root.configure(bg=PALETTE["bg"])
            self.container = ttk.Frame(self.root, style="Toolbar.TFrame")
            self.container.pack(fill="both", expand=True)
            self.container.columnconfigure(0, weight=1)
            self.container.rowconfigure(1, weight=1)

            actions = []
            for name, _asset, _fallback, tooltip in ICON_CONFIG:
                base_cmd = (lambda n=name: self._handle_action(n))
                actions.append(
                    {
                        "text": tooltip,
                        "command": self._wrap_icon_command(tooltip, base_cmd),
                    }
                )
            self.top_bar = Toolbar(self.container, actions=actions)
            self.top_bar.grid(row=0, column=0, sticky="ew")

            right_container = ttk.Frame(self.top_bar.content, style="Toolbar.TFrame")
            right_container.pack(side="right", fill="y")

            self._toolbar_timer_label = ttk.Label(
                right_container,
                text="",
                style="Toolbar.TLabel",
                anchor="e",
                justify="right",
            )
            self._toolbar_timer_label.pack(side="right", padx=(12, 0))
            try:
                self._toolbar_timer_default_color = self._toolbar_timer_label.cget("foreground")
            except Exception:
                self._toolbar_timer_default_color = None
            if not self._toolbar_timer_default_color:
                try:
                    self._toolbar_timer_default_color = COLORS.get("muted")
                except Exception:
                    self._toolbar_timer_default_color = None

            self.notification_label = ttk.Label(
                right_container,
                text="",
                style="Toolbar.TLabel",
                anchor="e",
                justify="right",
                wraplength=300,
            )
            self.notification_label.pack(side="right", padx=(16, 0))

            self._init_toolbar_actions()

            self.content = ttk.Frame(self.container, style="Toolbar.TFrame")
            self.content.grid(row=1, column=0, sticky="nsew")

        self._capture_notification_default_color()


    def _build_status_icons(self, container: tk.Misc) -> None:
        for name, asset_name, fallback_text, tooltip in ICON_CONFIG:
            asset_filename = (
                asset_name if asset_name.lower().endswith(".png") else f"{asset_name}.png"
            )
            icon = load_icon(asset_filename, 48 if CTK_AVAILABLE else 32)
            if icon is not None:
                self.icon_images[name] = icon

            base_cmd = (lambda n=name: self._handle_action(n))

            def create_icon_widget(parent: tk.Misc) -> tk.Misc:
                if CTK_AVAILABLE:
                    width = 78
                    height = 64
                    button = holo_button(
                        parent,
                        text=fallback_text,
                        image=icon,
                        compound="top",
                        font=font_tuple(12, "bold"),
                        width=width,
                        height=height,
                        fg_color=HOLO_COLORS["surface_alt"],
                        hover_color=HOLO_COLORS["accent"],
                        text_color=HOLO_COLORS["text"],
                    )
                else:
                    width = 6
                    button = tk.Button(
                        parent,
                        text=fallback_text,
                        image=icon,
                        compound="top",
                        fg=COLORS["fg"],
                        bg=COLORS["surface"],
                        activebackground=COLORS["surface"],
                        activeforeground=COLORS["fg"],
                        font=font_sans(12, "bold"),
                        padx=SPACING["xs"],
                        pady=SPACING["xs"],
                        relief="flat",
                        bd=0,
                        highlightthickness=0,
                    )
                    button.configure(width=width)

                button.configure(command=self._wrap_icon_command(tooltip, base_cmd))

                img = self.icon_images.get(name)
                if img is not None:
                    button.configure(image=img, compound="top", text=fallback_text)
                    button.image = img  # type: ignore[attr-defined]
                else:
                    button.configure(image="", text=fallback_text, compound="center")

                return button

            hint_targets: list[tk.Misc] = []
            pack_kwargs = {"side": "left", "padx": (0, SPACING["sm"]), "pady": 0}
            button_parent = container
            button = create_icon_widget(button_parent)
            hint_targets.append(button)

            if name == "speaker":
                try:
                    children = list(getattr(button, "winfo_children", lambda: [])())
                except Exception:
                    children = []
                child_canvas = next((child for child in children if self._is_canvas_like(child)), None)
                self_is_canvas = self._is_canvas_like(button)
                if AUDIT:
                    AUD.debug(
                        "speaker inspect: self_is_canvas="
                        f"{self_is_canvas} child_canvas={bool(child_canvas)}"
                    )

                if self_is_canvas or child_canvas is not None:
                    canvas_target = button if self_is_canvas else child_canvas

                    def _do_move(canvas: tk.Misc = canvas_target, offset: int = SPEAKER_OFFSET_PX) -> None:
                        try:
                            items = canvas.find_all() if hasattr(canvas, "find_all") else ()
                            if items:
                                canvas.move("all", 0, offset)
                                try:
                                    height = int(canvas.winfo_reqheight())
                                except Exception:
                                    height = 0
                                if height:
                                    try:
                                        canvas.configure(height=height + offset)
                                    except Exception:
                                        pass
                                canvas.update_idletasks()
                                if AUDIT:
                                    AUD.debug(
                                        f"speaker canvas move offset={SPEAKER_OFFSET_PX}px"
                                    )
                            else:
                                canvas.after(30, _do_move)
                        except Exception as exc:
                            if AUDIT:
                                AUD.debug(f"speaker move err: {exc}")

                    canvas_target.after_idle(_do_move)
                    button.pack(**pack_kwargs)
                    if child_canvas is not None and child_canvas is not button:
                        hint_targets.append(child_canvas)
                else:
                    try:
                        button.destroy()
                    except Exception:
                        pass

                    if CTK_AVAILABLE:
                        holder = holo_frame(container, fg_color=HOLO_COLORS["surface"])
                    else:
                        holder = tk.Frame(
                            container,
                            bg=COLORS["surface"],
                            highlightthickness=0,
                            bd=0,
                        )
                    holder.pack(**pack_kwargs)

                    def _apply_offset(target_holder: tk.Misc = holder) -> None:
                        try:
                            target_holder.pack_configure(pady=(SPEAKER_OFFSET_PX, 0))
                        except Exception:
                            pass

                    holder.after_idle(_apply_offset)

                    spacer = tk.Frame(
                        holder,
                        height=SPEAKER_OFFSET_PX,
                        bg=(
                            HOLO_COLORS["surface"]
                            if CTK_AVAILABLE
                            else COLORS["surface"]
                        ),
                        highlightthickness=0,
                        bd=0,
                    )
                    spacer.pack(side="top", fill="x")

                    button = create_icon_widget(holder)
                    button.pack(side="top", padx=0, pady=0)
                    hint_targets = [button, holder]
                    if AUDIT:
                        AUD.debug(
                            f"speaker holder+spacer offset={SPEAKER_OFFSET_PX}px"
                        )
            else:
                button.pack(**pack_kwargs)

            if AUDIT:
                try:
                    AUD.debug(
                        f"icon built name={name} class={button.winfo_class()} mgr={button.winfo_manager()}"
                    )
                    if name == "speaker":
                        kids = list(getattr(button, "winfo_children", lambda: [])())
                        canvas_kid = next(
                            (k for k in kids if hasattr(k, "move") and hasattr(k, "find_all")),
                            None,
                        )
                        AUD.debug(
                            "speaker inspect: self_is_canvas="
                            f"{hasattr(button,'move') and hasattr(button,'find_all')} "
                            f"child_canvas={bool(canvas_kid)}"
                        )
                    if name == "timer":
                        AUD.debug("timer icon wired (onPress should open TimerDialog)")
                except Exception as exc:
                    AUD.debug(f"icon audit error: {exc}")

            button.tooltip = tooltip  # type: ignore[attr-defined]
            button.configure(state="disabled")
            self._icon_widgets[name] = button

            events = ("<ButtonRelease-1>", "<Leave>", "<FocusOut>")
            for target in hint_targets:
                for sequence in events:
                    try:
                        target.bind(sequence, self._hint_clear, add=True)
                    except Exception:
                        continue

            if name == "timer":
                self._timer_pack = {"side": "left", "padx": (0, SPACING["sm"])}
                if CTK_AVAILABLE:
                    label = holo_label(
                        container,
                        text="",
                        text_color=HOLO_COLORS["text_muted"],
                        font=font_tuple(16, "bold"),
                        padx=SPACING["xs"],
                    )
                else:
                    label = tk.Label(
                        container,
                        text="",
                        fg=COLORS["muted"],
                        bg=COLORS["surface"],
                        font=font_sans(16, "bold"),
                        padx=SPACING["xs"],
                    )
                label.configure(cursor="hand2")
                label.bind("<Button-1>", lambda _e, n=name: self._handle_action(n))
                label.pack(side="left", padx=(0, SPACING["sm"]))
                self._timer_label = label
            elif name == "bg":
                if CTK_AVAILABLE:
                    label = holo_label(
                        container,
                        text="—",
                        text_color=HOLO_COLORS["text_muted"],
                        font=font_tuple(16, "bold"),
                        padx=SPACING["xs"],
                    )
                else:
                    label = tk.Label(
                        container,
                        text="—",
                        fg=COLORS["muted"],
                        bg=COLORS["surface"],
                        font=font_sans(16, "bold"),
                        padx=SPACING["xs"],
                    )
                label.pack(side="left", padx=(0, SPACING["sm"]))
                self._glucose_label = label

    def _init_toolbar_actions(self) -> None:
        if not isinstance(getattr(self, "top_bar", None), Toolbar):
            return

        buttons = list(self.top_bar.buttons)
        for idx, (name, asset_name, fallback_text, tooltip) in enumerate(ICON_CONFIG):
            if idx >= len(buttons):
                break

            button = buttons[idx]
            asset_filename = asset_name if asset_name.lower().endswith(".png") else f"{asset_name}.png"
            icon = load_icon(asset_filename, 24)
            if icon is not None:
                self.icon_images[name] = icon
                button.configure(image=icon, compound="left")
                button.image = icon  # type: ignore[attr-defined]
            else:
                button.configure(image="", text=fallback_text)

            base_cmd = (lambda n=name: self._handle_action(n))
            button.configure(command=self._wrap_icon_command(tooltip, base_cmd))
            button.configure(state="disabled")
            button.tooltip = tooltip  # type: ignore[attr-defined]
            self._icon_widgets[name] = button

            button.bind("<ButtonRelease-1>", self._hint_clear, add=True)
            button.bind("<Leave>", self._hint_clear, add=True)
            button.bind("<FocusOut>", self._hint_clear, add=True)

            if name == "speaker":
                button.pack_configure(pady=(SPEAKER_OFFSET_PX, 0))

            if name == "timer":
                self._timer_pack = {"side": "left", "padx": (0, 12)}
                label = ttk.Label(
                    self.top_bar.button_container,
                    text="",
                    style="Toolbar.TLabel",
                )
                try:
                    label.configure(cursor="hand2")
                except Exception:
                    pass
                label.bind("<Button-1>", lambda _e, n=name: self._handle_action(n))
                self._timer_label = label
            elif name == "bg":
                label = ttk.Label(
                    self.top_bar.button_container,
                    text="—",
                    style="Toolbar.TLabel",
                )
                label.pack(side="left", padx=(0, 12))
                self._glucose_label = label

    # ------------------------------------------------------------------
    # Cursor management
    # ------------------------------------------------------------------
    def _setup_cursor_timer(self) -> None:
        if self._cursor_forced_visible:
            self.root.configure(cursor="")
            return
        for sequence in ("<Motion>", "<Key>", "<Button>", "<FocusIn>"):
            self.root.bind_all(sequence, self._on_user_activity, add="+")
        self._schedule_cursor_hide()

    def _schedule_cursor_hide(self) -> None:
        if self._cursor_forced_visible:
            return
        if self._cursor_job is not None:
            try:
                self.root.after_cancel(self._cursor_job)
            except Exception:
                pass
        self._cursor_job = self.root.after(self.CURSOR_HIDE_DELAY_MS, self._hide_cursor)

    def _hide_cursor(self) -> None:
        if self._cursor_forced_visible:
            return
        self.root.configure(cursor="none")
        self._cursor_hidden = True

    def _show_cursor(self) -> None:
        if self._cursor_hidden:
            self.root.configure(cursor="")
            self._cursor_hidden = False

    def _on_user_activity(self, _event: tk.Event) -> None:
        if self._cursor_forced_visible:
            return
        self._show_cursor()
        self._schedule_cursor_hide()

    @staticmethod
    def _cursor_forced() -> bool:
        value = (os.environ.get("BASCULA_UI_CURSOR") or "").strip().lower()
        return value in {"1", "true", "yes", "on"}

    def get_icon_widget(self, name: str) -> Optional[tk.Button]:
        """Expose top bar widget reference for structural probes."""

        return self._icon_widgets.get(name)

    # ------------------------------------------------------------------
    # Actions / notifications
    # ------------------------------------------------------------------
    def bind_action(self, name: str, callback: Optional[Callable[[], None]]) -> None:
        if callback is None:
            self._icon_actions.pop(name, None)
        else:
            self._icon_actions[name] = callback
        widget = self._icon_widgets.get(name)
        if widget is not None:
            widget.configure(state="normal" if callback else "disabled")

    def _handle_action(self, name: str) -> None:
        if AUDIT:
            AUD.debug("handle action=%s", name)
        callback = self._icon_actions.get(name)
        if callback is None:
            self.notify("Acción no disponible")
            return
        try:
            callback()
        except Exception as exc:  # pragma: no cover - defensive
            log.exception("Error executing action %s", name)
            self.notify(str(exc))

    def notify(self, message: str, duration_ms: int = 4000) -> None:
        label = self.notification_label
        if label is None:
            return

        if self._notify_job is not None:
            try:
                label.after_cancel(self._notify_job)
            except Exception:
                pass
            self._notify_job = None

        self._notification_message = message or ""
        self._capture_notification_default_color()

        if self._notification_message:
            self._configure_notification_label(
                self._notification_message, self._notification_default_color
            )
            if duration_ms > 0:
                try:
                    self._notify_job = label.after(duration_ms, self._clear_notification_message)
                except Exception:
                    self._notify_job = None
        else:
            self._apply_notification_text()

    # ------------------------------------------------------------------
    # Timer indicator
    # ------------------------------------------------------------------
    def set_timer_state(
        self,
        text: Optional[str],
        state: str = "idle",
        *,
        flash: bool = False,
        blink: bool = False,
        seconds: Optional[int] = None,
    ) -> None:
        label = self.notification_label
        if label is None:
            return

        self._capture_notification_default_color()

        normalized = (state or "idle").lower()
        self._timer_state_name = normalized
        self._timer_seconds = seconds if seconds is None else max(0, int(seconds))

        if normalized in {"idle", "finished", "cancelled"} or not text:
            self._countdown_text = ""
            self._timer_display_text = ""
            self._timer_blink_text = None
            self._stop_timer_blink()
            self._apply_notification_text()
            return

        formatted = self._format_timer_display(normalized, text, self._timer_seconds)
        self._timer_display_text = formatted
        self._timer_blink_text = formatted if blink and normalized == "running" else None
        self._countdown_text = formatted

        if blink and normalized == "running":
            self._start_timer_blink()
        else:
            self._stop_timer_blink()

        self._apply_notification_text()

    def _start_timer_blink(self) -> None:
        widget = self._toolbar_timer_label or self.notification_label
        if widget is None:
            return
        self._stop_timer_blink()
        self._timer_blink_visible = True
        self._apply_notification_text()
        try:
            self._timer_blink_job = widget.after(250, self._toggle_timer_blink)
        except Exception:
            self._timer_blink_job = None

    def _toggle_timer_blink(self) -> None:
        widget = self._toolbar_timer_label or self.notification_label
        if widget is None:
            self._timer_blink_job = None
            return
        self._timer_blink_visible = not self._timer_blink_visible
        self._apply_notification_text()
        try:
            self._timer_blink_job = widget.after(250, self._toggle_timer_blink)
        except Exception:
            self._timer_blink_job = None

    def _stop_timer_blink(self) -> None:
        widget = self._toolbar_timer_label or self.notification_label
        if self._timer_blink_job is not None and widget is not None:
            try:
                widget.after_cancel(self._timer_blink_job)
            except Exception:
                pass
        self._timer_blink_job = None
        self._timer_blink_visible = True
        self._apply_notification_text()

    def _capture_notification_default_color(self) -> None:
        if self._notification_default_color:
            return
        label = self.notification_label
        if label is None:
            return
        for option in ("text_color", "foreground", "fg"):
            try:
                value = label.cget(option)
            except Exception:
                continue
            if value:
                self._notification_default_color = value
                break

    def _format_timer_display(
        self, state: str, original_text: Optional[str], seconds: Optional[int]
    ) -> str:
        time_part: str
        if seconds is not None:
            total = max(0, int(seconds))
            hours, remainder = divmod(total, 3600)
            minutes, secs = divmod(remainder, 60)
            if hours:
                time_part = f"{hours}:{minutes:02d}:{secs:02d}"
            else:
                time_part = f"{minutes:02d}:{secs:02d}"
        else:
            fallback = (original_text or "").strip()
            fallback = fallback.replace("⏱", "").strip()
            candidate = "00:00"
            if fallback:
                tokens = fallback.split()
                for token in reversed(tokens):
                    if ":" in token:
                        candidate = token
                        break
                else:
                    candidate = fallback
            time_part = candidate

        if state == "paused":
            return f"⏱ Pausa {time_part}"
        return f"⏱ {time_part}"

    def _update_toolbar_timer_label(self, text: str, *, active: bool) -> None:
        label = self._toolbar_timer_label
        if label is None:
            return
        try:
            label.configure(text=text)
        except Exception:
            pass
        color = COLOR_PRIMARY if active and text else self._toolbar_timer_default_color
        if color:
            for option in ("text_color", "fg", "foreground"):
                try:
                    label.configure(**{option: color})
                    break
                except Exception:
                    continue

    def _apply_notification_text(self) -> None:
        display_text = ""
        if self._countdown_text:
            if self._timer_blink_text and not self._timer_blink_visible:
                display_text = ""
            else:
                display_text = self._countdown_text
        self._update_toolbar_timer_label(display_text, active=bool(display_text))

        label = self.notification_label
        if label is None:
            return
        if self._notification_message:
            self._configure_notification_label(
                self._notification_message, self._notification_default_color
            )
            return
        if self._toolbar_hint_text:
            self._configure_notification_label(
                self._toolbar_hint_text, self._notification_default_color
            )
            return
        if self._countdown_text:
            self._configure_notification_label("", self._notification_default_color)
            return
        if not self._timer_display_text:
            self._configure_notification_label("", self._notification_default_color)
            return
        if self._timer_blink_text and not self._timer_blink_visible:
            display = ""
        else:
            display = self._timer_blink_text or self._timer_display_text
        self._configure_notification_label(display, self._notification_timer_color)

    def _configure_notification_label(self, text: str, color: Optional[str]) -> None:
        label = self.notification_label
        if label is None:
            return
        try:
            label.configure(text=text)
        except Exception:
            pass
        if not color:
            return
        for option in ("text_color", "fg", "foreground"):
            try:
                label.configure(**{option: color})
                break
            except Exception:
                continue

    def _clear_notification_message(self) -> None:
        self._notify_job = None
        self._notification_message = ""
        self._apply_notification_text()

    # ------------------------------------------------------------------
    # Glucose indicator
    # ------------------------------------------------------------------
    def set_glucose_status(self, text: Optional[str], color: Optional[str] = None) -> None:
        label = self._glucose_label
        if label is None:
            return
        palette = COLORS if CTK_AVAILABLE else {
            "text": PALETTE.get("text", "#d8f6ff"),
            "muted": PALETTE.get("text_muted", "#93b4c4"),
        }

        if text:
            try:
                label.configure(text=text)
                if color:
                    try:
                        label.configure(foreground=color)
                    except Exception:
                        label.configure(fg=color)
                else:
                    label.configure(foreground=palette.get("text", "white"))
            except Exception:
                return
        else:
            try:
                label.configure(text="—")
                try:
                    label.configure(foreground=palette.get("muted", "grey"))
                except Exception:
                    label.configure(fg=palette.get("muted", "grey"))
            except Exception:
                return

    # ------------------------------------------------------------------
    # Cleanup
    # ------------------------------------------------------------------
    def destroy(self) -> None:
        if self._notify_job is not None:
            try:
                self.notification_label.after_cancel(self._notify_job)
            except Exception:
                pass
            self._notify_job = None
        if self._hint_job is not None:
            try:
                self.root.after_cancel(self._hint_job)
            except Exception:
                pass
            self._hint_job = None
        self._toolbar_hint_text = ""
        if self._cursor_job is not None:
            try:
                self.root.after_cancel(self._cursor_job)
            except Exception:
                pass
            self._cursor_job = None
        if self._own_root:
            self.root.destroy()

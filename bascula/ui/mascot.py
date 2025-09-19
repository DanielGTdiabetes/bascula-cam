"""Mascot widget with animated sprites and graceful fallback."""
from __future__ import annotations

import contextlib
import json
import logging
import tkinter as tk
from pathlib import Path
from typing import Dict, List, Optional

from PIL import Image, ImageTk

from .mascot_placeholder import MascotPlaceholder
from .theme_classic import COLORS, font

logger = logging.getLogger("bascula.ui.mascot")


StateFrames = Dict[str, List[ImageTk.PhotoImage]]


class MascotCanvas(tk.Canvas):
    def __init__(
        self,
        parent: tk.Widget,
        width: int = 320,
        height: int = 240,
        assets_dir: str = "assets/mascot",
        fps: int = 16,
    ) -> None:
        super().__init__(parent, width=width, height=height, bg=COLORS["surface"], highlightthickness=0)
        self._fps = max(4, min(int(fps), 24))
        self._state = "idle"
        self._frames: StateFrames = {}
        self._frame_index = 0
        self._after_token: Optional[str] = None
        self._message_item: Optional[int] = None
        self._message_after: Optional[str] = None
        self._happy_timeout: Optional[str] = None
        self._placeholder: Optional[MascotPlaceholder] = None
        self._image_id: Optional[int] = None
        self._current_photo: Optional[ImageTk.PhotoImage] = None
        self._load_assets(Path(assets_dir), width, height)
        if self._frames:
            try:
                self._current_photo = self._frames.get("idle", [])[0]
                if self._current_photo is not None:
                    self._image_id = self.create_image(width // 2, height // 2, image=self._current_photo)
            except tk.TclError:
                logger.warning("PhotoImage no disponible; usando placeholder")
                self._frames.clear()
        if not self._frames:
            logger.warning("Usando mascota placeholder por falta de assets")
            self._placeholder = MascotPlaceholder(self, width=width, height=height)
            self.create_window(width // 2, height // 2, window=self._placeholder)
            self._placeholder.start()

    def _load_assets(self, assets_dir: Path, width: int, height: int) -> None:
        if not assets_dir.exists():
            return
        manifest_path = assets_dir / "manifest.json"
        manifest: dict[str, dict] = {}
        if manifest_path.exists():
            try:
                manifest = json.loads(manifest_path.read_text("utf-8"))
            except Exception:
                logger.warning("Manifest de mascota inválido", exc_info=True)
        for state in ("idle", "processing", "happy", "error"):
            frames = self._load_state_frames(assets_dir, state, manifest.get(state), width, height)
            if frames:
                self._frames[state] = frames

    def _load_state_frames(self, base: Path, state: str, info: Optional[dict], width: int, height: int) -> List[ImageTk.PhotoImage]:
        try:
            if info and "sheet" in info:
                sheet_path = base / info["sheet"]
                return self._load_from_sheet(sheet_path, info, width, height)
            return self._load_from_directory(base / state, width, height)
        except Exception:
            logger.warning("No se pudieron cargar frames para %s", state, exc_info=True)
            return []

    def _load_from_directory(self, path: Path, width: int, height: int) -> List[ImageTk.PhotoImage]:
        if not path.is_dir():
            return []
        images: List[ImageTk.PhotoImage] = []
        for entry in sorted(path.glob("*.png")):
            try:
                image = Image.open(entry)
                resized = image.resize((width, height), Image.LANCZOS)
                images.append(ImageTk.PhotoImage(resized))
            except Exception:
                logger.warning("Frame inválido %s", entry, exc_info=True)
        return images

    def _load_from_sheet(self, sheet_path: Path, info: dict, width: int, height: int) -> List[ImageTk.PhotoImage]:
        if not sheet_path.exists():
            return []
        try:
            cols = int(info.get("cols", 1))
            rows = int(info.get("rows", 1))
            total = int(info.get("frames", cols * rows))
        except (TypeError, ValueError):
            logger.warning("Manifest inválido para spritesheet %s", sheet_path)
            return []
        try:
            sheet = Image.open(sheet_path)
        except Exception:
            logger.warning("No se pudo abrir spritesheet %s", sheet_path, exc_info=True)
            return []
        frame_width = sheet.width // cols
        frame_height = sheet.height // rows
        frames: List[ImageTk.PhotoImage] = []
        for index in range(total):
            col = index % cols
            row = index // cols
            box = (col * frame_width, row * frame_height, (col + 1) * frame_width, (row + 1) * frame_height)
            frame = sheet.crop(box)
            resized = frame.resize((width, height), Image.LANCZOS)
            frames.append(ImageTk.PhotoImage(resized))
        return frames

    # Public API ---------------------------------------------------------
    def configure_state(self, state: str) -> None:
        state = state if state in self._frames else "idle"
        if self._placeholder is not None:
            self._placeholder.configure_state(state)
            if state == "happy":
                self.after(1500, lambda: self._placeholder.configure_state("idle"))
            return
        if state != self._state:
            self._state = state
            self._frame_index = 0
            if state == "happy":
                self._schedule_happy_reset()
        self._render_frame()

    def set_message(self, text: str | None) -> None:
        if self._placeholder is not None:
            self._placeholder.set_message(text)
            return
        if self._message_item is not None:
            self.delete(self._message_item)
            self._message_item = None
        if self._message_after is not None:
            with contextlib.suppress(Exception):
                self.after_cancel(self._message_after)
            self._message_after = None
        if not text:
            return
        self._message_item = self.create_text(
            self.winfo_reqwidth() // 2,
            24,
            text=text,
            font=font("sm"),
            fill=COLORS["text"],
            anchor="n",
        )
        self._message_after = self.after(3000, self._clear_message)

    def start(self) -> None:
        if self._placeholder is not None:
            self._placeholder.start()
            return
        if self._after_token is None:
            self._schedule_next()

    def stop(self) -> None:
        if self._placeholder is not None:
            self._placeholder.stop()
            return
        if self._after_token is not None:
            with contextlib.suppress(Exception):
                self.after_cancel(self._after_token)
            self._after_token = None

    # Internal helpers ---------------------------------------------------
    def _schedule_next(self) -> None:
        interval = int(1000 / max(1, self._fps))
        self._after_token = self.after(interval, self._tick)

    def _tick(self) -> None:
        frames = self._frames.get(self._state) or self._frames.get("idle")
        if not frames:
            return
        self._frame_index = (self._frame_index + 1) % len(frames)
        self._render_frame()
        self._schedule_next()

    def _render_frame(self) -> None:
        frames = self._frames.get(self._state) or self._frames.get("idle")
        if not frames:
            return
        frame = frames[self._frame_index % len(frames)]
        if self._image_id is None:
            self._image_id = self.create_image(self.winfo_reqwidth() // 2, self.winfo_reqheight() // 2, image=frame)
        else:
            self.itemconfigure(self._image_id, image=frame)
        self._current_photo = frame  # Prevent GC

    def _schedule_happy_reset(self) -> None:
        if self._happy_timeout is not None:
            with contextlib.suppress(Exception):
                self.after_cancel(self._happy_timeout)
        self._happy_timeout = self.after(1800, lambda: self.configure_state("idle"))

    def _clear_message(self) -> None:
        if self._message_item is not None:
            self.delete(self._message_item)
            self._message_item = None
        self._message_after = None


__all__ = ["MascotCanvas"]

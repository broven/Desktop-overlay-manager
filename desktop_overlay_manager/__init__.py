"""Public API for Desktop Overlay Manager."""

from __future__ import annotations

import json
import threading
import time
from concurrent.futures import Future
from pathlib import Path
from queue import Empty, Queue
from typing import Any, Dict, Optional

import tkinter as tk

from .overlay import (
    DraggableOverlay,
    DraggablePoint,
    clear_all_overlays,
    clear_all_points,
    create_overlay,
    create_point,
)

DEFAULT_RECT = {"x": 120, "y": 120, "width": 240, "height": 160}
DEFAULT_POINT = {"x": 160, "y": 160}
CONFIG_FILENAME = "overlays.json"


class Desktop_overlay_manager:
    """High level manager for draggable rectangles and points."""

    def __init__(self, config_dir: Optional[str] = None, loop_interval: float = 0.01) -> None:
        self.config_dir = Path(config_dir or Path.home() / ".desktop_overlay_manager")
        self.config_dir.mkdir(parents=True, exist_ok=True)
        self.loop_interval = loop_interval
        self._config_path = self.config_dir / CONFIG_FILENAME

        self._rects: Dict[str, DraggableOverlay] = {}
        self._points: Dict[str, DraggablePoint] = {}
        self._config = self._load_all_configs()
        self._rect_configs = self._config.setdefault("rects", {})
        self._point_configs = self._config.setdefault("points", {})

        self._tk_thread: Optional[threading.Thread] = None
        self._tk_queue: Queue[tuple[Future, Any, tuple, dict]] = Queue()
        self._root_ready = threading.Event()
        self._stop_event = threading.Event()
        self._root: Optional[tk.Tk] = None

        self._ensure_tk_thread()

    # --------------------------------------------------------------------- #
    # Public API
    # --------------------------------------------------------------------- #
    def registerRect(
        self,
        rect_id: str,
        *,
        label: str = "",
        x: Optional[int] = None,
        y: Optional[int] = None,
        width: Optional[int] = None,
        height: Optional[int] = None,
        **style: Any,
    ) -> None:
        """Create or show a draggable rectangle."""

        def _create() -> None:
            config = self._rect_configs.get(rect_id, {})
            rect_data = {
                "x": x if x is not None else config.get("x", DEFAULT_RECT["x"]),
                "y": y if y is not None else config.get("y", DEFAULT_RECT["y"]),
                "width": width if width is not None else config.get("width", DEFAULT_RECT["width"]),
                "height": height if height is not None else config.get("height", DEFAULT_RECT["height"]),
            }
            rect_label = label or config.get("label", rect_id)

            def _callback(nx: int, ny: int, w: int, h: int) -> None:
                self._rect_configs[rect_id] = {
                    "x": nx,
                    "y": ny,
                    "width": w,
                    "height": h,
                    "label": rect_label,
                }
                self._save_all_configs()

            overlay = self._rects.get(rect_id)
            if overlay is None:
                overlay = create_overlay(
                    root=self._root,  # type: ignore[arg-type]
                    x=rect_data["x"],
                    y=rect_data["y"],
                    width=rect_data["width"],
                    height=rect_data["height"],
                    label=rect_label,
                    on_rect_update=_callback,
                    **style,
                )
                self._rects[rect_id] = overlay
            else:
                overlay.update_position(rect_data["x"], rect_data["y"], notify=False)
                overlay.update_size(rect_data["width"], rect_data["height"], notify=False)
                overlay.update_label(rect_label)
                overlay.show()

        self._call_in_tk_thread(_create)

    def registerPosition(
        self,
        point_id: str,
        *,
        label: str = "",
        x: Optional[int] = None,
        y: Optional[int] = None,
        **style: Any,
    ) -> None:
        """Create or show a draggable point marker."""

        def _create() -> None:
            config = self._point_configs.get(point_id, {})
            point_data = {
                "x": x if x is not None else config.get("x", DEFAULT_POINT["x"]),
                "y": y if y is not None else config.get("y", DEFAULT_POINT["y"]),
            }
            point_label = label or config.get("label", point_id)

            def _callback(nx: int, ny: int) -> None:
                self._point_configs[point_id] = {
                    "x": nx,
                    "y": ny,
                    "label": point_label,
                }
                self._save_all_configs()

            point = self._points.get(point_id)
            if point is None:
                point = create_point(
                    root=self._root,  # type: ignore[arg-type]
                    x=point_data["x"],
                    y=point_data["y"],
                    label=point_label,
                    callback=_callback,
                    **style,
                )
                self._points[point_id] = point
            else:
                point.update_position(point_data["x"], point_data["y"], notify=False)
                point.update_label(point_label)
                point.show()

        self._call_in_tk_thread(_create)

    # Typo-friendly alias
    def regsterPositon(self, *args: Any, **kwargs: Any) -> None:  # pragma: no cover
        self.registerPosition(*args, **kwargs)

    def getRect(self, rect_id: str) -> Optional[Dict[str, int]]:
        """Return last known rectangle geometry."""

        def _read() -> Optional[Dict[str, int]]:
            overlay = self._rects.get(rect_id)
            if overlay is not None:
                x, y, width, height = overlay.get_position()
                return {"x": x, "y": y, "width": width, "height": height}
            if rect_id in self._rect_configs:
                saved = self._rect_configs[rect_id].copy()
                return {k: int(v) for k, v in saved.items() if k in {"x", "y", "width", "height"}}
            return None

        return self._call_in_tk_thread(_read)

    def getPosition(self, point_id: str) -> Optional[Dict[str, int]]:
        """Return last known point coordinates."""

        def _read() -> Optional[Dict[str, int]]:
            point = self._points.get(point_id)
            if point is not None:
                x, y = point.get_position()
                return {"x": x, "y": y}
            if point_id in self._point_configs:
                saved = self._point_configs[point_id].copy()
                return {k: int(v) for k, v in saved.items() if k in {"x", "y"}}
            return None

        return self._call_in_tk_thread(_read)

    def hideAll(self) -> None:
        """Hide all overlays and points."""

        def _hide() -> None:
            for overlay in self._rects.values():
                overlay.hide()
            for point in self._points.values():
                point.hide()

        self._call_in_tk_thread(_hide)

    def showAll(self) -> None:
        """Show all overlays and points."""

        def _show() -> None:
            for overlay in self._rects.values():
                overlay.show()
            for point in self._points.values():
                point.show()

        self._call_in_tk_thread(_show)

    def destroy(self) -> None:
        """Destroy all widgets and stop Tk loop."""

        def _destroy() -> None:
            clear_all_overlays()
            clear_all_points()
            self._rects.clear()
            self._points.clear()

        self._call_in_tk_thread(_destroy)
        self._stop_event.set()
        if self._tk_thread and self._tk_thread.is_alive():
            self._tk_thread.join(timeout=1)

    # ------------------------------------------------------------------ #
    # Internal helpers
    # ------------------------------------------------------------------ #
    def _ensure_tk_thread(self) -> None:
        if self._tk_thread and self._tk_thread.is_alive():
            return

        self._tk_thread = threading.Thread(target=self._run_tk_loop, daemon=True)
        self._tk_thread.start()
        self._root_ready.wait()

    def _run_tk_loop(self) -> None:
        self._root = tk.Tk()
        self._root.withdraw()
        self._root_ready.set()

        while not self._stop_event.is_set():
            self._drain_queue()
            try:
                self._root.update_idletasks()
                self._root.update()
            except tk.TclError:
                break
            time.sleep(self.loop_interval)

        self._drain_queue(set_exception=True)
        try:
            self._root.destroy()
        except tk.TclError:
            pass

    def _drain_queue(self, set_exception: bool = False) -> None:
        while True:
            try:
                future, func, args, kwargs = self._tk_queue.get_nowait()
            except Empty:
                break
            if set_exception:
                future.set_exception(RuntimeError("Tk loop already stopped"))
                continue
            try:
                result = func(*args, **kwargs)
            except Exception as exc:  # pragma: no cover - best-effort guard
                future.set_exception(exc)
            else:
                future.set_result(result)

    def _call_in_tk_thread(self, func: Any, *args: Any, **kwargs: Any) -> Any:
        self._ensure_tk_thread()
        future: Future = Future()
        self._tk_queue.put((future, func, args, kwargs))
        return future.result()

    def _load_all_configs(self) -> Dict[str, Dict[str, Any]]:
        if self._config_path.exists():
            try:
                with self._config_path.open("r", encoding="utf-8") as fh:
                    data = json.load(fh)
            except (json.JSONDecodeError, OSError):
                data = {}
            if not isinstance(data, dict):
                data = {}
            return {
                "rects": data.get("rects", {}) if isinstance(data.get("rects"), dict) else {},
                "points": data.get("points", {}) if isinstance(data.get("points"), dict) else {},
            }

        legacy = self._migrate_legacy_configs()
        if legacy is not None:
            return legacy
        return {"rects": {}, "points": {}}

    def _migrate_legacy_configs(self) -> Optional[Dict[str, Dict[str, Any]]]:
        rects = self._load_legacy_file("rects.json")
        points = self._load_legacy_file("points.json")
        if not rects and not points:
            return None
        data = {"rects": rects, "points": points}
        self._write_config_file(data)
        return data

    def _load_legacy_file(self, filename: str) -> Dict[str, Any]:
        path = self.config_dir / filename
        if not path.exists():
            return {}
        try:
            with path.open("r", encoding="utf-8") as fh:
                data = json.load(fh)
                return data if isinstance(data, dict) else {}
        except (json.JSONDecodeError, OSError):
            return {}

    def _save_all_configs(self) -> None:
        self._config["rects"] = self._rect_configs
        self._config["points"] = self._point_configs
        self._write_config_file(self._config)

    def _write_config_file(self, data: Dict[str, Any]) -> None:
        tmp_path = self._config_path.with_suffix(".tmp")
        with tmp_path.open("w", encoding="utf-8") as fh:
            json.dump(data, fh, ensure_ascii=False, indent=2)
        tmp_path.replace(self._config_path)


__all__ = ["Desktop_overlay_manager"]


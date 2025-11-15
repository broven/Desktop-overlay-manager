import json
import tempfile
import unittest
from pathlib import Path
from typing import Any, Dict
from unittest.mock import patch

from desktop_overlay_manager import Desktop_overlay_manager


class FakeTk:
    def withdraw(self) -> None:
        pass

    def update_idletasks(self) -> None:
        pass

    def update(self) -> None:
        pass

    def destroy(self) -> None:
        pass


class FakeOverlay:
    def __init__(self, *, x: int, y: int, width: int, height: int, label: str, on_rect_update, **kwargs: Any) -> None:
        self.x = x
        self.y = y
        self.width = width
        self.height = height
        self.label = label
        self.visible = True
        self._callback = on_rect_update

    def update_position(self, x: int, y: int, notify: bool = True) -> None:
        self.x = x
        self.y = y
        if notify:
            self._callback(self.x, self.y, self.width, self.height)

    def update_size(self, width: int, height: int, notify: bool = True) -> None:
        self.width = width
        self.height = height
        if notify:
            self._callback(self.x, self.y, self.width, self.height)

    def update_label(self, label: str) -> None:
        self.label = label

    def show(self) -> None:
        self.visible = True

    def hide(self) -> None:
        self.visible = False

    def get_position(self):
        return self.x, self.y, self.width, self.height

    def simulate_change(self, x: int, y: int, width: int, height: int) -> None:
        self.x = x
        self.y = y
        self.width = width
        self.height = height
        self._callback(self.x, self.y, self.width, self.height)


class FakePoint:
    def __init__(self, *, x: int, y: int, label: str, callback, **kwargs: Any) -> None:
        self.x = x
        self.y = y
        self.label = label
        self.visible = True
        self._callback = callback

    def update_position(self, x: int, y: int, notify: bool = True) -> None:
        self.x = x
        self.y = y
        if notify:
            self._callback(self.x, self.y)

    def update_label(self, label: str) -> None:
        self.label = label

    def show(self) -> None:
        self.visible = True

    def hide(self) -> None:
        self.visible = False

    def get_position(self):
        return self.x, self.y

    def simulate_change(self, x: int, y: int) -> None:
        self.x = x
        self.y = y
        self._callback(self.x, self.y)


class DesktopOverlayManagerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tempdir.cleanup)

        self.tk_patcher = patch("desktop_overlay_manager.tk.Tk", FakeTk)
        self.create_overlay_patcher = patch(
            "desktop_overlay_manager.create_overlay",
            side_effect=lambda **kwargs: FakeOverlay(**kwargs),
        )
        self.create_point_patcher = patch(
            "desktop_overlay_manager.create_point",
            side_effect=lambda **kwargs: FakePoint(**kwargs),
        )
        self.clear_overlays_patcher = patch("desktop_overlay_manager.clear_all_overlays")
        self.clear_points_patcher = patch("desktop_overlay_manager.clear_all_points")

        for patcher in (
            self.tk_patcher,
            self.create_overlay_patcher,
            self.create_point_patcher,
            self.clear_overlays_patcher,
            self.clear_points_patcher,
        ):
            patcher.start()
            self.addCleanup(patcher.stop)

    def _make_manager(self) -> Desktop_overlay_manager:
        manager = Desktop_overlay_manager(config_dir=self.tempdir.name, loop_interval=0.001)

        def cleanup_manager(m: Desktop_overlay_manager = manager) -> None:
            if m._tk_thread and m._tk_thread.is_alive():
                m.destroy()

        self.addCleanup(cleanup_manager)
        return manager

    def _read_config(self) -> Dict[str, Dict[str, Any]]:
        path = Path(self.tempdir.name) / "overlays.json"
        if not path.exists():
            return {}
        with path.open("r", encoding="utf-8") as fh:
            return json.load(fh)

    def test_rect_and_point_persist_in_single_file(self) -> None:
        manager = self._make_manager()
        manager.registerRect("rect-1", label="rect")
        manager.registerPosition("point-1", label="point")

        manager._rects["rect-1"].simulate_change(10, 20, 300, 200)  # type: ignore[attr-defined]
        manager._points["point-1"].simulate_change(30, 40)  # type: ignore[attr-defined]

        config = self._read_config()
        self.assertIn("rects", config)
        self.assertIn("points", config)
        self.assertEqual(config["rects"]["rect-1"]["width"], 300)
        self.assertEqual(config["points"]["point-1"]["y"], 40)

    def test_getters_use_persisted_data_when_widgets_absent(self) -> None:
        first = self._make_manager()
        first.registerRect("rect-2", label="rect")
        first._rects["rect-2"].simulate_change(50, 60, 150, 160)  # type: ignore[attr-defined]
        first.registerPosition("point-2", label="point")
        first._points["point-2"].simulate_change(70, 80)  # type: ignore[attr-defined]

        second = self._make_manager()
        rect = second.getRect("rect-2")
        pos = second.getPosition("point-2")

        self.assertEqual(rect, {"x": 50, "y": 60, "width": 150, "height": 160})
        self.assertEqual(pos, {"x": 70, "y": 80})


if __name__ == "__main__":
    unittest.main()


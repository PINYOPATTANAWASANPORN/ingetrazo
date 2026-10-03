# SPDX-License-Identifier: GPL-3.0-or-later
"""Regression checks for the Windows base-map crash (#327)."""
from __future__ import annotations

from PySide6.QtCore import QUrl

from georef.datum import SceneDatum
from georef.tile_fetcher import TileFetcher
from georef.tiles import PRESETS, TileCache, TileLayer
import views.viewport as viewport_module
from views.viewport import Viewport


class _QueuedTimer:
    callbacks = []

    @classmethod
    def singleShot(cls, _delay, callback):
        cls.callbacks.append(callback)


class _Fetcher:
    def __init__(self):
        self.requests = []

    def request(self, source, x, y, z):
        self.requests.append((source.id, x, y, z))
        return None


def test_missing_tiles_leave_paint_before_starting_network(monkeypatch):
    """A texture lookup during paint only queues work; it never enters QtNetwork."""
    _QueuedTimer.callbacks = []
    viewport = Viewport()
    monkeypatch.setattr(viewport_module, "QTimer", _QueuedTimer)
    layer = TileLayer(PRESETS["osm"], zoom=16)
    datum = SceneDatum(-12.0464, -77.0428)
    viewport.scene.tile_layer = layer
    viewport.scene.georef = datum
    fetcher = _Fetcher()
    monkeypatch.setattr(viewport, "_ensure_tile_fetcher", lambda: fetcher)

    x, y = layer.flat_tiles(datum)[0]
    assert viewport._tile_texture(layer, x, y) is None
    assert fetcher.requests == []
    assert len(_QueuedTimer.callbacks) == 1

    _QueuedTimer.callbacks.pop()()
    assert fetcher.requests
    assert viewport._tile_requests_scheduled is False
    viewport.deleteLater()


class _Signal:
    def connect(self, callback):
        self.callback = callback


class _Reply:
    def __init__(self):
        self.finished = _Signal()


class _NetworkManager:
    def get(self, request):
        self.request = request
        return _Reply()


def test_tile_download_passes_an_explicit_qurl_to_qt(tmp_path):
    fetcher = TileFetcher(TileCache(tmp_path))
    manager = _NetworkManager()
    fetcher._nam = manager

    fetcher._start_download(PRESETS["osm"], 1, 2, 3)

    assert isinstance(manager.request.url(), QUrl)
    assert manager.request.url().toString() == "https://tile.openstreetmap.org/3/1/2.png"

# -*- coding: utf-8 -*-

"""Discreet network status overlay (top-right corner).

Shows connection type (WiFi / 4G / ETH) and signal strength bars.
Designed for on-site debugging during events without distracting guests.
"""

import subprocess
import time

import pibooth
import pygame


# Signal bar colours
_GREEN = (76, 175, 80)
_ORANGE = (255, 152, 0)
_RED = (244, 67, 54)
_GRAY = (158, 158, 158)
_WHITE = (255, 255, 255)
_BG = (30, 30, 30, 153)  # semi-transparent dark pill


def _run(cmd):
    """Run a shell command and return stdout (empty string on failure)."""
    try:
        return subprocess.check_output(cmd, shell=True, text=True, timeout=3).strip()
    except Exception:
        return ""


def _get_default_interface():
    """Return the name of the interface used for the default route."""
    out = _run("ip route get 8.8.8.8 2>/dev/null")
    parts = out.split()
    for part in parts:
        if part.startswith(("wlan", "eth", "usb", "enp", "ens")):
            return part
    if "dev" in parts:
        idx = parts.index("dev")
        if idx + 1 < len(parts):
            return parts[idx + 1]
    return ""


def _wifi_signal_dbm(iface="wlan0"):
    """Read WiFi signal level in dBm from /proc/net/wireless."""
    try:
        with open("/proc/net/wireless") as f:
            for line in f:
                if iface in line:
                    cols = line.split()
                    return int(float(cols[3]))
    except Exception:
        pass
    return None


def _classify_signal(dbm):
    """Convert dBm to (bars 0-4, colour)."""
    if dbm is None:
        return 0, _RED
    if dbm > -50:
        return 4, _GREEN
    if dbm > -65:
        return 3, _GREEN
    if dbm > -75:
        return 2, _ORANGE
    if dbm > -85:
        return 1, _RED
    return 0, _RED


class NetworkStatusPlugin(object):
    """Plugin that draws a small network indicator pill in the top-right
    corner of every screen state (except capture)."""

    name = 'pibooth-core:network-status'

    _CACHE_TTL = 5  # seconds between network checks

    def __init__(self, plugin_manager):
        self._pm = plugin_manager
        self._net_type = "?"
        self._bars = 0
        self._color = _GRAY
        self._last_check = 0

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _refresh(self):
        """Poll network status (throttled to every _CACHE_TTL seconds)."""
        now = time.monotonic()
        if now - self._last_check < self._CACHE_TTL:
            return
        self._last_check = now

        iface = _get_default_interface()
        if not iface:
            self._net_type, self._bars, self._color = "OFF", 0, _GRAY
        elif iface.startswith("wlan"):
            dbm = _wifi_signal_dbm(iface)
            self._bars, self._color = _classify_signal(dbm)
            self._net_type = "WiFi"
        elif iface.startswith("usb"):
            self._net_type, self._bars, self._color = "4G", 3, _GREEN
        else:
            self._net_type, self._bars, self._color = "ETH", 4, _GREEN

    def _draw(self, win):
        """Render the overlay pill on *win.surface*."""
        self._refresh()

        scale = win.display_size[0] / 1920
        pad = int(12 * scale)
        font_size = max(14, int(18 * scale))
        bar_w = max(3, int(5 * scale))
        bar_gap = max(2, int(3 * scale))
        bar_max_h = max(10, int(16 * scale))
        pill_h = max(24, int(28 * scale))
        pill_r = pill_h // 2

        font = pygame.font.SysFont("sans", font_size, bold=True)
        text_surf = font.render(self._net_type, True, _WHITE)
        text_w, text_h = text_surf.get_size()

        bars_total_w = 4 * bar_w + 3 * bar_gap
        spacing = int(6 * scale)

        pill_w = pad + text_w + spacing + bars_total_w + pad
        pill_x = win.display_size[0] - pill_w - int(15 * scale)
        pill_y = int(15 * scale)

        # semi-transparent pill background
        pill_surf = pygame.Surface((pill_w, pill_h), pygame.SRCALPHA)
        pygame.draw.rect(pill_surf, _BG, (0, 0, pill_w, pill_h), border_radius=pill_r)
        win.surface.blit(pill_surf, (pill_x, pill_y))

        # text
        text_y = pill_y + (pill_h - text_h) // 2
        win.surface.blit(text_surf, (pill_x + pad, text_y))

        # signal bars
        bars_x = pill_x + pad + text_w + spacing
        bars_bottom = pill_y + pill_h - int(6 * scale)
        for i in range(4):
            h = int(bar_max_h * (i + 1) / 4)
            x = bars_x + i * (bar_w + bar_gap)
            y = bars_bottom - h
            bar_color = self._color if i < self._bars else _GRAY
            pygame.draw.rect(win.surface, bar_color, (x, y, bar_w, h))

    # ------------------------------------------------------------------
    # Hooks — draw on every state except capture
    # ------------------------------------------------------------------

    @pibooth.hookimpl
    def state_wait_do(self, win):
        self._draw(win)

    @pibooth.hookimpl
    def state_choose_do(self, win):
        self._draw(win)

    @pibooth.hookimpl
    def state_chosen_do(self, win):
        self._draw(win)

    @pibooth.hookimpl
    def state_preview_do(self, win):
        self._draw(win)

    @pibooth.hookimpl
    def state_processing_do(self, win):
        self._draw(win)

    @pibooth.hookimpl
    def state_print_do(self, win):
        self._draw(win)

    @pibooth.hookimpl
    def state_finish_do(self, win):
        self._draw(win)

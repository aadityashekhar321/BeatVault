import os
import sys
import ctypes
from ctypes import wintypes
import logging
import threading
from typing import Optional, Callable

logger = logging.getLogger("tray_and_media")

# Windows Virtual Key Codes for Multimedia
VK_MEDIA_NEXT_TRACK = 0xB0
VK_MEDIA_PREV_TRACK = 0xB1
VK_MEDIA_STOP = 0xB2
VK_MEDIA_PLAY_PAUSE = 0xB3
MOD_NOREPEAT = 0x4000
WM_HOTKEY = 0x0312

class GlobalMediaKeyService:
    """
    Hooks native Windows multimedia keyboard keys (Play/Pause, Next, Prev, Stop)
    so they work globally even when the app is minimized to tray or in background.
    """
    def __init__(
        self,
        on_play_pause: Optional[Callable[[], None]] = None,
        on_next: Optional[Callable[[], None]] = None,
        on_prev: Optional[Callable[[], None]] = None,
    ):
        self.on_play_pause = on_play_pause
        self.on_next = on_next
        self.on_prev = on_prev
        self._thread: Optional[threading.Thread] = None
        self._thread_id: Optional[int] = None
        self._stop_event = threading.Event()

    def start(self):
        """Starts the message loop thread for global media keys."""
        if self._thread and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()
        logger.info("Global multimedia keys listener started.")

    def stop(self):
        """Stops the listener and unregisters hotkeys."""
        self._stop_event.set()
        if self._thread_id:
            # Post WM_QUIT to thread message queue to break GetMessage
            WM_QUIT = 0x0012
            ctypes.windll.user32.PostThreadMessageW(self._thread_id, WM_QUIT, 0, 0)
        logger.info("Global multimedia keys listener stopped.")

    def _run_loop(self):
        user32 = ctypes.windll.user32
        kernel32 = ctypes.windll.kernel32
        self._thread_id = kernel32.GetCurrentThreadId()

        # Register hotkeys for media buttons
        hotkeys = [
            (101, VK_MEDIA_PLAY_PAUSE),
            (102, VK_MEDIA_NEXT_TRACK),
            (103, VK_MEDIA_PREV_TRACK),
            (104, VK_MEDIA_STOP),
        ]

        registered_ids = []
        for hk_id, vk in hotkeys:
            if user32.RegisterHotKey(None, hk_id, MOD_NOREPEAT, vk):
                registered_ids.append(hk_id)
            else:
                logger.debug(f"Could not register media key 0x{vk:X} (may already be hooked)")

        msg = wintypes.MSG()
        try:
            while not self._stop_event.is_set():
                res = user32.GetMessageW(ctypes.byref(msg), None, 0, 0)
                if res <= 0:
                    break

                if msg.message == WM_HOTKEY:
                    hk_id = msg.wParam
                    if hk_id == 101 or hk_id == 104:
                        if self.on_play_pause:
                            self.on_play_pause()
                    elif hk_id == 102:
                        if self.on_next:
                            self.on_next()
                    elif hk_id == 103:
                        if self.on_prev:
                            self.on_prev()

                user32.TranslateMessage(ctypes.byref(msg))
                user32.DispatchMessageW(ctypes.byref(msg))
        finally:
            for hk_id in registered_ids:
                user32.UnregisterHotKey(None, hk_id)


class SystemTrayService:
    """
    Manages the Windows Notification Tray icon and context menu.
    Allows minimizing BeatVault to tray and controlling playback.
    """
    def __init__(
        self,
        icon_path: str,
        on_show: Optional[Callable[[], None]] = None,
        on_toggle_play: Optional[Callable[[], None]] = None,
        on_next: Optional[Callable[[], None]] = None,
        on_prev: Optional[Callable[[], None]] = None,
        on_quit: Optional[Callable[[], None]] = None,
    ):
        self.icon_path = icon_path
        self.on_show = on_show
        self.on_toggle_play = on_toggle_play
        self.on_next = on_next
        self.on_prev = on_prev
        self.on_quit = on_quit
        self.tray_icon = None
        self._thread: Optional[threading.Thread] = None

    def start(self):
        """Initializes and displays the system tray icon in a background thread."""
        try:
            import pystray
            from PIL import Image

            if not os.path.exists(self.icon_path):
                logger.warning(f"Tray icon image not found: {self.icon_path}")
                return

            image = Image.open(self.icon_path)

            def action_show(icon, item):
                if self.on_show:
                    self.on_show()

            def action_toggle_play(icon, item):
                if self.on_toggle_play:
                    self.on_toggle_play()

            def action_next(icon, item):
                if self.on_next:
                    self.on_next()

            def action_prev(icon, item):
                if self.on_prev:
                    self.on_prev()

            def action_quit(icon, item):
                icon.stop()
                if self.on_quit:
                    self.on_quit()

            menu = pystray.Menu(
                pystray.MenuItem("🎵 BeatVault", action_show, default=True),
                pystray.Menu.SEPARATOR,
                pystray.MenuItem("▶ / ⏸  Play / Pause", action_toggle_play),
                pystray.MenuItem("⏭  Next Track", action_next),
                pystray.MenuItem("⏮  Previous Track", action_prev),
                pystray.Menu.SEPARATOR,
                pystray.MenuItem("🪟 Show Window", action_show),
                pystray.MenuItem("✕  Exit BeatVault", action_quit),
            )

            self.tray_icon = pystray.Icon(
                "BeatVault",
                image,
                "BeatVault - Music Studio",
                menu=menu
            )

            self._thread = threading.Thread(target=self.tray_icon.run, daemon=True)
            self._thread.start()
            logger.info("System tray icon started.")
        except Exception as e:
            logger.warning(f"Failed to start system tray service: {e}")

    def notify(self, title: str, message: str):
        """Shows a balloon notification in Windows notification center."""
        if self.tray_icon:
            try:
                self.tray_icon.notify(message, title)
            except Exception as e:
                logger.debug(f"Tray notification error: {e}")

    def stop(self):
        """Stops the system tray icon."""
        if self.tray_icon:
            try:
                self.tray_icon.stop()
            except Exception:
                pass

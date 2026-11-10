import os
import sys
import logging
import argparse
import webbrowser
from http.server import HTTPServer, SimpleHTTPRequestHandler
import threading

# Configure Logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("main")

# Add current directory to path (Supports PyInstaller frozen binary)
if getattr(sys, 'frozen', False):
    current_dir = getattr(sys, '_MEIPASS', os.path.dirname(sys.executable))
else:
    current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

import static_ffmpeg
try:
    static_ffmpeg.add_paths()
    logger.info("Static FFmpeg initialized.")
except Exception as e:
    logger.warning(f"Static FFmpeg path init warning: {e}")

from api import AppAPI
from tray_and_media_service import SystemTrayService, GlobalMediaKeyService

def run_desktop_app():
    """Launches the native desktop window using pywebview with tray and media keys."""
    import webview

    html_file = os.path.join(current_dir, "gui", "index.html")
    if not os.path.exists(html_file):
        raise FileNotFoundError(f"GUI file not found: {html_file}")

    app_api = AppAPI()
    
    logger.info("Creating desktop window...")
    window = webview.create_window(
        title="BeatVault - Music & Lyrics Studio",
        url=f"file:///{html_file.replace(os.sep, '/')}",
        js_api=app_api,
        width=1120,
        height=780,
        min_size=(880, 620),
        background_color="#0f1115"
    )

    app_api.set_window(window)

    # Initialize System Tray and Global Media Keys
    icon_path = os.path.join(current_dir, "assets", "icon.png")

    def on_media_play_pause():
        logger.info("Global Media Key: Play/Pause triggered")
        app_api.trigger_media_key("play_pause")

    def on_media_next():
        logger.info("Global Media Key: Next Track triggered")
        app_api.trigger_media_key("next")

    def on_media_prev():
        logger.info("Global Media Key: Prev Track triggered")
        app_api.trigger_media_key("prev")

    # Start global media keys
    media_keys = GlobalMediaKeyService(
        on_play_pause=on_media_play_pause,
        on_next=on_media_next,
        on_prev=on_media_prev
    )
    media_keys.start()

    # Start system tray
    def on_tray_show():
        if window:
            window.show()
            window.restore()

    def on_tray_quit():
        media_keys.stop()
        if window:
            window.destroy()

    tray = SystemTrayService(
        icon_path=icon_path,
        on_show=on_tray_show,
        on_toggle_play=on_media_play_pause,
        on_next=on_media_next,
        on_prev=on_media_prev,
        on_quit=on_tray_quit
    )
    tray.start()
    app_api.set_tray_service(tray)
    
    logger.info("Starting pywebview loop...")
    try:
        webview.start(debug=False)
    finally:
        media_keys.stop()
        tray.stop()

def run_browser_mode(port=8080):
    """
    Fallback server mode: runs a local server and opens the browser.
    Useful for testing or if WebView2 is missing.
    """
    import json
    from urllib.parse import urlparse, parse_qs
    from http.server import BaseHTTPRequestHandler

    app_api = AppAPI()

    class RequestHandler(BaseHTTPRequestHandler):
        def log_message(self, format, *args):
            pass  # suppress default log spam

        def do_GET(self):
            parsed = urlparse(self.path)
            if parsed.path == "/" or parsed.path == "/index.html":
                html_path = os.path.join(current_dir, "gui", "index.html")
                with open(html_path, "r", encoding="utf-8") as f:
                    content = f.read()

                # Inject browser compatibility shim for window.pywebview.api
                shim = """
                <script>
                  window.pywebview = {
                    api: {
                      get_default_folder: async () => {
                        const r = await fetch('/api/get_default_folder');
                        const data = await r.json();
                        return data.folder;
                      },
                      select_folder: async () => {
                        const r = await fetch('/api/select_folder');
                        const data = await r.json();
                        return data.folder;
                      },
                      open_folder: async (folder) => {
                        const r = await fetch('/api/open_folder', {
                          method: 'POST',
                          headers: {'Content-Type': 'application/json'},
                          body: JSON.stringify({folder})
                        });
                        return await r.json();
                      },
                      load_playlist: async (url) => {
                        const r = await fetch('/api/load_playlist', {
                          method: 'POST',
                          headers: {'Content-Type': 'application/json'},
                          body: JSON.stringify({url})
                        });
                        return await r.json();
                      },
                      scan_duplicates: async (tracks, folder) => {
                        const r = await fetch('/api/scan_duplicates', {
                          method: 'POST',
                          headers: {'Content-Type': 'application/json'},
                          body: JSON.stringify({tracks, folder})
                        });
                        return await r.json();
                      },
                      search_single_song: async (query) => {
                        const r = await fetch('/api/search_single_song', {
                          method: 'POST',
                          headers: {'Content-Type': 'application/json'},
                          body: JSON.stringify({query})
                        });
                        return await r.json();
                      },
                      get_audio_data: async (file_path) => {
                        const r = await fetch('/api/get_audio_data', {
                          method: 'POST',
                          headers: {'Content-Type': 'application/json'},
                          body: JSON.stringify({file_path})
                        });
                        return await r.json();
                      },
                      start_download: async (tracks, folder, title, quality, filename_template, embed_lyrics, save_lrc_file) => {
                        const r = await fetch('/api/start_download', {
                          method: 'POST',
                          headers: {'Content-Type': 'application/json'},
                          body: JSON.stringify({tracks, folder, title, quality, filename_template, embed_lyrics, save_lrc_file})
                        });
                        return await r.json();
                      },
                      respond_duplicate: async (decision, apply_to_all) => {
                        const r = await fetch('/api/respond_duplicate', {
                          method: 'POST',
                          headers: {'Content-Type': 'application/json'},
                          body: JSON.stringify({decision, apply_to_all})
                        });
                        return await r.json();
                      },
                      pause_download: async () => {
                        const r = await fetch('/api/pause_download');
                        return await r.json();
                      },
                      resume_download: async () => {
                        const r = await fetch('/api/resume_download');
                        return await r.json();
                      },
                      cancel_download: async () => {
                        const r = await fetch('/api/cancel_download');
                        return await r.json();
                      },
                      minimize_to_tray: async () => {
                        const r = await fetch('/api/minimize_to_tray');
                        return await r.json();
                      },
                      restore_from_tray: async () => {
                        const r = await fetch('/api/restore_from_tray');
                        return await r.json();
                      }
                    }
                  };
                  // Poll for progress updates in browser mode
                  setInterval(async () => {
                    try {
                      const r = await fetch('/api/poll_events');
                      const events = await r.json();
                      events.forEach(e => {
                        if (window.handleBackendEvent) {
                          window.handleBackendEvent(e.event, e.data);
                        }
                      });
                    } catch(err){}
                  }, 800);
                  setTimeout(() => {
                    window.dispatchEvent(new Event('pywebviewready'));
                  }, 200);
                </script>
                """
                content = content.replace("</head>", shim + "</head>")
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.end_headers()
                self.wfile.write(content.encode("utf-8"))

            elif parsed.path == "/api/get_default_folder":
                folder = app_api.get_default_folder()
                self._send_json({"folder": folder})

            elif parsed.path == "/api/select_folder":
                folder = app_api.select_folder()
                self._send_json({"folder": folder})

            elif parsed.path == "/api/poll_events":
                # Drain event queue
                events = []
                while not event_queue.empty():
                    try:
                        events.append(event_queue.get_nowait())
                    except Exception:
                        break
                self._send_json(events)

            elif parsed.path == "/api/pause_download":
                self._send_json(app_api.pause_download())

            elif parsed.path == "/api/resume_download":
                self._send_json(app_api.resume_download())

            elif parsed.path == "/api/cancel_download":
                self._send_json(app_api.cancel_download())

            elif parsed.path == "/api/minimize_to_tray":
                self._send_json(app_api.minimize_to_tray())

            elif parsed.path == "/api/restore_from_tray":
                self._send_json(app_api.restore_from_tray())

            else:
                self.send_response(404)
                self.end_headers()

        def do_POST(self):
            parsed = urlparse(self.path)
            content_length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_length)
            payload = json.loads(body.decode("utf-8")) if body else {}

            if parsed.path == "/api/load_playlist":
                res = app_api.load_playlist(payload.get("url", ""))
                self._send_json(res)

            elif parsed.path == "/api/open_folder":
                res = app_api.open_folder(payload.get("folder", ""))
                self._send_json({"success": res})

            elif parsed.path == "/api/scan_duplicates":
                res = app_api.scan_duplicates(payload.get("tracks", []), payload.get("folder", ""))
                self._send_json(res)

            elif parsed.path == "/api/search_single_song":
                res = app_api.search_single_song(payload.get("query", ""))
                self._send_json(res)

            elif parsed.path == "/api/get_audio_data":
                res = app_api.get_audio_data(payload.get("file_path", ""))
                self._send_json(res)

            elif parsed.path == "/api/start_download":
                res = app_api.start_download(
                    payload.get("tracks", []),
                    payload.get("folder", ""),
                    payload.get("title", "Music Playlist"),
                    payload.get("quality", "192"),
                    payload.get("filename_template", "title_artist"),
                    payload.get("embed_lyrics", True),
                    payload.get("save_lrc_file", True)
                )
                self._send_json(res)

            elif parsed.path == "/api/respond_duplicate":
                res = app_api.respond_duplicate(
                    payload.get("decision", "skip"),
                    payload.get("apply_to_all", False)
                )
                self._send_json(res)

            else:
                self.send_response(404)
                self.end_headers()

        def _send_json(self, data):
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(json.dumps(data).encode("utf-8"))

    import queue
    event_queue = queue.Queue()

    # Intercept pywebview send_event_to_frontend for browser mode
    def browser_event_sender(event_name, data):
        event_queue.put({"event": event_name, "data": data})

    app_api._send_event_to_frontend = browser_event_sender

    server = HTTPServer(("127.0.0.1", port), RequestHandler)
    url = f"http://127.0.0.1:{port}"
    print(f"\n==========================================")
    print(f"  BeatVault Music Studio running at:")
    print(f"  {url}")
    print(f"==========================================\n")
    webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down server.")

def main():
    parser = argparse.ArgumentParser(description="BeatVault - Music & Lyrics Studio")
    parser.add_argument("--browser", action="store_true", help="Launch in default web browser instead of desktop window")
    parser.add_argument("--port", type=int, default=8080, help="Port for browser mode (default: 8080)")
    args = parser.parse_args()

    if args.browser:
        run_browser_mode(args.port)
    else:
        try:
            run_desktop_app()
        except Exception as e:
            logger.warning(f"Desktop GUI mode encountered an issue: {e}")
            logger.info("Falling back to browser mode...")
            run_browser_mode(args.port)

if __name__ == "__main__":
    main()

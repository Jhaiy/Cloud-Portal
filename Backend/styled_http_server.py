from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from functools import partial
from html import escape
from pathlib import Path
from urllib.parse import quote
import argparse
import io
import os
import mimetypes
import re


PAGE_STYLE = """
<style>
  :root {
    color-scheme: dark;
    --bg: #0b111b;
    --panel: #121927;
    --panel-2: #192235;
    --text: #e7ecf5;
    --muted: #9aa7bd;
    --accent: #6fc6ff;
    --border: #283349;
    --hover: #223249;
    --tile: #161f31;
  }

  * { box-sizing: border-box; }

  body {
    margin: 0;
    padding: 24px;
    background: radial-gradient(circle at top, #15243a 0%, var(--bg) 60%);
    color: var(--text);
    font-family: Segoe UI, Arial, sans-serif;
  }

  .shell {
    max-width: 1280px;
    margin: 0 auto;
    background: rgba(23, 26, 33, 0.92);
    border: 1px solid var(--border);
    border-radius: 16px;
    overflow: hidden;
    box-shadow: 0 24px 80px rgba(0, 0, 0, 0.35);
  }

  header {
    padding: 18px 22px 14px;
    border-bottom: 1px solid var(--border);
    background: linear-gradient(180deg, rgba(125, 211, 252, 0.08), transparent);
  }

  h1 {
    margin: 0;
    font-size: 34px;
    font-weight: 700;
    letter-spacing: 0.02em;
  }

  .path {
    margin-top: 6px;
    color: var(--muted);
    font-size: 13px;
  }

  .layout {
    display: grid;
    grid-template-columns: 280px 1fr;
    min-height: 560px;
  }

  .sidebar {
    border-right: 1px solid var(--border);
    background: linear-gradient(180deg, rgba(111, 198, 255, 0.06), transparent);
    padding: 14px;
  }

  .sidebar-title {
    margin: 6px 8px 12px;
    font-size: 12px;
    text-transform: uppercase;
    letter-spacing: 0.1em;
    color: var(--muted);
  }

  .dir-list {
    display: flex;
    flex-direction: column;
    gap: 2px;
  }

  .dir-link {
    display: block;
    padding: 8px 10px;
    border-radius: 9px;
    color: var(--text);
    text-decoration: none;
    border: 1px solid transparent;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }

  .dir-link:hover {
    background: var(--hover);
    border-color: rgba(111, 198, 255, 0.3);
    text-decoration: none;
  }

  .dir-link.active {
    background: rgba(111, 198, 255, 0.18);
    border-color: rgba(111, 198, 255, 0.45);
  }

  .main {
    padding: 16px;
  }

  .grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(140px, 1fr));
    gap: 14px;
  }

  .search {
    margin-bottom: 12px;
    display: flex;
    gap: 8px;
    align-items: center;
  }

  .search input[type="search"] {
    width: 100%;
    padding: 10px 12px;
    border-radius: 8px;
    border: 1px solid var(--border);
    background: rgba(255,255,255,0.02);
    color: var(--text);
    outline: none;
  }

  .tile {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 10px;
    padding: 12px 10px 14px;
    border-radius: 12px;
    border: 1px solid transparent;
    background: rgba(22, 31, 49, 0.45);
    text-decoration: none;
    color: var(--text);
    min-height: 150px;
  }

  .tile:hover {
    background: var(--tile);
    border-color: rgba(111, 198, 255, 0.35);
    text-decoration: none;
  }

  .icon {
    width: 72px;
    height: 72px;
    display: grid;
    place-items: center;
    font-size: 48px;
    border-radius: 14px;
    background: rgba(255, 255, 255, 0.04);
  }

  .name {
    text-align: center;
    font-size: 14px;
    line-height: 1.35;
    word-break: break-word;
  }

  .meta {
    color: var(--muted);
    font-size: 12px;
  }

  a {
    color: var(--accent);
    text-decoration: none;
  }

  a:hover { text-decoration: underline; }

  .footer {
    padding: 12px 18px 16px;
    color: var(--muted);
    font-size: 13px;
    border-top: 1px solid var(--border);
  }

  @media (max-width: 900px) {
    body { padding: 12px; }
    .layout { grid-template-columns: 1fr; }
    .sidebar { border-right: none; border-bottom: 1px solid var(--border); }
  }
</style>
"""


class StyledHTTPRequestHandler(SimpleHTTPRequestHandler):
  def end_headers(self):
    self.send_header("ngrok-skip-browser-warning", "any-value")
    self.send_header("Accept-Ranges", "bytes")
    super().end_headers()

  def guess_type(self, path):
    base_type = super().guess_type(path)
    if path.endswith('.mp4'): return 'video/mp4'
    return base_type
  
  def do_GET(self):
    """Treat video files as streamable or handle explicit Range requests."""
    path_on_disk = self.translate_path(self.path)
    ext = Path(path_on_disk).suffix.lower()
    VIDEO_EXTS = {'.mp4', '.webm', '.ogg', '.mov'}
    if "Range" in self.headers or ext in VIDEO_EXTS:
      self.handle_range_request()
    else:
      super().do_GET()

  def handle_range_request(self):
    """Handle byte-range requests and stream files in chunks (sendfile fast-path).

    Accepts missing Range headers (streams whole file starting at 0) to
    allow browsers to begin playback immediately for large video files.
    """
    path = self.translate_path(self.path)
    if not os.path.isfile(path):
      self.send_error(404)
      return

    size = os.path.getsize(path)
    range_header = self.headers.get('Range')
    match = re.match(r'bytes=(\d+)-(\d+)?', range_header) if range_header else None

    if match:
      start = int(match.group(1))
      end = int(match.group(2)) if match.group(2) else size - 1
      status = 206
    else:
      start = 0
      end = size - 1
      status = 200

    if start >= size:
      self.send_error(416, "Requested Range Not Satisfied")
      return

    chunk_size = end - start + 1

    self.send_response(status)
    self.send_header("Content-Type", self.guess_type(path))
    if status == 206:
      self.send_header("Content-Range", f"bytes {start}-{end}/{size}")
    self.send_header("Content-Length", str(chunk_size))
    self.send_header("Accept-Ranges", "bytes")
    self.end_headers()

    try:
      with open(path, 'rb') as f:
        f.seek(start)
        remaining = chunk_size
        sock = getattr(self, "connection", None)
        if sock is not None and hasattr(sock, "sendfile"):
          while remaining > 0:
            to_send = min(64 * 1024, remaining)
            try:
              sent = sock.sendfile(f, offset=f.tell(), count=to_send)
            except (BlockingIOError, OSError):
              break
            if not sent:
              break
            remaining -= sent
        if remaining > 0:
          f.seek(f.tell())
          bufsize = 64 * 1024
          while remaining > 0:
            data = f.read(min(bufsize, remaining))
            if not data:
              break
            self.wfile.write(data)
            remaining -= len(data)
    except Exception:
      pass

  def list_directory(self, path):
    VIDEO_EXTS = {'.mp4', '.webm', '.ogg', '.mov'}

    try:
      entries = sorted(
        os.listdir(path),
        key=lambda name: (not os.path.isdir(os.path.join(path, name)), name.lower())
      )
    except OSError:
      self.send_error(404, "No permission to list directory")
      return None

    displaypath = escape(self.path, quote=False)
    title = f"Directory listing for {displaypath}"

    sidebar_items = []
    main_tiles = []

    if self.path != "/":
      parent = Path(self.path.rstrip("/")).parent.as_posix()
      parent_href = parent if parent.startswith("/") else f"/{parent}"
      sidebar_items.append(
        f'<a class="dir-link" href="{quote(parent_href)}">..</a>'
      )

    sidebar_items.append(
      f'<a class="dir-link active" href="{quote(self.path)}">{escape(Path(path).name or path)}</a>'
    )

    for name in entries:
      full_path = os.path.join(path, name)
      display_name = escape(name)
      href = quote(name)
      if os.path.isdir(full_path):
        display_name += "/"
        href += "/"
        sidebar_items.append(
          f'<a class="dir-link" href="{href}">{display_name}</a>'
        )
        main_tiles.append(
          f'<a class="tile" href="{href}"><div class="icon">📁</div><div class="name">{display_name}</div><div class="meta">Folder</div></a>'
        )
      else:
        size = f"{os.path.getsize(full_path):,} B"
        ext = Path(name).suffix.lower()
        if ext in VIDEO_EXTS:
          main_tiles.append(
            f'<a class="tile" href="{href}" target="_blank">'
            f'<div class="icon">🎬</div>'
            f'<div class="name">{display_name}</div>'
            f'<div class="meta">{size}</div>'
            f'</a>'
          )
        else:
          main_tiles.append(
            f'<a class="tile" href="{href}" target="_blank">'
            f'<div class="icon">📄</div>'
            f'<div class="name">{display_name}</div>'
            f'<div class="meta">{size}</div>'
            f'</a>'
          )

    sidebar_html = "\n".join(sidebar_items) if sidebar_items else '<div class="meta">No folders</div>'
    main_html = "\n".join(main_tiles) if main_tiles else '<div class="meta">This folder is empty.</div>'

    content = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{title}</title>
  {PAGE_STYLE}
</head>
<body>
  <div class="shell">
    <header>
      <h1>{title}</h1>
      <div class="path">Serving from: {escape(os.path.abspath(path))}</div>
    </header>
    <div class="layout">
      <aside class="sidebar">
        <div class="sidebar-title">Folders</div>
        <div class="dir-list">{sidebar_html}</div>
      </aside>
      <main class="main">
        <div class="search">
          <input id="searchBox" type="search" placeholder="Search files and folders..." aria-label="Search files" />
        </div>
        <div class="grid">{main_html}</div>
      </main>
    </div>
    <div class="footer">Cloud Portal file server</div>
  </div>
  <script>
    (function(){{
      const search = document.getElementById('searchBox');
      if(!search) return;
      const tiles = () => Array.from(document.querySelectorAll('.grid .tile'));
      const links = () => Array.from(document.querySelectorAll('.dir-list .dir-link'));

      function normalize(s){{ return (s||'').toLowerCase(); }}

      search.addEventListener('input', function(e){{
        const q = normalize(e.target.value.trim());
        // filter tiles
        tiles().forEach(t => {{
          const nameEl = t.querySelector('.name');
          const txt = normalize(nameEl && nameEl.textContent);
          t.style.display = q === '' || txt.includes(q) ? '' : 'none';
        }});
        // filter sidebar links
        links().forEach(a => {{
          const txt = normalize(a.textContent);
          a.style.display = q === '' || txt.includes(q) ? '' : 'none';
        }});
      }});
    }})();
  </script>
</body>
</html>"""

    encoded = content.encode("utf-8", "surrogateescape")
    body = io.BytesIO(encoded)
    self.send_response(200)
    self.send_header("Content-Type", "text/html; charset=utf-8")
    self.send_header("Content-Length", str(len(encoded)))
    self.end_headers()
    return body


def run_server(directory, port=7000, bind="0.0.0.0"):
  httpd = create_server(directory, port, bind)
  httpd.serve_forever()


def create_server(directory, port=7000, bind="0.0.0.0"):
    class BoundHandler(StyledHTTPRequestHandler):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, directory=directory, **kwargs)
    return ThreadingHTTPServer((bind, port), BoundHandler)

def main():
  parser = argparse.ArgumentParser()
  parser.add_argument("directory")
  parser.add_argument("--port", type=int, default=7000)
  parser.add_argument("--bind", default="0.0.0.0")
  args = parser.parse_args()

  print(f"Styled server starting on {args.bind}:{args.port}", flush=True)
  print(f"Serving files from: {args.directory}", flush=True)

  os.chdir(args.directory)
  run_server(args.directory, args.port, args.bind)


if __name__ == "__main__":
  main()
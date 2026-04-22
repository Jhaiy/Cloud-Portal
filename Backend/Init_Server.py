import subprocess
import os
import sys
import threading
import socket
import urllib.request
import urllib.error
from pyngrok import ngrok, conf
import time
from Backend.styled_http_server import create_server

# Dev note: The playit support is currently disabled due to costing. 
# I may bring it back in the future if I can find a way to make it work without costing me money, but for now it's just not worth it. 
# The code is still here and can be easily re-enabled if needed, but for now it's just not worth the hassle.

# def check_playit_client(log):
#   script_path = os.path.join(os.path.dirname(__file__), "Scripts", "Check_Playit.ps1")
#   subprocess.run([
#     "powershell",
#     "-ExecutionPolicy", "Bypass",
#     "-File", script_path
#   ], 
#     stdout=subprocess.PIPE,
#     stderr=subprocess.STDOUT,
#     text=True,
#     check=True,
#   )
#   log("Playit.gg client is installed and ready to use.")

# def locate_playit_client():
#   possible_paths = [
#     os.path.join(os.environ.get("LOCALAPPDATA", ""), "Programs", "playit", "playit.exe"),
#     os.path.join(os.environ.get("APPDATA", ""), "playit", "playit.exe"),
#     r"C:\Program Files\playit\playit.exe",
#     r"C:\Program Files\playit_gg\bin\playit.exe",
#     r"C:\Program Files (x86)\playit\playit.exe"
#   ]

#   for path in possible_paths:
#     if os.path.isfile(path):
#       return path
    
#   return None

# def _monitor_playit_setup(proc, log):
#   return_code = proc.wait()
#   if return_code == 0:
#     log("Playit setup completed successfully.")
#   elif return_code in (1, 2, 130, 3221225786):
#     log("Playit setup was cancelled by the user.")
#   else:
#     log(f"Playit setup failed with return code: {return_code}")

# def start_playit_client(log):
#   executable_path = locate_playit_client()

#   try:
#     if executable_path:
#       log(f"Starting Playit.gg client from: {executable_path}")
#       proc = subprocess.Popen([executable_path], creationflags=subprocess.CREATE_NEW_CONSOLE)

#   except FileNotFoundError:
#     try:
#       os.startfile("playit://")
#       log("Playit started via protocol handler.")
#     except Exception:
#       check_playit_client(log)

#   threading.Thread(target=_monitor_playit_setup, args=(proc, log), daemon=True).start()
#   log("Playit.gg client started.")

current_process = None
current_tunnel = None
current_server = None
current_server_thread = None

CREATE_NO_WINDOW = 0x08000000

def get_resource_path(relative_path):
    if getattr(sys, 'frozen', False):
        base_path = sys._MEIPASS
    else:
        base_path = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    return os.path.join(base_path, relative_path)

def stop_server(log):
  global current_process, current_tunnel, current_server, current_server_thread
    
  if current_tunnel:
    log("Stopping ngrok tunnel...")
    try:
      ngrok.disconnect(current_tunnel.public_url)
    except Exception:
      pass
    ngrok.kill()
    current_tunnel = None

  if current_server:
    log("Stopping HTTP server...")
    current_server.shutdown()
    current_server.server_close()
    current_server = None
    current_server_thread = None
    
  if current_process:
    log("Stopping server process...")
    current_process.terminate()
    current_process = None
    
    log("Server stopped.")

def start_ngrok_tunnel(port, log):
  global current_tunnel
  try: 
    log("Starting ngrok tunnel...")
    current_tunnel = ngrok.connect(addr=f"http://127.0.0.1:{port}")
    public_url = current_tunnel.public_url

    log(f"ngrok tunnel established at: {public_url}")
    return public_url
  
  except Exception as e:
    log(f"Failed to start ngrok tunnel: {e}")
    return None

def stream_process(cmd, log, cwd=None):
  process = subprocess.Popen(
    cmd, 
    stdout=subprocess.PIPE, 
    stderr=subprocess.STDOUT, 
    text=True, 
    bufsize=1,
    cwd=cwd
  )

  for line in process.stdout:
    log(line.rstrip())
  
  return_code = process.wait()
  if return_code != 0:
    raise subprocess.CalledProcessError(return_code, process.args)


def is_server_up(host="127.0.0.1", port=7000, timeout=0.25):
  try:
    with socket.create_connection((host, port), timeout=timeout):
      return True
  except OSError:
    return False


def is_http_ready(host="127.0.0.1", port=7000, timeout=1.0):
  url = f"http://{host}:{port}/"
  try:
    with urllib.request.urlopen(url, timeout=timeout) as response:
      return (200 <= response.status < 500, None)
  except urllib.error.HTTPError as e:
    return (True, f"HTTP error during probe: {e.code}")
  except Exception as e:
    return (False, str(e))

def init_server(log, directory, auth_token):
  global current_server, current_server_thread
  PORT = 7000

  try:
    log("Starting server...")
    os.chdir(directory)
    ngrok.set_auth_token(auth_token)
    current_server = create_server(directory, PORT, "0.0.0.0")

    def _serve_and_log():
      try:
        current_server.serve_forever()
      except Exception as e:
        log(f"HTTP server thread crashed: {e}")

    current_server_thread = threading.Thread(target=_serve_and_log, daemon=True)
    current_server_thread.start()

    log("Waiting for server to stabilize...")
    max_wait_seconds = 10
    started = False
    last_http_error = "no response"
    for _ in range(max_wait_seconds * 10):
      up = is_server_up(port=PORT)
      ready, probe_error = is_http_ready(port=PORT)
      if probe_error:
        last_http_error = probe_error

      if up and ready:
        started = True
        break
      time.sleep(0.1)

    if not started:
      log(f"HTTP server failed to start on port 7000. Last probe error: {last_http_error}")
      return

    tunnel_url = start_ngrok_tunnel(PORT, log)

    if tunnel_url:
      log("--- SERVER INFO ---")
      log(f"Local: http://localhost:{PORT}")
      log(f"Global: {tunnel_url}")
      log("-------------------")
    else:
      log("Tunnel did not start. Local server is still running.")

  except Exception as e:
    log(f"An error occurred while starting the client: {e}")
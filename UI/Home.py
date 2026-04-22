import dearpygui.dearpygui as dpg
import queue
import threading
import os
import sys
import multiprocessing

def get_resource_path(relative_path):
  if getattr(sys, 'frozen', False):
    return os.path.join(sys._MEIPASS, relative_path)
  return os.path.join(os.path.abspath("."), relative_path)

if getattr(sys, 'frozen', False):
    bundle_dir = sys._MEIPASS
    sys.path.append(bundle_dir)

from UI.Theme import create_warning_theme as warning_theme
from UI.Theme import init_header, add_header, button_theme, caution_button
from Backend.Init_Server import init_server as server, is_server_up, stop_server

dpg.create_context()
dpg.create_viewport(title='Cloud Portal', resizable=False, width=1000, height=750)

log_queue = queue.Queue()
full_log = ""
server_status_text = "Server offline"
server_status_color = (220, 80, 80, 255)

def log_output(msg):
  log_queue.put(msg)

def start_server_callback():
  directory_path = dpg.get_value("file_directory")
  ngrok_token = dpg.get_value("ngrok_auth_token")
  if not directory_path:
    log_output("Error: No directory selected")
  
  if not ngrok_token:
    log_output("Error: Ngrok auth token is required")

  threading.Thread(target=server, args=(log_output, directory_path, ngrok_token), daemon=True).start()

def stop_server_callback():
  log_output("Stopping server...")
  threading.Thread(target=stop_server, args=(log_output,), daemon=True).start()

def pump_log():
  global full_log
  updated = False
  while not log_queue.empty():
    full_log += log_queue.get() + "\n"
    updated = True
  if updated:
    dpg.set_value("log_output", full_log)


def pump_status():
  global server_status_text, server_status_color
  if is_server_up():
    new_text = "Server online"
    new_color = (90, 220, 90, 255)
  else:
    new_text = "Server offline"
    new_color = (220, 80, 80, 255)

  if new_text != server_status_text or new_color != server_status_color:
    server_status_text = new_text
    server_status_color = new_color
    dpg.configure_item("server_status", default_value=f"● {server_status_text}")
    dpg.configure_item("server_status", color=server_status_color)

def select_directory_native():
  import tkinter as tk
  from tkinter import filedialog

  
  root = tk.Tk()
  root.withdraw()
  root.attributes('-topmost', True)

  folder_selected = filedialog.askdirectory()

  root.destroy()

  if folder_selected:
    dpg.set_value("file_directory", folder_selected)

def close_banner():
  dpg.hide_item("warning_banner")

def callback(sender, app_data):
    print('OK was clicked.')
    print("Sender: ", sender)
    print("App Data: ", app_data)

def cancel_callback(sender, app_data):
  print('Cancel was clicked.')
  print("Sender: ", sender)
  print("App Data: ", app_data)

init_header()
button_theme()
caution_button()

def main():
  with dpg.window(label="Cloud Portal", no_title_bar=True, no_resize=True, no_move=True, width=1000, height=800):
    with dpg.child_window(tag="warning_banner", height=40, width=-1):
      dpg.bind_item_theme(dpg.last_item(), warning_theme())
      dpg.add_text("Disclaimer: Be careful who you share your IP with, it can be used to attack you.")

    add_header("Welcome to Cloud Portal!", 1)
    dpg.add_text("Easily setup a temporary web server to share files or host locally for file sharing, movies, or even light web hosting. \nPerfect for quick demos, sharing files on the fly, or just experimenting with web servers without the hassle of complex configurations.")
    dpg.add_separator()

    add_header("Ngrok Auth Token:", 3)
    ngrok_token = dpg.add_input_text(tag="ngrok_auth_token", label="Ngrok Auth Token", password=True, width=-1)

    add_header("Select a directory to host:", 3)

    directory = dpg.add_input_text(tag="file_directory", multiline=False, readonly=True, width=-1)
    dpg.add_button(label="Select directory", callback=select_directory_native)

    dpg.add_text("● Server offline", tag="server_status", color=server_status_color)

    dpg.add_text("Console:")
    dpg.add_input_text(tag="log_output", multiline=True, readonly=True, width=-1, height=350)

    with dpg.group(horizontal=True):
      start_button = dpg.add_button(label="Start Server", callback=start_server_callback)
      stop_button = dpg.add_button(label="Stop Server", callback=stop_server_callback)
      dpg.bind_item_theme(start_button, button_theme())
      dpg.bind_item_theme(stop_button, caution_button())

  dpg.setup_dearpygui()
  dpg.show_viewport()

  while dpg.is_dearpygui_running():
    pump_log()
    pump_status()
    dpg.render_dearpygui_frame()

  dpg.destroy_context()

if __name__ == '__main__':
    multiprocessing.freeze_support()
    main()

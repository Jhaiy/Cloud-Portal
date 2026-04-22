import dearpygui.dearpygui as dpg

dpg.create_context()

def create_warning_theme():
  with dpg.theme() as warning_theme:
    with dpg.theme_component(dpg.mvChildWindow):
      dpg.add_theme_color(dpg.mvThemeCol_ChildBg, (60, 40, 0, 255))
      dpg.add_theme_style(dpg.mvStyleVar_WindowPadding, 10, 10)
  
  return warning_theme

def init_header():
  global FONT_H1, FONT_H2, FONT_H3

  with dpg.font_registry():
    FONT_H1 = dpg.add_font("C:/Windows/Fonts/arial.ttf",35)
    FONT_H2 = dpg.add_font("C:/Windows/Fonts/arial.ttf",25)
    FONT_H3 = dpg.add_font("C:/Windows/Fonts/arial.ttf",15)

def add_header(text, level):
  tag = dpg.generate_uuid()
  dpg.add_text(text, tag=tag)
  dpg.bind_item_font(tag, FONT_H1 if level == 1 else FONT_H2 if level == 2 else FONT_H3)

  return tag

def button_theme():
  with dpg.theme() as theme:
    with dpg.theme_component(dpg.mvButton):
      dpg.add_theme_color(dpg.mvThemeCol_Button, (62, 207, 142, 255))
      dpg.add_theme_color(dpg.mvThemeCol_ButtonHovered, (56, 188, 129, 255))
      dpg.add_theme_color(dpg.mvThemeCol_Text, (0, 0, 0, 255))

  return theme

def caution_button():
  with dpg.theme() as theme:
    with dpg.theme_component(dpg.mvButton):
      dpg.add_theme_color(dpg.mvThemeCol_Button, (220, 80, 80, 255))
      dpg.add_theme_color(dpg.mvThemeCol_ButtonHovered, (200, 70, 70, 255))
      dpg.add_theme_color(dpg.mvThemeCol_Text, (255, 255, 255, 255))

  return theme
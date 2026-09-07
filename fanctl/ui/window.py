import sys
import json
import signal
import warnings
import gi

warnings.filterwarnings("ignore")

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gtk, Adw, GLib, Gio, Gdk

from fanctl.config import DBUS_NAME, DBUS_PATH
from fanctl.ui.views import (
    VitalsGroup,
    PresetsGroup,
    CurveConfigGroup,
    ManualSliderGroup,
    EmergencyGroup,
    SensorsExpander,
    QuoteGroup,
)

class FanControlWindow(Adw.ApplicationWindow):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        self.set_title("fan control")
        self.set_default_size(480, 720)

        # force dark mode so my retinas survive
        style_manager = Adw.StyleManager.get_default()
        style_manager.set_color_scheme(Adw.ColorScheme.PREFER_DARK)

        self.toast_overlay = Adw.ToastOverlay()
        self.set_content(self.toast_overlay)

        # connect to root dbus daemon
        self.dbus_proxy = None
        try:
            self.dbus_proxy = Gio.DBusProxy.new_for_bus_sync(
                Gio.BusType.SYSTEM,
                Gio.DBusProxyFlags.NONE,
                None,
                DBUS_NAME,
                DBUS_PATH,
                DBUS_NAME,
                None,
            )
        except Exception as e:
            # dbus socket being stubborn
            pass

        main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.toast_overlay.set_child(main_box)

        # headerbar
        header = Adw.HeaderBar()
        title_widget = Adw.WindowTitle(title="fan control", subtitle="thinkpad thermal chaos controller")
        header.set_title_widget(title_widget)

        btn_copy = Gtk.Button(icon_name="edit-copy-symbolic")
        btn_copy.set_tooltip_text("copy live vitals to clipboard")
        btn_copy.connect("clicked", self.on_copy_vitals)
        header.pack_end(btn_copy)

        main_box.append(header)

        # scrollable page
        scroll = Gtk.ScrolledWindow()
        scroll.set_vexpand(True)
        main_box.append(scroll)

        clamp = Adw.Clamp(maximum_size=460)
        clamp.set_margin_top(16)
        clamp.set_margin_bottom(20)
        clamp.set_margin_start(16)
        clamp.set_margin_end(16)
        scroll.set_child(clamp)

        page_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16)
        clamp.set_child(page_box)

        # view groups
        self.vitals_group = VitalsGroup()
        page_box.append(self.vitals_group)

        self.presets_group = PresetsGroup(on_set_level_cb=self.set_level)
        page_box.append(self.presets_group)

        self.curve_config_group = CurveConfigGroup(on_profile_changed_cb=self.set_curve_profile)
        page_box.append(self.curve_config_group)

        self.slider_group = ManualSliderGroup(on_slider_changed_cb=self.set_level)
        page_box.append(self.slider_group)

        self.emergency_group = EmergencyGroup(
            on_unstick_cb=self.trigger_unstick,
            on_toggle_watchdog_cb=self.toggle_watchdog,
        )
        page_box.append(self.emergency_group)

        self.sensors_expander = SensorsExpander()
        page_box.append(self.sensors_expander)

        self.quote_group = QuoteGroup()
        page_box.append(self.quote_group)

        self.last_status_text = "loading..."

        # timers for live updates
        GLib.timeout_add(1200, self.update_status)
        GLib.timeout_add(7000, self.rotate_quote)
        self.update_status()

    def set_level(self, level_str: str):
        if not self.dbus_proxy:
            self.toast_overlay.add_toast(Adw.Toast(title="error: dbus disconnected"))
            return

        try:
            self.dbus_proxy.SetLevel("(s)", level_str)
            self.toast_overlay.add_toast(Adw.Toast(title=f"fan mode set to: {level_str}"))
        except Exception as e:
            self.toast_overlay.add_toast(Adw.Toast(title=f"failed to set mode: {e}"))

    def set_curve_profile(self, profile: str):
        if not self.dbus_proxy:
            return

        try:
            self.dbus_proxy.SetCurveProfile("(s)", profile)
            self.toast_overlay.add_toast(Adw.Toast(title=f"curve profile: {profile}"))
        except Exception as e:
            self.toast_overlay.add_toast(Adw.Toast(title=f"failed to change curve: {e}"))

    def trigger_unstick(self):
        if not self.dbus_proxy:
            self.toast_overlay.add_toast(Adw.Toast(title="error: dbus disconnected"))
            return

        try:
            self.dbus_proxy.TriggerUnstick()
            self.toast_overlay.add_toast(Adw.Toast(title="⚡ nuking 400mhz lock! fan burst engaged."))
        except Exception as e:
            self.toast_overlay.add_toast(Adw.Toast(title=f"unstick failed: {e}"))

    def toggle_watchdog(self, enable: bool):
        if not self.dbus_proxy:
            return

        try:
            self.dbus_proxy.EnableAutoUnstick("(b)", enable)
            state_text = "enabled" if enable else "disabled"
            self.toast_overlay.add_toast(Adw.Toast(title=f"auto-unstick watchdog {state_text}"))
        except Exception as e:
            self.toast_overlay.add_toast(Adw.Toast(title=f"failed to toggle watchdog: {e}"))

    def on_copy_vitals(self, button):
        clipboard = Gdk.Display.get_default().get_clipboard()
        clipboard.set(f"thinkpad vitals: {self.last_status_text}")
        self.toast_overlay.add_toast(Adw.Toast(title="copied vitals to clipboard!"))

    def rotate_quote(self):
        self.quote_group.rotate()
        return True

    def update_status(self):
        if not self.dbus_proxy:
            try:
                self.dbus_proxy = Gio.DBusProxy.new_for_bus_sync(
                    Gio.BusType.SYSTEM,
                    Gio.DBusProxyFlags.NONE,
                    None,
                    DBUS_NAME,
                    DBUS_PATH,
                    DBUS_NAME,
                    None,
                )
            except Exception:
                pass

        try:
            res = self.dbus_proxy.GetStatus() if self.dbus_proxy else None
            if res:
                json_str = res[0] if isinstance(res, (tuple, list)) else res
                data = json.loads(json_str)

                temp = data.get("temp", 0.0)
                rpm = data.get("speed_rpm", 0)
                cpu = data.get("cpu_mhz", 0)
                mode = data.get("mode", "unknown")
                level = data.get("level", "unknown")
                curve_prof = data.get("curve_profile", "balanced")
                auto_unstick = data.get("auto_unstick", True)

                self.last_status_text = f"{temp:.1f}°c | {rpm} rpm | {cpu} mhz | mode: {mode} (lvl {level})"

                self.vitals_group.update(data)
                self.curve_config_group.sync_profile(curve_prof)
                self.slider_group.sync_value(level)
                self.emergency_group.sync_watchdog(auto_unstick)
                self.sensors_expander.update(data)

        except Exception as e:
            # daemon offline or restarting
            self.vitals_group.temp_row.set_subtitle("daemon inactive")
            self.vitals_group.rpm_row.set_subtitle("check fan-control.service")
            self.vitals_group.cpu_row.set_subtitle("dbus disconnected")

        return True


class FanControlApp(Adw.Application):
    def __init__(self):
        super().__init__(
            application_id="io.github.fancontrol",
            flags=Gio.ApplicationFlags.FLAGS_NONE,
        )

    def do_activate(self):
        win = self.props.active_window
        if not win:
            win = FanControlWindow(application=self)
        win.present()


def main():
    signal.signal(signal.SIGINT, signal.SIG_DFL)
    app = FanControlApp()
    app.run(sys.argv)


if __name__ == "__main__":
    main()

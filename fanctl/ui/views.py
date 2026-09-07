import random
import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gtk, Adw, Gdk

from fanctl.config import CHAOTIC_QUOTES, CURVE_PROFILES

class VitalsGroup(Adw.PreferencesGroup):
    def __init__(self):
        super().__init__(title="live vitals")

        self.temp_row = Adw.ActionRow(title="cpu temperature", subtitle="loading...")
        self.temp_bar = Gtk.ProgressBar(fraction=0.4, hexpand=True, valign=Gtk.Align.CENTER)
        self.temp_row.add_suffix(self.temp_bar)
        self.add(self.temp_row)

        self.rpm_row = Adw.ActionRow(title="fan speed (rpm)", subtitle="loading...")
        self.rpm_bar = Gtk.ProgressBar(fraction=0.0, hexpand=True, valign=Gtk.Align.CENTER)
        self.rpm_row.add_suffix(self.rpm_bar)
        self.add(self.rpm_row)

        self.cpu_row = Adw.ActionRow(title="cpu clock", subtitle="loading...")
        self.add(self.cpu_row)

    def update(self, data: dict):
        temp = data.get("temp", 0.0)
        rpm = data.get("speed_rpm", 0)
        cpu_avg = data.get("cpu_mhz", 0)
        cpu_max = data.get("cpu_max_mhz", 0)
        mode = data.get("mode", "unknown")
        level = data.get("level", "unknown")
        is_locked = data.get("is_locked", False)
        is_shocking = data.get("is_shocking", False)

        # so i dont get blinded or die by it
        self.temp_row.set_subtitle(f"{temp:.1f}°c (package/max: {data.get('max_temp', temp):.1f}°c)")
        fraction = min(1.0, max(0.0, temp / 100.0))
        self.temp_bar.set_fraction(fraction)

        # dynamic thermal bar coloring
        self.temp_bar.remove_css_class("accent")
        self.temp_bar.remove_css_class("warning")
        self.temp_bar.remove_css_class("error")
        if temp < 58.0:
            self.temp_bar.add_css_class("accent")
        elif temp < 75.0:
            self.temp_bar.add_css_class("warning")
        else:
            self.temp_bar.add_css_class("error")

        if is_shocking:
            self.rpm_row.set_subtitle(f"⚡ {rpm} rpm (unstick shock burst engaged!)")
        else:
            self.rpm_row.set_subtitle(f"{rpm} rpm  (mode: {mode} | level: {level})")
        self.rpm_bar.set_fraction(min(1.0, max(0.0, rpm / 5200.0)))

        if is_locked:
            self.cpu_row.set_subtitle(f"⚠️ {cpu_avg} mhz (stuck in 400mhz hell! hit 'nuke lock')")
        else:
            self.cpu_row.set_subtitle(f"{cpu_avg} mhz avg  (peak: {cpu_max} mhz)")


class PresetsGroup(Adw.PreferencesGroup):
    def __init__(self, on_set_level_cb):
        super().__init__(title="preset profiles")
        self.on_set_level = on_set_level_cb

        # row 1: standard modes
        row1 = Adw.ActionRow(title="standard profiles", subtitle="quick thermal modes")
        self.add(row1)

        box1 = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        box1.set_valign(Gtk.Align.CENTER)

        self.btn_auto = Gtk.Button(label="auto")
        self.btn_auto.set_tooltip_text("default bios controller")
        self.btn_auto.connect("clicked", lambda b: self.on_set_level("auto"))
        box1.append(self.btn_auto)

        self.btn_quiet = Gtk.Button(label="quiet")
        self.btn_quiet.set_tooltip_text("level 2 - low noise")
        self.btn_quiet.connect("clicked", lambda b: self.on_set_level("2"))
        box1.append(self.btn_quiet)

        self.btn_bal = Gtk.Button(label="balanced")
        self.btn_bal.set_tooltip_text("level 4 - medium airflow")
        self.btn_bal.connect("clicked", lambda b: self.on_set_level("4"))
        box1.append(self.btn_bal)

        row1.add_suffix(box1)

        # row 2: power + curve modes
        row2 = Adw.ActionRow(title="power + curve profiles", subtitle="automated curve + max airflow")
        self.add(row2)

        box2 = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        box2.set_valign(Gtk.Align.CENTER)

        self.btn_perf = Gtk.Button(label="perf")
        self.btn_perf.set_tooltip_text("level 7 - max safe speed")
        self.btn_perf.connect("clicked", lambda b: self.on_set_level("7"))
        box2.append(self.btn_perf)

        self.btn_curve = Gtk.Button(label="smart curve")
        self.btn_curve.set_tooltip_text("dynamic fan curve managed by daemon")
        self.btn_curve.connect("clicked", lambda b: self.on_set_level("curve"))
        box2.append(self.btn_curve)

        self.btn_full = Gtk.Button(label="full-speed")
        self.btn_full.add_css_class("destructive-action")
        self.btn_full.set_tooltip_text("jet engine mode - disengages ec limits")
        self.btn_full.connect("clicked", lambda b: self.on_set_level("full-speed"))
        box2.append(self.btn_full)

        row2.add_suffix(box2)


class CurveConfigGroup(Adw.PreferencesGroup):
    def __init__(self, on_profile_changed_cb):
        super().__init__(title="smart curve configuration")
        self.on_profile_changed = on_profile_changed_cb
        self.profiles = ["balanced", "quiet", "aggressive"]

        self.combo_row = Adw.ComboRow(
            title="curve preset",
            subtitle="thermal hysteresis and threshold profile"
        )
        model = Gtk.StringList.new(self.profiles)
        self.combo_row.set_model(model)
        self.combo_signal = self.combo_row.connect("notify::selected", self._on_selected)
        self.add(self.combo_row)

    def _on_selected(self, widget, param):
        idx = self.combo_row.get_selected()
        if 0 <= idx < len(self.profiles):
            self.on_profile_changed(self.profiles[idx])

    def sync_profile(self, profile: str):
        if profile in self.profiles:
            idx = self.profiles.index(profile)
            if self.combo_row.get_selected() != idx:
                self.combo_row.handler_block(self.combo_signal)
                self.combo_row.set_selected(idx)
                self.combo_row.handler_unblock(self.combo_signal)


class ManualSliderGroup(Adw.PreferencesGroup):
    def __init__(self, on_slider_changed_cb):
        super().__init__(title="manual slider")
        self.on_slider_changed = on_slider_changed_cb

        slider_row = Adw.ActionRow(title="level (0 - 7)", subtitle="direct ec register override")
        self.add(slider_row)

        self.scale = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, 0, 7, 1)
        self.scale.set_draw_value(True)
        self.scale.set_value_pos(Gtk.PositionType.RIGHT)
        self.scale.set_hexpand(True)
        self.scale.set_size_request(140, -1)
        self.scale.set_valign(Gtk.Align.CENTER)

        for i in range(8):
            self.scale.add_mark(i, Gtk.PositionType.BOTTOM, str(i))

        self.scale_signal_id = self.scale.connect("value-changed", self._on_val_changed)
        slider_row.add_suffix(self.scale)

    def _on_val_changed(self, scale):
        val = str(int(scale.get_value()))
        self.on_slider_changed(val)

    def sync_value(self, level: str):
        if level.isdigit():
            val = int(level)
            if int(self.scale.get_value()) != val:
                self.scale.handler_block(self.scale_signal_id)
                self.scale.set_value(val)
                self.scale.handler_unblock(self.scale_signal_id)


class EmergencyGroup(Adw.PreferencesGroup):
    def __init__(self, on_unstick_cb, on_toggle_watchdog_cb):
        super().__init__(title="emergency + ec recovery")
        self.on_unstick = on_unstick_cb
        self.on_toggle_watchdog = on_toggle_watchdog_cb

        # auto-unstick switch row
        self.switch_watchdog = Adw.SwitchRow(
            title="auto 400mhz watchdog",
            subtitle="automatically shocks ec firmware if cpu clock locks at 400mhz"
        )
        self.switch_signal = self.switch_watchdog.connect("notify::active", self._on_switch)
        self.add(self.switch_watchdog)

        # manual nuke lock row
        unstick_row = Adw.ActionRow(
            title="manual nuke lock",
            subtitle="bursts fans to maximum to reset ec power limits"
        )
        self.add(unstick_row)

        self.btn_unstick = Gtk.Button(label="nuke lock")
        self.btn_unstick.add_css_class("suggested-action")
        self.btn_unstick.set_tooltip_text("bursts fans to max to reset power limits")
        self.btn_unstick.connect("clicked", lambda b: self.on_unstick())
        unstick_row.add_suffix(self.btn_unstick)

    def _on_switch(self, widget, param):
        self.on_toggle_watchdog(self.switch_watchdog.get_active())

    def sync_watchdog(self, active: bool):
        if self.switch_watchdog.get_active() != active:
            self.switch_watchdog.handler_block(self.switch_signal)
            self.switch_watchdog.set_active(active)
            self.switch_watchdog.handler_unblock(self.switch_signal)


class SensorsExpander(Adw.PreferencesGroup):
    def __init__(self):
        super().__init__(title="detailed telemetry")

        self.expander = Adw.ExpanderRow(
            title="hardware thermal sensors",
            subtitle="individual core and drive readings"
        )
        self.add(self.expander)
        self.rows_cache = {}

    def update(self, data: dict):
        sensors_to_show = []

        if data.get("package_temp"):
            sensors_to_show.append(("cpu package", f"{data['package_temp']}°c"))
        if data.get("gpu_temp"):
            sensors_to_show.append(("thinkpad gpu", f"{data['gpu_temp']}°c"))

        for nvme in data.get("nvme_temps", []):
            sensors_to_show.append((f"nvme ({nvme['label']})", f"{nvme['temp']}°c"))

        for core in data.get("core_temps", [])[:8]:
            sensors_to_show.append((f"{core['label'].lower()}", f"{core['temp']}°c"))

        for label, val_str in sensors_to_show:
            if label not in self.rows_cache:
                row = Adw.ActionRow(title=label, subtitle=val_str)
                self.expander.add_row(row)
                self.rows_cache[label] = row
            else:
                self.rows_cache[label].set_subtitle(val_str)


class QuoteGroup(Adw.PreferencesGroup):
    def __init__(self):
        super().__init__(title="thinkpad wisdom")
        self.quote_row = Adw.ActionRow(
            title="quote of the second",
            subtitle=random.choice(CHAOTIC_QUOTES)
        )
        self.add(self.quote_row)

    def rotate(self):
        self.quote_row.set_subtitle(random.choice(CHAOTIC_QUOTES))

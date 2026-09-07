import os
import sys
import json
import time
import signal
import threading
import warnings
from gi.repository import GLib, Gio

warnings.filterwarnings("ignore")

from fanctl.config import DBUS_NAME, DBUS_PATH, DBUS_XML
from fanctl.hardware import HardwareController
from fanctl.curve import CurveController
from fanctl.watchdog import UnstickEngine

class FanDaemon:
    def __init__(self):
        self.hardware = HardwareController()
        self.curve = CurveController()
        self.unstick = UnstickEngine(self.hardware)
        
        self.mode = "auto"
        self.auto_unstick = True
        self.running = True
        self.cached_status = {
            "temp": 45.0,
            "max_temp": 45.0,
            "package_temp": 45.0,
            "core_temps": [],
            "nvme_temps": [],
            "gpu_temp": None,
            "speed_rpm": 0,
            "level": "auto",
            "mode": "auto",
            "curve_profile": "balanced",
            "cpu_mhz": 0,
            "cpu_min_mhz": 0,
            "cpu_max_mhz": 0,
            "is_locked": False,
            "auto_unstick": True,
            "is_shocking": False,
        }

        if not self.hardware.check_fan_support():
            print("[FATAL] /proc/acpi/ibm/fan missing! check thinkpad_acpi fan_control=1")
            sys.exit(1)

        # daemon loop running in background
        self.worker_thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self.worker_thread.start()

    def _restore_mode(self):
        # bring fan back to whatever mode user picked before shock
        if self.mode == "curve":
            target = self.curve.calculate_target_level(self.cached_status.get("temp", 50.0))
            self.hardware.write_fan_level(target)
        else:
            self.hardware.write_fan_level(self.mode)

    def _monitor_loop(self):
        while self.running:
            try:
                sensors = self.hardware.read_sensors()
                cpu_freq = self.hardware.read_cpu_frequencies()
                fan_info = self.hardware.read_fan_status()

                cpu_temp = sensors.get("cpu_temp", 45.0)

                if not self.unstick.is_shocking:
                    if self.mode == "curve":
                        target_level = self.curve.calculate_target_level(cpu_temp)
                        if fan_info.get("level") != target_level:
                            self.hardware.write_fan_level(target_level)

                    if self.auto_unstick:
                        self.unstick.evaluate(cpu_freq, restore_callback=self._restore_mode)

                self.cached_status = {
                    "temp": cpu_temp,
                    "max_temp": sensors.get("max_temp", cpu_temp),
                    "package_temp": sensors.get("package_temp", cpu_temp),
                    "core_temps": sensors.get("core_temps", []),
                    "nvme_temps": sensors.get("nvme_temps", []),
                    "gpu_temp": sensors.get("gpu_temp"),
                    "speed_rpm": fan_info.get("speed_rpm", 0),
                    "level": fan_info.get("level", "unknown"),
                    "mode": self.mode,
                    "curve_profile": self.curve.get_profile(),
                    "cpu_mhz": cpu_freq.get("avg_mhz", 0),
                    "cpu_min_mhz": cpu_freq.get("min_mhz", 0),
                    "cpu_max_mhz": cpu_freq.get("max_mhz", 0),
                    "is_locked": cpu_freq.get("is_locked", False),
                    "auto_unstick": self.auto_unstick,
                    "is_shocking": self.unstick.is_shocking,
                }
            except Exception as e:
                # ignoring random sysfs read blips
                pass

            time.sleep(1.0)

    def set_level(self, level: str) -> bool:
        if level == "curve":
            self.mode = "curve"
            target = self.curve.calculate_target_level(self.cached_status.get("temp", 50.0))
            self.hardware.write_fan_level(target)
            return True

        res = self.hardware.write_fan_level(level)
        if res:
            self.mode = level
        return res

    def get_status_json(self) -> str:
        return json.dumps(self.cached_status)

    def enable_auto_unstick(self, enable: bool) -> bool:
        self.auto_unstick = enable
        return True

    def trigger_unstick(self) -> bool:
        return self.unstick.trigger_unstick(restore_callback=self._restore_mode)

    def set_curve_profile(self, profile: str) -> bool:
        res = self.curve.set_profile(profile)
        if res and self.mode == "curve":
            target = self.curve.calculate_target_level(self.cached_status.get("temp", 50.0))
            self.hardware.write_fan_level(target)
        return res

    def get_curve_profile(self) -> str:
        return self.curve.get_profile()

    def handle_method_call(self, conn, sender, object_path, interface_name, method_name, parameters, invocation):
        args = parameters.unpack()

        if method_name == "SetLevel":
            level = args[0]
            res = self.set_level(level)
            invocation.return_value(GLib.Variant("(b)", (res,)))

        elif method_name == "GetStatus":
            status_json = self.get_status_json()
            invocation.return_value(GLib.Variant("(s)", (status_json,)))

        elif method_name == "EnableAutoUnstick":
            val = bool(args[0])
            res = self.enable_auto_unstick(val)
            invocation.return_value(GLib.Variant("(b)", (res,)))

        elif method_name == "TriggerUnstick":
            res = self.trigger_unstick()
            invocation.return_value(GLib.Variant("(b)", (res,)))

        elif method_name == "SetCurveProfile":
            profile = str(args[0])
            res = self.set_curve_profile(profile)
            invocation.return_value(GLib.Variant("(b)", (res,)))

        elif method_name == "GetCurveProfile":
            prof = self.get_curve_profile()
            invocation.return_value(GLib.Variant("(s)", (prof,)))

def on_bus_acquired(conn, name, daemon):
    node_info = Gio.DBusNodeInfo.new_for_xml(DBUS_XML)
    conn.register_object(
        DBUS_PATH,
        node_info.interfaces[0],
        daemon.handle_method_call,
        None,
        None,
    )
    print(f"[READY] registered {name} on system dbus. fan curves and ec watchdog active.")

def main():
    daemon = FanDaemon()

    def _sig_handler(sig, frame):
        # resetting fan to auto before dying
        daemon.running = False
        daemon.hardware.write_fan_level("auto")
        sys.exit(0)

    signal.signal(signal.SIGINT, _sig_handler)
    signal.signal(signal.SIGTERM, _sig_handler)

    Gio.bus_own_name(
        Gio.BusType.SYSTEM,
        DBUS_NAME,
        Gio.BusNameOwnerFlags.NONE,
        lambda conn, name: on_bus_acquired(conn, name, daemon),
        None,
        lambda conn, name: print("[FATAL] lost dbus name") or sys.exit(1),
    )

    loop = GLib.MainLoop()
    try:
        loop.run()
    except (KeyboardInterrupt, SystemExit):
        _sig_handler(None, None)

if __name__ == "__main__":
    main()

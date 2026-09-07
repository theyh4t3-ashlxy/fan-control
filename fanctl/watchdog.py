import time
import threading
from fanctl.hardware import HardwareController

class UnstickEngine:
    def __init__(self, hardware: HardwareController):
        self.hardware = hardware
        self.is_shocking = False
        self.last_shock_time = 0.0
        self.shock_cooldown = 30.0

    def trigger_unstick(self, restore_callback=None) -> bool:
        if self.is_shocking:
            return False

        def _shock_worker():
            self.is_shocking = True
            try:
                # blast ec with full power to break bd prochot lock
                self.hardware.write_fan_level("full-speed")
                time.sleep(2.0)
                self.hardware.write_fan_level("7")
                time.sleep(1.0)
            finally:
                self.last_shock_time = time.time()
                self.is_shocking = False
                if restore_callback:
                    restore_callback()

        t = threading.Thread(target=_shock_worker, daemon=True)
        t.start()
        return True

    def evaluate(self, cpu_stats: dict, restore_callback=None) -> bool:
        # waking up the cpu from its 400mhz coma
        if self.is_shocking:
            return False

        now = time.time()
        if (now - self.last_shock_time) < self.shock_cooldown:
            return False

        if cpu_stats.get("is_locked", False):
            return self.trigger_unstick(restore_callback)

        return False

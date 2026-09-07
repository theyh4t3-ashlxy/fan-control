import os
import glob
import threading
from fanctl.config import PROC_FAN

class HardwareController:
    def __init__(self):
        # if this lock dies the whole kernel is next
        self.lock = threading.Lock()

    def check_fan_support(self) -> bool:
        return os.path.exists(PROC_FAN)

    def read_fan_status(self) -> dict:
        info = {"status": "unknown", "speed_rpm": 0, "level": "unknown"}
        if not os.path.exists(PROC_FAN):
            return info

        try:
            with open(PROC_FAN, "r") as f:
                for line in f:
                    parts = line.strip().split(":")
                    if len(parts) == 2:
                        k, v = parts[0].strip(), parts[1].strip()
                        if k == "status":
                            info["status"] = v
                        elif k == "speed":
                            try:
                                info["speed_rpm"] = int(v.split()[0])
                            except (ValueError, IndexError):
                                info["speed_rpm"] = 0
                        elif k == "level":
                            info["level"] = v
        except Exception as e:
            # ibm acpi being finicky as usual
            pass
        return info

    def write_fan_level(self, level: str) -> bool:
        valid = [str(i) for i in range(8)] + ["auto", "full-speed", "disengaged"]
        if level not in valid:
            return False

        with self.lock:
            try:
                with open(PROC_FAN, "w") as f:
                    f.write(f"level {level}\n")
                return True
            except Exception as e:
                # permissions or acpi refusing to cooperate
                return False

    def read_sensors(self) -> dict:
        cpu_temps = []
        package_temp = None
        core_temps = []
        nvme_temps = []
        gpu_temp = None

        for hwmon_dir in glob.glob("/sys/class/hwmon/hwmon*"):
            name_file = os.path.join(hwmon_dir, "name")
            name = ""
            if os.path.exists(name_file):
                try:
                    with open(name_file, "r") as f:
                        name = f.read().strip()
                except Exception:
                    pass

            for temp_input in glob.glob(os.path.join(hwmon_dir, "temp*_input")):
                try:
                    with open(temp_input, "r") as f:
                        t = float(f.read().strip()) / 1000.0
                    if not (0 < t < 120):
                        continue

                    label_file = temp_input.replace("_input", "_label")
                    label = ""
                    if os.path.exists(label_file):
                        with open(label_file, "r") as f:
                            label = f.read().strip()

                    if name == "coretemp":
                        cpu_temps.append(t)
                        if "Package" in label:
                            package_temp = t
                        elif "Core" in label:
                            core_temps.append({"label": label, "temp": round(t, 1)})
                    elif name == "thinkpad":
                        if label == "CPU":
                            cpu_temps.append(t)
                        elif label == "GPU":
                            gpu_temp = round(t, 1)
                    elif name == "nvme":
                        nvme_label = label if label else "NVMe"
                        nvme_temps.append({"label": nvme_label, "temp": round(t, 1)})
                    elif "acpitz" in name or "k10temp" in name:
                        cpu_temps.append(t)
                except Exception:
                    pass

        # thermal fallback so we dont melt
        primary_temp = package_temp if package_temp else (max(cpu_temps) if cpu_temps else 45.0)

        return {
            "cpu_temp": round(primary_temp, 1),
            "package_temp": round(package_temp, 1) if package_temp else None,
            "core_temps": sorted(core_temps, key=lambda x: x["label"]),
            "nvme_temps": nvme_temps,
            "gpu_temp": gpu_temp,
            "max_temp": round(max(cpu_temps), 1) if cpu_temps else round(primary_temp, 1),
        }

    def read_cpu_frequencies(self) -> dict:
        freqs = []
        for path in glob.glob("/sys/devices/system/cpu/cpu*/cpufreq/scaling_cur_freq"):
            try:
                with open(path, "r") as f:
                    freqs.append(int(f.read().strip()) // 1000)
            except Exception:
                pass

        if not freqs:
            return {"avg_mhz": 0, "min_mhz": 0, "max_mhz": 0, "is_locked": False}

        avg_mhz = sum(freqs) // len(freqs)
        min_mhz = min(freqs)
        max_mhz = max(freqs)
        is_locked = max_mhz <= 450

        return {
            "avg_mhz": avg_mhz,
            "min_mhz": min_mhz,
            "max_mhz": max_mhz,
            "is_locked": is_locked,
        }

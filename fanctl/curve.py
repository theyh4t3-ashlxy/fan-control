from fanctl.config import CURVE_PROFILES, HYSTERESIS_TEMP, HYSTERESIS_TICKS

class CurveController:
    def __init__(self, default_profile: str = "balanced"):
        self.profile = default_profile if default_profile in CURVE_PROFILES else "balanced"
        self.current_level = "0"
        self.ticks_below = 0

    def set_profile(self, profile: str) -> bool:
        if profile in CURVE_PROFILES:
            self.profile = profile
            self.ticks_below = 0
            return True
        return False

    def get_profile(self) -> str:
        return self.profile

    def get_available_profiles(self) -> list:
        return list(CURVE_PROFILES.keys())

    def _level_numeric_rank(self, level: str) -> int:
        if level == "auto":
            return -1
        if level.isdigit():
            return int(level)
        if level in ["full-speed", "disengaged"]:
            return 8
        return 0

    def _get_threshold_for_level(self, level: str) -> float:
        points = CURVE_PROFILES[self.profile]
        for threshold, lvl in points:
            if lvl == level:
                return float(threshold)
        return float(points[0][0])

    def calculate_target_level(self, temp: float) -> str:
        points = CURVE_PROFILES[self.profile]
        # find target based purely on temp
        raw_target = points[0][1]
        for threshold, level in points:
            if temp >= threshold:
                raw_target = level

        current_rank = self._level_numeric_rank(self.current_level)
        target_rank = self._level_numeric_rank(raw_target)

        # instant spinup when the cpu starts sweating
        if target_rank > current_rank:
            self.current_level = raw_target
            self.ticks_below = 0
            return self.current_level

        # smooth stepped cooldown with hysteresis
        if target_rank < current_rank:
            current_threshold = self._get_threshold_for_level(self.current_level)
            if temp < (current_threshold - HYSTERESIS_TEMP):
                self.ticks_below += 1
                if self.ticks_below >= HYSTERESIS_TICKS:
                    self.current_level = raw_target
                    self.ticks_below = 0
            else:
                self.ticks_below = 0

        return self.current_level

import os

DBUS_NAME = "org.thinkpad.FanControl"
DBUS_PATH = "/org/thinkpad/FanControl"
PROC_FAN = "/proc/acpi/ibm/fan"

DBUS_XML = """
<node>
  <interface name="org.thinkpad.FanControl">
    <method name="SetLevel">
      <arg type="s" name="level" direction="in"/>
      <arg type="b" name="success" direction="out"/>
    </method>
    <method name="GetStatus">
      <arg type="s" name="json_data" direction="out"/>
    </method>
    <method name="EnableAutoUnstick">
      <arg type="b" name="enable" direction="in"/>
      <arg type="b" name="success" direction="out"/>
    </method>
    <method name="TriggerUnstick">
      <arg type="b" name="success" direction="out"/>
    </method>
    <method name="SetCurveProfile">
      <arg type="s" name="profile" direction="in"/>
      <arg type="b" name="success" direction="out"/>
    </method>
    <method name="GetCurveProfile">
      <arg type="s" name="profile" direction="out"/>
    </method>
  </interface>
</node>
"""

# curves mapped (temp_c, fan_level)
# if the chassis melts that is a skill issue
CURVE_PROFILES = {
    "quiet": [
        (45, "0"),
        (55, "1"),
        (65, "2"),
        (72, "3"),
        (80, "5"),
        (88, "7"),
        (94, "full-speed"),
    ],
    "balanced": [
        (40, "0"),
        (50, "1"),
        (60, "2"),
        (68, "4"),
        (75, "6"),
        (82, "7"),
        (90, "full-speed"),
    ],
    "aggressive": [
        (35, "1"),
        (45, "3"),
        (55, "5"),
        (65, "7"),
        (78, "full-speed"),
    ],
}

HYSTERESIS_TEMP = 3.5
HYSTERESIS_TICKS = 3

CHAOTIC_QUOTES = [
    "intel 12th gen: turning electricity into heat and noise since 2022",
    "400mhz lock is not a bug, it's a lifestyle choice",
    "fan spinning at 4500 rpm: cleared for take-off on runway 2",
    "if your lap gets warm, consider it free winter heating",
    "thinkpad acpi: maintaining sanity one register at a time",
    "bd prochot triggered? hit nuke lock and pray to the ec gods",
    "uppercase letters are aggressive and stress out the CPU",
    "thermal paste curing in real time... please do not panic",
    "cooling fans provided by Boeing aerospace engineers",
    "silicon lottery ticket: scratched with a rusty screwdriver",
    "the embedded controller is having an existential crisis",
]

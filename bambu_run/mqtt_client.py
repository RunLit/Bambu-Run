"""
BambuLab Cloud API Client
Provides authentication, device management, and real-time MQTT monitoring
for BambuLab 3D printers via the Cloud API.

Requires: pip install bambu-lab-cloud-api

Usage:
    from bambu_run.mqtt_client import BambuPrinter, PrinterState

    printer = BambuPrinter(token="your_token", device_id="your_device_id")
    printer.connect()
    state = printer.get_state()
    snapshot = printer.get_snapshot()
    printer.disconnect()
"""

import io
import logging
import os
import platform
import sys
import select
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional
from zoneinfo import ZoneInfo

from .conf import app_settings

# Re-export from bambu-lab-cloud-api package
try:
    from bambulab import BambuAuthenticator, BambuClient, MQTTClient
except ImportError as e:
    raise ImportError(
        "bambu-lab-cloud-api package is required. Install with: pip install bambu-lab-cloud-api"
    ) from e


logger = logging.getLogger(__name__)


@contextmanager
def suppress_stdout():
    """Context manager to suppress stdout (for silencing library print statements)"""
    old_stdout = sys.stdout
    sys.stdout = io.StringIO()
    try:
        yield
    finally:
        sys.stdout = old_stdout


def timed_input(prompt: str, timeout_sec: int = 300) -> str:
    """
    Get user input with a timeout.

    Args:
        prompt: The prompt to display
        timeout_sec: Timeout in seconds (default 300 = 5 minutes)

    Returns:
        User input string

    Raises:
        TimeoutError: If no input received within timeout
    """
    print(prompt, end='', flush=True)

    if platform.system() == 'Windows':
        import threading
        result = {'value': None, 'done': False}

        def get_input():
            try:
                result['value'] = input()
            except EOFError:
                result['value'] = None
            result['done'] = True

        thread = threading.Thread(target=get_input, daemon=True)
        thread.start()
        thread.join(timeout=timeout_sec)

        if not result['done']:
            print()
            raise TimeoutError(f"No input received within {timeout_sec} seconds")
        return result['value'] or ""
    else:
        ready, _, _ = select.select([sys.stdin], [], [], timeout_sec)
        if ready:
            return sys.stdin.readline().strip()
        else:
            print()
            raise TimeoutError(f"No input received within {timeout_sec} seconds")


@dataclass
class FilamentTray:
    """Represents a single filament tray in an AMS unit"""
    tray_id: str = ""
    tray_id_name: str = ""
    tray_type: str = ""
    tray_sub_brands: str = ""
    tray_color: str = ""
    remain_percent: int = -1
    tray_weight: int = 0
    tray_diameter: float = 1.75
    tray_temp: int = 0
    nozzle_temp_min: int = 0
    nozzle_temp_max: int = 0
    state: int = 0
    tag_uid: str = ""
    tray_uuid: str = ""
    k: float = 0.0
    n: float = 0.0
    cali_idx: int = -1
    total_len: int = 0
    tray_info_idx: str = ""
    tray_time: int = 0
    tray_bed_temp: int = 0
    bed_temp_type: int = 0
    cols: List[str] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "FilamentTray":
        """Create FilamentTray from MQTT tray data"""
        return cls(
            tray_id=str(data.get("id", "")),
            tray_id_name=data.get("tray_id_name", ""),
            tray_type=data.get("tray_type", ""),
            tray_sub_brands=data.get("tray_sub_brands", ""),
            tray_color=data.get("tray_color", ""),
            remain_percent=data.get("remain", -1),
            tray_weight=int(data.get("tray_weight", 0)),
            tray_diameter=float(data.get("tray_diameter", 1.75)),
            tray_temp=int(data.get("tray_temp", 0)),
            nozzle_temp_min=int(data.get("nozzle_temp_min", 0)),
            nozzle_temp_max=int(data.get("nozzle_temp_max", 0)),
            state=data.get("state", 0),
            tag_uid=data.get("tag_uid", ""),
            tray_uuid=data.get("tray_uuid", ""),
            k=float(data.get("k", 0.0)),
            n=float(data.get("n", 0.0)),
            cali_idx=int(data.get("cali_idx", -1)),
            total_len=int(data.get("total_len", 0)),
            tray_info_idx=data.get("tray_info_idx", ""),
            tray_time=int(data.get("tray_time", 0)),
            tray_bed_temp=int(data.get("bed_temp", 0)),
            bed_temp_type=int(data.get("bed_temp_type", 0)),
            cols=data.get("cols", []),
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for database storage"""
        return {
            "tray_id": self.tray_id,
            "tray_id_name": self.tray_id_name,
            "tray_type": self.tray_type,
            "tray_sub_brands": self.tray_sub_brands,
            "tray_color": self.tray_color,
            "remain_percent": self.remain_percent,
            "tray_weight": self.tray_weight,
            "tray_diameter": self.tray_diameter,
            "tray_temp": self.tray_temp,
            "nozzle_temp_min": self.nozzle_temp_min,
            "nozzle_temp_max": self.nozzle_temp_max,
            "state": self.state,
            "tag_uid": self.tag_uid,
            "tray_uuid": self.tray_uuid,
            "k": self.k,
            "n": self.n,
            "cali_idx": self.cali_idx,
            "total_len": self.total_len,
            "tray_info_idx": self.tray_info_idx,
            "tray_time": self.tray_time,
            "tray_bed_temp": self.tray_bed_temp,
            "bed_temp_type": self.bed_temp_type,
            "cols": self.cols,
        }


@dataclass
class AMSUnit:
    """Represents a single AMS (Automatic Material System) unit"""
    ams_id: str = ""
    unit_id: str = ""
    humidity: int = -1
    humidity_raw: int = -1
    temp: float = 0.0
    dry_time: int = 0
    chip_id: str = ""
    info: str = ""
    trays: List[FilamentTray] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AMSUnit":
        """Create AMSUnit from MQTT ams data"""
        trays = [FilamentTray.from_dict(t) for t in data.get("tray", [])]
        return cls(
            ams_id=data.get("ams_id", ""),
            unit_id=str(data.get("id", "")),
            humidity=int(data.get("humidity", -1)),
            humidity_raw=int(data.get("humidity_raw", -1)),
            temp=float(data.get("temp", 0.0)),
            dry_time=data.get("dry_time", 0),
            chip_id=data.get("chip_id", ""),
            info=data.get("info", ""),
            trays=trays,
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for database storage"""
        return {
            "ams_id": self.ams_id,
            "unit_id": self.unit_id,
            "humidity": self.humidity,
            "humidity_raw": self.humidity_raw,
            "temp": self.temp,
            "dry_time": self.dry_time,
            "chip_id": self.chip_id,
            "info": self.info,
            "trays": [t.to_dict() for t in self.trays],
        }


@dataclass
class AMSState:
    """Complete AMS system state including all units"""
    ams_exist_bits: str = ""
    tray_exist_bits: str = ""
    tray_now: str = ""
    tray_pre: str = ""
    tray_tar: str = ""
    ams_status: int = 0
    ams_rfid_status: int = 0
    tray_is_bbl_bits: str = ""
    tray_read_done_bits: str = ""
    version: int = 0
    insert_flag: bool = False
    power_on_flag: bool = False
    units: List[AMSUnit] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AMSState":
        """Create AMSState from MQTT ams data"""
        units = [AMSUnit.from_dict(u) for u in data.get("ams", [])]
        return cls(
            ams_exist_bits=data.get("ams_exist_bits", ""),
            tray_exist_bits=data.get("tray_exist_bits", ""),
            tray_now=data.get("tray_now", ""),
            tray_pre=data.get("tray_pre", ""),
            tray_tar=data.get("tray_tar", ""),
            ams_status=data.get("ams_status", 0),
            ams_rfid_status=data.get("ams_rfid_status", 0),
            tray_is_bbl_bits=data.get("tray_is_bbl_bits", ""),
            tray_read_done_bits=data.get("tray_read_done_bits", ""),
            version=int(data.get("version", 0)),
            insert_flag=bool(data.get("insert_flag", False)),
            power_on_flag=bool(data.get("power_on_flag", False)),
            units=units,
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for database storage"""
        return {
            "ams_exist_bits": self.ams_exist_bits,
            "tray_exist_bits": self.tray_exist_bits,
            "tray_now": self.tray_now,
            "tray_pre": self.tray_pre,
            "tray_tar": self.tray_tar,
            "ams_status": self.ams_status,
            "ams_rfid_status": self.ams_rfid_status,
            "tray_is_bbl_bits": self.tray_is_bbl_bits,
            "tray_read_done_bits": self.tray_read_done_bits,
            "version": self.version,
            "insert_flag": self.insert_flag,
            "power_on_flag": self.power_on_flag,
            "units": [u.to_dict() for u in self.units],
        }

    @property
    def total_trays(self) -> int:
        """Total number of trays across all units"""
        return sum(len(u.trays) for u in self.units)

    @property
    def loaded_trays(self) -> List[FilamentTray]:
        """Get all trays that have filament loaded"""
        loaded = []
        for unit in self.units:
            for tray in unit.trays:
                if tray.tray_type:
                    loaded.append(tray)
        return loaded


@dataclass
class PrinterState:
    """Complete printer state parsed from MQTT data"""
    timestamp: str = ""
    sequence_id: str = ""

    # Temperature info
    nozzle_temp: float = 0.0
    nozzle_target_temp: float = 0.0
    bed_temp: float = 0.0
    bed_target_temp: float = 0.0
    chamber_temp: float = 0.0

    # Print progress
    gcode_state: str = ""
    print_percent: int = 0
    remaining_time_min: int = 0
    layer_num: int = 0
    total_layer_num: int = 0
    print_line_number: int = 0

    # Current job info
    gcode_file: str = ""
    subtask_name: str = ""
    subtask_id: str = ""
    task_id: str = ""
    project_id: str = ""
    profile_id: str = ""
    print_type: str = ""

    # Fan speeds
    fan_gear: int = 0
    cooling_fan_speed: int = 0
    heatbreak_fan_speed: int = 0

    # WiFi / Network
    wifi_signal: str = ""
    wifi_signal_dbm: int = 0

    # Nozzle info
    nozzle_diameter: float = 0.4
    nozzle_type: str = ""

    # System status
    home_flag: int = 0
    hw_switch_state: int = 0
    mc_print_stage: str = ""
    mc_print_sub_stage: int = 0
    print_error: int = 0
    stg_cur: int = 0

    # AMS state
    ams: Optional[AMSState] = None

    # Upgrade state
    upgrade_state: Dict[str, Any] = field(default_factory=dict)

    # Version info
    version: Dict[str, Any] = field(default_factory=dict)

    # Camera / Timelapse
    ipcam: Dict[str, Any] = field(default_factory=dict)
    timelapse: Dict[str, Any] = field(default_factory=dict)

    # Lights
    lights_report: List[Dict[str, Any]] = field(default_factory=list)

    # HMS (Health Management System) messages
    hms: List[Dict[str, Any]] = field(default_factory=list)

    # Speed settings
    spd_lvl: int = 0
    spd_mag: int = 0

    # Auxiliary fans
    big_fan1_speed: int = 0
    big_fan2_speed: int = 0

    # System info
    sdcard: bool = False
    gcode_file_prepare_percent: str = ""
    lifecycle: str = ""

    # External spool (virtual tray)
    vt_tray: Optional[Dict[str, Any]] = None

    # Raw data for any additional fields
    _raw_data: Dict[str, Any] = field(default_factory=dict, repr=False)

    @staticmethod
    def _parse_wifi_signal(signal_str: str) -> int:
        """Parse WiFi signal string (e.g., '-34dBm') to integer dBm"""
        if not signal_str:
            return 0
        try:
            return int(signal_str.replace("dBm", ""))
        except (ValueError, AttributeError):
            return 0

    @classmethod
    def from_mqtt_data(cls, data: Dict[str, Any], timestamp: Optional[str] = None) -> "PrinterState":
        """Create PrinterState from MQTT push_status data."""
        if timestamp is None:
            timestamp = datetime.now(ZoneInfo(app_settings.TIMEZONE)).isoformat()

        print_data = data.get("print", {})

        # Parse AMS data if present
        ams = None
        if "ams" in print_data:
            ams = AMSState.from_dict(print_data["ams"])

        wifi_signal = print_data.get("wifi_signal", "")

        return cls(
            timestamp=timestamp,
            sequence_id=str(print_data.get("sequence_id", "")),
            nozzle_temp=float(print_data.get("nozzle_temper", 0.0)),
            nozzle_target_temp=float(print_data.get("nozzle_target_temper", 0.0)),
            bed_temp=float(print_data.get("bed_temper", 0.0)),
            bed_target_temp=float(print_data.get("bed_target_temper", 0.0)),
            chamber_temp=float(print_data.get("chamber_temper", 0.0)),
            gcode_state=print_data.get("gcode_state", ""),
            print_percent=int(print_data.get("mc_percent", 0)),
            remaining_time_min=int(print_data.get("mc_remaining_time", 0)),
            layer_num=int(print_data.get("layer_num", 0)),
            total_layer_num=int(print_data.get("total_layer_num", 0)),
            print_line_number=int(print_data.get("mc_print_line_number", 0)),
            gcode_file=print_data.get("gcode_file", ""),
            subtask_name=print_data.get("subtask_name", ""),
            subtask_id=print_data.get("subtask_id", ""),
            task_id=print_data.get("task_id", ""),
            project_id=print_data.get("project_id", ""),
            profile_id=print_data.get("profile_id", ""),
            print_type=print_data.get("print_type", ""),
            fan_gear=int(print_data.get("fan_gear", 0)),
            cooling_fan_speed=int(print_data.get("cooling_fan_speed", 0)),
            heatbreak_fan_speed=int(print_data.get("heatbreak_fan_speed", 0)),
            wifi_signal=wifi_signal,
            wifi_signal_dbm=cls._parse_wifi_signal(wifi_signal),
            nozzle_diameter=float(print_data.get("nozzle_diameter", 0.4)),
            nozzle_type=print_data.get("nozzle_type", ""),
            home_flag=int(print_data.get("home_flag", 0)),
            hw_switch_state=int(print_data.get("hw_switch_state", 0)),
            mc_print_stage=str(print_data.get("mc_print_stage", "")),
            mc_print_sub_stage=int(print_data.get("mc_print_sub_stage", 0)),
            print_error=int(print_data.get("print_error", 0)),
            stg_cur=int(print_data.get("stg_cur", 0)),
            ams=ams,
            upgrade_state=print_data.get("upgrade_state", {}),
            version=print_data.get("version", {}),
            ipcam=print_data.get("ipcam", {}),
            timelapse=print_data.get("timelapse", {}),
            lights_report=print_data.get("lights_report", []),
            hms=print_data.get("hms", []),
            spd_lvl=int(print_data.get("spd_lvl", 0)),
            spd_mag=int(print_data.get("spd_mag", 0)),
            big_fan1_speed=int(print_data.get("big_fan1_speed", 0)),
            big_fan2_speed=int(print_data.get("big_fan2_speed", 0)),
            sdcard=bool(print_data.get("sdcard", False)),
            gcode_file_prepare_percent=str(print_data.get("gcode_file_prepare_percent", "")),
            lifecycle=print_data.get("lifecycle", ""),
            vt_tray=print_data.get("vt_tray"),
            _raw_data=data,
        )

    def get_snapshot(self) -> Dict[str, Any]:
        """Get a simplified snapshot for database logging."""
        snapshot = {
            "timestamp": self.timestamp,
            "nozzle_temp": round(self.nozzle_temp, 2),
            "nozzle_target_temp": round(self.nozzle_target_temp, 2),
            "bed_temp": round(self.bed_temp, 2),
            "bed_target_temp": round(self.bed_target_temp, 2),
            "chamber_temp": round(self.chamber_temp, 2),
            "nozzle_diameter": self.nozzle_diameter,
            "nozzle_type": self.nozzle_type,
            "gcode_state": self.gcode_state,
            "print_type": self.print_type,
            "print_percent": self.print_percent,
            "remaining_time_min": self.remaining_time_min,
            "layer_num": self.layer_num,
            "total_layer_num": self.total_layer_num,
            "print_line_number": self.print_line_number,
            "subtask_name": self.subtask_name,
            "gcode_file": self.gcode_file,
            "cooling_fan_speed": self.cooling_fan_speed,
            "heatbreak_fan_speed": self.heatbreak_fan_speed,
            "big_fan1_speed": self.big_fan1_speed,
            "big_fan2_speed": self.big_fan2_speed,
            "spd_lvl": self.spd_lvl,
            "spd_mag": self.spd_mag,
            "wifi_signal_dbm": self.wifi_signal_dbm,
            "print_error": self.print_error,
            "has_errors": self.print_error != 0,
            "hms": self.hms,
            "stg_cur": self.stg_cur,
            "lights_report": self.lights_report,
            "chamber_light": self._get_chamber_light_status(),
            "ipcam_record": self.ipcam.get("ipcam_record", ""),
            "timelapse": self.ipcam.get("timelapse", ""),
            "sdcard": self.sdcard,
            "gcode_file_prepare_percent": self.gcode_file_prepare_percent,
            "lifecycle": self.lifecycle,
        }

        if self.ams:
            snapshot["ams_unit_count"] = len(self.ams.units)
            snapshot["ams_status"] = self.ams.ams_status
            snapshot["ams_rfid_status"] = self.ams.ams_rfid_status
            snapshot["ams_exist_bits"] = self.ams.ams_exist_bits
            snapshot["tray_exist_bits"] = self.ams.tray_exist_bits
            snapshot["tray_is_bbl_bits"] = self.ams.tray_is_bbl_bits
            snapshot["tray_read_done_bits"] = self.ams.tray_read_done_bits
            snapshot["tray_now"] = self.ams.tray_now
            snapshot["ams_version"] = self.ams.version

            filaments = []
            for unit in self.ams.units:
                for tray in unit.trays:
                    if tray.tray_type:
                        filaments.append({
                            "tray_id": tray.tray_id,
                            "slot": tray.tray_id_name,
                            "type": tray.tray_type,
                            "sub_type": tray.tray_sub_brands,
                            "color": tray.tray_color,
                            "remain_percent": tray.remain_percent,
                            "tray_weight": tray.tray_weight,
                            "tray_diameter": tray.tray_diameter,
                            "nozzle_temp_min": tray.nozzle_temp_min,
                            "nozzle_temp_max": tray.nozzle_temp_max,
                            "tag_uid": tray.tag_uid,
                            "state": tray.state,
                            "tray_uuid": tray.tray_uuid,
                            "k": tray.k,
                            "n": tray.n,
                            "cali_idx": tray.cali_idx,
                            "total_len": tray.total_len,
                            "tray_info_idx": tray.tray_info_idx,
                            "tray_time": tray.tray_time,
                            "tray_bed_temp": tray.tray_bed_temp,
                            "bed_temp_type": tray.bed_temp_type,
                            "cols": tray.cols,
                        })
            snapshot["filaments"] = filaments

            ams_units = []
            for unit in self.ams.units:
                ams_units.append({
                    "unit_id": unit.unit_id,
                    "ams_id": unit.ams_id,
                    "chip_id": unit.chip_id,
                    "info": unit.info,
                    "humidity": unit.humidity,
                    "humidity_raw": unit.humidity_raw,
                    "temp": unit.temp,
                    "dry_time": unit.dry_time,
                })
            snapshot["ams_units"] = ams_units

            if self.ams.units:
                snapshot["ams_humidity"] = self.ams.units[0].humidity
                snapshot["ams_humidity_raw"] = self.ams.units[0].humidity_raw
                snapshot["ams_temp"] = self.ams.units[0].temp

        if self.vt_tray:
            snapshot["external_spool"] = {
                "type": self.vt_tray.get("tray_type", ""),
                "color": self.vt_tray.get("tray_color", ""),
                "remain": self.vt_tray.get("remain", 0),
            }

        return snapshot

    def _get_chamber_light_status(self) -> str:
        """Extract chamber light status from lights_report"""
        for light in self.lights_report:
            if light.get("node") == "chamber_light":
                return light.get("mode", "unknown")
        return "unknown"

    @property
    def is_printing(self) -> bool:
        return self.gcode_state.upper() in ("RUNNING", "PRINTING")

    @property
    def is_idle(self) -> bool:
        return self.gcode_state.upper() in ("IDLE", "FINISH", "")

    @property
    def is_paused(self) -> bool:
        return self.gcode_state.upper() == "PAUSE"


class PrinterStateAccumulator:
    """
    Accumulates MQTT updates into a complete printer state.

    BambuLab MQTT sends incremental updates - each message may only contain
    a subset of fields that have changed. This class maintains the complete
    state by merging updates.
    """

    def __init__(self):
        self._state_data: Dict[str, Any] = {"print": {}}
        self._last_update: Optional[str] = None
        self._update_count: int = 0

    def update(self, data: Dict[str, Any]) -> PrinterState:
        """Merge new MQTT data into accumulated state and return complete PrinterState."""
        timestamp = datetime.now(ZoneInfo(app_settings.TIMEZONE)).isoformat()
        self._last_update = timestamp
        self._update_count += 1

        if "print" in data:
            self._deep_merge(self._state_data["print"], data["print"])

        return PrinterState.from_mqtt_data(self._state_data, timestamp)

    def _deep_merge(self, base: Dict, update: Dict) -> None:
        """Recursively merge update into base dict"""
        for key, value in update.items():
            if key in base and isinstance(base[key], dict) and isinstance(value, dict):
                self._deep_merge(base[key], value)
            else:
                base[key] = value

    def get_state(self) -> PrinterState:
        """Get current accumulated state without updating"""
        timestamp = self._last_update or datetime.now(ZoneInfo(app_settings.TIMEZONE)).isoformat()
        return PrinterState.from_mqtt_data(self._state_data, timestamp)

    def reset(self) -> None:
        """Reset accumulated state"""
        self._state_data = {"print": {}}
        self._last_update = None
        self._update_count = 0

    @property
    def update_count(self) -> int:
        return self._update_count

    @property
    def last_update(self) -> Optional[str]:
        return self._last_update


class BambuPrinter:
    """
    High-level interface for BambuLab printer monitoring.
    Combines authentication, client, and MQTT into a single interface.
    """

    def __init__(
        self,
        username: Optional[str] = None,
        password: Optional[str] = None,
        token: Optional[str] = None,
        device_id: Optional[str] = None,
        on_update: Optional[Callable[[PrinterState], None]] = None,
        silent: bool = True,
        verification_timeout: int = 300,
    ):
        self.username = username or os.getenv("BAMBU_USERNAME")
        self.password = password or os.getenv("BAMBU_PASSWORD")
        self._token = token or os.getenv("BAMBU_TOKEN")
        self._device_id = device_id or os.getenv("BAMBU_DEVICE_ID")
        self._uid: Optional[str] = None
        self._on_update = on_update
        self._silent = silent
        self._verification_timeout = verification_timeout

        self._client: Optional[BambuClient] = None
        self._mqtt: Optional[MQTTClient] = None
        self._accumulator = PrinterStateAccumulator()
        self._connected = False
        self._devices: List[Dict[str, Any]] = []

    def _get_fresh_token(self, verification_code_timeout: int = 300) -> str:
        """Get a fresh token using credentials."""
        if not self.username or not self.password:
            raise ValueError(
                "Username and password required for token refresh. Provide as arguments "
                "or set BAMBU_USERNAME and BAMBU_PASSWORD environment variables."
            )

        print("\n" + "=" * 60)
        print("BambuLab Authentication")
        print("=" * 60)
        print(f"Authenticating as: {self.username}")
        print("This may require email verification (2FA)...")
        print()

        auth = BambuAuthenticator()

        try:
            if self._silent:
                with suppress_stdout():
                    token = auth.get_or_create_token(
                        username=self.username,
                        password=self.password
                    )
            else:
                token = auth.get_or_create_token(
                    username=self.username,
                    password=self.password
                )

            self._token = token
            print("Authentication successful!")
            print(f"Token: {token[:20]}...{token[-10:]}")
            print("=" * 60 + "\n")
            logger.info("BambuLab token obtained successfully")
            return token

        except Exception as e:
            error_msg = str(e).lower()

            if "verification" in error_msg or "code" in error_msg or "2fa" in error_msg:
                print("\n" + "-" * 60)
                print("EMAIL VERIFICATION REQUIRED")
                print("-" * 60)
                print("A verification code has been sent to your email.")
                print(f"You have {verification_code_timeout} seconds to enter it.")
                print()

                try:
                    code = timed_input(
                        "Enter verification code: ",
                        timeout_sec=verification_code_timeout
                    )

                    if not code:
                        raise ValueError("No verification code entered")

                    print("Verifying code...")
                    token = auth.login(
                        self.username,
                        self.password,
                        verification_code=code
                    )

                    self._token = token
                    print("\nAuthentication successful!")
                    print(f"Token: {token[:20]}...{token[-10:]}")
                    print("=" * 60 + "\n")
                    print("TIP: Save this token to BAMBU_TOKEN env var to skip login next time")
                    logger.info("BambuLab token obtained with 2FA verification")
                    return token

                except TimeoutError:
                    print("\nVerification timed out!")
                    raise TimeoutError(
                        f"Verification code not entered within {verification_code_timeout} seconds"
                    )
            else:
                print(f"\nAuthentication failed: {e}")
                raise

    def _ensure_token(self) -> str:
        """Ensure we have a valid token, refreshing if needed"""
        if self._token:
            logger.debug("Using existing token")
            return self._token

        print("\n" + "!" * 60)
        print("NO TOKEN FOUND")
        print("!" * 60)
        print("Checked:")
        print("  - Constructor 'token' parameter: Not provided")
        print("  - Environment variable 'BAMBU_TOKEN': Not set")
        print()
        print("Will attempt to authenticate with username/password...")
        print("!" * 60 + "\n")

        return self._get_fresh_token(verification_code_timeout=self._verification_timeout)

    def _on_mqtt_message(self, device_id: str, data: Dict[str, Any]) -> None:
        """Internal MQTT message handler"""
        if not data:
            return
        state = self._accumulator.update(data)
        if self._on_update:
            self._on_update(state)

    def connect(self, blocking: bool = False, retry_on_auth_error: bool = True) -> None:
        """Connect to printer via MQTT."""
        token = self._ensure_token()

        try:
            self._client = BambuClient(token=token)
            user_info = self._client.get_user_info()
            self._uid = str(user_info.get("uid", ""))

            if not self._device_id:
                self._devices = self._client.get_devices()
                if not self._devices:
                    raise RuntimeError("No devices found on this account")
                self._device_id = self._devices[0].get("dev_id")

            self._mqtt = MQTTClient(
                self._uid,
                token,
                self._device_id,
                on_message=self._on_mqtt_message
            )
            self._mqtt.connect(blocking=blocking)
            self._connected = True
            logger.info(f"Connected to BambuLab printer: {self._device_id}")

        except Exception as e:
            error_msg = str(e).lower()
            is_auth_error = any(x in error_msg for x in ["401", "unauthorized", "token", "auth", "expired"])

            if is_auth_error and retry_on_auth_error and self.username and self.password:
                logger.warning("Auth error detected, refreshing token and retrying...")
                self._token = None
                self._get_fresh_token()
                self.connect(blocking=blocking, retry_on_auth_error=False)
            else:
                raise

    def reconnect(self, blocking: bool = False) -> None:
        """Disconnect and reconnect."""
        self.disconnect()
        self._accumulator.reset()
        self.connect(blocking=blocking)

    def disconnect(self) -> None:
        """Disconnect from MQTT"""
        if self._mqtt:
            try:
                self._mqtt.disconnect()
            except Exception:
                pass
        self._connected = False
        logger.debug("Disconnected from BambuLab printer")

    def get_state(self) -> PrinterState:
        """Get current accumulated printer state"""
        return self._accumulator.get_state()

    def get_snapshot(self) -> Dict[str, Any]:
        """Get simplified snapshot for database logging"""
        return self._accumulator.get_state().get_snapshot()

    @property
    def device_id(self) -> Optional[str]:
        return self._device_id

    @property
    def devices(self) -> List[Dict[str, Any]]:
        return self._devices

    @property
    def is_connected(self) -> bool:
        return self._connected

    def __enter__(self):
        self.connect(blocking=False)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.disconnect()


__all__ = [
    "BambuAuthenticator",
    "BambuClient",
    "MQTTClient",
    "FilamentTray",
    "AMSUnit",
    "AMSState",
    "PrinterState",
    "PrinterStateAccumulator",
    "BambuPrinter",
]

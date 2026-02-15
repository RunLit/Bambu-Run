"""
Management command to continuously collect 3D printer MQTT data.
Collects printer metrics from Bambu Lab 3D printers.

Usage:
    python manage.py bambu_collector
    python manage.py bambu_collector --interval 60
    python manage.py bambu_collector --once
    python manage.py bambu_collector --verbose
"""

import logging
import os
import ssl
import time
from decimal import Decimal
from typing import Optional

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from bambu_run.conf import app_settings
from bambu_run.models import Printer, PrinterMetrics

logger = logging.getLogger("bambu_run.collector")


class Command(BaseCommand):
    """
    MQTT Poll -> PrinterMetrics -> FilamentSnapshot -> Auto-Match -> Update Filament
    """
    help = "Continuously collect 3D printer MQTT data from Bambu Lab printer"

    def add_arguments(self, parser):
        parser.add_argument(
            "--interval", type=int, default=30,
            help="Data collection interval in seconds (default: 30)",
        )
        parser.add_argument(
            "--once", action="store_true",
            help="Run once and exit (useful for testing/cron)",
        )
        parser.add_argument(
            "--verbose", action="store_true", help="Enable verbose logging"
        )
        parser.add_argument(
            "--disable-ssl-verify", action="store_true",
            help="Disable SSL certificate verification (use with caution)",
        )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.printer_client = None
        self.printer_device = None
        self.verbose = False
        self.disable_ssl_verify = False
        self.error_count = 0
        self.success_count = 0
        self.mqtt_connect_errors = 0
        self.start_time = None
        self.current_print_job = None
        self.last_gcode_state = None
        self.last_subtask_name = None
        self.trays_used = set()

    def handle(self, *args, **options):
        self.verbose = options["verbose"]
        self.disable_ssl_verify = options["disable_ssl_verify"]
        interval = options["interval"]
        run_once = options["once"]

        if self.disable_ssl_verify:
            logger.warning("SSL verification disabled - use with caution!")
            ssl._create_default_https_context = ssl._create_unverified_context
            os.environ["PYTHONHTTPSVERIFY"] = "0"
            os.environ["CURL_CA_BUNDLE"] = ""
            os.environ["REQUESTS_CA_BUNDLE"] = ""

            try:
                import paho.mqtt.client as mqtt_client

                original_tls_set = mqtt_client.Client.tls_set

                def patched_tls_set(
                    self, ca_certs=None, certfile=None, keyfile=None,
                    cert_reqs=ssl.CERT_NONE, tls_version=ssl.PROTOCOL_TLS, ciphers=None,
                ):
                    return original_tls_set(
                        self, ca_certs, certfile, keyfile, ssl.CERT_NONE, tls_version, ciphers,
                    )

                mqtt_client.Client.tls_set = patched_tls_set
                logger.debug("Successfully patched paho-mqtt SSL verification")
            except ImportError:
                logger.debug("paho-mqtt not yet imported, will rely on SSL context")
            except Exception as e:
                logger.debug(f"Could not patch paho-mqtt: {e}")

        self._configure_logging()

        try:
            self._initialize_printer()
        except Exception as e:
            raise CommandError(f"Initialization failed: {e}")

        self.start_time = timezone.now()
        logger.info(f"Bambu Run data collector started for printer: {self.printer_device.name}")
        logger.info(f"Collection interval: {interval} seconds")
        logger.info(f"Mode: {'Single run' if run_once else 'Continuous'}")

        try:
            if run_once:
                self._collect_printer_data()
                logger.info("Single collection completed successfully")
            else:
                self._run_continuous_loop(interval)
        except KeyboardInterrupt:
            self._print_statistics()
            logger.info("Bambu Run data collector stopped by user")
        except Exception as e:
            logger.exception(f"Fatal error in main loop: {e}")
            raise CommandError(f"Runner failed: {e}")

    def _configure_logging(self):
        log_level = logging.DEBUG if self.verbose else logging.INFO
        logger.setLevel(log_level)

        if not logger.handlers:
            handler = logging.StreamHandler()
            handler.setLevel(log_level)
            formatter = logging.Formatter(
                "%(asctime)s [%(levelname)s] %(message)s", datefmt="%Y-%m-%d %H:%M:%S"
            )
            handler.setFormatter(formatter)
            logger.addHandler(handler)

    def _initialize_printer(self):
        from bambu_run.mqtt_client import BambuPrinter

        bambu_username = os.environ.get("BAMBU_USERNAME")
        bambu_password = os.environ.get("BAMBU_PASSWORD")
        bambu_token = os.environ.get("BAMBU_TOKEN")
        bambu_device_id = os.environ.get("BAMBU_DEVICE_ID")

        if not bambu_token and not all([bambu_username, bambu_password]):
            raise CommandError(
                "Either BAMBU_TOKEN or both BAMBU_USERNAME and BAMBU_PASSWORD "
                "environment variables must be set"
            )

        logger.info("Connecting to Bambu Lab printer...")
        try:
            if bambu_token:
                logger.info("Using saved BAMBU_TOKEN for authentication")
                self.printer_client = BambuPrinter(
                    token=bambu_token, device_id=bambu_device_id
                )
            else:
                logger.info("Authenticating with username/password")
                self.printer_client = BambuPrinter(
                    username=bambu_username,
                    password=bambu_password,
                    device_id=bambu_device_id,
                )

            logger.info("Initiating MQTT connection...")
            self.printer_client.connect(blocking=False)
            logger.info("MQTT connection initiated (non-blocking)")

        except Exception as e:
            if "CERTIFICATE_VERIFY_FAILED" in str(e) or "SSL" in str(e):
                error_msg = (
                    f"SSL certificate verification failed: {e}\n\n"
                    "Solutions:\n"
                    "1. Run with --disable-ssl-verify flag\n"
                    "2. Install Python SSL certificates\n"
                    "3. pip install --upgrade certifi\n"
                )
                raise CommandError(error_msg)
            raise CommandError(f"Failed to initialize printer client: {e}")

        self.printer_device = self._ensure_printer_device_exists()
        logger.info(f"Initialized for printer device: {self.printer_device}")

    def _ensure_printer_device_exists(self) -> Printer:
        try:
            snapshot = self.printer_client.get_snapshot()

            if snapshot:
                device, created = Printer.objects.update_or_create(
                    model="Bambu Lab",
                    defaults={
                        "name": "Bambu Lab Printer",
                        "manufacturer": "Bambu Lab",
                        "is_active": True,
                    },
                )
                action = "Created" if created else "Updated"
                logger.info(f"{action} printer device record: {device}")
                return device
            else:
                logger.warning("Snapshot returned None - MQTT not connected yet")
                device = Printer.objects.filter(is_active=True).first()
                if device:
                    logger.info(f"Using existing device record: {device}")
                    return device
                else:
                    device = Printer.objects.create(
                        name="Bambu Lab Printer",
                        model="Bambu Lab",
                        manufacturer="Bambu Lab",
                        is_active=True,
                    )
                    logger.info(f"Created placeholder device: {device}")
                    return device

        except Exception as e:
            logger.error(f"Error during device initialization: {e}")
            try:
                device = Printer.objects.filter(is_active=True).first()
                if device:
                    logger.warning(f"Using existing device record from DB: {device}")
                    return device
                else:
                    raise CommandError(
                        "No printer device found in database and initialization failed."
                    )
            except Printer.DoesNotExist:
                raise CommandError("Failed to create or retrieve printer device.")

    def _run_continuous_loop(self, interval: int):
        iteration = 0
        while True:
            iteration += 1
            loop_start = time.time()

            if self.verbose:
                logger.debug(f"=== Iteration {iteration} ===")

            self._collect_printer_data()

            elapsed = time.time() - loop_start
            sleep_time = max(0, interval - elapsed)

            if self.verbose:
                logger.debug(f"Collection took {elapsed:.2f}s, sleeping for {sleep_time:.2f}s")

            if iteration % 100 == 0:
                self._print_statistics()

            time.sleep(sleep_time)

    def _convert_mqtt_color(self, mqtt_color):
        if not mqtt_color:
            return None
        color_hex = mqtt_color[:6] if len(mqtt_color) >= 6 else mqtt_color
        return f"#{color_hex.upper()}"

    def _match_filament_to_inventory(self, tray_data):
        from bambu_run.models import Filament

        tray_id = tray_data.get('tray_id')
        tray_uuid = tray_data.get('tray_uuid')
        tag_uid = tray_data.get('tag_uid')
        tag_id = tray_data.get('tag_id')
        type_val = tray_data.get('type')
        sub_type = tray_data.get('sub_type')
        color = tray_data.get('color')

        if tray_uuid:
            filament = Filament.objects.filter(tray_uuid=tray_uuid).first()
            if filament:
                if self.verbose:
                    logger.debug(f"Matched filament via tray_uuid: {tray_uuid[:16]}...")
                return filament, 'tray_uuid'

        if tag_uid:
            filament = Filament.objects.filter(tag_uid=tag_uid).first()
            if filament:
                if self.verbose:
                    logger.debug(f"Matched filament via tag_uid: {tag_uid}")
                return filament, 'tag_uid'

        if tag_id:
            filament = Filament.objects.filter(tag_id=tag_id).first()
            if filament:
                if self.verbose:
                    logger.debug(f"Matched filament via tag_id: {tag_id}")
                return filament, 'tag_id'

        if type_val and color:
            query_filters = {'type': type_val, 'color': color}
            if sub_type:
                query_filters['sub_type'] = sub_type

            filament = Filament.objects.filter(
                **query_filters, is_loaded_in_ams=False
            ).order_by('remaining_percent', 'last_used').first()

            if not filament:
                filament = Filament.objects.filter(
                    **query_filters
                ).order_by('remaining_percent', 'last_used').first()

            if filament:
                if self.verbose:
                    logger.debug(f"Matched filament via type+sub_type+color: {filament}")
                return filament, 'type_sub_type_color'

        if self.verbose:
            logger.info(f"No match found for tray {tray_id}. Auto-creating new filament...")

        filament = self._auto_create_filament(tray_data)
        return filament, 'auto_created'

    def _auto_create_filament(self, tray_data):
        from bambu_run.models import Filament, FilamentType
        from bambu_run.utils import strip_color_padding, match_filament_color

        tray_uuid = tray_data.get('tray_uuid')
        tag_uid = tray_data.get('tag_uid')
        type_val = tray_data.get('type', 'Unknown')
        sub_type = tray_data.get('sub_type', '')
        mqtt_color = tray_data.get('color')
        remain_percent = tray_data.get('remain_percent', 100)
        diameter = tray_data.get('tray_diameter', 1.75)
        initial_weight = tray_data.get('tray_weight', 1000)

        default_brand = app_settings.AUTO_CREATE_BRAND

        color_code = strip_color_padding(mqtt_color)
        color_hex = f"#{color_code}" if color_code else None

        color_name = mqtt_color
        filament_color = match_filament_color(
            filament_type=type_val,
            filament_sub_type=sub_type,
            color_code=color_code,
            brand=default_brand
        )

        if filament_color:
            color_name = filament_color.color_name
            if self.verbose:
                logger.info(f"Matched color from database: {color_name} (#{color_code})")
        else:
            color_name = mqtt_color
            if self.verbose:
                logger.warning(
                    f"No color match in database for {type_val} {sub_type} #{color_code}. "
                    f"Using hex code as color name."
                )

        filament_type_obj, ft_created = FilamentType.objects.get_or_create(
            type=type_val,
            sub_type=sub_type or None,
            brand=default_brand,
        )
        if ft_created and self.verbose:
            logger.info(f"Auto-created FilamentType: {filament_type_obj}")

        filament = Filament.objects.create(
            filament_type=filament_type_obj,
            tray_uuid=tray_uuid,
            tag_uid=tag_uid,
            type=type_val,
            sub_type=sub_type,
            brand=default_brand,
            color=color_name,
            color_hex=color_hex,
            diameter=diameter,
            initial_weight_grams=initial_weight,
            remaining_percent=remain_percent,
            created_by='Auto Detection',
            is_loaded_in_ams=True,
            current_tray_id=tray_data.get('tray_id'),
            last_loaded_date=timezone.now(),
        )

        filament.update_remaining_weight()
        filament.save()

        logger.info(
            f"Auto-created filament: {filament.brand} {filament.type} "
            f"{filament.sub_type} - {filament.color} (SN: {tray_uuid[:16] if tray_uuid else 'N/A'}...)"
        )

        return filament

    def _update_filament_status(self, filament, tray_id, remain_percent):
        from bambu_run.models import Filament

        if filament.remaining_percent != remain_percent:
            filament.remaining_percent = remain_percent
            filament.update_remaining_weight()
            filament.last_used = timezone.now()
            if self.verbose:
                logger.debug(f"Updated filament {filament}: {remain_percent}%")

        if not filament.is_loaded_in_ams or filament.current_tray_id != tray_id:
            previous_filament = Filament.objects.filter(
                is_loaded_in_ams=True, current_tray_id=tray_id
            ).exclude(id=filament.id).first()

            if previous_filament:
                previous_filament.is_loaded_in_ams = False
                previous_filament.current_tray_id = None
                previous_filament.save()
                logger.info(
                    f"Auto-unloaded {previous_filament} from Tray {tray_id} "
                    f"(replaced by {filament.brand} {filament.type} - {filament.color})"
                )

            filament.is_loaded_in_ams = True
            filament.current_tray_id = tray_id
            filament.last_loaded_date = timezone.now()
            if self.verbose:
                logger.debug(f"Updated filament location: Tray {tray_id}")

        filament.save()

    def _create_filament_snapshots(self, printer_metric, filaments_data, snapshot):
        from bambu_run.models import FilamentSnapshot

        ams_units = {
            u.get('unit_id'): u for u in snapshot.get('ams_units', [])
        }

        for tray_data in filaments_data:
            tray_id = tray_data.get('tray_id')
            if tray_id is None:
                continue

            filament, match_method = self._match_filament_to_inventory(tray_data)

            if filament:
                remain_percent = tray_data.get('remain_percent')
                if remain_percent is not None:
                    self._update_filament_status(filament, tray_id, remain_percent)

            unit_id = str(int(tray_id) // 4) if tray_id.isdigit() else None
            unit_data = ams_units.get(unit_id, {})

            FilamentSnapshot.objects.create(
                printer_metric=printer_metric,
                filament=filament,
                tray_id=tray_id,
                slot_name=tray_data.get('slot'),
                type=tray_data.get('type'),
                sub_type=tray_data.get('sub_type'),
                color=tray_data.get('color'),
                remain_percent=tray_data.get('remain_percent'),
                k_value=tray_data.get('k'),
                temp=self._to_decimal(unit_data.get('temp')),
                humidity=unit_data.get('humidity'),
                tag_uid=tray_data.get('tag_uid'),
                tray_uuid=tray_data.get('tray_uuid'),
                state=tray_data.get('state'),
                auto_matched=bool(filament),
                match_method=match_method
            )

    def _track_print_job(self, metric, snapshot):
        from bambu_run.models import PrintJob, FilamentUsage

        gcode_state = snapshot.get('gcode_state')
        subtask_name = snapshot.get('subtask_name')

        if self._is_print_starting(gcode_state, subtask_name):
            if self.current_print_job:
                self._finalize_print_job(metric, snapshot)

            self.current_print_job = PrintJob.objects.create(
                device=self.printer_device,
                project_name=subtask_name,
                gcode_file=snapshot.get('gcode_file'),
                start_time=metric.timestamp,
                start_metric=metric,
                total_layers=snapshot.get('total_layer_num'),
                completion_percent=snapshot.get('print_percent', 0)
            )
            self.trays_used = set()
            logger.info(f"Print job started: {subtask_name}")

        if self.current_print_job:
            tray_now = snapshot.get('tray_now', '')
            if tray_now not in (None, '', '255'):
                try:
                    tray_id = int(tray_now)
                    if 0 <= tray_id <= 15:
                        self.trays_used.add(tray_id)
                except (ValueError, TypeError):
                    pass

        if self._is_print_ending(gcode_state) and self.current_print_job:
            self._finalize_print_job(metric, snapshot)

        self.last_gcode_state = gcode_state
        self.last_subtask_name = subtask_name

    def _is_print_starting(self, gcode_state, subtask_name):
        is_printing = gcode_state not in ['FINISH', 'IDLE', 'FAILED', None, '']
        has_new_job = subtask_name and subtask_name != self.last_subtask_name
        return is_printing and has_new_job

    def _is_print_ending(self, gcode_state):
        ending_states = ['FINISH', 'FAILED']
        return gcode_state in ending_states and self.last_gcode_state not in ending_states

    def _finalize_print_job(self, metric, snapshot):
        from bambu_run.models import FilamentUsage

        self.current_print_job.end_time = metric.timestamp
        self.current_print_job.end_metric = metric
        self.current_print_job.final_status = snapshot.get('gcode_state')
        self.current_print_job.completion_percent = snapshot.get('print_percent', 0)
        self.current_print_job.calculate_duration()
        self.current_print_job.save()

        start_metric = self.current_print_job.start_metric
        if not start_metric:
            logger.warning(f"No start_metric for job {self.current_print_job.id}, skipping filament usage")
        elif not self.trays_used:
            logger.warning(f"No trays tracked for job {self.current_print_job.project_name}, skipping filament usage")
        else:
            for tray_id in self.trays_used:
                start_snap = start_metric.filament_snapshots.filter(
                    tray_id=tray_id, filament__isnull=False
                ).first()
                if not start_snap:
                    continue

                end_snap = metric.filament_snapshots.filter(
                    filament=start_snap.filament, tray_id=tray_id
                ).first()

                usage = FilamentUsage.objects.create(
                    print_job=self.current_print_job,
                    filament=start_snap.filament,
                    tray_id=tray_id,
                    starting_percent=start_snap.remain_percent or 100,
                    ending_percent=end_snap.remain_percent if end_snap else None,
                    is_primary=(len(self.trays_used) == 1),
                )
                usage.calculate_consumed()
                usage.save()

                if self.verbose:
                    logger.debug(
                        f"Filament usage for {start_snap.filament} (tray {tray_id}): "
                        f"{usage.starting_percent}% -> {usage.ending_percent}%, consumed {usage.consumed_percent}%"
                    )

        logger.info(
            f"Print job finished: {self.current_print_job.project_name} "
            f"({self.current_print_job.final_status}) - Duration: {self.current_print_job.duration_minutes} min, "
            f"Trays used: {sorted(self.trays_used) if self.trays_used else 'none tracked'}"
        )

        self.current_print_job = None
        self.trays_used = set()

    def _collect_printer_data(self):
        try:
            snapshot = self.printer_client.get_snapshot()

            if snapshot is None:
                self.mqtt_connect_errors += 1
                if self.mqtt_connect_errors <= 5 or self.verbose:
                    logger.warning(
                        f"MQTT not connected yet or no data available "
                        f"(attempt {self.mqtt_connect_errors})"
                    )
                return

            with transaction.atomic():
                metric = PrinterMetrics.objects.create(
                    device=self.printer_device,
                    timestamp=timezone.now(),
                    nozzle_temp=self._to_decimal(snapshot.get("nozzle_temp")),
                    nozzle_target_temp=self._to_decimal(snapshot.get("nozzle_target_temp")),
                    bed_temp=self._to_decimal(snapshot.get("bed_temp")),
                    bed_target_temp=self._to_decimal(snapshot.get("bed_target_temp")),
                    chamber_temp=self._to_decimal(snapshot.get("chamber_temp")),
                    nozzle_diameter=self._to_decimal(snapshot.get("nozzle_diameter")),
                    nozzle_type=snapshot.get("nozzle_type"),
                    gcode_state=snapshot.get("gcode_state"),
                    print_type=snapshot.get("print_type"),
                    print_percent=snapshot.get("print_percent"),
                    remaining_time_min=snapshot.get("remaining_time_min"),
                    layer_num=snapshot.get("layer_num"),
                    total_layer_num=snapshot.get("total_layer_num"),
                    print_line_number=snapshot.get("print_line_number"),
                    subtask_name=snapshot.get("subtask_name"),
                    gcode_file=snapshot.get("gcode_file"),
                    cooling_fan_speed=snapshot.get("cooling_fan_speed"),
                    heatbreak_fan_speed=snapshot.get("heatbreak_fan_speed"),
                    big_fan1_speed=snapshot.get("big_fan1_speed"),
                    big_fan2_speed=snapshot.get("big_fan2_speed"),
                    spd_lvl=snapshot.get("spd_lvl"),
                    spd_mag=snapshot.get("spd_mag"),
                    wifi_signal_dbm=snapshot.get("wifi_signal_dbm"),
                    print_error=snapshot.get("print_error", 0),
                    has_errors=snapshot.get("has_errors", False),
                    chamber_light=snapshot.get("chamber_light"),
                    ipcam_record=snapshot.get("ipcam_record"),
                    timelapse=snapshot.get("timelapse"),
                    stg_cur=snapshot.get("stg_cur"),
                    sdcard=snapshot.get("sdcard"),
                    gcode_file_prepare_percent=snapshot.get("gcode_file_prepare_percent"),
                    lifecycle=snapshot.get("lifecycle"),
                    hms=snapshot.get("hms", []),
                    ams_unit_count=snapshot.get("ams_unit_count"),
                    ams_status=snapshot.get("ams_status"),
                    ams_rfid_status=snapshot.get("ams_rfid_status"),
                    ams_humidity=snapshot.get("ams_humidity"),
                    ams_humidity_raw=snapshot.get("ams_humidity_raw"),
                    ams_temp=self._to_decimal(snapshot.get("ams_temp")),
                    ams_version=snapshot.get("ams_version"),
                    tray_is_bbl_bits=snapshot.get("tray_is_bbl_bits"),
                    tray_read_done_bits=snapshot.get("tray_read_done_bits"),
                    filaments=snapshot.get("filaments", []),
                    ams_units=snapshot.get("ams_units", []),
                    external_spool=snapshot.get("external_spool", {}),
                    lights_report=snapshot.get("lights_report", []),
                )

                filaments_data = snapshot.get('filaments', [])
                if filaments_data:
                    self._create_filament_snapshots(metric, filaments_data, snapshot)

                self._track_print_job(metric, snapshot)

                self.success_count += 1

                if self.verbose:
                    logger.debug(
                        f"Printer Metrics: Nozzle={snapshot.get('nozzle_temp')}C, "
                        f"Bed={snapshot.get('bed_temp')}C, "
                        f"Progress={snapshot.get('print_percent')}%, "
                        f"State={snapshot.get('gcode_state')}"
                    )

        except Exception as e:
            self.error_count += 1
            logger.error(f"Error collecting printer data (total errors: {self.error_count}): {e}")
            if self.verbose:
                logger.exception("Detailed traceback:")

    def _to_decimal(self, value) -> Optional[Decimal]:
        if value is None:
            return None
        try:
            return Decimal(str(value))
        except (ValueError, TypeError):
            return None

    def _print_statistics(self):
        if self.start_time:
            runtime = timezone.now() - self.start_time
            total_collections = self.success_count + self.error_count
            success_rate = (
                (self.success_count / total_collections * 100)
                if total_collections > 0
                else 0
            )

            logger.info("=== Statistics ===")
            logger.info(f"Runtime: {runtime}")
            logger.info(f"Successful collections: {self.success_count}")
            logger.info(f"Failed collections: {self.error_count}")
            logger.info(f"MQTT connection warnings: {self.mqtt_connect_errors}")
            logger.info(f"Success rate: {success_rate:.1f}%")

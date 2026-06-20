"""
Diagnose multi-printer cloud data for a Bambu Lab account.

Run this if `bambu_collector` doesn't pick up all your printers, or the data
collected for a second/third printer looks wrong. It authenticates with your
Bambu Lab account, lists every device the cloud API reports, listens briefly
for raw MQTT data from each one, and writes a redacted JSON report you can
attach to a GitHub issue.

Usage:
    python manage.py bambu_diagnose
    python manage.py bambu_diagnose --listen-seconds 15
    python manage.py bambu_diagnose --output my_report.json
    python manage.py bambu_diagnose --no-redact   # local debugging only — do NOT post this output publicly
"""

import json
import logging
import time

from django.core.management.base import BaseCommand, CommandError

from bambu_run.diagnostics import build_diagnostics_report, redact_diagnostics

logger = logging.getLogger("bambu_run.diagnose")


class Command(BaseCommand):
    help = "Authenticate, list every printer on the account, and write a redacted diagnostics report."

    def add_arguments(self, parser):
        parser.add_argument(
            "--listen-seconds", type=float, default=8.0,
            help="How long to listen for MQTT data per device (default: 8)",
        )
        parser.add_argument(
            "--output", type=str, default=None,
            help="Output file path (default: bambu_diagnostics_<timestamp>.json)",
        )
        parser.add_argument(
            "--no-redact", action="store_true",
            help="Keep full serials/identifiers unmasked. For your own debugging only — "
                 "do not paste this output into a public GitHub issue.",
        )

    def handle(self, *args, **options):
        import os
        from bambu_run.mqtt_client import BambuPrinter, BambuClient

        listen_seconds = options["listen_seconds"]
        redact = not options["no_redact"]

        bambu_username = os.environ.get("BAMBU_USERNAME")
        bambu_password = os.environ.get("BAMBU_PASSWORD")
        bambu_token = os.environ.get("BAMBU_TOKEN")

        if not bambu_token and not all([bambu_username, bambu_password]):
            raise CommandError(
                "Either BAMBU_TOKEN or both BAMBU_USERNAME and BAMBU_PASSWORD "
                "environment variables must be set"
            )

        self.stdout.write("Authenticating with Bambu Lab cloud...")
        auth = BambuPrinter(username=bambu_username, password=bambu_password, token=bambu_token)
        token = auth._ensure_token()

        cloud = BambuClient(token=token)
        devices = cloud.get_devices()

        self.stdout.write(self.style.SUCCESS(f"Found {len(devices)} device(s) on this account:"))
        for device in devices:
            self.stdout.write(
                f"  - {device.get('name', 'unknown')} "
                f"({device.get('dev_product_name', 'unknown model')}) "
                f"online={device.get('online')}"
            )
        if len(devices) < 2:
            self.stdout.write(self.style.WARNING(
                "Only one device returned by the cloud API — if you own multiple printers, "
                "this is likely the root cause. Note this in the GitHub issue."
            ))

        raw_payloads = {}
        for device in devices:
            dev_id = device.get("dev_id")
            if not dev_id:
                continue
            self.stdout.write(f"Listening to {device.get('name', dev_id)} for {listen_seconds:.0f}s...")
            client = BambuPrinter(token=token, device_id=dev_id)
            try:
                client.connect(blocking=False)
                self._request_full_status_when_ready(client)
                time.sleep(listen_seconds)
                state = client.get_state()
                raw_payloads[dev_id] = state._raw_data.get("print") if state._raw_data else None
            except Exception as e:
                self.stdout.write(self.style.WARNING(f"  Could not collect data for {dev_id}: {e}"))
                raw_payloads[dev_id] = None
            finally:
                client.disconnect()

        report = build_diagnostics_report(devices, raw_payloads)
        report = redact_diagnostics(report, redact=redact)

        output_path = options["output"] or f"bambu_diagnostics_{int(time.time())}.json"
        with open(output_path, "w") as f:
            json.dump(report, f, indent=2, default=str)

        self.stdout.write(self.style.SUCCESS(f"\nDiagnostics written to: {output_path}"))
        if not redact:
            self.stdout.write(self.style.WARNING(
                "--no-redact was used: this file contains unmasked serials/identifiers. "
                "Do not attach it to a public GitHub issue as-is."
            ))
        else:
            self.stdout.write(
                "Serials/identifiers are masked. Please skim the file once before posting — "
                "then attach it to https://github.com/RunLit/Bambu-Run/issues/10"
            )

    def _request_full_status_when_ready(self, client, timeout: float = 20.0) -> None:
        deadline = time.time() + timeout
        while time.time() < deadline:
            mqtt_client = getattr(client, "_mqtt", None)
            if mqtt_client is not None and getattr(mqtt_client, "connected", False):
                client._mqtt.request_full_status()
                return
            time.sleep(0.5)

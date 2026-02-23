"""
Management command to import Bambu Lab filament color catalogs into the FilamentColor database.

Parses .txt color catalog files (one file per filament sub-type) and creates or skips
FilamentColor records. FilamentType records are auto-created as needed.

Usage:
    # Import a single file
    python manage.py bambu_import_colors docs/Bambu_Color_Catalog/PLA\ Basic.txt

    # Import all .txt files in a directory
    python manage.py bambu_import_colors docs/Bambu_Color_Catalog/

    # Dry-run (preview without writing)
    python manage.py bambu_import_colors docs/Bambu_Color_Catalog/ --dry-run

    # Fail instead of auto-creating missing FilamentType entries
    python manage.py bambu_import_colors docs/Bambu_Color_Catalog/ --no-auto-create-filament-type

File naming convention:
    The stem determines filament type and sub-type:
      PLA Basic.txt  → type=PLA,  sub_type=PLA Basic
      PA6-GF.txt     → type=PA6,  sub_type=PA6-GF
      ABS.txt        → type=ABS,  sub_type=ABS

Supported file formats:
    Format 1 (multi-line):    Format 2 (same-line / tab-separated):
      Jade White                Black Walnut    #4F3F24
      Hex:#FFFFFF               Rosewood        #4C241C

    Hex values may appear as: Hex:#RRGGBB  Hex: #RRGGBB  #RRGGBB  RRGGBB
"""

import logging
import re
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from bambu_run.models import FilamentColor, FilamentType

logger = logging.getLogger("bambu_run.import_colors")

BRAND = "Bambu Lab"

# ─── Parsing helpers ──────────────────────────────────────────────────────────

_SAME_LINE_RE = re.compile(
    r'^(.+?)\s+(?:Hex\s*:\s*)?#?([0-9A-Fa-f]{6})\s*$', re.IGNORECASE
)
_HEX_ONLY_RE = re.compile(
    r'^\s*(?:Hex\s*:\s*)?#?([0-9A-Fa-f]{6})\s*$', re.IGNORECASE
)


def _stem_to_type_and_subtype(stem):
    """
    Derive (filament_type, filament_sub_type) from a file stem.

    The sub-type is the full stem. The type is everything before the first
    space or hyphen.

      "PLA Basic"      → ("PLA",  "PLA Basic")
      "PA6-GF"         → ("PA6",  "PA6-GF")
      "ABS"            → ("ABS",  "ABS")
      "PETG HF"        → ("PETG", "PETG HF")
    """
    sub_type = stem
    m = re.search(r'[ -]', stem)
    filament_type = stem[: m.start()] if m else stem
    return filament_type, sub_type


def _parse_file(path):
    """
    Parse a color catalog file and return a list of (color_name, hex_code) tuples.

    hex_code is always 6-char uppercase without '#'.

    Raises ValueError if the file cannot be read.
    """
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        raise ValueError(f"Cannot read file: {exc}") from exc

    lines = text.splitlines()
    colors = []
    i = 0

    while i < len(lines):
        stripped = lines[i].strip()
        i += 1

        if not stripped:
            continue

        # ── Format 2: color name + hex on the same line ─────────────────────
        m = _SAME_LINE_RE.match(stripped)
        if m:
            colors.append((m.group(1).strip(), m.group(2).upper()))
            continue

        # ── Orphaned hex line with no preceding name — skip ──────────────────
        if _HEX_ONLY_RE.match(stripped):
            logger.warning("  [parse] Orphaned hex line (no preceding name): '%s'", stripped)
            continue

        # ── Format 1: color name on this line, hex on the next ──────────────
        color_name = stripped
        found_hex = False

        while i < len(lines):
            next_stripped = lines[i].strip()
            i += 1  # tentatively consume

            if not next_stripped:
                continue  # skip blank lines between name and hex

            m_hex = _HEX_ONLY_RE.match(next_stripped)
            if m_hex:
                colors.append((color_name, m_hex.group(1).upper()))
                found_hex = True
            else:
                # Not a hex line — put it back for the outer loop
                i -= 1
                logger.warning(
                    "  [parse] Expected hex after '%s', got '%s' — skipping name",
                    color_name,
                    next_stripped,
                )
            break  # look-ahead done (one non-empty line checked)

        if not found_hex:
            logger.warning(
                "  [parse] Color '%s' has no hex line following it — skipping", color_name
            )

    return colors


# ─── Command ──────────────────────────────────────────────────────────────────


class Command(BaseCommand):
    help = (
        "Import Bambu Lab filament color catalog .txt files into the FilamentColor database. "
        "Accepts a single .txt file or a directory of .txt files."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "path",
            help="Path to a single .txt catalog file or a directory containing .txt files.",
        )
        parser.add_argument(
            "--auto-create-filament-type",
            default=True,
            action="store_true",
            dest="auto_create",
            help="Auto-create FilamentType entries when missing (default: enabled).",
        )
        parser.add_argument(
            "--no-auto-create-filament-type",
            action="store_false",
            dest="auto_create",
            help="Skip colors whose FilamentType entry does not exist instead of creating it.",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Preview what would be imported without writing to the database.",
        )

    def handle(self, *args, **options):
        input_path = Path(options["path"]).expanduser().resolve()
        auto_create = options["auto_create"]
        dry_run = options["dry_run"]

        if dry_run:
            self.stdout.write(self.style.WARNING("DRY RUN — no changes will be written.\n"))

        # ── Collect files to process ─────────────────────────────────────────
        if input_path.is_dir():
            files = sorted(input_path.glob("*.txt"))
            if not files:
                raise CommandError(f"No .txt files found in: {input_path}")
            self.stdout.write(f"Found {len(files)} .txt file(s) in {input_path}\n")
        elif input_path.is_file():
            if input_path.suffix.lower() != ".txt":
                raise CommandError(f"Expected a .txt file, got: {input_path.name}")
            files = [input_path]
        else:
            raise CommandError(f"Path does not exist: {input_path}")

        # ── Counters ─────────────────────────────────────────────────────────
        total_created = 0
        total_skipped_dup = 0
        total_skipped_no_type = 0
        total_errors = 0

        for file_path in files:
            created, skipped_dup, skipped_no_type, errors = self._process_file(
                file_path, auto_create=auto_create, dry_run=dry_run
            )
            total_created += created
            total_skipped_dup += skipped_dup
            total_skipped_no_type += skipped_no_type
            total_errors += errors

        # ── Summary ──────────────────────────────────────────────────────────
        self.stdout.write("\n" + "─" * 50)
        self.stdout.write(
            self.style.SUCCESS(f"  Created:              {total_created}")
        )
        self.stdout.write(f"  Skipped (duplicate):  {total_skipped_dup}")
        if total_skipped_no_type:
            self.stdout.write(
                self.style.WARNING(f"  Skipped (no type):    {total_skipped_no_type}")
            )
        if total_errors:
            self.stdout.write(
                self.style.ERROR(f"  Errors:               {total_errors}")
            )
        if dry_run:
            self.stdout.write(self.style.WARNING("\nDRY RUN complete — nothing was written."))

    # ── Per-file processing ───────────────────────────────────────────────────

    def _process_file(self, file_path, *, auto_create, dry_run):
        """Process one catalog file. Returns (created, skipped_dup, skipped_no_type, errors)."""
        stem = file_path.stem
        filament_type, filament_sub_type = _stem_to_type_and_subtype(stem)

        self.stdout.write(
            f"\nProcessing: {file_path.name}  "
            f"→  type={filament_type!r}  sub_type={filament_sub_type!r}"
        )

        # ── Parse file ───────────────────────────────────────────────────────
        try:
            colors = _parse_file(file_path)
        except ValueError as exc:
            self.stderr.write(self.style.ERROR(f"  ERROR reading file: {exc}"))
            return 0, 0, 0, 1

        if not colors:
            self.stdout.write(self.style.WARNING("  No colors parsed — skipping file."))
            return 0, 0, 0, 0

        self.stdout.write(f"  Parsed {len(colors)} color(s).")

        # ── Resolve FilamentType ─────────────────────────────────────────────
        filament_type_obj = self._resolve_filament_type(
            filament_type, filament_sub_type, auto_create=auto_create, dry_run=dry_run
        )
        if filament_type_obj is None and not auto_create:
            self.stdout.write(
                self.style.WARNING(
                    f"  No FilamentType for type={filament_type!r} "
                    f"sub_type={filament_sub_type!r} brand={BRAND!r} — "
                    f"skipping all {len(colors)} color(s) in this file."
                )
            )
            return 0, 0, len(colors), 0

        # ── Import colors ────────────────────────────────────────────────────
        created = skipped_dup = skipped_no_type = errors = 0

        for color_name, hex_code in colors:
            result = self._import_color(
                color_name=color_name,
                hex_code=hex_code,
                filament_type=filament_type,
                filament_sub_type=filament_sub_type,
                filament_type_obj=filament_type_obj,
                dry_run=dry_run,
            )
            if result == "created":
                created += 1
            elif result == "duplicate":
                skipped_dup += 1
            elif result == "no_type":
                skipped_no_type += 1
            elif result == "error":
                errors += 1

        self.stdout.write(
            f"  → created={created}  duplicate={skipped_dup}  "
            f"no_type={skipped_no_type}  errors={errors}"
        )
        return created, skipped_dup, skipped_no_type, errors

    def _resolve_filament_type(self, filament_type, filament_sub_type, *, auto_create, dry_run):
        """
        Return the matching FilamentType instance.

        If none exists:
          - auto_create=True  → create it (or simulate in dry-run) and return it
          - auto_create=False → return None
        """
        try:
            obj = FilamentType.objects.get(
                type=filament_type,
                sub_type=filament_sub_type,
                brand=BRAND,
            )
            return obj
        except FilamentType.DoesNotExist:
            pass

        if not auto_create:
            return None

        if dry_run:
            self.stdout.write(
                self.style.NOTICE(
                    f"  [dry-run] Would create FilamentType: "
                    f"type={filament_type!r} sub_type={filament_sub_type!r} brand={BRAND!r}"
                )
            )
            return None  # can't return a real object in dry-run

        try:
            with transaction.atomic():
                obj, created = FilamentType.objects.get_or_create(
                    type=filament_type,
                    sub_type=filament_sub_type,
                    brand=BRAND,
                )
            if created:
                self.stdout.write(
                    self.style.SUCCESS(
                        f"  Created FilamentType: "
                        f"type={filament_type!r} sub_type={filament_sub_type!r} brand={BRAND!r}"
                    )
                )
            return obj
        except Exception as exc:
            self.stderr.write(
                self.style.ERROR(
                    f"  ERROR creating FilamentType "
                    f"(type={filament_type!r} sub_type={filament_sub_type!r}): {exc}"
                )
            )
            return None

    def _import_color(
        self,
        *,
        color_name,
        hex_code,
        filament_type,
        filament_sub_type,
        filament_type_obj,
        dry_run,
    ):
        """
        Import a single (color_name, hex_code) entry.

        Returns one of: "created", "duplicate", "no_type", "error"
        """
        if filament_type_obj is None:
            # dry-run path: FilamentType would have been created but isn't real yet
            if dry_run:
                self.stdout.write(
                    f"  [dry-run] Would create: {color_name!r} #{hex_code}  "
                    f"({filament_type} / {filament_sub_type})"
                )
                return "created"
            return "no_type"

        # ── Duplicate check ──────────────────────────────────────────────────
        # All five fields must match to be considered a duplicate:
        #   color_code (exact), color_name (case-insensitive), brand,
        #   denormalised filament_type + filament_sub_type
        duplicate = FilamentColor.objects.filter(
            color_code=hex_code,
            color_name__iexact=color_name,
            brand=BRAND,
            filament_type=filament_type,
            filament_sub_type=filament_sub_type,
        ).exists()

        if duplicate:
            logger.debug("  Duplicate — skipping: %s #%s", color_name, hex_code)
            return "duplicate"

        if dry_run:
            self.stdout.write(
                f"  [dry-run] Would create: {color_name!r} #{hex_code}  "
                f"({filament_type} / {filament_sub_type})"
            )
            return "created"

        # ── Write to database ────────────────────────────────────────────────
        try:
            with transaction.atomic():
                FilamentColor.objects.create(
                    color_code=hex_code,
                    color_name=color_name,
                    filament_type_fk=filament_type_obj,
                    filament_type=filament_type,
                    filament_sub_type=filament_sub_type,
                    brand=BRAND,
                )
            self.stdout.write(
                f"  + {color_name!r} #{hex_code}  ({filament_type} / {filament_sub_type})"
            )
            return "created"
        except Exception as exc:
            self.stderr.write(
                self.style.ERROR(
                    f"  ERROR saving {color_name!r} #{hex_code}: {exc}"
                )
            )
            return "error"

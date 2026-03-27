"""
Utility functions for filament color matching
"""

# BambuLab AMS reports colors as 8-char hex with an alpha channel suffix (e.g. '489FDFFF').
# Opaque filaments use alpha 'FF'. Clear/transparent filaments use alpha '00' (e.g. '00000000').
MQTT_COLOR_HEX_LENGTH = 6


def is_mqtt_color_transparent(mqtt_color):
    """
    Return True if the AMS color represents a clear/transparent filament.
    Bambu Lab uses alpha=00 for transparent (e.g. '00000000'), not 'FF' like opaque filaments.
    """
    return bool(mqtt_color) and len(mqtt_color) == 8 and mqtt_color[6:8].upper() == '00'


def strip_color_padding(mqtt_color):
    """
    Strip alpha padding from MQTT color, returning the 6-char RGB hex.
    MQTT: '000000FF' -> '000000'  (opaque black)
    MQTT: '00000000' -> '000000'  (transparent — use is_mqtt_color_transparent() to distinguish)
    MQTT: 'FF6A13FF' -> 'FF6A13'
    """
    if not mqtt_color:
        return None
    if len(mqtt_color) == 8:
        return mqtt_color[:MQTT_COLOR_HEX_LENGTH].upper()
    return mqtt_color[:MQTT_COLOR_HEX_LENGTH].upper() if len(mqtt_color) >= MQTT_COLOR_HEX_LENGTH else mqtt_color.upper()


def match_filament_color(filament_type, filament_sub_type, color_code, brand='Bambu Lab'):
    """
    Match a FilamentColor from database based on type, sub_type, color_code, and brand

    Returns:
        FilamentColor instance or None
    """
    from .models import FilamentColor

    if not all([filament_type, color_code]):
        return None

    # Try exact match first (with sub_type)
    if filament_sub_type:
        color_match = FilamentColor.objects.filter(
            filament_type=filament_type,
            filament_sub_type=filament_sub_type,
            color_code=color_code,
            brand=brand
        ).first()

        if color_match:
            return color_match

    # Try match without sub_type (more flexible)
    color_match = FilamentColor.objects.filter(
        filament_type=filament_type,
        color_code=color_code,
        brand=brand
    ).first()

    return color_match


def match_and_update_filament_color(filament_color):
    """
    Retroactively update all Filament spools that match this FilamentColor

    Returns:
        Number of Filament records updated
    """
    from .models import Filament

    query_filters = {
        'type': filament_color.filament_type,
        'brand': filament_color.brand,
    }

    color_hex = f"#{filament_color.color_code}"
    query_filters['color_hex'] = color_hex

    if filament_color.filament_sub_type:
        query_filters['sub_type'] = filament_color.filament_sub_type

    matching_filaments = Filament.objects.filter(**query_filters)
    updated_count = matching_filaments.update(color=filament_color.color_name)

    return updated_count

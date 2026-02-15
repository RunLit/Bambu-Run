"""
Utility functions for filament color matching
"""


def strip_color_padding(mqtt_color):
    """
    Strip FF padding from MQTT color
    MQTT: '000000FF' -> '000000'
    MQTT: 'FF6A13FF' -> 'FF6A13'
    """
    if not mqtt_color:
        return None
    if len(mqtt_color) == 8:
        return mqtt_color[:6].upper()
    return mqtt_color[:6].upper() if len(mqtt_color) >= 6 else mqtt_color.upper()


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

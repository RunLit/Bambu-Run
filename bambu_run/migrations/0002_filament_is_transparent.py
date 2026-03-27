from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("bambu_run", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="filamentcolor",
            name="is_transparent",
            field=models.BooleanField(
                default=False,
                help_text="True for clear/transparent filaments — display as checkerboard, not solid color",
            ),
        ),
        migrations.AddField(
            model_name="filament",
            name="is_transparent",
            field=models.BooleanField(
                default=False,
                help_text="True for clear/transparent filaments — display as checkerboard, not solid color",
            ),
        ),
    ]

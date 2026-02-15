from django import forms
from .models import Filament, FilamentColor, FilamentType


class FilamentTypeForm(forms.ModelForm):
    """Form for managing FilamentType registry"""

    PRESET_TYPES = ['PLA', 'PETG', 'PET', 'ABS', 'ASA', 'TPU', 'PA', 'PC', 'PPS']
    PRESET_SUB_TYPES = [
        'PLA Basic', 'PLA Matte', 'PLA Silk', 'PLA Metal', 'PLA Marble', 'PLA Glow', 'PLA-CF',
        'PETG Basic', 'PETG-CF', 'PETG-HF', 'ABS', 'TPU 95A', 'PA6-CF', 'ASA', 'PC', 'PPS-CF',
        'Support W', 'Support G',
    ]
    PRESET_BRANDS = [
        'Bambu Lab', 'eSUN', 'Polymaker', 'Hatchbox', 'Prusament',
        'MatterHackers', 'Overture', '3DXTech', 'ColorFabb',
    ]

    class Meta:
        model = FilamentType
        fields = ['type', 'sub_type', 'brand']
        widgets = {
            'type': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'e.g., PLA, PETG, ABS'
            }),
            'sub_type': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'e.g., PLA Basic, PLA Matte (optional)'
            }),
            'brand': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'e.g., Bambu Lab'
            }),
        }


class FilamentForm(forms.ModelForm):
    color_hex_text = forms.CharField(
        required=False,
        max_length=7,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': '#000000',
            'pattern': '#[0-9A-Fa-f]{6}',
            'id': 'id_color_hex_text'
        }),
        label='Color Hex Code'
    )

    class Meta:
        model = Filament
        fields = [
            'tray_uuid', 'tag_uid', 'tag_id', 'created_by',
            'filament_type', 'type', 'sub_type', 'brand', 'color', 'color_hex',
            'diameter', 'initial_weight_grams',
            'remaining_percent', 'remaining_weight_grams',
            'is_loaded_in_ams', 'current_tray_id',
            'purchase_date', 'purchase_price', 'supplier', 'notes'
        ]
        widgets = {
            'tray_uuid': forms.TextInput(attrs={
                'class': 'form-control font-monospace',
                'placeholder': 'Optional - Auto-filled by MQTT',
                'style': 'font-size: 0.9em;'
            }),
            'tag_uid': forms.TextInput(attrs={
                'class': 'form-control font-monospace',
                'placeholder': 'Optional - RFID chip ID',
                'style': 'font-size: 0.9em;'
            }),
            'tag_id': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Optional - User-defined ID'}),
            'created_by': forms.Select(attrs={'class': 'form-select'}),
            'filament_type': forms.Select(attrs={'class': 'form-select'}),
            'type': forms.HiddenInput(),
            'sub_type': forms.HiddenInput(),
            'brand': forms.HiddenInput(),
            'color': forms.Select(attrs={'class': 'form-select', 'id': 'id_color'}),
            'color_hex': forms.TextInput(attrs={
                'class': 'form-control',
                'type': 'color',
                'id': 'id_color_hex_picker'
            }),
            'diameter': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'initial_weight_grams': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': '1000'}),
            'remaining_percent': forms.NumberInput(attrs={'class': 'form-control', 'min': '0', 'max': '100'}),
            'remaining_weight_grams': forms.NumberInput(attrs={'class': 'form-control', 'readonly': 'readonly'}),
            'is_loaded_in_ams': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'current_tray_id': forms.NumberInput(attrs={'class': 'form-control', 'min': '0', 'max': '3'}),
            'purchase_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'purchase_price': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'supplier': forms.TextInput(attrs={'class': 'form-control'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.color_hex:
            self.fields['color_hex_text'].initial = self.instance.color_hex

        self.fields['filament_type'].queryset = FilamentType.objects.all()
        self.fields['filament_type'].empty_label = '--- Select Filament Type ---'
        self.fields['filament_type'].required = False

        self.fields['type'].required = False
        self.fields['sub_type'].required = False
        self.fields['brand'].required = False

        self._populate_color_choices()

    def _populate_color_choices(self):
        """Populate color field choices from FilamentColor database with suggested colors"""
        from .utils import strip_color_padding, match_filament_color

        color_choices = [('', '--- Select Color ---')]
        suggested_color = None

        all_colors = FilamentColor.objects.all().order_by('filament_type', 'filament_sub_type', 'color_name')

        if self.instance and self.instance.type and self.instance.color_hex:
            color_code = strip_color_padding(self.instance.color_hex.lstrip('#'))
            suggested = match_filament_color(
                filament_type=self.instance.type,
                filament_sub_type=self.instance.sub_type,
                color_code=color_code,
                brand=self.instance.brand or 'Bambu Lab'
            )
            if suggested:
                suggested_color = suggested

        if suggested_color:
            color_choices.append((
                suggested_color.color_name,
                f"SUGGESTED: {suggested_color.filament_sub_type or suggested_color.filament_type}: {suggested_color.color_name}"
            ))
            color_choices.append(('---separator---', '---' * 20))

        for color in all_colors:
            if suggested_color and color.pk == suggested_color.pk:
                continue

            display_name = f"{color.filament_sub_type or color.filament_type}: {color.color_name}"
            color_choices.append((color.color_name, display_name))

        color_choices.append(('---separator2---', '---' * 20))
        color_choices.append(('custom', 'Custom (type in manually)'))

        self.fields['color'].widget.choices = color_choices

    def clean(self):
        cleaned_data = super().clean()
        is_loaded = cleaned_data.get('is_loaded_in_ams')
        tray_id = cleaned_data.get('current_tray_id')

        color_hex_text = cleaned_data.get('color_hex_text')
        if color_hex_text:
            cleaned_data['color_hex'] = color_hex_text

        color = cleaned_data.get('color')
        if color and 'separator' in color:
            cleaned_data['color'] = ''

        ft = cleaned_data.get('filament_type')
        if ft:
            cleaned_data['type'] = ft.type
            cleaned_data['sub_type'] = ft.sub_type or ''
            cleaned_data['brand'] = ft.brand

        if is_loaded and tray_id is None:
            raise forms.ValidationError('Tray ID required when filament is loaded in AMS')

        return cleaned_data


class FilamentColorForm(forms.ModelForm):
    """Form for managing FilamentColor database"""

    color_code = forms.CharField(
        required=False,
        widget=forms.HiddenInput()
    )

    color_hex_input = forms.CharField(
        required=True,
        max_length=7,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': '#000000',
            'pattern': '#[0-9A-Fa-f]{6}',
        }),
        label='Color Hex Code'
    )

    class Meta:
        model = FilamentColor
        fields = ['color_code', 'color_name', 'filament_type_fk', 'filament_type', 'filament_sub_type', 'brand']
        widgets = {
            'color_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g., Black, Orange'}),
            'filament_type_fk': forms.Select(attrs={'class': 'form-select'}),
            'filament_type': forms.HiddenInput(),
            'filament_sub_type': forms.HiddenInput(),
            'brand': forms.HiddenInput(),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.color_code:
            self.fields['color_hex_input'].initial = f"#{self.instance.color_code}"

        self.fields['filament_type_fk'].queryset = FilamentType.objects.all()
        self.fields['filament_type_fk'].empty_label = '--- Select Filament Type ---'
        self.fields['filament_type_fk'].required = False

        self.fields['filament_type'].required = False
        self.fields['filament_sub_type'].required = False
        self.fields['brand'].required = False

    def clean(self):
        cleaned_data = super().clean()

        color_hex = cleaned_data.get('color_hex_input', '')
        if color_hex:
            color_code = color_hex.lstrip('#').upper()[:6]
            cleaned_data['color_code'] = color_code

        ft_fk = cleaned_data.get('filament_type_fk')
        if ft_fk:
            cleaned_data['filament_type'] = ft_fk.type
            cleaned_data['filament_sub_type'] = ft_fk.sub_type or ''
            cleaned_data['brand'] = ft_fk.brand

        return cleaned_data

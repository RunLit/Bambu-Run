from datetime import timedelta
from django.views.generic import TemplateView, View, ListView, CreateView, UpdateView, DetailView, DeleteView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.utils import timezone
from django.http import JsonResponse
from django.urls import reverse_lazy
from django.contrib import messages
from django.db.models import Q, Sum
import json
import zoneinfo

from .conf import app_settings
from .models import Printer, PrinterMetrics, Filament, FilamentColor, FilamentType, FilamentSnapshot, PrintJob, FilamentUsage
from .forms import FilamentForm, FilamentColorForm, FilamentTypeForm


class PrinterDashboardView(LoginRequiredMixin, TemplateView):
    template_name = "bambu_run/printer_dashboard.html"

    def _get_date_range(self, request):
        """Return (start_dt, end_dt) for the dashboard query. Override for custom date logic."""
        time_24h_ago = timezone.now() - timedelta(hours=24)
        return time_24h_ago, None  # None means "now"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['bambu_run_base_template'] = app_settings.BASE_TEMPLATE

        try:
            printer_device = Printer.objects.filter(is_active=True).first()
            if not printer_device:
                context["error"] = (
                    "No 3D printer device found. Please run bambu_collector first."
                )
                return context
        except Exception as e:
            context["error"] = f"Error loading printer device: {str(e)}"
            return context

        tz = zoneinfo.ZoneInfo(app_settings.TIMEZONE)

        # Get date range (overridable by subclasses)
        start_dt, end_dt = self._get_date_range(self.request)
        metrics = PrinterMetrics.objects.filter(
            device=printer_device, timestamp__gte=start_dt
        )
        if end_dt:
            metrics = metrics.filter(timestamp__lte=end_dt)
        metrics = metrics.prefetch_related('filament_snapshots').order_by("timestamp")

        latest_metric = metrics.last()

        printer_data_json = {
            "timestamps": [
                m.timestamp.astimezone(tz).strftime("%H:%M") for m in metrics
            ],
            "nozzle_temp": [
                float(m.nozzle_temp) if m.nozzle_temp else None for m in metrics
            ],
            "nozzle_target_temp": [
                float(m.nozzle_target_temp) if m.nozzle_target_temp else None
                for m in metrics
            ],
            "bed_temp": [float(m.bed_temp) if m.bed_temp else None for m in metrics],
            "bed_target_temp": [
                float(m.bed_target_temp) if m.bed_target_temp else None for m in metrics
            ],
            "print_percent": [
                m.print_percent if m.print_percent else 0 for m in metrics
            ],
            "print_type": [m.print_type for m in metrics],
            "gcode_state": [m.gcode_state for m in metrics],
            "cooling_fan_speed": [
                m.cooling_fan_speed if m.cooling_fan_speed else 0 for m in metrics
            ],
            "heatbreak_fan_speed": [
                m.heatbreak_fan_speed if m.heatbreak_fan_speed else 0 for m in metrics
            ],
            "wifi_signal_dbm": [
                m.wifi_signal_dbm if m.wifi_signal_dbm else None for m in metrics
            ],
            "ams_humidity_raw": [
                m.ams_humidity_raw if m.ams_humidity_raw else None for m in metrics
            ],
            "ams_temp": [
                float(m.ams_temp) if m.ams_temp else None for m in metrics
            ],
            "layer_num": [
                m.layer_num if m.layer_num else 0 for m in metrics
            ],
            "total_layer_num": [
                m.total_layer_num if m.total_layer_num else 0 for m in metrics
            ],
            "filament_timeline": self._prepare_filament_timeline(metrics),
        }

        stats = {}
        if latest_metric:
            filaments_list = []
            try:
                filament_snapshots = latest_metric.filament_snapshots.select_related('filament').all()
                for snapshot in filament_snapshots:
                    filament_dict = {
                        'tray_id': snapshot.tray_id,
                        'type': snapshot.type or 'Unknown',
                        'brand': snapshot.sub_type or 'Unknown',
                        'color': snapshot.color or 'FFFFFFFF',
                        'remain_percent': snapshot.remain_percent or 0,
                    }
                    if snapshot.filament:
                        filament_dict['color_name'] = snapshot.filament.color
                        filament_dict['filament_pk'] = snapshot.filament.pk
                    filaments_list.append(filament_dict)
            except Exception:
                filaments_list = []

            stats = {
                "nozzle_temp": float(latest_metric.nozzle_temp) if latest_metric.nozzle_temp else 0,
                "bed_temp": float(latest_metric.bed_temp) if latest_metric.bed_temp else 0,
                "chamber_temp": float(latest_metric.chamber_temp) if latest_metric.chamber_temp else 0,
                "print_percent": latest_metric.print_percent or 0,
                "gcode_state": latest_metric.gcode_state or "Unknown",
                "print_type": latest_metric.print_type or "idle",
                "subtask_name": latest_metric.subtask_name or "No active print",
                "chamber_light": latest_metric.chamber_light or "unknown",
                "ams_temp": float(latest_metric.ams_temp) if latest_metric.ams_temp else None,
                "ams_humidity": latest_metric.ams_humidity,
                "filaments": filaments_list,
                "external_spool": latest_metric.external_spool or {},
                "timestamp": latest_metric.timestamp.astimezone(tz).strftime("%Y-%m-%d %H:%M:%S"),
            }

        project_markers = self._calculate_project_markers(list(metrics), tz)
        printer_data_json["project_markers"] = project_markers

        context["printer_device"] = printer_device
        context["device_name"] = printer_device.name
        context["stats"] = stats
        context["metrics_count"] = metrics.count()
        context["printer_data_json"] = json.dumps(printer_data_json)

        return context

    def _calculate_project_markers(self, metrics, timezone_info):
        """Calculate where print jobs start and end"""
        markers = []
        current_job = None
        last_state = None

        for idx, metric in enumerate(metrics):
            subtask = metric.subtask_name
            gcode_state = metric.gcode_state

            is_printing = gcode_state not in ['FINISH', 'IDLE', None, '']

            if subtask and subtask != current_job and is_printing:
                markers.append({
                    'type': 'start',
                    'index': idx,
                    'timestamp': metric.timestamp.astimezone(timezone_info).isoformat(),
                    'project_name': subtask,
                })
                current_job = subtask
                last_state = gcode_state

            elif current_job and last_state and last_state not in ['FINISH', 'IDLE'] and gcode_state in ['FINISH', 'IDLE']:
                markers.append({
                    'type': 'end',
                    'index': idx,
                    'timestamp': metric.timestamp.astimezone(timezone_info).isoformat(),
                    'project_name': current_job,
                })
                current_job = None

            last_state = gcode_state

        return markers

    def _prepare_filament_timeline(self, metrics):
        """Prepare filament data organized by unique filament configurations."""
        filament_data = {}
        total_points = len(metrics)

        for idx, metric in enumerate(metrics):
            try:
                snapshots = metric.filament_snapshots.all()
            except Exception:
                snapshots = []

            for snapshot in snapshots:
                tray_id = snapshot.tray_id
                fil_type = snapshot.type or 'Unknown'
                fil_sub_type = snapshot.sub_type or 'Unknown'
                fil_color = snapshot.color or 'FFFFFFFF'

                unique_key = f"{tray_id}_{fil_type}_{fil_sub_type}_{fil_color}"

                if unique_key not in filament_data:
                    filament_data[unique_key] = {
                        'tray_id': tray_id,
                        'type': fil_type,
                        'brand': fil_sub_type,
                        'color': fil_color,
                        'remain_data': [None] * total_points,
                        'start_idx': idx,
                    }

                remain_percent = snapshot.remain_percent or 0
                filament_data[unique_key]['remain_data'][idx] = remain_percent

        for idx, metric in enumerate(metrics):
            external = metric.external_spool or {}
            if external.get('type'):
                fil_type = external.get('type', 'Unknown')
                fil_color = external.get('color', '161616FF')
                unique_key = f"External_{fil_type}_{fil_color}"

                if unique_key not in filament_data:
                    filament_data[unique_key] = {
                        'tray_id': 'External',
                        'type': fil_type,
                        'brand': 'External',
                        'color': fil_color,
                        'remain_data': [None] * total_points,
                        'start_idx': idx,
                    }

                remain_percent = external.get('remain', 0)
                filament_data[unique_key]['remain_data'][idx] = remain_percent

        return filament_data


class PrinterDataAPIView(LoginRequiredMixin, View):
    """API endpoint for dynamic printer chart updates"""

    def get(self, request):
        start_date = request.GET.get("start_date")
        end_date = request.GET.get("end_date")
        start_time = request.GET.get("start_time", "00:00")
        end_time = request.GET.get("end_time", "23:59")

        try:
            printer_device = Printer.objects.filter(is_active=True).first()
            if not printer_device:
                return JsonResponse({"error": "No printer device found"}, status=404)

            query = PrinterMetrics.objects.filter(device=printer_device).prefetch_related('filament_snapshots')

            tz = zoneinfo.ZoneInfo(app_settings.TIMEZONE)

            if start_date and start_time:
                from datetime import datetime
                start_dt_naive = datetime.strptime(f"{start_date} {start_time}", "%Y-%m-%d %H:%M")
                start_dt = start_dt_naive.replace(tzinfo=tz)
                query = query.filter(timestamp__gte=start_dt)

            if end_date and end_time:
                from datetime import datetime
                end_dt_naive = datetime.strptime(f"{end_date} {end_time}", "%Y-%m-%d %H:%M")
                end_dt = end_dt_naive.replace(tzinfo=tz)
                query = query.filter(timestamp__lte=end_dt)

            metrics = query.order_by("timestamp")

            data = {
                "timestamps": [m.timestamp.astimezone(tz).strftime('%H:%M') for m in metrics],
                "timestamps_iso": [m.timestamp.astimezone(tz).isoformat() for m in metrics],
                "nozzle_temp": [float(m.nozzle_temp) if m.nozzle_temp else None for m in metrics],
                "nozzle_target_temp": [float(m.nozzle_target_temp) if m.nozzle_target_temp else None for m in metrics],
                "bed_temp": [float(m.bed_temp) if m.bed_temp else None for m in metrics],
                "bed_target_temp": [float(m.bed_target_temp) if m.bed_target_temp else None for m in metrics],
                "print_percent": [m.print_percent if m.print_percent else 0 for m in metrics],
                "cooling_fan_speed": [m.cooling_fan_speed if m.cooling_fan_speed else 0 for m in metrics],
                "heatbreak_fan_speed": [m.heatbreak_fan_speed if m.heatbreak_fan_speed else 0 for m in metrics],
                "wifi_signal_dbm": [m.wifi_signal_dbm if m.wifi_signal_dbm else None for m in metrics],
                "ams_humidity_raw": [m.ams_humidity_raw if m.ams_humidity_raw else None for m in metrics],
                "ams_temp": [float(m.ams_temp) if m.ams_temp else None for m in metrics],
                "layer_num": [m.layer_num if m.layer_num else 0 for m in metrics],
                "total_layer_num": [m.total_layer_num if m.total_layer_num else 0 for m in metrics],
                "gcode_state": [m.gcode_state for m in metrics],
                "print_type": [m.print_type for m in metrics],
                "subtask_name": [m.subtask_name for m in metrics],
            }

            project_markers = self._calculate_project_markers(metrics, tz)
            data["project_markers"] = project_markers

            filament_timeline = self._prepare_filament_timeline_for_api(metrics)
            data["filament_timeline"] = filament_timeline

            return JsonResponse(data)

        except Exception as e:
            import traceback
            traceback.print_exc()
            return JsonResponse({"error": str(e)}, status=500)

    def _calculate_project_markers(self, metrics, timezone_info):
        markers = []
        current_job = None
        last_state = None

        for idx, metric in enumerate(metrics):
            subtask = metric.subtask_name
            gcode_state = metric.gcode_state

            is_printing = gcode_state not in ['FINISH', 'IDLE', None, '']

            if subtask and subtask != current_job and is_printing:
                markers.append({
                    'type': 'start',
                    'index': idx,
                    'timestamp': metric.timestamp.astimezone(timezone_info).isoformat(),
                    'project_name': subtask,
                })
                current_job = subtask
                last_state = gcode_state

            elif current_job and last_state and last_state not in ['FINISH', 'IDLE'] and gcode_state in ['FINISH', 'IDLE']:
                markers.append({
                    'type': 'end',
                    'index': idx,
                    'timestamp': metric.timestamp.astimezone(timezone_info).isoformat(),
                    'project_name': current_job,
                })
                current_job = None

            last_state = gcode_state

        return markers

    def _prepare_filament_timeline_for_api(self, metrics):
        filament_data = {}
        total_points = len(metrics)

        for idx, metric in enumerate(metrics):
            try:
                snapshots = metric.filament_snapshots.all()
            except Exception:
                snapshots = []

            for snapshot in snapshots:
                tray_id = snapshot.tray_id
                fil_type = snapshot.type or 'Unknown'
                fil_sub_type = snapshot.sub_type or 'Unknown'
                fil_color = snapshot.color or 'FFFFFFFF'

                unique_key = f"{tray_id}_{fil_type}_{fil_sub_type}_{fil_color}"

                if unique_key not in filament_data:
                    filament_data[unique_key] = {
                        'tray_id': tray_id,
                        'type': fil_type,
                        'brand': fil_sub_type,
                        'color': fil_color,
                        'remain_data': [None] * total_points,
                        'start_idx': idx,
                    }

                remain_percent = snapshot.remain_percent or 0
                filament_data[unique_key]['remain_data'][idx] = remain_percent

        for idx, metric in enumerate(metrics):
            external = metric.external_spool or {}
            if external.get('type'):
                fil_type = external.get('type', 'Unknown')
                fil_color = external.get('color', '161616FF')
                unique_key = f"External_{fil_type}_{fil_color}"

                if unique_key not in filament_data:
                    filament_data[unique_key] = {
                        'tray_id': 'External',
                        'type': fil_type,
                        'brand': 'External',
                        'color': fil_color,
                        'remain_data': [None] * total_points,
                        'start_idx': idx,
                    }

                remain_percent = external.get('remain', 0)
                filament_data[unique_key]['remain_data'][idx] = remain_percent

        return filament_data


class FilamentUsageDataAPIView(LoginRequiredMixin, View):
    """API endpoint for filament usage history with date/time filtering"""

    def get(self, request, pk):
        start_date = request.GET.get("start_date")
        end_date = request.GET.get("end_date")
        start_time = request.GET.get("start_time", "00:00")
        end_time = request.GET.get("end_time", "23:59")

        try:
            filament = Filament.objects.get(pk=pk)
            tz = zoneinfo.ZoneInfo(app_settings.TIMEZONE)
            query = filament.usage_snapshots.select_related('printer_metric')

            if start_date and start_time:
                from datetime import datetime
                start_dt_naive = datetime.strptime(f"{start_date} {start_time}", "%Y-%m-%d %H:%M")
                start_dt = start_dt_naive.replace(tzinfo=tz)
                query = query.filter(printer_metric__timestamp__gte=start_dt)

            if end_date and end_time:
                from datetime import datetime
                end_dt_naive = datetime.strptime(f"{end_date} {end_time}", "%Y-%m-%d %H:%M")
                end_dt = end_dt_naive.replace(tzinfo=tz)
                query = query.filter(printer_metric__timestamp__lte=end_dt)

            if not start_date and not end_date:
                time_24h_ago = timezone.now() - timedelta(hours=24)
                query = query.filter(printer_metric__timestamp__gte=time_24h_ago)

            snapshots = query.order_by('printer_metric__timestamp')

            data = {
                "timestamps": [s.printer_metric.timestamp.astimezone(tz).strftime('%Y-%m-%d %H:%M') for s in snapshots],
                "remaining": [s.remain_percent for s in snapshots]
            }

            return JsonResponse(data)

        except Filament.DoesNotExist:
            return JsonResponse({"error": "Filament not found"}, status=404)
        except Exception as e:
            import traceback
            traceback.print_exc()
            return JsonResponse({"error": str(e)}, status=500)


# ==================== Filament CRUD Views ====================

class FilamentListView(LoginRequiredMixin, ListView):
    model = Filament
    template_name = 'bambu_run/filament_list.html'
    context_object_name = 'filaments'
    paginate_by = 20

    def get_queryset(self):
        queryset = Filament.objects.all()

        filament_type = self.request.GET.get('type')
        if filament_type:
            queryset = queryset.filter(type=filament_type)

        loaded = self.request.GET.get('loaded')
        if loaded == 'yes':
            queryset = queryset.filter(is_loaded_in_ams=True)
        elif loaded == 'no':
            queryset = queryset.filter(is_loaded_in_ams=False)

        search = self.request.GET.get('search')
        if search:
            queryset = queryset.filter(
                Q(brand__icontains=search) |
                Q(color__icontains=search) |
                Q(type__icontains=search)
            )

        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['bambu_run_base_template'] = app_settings.BASE_TEMPLATE
        context['total_spools'] = Filament.objects.count()
        context['loaded_spools'] = Filament.objects.filter(is_loaded_in_ams=True).count()
        context['low_filaments'] = Filament.objects.filter(remaining_percent__lt=20).count()
        context['filament_types'] = sorted(
            set(Filament.objects.exclude(type__isnull=True).exclude(type='').values_list('type', flat=True))
        )
        return context


class FilamentCreateView(LoginRequiredMixin, CreateView):
    model = Filament
    form_class = FilamentForm
    template_name = 'bambu_run/filament_form.html'
    success_url = reverse_lazy('bambu_run:filament_list')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['bambu_run_base_template'] = app_settings.BASE_TEMPLATE
        return context

    def form_valid(self, form):
        messages.success(self.request, f'Filament spool "{form.instance}" added successfully!')
        return super().form_valid(form)


class FilamentUpdateView(LoginRequiredMixin, UpdateView):
    model = Filament
    form_class = FilamentForm
    template_name = 'bambu_run/filament_form.html'
    success_url = reverse_lazy('bambu_run:filament_list')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['bambu_run_base_template'] = app_settings.BASE_TEMPLATE
        return context

    def form_valid(self, form):
        messages.success(self.request, f'Filament spool "{form.instance}" updated successfully!')
        return super().form_valid(form)


class FilamentDeleteView(LoginRequiredMixin, DeleteView):
    model = Filament
    template_name = 'bambu_run/filament_confirm_delete.html'
    success_url = reverse_lazy('bambu_run:filament_list')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['bambu_run_base_template'] = app_settings.BASE_TEMPLATE
        return context

    def delete(self, request, *args, **kwargs):
        filament = self.get_object()
        messages.success(self.request, f'Filament spool "{filament}" has been deleted.')
        return super().delete(request, *args, **kwargs)


class FilamentDetailView(LoginRequiredMixin, DetailView):
    model = Filament
    template_name = 'bambu_run/filament_detail.html'
    context_object_name = 'filament'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['bambu_run_base_template'] = app_settings.BASE_TEMPLATE
        filament = self.object

        context['print_usages'] = filament.print_usages.select_related('print_job').order_by('-print_job__start_time')[:20]

        total_consumed = filament.print_usages.aggregate(
            total=Sum('consumed_percent')
        )['total'] or 0
        context['total_consumed_percent'] = total_consumed

        return context


# ==================== FilamentColor Views ====================

class FilamentColorListView(LoginRequiredMixin, ListView):
    model = FilamentColor
    template_name = 'bambu_run/filament_color_list.html'
    context_object_name = 'colors'
    paginate_by = 50

    def get_queryset(self):
        return FilamentColor.objects.all().order_by('filament_type', 'filament_sub_type', 'color_name')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['bambu_run_base_template'] = app_settings.BASE_TEMPLATE
        context['total_colors'] = FilamentColor.objects.count()
        return context


class FilamentColorCreateView(LoginRequiredMixin, CreateView):
    model = FilamentColor
    form_class = FilamentColorForm
    template_name = 'bambu_run/filament_color_form.html'
    success_url = reverse_lazy('bambu_run:filament_color_list')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['bambu_run_base_template'] = app_settings.BASE_TEMPLATE
        return context

    def form_valid(self, form):
        response = super().form_valid(form)
        self._update_matching_filaments(self.object)
        return response

    def _update_matching_filaments(self, filament_color):
        from .utils import match_and_update_filament_color
        updated_count = match_and_update_filament_color(filament_color)
        if updated_count > 0:
            messages.success(
                self.request,
                f"Color '{filament_color.color_name}' created! "
                f"Updated {updated_count} matching filament spool(s)."
            )


class FilamentColorUpdateView(LoginRequiredMixin, UpdateView):
    model = FilamentColor
    form_class = FilamentColorForm
    template_name = 'bambu_run/filament_color_form.html'
    success_url = reverse_lazy('bambu_run:filament_color_list')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['bambu_run_base_template'] = app_settings.BASE_TEMPLATE
        return context

    def form_valid(self, form):
        response = super().form_valid(form)
        self._update_matching_filaments(self.object)
        return response

    def _update_matching_filaments(self, filament_color):
        from .utils import match_and_update_filament_color
        updated_count = match_and_update_filament_color(filament_color)
        if updated_count > 0:
            messages.success(
                self.request,
                f"Color '{filament_color.color_name}' updated! "
                f"Updated {updated_count} matching filament spool(s)."
            )


class FilamentColorDeleteView(LoginRequiredMixin, DeleteView):
    model = FilamentColor
    template_name = 'bambu_run/filament_color_confirm_delete.html'
    success_url = reverse_lazy('bambu_run:filament_color_list')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['bambu_run_base_template'] = app_settings.BASE_TEMPLATE
        return context

    def delete(self, request, *args, **kwargs):
        messages.success(request, f"Color '{self.get_object().color_name}' deleted successfully!")
        return super().delete(request, *args, **kwargs)


# ==================== FilamentType Views ====================

class FilamentTypeListView(LoginRequiredMixin, ListView):
    model = FilamentType
    template_name = 'bambu_run/filament_type_list.html'
    context_object_name = 'types'
    paginate_by = 50

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['bambu_run_base_template'] = app_settings.BASE_TEMPLATE
        context['total_types'] = FilamentType.objects.count()
        return context


class FilamentTypeCreateView(LoginRequiredMixin, CreateView):
    model = FilamentType
    form_class = FilamentTypeForm
    template_name = 'bambu_run/filament_type_form.html'
    success_url = reverse_lazy('bambu_run:filament_type_list')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['bambu_run_base_template'] = app_settings.BASE_TEMPLATE
        context['existing_types'] = list(
            FilamentType.objects.values_list('type', flat=True).distinct().order_by('type')
        )
        context['existing_sub_types'] = list(
            FilamentType.objects.exclude(sub_type__isnull=True).exclude(sub_type='')
            .values_list('sub_type', flat=True).distinct().order_by('sub_type')
        )
        context['existing_brands'] = list(
            FilamentType.objects.values_list('brand', flat=True).distinct().order_by('brand')
        )
        context['preset_types'] = FilamentTypeForm.PRESET_TYPES
        context['preset_sub_types'] = FilamentTypeForm.PRESET_SUB_TYPES
        context['preset_brands'] = FilamentTypeForm.PRESET_BRANDS
        return context

    def form_valid(self, form):
        messages.success(self.request, f'Filament type "{form.instance}" added successfully!')
        return super().form_valid(form)


class FilamentTypeUpdateView(LoginRequiredMixin, UpdateView):
    model = FilamentType
    form_class = FilamentTypeForm
    template_name = 'bambu_run/filament_type_form.html'
    success_url = reverse_lazy('bambu_run:filament_type_list')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['bambu_run_base_template'] = app_settings.BASE_TEMPLATE
        context['existing_types'] = list(
            FilamentType.objects.values_list('type', flat=True).distinct().order_by('type')
        )
        context['existing_sub_types'] = list(
            FilamentType.objects.exclude(sub_type__isnull=True).exclude(sub_type='')
            .values_list('sub_type', flat=True).distinct().order_by('sub_type')
        )
        context['existing_brands'] = list(
            FilamentType.objects.values_list('brand', flat=True).distinct().order_by('brand')
        )
        context['preset_types'] = FilamentTypeForm.PRESET_TYPES
        context['preset_sub_types'] = FilamentTypeForm.PRESET_SUB_TYPES
        context['preset_brands'] = FilamentTypeForm.PRESET_BRANDS
        return context

    def form_valid(self, form):
        messages.success(self.request, f'Filament type "{form.instance}" updated successfully!')
        return super().form_valid(form)


class FilamentTypeDeleteView(LoginRequiredMixin, DeleteView):
    model = FilamentType
    template_name = 'bambu_run/filament_type_confirm_delete.html'
    success_url = reverse_lazy('bambu_run:filament_type_list')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['bambu_run_base_template'] = app_settings.BASE_TEMPLATE
        return context

    def delete(self, request, *args, **kwargs):
        messages.success(request, f"Filament type '{self.get_object()}' deleted successfully!")
        return super().delete(request, *args, **kwargs)

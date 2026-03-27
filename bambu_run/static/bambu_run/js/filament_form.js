/**
 * filament_form.js — Filament add/edit form interactions.
 *
 * Handles:
 *   - Filament type preset → auto-fill Type / Sub Type / Brand
 *   - Transparent checkbox → toggle color picker vs. checkerboard swatch
 *   - Color picker ↔ hex text sync
 *   - Delete confirmation modal
 */

document.addEventListener('DOMContentLoaded', function () {

    // ── Filament type preset auto-fill ────────────────────────────────────────

    const dataEl = document.getElementById('filament-type-data');
    const filamentTypeMap = dataEl ? JSON.parse(dataEl.textContent) : {};

    const filamentTypeSelect = document.getElementById('id_filament_type');
    const typeField    = document.getElementById('id_type');
    const subTypeField = document.getElementById('id_sub_type');
    const brandField   = document.getElementById('id_brand');

    if (filamentTypeSelect) {
        filamentTypeSelect.addEventListener('change', function () {
            const mapping = filamentTypeMap[this.value];
            if (mapping && typeField && subTypeField && brandField) {
                typeField.value    = mapping.type;
                subTypeField.value = mapping.sub_type;
                brandField.value   = mapping.brand;
            }
        });
    }

    // ── Transparent toggle ────────────────────────────────────────────────────

    const transparentCheckbox = document.getElementById('id_is_transparent');
    const transparentSwatch   = document.getElementById('transparent-swatch');
    const colorPicker         = document.getElementById('id_color_hex_picker');
    const colorText           = document.getElementById('id_color_hex_text');

    /**
     * Show checkerboard swatch and disable color inputs when transparent,
     * restore normal color picker when not transparent.
     * @param {boolean} isTransparent
     */
    function applyTransparentState(isTransparent) {
        if (!colorPicker) return;
        if (isTransparent) {
            transparentSwatch.style.display = 'block';
            colorPicker.style.display       = 'none';
            colorPicker.disabled            = true;
            if (colorText) { colorText.disabled = true; colorText.value = ''; }
        } else {
            transparentSwatch.style.display = 'none';
            colorPicker.style.display       = '';
            colorPicker.disabled            = false;
            if (colorText) { colorText.disabled = false; }
        }
    }

    if (transparentCheckbox) {
        applyTransparentState(transparentCheckbox.checked);
        transparentCheckbox.addEventListener('change', function () {
            applyTransparentState(this.checked);
        });
    }

    // ── Color picker ↔ hex text sync ──────────────────────────────────────────

    if (colorPicker && colorText) {
        colorPicker.addEventListener('input', function () {
            colorText.value = this.value.toUpperCase();
        });

        colorText.addEventListener('input', function () {
            const value = this.value.trim();
            if (/^#[0-9A-Fa-f]{6}$/.test(value)) {
                colorPicker.value = value;
                this.classList.remove('is-invalid');
            } else if (value.length === 7) {
                this.classList.add('is-invalid');
            }
        });

        if (colorText.value && /^#[0-9A-Fa-f]{6}$/.test(colorText.value)) {
            colorPicker.value = colorText.value;
        } else if (colorPicker.value && !colorText.value) {
            colorText.value = colorPicker.value.toUpperCase();
        }
    }

    // ── Delete confirmation modal ─────────────────────────────────────────────

    const deleteConfirmText = document.getElementById('deleteConfirmText');
    const confirmDeleteBtn  = document.getElementById('confirmDeleteBtn');
    const deleteForm        = document.getElementById('deleteForm');
    const deleteModal       = document.getElementById('deleteModal');

    if (deleteConfirmText && confirmDeleteBtn) {
        deleteConfirmText.addEventListener('input', function () {
            const value = this.value.trim();
            if (value === 'DELETE') {
                confirmDeleteBtn.disabled = false;
                this.classList.remove('is-invalid');
                this.classList.add('is-valid');
            } else {
                confirmDeleteBtn.disabled = true;
                this.classList.remove('is-valid');
                if (value.length > 0) {
                    this.classList.add('is-invalid');
                } else {
                    this.classList.remove('is-invalid');
                }
            }
        });

        if (deleteForm) {
            deleteForm.addEventListener('submit', function (e) {
                if (confirmDeleteBtn.disabled) {
                    e.preventDefault();
                    alert('Please type DELETE to confirm deletion');
                    return false;
                }
                return true;
            });
        }

        if (deleteModal) {
            deleteModal.addEventListener('hidden.bs.modal', function () {
                deleteConfirmText.value = '';
                confirmDeleteBtn.disabled = true;
                deleteConfirmText.classList.remove('is-valid', 'is-invalid');
            });

            deleteModal.addEventListener('shown.bs.modal', function () {
                deleteConfirmText.focus();
            });
        }
    }

    // ── Delete button modal opener (backup) ───────────────────────────────────

    const deleteBtn = document.getElementById('deleteBtn');
    if (deleteBtn && deleteModal) {
        deleteBtn.addEventListener('click', function () {
            if (!deleteModal.classList.contains('show')) {
                if (typeof bootstrap !== 'undefined') {
                    bootstrap.Modal.getOrCreateInstance(deleteModal).show();
                } else if (typeof coreui !== 'undefined' && coreui.Modal) {
                    coreui.Modal.getOrCreateInstance(deleteModal).show();
                }
            }
        });
    }

});

/**
 * Dropdown-assisted text inputs for FilamentType add/edit form.
 * Reads existing DB values and preset suggestions from json_script tags,
 * then populates dropdown menus that fill the adjacent text input on click.
 */

/**
 * Build a dropdown menu with existing DB values and preset suggestions.
 * @param {string} dropdownId - ID of the <ul> dropdown menu element
 * @param {string} inputId - ID of the text input to fill on click
 * @param {Array<string>} existingValues - Values already in the database
 * @param {Array<string>} presetValues - Pre-coded suggestion values
 */
function buildDropdown(dropdownId, inputId, existingValues, presetValues) {
    const menu = document.getElementById(dropdownId);

    // Add existing DB values
    existingValues.forEach(val => {
        const li = document.createElement('li');
        li.innerHTML = `<a class="dropdown-item" href="#">${val}</a>`;
        li.querySelector('a').addEventListener('click', e => {
            e.preventDefault();
            document.getElementById(inputId).value = val;
        });
        menu.appendChild(li);
    });

    // Add dotted separator if there were DB values
    if (existingValues.length > 0) {
        const sep = document.createElement('li');
        sep.innerHTML = '<hr class="dropdown-divider" style="border-style: dotted;">';
        menu.appendChild(sep);
    }

    // Add preset values (skip duplicates already in DB)
    const existingSet = new Set(existingValues);
    presetValues.forEach(val => {
        if (existingSet.has(val)) return;
        const li = document.createElement('li');
        li.innerHTML = `<a class="dropdown-item text-muted" href="#">${val}</a>`;
        li.querySelector('a').addEventListener('click', e => {
            e.preventDefault();
            document.getElementById(inputId).value = val;
        });
        menu.appendChild(li);
    });
}

// Parse data from json_script tags and build all three dropdowns
document.addEventListener('DOMContentLoaded', () => {
    const existingTypes = JSON.parse(document.getElementById('existing-types').textContent);
    const existingSubTypes = JSON.parse(document.getElementById('existing-sub-types').textContent);
    const existingBrands = JSON.parse(document.getElementById('existing-brands').textContent);
    const presetTypes = JSON.parse(document.getElementById('preset-types').textContent);
    const presetSubTypes = JSON.parse(document.getElementById('preset-sub-types').textContent);
    const presetBrands = JSON.parse(document.getElementById('preset-brands').textContent);

    buildDropdown('type-dropdown', 'id_type', existingTypes, presetTypes);
    buildDropdown('sub-type-dropdown', 'id_sub_type', existingSubTypes, presetSubTypes);
    buildDropdown('brand-dropdown', 'id_brand', existingBrands, presetBrands);
});

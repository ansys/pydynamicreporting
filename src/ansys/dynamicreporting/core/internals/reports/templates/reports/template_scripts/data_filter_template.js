const TAG_FILTER_KEY = 'tag';
const SINGLE_TAG_FILTER_KEY = 'single-tag';
const X_FILTER_KEY = 'plot_range_x';
const Y_FILTER_KEY = 'plot_range_y';

// TODO: update selectors when ID generation is fixed
const parent_container_id = '{{ parent_container_id }}'.split('_')[0];
const parent_container_selector = `div[nexus_template="${parent_container_id}"]`;
const targetElement = $(document.querySelector(`${parent_container_selector} .nexus-plot`) ||
                        document.querySelector(`${parent_container_selector} .dataTables_wrapper`));

let filtersMap = new Map();

filtersMap.set(TAG_FILTER_KEY, new Map());
filtersMap.set(SINGLE_TAG_FILTER_KEY, new Map());
filtersMap.set(X_FILTER_KEY, new Map());
filtersMap.set(Y_FILTER_KEY, new Map());

let filterClearEvents = new Map();

function addFilterChip(key, name, title, closeEvent) {
    if (filterClearEvents.size >= 1) {
        let closeAllFiltersSelector = `${parent_container_selector} #close-all-filters`;
        $(closeAllFiltersSelector).addClass('show');
        $(closeAllFiltersSelector).on('click', () => {
            filterClearEvents.forEach((closeEvent, filterName) => {
                closeEvent();
                removeFilterChip(key, filterName);
            })
        });
    }

    let filterChipElement = `<div id="filter-chip-${key}" class="filter-chip"` +
        `data-toggle="tooltip" title="${title}">` +
        `${name}<i class="fas fa-times">` +
        '</i></div>';

    $(`${parent_container_selector} #filter-chips`).append(filterChipElement);
    $(`${parent_container_selector} #filter-chip-${key} i`).on('click', closeEvent);

    filterClearEvents.set(name, closeEvent);
}

function removeFilterChip(key, filterName) {
    $(`${parent_container_selector} #filter-chip-${key}`).remove();

    filterClearEvents.delete(filterName);

    if (filterClearEvents.size <= 1) {
        $(`${parent_container_selector} #close-all-filters`).removeClass('show');
    }
}

// toggle sidebar
$(`${parent_container_selector} #filter-header`).on('click', (clickEvt) => {
    $(`${parent_container_selector} #accordion`).toggleClass('show');
    window.dispatchEvent(new Event('resize'));
});

{% for key, filter in filters.items %}
    {% if filter.type == 'slider' %}
        /**
         * Slider filter
         * Template fields:
         *   name: string
         *   type: 'slider'
         *   event_type: 'plot_range_x'|'plot_range_y'|'tag'
         *   min: number
         *   max: number
         *   step: number
         * Event object:
         *   min: number
         *   max: number
         */
        let slider_bar_{{ key }} = $('#slider_bar_{{ key }}_{{ parent_container_id }}');
        let slider_bar_{{ key }}_left_value = $('#left-value-{{ key }}_{{ parent_container_id }}');
        let slider_bar_{{ key }}_right_value = $('#right-value-{{ key }}_{{ parent_container_id }}');

        let slider_{{ key }} = $('#slider_bar_{{ key }}_{{ parent_container_id }}').slider({
            min: {{ filter.min }},
            max: {{ filter.max }},
            value: [({{ filter.min }}), ({{ filter.max }})],
            step: {{ filter.step }},
            ticks: {{ filter.step }},
            selection: 'after',
            tooltip: 'hide'
        });

        $(slider_bar_{{ key }}).on('change', (changeEvt) => {
            $(slider_bar_{{ key }}_left_value).text(changeEvt.value.newValue[0].toFixed(1));
            $(slider_bar_{{ key }}_right_value).text(changeEvt.value.newValue[1].toFixed(1));
        });

        $(slider_bar_{{ key }}).on('change', function (e) {
            let [leftValue, rightValue] = slider_{{ key }}.slider('getValue');
            let filterApplied = leftValue !== {{ filter.min }} || rightValue !== {{ filter.max }};

            removeFilterChip('{{ key }}', '{{ filter.name }}');

            filtersMap.get('{{ filter.event_type }}').set('{{ filter.name }}', {
                min: leftValue,
                max: rightValue
            });

            if (filterApplied) {
                let title = `${leftValue} - ${rightValue}`;
                let closeEvent = () => {
                    slider_{{ key }}.slider('refresh');

                    removeFilterChip('{{ key }}', '{{ filter.name }}');

                    $(slider_bar_{{ key }}_left_value).text(({{ filter.min }}).toFixed(1));
                    $(slider_bar_{{ key }}_right_value).text(({{ filter.max }}).toFixed(1));

                    filtersMap.get('{{ filter.event_type }}').delete('{{ filter.name }}');

                    targetElement[0].dispatchEvent(new CustomEvent('filter_event', {
                        detail: filtersMap
                    }));
                };

                addFilterChip('{{ key }}', '{{ filter.name }}', title, closeEvent);
            } else {
                filtersMap.get('{{ filter.event_type }}').delete('{{ filter.name }}');
            }

            targetElement[0].dispatchEvent(new CustomEvent('filter_event', {
                detail: filtersMap
            }));
        });
    {% elif filter.type == 'dropdown' %}
        /**
         * Dropdown filter
         * Template fields:
         *   name: string
         *   type: 'dropdown'
         *   event_type: 'plot_range_x'|'plot_range_y'|'tag'
         *   values: [number]
         * Event object:
         *   min: number
         *   max: number
         */
        let range_select_min_{{ key }} = $('#range-select-min-{{ key }}_{{ parent_container_id }}');
        let range_select_max_{{ key }} = $('#range-select-max-{{ key }}_{{ parent_container_id }}');

        $(`${parent_container_selector} .range-dropdown`).on('change', (event) => {
            let min_value = parseFloat(range_select_min_{{ key }}.prop('value'));
            let max_value = parseFloat(range_select_max_{{ key }}.prop('value'));

            removeFilterChip('{{ key }}', '{{ filter.name }}');

            if (min_value !== {{ filter.min }} || max_value !== {{ filter.max }}) {
                filtersMap.get('{{ filter.event_type }}').set('{{ filter.name }}', {
                    min: min_value,
                    max: max_value
                });

                let title = `${min_value} - ${max_value}`;
                let closeEvent = () => {
                    let filter_min = range_select_min_{{ key }}.find('option:first').val();
                    let filter_max = range_select_max_{{ key }}.find('option:last').val();

                    removeFilterChip('{{ key }}', '{{ filter.name }}');

                    range_select_min_{{ key }}.val(filter_min);
                    range_select_max_{{ key }}.val(filter_max);

                    $('#range-filter-{{ key }}_{{ parent_container_id }}').find('option.hidden').each((index, element) => {
                        $(element).removeClass('hidden');
                    });

                    filtersMap.get('{{ filter.event_type }}').delete('{{ filter.name }}');

                    targetElement[0].dispatchEvent(new CustomEvent('filter_event', {
                        detail: filtersMap
                    }));
                };

                addFilterChip('{{ key }}', '{{ filter.name }}', title, closeEvent);
            } else {
                filtersMap.get('{{ filter.event_type }}').delete('{{ filter.name }}');
            }

            targetElement[0].dispatchEvent(new CustomEvent('filter_event', {
                detail: filtersMap
            }));

            if ($(event.target).attr('id') === range_select_min_{{ key }}.attr('id')) {
                range_select_max_{{ key }}.find('option.hidden').each((index, element) => {
                    $(element).removeClass('hidden');
                });

                if (min_value !== {{ filter.min }}) {
                    range_select_max_{{ key }}.find('option').each((index, element) => {
                        let value = parseFloat($(element).prop('value'));
                        if (value <= min_value) {
                            $(element).addClass('hidden');
                        }
                    });
                }
            } else if ($(event.target).attr('id') === range_select_max_{{ key }}.attr('id')) {
                range_select_min_{{ key }}.find('option.hidden').each((index, element) => {
                    $(element).removeClass('hidden');
                });

                if (max_value !== {{ filter.max }}) {
                    range_select_min_{{ key }}.find('option').each((index, element) => {
                        let value = parseFloat($(element).prop('value'));
                        if (value >= max_value) {
                            $(element).addClass('hidden');
                        }
                    });
                }
            }
        });
    {% elif filter.type == 'input' %}
        /**
         * Number input filter
         * Template fields:
         *   name: string
         *   type: 'input'
         *   event_type: 'plot_range_x'|'plot_range_y'|'tag'
         *   min: number
         *   max: number
         *   step: number
         * Event object:
         *   min: number
         *   max: number
         */
        let range_input_min_{{ key }} = $('#range-input-min-{{ key }}_{{ parent_container_id }}');
        let range_input_max_{{ key }} = $('#range-input-max-{{ key }}_{{ parent_container_id }}');

        $(`${parent_container_selector} .range-input`).on('change', function(event) {
            let min_value = parseFloat(range_input_min_{{ key }}.prop('value'));
            let max_value = parseFloat(range_input_max_{{ key }}.prop('value'));

            if (min_value >= max_value) {
                if ($(this).is(range_input_min_{{ key }})) {
                    min_value = max_value - {{ filter.step }};
                    $(this).val(min_value);
                } else {
                    max_value = min_value + {{ filter.step }};
                    $(this).val(max_value);
                }
            }

            removeFilterChip('{{ key }}', '{{ filter.name }}');

            filtersMap.get('{{ filter.event_type }}').set('{{ filter.name }}', {
                min: min_value,
                max: max_value
            });

            if (min_value !== parseFloat({{ filter.min }}) || max_value !== parseFloat({{ filter.max }}) ) {
                let title = `${min_value} - ${max_value}`;
                let closeEvent = () => {
                    removeFilterChip('{{ key }}', '{{ filter.name }}');

                    range_input_min_{{ key }}.val({{ filter.min }});
                    range_input_max_{{ key }}.val({{ filter.max }});

                    $('#range-filter-{{ key }}_{{ parent_container_id }}').find('option.hidden').each((index, element) => {
                        $(element).removeClass('hidden');
                    });

                    filtersMap.get('{{ filter.event_type }}').delete('{{ filter.name }}');

                    targetElement[0].dispatchEvent(new CustomEvent('filter_event', {
                        detail: filtersMap
                    }));
                };

                addFilterChip('{{ key }}', '{{ filter.name }}', title, closeEvent);
            }

            targetElement[0].dispatchEvent(new CustomEvent('filter_event', {
                detail: filtersMap
            }));
        });
    {% elif filter.type == 'checkbox' %}
        /**
         * Checkbox filter
         * Template fields:
         *   name: string
         *   type: 'checkbox'
         *   event_type: 'tag'
         *   values: [string]
         * Event object:
         *   [string]
         */
        $(`${parent_container_selector} #checkbox-form-{{ key }}-container .select-all`).on('click', () => {
            $(`${parent_container_selector} #checkbox-form-{{ key }}-container`).find('input').prop('checked', true);
            $(`${parent_container_selector} #checkbox-form-{{ key }}-container`).trigger('change');
        });
        $(`${parent_container_selector} #checkbox-form-{{ key }}-container .deselect-all`).on('click', () => {
            $(`${parent_container_selector} #checkbox-form-{{ key }}-container`).find('input').prop('checked', false);
            $(`${parent_container_selector} #checkbox-form-{{ key }}-container`).trigger('change');
        });

        $(`${parent_container_selector} #checkbox-form-{{ key }}-container`).on('change', function (e) {
            let hiddenTags = [];
            let visibleTags = [];
            $(this).find('input').each((index, input) => {
                if (!$(input).prop('checked')) {
                    hiddenTags.push($(input).prop('value'));
                } else {
                    visibleTags.push($(input).prop('value'));
                }
            });

            removeFilterChip('{{ key }}', '{{ filter.name }}');

            if (hiddenTags.length) {
                filtersMap.get(TAG_FILTER_KEY).set('{{ filter.name }}', hiddenTags);

                let title = visibleTags.length ? visibleTags.join(', ') : 'none'
                let closeEvent = () => {
                    $(`${parent_container_selector} #checkbox-form-{{ key }}-container`).find('input').prop('checked', true);
                    removeFilterChip('{{ key }}', '{{ filter.name }}');

                    filtersMap.get(TAG_FILTER_KEY).delete('{{ filter.name }}');

                    targetElement[0].dispatchEvent(new CustomEvent('filter_event', {
                        detail: filtersMap
                    }));
                };

                addFilterChip('{{ key }}', '{{ filter.name }}', title, closeEvent);
            } else {
                filtersMap.get(TAG_FILTER_KEY).delete('{{ filter.name }}');
            }

            targetElement[0].dispatchEvent(new CustomEvent('filter_event', {
                detail: filtersMap
            }));
        });
    {% elif filter.type == 'single_dropdown' %}
        /**
         * Single dropdown filter
         * Template fields:
         *   name: string
         *   type: 'single_dropdown'
         *   event_type: 'single_tag'
         *   values: [string]
         * Event object:
         *   [string]
         */
        $('#dropdown-select-{{ key }}_{{ parent_container_id }}').on('change', (event) => {
            let value = $(event.target).prop('value');

            removeFilterChip('{{ key }}', '{{ filter.name }}');

            if (value !== 'Any') {
                filtersMap.get(SINGLE_TAG_FILTER_KEY).set('{{ filter.name }}', [value]);

                let closeEvent = () => {
                    $('#dropdown-select-{{ key }}_{{ parent_container_id }}').val('Any');
                    removeFilterChip('{{ key }}', '{{ filter.name }}');

                    filtersMap.get(SINGLE_TAG_FILTER_KEY).delete('{{ filter.name }}');

                    targetElement[0].dispatchEvent(new CustomEvent('filter_event', {
                        detail: filtersMap
                    }));
                };

                addFilterChip('{{ key }}', '{{ filter.name }}', value, closeEvent);
            } else {
                filtersMap.get(SINGLE_TAG_FILTER_KEY).delete('{{ filter.name }}');
            }

            targetElement[0].dispatchEvent(new CustomEvent('filter_event', {
                detail: filtersMap
            }));
        });
    {% endif %}
{% endfor %}


// show and hide filters menu
$(`${parent_container_selector} #filters-container .collapse`).on('show.bs.collapse', function () {
    $(this).parent().find('.card-header i').addClass('shown');
}).on('hide.bs.collapse', function () {
    $(this).parent().find('.card-header i').removeClass('shown');
});
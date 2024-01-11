function setWidth(uuid) {
    let tableSelector = `#table_${uuid}`;
    let width = $(tableSelector).css('width');

    $(tableSelector).parents('.dataTables_scroll').css('width', width);
}

$(document).ready(function () {
    let data = '{{ opts | safe }}'.replace(/, }/g, ' }').replace(/, ]/g, ' ]').replace(/,$/, '');
    let options = JSON.parse('{' + data + '}');
    let table = $('#table_{{ uuid }}').DataTable(options);

    const const_data_{{ uuid }} = table.rows().data();

    const row_tags_{{ uuid }} = $.map(table.rows().nodes(), (item) => {
        let tags = $(item).data('tags');
        let split = [(tags !== undefined ? tags.split(' ') : [''])];
        return split.map((tags) => {
            return tags.map((tag) => tag.substring(tag.indexOf('=') + 1));
        });
    });

    const column_tags_{{ uuid }} = $('#table_{{ uuid }}_wrapper .dataTables_scrollHead thead').find('th')
            .map((index, elem) => {
                let tags = $(elem).data('tags');
                return [(tags !== undefined ? tags.split(' ') : [''])].map((tags) => {
                    return tags.map((tag) => tag.substring(tag.indexOf('=') + 1));
                });
            }).toArray();

    const table_{{ uuid }} = document.getElementById('table_{{ uuid }}_wrapper');

    setWidth('{{ uuid }}');

    table_{{ uuid }}.addEventListener('filter_event', function(event) {
        table.clear();
        table.rows.add(const_data_{{ uuid }});
        table.columns().visible(true);

        $('#table_{{ uuid }}').parents('.dataTables_scroll').css('width', '');

        event.detail.forEach((filterDetail, key) => {
            let hideList = key === 'tag';

            filterDetail.forEach((filterTags, key) => {
                let columnFilter = false;
                column_tags_{{ uuid }}.every((rowTags) => {
                    return rowTags.every((tag) => {
                        if (filterTags.includes(tag)) {
                            columnFilter = true;
                            return false;
                        }
                        return true;
                    });
                });

                if (columnFilter) {
                    column_tags_{{ uuid }}.forEach((columnTags, index) => {
                        if (index === 0) {
                            return;
                        }

                        let foundTags = columnTags.filter((tag) => filterTags.includes(tag));
                        if (foundTags.length > 0 === hideList) {
                            table.column(index).visible(false);
                        }
                    });
                } else {
                    let rowData = table.rows().data();
                    rowData = rowData.filter((row, index, data) => {
                        let hidden = false;
                        let foundTags = row_tags_{{ uuid }}[index].filter((rowTag) => filterTags.includes(rowTag));
                        if (foundTags.length > 0 === hideList) {
                            hidden = true;
                        }
                        return !hidden;
                    });

                    table.clear();
                    table.rows.add(rowData);
                }
            });
        });

        table.draw();

        setWidth('{{ uuid }}');
    });
});

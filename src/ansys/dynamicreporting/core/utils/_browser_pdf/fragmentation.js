// Copyright (C) 2023 - 2026 ANSYS, Inc. and/or its affiliates.
// SPDX-License-Identifier: MIT
//
//
// Permission is hereby granted, free of charge, to any person obtaining a copy
// of this software and associated documentation files (the "Software"), to deal
// in the Software without restriction, including without limitation the rights
// to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
// copies of the Software, and to permit persons to whom the Software is
// furnished to do so, subject to the following conditions:
//
// The above copyright notice and this permission notice shall be included in all
// copies or substantial portions of the Software.
//
// THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
// IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
// FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
// AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
// LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
// OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
// SOFTWARE.

(() => {
    const api = globalThis.__ansysDynamicReportingBrowserPdf;

    api.makeOversizedStructuresFragmentable = (printableHeightPx) => {
        // Capture CSS initially protects these structures from page breaks. Release every
        // relevant layer only when the complete structure is taller than one printable page.
        const breakableSliders = [];
        for (const slider of document.querySelectorAll('adr-slider-template')) {
            const container = [...slider.children].find(
                (child) => child.matches('section[id^="slider_container_"]')
            );
            if (!container || container.getBoundingClientRect().height <= printableHeightPx) {
                continue;
            }
            container.style.setProperty('break-inside', 'auto', 'important');
            container.style.setProperty('page-break-inside', 'auto', 'important');
            const row = container.querySelector(':scope > section.adr-row');
            if (row) {
                row.style.setProperty('break-inside', 'auto', 'important');
                row.style.setProperty('page-break-inside', 'auto', 'important');
            }
            breakableSliders.push(slider.dataset.guid || slider.id || 'untitled');
        }

        const breakableItems = [];
        for (const item of document.querySelectorAll('adr-data-item')) {
            const itemRect = item.getBoundingClientRect();
            if (itemRect.height <= printableHeightPx) {
                continue;
            }

            item.style.setProperty('break-inside', 'auto', 'important');
            item.style.setProperty('page-break-inside', 'auto', 'important');
            const layout = item.closest('div[data-layout-type="basic"]');
            if (layout) {
                layout.style.setProperty('break-inside', 'auto', 'important');
                layout.style.setProperty('page-break-inside', 'auto', 'important');
            }
            for (const child of item.querySelectorAll('.table-responsive, table')) {
                child.style.setProperty('break-inside', 'auto', 'important');
                child.style.setProperty('page-break-inside', 'auto', 'important');
            }
            breakableItems.push({
                id: item.id,
                type: item.dataset.itemType || 'unknown',
                heightPx: itemRect.height,
            });
        }

        return { breakableSliders, breakableItems };
    };
})();

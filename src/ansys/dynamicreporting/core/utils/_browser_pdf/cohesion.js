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

    api.setPaginationCohesion = (options) => {
        // Keep a complete section or panel together only when it fits. Forcing an over-height
        // structure to remain whole can push it away from a page or clip its content.
        const { printableHeightPx, fitGuardPx, headingSelector } = options;
        const isVisible = (element) => {
            const style = window.getComputedStyle(element);
            return element.getClientRects().length > 0
                && style.display !== 'none'
                && style.visibility !== 'hidden';
        };
        const fitsOnPage = (element) => (
            element.getBoundingClientRect().height <= printableHeightPx - fitGuardPx
        );

        const keptLayouts = [];
        for (const layout of document.querySelectorAll('div[data-layout-type="basic"]')) {
            const heading = layout.querySelector(headingSelector);
            const container = heading?.nextElementSibling;
            if (!container?.matches('section.adr-container') || !isVisible(layout)) {
                continue;
            }

            const fits = fitsOnPage(layout);
            layout.style.setProperty('break-inside', fits ? 'avoid' : 'auto', 'important');
            layout.style.setProperty('page-break-inside', fits ? 'avoid' : 'auto', 'important');
            if (fits) {
                keptLayouts.push(heading.textContent.trim() || 'Untitled layout');
            }
        }

        const keptPanels = [];
        for (const panel of document.querySelectorAll('adr-panel')) {
            const panelLayout = panel.closest('div[data-layout-type="panel"]');
            const visibleChildren = [...panel.children].filter(isVisible);
            if (!panelLayout || !visibleChildren.length) {
                continue;
            }

            const fits = fitsOnPage(panelLayout);
            panelLayout.style.setProperty('break-inside', fits ? 'avoid' : 'auto', 'important');
            panelLayout.style.setProperty(
                'page-break-inside', fits ? 'avoid' : 'auto', 'important'
            );
            if (fits) {
                keptPanels.push(
                    panel.shadowRoot?.querySelector('header.adr-panel-header')
                        ?.textContent.trim() || 'Untitled panel'
                );
            }
        }

        return { keptLayouts, keptPanels };
    };
})();

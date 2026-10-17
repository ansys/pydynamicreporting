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

    api.applyPanelCaptureStyles = () => {
        // An <adr-panel> renders inside a shadow DOM, which page-level styles cannot reach.
        for (const panel of document.querySelectorAll('adr-panel')) {
            const shadowRoot = panel.shadowRoot;
            // The marker makes repeated capture preparation harmless.
            if (!shadowRoot || shadowRoot.querySelector('style[data-adr-pdf-pagination]')) {
                continue;
            }

            const style = document.createElement('style');
            style.dataset.adrPdfPagination = '';
            style.textContent = `
                section.adr-panel {
                    display: block !important;
                }

                /* Keep the panel header with the body that follows it. */
                header.adr-panel-header {
                    break-after: avoid !important;
                    page-break-after: avoid !important;
                }
            `;
            shadowRoot.append(style);

            // Protect the other side of the header/content boundary in the light DOM.
            const firstPanelContent = panel.firstElementChild;
            if (firstPanelContent) {
                firstPanelContent.style.setProperty('break-before', 'avoid', 'important');
                firstPanelContent.style.setProperty('page-break-before', 'avoid', 'important');
            }
        }
    };
})();

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

    api.fitVisualsForPagination = async (options) => {
        // Find each visual that must not split across pages and shrink it, when needed, to fit
        // inside one printable page. Python supplies page geometry and ADR selectors in options.
        const {
            printableHeightPx,
            fitGuardPx,
            headingSelector,
            visualSelector,
            sceneViewerSelector,
            timeoutMs,
        } = options;
        let timeoutHandle;
        const timeoutResult = new Promise((resolve) => {
            timeoutHandle = window.setTimeout(() => {
                resolve({ __adrTimedOut: true });
            }, timeoutMs);
        });
        const preparedVisuals = new Set();
        const resizedVisuals = [];
        const resizePromises = [];

        const isVisible = (element) => {
            const style = window.getComputedStyle(element);
            return element.getClientRects().length > 0
                && style.display !== 'none'
                && style.visibility !== 'hidden';
        };

        // De-duplicate nested render nodes and resize the stable Plotly/viewer container instead
        // of an internal image or canvas that the component may replace later.
        const findRenderedVisuals = (root) => {
            const visuals = [];
            const seen = new Set();
            for (const candidate of root.querySelectorAll(visualSelector)) {
                const visual = candidate.closest(`.nexus-plot, ${sceneViewerSelector}`)
                    || candidate;
                if (!root.contains(visual) || seen.has(visual) || !isVisible(visual)) {
                    continue;
                }
                seen.add(visual);
                visuals.push(visual);
            }
            return visuals;
        };

        const visualLabel = (visual) => {
            const id = visual.id ? `#${visual.id}` : '';
            return `${visual.tagName.toLowerCase()}${id}`;
        };

        // A scene viewer can sit inside a product-owned sizing wrapper. Resize the outermost
        // wrapper inside its data item so the viewer and the space reserved for it stay aligned.
        const sceneLayoutRoot = (viewer) => {
            const item = viewer.closest('adr-data-item');
            let layoutRoot = viewer;
            while (item && layoutRoot.parentElement && layoutRoot.parentElement !== item) {
                layoutRoot = layoutRoot.parentElement;
            }
            return layoutRoot;
        };

        const prepareSceneViewer = (viewer, layoutRoot, layoutRect) => {
            if (layoutRect.width < 1) {
                return;
            }

            const configuredAspectRatio = Number.parseFloat(
                viewer.aspect_ratio ?? viewer.getAttribute('aspect_ratio')
            );
            const renderedAspectRatio = layoutRect.height > 0
                ? layoutRect.width / layoutRect.height
                : Number.NaN;
            const aspectRatio = Number.isFinite(configuredAspectRatio)
                    && configuredAspectRatio > 0
                ? configuredAspectRatio
                : Number.isFinite(renderedAspectRatio) && renderedAspectRatio > 0
                    ? renderedAspectRatio
                    : 16 / 9;

            layoutRoot.style.setProperty('aspect-ratio', `${aspectRatio}`, 'important');
            layoutRoot.style.setProperty('box-sizing', 'border-box', 'important');
            layoutRoot.style.setProperty('display', 'block', 'important');
            layoutRoot.style.setProperty('width', '100%', 'important');
            layoutRoot.style.setProperty('height', 'auto', 'important');
            layoutRoot.style.setProperty(
                'max-width', `${Math.ceil(layoutRect.width)}px`, 'important'
            );
            layoutRoot.style.setProperty('overflow', 'hidden', 'important');
            layoutRoot.style.setProperty('break-inside', 'avoid', 'important');
            layoutRoot.style.setProperty('page-break-inside', 'avoid', 'important');

            if (layoutRoot !== viewer) {
                viewer.style.setProperty('width', '100%', 'important');
                viewer.style.setProperty('height', '100%', 'important');
                viewer.style.setProperty('max-width', '100%', 'important');
                viewer.style.setProperty('max-height', '100%', 'important');
            }
            viewer.style.setProperty('overflow', 'hidden', 'important');
        };

        // Fit one visual together with fixed content that shares its page, such as a heading,
        // panel header, owner chrome, or panel padding.
        const fitVisual = (visual, groupStart, groupEnd, title) => {
            if (preparedVisuals.has(visual)) {
                return true;
            }
            const isSceneViewer = visual.matches(sceneViewerSelector);
            const fittedVisual = isSceneViewer ? sceneLayoutRoot(visual) : visual;
            const initialVisualRect = fittedVisual.getBoundingClientRect();
            if (isSceneViewer) {
                prepareSceneViewer(visual, fittedVisual, initialVisualRect);
            }
            const visualRect = fittedVisual.getBoundingClientRect();
            const responsiveHeightReduction = Math.max(
                0, initialVisualRect.height - visualRect.height
            );
            const fixedHeight = Math.max(0, visualRect.top - groupStart)
                + Math.max(0, groupEnd - responsiveHeightReduction - visualRect.bottom);
            const fittedHeight = Math.floor(
                printableHeightPx - fixedHeight - fitGuardPx
            );
            if (fittedHeight < 1 || visualRect.height < 1 || visualRect.width < 1) {
                return false;
            }

            const computedMaxHeight = Number.parseFloat(
                window.getComputedStyle(fittedVisual).maxHeight
            );
            const existingMaxHeight = Number.isFinite(computedMaxHeight)
                    && computedMaxHeight > 0
                ? computedMaxHeight
                : Number.POSITIVE_INFINITY;
            let constrainedHeight = Math.max(1, Math.floor(Math.min(
                visualRect.height, fittedHeight, existingMaxHeight
            )));
            let constrainedWidth = Math.max(1, Math.ceil(visualRect.width));
            const wasResized = visualRect.height > constrainedHeight + 0.5;

            // A scene viewer must shrink in both directions to preserve its aspect ratio.
            if (wasResized && isSceneViewer) {
                const aspectRatio = visualRect.width / visualRect.height;
                constrainedWidth = Math.max(1, Math.floor(Math.min(
                    visualRect.width, constrainedHeight * aspectRatio
                )));
                constrainedHeight = Math.max(1, Math.floor(constrainedWidth / aspectRatio));
            }

            fittedVisual.style.setProperty(
                'max-height', `${constrainedHeight}px`, 'important'
            );
            fittedVisual.style.setProperty('max-width', `${constrainedWidth}px`, 'important');
            if (wasResized && isSceneViewer) {
                fittedVisual.style.setProperty('height', `${constrainedHeight}px`, 'important');
                fittedVisual.style.setProperty('width', `${constrainedWidth}px`, 'important');
            } else if (wasResized && visual.matches('img, video, canvas')) {
                // Let media scale within the caps without stretching.
                visual.style.setProperty('height', 'auto', 'important');
                visual.style.setProperty('width', 'auto', 'important');
                visual.style.setProperty('object-fit', 'contain', 'important');
            } else if (wasResized) {
                visual.style.setProperty('height', `${constrainedHeight}px`, 'important');
            }

            if (wasResized && isSceneViewer) {
                const item = visual.closest('adr-data-item');
                fittedVisual.style.setProperty('overflow', 'hidden', 'important');
                if (item) {
                    item.style.setProperty('height', `${constrainedHeight}px`, 'important');
                    item.style.setProperty('max-height', `${constrainedHeight}px`, 'important');
                    item.style.setProperty('overflow', 'hidden', 'important');
                }
            }

            // Plotly retains its old pixel geometry until its resize hook completes.
            if (
                wasResized
                && visual.matches('.nexus-plot')
                && window.Plotly?.Plots?.resize
            ) {
                resizePromises.push(Promise.resolve(window.Plotly.Plots.resize(visual)));
            }
            preparedVisuals.add(visual);
            if (wasResized) {
                resizedVisuals.push({
                    title,
                    visual: visualLabel(visual),
                    originalHeightPx: visualRect.height,
                    fittedHeightPx: constrainedHeight,
                });
            }
            return true;
        };

        // Basic layouts own a heading and its content container. Include both in the first
        // visual's height budget so resizing cannot strand the title on the previous page.
        for (const layout of document.querySelectorAll('div[data-layout-type="basic"]')) {
            const heading = layout.querySelector(headingSelector);
            const container = heading?.nextElementSibling;
            if (!container?.matches('section.adr-container')) {
                continue;
            }

            const visuals = findRenderedVisuals(container);
            if (!visuals.length) {
                continue;
            }

            const panel = layout.closest('adr-panel');
            const panelHeader = panel?.shadowRoot?.querySelector('header.adr-panel-header');
            const panelBody = panel?.shadowRoot?.querySelector('section.adr-panel-body');
            const layoutRect = layout.getBoundingClientRect();
            const panelLayout = panel?.closest('div[data-layout-type="panel"]');
            const firstVisiblePanelChild = panel
                ? [...panel.children].find(isVisible)
                : null;
            const firstOwner = visuals[0].closest('adr-data-item, adr-slider-template')
                || visuals[0];
            const fragmentPaddingPx = panelBody
                ? Number.parseFloat(window.getComputedStyle(panelBody).paddingBottom) || 0
                : 0;
            for (const visual of visuals) {
                const owner = visual.closest('adr-data-item, adr-slider-template') || visual;
                const ownerRect = owner.getBoundingClientRect();
                const includesHeading = owner === firstOwner;
                const groupStart = includesHeading && panelHeader
                        && firstVisiblePanelChild === layout && panelLayout
                    ? panelLayout.getBoundingClientRect().top
                    : includesHeading
                        ? layoutRect.top
                        : ownerRect.top;
                fitVisual(
                    visual,
                    groupStart,
                    ownerRect.bottom + fragmentPaddingPx,
                    heading.textContent.trim()
                );
            }
        }

        // Panels without the basic-layout wrapper still need their shadow-DOM header included.
        for (const panel of document.querySelectorAll('adr-panel')) {
            const panelLayout = panel.closest('div[data-layout-type="panel"]');
            const visibleChildren = [...panel.children].filter(
                (child) => child.getClientRects().length > 0
            );
            if (!panelLayout || visibleChildren.length !== 1) {
                continue;
            }

            const panelRect = panelLayout.getBoundingClientRect();
            const panelHeader = panel.shadowRoot?.querySelector('header.adr-panel-header');
            for (const visual of findRenderedVisuals(visibleChildren[0])) {
                fitVisual(
                    visual,
                    panelRect.top,
                    panelRect.bottom,
                    panelHeader?.textContent.trim() || 'Untitled panel'
                );
            }
        }

        const reportRoot = document.getElementById('report_root');
        if (reportRoot) {
            // Catch standalone visuals not owned by either known layout shape.
            for (const visual of findRenderedVisuals(reportRoot)) {
                if (preparedVisuals.has(visual)) {
                    continue;
                }
                const owner = visual.closest(
                    'adr-data-item, adr-slider-template, div[data-layout-type]'
                ) || visual;
                const ownerRect = owner.getBoundingClientRect();
                fitVisual(
                    visual,
                    ownerRect.top,
                    ownerRect.bottom,
                    visualLabel(visual)
                );
            }
        }

        const preparationResult = (async () => {
            await Promise.all(resizePromises);
            // Two frames allow the browser to apply resized geometry before later measurements.
            await new Promise((resolve) => requestAnimationFrame(
                () => requestAnimationFrame(resolve)
            ));
            return {
                __adrTimedOut: false,
                cappedVisualCount: preparedVisuals.size,
                resizedVisuals,
            };
        })();
        const result = await Promise.race([preparationResult, timeoutResult]);
        if (!result.__adrTimedOut) {
            window.clearTimeout(timeoutHandle);
        }
        return result;
    };
})();

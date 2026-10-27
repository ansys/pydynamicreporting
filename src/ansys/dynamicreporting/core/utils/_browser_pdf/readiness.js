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

    // ADR hides the report until its custom elements are registered. Non-ADR HTML has no
    // report root and can pass immediately.
    api.registerReadyStep('foucGate', () => new Promise((resolve) => {
        const root = document.getElementById('report_root');
        if (!root || document.body.classList.contains('loaded')) {
            resolve();
            return;
        }
        const observer = new MutationObserver(() => {
            if (document.body.classList.contains('loaded')) {
                observer.disconnect();
                resolve();
            }
        });
        observer.observe(document.body, { attributes: true, attributeFilter: ['class'] });
    }));

    // The loaded class starts an opacity transition. Printing before opacity reaches 1 can
    // capture a partly transparent or invisible report.
    api.registerReadyStep('foucTransition', () => new Promise((resolve) => {
        const root = document.getElementById('report_root');
        if (!root || getComputedStyle(root).opacity === '1') {
            resolve();
            return;
        }
        root.addEventListener('transitionend', function handler(event) {
            if (
                event.target === root
                && event.propertyName === 'opacity'
                && getComputedStyle(root).opacity === '1'
            ) {
                root.removeEventListener('transitionend', handler);
                resolve();
            }
        });
    }));

    api.registerReadyStep('webFonts', () => document.fonts.ready);

    api.registerReadyStep('mathJax', () => new Promise((resolve, reject) => {
        if (typeof MathJax === 'undefined') {
            resolve();
            return;
        }

        // MathJax 4.1 documents MathDocument.whenReady() for pending typesetting.
        // Keep the startup promise for v3/v4 and Hub.Queue() for legacy v2 exports.
        if (
            MathJax.startup
            && MathJax.startup.document
            && typeof MathJax.startup.document.whenReady === 'function'
        ) {
            MathJax.startup.document.whenReady(() => undefined).then(resolve, reject);
        } else if (
            MathJax.startup
            && MathJax.startup.promise
            && typeof MathJax.startup.promise.then === 'function'
        ) {
            MathJax.startup.promise.then(resolve, reject);
        } else if (MathJax.Hub && typeof MathJax.Hub.Queue === 'function') {
            MathJax.Hub.Queue(resolve);
        } else {
            resolve();
        }
    }));

    api.registerReadyStep('plotlyCharts', () => new Promise((resolve) => {
        const plots = document.querySelectorAll('.nexus-plot');
        if (plots.length === 0) {
            resolve();
            return;
        }

        let remaining = plots.length;
        const completeOne = () => {
            remaining -= 1;
            if (remaining <= 0) {
                resolve();
            }
        };
        const findLoader = (plot) => {
            const item = plot.closest('adr-data-item');
            return item ? item.querySelector('.adr-spinner-loader-container') : null;
        };
        const loaderHidden = (loader) => {
            if (!loader) {
                return true;
            }
            const style = getComputedStyle(loader);
            return style.display === 'none'
                || style.visibility === 'hidden'
                || style.opacity === '0';
        };
        const findPlotContainer = (plot) => plot.querySelector(':scope > .plot-container');
        const plotVisible = (plot) => {
            const container = findPlotContainer(plot);
            return !container || getComputedStyle(container).opacity === '1';
        };
        const isReady = (plot) => plot.classList.contains('loaded')
            && loaderHidden(findLoader(plot))
            && plotVisible(plot);

        plots.forEach((plot) => {
            if (isReady(plot)) {
                completeOne();
                return;
            }
            const loader = findLoader(plot);
            let settled = false;
            const finishIfReady = () => {
                if (settled || !isReady(plot)) {
                    return;
                }
                settled = true;
                observer.disconnect();
                plot.removeEventListener('transitionend', handleTransitionEnd);
                completeOne();
            };
            const handleTransitionEnd = (event) => {
                // Plotly can create or replace its direct container after readiness starts.
                // Listen on the stable plot and accept only its current container's opacity event.
                if (
                    event.target === findPlotContainer(plot)
                    && event.propertyName === 'opacity'
                ) {
                    finishIfReady();
                }
            };
            const observer = new MutationObserver(finishIfReady);
            observer.observe(plot, { attributes: true, attributeFilter: ['class'] });
            if (loader) {
                observer.observe(loader, {
                    attributes: true,
                    attributeFilter: ['style', 'class', 'hidden'],
                });
            }
            plot.addEventListener('transitionend', handleTransitionEnd);
            // Close the gap between the initial readiness check and subscriptions.
            finishIfReady();
        });
    }));

    api.registerReadyStep('images', () => new Promise((resolve) => {
        const images = document.querySelectorAll('img');
        if (images.length === 0) {
            resolve();
            return;
        }

        let remaining = images.length;
        const completeOne = () => {
            remaining -= 1;
            if (remaining <= 0) {
                resolve();
            }
        };
        const findCompanionCanvas = (image) => {
            if (!image.id) {
                return null;
            }
            return document.getElementById(`${image.id}_canvas`);
        };
        const companionCanvasReady = (image) => {
            const canvas = findCompanionCanvas(image);
            if (!canvas) {
                return true;
            }
            const style = getComputedStyle(canvas);
            return style.display !== 'none' && style.visibility !== 'hidden';
        };
        const hasSource = (image) => Boolean(image.currentSrc || image.getAttribute('src'));
        const isReady = (image) => (
            hasSource(image)
            && image.complete
            && image.naturalWidth > 0
            && companionCanvasReady(image)
        );
        // A sourced image that completed without decoded dimensions has already emitted its
        // error event, so waiting for a new event would consume the whole render timeout.
        const hasFailed = (image) => hasSource(image)
            && image.complete
            && image.naturalWidth === 0;

        images.forEach((image) => {
            if (isReady(image) || hasFailed(image)) {
                completeOne();
                return;
            }

            let observer = null;
            let settled = false;
            const cleanup = () => {
                image.removeEventListener('load', onLoad);
                image.removeEventListener('error', onError);
                if (observer) {
                    observer.disconnect();
                }
            };
            const settle = () => {
                if (settled) {
                    return;
                }
                settled = true;
                cleanup();
                completeOne();
            };
            const onLoad = () => {
                if (isReady(image)) {
                    settle();
                }
            };
            const onError = () => settle();
            image.addEventListener('load', onLoad, { once: true });
            image.addEventListener('error', onError, { once: true });
            const companionCanvas = findCompanionCanvas(image);
            if (companionCanvas) {
                observer = new MutationObserver(() => {
                    if (isReady(image)) {
                        settle();
                    }
                });
                observer.observe(companionCanvas, {
                    attributes: true,
                    attributeFilter: ['style', 'class', 'hidden'],
                });
            }
        });
    }));

    api.registerReadyStep('videos', () => new Promise((resolve) => {
        const videos = document.querySelectorAll('video');
        if (videos.length === 0) {
            resolve();
            return;
        }

        let remaining = videos.length;
        const completeOne = () => {
            remaining -= 1;
            if (remaining <= 0) {
                resolve();
            }
        };
        videos.forEach((video) => {
            if (video.readyState >= 2 || video.error) {
                completeOne();
                return;
            }
            let settled = false;
            const cleanup = () => {
                video.removeEventListener('loadeddata', settle);
                video.removeEventListener('error', settle);
            };
            const settle = () => {
                if (settled) {
                    return;
                }
                settled = true;
                cleanup();
                completeOne();
            };
            video.addEventListener('loadeddata', settle);
            video.addEventListener('error', settle);
            // Close the gap between the initial state check and listener registration.
            if (video.readyState >= 2 || video.error) {
                settle();
            }
        });
    }));

    api.registerReadyStep('doubleAnimationFrame', () => new Promise((resolve) => {
        requestAnimationFrame(() => requestAnimationFrame(resolve));
    }));
})();

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
    const readySteps = new Map();
    const api = {
        registerReadyStep(stepKey, waitForReady) {
            if (typeof stepKey !== 'string' || typeof waitForReady !== 'function') {
                throw new TypeError('Browser PDF readiness steps require a string key and function.');
            }
            readySteps.set(stepKey, waitForReady);
        },

        async waitForReadyStep(options) {
            const waitForReady = readySteps.get(options.stepKey);
            if (!waitForReady) {
                throw new Error(`Unknown browser PDF readiness step: ${options.stepKey}`);
            }

            let timeoutHandle;
            const timeoutResult = new Promise((resolve) => {
                timeoutHandle = window.setTimeout(() => {
                    resolve({ __adrTimedOut: true });
                }, options.timeoutMs);
            });
            const readinessResult = Promise.resolve()
                .then(waitForReady)
                .then(() => ({ __adrTimedOut: false }));
            const result = await Promise.race([readinessResult, timeoutResult]);
            if (!result.__adrTimedOut) {
                window.clearTimeout(timeoutHandle);
            }
            return result;
        },
    };

    // A single private namespace keeps the report's globals clean and gives Python one
    // stable entry point for every packaged browser-PDF operation.
    globalThis.__ansysDynamicReportingBrowserPdf = api;
})();

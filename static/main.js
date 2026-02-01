document.addEventListener('DOMContentLoaded', () => {
    const step1 = document.getElementById('step1');
    const step2 = document.getElementById('step2');
    const step1Indicator = document.getElementById('step1-indicator');
    const step2Indicator = document.getElementById('step2-indicator');
    const inspectBtn = document.getElementById('inspect-btn');
    const newProductBtn = document.getElementById('new-product-btn');
    const resetBtn = document.getElementById('reset-btn');
    const displayImage = document.getElementById('display-image');
    const statusBadgeContainer = document.getElementById('status-badge-container');
    const resultDetails = document.getElementById('result-details');
    const step2Subtitle = document.getElementById('step2-subtitle');

    // QR Entry elements
    const qrInput = document.getElementById('qr-input');
    const qrStatus = document.getElementById('qr-status');
    const submitBtn = document.getElementById('submit-btn');
    const cancelBtn = document.getElementById('cancel-btn');

    // QR Input handling
    qrInput.addEventListener('input', () => {
        const value = qrInput.value.trim();
        const length = value.length;

        if (length === 0) {
            qrStatus.textContent = 'ENTER QR CODE';
            qrStatus.className = 'qr-status';
            submitBtn.disabled = true;
        } else if (length < 5) {
            qrStatus.textContent = 'PLEASE ENTER CORRECT QR CODE';
            qrStatus.className = 'qr-status';
            submitBtn.disabled = true;
        }
        else {
            qrStatus.textContent = 'CLICK SUBMIT';
            qrStatus.className = 'qr-status ready';
            submitBtn.disabled = false;
        }
    });

    // Cancel button - clear input
    cancelBtn.addEventListener('click', () => {
        qrInput.value = '';
        qrStatus.textContent = 'ENTER QR CODE';
        qrStatus.className = 'qr-status';
        submitBtn.disabled = true;
        qrInput.focus();
    });

    // Submit button - validate QR code
    submitBtn.addEventListener('click', async () => {
        const qrCode = qrInput.value.trim();
        if (qrCode.length < 5) return;

        submitBtn.disabled = true;
        submitBtn.textContent = 'Validating...';
        qrStatus.textContent = 'Validating QR code...';
        qrStatus.className = 'qr-status';

        try {
            const response = await fetch('/api/validate_qr', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ qr_code: qrCode })
            });
            const result = await response.json();

            if (result.valid) {
                if (result.exists && result.existing_record) {
                    // Show existing results in the QR input area
                    showExistingResults(qrCode, result.existing_record);
                } else {
                    // store inspection id returned by server
                    window._currentInspectionId = result.inspection_id;
                    qrInput.classList.add('success');
                    qrStatus.textContent = 'QR code validated!';
                    qrStatus.className = 'qr-status ready';
                    goToStep2();
                }
            } else {
                qrStatus.textContent = result.message || 'Invalid QR code';
                qrStatus.className = 'qr-status error';
            }
        } catch (err) {
            console.error('QR validation error:', err);
            qrStatus.textContent = 'Validation failed. Please try again.';
            qrStatus.className = 'qr-status error';
        } finally {
            submitBtn.disabled = qrInput.value.trim().length < 5;
            submitBtn.textContent = 'Submit';
        }
    });

    // Show existing inspection results
    function showExistingResults(qrCode, record) {
        const qrInputCard = document.querySelector('.qr-input-card');
        const qrButtonGroup = document.querySelector('.qr-button-group');

        // Replace QR input with results display
        qrInputCard.innerHTML = `
            <label>Inspection Record Found</label>
            <div class="existing-results">
                <div class="existing-barcode">${qrCode}</div>
                <div class="wire-results-grid">
                    <div class="wire-result ${record.wire1 === true ? 'pass' : record.wire1 === false ? 'fail' : 'pending'}">
                        <span class="wire-label">Wire 1</span>
                        <span class="wire-value">${record.wire1 === true ? 'PASS' : record.wire1 === false ? 'FAIL' : 'N/A'}</span>
                    </div>
                    <div class="wire-result ${record.wire2 === true ? 'pass' : record.wire2 === false ? 'fail' : 'pending'}">
                        <span class="wire-label">Wire 2</span>
                        <span class="wire-value">${record.wire2 === true ? 'PASS' : record.wire2 === false ? 'FAIL' : 'N/A'}</span>
                    </div>
                    <div class="wire-result ${record.wire3 === true ? 'pass' : record.wire3 === false ? 'fail' : 'pending'}">
                        <span class="wire-label">Wire 3</span>
                        <span class="wire-value">${record.wire3 === true ? 'PASS' : record.wire3 === false ? 'FAIL' : 'N/A'}</span>
                    </div>
                    <div class="wire-result ${record.wire4 === true ? 'pass' : record.wire4 === false ? 'fail' : 'pending'}">
                        <span class="wire-label">Wire 4</span>
                        <span class="wire-value">${record.wire4 === true ? 'PASS' : record.wire4 === false ? 'FAIL' : 'N/A'}</span>
                    </div>
                    <div class="wire-result ${record.wire5 === true ? 'pass' : record.wire5 === false ? 'fail' : 'pending'}">
                        <span class="wire-label">Wire 5</span>
                        <span class="wire-value">${record.wire5 === true ? 'PASS' : record.wire5 === false ? 'FAIL' : 'N/A'}</span>
                    </div>
                    <div class="wire-result ${record.wire6 === true ? 'pass' : record.wire6 === false ? 'fail' : 'pending'}">
                        <span class="wire-label">Wire 6</span>
                        <span class="wire-value">${record.wire6 === true ? 'PASS' : record.wire6 === false ? 'FAIL' : 'N/A'}</span>
                    </div>
                    <div class="wire-result ${record.wire7 === true ? 'pass' : record.wire7 === false ? 'fail' : 'pending'}">
                        <span class="wire-label">Wire 7</span>
                        <span class="wire-value">${record.wire7 === true ? 'PASS' : record.wire7 === false ? 'FAIL' : 'N/A'}</span>
                    </div>
                </div>
                <div class="final-result ${record.final_result === true ? 'pass' : 'fail'}">
                    Final: ${record.final_result === true ? 'PASS' : 'FAIL/PENDING'}
                </div>
            </div>
        `;

        // Replace buttons with Proceed/Cancel and add prompt
        qrButtonGroup.innerHTML = `
            <p class="existing-prompt">Do you want to proceed with re-inspection?</p>
            <button id="cancel-existing-btn" class="btn-secondary">Cancel</button>
            <button id="proceed-btn" class="btn-primary">Proceed</button>
        `;

        // Add event listeners for new buttons
        document.getElementById('cancel-existing-btn').addEventListener('click', () => {
            location.reload(); // Reload to reset the UI
        });

        document.getElementById('proceed-btn').addEventListener('click', async () => {
            // Force proceed - create new inspection record
            try {
                const response = await fetch('/api/validate_qr', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ qr_code: qrCode, force_proceed: true })
                });
                const result = await response.json();
                if (result.valid) {
                    goToStep2();
                }
            } catch (err) {
                console.error('Proceed error:', err);
            }
        });
    }

    function goToStep2() {
        step1.classList.remove('active');
        step2.classList.add('active');
        step1Indicator.classList.remove('active');
        step1Indicator.classList.add('completed');
        step2Indicator.classList.add('active');

        // Reset to live feed
        resetDisplay();
    }

    function goToStep1() {
        // Reload page with cache-busting to fully reset UI state
        window.location.href = window.location.pathname + '?t=' + Date.now();
    }

    function resetDisplay() {
        // Show live camera feed
        displayImage.src = '/camera/stream?' + Date.now();
        statusBadgeContainer.innerHTML = '';
        resultDetails.innerHTML = `
            <div class="detail-placeholder">
                <p>Results will appear here</p>
            </div>
        `;
        step2Subtitle.textContent = 'Position the product and click Inspect';

        // Toggle buttons
        inspectBtn.style.display = 'block';
        newProductBtn.style.display = 'none';
    }

    // Reset button
    resetBtn.addEventListener('click', goToStep1);

    // New Product button - go back to QR entry
    newProductBtn.addEventListener('click', () => {
        goToStep1();
    });

    // Inspect button handler
    inspectBtn.addEventListener('click', async () => {
        inspectBtn.disabled = true;
        inspectBtn.textContent = 'Processing...';

        try {
            const response = await fetch('/api/inspect', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ inspection_id: window._currentInspectionId }) });
            const result = await response.json();

            // Stop camera feed and show result image
            displayImage.src = result.annotated_image;

            // Update subtitle in sidebar
            step2Subtitle.textContent = 'Review and override results if needed';

            // Store AI results for reference
            const aiResults = {};
            const detections = result.detections || [];
            const failedWires = result.failed_wires || [];
            const failedWireIds = failedWires.map(w => w.wire);

            // Build wire results with dropdowns using detections array
            let detailsHTML = `<div id="final-status-display" class="final-status ${result.status.toLowerCase()}">${result.status}</div>`;

            // Sort detections by wire_id to ensure consistent display order
            const sortedDetections = [...detections].sort((a, b) => a.wire_id - b.wire_id);

            for (const det of sortedDetections) {
                const wireNum = det.wire_id;
                const color = det.color;
                const isError = failedWireIds.includes(wireNum);
                const aiPass = !isError;
                aiResults[wireNum] = aiPass;

                detailsHTML += `
                    <div class="wire-item-override ${aiPass ? 'ok' : 'error'}" data-wire-item="${wireNum}">
                        <div class="wire-info">
                            <strong>Wire ${wireNum}</strong> - ${color.toUpperCase()}
                        </div>
                        <select class="wire-override-select" data-wire="${wireNum}">
                            <option value="pass" ${aiPass ? 'selected' : ''}>PASS</option>
                            <option value="fail" ${!aiPass ? 'selected' : ''}>FAIL</option>
                        </select>
                    </div>
                `;
            }

            resultDetails.innerHTML = detailsHTML;

            // Add event listeners to dropdowns for real-time update
            const dropdowns = document.querySelectorAll('.wire-override-select');
            dropdowns.forEach(dropdown => {
                dropdown.addEventListener('change', updateFinalResult);
            });

            // Initial final result calculation
            updateFinalResult();

            // Hide inspect button and show Cancel/Submit buttons
            inspectBtn.style.display = 'none';

            // Replace the button group content
            const buttonGroup = document.querySelector('.button-group');
            buttonGroup.innerHTML = `
                <button id="cancel-result-btn" class="btn-secondary">Cancel</button>
                <button id="submit-result-btn" class="btn-primary">Submit</button>
            `;

            // Add Cancel button handler
            document.getElementById('cancel-result-btn').addEventListener('click', () => {
                goToStep1();
            });

            // Add Submit button handler
            document.getElementById('submit-result-btn').addEventListener('click', async () => {
                const manualResults = {};
                document.querySelectorAll('.wire-override-select').forEach(select => {
                    const wireNum = select.dataset.wire;
                    manualResults[`wire${wireNum}`] = select.value === 'pass';
                });

                try {
                    await fetch('/api/save_manual_results', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ inspection_id: window._currentInspectionId, manual_results: manualResults })
                    });
                    goToStep1();
                } catch (err) {
                    console.error('Save error:', err);
                }
            });

        } catch (err) {
            console.error('Inspect error:', err);
            step2Subtitle.textContent = 'Inspection failed. Please try again.';
        } finally {
            inspectBtn.disabled = false;
            inspectBtn.textContent = 'Inspect';
        }
    });

    // Function to update final result based on dropdown values
    function updateFinalResult() {
        const dropdowns = document.querySelectorAll('.wire-override-select');
        let allPass = true;

        dropdowns.forEach(dropdown => {
            const wireNum = dropdown.dataset.wire;
            const isPass = dropdown.value === 'pass';

            if (!isPass) {
                allPass = false;
            }

            // Update individual wire item color
            const wireItem = document.querySelector(`[data-wire-item="${wireNum}"]`);
            if (wireItem) {
                wireItem.classList.remove('ok', 'error');
                wireItem.classList.add(isPass ? 'ok' : 'error');
            }
        });

        const finalStatus = document.getElementById('final-status-display');
        const resultsCorner = document.querySelector('.results-corner');

        if (finalStatus) {
            finalStatus.textContent = allPass ? 'PASS' : 'FAIL';
            finalStatus.className = `final-status ${allPass ? 'pass' : 'fail'}`;
        }

        if (resultsCorner) {
            resultsCorner.classList.remove('pass', 'fail');
            resultsCorner.classList.add(allPass ? 'pass' : 'fail');
        }
    }

    // Initialize
    step1Indicator.classList.add('active');
});

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

    // QR Entry elements - using let because they get recreated on reset
    let qrInput = document.getElementById('qr-input');
    let qrStatus = document.getElementById('qr-status');
    let submitBtn = document.getElementById('submit-btn');
    let cancelBtn = document.getElementById('cancel-btn');

    // Toast notification helper with smooth animation
    function showToast(message, type = 'info') {
        const container = document.getElementById('toast-container');
        const toast = document.createElement('div');
        toast.className = `toast ${type}`;

        const icons = {
            success: '✓',
            error: '✕',
            info: 'ℹ'
        };

        toast.innerHTML = `
            <span class="toast-icon">${icons[type] || icons.info}</span>
            <span>${message}</span>
        `;

        container.appendChild(toast);

        // Auto-remove with smooth exit
        setTimeout(() => {
            toast.style.transition = 'all 0.3s cubic-bezier(0.16, 1, 0.3, 1)';
            toast.style.opacity = '0';
            toast.style.transform = 'translateX(80px) scale(0.95)';
            setTimeout(() => toast.remove(), 300);
        }, 4000);
    }

    // Update QR status with icon
    function setQrStatus(text, className) {
        const statusEl = document.getElementById('qr-status') || qrStatus;
        // Determine icon based on class
        let iconSvg = '';
        if (className === 'qr-status ready') {
            iconSvg = `<svg class="qr-status-icon" width="14" height="14" viewBox="0 0 14 14" fill="none">
                <circle cx="7" cy="7" r="6" stroke="currentColor" stroke-width="1.5"/>
                <path d="M4 7L6 9L10 5" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>
            </svg>`;
        } else if (className === 'qr-status error') {
            iconSvg = `<svg class="qr-status-icon" width="14" height="14" viewBox="0 0 14 14" fill="none">
                <circle cx="7" cy="7" r="6" stroke="currentColor" stroke-width="1.5"/>
                <path d="M5 5L9 9M9 5L5 9" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/>
            </svg>`;
        } else {
            iconSvg = `<svg class="qr-status-icon" width="14" height="14" viewBox="0 0 14 14" fill="none">
                <circle cx="7" cy="7" r="6" stroke="currentColor" stroke-width="1.5"/>
                <path d="M7 4.5V7.5" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/>
                <circle cx="7" cy="9.5" r="0.75" fill="currentColor"/>
            </svg>`;
        }
        statusEl.innerHTML = `${iconSvg}<span>${text}</span>`;
        statusEl.className = className;
    }

    // Smooth reset to Step 1 (no page reload)
    function goToStep1() {
        // Reset step indicators
        step1Indicator.classList.remove('completed', 'active');
        step1Indicator.classList.add('active');
        step2Indicator.classList.remove('active');

        // Switch panels
        step2.classList.remove('active');
        step1.classList.add('active');

        // Reset QR input
        qrInput.value = '';
        qrInput.classList.remove('success');
        qrInput.disabled = false;
        setQrStatus('Ready for Scan', 'qr-status');
        submitBtn.disabled = true;
        submitBtn.innerHTML = '<span>Submit</span><svg width="16" height="16" viewBox="0 0 16 16" fill="none"><path d="M3 8H13M13 8L9 4M13 8L9 12" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/></svg>';

        // Reset subtitle
        step2Subtitle.textContent = 'Ready for Scan';

        // Clear any existing results display
        const qrInputCard = document.querySelector('.qr-input-card');
        const qrButtonGroup = document.querySelector('.qr-button-group');

        // Restore original QR input card
        qrInputCard.innerHTML = `
            <label for="qr-input">
                <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
                    <rect x="1" y="1" width="5" height="5" rx="0.5" stroke="currentColor" stroke-width="1.5"/>
                    <rect x="10" y="1" width="5" height="5" rx="0.5" stroke="currentColor" stroke-width="1.5"/>
                    <rect x="1" y="10" width="5" height="5" rx="0.5" stroke="currentColor" stroke-width="1.5"/>
                    <rect x="10" y="10" width="2" height="2" fill="currentColor"/>
                    <rect x="13" y="10" width="2" height="2" fill="currentColor"/>
                    <rect x="10" y="13" width="2" height="2" fill="currentColor"/>
                </svg>
                Product QR Code
            </label>
            <div class="input-wrapper">
                <input type="text" id="qr-input" class="qr-input" placeholder="Scan or type QR code..." autocomplete="off" autofocus>
                <div class="input-glow"></div>
            </div>
            <p id="qr-status" class="qr-status">
                <svg class="qr-status-icon" width="14" height="14" viewBox="0 0 14 14" fill="none">
                    <circle cx="7" cy="7" r="6" stroke="currentColor" stroke-width="1.5"/>
                    <path d="M7 4.5V7.5" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/>
                    <circle cx="7" cy="9.5" r="0.75" fill="currentColor"/>
                </svg>
                <span>Ready for Scan</span>
            </p>
        `;

        // Restore original button group
        qrButtonGroup.innerHTML = `
            <button id="cancel-btn" class="btn-secondary"><span>Cancel</span></button>
            <button id="submit-btn" class="btn-primary" disabled>
                <span>Submit</span>
                <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
                    <path d="M3 8H13M13 8L9 4M13 8L9 12" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>
                </svg>
            </button>
        `;

        // Re-bind QR input handler (element was recreated)
        const newQrInput = document.getElementById('qr-input');
        const newQrStatus = document.getElementById('qr-status');
        const newSubmitBtn = document.getElementById('submit-btn');
        const newCancelBtn = document.getElementById('cancel-btn');

        // QR Input handling
        newQrInput.addEventListener('input', () => {
            const value = newQrInput.value.trim();
            const length = value.length;

            if (length === 0) {
                setQrStatus('Ready for Scan', 'qr-status');
                newSubmitBtn.disabled = true;
            } else if (length < 5) {
                setQrStatus('Enter at least 5 characters', 'qr-status');
                newSubmitBtn.disabled = true;
            } else {
                setQrStatus('Ready to submit', 'qr-status ready');
                newSubmitBtn.disabled = false;
            }
        });

        newCancelBtn.addEventListener('click', () => {
            newQrInput.value = '';
            setQrStatus('Ready for Scan', 'qr-status');
            newSubmitBtn.disabled = true;
            newQrInput.focus();
        });

        newSubmitBtn.addEventListener('click', handleQrSubmit);

        // Update global references
        qrInput = newQrInput;
        qrStatus = newQrStatus;
        submitBtn = newSubmitBtn;
        cancelBtn = newCancelBtn;

        // Focus input
        setTimeout(() => newQrInput.focus(), 100);

        showToast('Inspection reset', 'info');
    }

    // Initial QR input handler
    qrInput.addEventListener('input', () => {
        const value = qrInput.value.trim();
        const length = value.length;

        if (length === 0) {
            setQrStatus('Ready for Scan', 'qr-status');
            submitBtn.disabled = true;
        } else if (length < 5) {
            setQrStatus('Enter at least 5 characters', 'qr-status');
            submitBtn.disabled = true;
        } else {
            setQrStatus('Ready to submit', 'qr-status ready');
            submitBtn.disabled = false;
        }
    });

    // Handle QR code submission
    async function handleQrSubmit() {
        const qrCode = qrInput.value.trim();
        if (qrCode.length < 5) return;

        submitBtn.disabled = true;
        submitBtn.innerHTML = '<span class="loading-spinner"></span><span>Validating...</span>';
        setQrStatus('Validating QR code...', 'qr-status');

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
                    setQrStatus('QR code validated!', 'qr-status ready');
                    showToast('QR code validated successfully', 'success');
                    goToStep2();
                }
            } else {
                setQrStatus(result.message || 'Invalid QR code', 'qr-status error');
                showToast(result.message || 'Invalid QR code', 'error');
            }
        } catch (err) {
            console.error('QR validation error:', err);
            setQrStatus('Validation failed. Please try again.', 'qr-status error');
            showToast('Validation failed. Please try again.', 'error');
        } finally {
            submitBtn.disabled = qrInput.value.trim().length < 5;
            submitBtn.innerHTML = '<span>Submit</span><svg width="16" height="16" viewBox="0 0 16 16" fill="none"><path d="M3 8H13M13 8L9 4M13 8L9 12" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/></svg>';
        }
    }

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
            <button id="cancel-existing-btn" class="btn-secondary"><span>Cancel</span></button>
            <button id="proceed-btn" class="btn-primary">
                <span>Proceed</span>
                <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
                    <path d="M3 8H13M13 8L9 4M13 8L9 12" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>
                </svg>
            </button>
        `;

        // Add event listeners for new buttons
        document.getElementById('cancel-existing-btn').addEventListener('click', () => {
            goToStep1();
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
                    window._currentInspectionId = result.inspection_id;
                    showToast('Starting re-inspection', 'info');
                    goToStep2();
                }
            } catch (err) {
                console.error('Proceed error:', err);
                showToast('Failed to start re-inspection', 'error');
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

    function resetDisplay() {
        // Show live camera feed
        displayImage.src = '/camera/stream?' + Date.now();
        statusBadgeContainer.innerHTML = '';
        resultDetails.innerHTML = `
            <div class="detail-placeholder">
                <svg width="32" height="32" viewBox="0 0 32 32" fill="none">
                    <circle cx="16" cy="16" r="12" stroke="currentColor" stroke-width="1.5" stroke-dasharray="4 4"/>
                    <path d="M16 12V18" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/>
                    <circle cx="16" cy="21" r="1" fill="currentColor"/>
                </svg>
                <p>Results will appear here</p>
            </div>
        `;
        step2Subtitle.textContent = 'Position the product and click Inspect';

        // Toggle buttons
        inspectBtn.style.display = 'flex';
        newProductBtn.style.display = 'none';

        // Restore inspect button in button group
        const buttonGroup = document.querySelector('.button-group');
        buttonGroup.innerHTML = `
            <button id="inspect-btn" class="btn-primary btn-inspect">
                <svg width="18" height="18" viewBox="0 0 18 18" fill="none">
                    <circle cx="8" cy="8" r="5.5" stroke="currentColor" stroke-width="1.5"/>
                    <path d="M12.5 12.5L16 16" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/>
                </svg>
                <span>Inspect</span>
            </button>
            <button id="new-product-btn" class="btn-secondary" style="display: none;">
                <span>New Product</span>
            </button>
        `;

        // Re-bind inspect button
        const newInspectBtn = document.getElementById('inspect-btn');
        const newNewProductBtn = document.getElementById('new-product-btn');
        newInspectBtn.addEventListener('click', handleInspect);
        newNewProductBtn.addEventListener('click', goToStep1);
    }

    // Reset button handler
    resetBtn.addEventListener('click', goToStep1);

    // New Product button handler
    newProductBtn.addEventListener('click', goToStep1);

    // Keyboard shortcuts
    document.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && step1.classList.contains('active')) {
            const activeElement = document.activeElement;
            if (activeElement === qrInput || activeElement.tagName === 'INPUT') {
                e.preventDefault();
                if (!submitBtn.disabled) {
                    handleQrSubmit();
                }
            }
        }
        if (e.key === 'Escape') {
            if (step1.classList.contains('active') && !qrInput.value.trim()) {
                goToStep1();
            }
        }
    });

    // Inspect button handler
    async function handleInspect() {
        const btn = document.getElementById('inspect-btn');
        btn.disabled = true;
        btn.innerHTML = '<span class="loading-spinner"></span><span>Processing...</span>';

        try {
            const response = await fetch('/api/inspect', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ inspection_id: window._currentInspectionId })
            });
            const result = await response.json();

            // Stop camera feed and show result image
            displayImage.src = result.annotated_image;

            // Hide scan line animation
            const scanLine = document.querySelector('.scan-line');
            if (scanLine) scanLine.style.display = 'none';

            // Update subtitle
            step2Subtitle.textContent = 'Review and override results if needed';

            // Store AI results for reference
            const aiResults = {};
            const detections = result.detections || [];
            const failedWires = result.failed_wires || [];
            const failedWireIds = failedWires.map(w => w.wire);

            // Build wire results with dropdowns
            let detailsHTML = `<div id="final-status-display" class="final-status ${result.status.toLowerCase()}">${result.status}</div>`;

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
                            <strong>Wire ${wireNum}</strong> — ${color.toUpperCase()}
                        </div>
                        <select class="wire-override-select" data-wire="${wireNum}">
                            <option value="pass" ${aiPass ? 'selected' : ''}>PASS</option>
                            <option value="fail" ${!aiPass ? 'selected' : ''}>FAIL</option>
                        </select>
                    </div>
                `;
            }

            resultDetails.innerHTML = detailsHTML;

            // Add event listeners to dropdowns
            const dropdowns = document.querySelectorAll('.wire-override-select');
            dropdowns.forEach(dropdown => {
                dropdown.addEventListener('change', updateFinalResult);
            });

            updateFinalResult();

            // Replace buttons with Cancel/Submit
            const buttonGroup = document.querySelector('.button-group');
            buttonGroup.innerHTML = `
                <button id="cancel-result-btn" class="btn-secondary"><span>Cancel</span></button>
                <button id="submit-result-btn" class="btn-primary">
                    <span>Submit Results</span>
                    <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
                        <path d="M2 8L6 12L14 4" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
                    </svg>
                </button>
            `;

            document.getElementById('cancel-result-btn').addEventListener('click', () => {
                goToStep1();
            });

            document.getElementById('submit-result-btn').addEventListener('click', async () => {
                const submitResultBtn = document.getElementById('submit-result-btn');
                submitResultBtn.disabled = true;
                submitResultBtn.innerHTML = '<span class="loading-spinner"></span><span>Saving...</span>';

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
                    showToast('Results saved successfully', 'success');
                    goToStep1();
                } catch (err) {
                    console.error('Save error:', err);
                    showToast('Failed to save results', 'error');
                    submitResultBtn.disabled = false;
                    submitResultBtn.innerHTML = '<span>Submit Results</span>';
                }
            });

            showToast('Inspection complete', 'success');

        } catch (err) {
            console.error('Inspect error:', err);
            step2Subtitle.textContent = 'Inspection failed. Please try again.';
            showToast('Inspection failed. Please try again.', 'error');
            btn.disabled = false;
            btn.innerHTML = `
                <svg width="18" height="18" viewBox="0 0 18 18" fill="none">
                    <circle cx="8" cy="8" r="5.5" stroke="currentColor" stroke-width="1.5"/>
                    <path d="M12.5 12.5L16 16" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/>
                </svg>
                <span>Inspect</span>
            `;
        }
    }

    // Initial inspect button binding
    inspectBtn.addEventListener('click', handleInspect);

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
    submitBtn.addEventListener('click', handleQrSubmit);

    // Focus QR input on load
    setTimeout(() => qrInput.focus(), 200);
});

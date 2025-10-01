/**
 * Clinical Text De-Identification Frontend Application
 * Handles authentication, entity detection, and de-identification
 */

// Configuration
const API_BASE_URL = 'https://8000-igoy3cr883cnchk200st0-6532622b.e2b.dev';
let authToken = null;
let currentUser = null;

// Sample texts for testing
const sampleTexts = {
    thai: "คุณสมชาย วิทยาภูมิ โทรศัพท์ 089-123-4567 อีเมล somchai@hospital.co.th วันเกิด 15 มกราคม 2540 มีอาการปวดหัว หมอสมชาย ให้ยา Paracetamol กับ ยาหม่อง ส่วนหมอ Peter ให้ยาถ่าย",
    english: "Patient John Smith, DOB 01/15/1990, called 555-123-4567 regarding test results. Email: john.smith@hospital.com. Dr. Anderson prescribed medication.",
    mixed: "Patient คุณสมใส มีอาการ fever และ cough โทร 081-234-5678 อีเมล patient@hospital.co.th หมอ Wilson ให้ยา Amoxicillin"
};

// DOM Elements
const elements = {
    loginBtn: document.getElementById('loginBtn'),
    loginModal: document.getElementById('loginModal'),
    loginForm: document.getElementById('loginForm'),
    loginSubmit: document.getElementById('loginSubmit'),
    username: document.getElementById('username'),
    password: document.getElementById('password'),
    connectionStatus: document.getElementById('connectionStatus'),
    inputText: document.getElementById('inputText'),
    outputText: document.getElementById('outputText'),
    detectBtn: document.getElementById('detectBtn'),
    deidentifyBtn: document.getElementById('deidentifyBtn'),
    clearBtn: document.getElementById('clearBtn'),
    copyBtn: document.getElementById('copyBtn'),
    loading: document.querySelector('.loading'),
    resultSection: document.getElementById('resultSection'),
    entitiesCount: document.getElementById('entitiesCount'),
    detectedLanguage: document.getElementById('detectedLanguage'),
    detectedEntities: document.getElementById('detectedEntities'),
    backendStatus: document.getElementById('backendStatus')
};

// Initialize application
document.addEventListener('DOMContentLoaded', function() {
    initializeApp();
    setupEventListeners();
    checkBackendStatus();
});

/**
 * Initialize application
 */
function initializeApp() {
    console.log('=== Initializing App ===');
    console.log('All elements found:', elements);
    console.log('inputText element:', elements.inputText);
    console.log('outputText element:', elements.outputText);
    
    // Verify critical elements exist
    if (!elements.inputText) {
        console.error('ERROR: inputText element not found!');
    }
    if (!elements.outputText) {
        console.error('ERROR: outputText element not found!');
    }
    
    // Auto-fill password based on username selection
    elements.username.addEventListener('change', function() {
        const username = this.value;
        if (username) {
            elements.password.value = username + '123';
        } else {
            elements.password.value = '';
        }
    });

    // Initialize Bootstrap modal
    window.loginModalInstance = new bootstrap.Modal(elements.loginModal);
    
    updateUI();
}

/**
 * Setup event listeners
 */
function setupEventListeners() {
    // Authentication
    elements.loginBtn.addEventListener('click', () => {
        if (authToken) {
            logout();
        } else {
            window.loginModalInstance.show();
        }
    });

    elements.loginSubmit.addEventListener('click', login);
    
    elements.loginForm.addEventListener('submit', (e) => {
        e.preventDefault();
        login();
    });

    // Text processing
    elements.detectBtn.addEventListener('click', detectEntities);
    elements.deidentifyBtn.addEventListener('click', deidentifyText);
    elements.clearBtn.addEventListener('click', clearText);
    elements.copyBtn.addEventListener('click', copyResult);

    // Input validation
    elements.inputText.addEventListener('input', function() {
        const hasText = this.value.trim().length > 0;
        elements.detectBtn.disabled = !hasText || !authToken;
        elements.deidentifyBtn.disabled = !hasText || !authToken;
    });
}

/**
 * Check backend status
 */
async function checkBackendStatus() {
    try {
        const response = await fetch(`${API_BASE_URL}/health`);
        if (response.ok) {
            const data = await response.json();
            updateConnectionStatus('online', 'Connected');
            elements.backendStatus.textContent = `${data.status} (${data.version})`;
        } else {
            updateConnectionStatus('error', 'Backend Error');
            elements.backendStatus.textContent = 'Error';
        }
    } catch (error) {
        console.error('Backend status check failed:', error);
        updateConnectionStatus('offline', 'Offline');
        elements.backendStatus.textContent = 'Offline';
    }
}

/**
 * Update connection status indicator
 */
function updateConnectionStatus(status, text) {
    const statusElement = elements.connectionStatus;
    statusElement.className = 'badge';
    
    switch (status) {
        case 'online':
            statusElement.classList.add('bg-success');
            break;
        case 'offline':
            statusElement.classList.add('bg-danger');
            break;
        case 'error':
            statusElement.classList.add('bg-warning');
            break;
        default:
            statusElement.classList.add('bg-secondary');
    }
    
    statusElement.innerHTML = `<i class="fas fa-circle"></i> ${text}`;
}

/**
 * Login function
 */
async function login() {
    const username = elements.username.value;
    const password = elements.password.value;

    if (!username || !password) {
        showAlert('Please fill in all fields', 'warning');
        return;
    }

    try {
        showLoading(true);
        
        const response = await fetch(`${API_BASE_URL}/auth/login`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ username, password })
        });

        const data = await response.json();

        if (response.ok) {
            authToken = data.access_token;
            currentUser = data.user;
            
            window.loginModalInstance.hide();
            showAlert(`Welcome ${currentUser.username}! You are logged in as ${currentUser.role}.`, 'success');
            updateUI();
        } else {
            showAlert(data.detail || 'Login failed', 'danger');
        }
    } catch (error) {
        console.error('Login error:', error);
        showAlert('Login failed. Please check your connection.', 'danger');
    } finally {
        showLoading(false);
    }
}

/**
 * Logout function
 */
function logout() {
    authToken = null;
    currentUser = null;
    updateUI();
    showAlert('Logged out successfully', 'info');
}

/**
 * Update UI based on authentication status
 */
function updateUI() {
    const isLoggedIn = !!authToken;
    
    // Update login button
    if (isLoggedIn) {
        elements.loginBtn.innerHTML = `<i class="fas fa-sign-out-alt"></i> Logout (${currentUser.username})`;
        elements.loginBtn.className = 'btn btn-outline-light btn-sm';
    } else {
        elements.loginBtn.innerHTML = '<i class="fas fa-sign-in-alt"></i> Login';
        elements.loginBtn.className = 'btn btn-light btn-sm';
    }

    // Update button states
    const hasText = elements.inputText.value.trim().length > 0;
    elements.detectBtn.disabled = !isLoggedIn || !hasText;
    elements.deidentifyBtn.disabled = !isLoggedIn || !hasText;

    if (!isLoggedIn) {
        elements.resultSection.style.display = 'none';
        elements.outputText.value = '';
    }
}

/**
 * Load sample text
 */
function loadSampleText(type) {
    elements.inputText.value = sampleTexts[type];
    elements.inputText.focus();
    updateUI(); // Update button states
}

/**
 * Detect entities in text
 */
async function detectEntities() {
    const text = elements.inputText.value.trim();
    
    if (!text) {
        showAlert('Please enter some text to analyze', 'warning');
        return;
    }

    if (!authToken) {
        showAlert('Please login first', 'warning');
        return;
    }

    try {
        showLoading(true);
        
        const response = await fetch(`${API_BASE_URL}/api/v1/detect`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${authToken}`
            },
            body: JSON.stringify({ text })
        });

        const data = await response.json();

        if (response.ok) {
            displayDetectionResults(data);
            showAlert(`Detected ${data.entities_found} entities in ${data.detected_language} text`, 'success');
        } else {
            showAlert(data.detail || 'Detection failed', 'danger');
        }
    } catch (error) {
        console.error('Detection error:', error);
        showAlert('Detection failed. Please check your connection.', 'danger');
    } finally {
        showLoading(false);
    }
}

/**
 * De-identify text
 */
async function deidentifyText() {
    const text = elements.inputText.value.trim();
    
    if (!text) {
        showAlert('Please enter some text to de-identify', 'warning');
        return;
    }

    if (!authToken) {
        showAlert('Please login first', 'warning');
        return;
    }

    try {
        showLoading(true);
        
        const response = await fetch(`${API_BASE_URL}/api/v1/jobs`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${authToken}`
            },
            body: JSON.stringify({
                documents: [
                    {
                        content: text,
                        document_id: `frontend_${Date.now()}`,
                        metadata: { source: 'frontend', timestamp: new Date().toISOString() }
                    }
                ],
                policy_version: 'pdpa_v1.0',
                linkage_domain: 'patient_id'
            })
        });

        const data = await response.json();

        if (response.ok) {
            console.log('De-identification API response:', data);
            console.log('Calling displayDeidentificationResults with data:', JSON.stringify(data, null, 2));
            displayDeidentificationResults(data);
            showAlert(`De-identification completed! ${data.results[0].transformations_applied} transformations applied.`, 'success');
        } else {
            console.error('De-identification API error:', data);
            showAlert(data.detail || 'De-identification failed', 'danger');
        }
    } catch (error) {
        console.error('De-identification error:', error);
        showAlert('De-identification failed. Please check your connection.', 'danger');
    } finally {
        showLoading(false);
    }
}

/**
 * Display detection results
 */
function displayDetectionResults(data) {
    elements.outputText.value = `Detection Results:\n\nText Length: ${data.text_length} characters\nLanguage: ${data.detected_language}\nEntities Found: ${data.entities_found}\n\n` +
        data.detections.map((entity, index) => 
            `${index + 1}. ${entity.entity_type}\n   Text: "${entity.text}"\n   Position: ${entity.start}-${entity.end}\n   Confidence: ${(entity.confidence * 100).toFixed(1)}%\n   Detector: ${entity.detector}\n`
        ).join('\n');

    // Update statistics
    elements.entitiesCount.textContent = data.entities_found;
    elements.detectedLanguage.textContent = data.detected_language.toUpperCase();

    // Update entities display
    displayEntitiesBadges(data.detections);

    elements.resultSection.style.display = 'block';
}

/**
 * Display de-identification results
 */
function displayDeidentificationResults(data) {
    console.log('=== displayDeidentificationResults called ===');
    console.log('Input data:', JSON.stringify(data, null, 2));
    
    // Get the output textarea by ID directly as a backup
    const outputTextarea = document.getElementById('outputText');
    console.log('Direct getElementById outputText:', outputTextarea);
    
    if (!data || !data.results || data.results.length === 0) {
        console.error('Invalid de-identification data:', data);
        showAlert('Invalid response from de-identification API', 'danger');
        return;
    }
    
    const result = data.results[0];
    console.log('First result:', JSON.stringify(result, null, 2));
    
    if (!result) {
        console.error('No result found in response');
        showAlert('No results found in API response', 'danger');
        return;
    }
    
    // Safely construct output content
    const outputContent = `De-identification Results:\n\n` +
        `Job ID: ${data.job_id || 'N/A'}\n` +
        `Status: ${data.status || 'N/A'}\n` +
        `Original Length: ${result.original_length || 'N/A'} characters\n` +
        `Entities Detected: ${result.entities_detected || 0}\n` +
        `Transformations Applied: ${result.transformations_applied || 0}\n\n` +
        `ORIGINAL TEXT:\n${elements.inputText ? elements.inputText.value : 'N/A'}\n\n` +
        `DE-IDENTIFIED TEXT:\n${result.deidentified_text || 'No text available'}`;
    
    console.log('Constructed output content (length: ' + outputContent.length + '):', outputContent.substring(0, 200) + '...');
    
    // Try multiple ways to set the output
    if (elements.outputText) {
        console.log('Setting via elements.outputText...');
        elements.outputText.value = outputContent;
        console.log('Set via elements.outputText - current value length:', elements.outputText.value.length);
    } else {
        console.error('elements.outputText is null/undefined');
    }
    
    if (outputTextarea) {
        console.log('Setting via direct getElementById...');
        outputTextarea.value = outputContent;
        console.log('Set via getElementById - current value length:', outputTextarea.value.length);
    } else {
        console.error('Direct getElementById also failed');
    }

    // Update statistics with null checks
    if (elements.entitiesCount) {
        elements.entitiesCount.textContent = result.entities_detected || 0;
    }
    
    if (elements.detectedLanguage) {
        elements.detectedLanguage.textContent = 'PROTECTED';
    }

    // Show transformation info with null check
    if (elements.detectedEntities) {
        elements.detectedEntities.innerHTML = `
            <div class="alert alert-success mb-0">
                <h6><i class="fas fa-shield-alt"></i> Privacy Protection Applied</h6>
                <p class="mb-2">✅ <strong>${result.transformations_applied || 0}</strong> sensitive entities have been masked or pseudonymized.</p>
                <p class="mb-0"><small>All personal information has been protected while preserving clinical context.</small></p>
            </div>
        `;
    }

    console.log('Showing result section');
    if (elements.resultSection) {
        elements.resultSection.style.display = 'block';
    }
}

/**
 * Display entity badges
 */
function displayEntitiesBadges(detections) {
    if (!detections || detections.length === 0) {
        elements.detectedEntities.innerHTML = '<span class="text-muted">No entities detected</span>';
        return;
    }

    const entityColors = {
        'PERSON': 'bg-primary',
        'PHONE_NUMBER': 'bg-success',
        'EMAIL_ADDRESS': 'bg-info',
        'DATE_TIME': 'bg-warning',
        'ORGANIZATION': 'bg-secondary',
        'ADDRESS': 'bg-dark'
    };

    elements.detectedEntities.innerHTML = detections.map(entity => {
        const colorClass = entityColors[entity.entity_type] || 'bg-light text-dark';
        return `<span class="badge ${colorClass} entity-badge" title="${entity.text} (${(entity.confidence * 100).toFixed(1)}%)">${entity.entity_type}</span>`;
    }).join(' ');
}

/**
 * Clear all text
 */
function clearText() {
    elements.inputText.value = '';
    elements.outputText.value = '';
    elements.resultSection.style.display = 'none';
    updateUI();
}

/**
 * Copy result to clipboard
 */
async function copyResult() {
    try {
        await navigator.clipboard.writeText(elements.outputText.value);
        showAlert('Results copied to clipboard!', 'success');
    } catch (error) {
        // Fallback for older browsers
        elements.outputText.select();
        document.execCommand('copy');
        showAlert('Results copied to clipboard!', 'success');
    }
}

/**
 * Show loading indicator
 */
function showLoading(show) {
    elements.loading.style.display = show ? 'block' : 'none';
    
    // Disable buttons during loading
    elements.detectBtn.disabled = show;
    elements.deidentifyBtn.disabled = show;
    elements.loginSubmit.disabled = show;
}

/**
 * Show alert message
 */
function showAlert(message, type = 'info') {
    // Remove existing alerts
    const existingAlert = document.querySelector('.alert-notification');
    if (existingAlert) {
        existingAlert.remove();
    }

    // Create new alert
    const alert = document.createElement('div');
    alert.className = `alert alert-${type} alert-dismissible fade show alert-notification position-fixed`;
    alert.style.cssText = 'top: 20px; right: 20px; z-index: 1050; max-width: 400px;';
    
    alert.innerHTML = `
        ${message}
        <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
    `;

    document.body.appendChild(alert);

    // Auto remove after 5 seconds
    setTimeout(() => {
        if (alert.parentNode) {
            alert.remove();
        }
    }, 5000);
}

// Test function for debugging
function testOutputDisplay() {
    console.log('=== Testing Output Display ===');
    console.log('outputText element:', elements.outputText);
    console.log('Current value:', elements.outputText ? elements.outputText.value : 'ELEMENT NOT FOUND');
    
    if (elements.outputText) {
        elements.outputText.value = 'TEST: This is a test message to verify output display is working!';
        console.log('Set test value, current value now:', elements.outputText.value);
        
        // Show result section
        if (elements.resultSection) {
            elements.resultSection.style.display = 'block';
            console.log('Result section displayed');
        }
    }
}

// Expose functions globally for HTML onclick handlers
window.loadSampleText = loadSampleText;
window.testOutputDisplay = testOutputDisplay;
window.elements = elements; // For debugging
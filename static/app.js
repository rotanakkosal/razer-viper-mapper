/**
 * Razer Viper Mini Button Mapper — Frontend Application
 * Handles WebSocket communication, mouse visualization, and UI interactions.
 */

// ── State ─────────────────────────────────────────────────────
const state = {
    socket: null,
    connected: false,
    detectionActive: false,
    remappingActive: false,
    smoothScrollActive: false,
    scrollSettings: { speed: 1.0, smoothness: 0.78 },
    selectedButton: null,
    currentProfile: null,
    mappings: {},
    presets: {},
    profiles: [],
    eventLog: [],
};

// ── Button metadata ───────────────────────────────────────────
const BUTTONS = {
    left_click:     { name: "Left Click",     remappable: false },
    right_click:    { name: "Right Click",    remappable: false },
    middle_click:   { name: "Middle Click",   remappable: true },
    side_back:      { name: "Side (Back)",    remappable: true },
    side_forward:   { name: "Side (Forward)", remappable: true },
    scroll_up:      { name: "Scroll Up",      remappable: true },
    scroll_down:    { name: "Scroll Down",    remappable: true },
};

// ── Initialize ────────────────────────────────────────────────
document.addEventListener("DOMContentLoaded", () => {
    initSocket();
    loadPresets();
    renderMouseSVG();
    loadProfiles();
});

// ── WebSocket ─────────────────────────────────────────────────
function initSocket() {
    state.socket = io();

    state.socket.on("connect", () => {
        state.connected = true;
        updateConnectionStatus();
        console.log("[WS] Connected");
    });

    state.socket.on("disconnect", () => {
        state.connected = false;
        state.detectionActive = false;
        updateConnectionStatus();
        updateDetectionStatus();
        console.log("[WS] Disconnected");
    });

    state.socket.on("status", (data) => {
        state.detectionActive = data.detection_active;
        state.remappingActive = data.remapping_active;
        state.smoothScrollActive = !!data.smooth_scroll_active;
        if (data.scroll_settings) state.scrollSettings = data.scroll_settings;
        state.currentProfile = data.current_profile;
        updateDetectionStatus();
        updateRemappingToggle();
        updateSmoothScrollUI();
        updateProfileHighlight();
    });

    state.socket.on("button_event", (data) => {
        handleButtonEvent(data);
    });

    state.socket.on("mapping_updated", (data) => {
        if (data.mapping) {
            state.mappings[data.button_id] = data.mapping;
        } else {
            delete state.mappings[data.button_id];
        }
        updateButtonMappingDisplay(data.button_id);
        if (state.selectedButton === data.button_id) {
            renderConfigPanel();
        }
    });

    state.socket.on("all_mappings", (data) => {
        state.mappings = data;
        Object.keys(BUTTONS).forEach(bid => updateButtonMappingDisplay(bid));
    });

    state.socket.on("profile_saved", (data) => {
        showToast(`Profile "${data.name}" saved`, "success");
        loadProfiles();
    });

    state.socket.on("profile_loaded", (data) => {
        state.currentProfile = data.name;
        state.mappings = data.mappings;
        Object.keys(BUTTONS).forEach(bid => updateButtonMappingDisplay(bid));
        if (state.selectedButton) renderConfigPanel();
        updateProfileHighlight();
        showToast(`Loaded profile "${data.name}"`, "success");
    });

    state.socket.on("profiles_list", (data) => {
        state.profiles = data;
        renderProfileList();
    });

    state.socket.on("error", (data) => {
        showToast(data.message, "error");
    });
}

// ── Load presets from server ──────────────────────────────────
async function loadPresets() {
    try {
        const resp = await fetch("/api/presets");
        state.presets = await resp.json();
    } catch (e) {
        console.error("Failed to load presets", e);
    }
}

async function loadProfiles() {
    try {
        const resp = await fetch("/api/profiles");
        state.profiles = await resp.json();
        renderProfileList();
    } catch (e) {
        console.error("Failed to load profiles", e);
    }
}

// ── Mouse SVG Rendering ──────────────────────────────────────
function renderMouseSVG() {
    const container = document.getElementById("mouse-container");
    container.innerHTML = `
    <svg viewBox="0 0 240 440" class="mouse-svg" xmlns="http://www.w3.org/2000/svg">
      <!-- Mouse body outline -->
      <path class="mouse-body" d="
        M 60 140
        C 60 60, 80 20, 120 15
        C 160 20, 180 60, 180 140
        L 180 320
        C 180 390, 160 420, 120 425
        C 80 420, 60 390, 60 320
        Z
      "/>

      <!-- Scroll wheel -->
      <rect x="108" y="100" width="24" height="50" rx="12"
            fill="var(--bg-primary)" stroke="var(--border)" stroke-width="1.5"/>

      <!-- Divider line (left/right click separator) -->
      <line x1="120" y1="15" x2="120" y2="140" stroke="var(--border)" stroke-width="1"/>

      <!-- Left click zone -->
      <path id="zone-left_click" class="mouse-button-zone" d="
        M 62 140
        L 120 140
        L 120 15
        C 80 20, 62 60, 62 140
      " onclick="selectButton('left_click')"/>

      <!-- Right click zone -->
      <path id="zone-right_click" class="mouse-button-zone" d="
        M 120 15
        L 120 140
        L 178 140
        C 178 60, 160 20, 120 15
      " onclick="selectButton('right_click')"/>

      <!-- Middle click (scroll wheel) zone -->
      <rect id="zone-middle_click" class="mouse-button-zone"
            x="106" y="98" width="28" height="54" rx="14"
            onclick="selectButton('middle_click')"/>

      <!-- Side buttons (shown on left side of mouse = thumb buttons) -->
      <rect id="zone-side_forward" class="mouse-button-zone"
            x="0" y="170" width="66" height="42" rx="4"
            onclick="selectButton('side_forward')"/>
      <rect id="zone-side_back" class="mouse-button-zone"
            x="0" y="215" width="66" height="42" rx="4"
            onclick="selectButton('side_back')"/>

      <!-- Scroll indicators (top of mouse) -->
      <path id="zone-scroll_up" class="mouse-button-zone"
            d="M 112 86 L 120 74 L 128 86 Z"
            onclick="selectButton('scroll_up')"/>
      <path id="zone-scroll_down" class="mouse-button-zone"
            d="M 112 163 L 120 175 L 128 163 Z"
            onclick="selectButton('scroll_down')"/>

      <!-- Button labels -->
      <text class="button-label" x="90" y="85" id="label-left_click">L</text>
      <text class="button-label" x="150" y="85" id="label-right_click">R</text>
      <text class="button-label" x="120" y="130" id="label-middle_click">M</text>
      <text class="button-label" x="30" y="197" id="label-side_forward" text-anchor="end" style="cursor:pointer" onclick="selectButton('side_forward')">FWD</text>
      <text class="button-label" x="30" y="243" id="label-side_back" text-anchor="end" style="cursor:pointer" onclick="selectButton('side_back')">BACK</text>
      <text class="button-label" x="145" y="82" id="label-scroll_up" font-size="9">UP</text>
      <text class="button-label" x="145" y="172" id="label-scroll_down" font-size="9">DN</text>

      <!-- Mapping indicators (small tags below labels) -->
      <text class="button-label" x="30" y="210" id="mapping-side_forward"
            text-anchor="end" font-size="8" fill="var(--accent)"></text>
      <text class="button-label" x="30" y="256" id="mapping-side_back"
            text-anchor="end" font-size="8" fill="var(--accent)"></text>
      <text class="button-label" x="120" y="143" id="mapping-middle_click"
            font-size="8" fill="var(--accent)"></text>

      <!-- DPI indicator (bottom) -->
      <circle cx="120" cy="370" r="12" fill="var(--bg-primary)"
              stroke="var(--text-muted)" stroke-width="1" stroke-dasharray="3 2"/>
      <text x="120" y="374" text-anchor="middle" fill="var(--text-muted)"
            font-size="8" font-family="sans-serif">DPI</text>
      <text x="120" y="398" text-anchor="middle" fill="var(--text-muted)"
            font-size="8" font-family="sans-serif">(firmware)</text>
    </svg>`;
}

// ── Button interaction ────────────────────────────────────────
function selectButton(buttonId) {
    // Remove old selection
    document.querySelectorAll(".mouse-button-zone.selected").forEach(el => {
        el.classList.remove("selected");
    });

    if (state.selectedButton === buttonId) {
        state.selectedButton = null;
    } else {
        state.selectedButton = buttonId;
        const zone = document.getElementById(`zone-${buttonId}`);
        if (zone) zone.classList.add("selected");
    }

    renderConfigPanel();
}

function handleButtonEvent(data) {
    const { button_id, event_type, button_name } = data;

    // Flash the button zone
    const zone = document.getElementById(`zone-${button_id}`);
    if (zone && event_type === "down") {
        zone.classList.add("pressed");
        setTimeout(() => zone.classList.remove("pressed"), 200);
    }

    // Flash the label
    const label = document.getElementById(`label-${button_id}`);
    if (label && event_type === "down") {
        label.classList.add("active");
        setTimeout(() => label.classList.remove("active"), 300);
    }

    // Add to event log
    if (event_type === "down" || event_type === "scroll") {
        addEventLogEntry(button_name, event_type);
    }
}

function addEventLogEntry(buttonName, eventType) {
    const now = new Date();
    const time = now.toLocaleTimeString("en-US", {
        hour12: false, hour: "2-digit", minute: "2-digit", second: "2-digit"
    });

    state.eventLog.unshift({ time, buttonName, eventType });
    if (state.eventLog.length > 50) state.eventLog.pop();

    renderEventLog();
}

// ── Config Panel ──────────────────────────────────────────────
function renderConfigPanel() {
    const panel = document.getElementById("config-panel");

    if (!state.selectedButton) {
        panel.innerHTML = `
            <div class="button-config-empty">
                Click a button on the mouse<br/>to configure it
            </div>`;
        return;
    }

    const btn = BUTTONS[state.selectedButton];
    const mapping = state.mappings[state.selectedButton];

    let currentLabel = "No mapping (default)";
    if (mapping) {
        currentLabel = mapping.label || mapping.description || "Mapped";
    }

    let html = `
        <div class="config-button-name">${btn.name}</div>
        <div class="config-current">Current: ${currentLabel}</div>`;

    if (!btn.remappable) {
        html += `<div style="color: var(--text-muted); font-size: 13px; margin-top: 10px;">
            Primary click buttons cannot be remapped to avoid breaking basic mouse functionality.
        </div>`;
        panel.innerHTML = html;
        return;
    }

    // Preset shortcuts
    html += `<div style="margin-bottom: 8px; font-size: 12px; color: var(--text-secondary);">
        Select a preset shortcut:</div>`;
    html += `<div class="preset-grid">`;

    // "None" option to clear mapping
    const noneActive = !mapping ? "active" : "";
    html += `<div class="preset-item ${noneActive}" onclick="setPreset('${state.selectedButton}', 'none')">
        <span class="preset-item-label">No Mapping</span>
        <span class="preset-item-shortcut">default</span>
    </div>`;

    for (const [key, preset] of Object.entries(state.presets)) {
        if (key === "none") continue;
        const isActive = mapping && mapping.preset === key ? "active" : "";
        const shortcutText = preset.modifiers.length
            ? preset.modifiers.map(m => m.charAt(0).toUpperCase() + m.slice(1)).join("+") + "+" + preset.key.toUpperCase()
            : preset.key ? preset.key.toUpperCase() : "";

        html += `<div class="preset-item ${isActive}" onclick="setPreset('${state.selectedButton}', '${key}')">
            <span class="preset-item-label">${preset.label}</span>
            <span class="preset-item-shortcut">${shortcutText}</span>
        </div>`;
    }
    html += `</div>`;

    // Custom shortcut section
    html += `
        <div class="custom-shortcut-section">
            <div style="font-size: 12px; color: var(--text-secondary); margin-bottom: 6px;">
                Or set a custom shortcut:
            </div>
            <div style="display: flex; gap: 6px; flex-wrap: wrap; margin-bottom: 8px;">
                <label style="font-size: 12px; display: flex; align-items: center; gap: 4px;">
                    <input type="checkbox" id="mod-cmd" class="custom-mod"> Cmd
                </label>
                <label style="font-size: 12px; display: flex; align-items: center; gap: 4px;">
                    <input type="checkbox" id="mod-option" class="custom-mod"> Option
                </label>
                <label style="font-size: 12px; display: flex; align-items: center; gap: 4px;">
                    <input type="checkbox" id="mod-ctrl" class="custom-mod"> Ctrl
                </label>
                <label style="font-size: 12px; display: flex; align-items: center; gap: 4px;">
                    <input type="checkbox" id="mod-shift" class="custom-mod"> Shift
                </label>
            </div>
            <div style="display: flex; gap: 8px;">
                <select id="custom-key" style="flex: 1; padding: 8px; background: var(--bg-primary);
                    border: 1px solid var(--border); border-radius: 4px; color: var(--text-primary);
                    font-size: 13px;">
                    <option value="">Select key...</option>
                    <optgroup label="Letters">
                        ${['a','b','c','d','e','f','g','h','i','j','k','l','m','n','o','p','q','r','s','t','u','v','w','x','y','z']
                            .map(k => `<option value="${k}">${k.toUpperCase()}</option>`).join('')}
                    </optgroup>
                    <optgroup label="Numbers">
                        ${['0','1','2','3','4','5','6','7','8','9']
                            .map(k => `<option value="${k}">${k}</option>`).join('')}
                    </optgroup>
                    <optgroup label="Function Keys">
                        ${['f1','f2','f3','f4','f5','f6','f7','f8','f9','f10','f11','f12']
                            .map(k => `<option value="${k}">${k.toUpperCase()}</option>`).join('')}
                    </optgroup>
                    <optgroup label="Navigation">
                        ${['up','down','left','right','home','end','pageup','pagedown']
                            .map(k => `<option value="${k}">${k.charAt(0).toUpperCase() + k.slice(1)}</option>`).join('')}
                    </optgroup>
                    <optgroup label="Special">
                        ${['space','tab','return','escape','delete']
                            .map(k => `<option value="${k}">${k.charAt(0).toUpperCase() + k.slice(1)}</option>`).join('')}
                    </optgroup>
                </select>
                <button class="btn btn-primary btn-sm" onclick="setCustomShortcut('${state.selectedButton}')">
                    Apply
                </button>
            </div>
        </div>`;

    panel.innerHTML = html;
}

// ── Set mappings ──────────────────────────────────────────────
function setPreset(buttonId, presetName) {
    if (presetName === "none") {
        state.socket.emit("remove_mapping", { button_id: buttonId });
    } else {
        state.socket.emit("set_mapping", {
            button_id: buttonId,
            preset: presetName,
        });
    }
}

function setCustomShortcut(buttonId) {
    const key = document.getElementById("custom-key").value;
    if (!key) {
        showToast("Please select a key", "error");
        return;
    }

    const modifiers = [];
    if (document.getElementById("mod-cmd").checked) modifiers.push("cmd");
    if (document.getElementById("mod-option").checked) modifiers.push("option");
    if (document.getElementById("mod-ctrl").checked) modifiers.push("ctrl");
    if (document.getElementById("mod-shift").checked) modifiers.push("shift");

    const label = [...modifiers.map(m => m.charAt(0).toUpperCase() + m.slice(1)),
                    key.toUpperCase()].join("+");

    state.socket.emit("set_mapping", {
        button_id: buttonId,
        preset: "custom",
        key: key,
        modifiers: modifiers,
        label: label,
    });
}

// ── Update button mapping display on mouse SVG ───────────────
function updateButtonMappingDisplay(buttonId) {
    const el = document.getElementById(`mapping-${buttonId}`);
    if (!el) return;

    const mapping = state.mappings[buttonId];
    if (mapping) {
        el.textContent = mapping.label || "";
    } else {
        el.textContent = "";
    }

    // Also update the zone visual
    const zone = document.getElementById(`zone-${buttonId}`);
    if (zone) {
        if (mapping && mapping.preset !== "none") {
            zone.classList.add("active");
        } else {
            zone.classList.remove("active");
        }
    }
}

// ── Profiles ──────────────────────────────────────────────────
function renderProfileList() {
    const container = document.getElementById("profile-list");
    if (!container) return;

    if (state.profiles.length === 0) {
        container.innerHTML = `<div style="color: var(--text-muted); font-size: 13px;">No profiles yet</div>`;
        return;
    }

    container.innerHTML = state.profiles.map(p => {
        const isActive = state.currentProfile === p.name ? "active" : "";
        return `<div class="profile-item ${isActive}" onclick="loadProfile('${p.name.replace(/'/g, "\\'")}')">
            <div>
                <div class="profile-item-name">${p.name}</div>
                <div class="profile-item-meta">${p.mapping_count} mapping(s)${p.app_bundle_id ? ' · ' + p.app_bundle_id : ''}</div>
            </div>
            <button class="btn btn-icon btn-sm btn-danger" onclick="event.stopPropagation(); deleteProfile('${p.name.replace(/'/g, "\\'")}')">✕</button>
        </div>`;
    }).join("");
}

function updateProfileHighlight() {
    document.querySelectorAll(".profile-item").forEach(el => {
        el.classList.remove("active");
    });
    // Re-render to update highlight
    renderProfileList();
}

function saveProfile() {
    const nameInput = document.getElementById("profile-name-input");
    const appInput = document.getElementById("profile-app-input");

    const name = (nameInput && nameInput.value.trim()) || "Untitled";
    const appBundleId = appInput ? appInput.value.trim() : "";

    state.socket.emit("save_profile", {
        name: name,
        app_bundle_id: appBundleId || null,
    });

    closeModal();
}

function loadProfile(name) {
    state.socket.emit("load_profile", { name: name });
}

function deleteProfile(name) {
    if (!confirm(`Delete profile "${name}"?`)) return;

    fetch(`/api/profiles/${encodeURIComponent(name)}`, { method: "DELETE" })
        .then(resp => resp.json())
        .then(() => {
            showToast(`Deleted "${name}"`, "success");
            loadProfiles();
        })
        .catch(() => showToast("Delete failed", "error"));
}

function showSaveProfileModal() {
    const modal = document.getElementById("modal-overlay");
    document.getElementById("modal-content").innerHTML = `
        <h3>Save Profile</h3>
        <label style="font-size: 13px; color: var(--text-secondary); display: block; margin-bottom: 4px;">
            Profile Name
        </label>
        <input id="profile-name-input" type="text" placeholder="e.g., Gaming, Browsing, Coding..."
               value="${state.currentProfile || ''}" autofocus/>
        <label style="font-size: 13px; color: var(--text-secondary); display: block; margin-bottom: 4px;">
            App Bundle ID (optional — for auto-switching)
        </label>
        <input id="profile-app-input" type="text" placeholder="e.g., com.apple.Safari"/>
        <div class="modal-buttons">
            <button class="btn" onclick="closeModal()">Cancel</button>
            <button class="btn btn-primary" onclick="saveProfile()">Save</button>
        </div>`;
    modal.classList.add("visible");
}

function closeModal() {
    document.getElementById("modal-overlay").classList.remove("visible");
}

// ── Detection controls ────────────────────────────────────────
function toggleDetection() {
    if (state.detectionActive) {
        state.socket.emit("stop_detection");
    } else {
        state.socket.emit("start_detection");
    }
}

function toggleRemapping() {
    const toggle = document.getElementById("remapping-toggle");
    state.socket.emit("toggle_remapping", { enabled: toggle.checked });
}

// ── Smooth scrolling controls ─────────────────────────────────
function toggleSmoothScroll() {
    const toggle = document.getElementById("smooth-scroll-toggle");
    state.socket.emit("toggle_smooth_scroll", { enabled: toggle.checked });
}

let scrollSettingsTimer = null;
function onScrollSettingInput() {
    const speed = parseFloat(document.getElementById("scroll-speed").value);
    const smoothness = parseFloat(document.getElementById("scroll-smoothness").value);
    updateScrollSettingLabels(speed, smoothness);

    // Debounce so dragging a slider doesn't flood the socket
    clearTimeout(scrollSettingsTimer);
    scrollSettingsTimer = setTimeout(() => {
        state.socket.emit("set_scroll_settings", { speed, smoothness });
    }, 150);
}

function glideLabel(smoothness) {
    if (smoothness < 0.62) return "Snappy";
    if (smoothness < 0.75) return "Regular";
    if (smoothness < 0.86) return "Smooth";
    return "Floaty";
}

function updateScrollSettingLabels(speed, smoothness) {
    document.getElementById("scroll-speed-value").textContent = speed.toFixed(1) + "×";
    document.getElementById("scroll-smoothness-value").textContent = glideLabel(smoothness);
}

function updateSmoothScrollUI() {
    const toggle = document.getElementById("smooth-scroll-toggle");
    if (toggle) toggle.checked = state.smoothScrollActive;

    const settings = document.getElementById("scroll-settings");
    if (settings) settings.classList.toggle("visible", state.smoothScrollActive);

    const { speed, smoothness } = state.scrollSettings;
    const speedEl = document.getElementById("scroll-speed");
    const smoothEl = document.getElementById("scroll-smoothness");
    // Don't yank sliders around while the user is dragging them
    if (speedEl && document.activeElement !== speedEl) speedEl.value = speed;
    if (smoothEl && document.activeElement !== smoothEl) smoothEl.value = smoothness;
    updateScrollSettingLabels(speed, smoothness);
}

// ── Status updates ────────────────────────────────────────────
function updateConnectionStatus() {
    const dot = document.getElementById("status-connection");
    const label = document.getElementById("status-connection-label");
    if (state.connected) {
        dot.classList.add("active");
        label.textContent = "Connected";
    } else {
        dot.classList.remove("active");
        label.textContent = "Disconnected";
    }
}

function updateDetectionStatus() {
    const dot = document.getElementById("status-detection");
    const label = document.getElementById("status-detection-label");
    const btn = document.getElementById("detect-btn");

    if (state.detectionActive) {
        dot.classList.add("active");
        label.textContent = "Detecting";
        if (btn) {
            btn.textContent = "Stop Detection";
            btn.classList.remove("btn-primary");
            btn.classList.add("btn-danger");
        }
    } else {
        dot.classList.remove("active");
        label.textContent = "Idle";
        if (btn) {
            btn.textContent = "Start Detection";
            btn.classList.remove("btn-danger");
            btn.classList.add("btn-primary");
        }
    }
}

function updateRemappingToggle() {
    const toggle = document.getElementById("remapping-toggle");
    if (toggle) toggle.checked = state.remappingActive;
}

// ── Event Log ─────────────────────────────────────────────────
function renderEventLog() {
    const container = document.getElementById("event-log");
    if (!container) return;

    container.innerHTML = state.eventLog.slice(0, 20).map(e =>
        `<div class="event-log-entry">
            <span class="time">${e.time}</span>
            <span class="btn-name">${e.buttonName}</span>
            <span class="ev-type">${e.eventType}</span>
        </div>`
    ).join("");
}

// ── Toast notifications ───────────────────────────────────────
function showToast(message, type = "success") {
    const container = document.getElementById("toast-container");
    const toast = document.createElement("div");
    toast.className = `toast ${type}`;
    toast.textContent = message;
    container.appendChild(toast);

    setTimeout(() => {
        toast.style.opacity = "0";
        toast.style.transform = "translateX(100%)";
        toast.style.transition = "all 0.3s";
        setTimeout(() => toast.remove(), 300);
    }, 3000);
}

/**
 * VitalGrid — Hospital Spatial Resource Arbiter Client & 2D Hospital Ward Canvas Engine
 */

const API = "";

// ── DOM References ────────────────────────────────────────────
const navLanding       = document.getElementById("nav-landing");
const navDashboard     = document.getElementById("nav-dashboard");
const landingView      = document.getElementById("landing-view");
const dashboardView    = document.getElementById("dashboard-view");
const btnLaunchDash    = document.getElementById("btn-launch-dashboard");

const treeContainer    = document.getElementById("tree-container");
const canvasContainer  = document.getElementById("canvas-container");
const spatialViewport  = document.getElementById("spatial-viewport");
const canvas           = document.getElementById("warehouse-canvas");
const canvasTooltip    = document.getElementById("canvas-tooltip");
const ttTitle          = document.getElementById("tt-title");
const ttBody           = document.getElementById("tt-body");

const btnModeTree      = document.getElementById("btn-mode-tree");
const btnModeCanvas    = document.getElementById("btn-mode-canvas");
const btnModeSplit     = document.getElementById("btn-mode-split");

const nodeSelect       = document.getElementById("select-node");
const agentSelect      = document.getElementById("select-agent");
const btnLock          = document.getElementById("btn-lock");
const btnUnlock        = document.getElementById("btn-unlock");
const btnUpgrade       = document.getElementById("btn-upgrade");
const btnRefresh       = document.getElementById("btn-refresh");

const btnSendHb        = document.getElementById("btn-send-hb");
const btnSimCrash      = document.getElementById("btn-sim-crash");
const chkAutoHb        = document.getElementById("chk-auto-hb");
const wsStatusText     = document.getElementById("ws-status-text");

const toast            = document.getElementById("response-toast");
const toastIcon        = document.getElementById("toast-icon");
const toastMsg         = document.getElementById("toast-msg");
const auditList        = document.getElementById("audit-list");
const auditCount       = document.getElementById("audit-count");

// ── State ─────────────────────────────────────────────────────
let currentTree       = null;
let selectedNode      = null;
let ws                = null;
let heartbeatInterval = null;
let canvasRenderer    = null;

// ── Initialization ────────────────────────────────────────────
document.addEventListener("DOMContentLoaded", () => {
    setupTabNavigation();
    setupViewModeSwitcher();
    setupWebSocket();
    loadAll();

    // Initialize 2D Hospital Canvas Engine
    if (canvas) {
        canvasRenderer = new HospitalCanvasRenderer(canvas);
        canvasRenderer.start();
    }

    btnLock.addEventListener("click", () => doAction("lock"));
    btnUnlock.addEventListener("click", () => doAction("unlock"));
    btnUpgrade.addEventListener("click", () => doAction("upgrade"));
    btnRefresh.addEventListener("click", loadAll);

    if (btnSendHb) btnSendHb.addEventListener("click", sendManualHeartbeat);
    if (btnSimCrash) btnSimCrash.addEventListener("click", simulateUnloggedDischarge);

    // Start Auto-Telemetry pulse loop (every 10s)
    startAutoHeartbeatLoop();
});

// ── Navigation Handler ────────────────────────────────────────
function setupTabNavigation() {
    navLanding.addEventListener("click", () => switchView("landing"));
    navDashboard.addEventListener("click", () => switchView("dashboard"));
    if (btnLaunchDash) {
        btnLaunchDash.addEventListener("click", () => switchView("dashboard"));
    }
}

function switchView(viewName) {
    if (viewName === "landing") {
        navLanding.classList.add("active");
        navDashboard.classList.remove("active");
        landingView.classList.add("active");
        dashboardView.classList.remove("active");
    } else {
        navDashboard.classList.add("active");
        navLanding.classList.remove("active");
        dashboardView.classList.add("active");
        landingView.classList.remove("active");
        if (currentTree) {
            renderTree(currentTree);
            if (canvasRenderer) canvasRenderer.updateTreeState(currentTree);
        }
    }
}

// ── View Mode Switcher ────────────────────────────────────────
function setupViewModeSwitcher() {
    if (!btnModeTree || !btnModeCanvas || !btnModeSplit) return;

    btnModeTree.addEventListener("click", () => setViewMode("tree"));
    btnModeCanvas.addEventListener("click", () => setViewMode("canvas"));
    btnModeSplit.addEventListener("click", () => setViewMode("split"));
}

function setViewMode(mode) {
    btnModeTree.classList.remove("active");
    btnModeCanvas.classList.remove("active");
    btnModeSplit.classList.remove("active");

    treeContainer.classList.remove("active");
    canvasContainer.classList.remove("active");
    spatialViewport.classList.remove("split-mode");

    if (mode === "tree") {
        btnModeTree.classList.add("active");
        treeContainer.classList.add("active");
    } else if (mode === "canvas") {
        btnModeCanvas.classList.add("active");
        canvasContainer.classList.add("active");
    } else if (mode === "split") {
        btnModeSplit.classList.add("active");
        spatialViewport.classList.add("split-mode");
        treeContainer.classList.add("active");
        canvasContainer.classList.add("active");
    }
}

// ── WebSockets Stream ─────────────────────────────────────────
function setupWebSocket() {
    const protocol = location.protocol === "https:" ? "wss:" : "ws:";
    const wsUrl    = `${protocol}//${location.host}/ws/events`;

    try {
        ws = new WebSocket(wsUrl);

        ws.onopen = () => {
            if (wsStatusText) wsStatusText.textContent = "WebSocket Active";
        };

        ws.onmessage = (event) => {
            const msg = JSON.parse(event.data);

            if (msg.tree) {
                currentTree = msg.tree;
                renderTree(currentTree);
                if (canvasRenderer) canvasRenderer.updateTreeState(currentTree);
            }
            if (msg.audit) {
                renderAudit(msg.audit);
            }

            if (msg.type === "LEASE_EXPIRED") {
                showToast(false, `Lease Expired: ${msg.detail.message}`);
            }
        };

        ws.onclose = () => {
            if (wsStatusText) wsStatusText.textContent = "WS Reconnecting...";
            setTimeout(setupWebSocket, 3000);
        };

        ws.onerror = () => {
            if (wsStatusText) wsStatusText.textContent = "WS Offline";
        };
    } catch (e) {
        if (wsStatusText) wsStatusText.textContent = "WS Unsupported";
    }
}

// ── Data Fetching ─────────────────────────────────────────────
async function loadAll() {
    await Promise.all([loadTree(), loadAudit()]);
}

async function loadTree() {
    try {
        const res  = await fetch(`${API}/api/v1/resource/status`);
        const data = await res.json();
        if (data.success) {
            currentTree = data.data.tree;
            renderTree(currentTree);
            populateNodeSelect(data.data.nodes);
            if (canvasRenderer) canvasRenderer.updateTreeState(currentTree);
        }
    } catch (err) {
        treeContainer.innerHTML = `<div class="tree-loading">Unable to connect to arbiter engine</div>`;
    }
}

// ── Tree DOM Rendering ────────────────────────────────────────
function renderTree(node) {
    treeContainer.innerHTML = "";
    const ul = buildTreeDOM(node);
    treeContainer.appendChild(ul);
}

function buildTreeDOM(node) {
    const ul = document.createElement("ul");
    ul.className = "tree-level";

    const li = document.createElement("li");
    li.className = "tree-node";

    const card = document.createElement("div");
    card.className = "node-card";
    card.dataset.nodeId = node.id;

    if (node.is_locked) {
        card.classList.add("state-locked");
    } else if (node.locked_descendant_count > 0) {
        card.classList.add("state-partial");
    } else {
        card.classList.add("state-free");
    }

    if (selectedNode === node.id) {
        card.classList.add("selected");
    }

    const dot = document.createElement("span");
    dot.className = "node-status-dot";
    card.appendChild(dot);

    const info = document.createElement("div");
    info.className = "node-info";

    const name = document.createElement("span");
    name.className = "node-name";
    name.textContent = node.name;

    const type = document.createElement("span");
    type.className = "node-type";
    type.textContent = node.type;

    info.appendChild(name);
    info.appendChild(type);
    card.appendChild(info);

    if (node.is_locked && node.locked_by) {
        const badge = document.createElement("span");
        badge.className = "node-agent-badge";
        badge.textContent = node.locked_by;
        card.appendChild(badge);

        if (node.ttl_remaining > 0) {
            const ttlBadge = document.createElement("span");
            ttlBadge.className = "node-ttl-badge";
            ttlBadge.textContent = `${node.ttl_remaining}s`;
            card.appendChild(ttlBadge);
        }
    }

    card.addEventListener("click", (e) => {
        e.stopPropagation();
        selectedNode = node.id;
        nodeSelect.value = node.id;
        renderTree(currentTree);
        if (canvasRenderer) canvasRenderer.selectNode(node.id);
    });

    li.appendChild(card);

    if (node.children && node.children.length > 0) {
        const childUl = document.createElement("ul");
        childUl.className = "tree-level";
        for (const child of node.children) {
            const childLi = buildTreeDOM(child);
            childUl.appendChild(childLi.firstChild);
        }
        li.appendChild(childUl);
    }

    ul.appendChild(li);
    return ul;
}

function populateNodeSelect(nodes) {
    const currentVal = nodeSelect.value;
    nodeSelect.innerHTML = "";
    for (const n of nodes) {
        const opt = document.createElement("option");
        opt.value = n.id;
        opt.textContent = `${n.name} (${n.type})`;
        nodeSelect.appendChild(opt);
    }
    if (currentVal && nodes.some(n => n.id === currentVal)) {
        nodeSelect.value = currentVal;
    }
}

// ── Action Handlers ───────────────────────────────────────────
async function doAction(action) {
    const agentId = agentSelect.value;
    const nodeId  = nodeSelect.value;

    if (!nodeId) {
        showToast(false, "Please select a target hospital node.");
        return;
    }

    let url, body;
    if (action === "lock") {
        url  = `${API}/api/v1/resource/lock`;
        body = { node_id: nodeId, agent_id: agentId, ttl_seconds: 30 };
    } else if (action === "unlock") {
        url  = `${API}/api/v1/resource/unlock`;
        body = { node_id: nodeId, agent_id: agentId };
    } else if (action === "upgrade") {
        url  = `${API}/api/v1/resource/upgrade`;
        body = { parent_id: nodeId, agent_id: agentId };
    }

    try {
        const res  = await fetch(url, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(body),
        });
        const data = await res.json();
        showToast(data.success, data.message || data.detail);
        await loadAll();
    } catch (err) {
        showToast(false, "Network error: unable to contact backend API.");
    }
}

// ── Heartbeat & Unlogged Discharge Handlers ───────────────────
async function sendManualHeartbeat() {
    const agentId = agentSelect.value;
    const nodeId  = nodeSelect.value;

    if (!nodeId) {
        showToast(false, "Select a target bed to send telemetry pulse.");
        return;
    }

    try {
        const res = await fetch(`${API}/api/v1/resource/heartbeat`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ node_id: nodeId, agent_id: agentId, ttl_seconds: 30 }),
        });
        const data = await res.json();
        showToast(data.success, data.message || data.detail);
        await loadAll();
    } catch (err) {
        showToast(false, "Telemetry heartbeat failed.");
    }
}

function simulateUnloggedDischarge() {
    chkAutoHb.checked = false;
    showToast(false, "Unlogged Discharge Simulated. Auto-telemetry stopped. Watch bed state expire in 30 seconds.");
}

function startAutoHeartbeatLoop() {
    if (heartbeatInterval) clearInterval(heartbeatInterval);

    heartbeatInterval = setInterval(async () => {
        if (!chkAutoHb || !chkAutoHb.checked || !currentTree) return;

        const lockedNodes = getLockedNodes(currentTree);
        for (const n of lockedNodes) {
            try {
                await fetch(`${API}/api/v1/resource/heartbeat`, {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ node_id: n.id, agent_id: n.locked_by, ttl_seconds: 30 }),
                });
            } catch (e) {
                // Ignore
            }
        }
    }, 10000); // 10s telemetry heartbeat
}

function getLockedNodes(node) {
    let result = [];
    if (node.is_locked && node.locked_by) {
        result.push(node);
    }
    if (node.children) {
        for (const child of node.children) {
            result = result.concat(getLockedNodes(child));
        }
    }
    return result;
}

// ── Feedback Toast ────────────────────────────────────────────
function showToast(success, message) {
    toast.classList.remove("hidden", "success", "error");
    toast.classList.add(success ? "success" : "error");
    toastIcon.textContent = success ? "OK" : "ERR";
    toastMsg.textContent  = message;

    clearTimeout(toast._timer);
    toast._timer = setTimeout(() => toast.classList.add("hidden"), 5000);
}

// ── Audit Ledger Trail ────────────────────────────────────────
async function loadAudit() {
    try {
        const res  = await fetch(`${API}/api/v1/audit`);
        const data = await res.json();
        if (data.success) {
            renderAudit(data.data.log);
        }
    } catch (err) {
        // Silently handle
    }
}

function renderAudit(log) {
    auditCount.textContent = log.length;
    if (log.length === 0) {
        auditList.innerHTML = `<div class="audit-empty">No transactions recorded yet.</div>`;
        return;
    }

    auditList.innerHTML = "";
    const reversed = [...log].reverse();

    for (const entry of reversed) {
        const el = document.createElement("div");
        el.className = `audit-item ${entry.success ? "success" : "fail"}`;

        const headerLine = document.createElement("div");
        headerLine.className = "audit-header-line";

        const badge = document.createElement("span");
        badge.className = `audit-badge ${entry.action}`;
        badge.textContent = entry.action;

        const time = document.createElement("span");
        time.className = "audit-timestamp";
        time.textContent = formatTime(entry.timestamp);

        headerLine.appendChild(badge);
        headerLine.appendChild(time);

        const text = document.createElement("div");
        text.className = "audit-text";
        text.innerHTML = `<span class="audit-agent">${entry.agent_id}</span> &rarr; ${entry.node_id}<br><span style="color:var(--text-muted); font-size:0.74rem;">${entry.detail}</span>`;

        el.appendChild(headerLine);
        el.appendChild(text);

        auditList.appendChild(el);
    }
}

function formatTime(isoStr) {
    try {
        const d = new Date(isoStr);
        return d.toLocaleTimeString("en-US", { hour12: false, hour: "2-digit", minute: "2-digit", second: "2-digit" });
    } catch {
        return isoStr;
    }
}

// ==============================================================================
// ── 2D HOSPITAL WARD FLOOR CANVAS RENDERER CLASS ─────────────────────────────
// ==============================================================================

class HospitalCanvasRenderer {
    constructor(canvasElement) {
        this.canvas  = canvasElement;
        this.ctx     = canvasElement.getContext("2d");
        this.treeMap = new Map();
        this.selectedId = null;
        this.hoveredId  = null;
        this.animFrame  = null;

        // Physical Hospital Spatial Coordinates (840x540 canvas)
        this.regions = [
            // Hospital Boundary
            { id: "hospital-1", name: "St. Thomas' Hospital", type: "HOSPITAL", x: 20, y: 20, w: 800, h: 500 },

            // Ward Alpha (Acute Care)
            { id: "ward-Alpha", name: "Ward Alpha (Acute Care)", type: "WARD", x: 45, y: 60, w: 360, h: 380 },
            // Ward Beta (Surgical Ward)
            { id: "ward-Beta", name: "Ward Beta (Surgical Ward)", type: "WARD", x: 435, y: 60, w: 360, h: 380 },

            // Departments inside Ward Alpha
            { id: "dept-ICU", name: "ICU Department", type: "DEPARTMENT", x: 65, y: 100, w: 320, h: 180 },
            { id: "dept-Cardiology", name: "Cardiology Dept", type: "DEPARTMENT", x: 65, y: 290, w: 320, h: 130 },

            // Department inside Ward Beta
            { id: "dept-Surgery", name: "Surgical Dept", type: "DEPARTMENT", x: 455, y: 100, w: 320, h: 320 },

            // Rooms inside ICU
            { id: "room-101", name: "Room 101", type: "ROOM", x: 80, y: 135, w: 140, h: 130 },
            { id: "room-102", name: "Room 102", type: "ROOM", x: 230, y: 135, w: 140, h: 130 },

            // Room inside Cardiology
            { id: "room-201", name: "Room 201", type: "ROOM", x: 80, y: 325, w: 290, h: 80 },

            // Room inside Surgery
            { id: "room-301", name: "Room 301", type: "ROOM", x: 470, y: 135, w: 290, h: 270 },

            // Beds inside Room 101
            { id: "bed-101A", name: "Bed 101A", type: "BED", x: 90, y: 170, w: 55, h: 75 },
            { id: "bed-101B", name: "Bed 101B", type: "BED", x: 155, y: 170, w: 55, h: 75 },

            // Beds inside Room 102
            { id: "bed-102A", name: "Bed 102A", type: "BED", x: 240, y: 170, w: 55, h: 75 },
            { id: "bed-102B", name: "Bed 102B", type: "BED", x: 305, y: 170, w: 55, h: 75 },

            // Bed inside Room 201
            { id: "bed-201A", name: "Bed 201A", type: "BED", x: 90, y: 345, w: 120, h: 50 },

            // Bed inside Room 301
            { id: "bed-301A", name: "Bed 301A", type: "BED", x: 485, y: 170, w: 120, h: 75 },

            // Clinical Staff Workstations
            { id: "station-1", name: "Nurse Station 1", type: "STATION", x: 100, y: 460, w: 90, h: 45 },
            { id: "station-2", name: "Triage Station", type: "STATION", x: 375, y: 460, w: 90, h: 45 },
            { id: "station-3", name: "Staff Hub", type: "STATION", x: 650, y: 460, w: 90, h: 45 },
        ];

        // Animated Clinical Staff State
        this.staff = {
            "dr-smith":        { id: "dr-smith",        label: "Dr. Smith",   x: 145, y: 482, targetX: 145, targetY: 482, color: "#10b981", isLocked: false },
            "nurse-jones":     { id: "nurse-jones",     label: "Nurse Jones", x: 420, y: 482, targetX: 420, targetY: 482, color: "#059669", isLocked: false },
            "patient-ref-4910":{ id: "patient-ref-4910",label: "Patient 4910",x: 695, y: 482, targetX: 695, targetY: 482, color: "#34d399", isLocked: false },
        };

        this.pulseTime = 0;
        this.setupEvents();
    }

    start() {
        const renderLoop = () => {
            this.pulseTime += 0.05;
            this.updateStaffTargets();
            this.draw();
            this.animFrame = requestAnimationFrame(renderLoop);
        };
        renderLoop();
    }

    updateTreeState(rootNode) {
        this.treeMap.clear();
        this.flattenTree(rootNode);
    }

    flattenTree(node) {
        if (!node) return;
        this.treeMap.set(node.id, node);
        if (node.children) {
            for (const child of node.children) {
                this.flattenTree(child);
            }
        }
    }

    selectNode(nodeId) {
        this.selectedId = nodeId;
    }

    updateStaffTargets() {
        this.staff["dr-smith"].targetX = 145;
        this.staff["dr-smith"].targetY = 482;
        this.staff["dr-smith"].isLocked = false;

        this.staff["nurse-jones"].targetX = 420;
        this.staff["nurse-jones"].targetY = 482;
        this.staff["nurse-jones"].isLocked = false;

        this.staff["patient-ref-4910"].targetX = 695;
        this.staff["patient-ref-4910"].targetY = 482;
        this.staff["patient-ref-4910"].isLocked = false;

        for (const [nodeId, nodeData] of this.treeMap.entries()) {
            if (nodeData.is_locked && nodeData.locked_by && this.staff[nodeData.locked_by]) {
                const reg = this.regions.find(r => r.id === nodeId);
                if (reg) {
                    const st = this.staff[nodeData.locked_by];
                    st.targetX = reg.x + reg.w / 2;
                    st.targetY = reg.y + reg.h / 2;
                    st.isLocked = true;
                }
            }
        }

        for (const sKey in this.staff) {
            const st = this.staff[sKey];
            st.x += (st.targetX - st.x) * 0.08;
            st.y += (st.targetY - st.y) * 0.08;
        }
    }

    draw() {
        const ctx = this.ctx;
        const w = this.canvas.width;
        const h = this.canvas.height;

        ctx.fillStyle = "#064e3b";
        ctx.fillRect(0, 0, w, h);

        this.drawFloorGridPattern(ctx, w, h);

        for (const reg of this.regions) {
            const nodeData = this.treeMap.get(reg.id);
            const isHovered  = this.hoveredId === reg.id;
            const isSelected = this.selectedId === reg.id;

            this.drawSpatialRegion(ctx, reg, nodeData, isHovered, isSelected);
        }

        for (const sKey in this.staff) {
            this.drawStaffIcon(ctx, this.staff[sKey]);
        }
    }

    drawFloorGridPattern(ctx, w, h) {
        ctx.strokeStyle = "rgba(16, 185, 129, 0.15)";
        ctx.lineWidth = 1;

        const gridSize = 30;
        ctx.beginPath();
        for (let x = 0; x < w; x += gridSize) {
            ctx.moveTo(x, 0);
            ctx.lineTo(x, h);
        }
        for (let y = 0; y < h; y += gridSize) {
            ctx.moveTo(0, y);
            ctx.lineTo(w, y);
        }
        ctx.stroke();
    }

    drawSpatialRegion(ctx, reg, nodeData, isHovered, isSelected) {
        const isLocked = nodeData ? nodeData.is_locked : false;
        const isDescLocked = nodeData ? nodeData.locked_descendant_count > 0 : false;

        ctx.save();

        if (isLocked) {
            const pulseGlow = Math.sin(this.pulseTime * 4) * 0.1 + 0.3;
            ctx.fillStyle = `rgba(239, 68, 68, ${pulseGlow})`;
            ctx.strokeStyle = "#ef4444";
            ctx.lineWidth = 2.5;
        } else if (isDescLocked) {
            ctx.fillStyle = "rgba(245, 158, 11, 0.15)";
            ctx.strokeStyle = "#f59e0b";
            ctx.lineWidth = 1.8;
            ctx.setLineDash([4, 4]);
        } else if (reg.type === "STATION") {
            ctx.fillStyle = "rgba(16, 185, 129, 0.2)";
            ctx.strokeStyle = "#10b981";
            ctx.lineWidth = 1;
        } else {
            ctx.fillStyle = "rgba(4, 120, 87, 0.4)";
            ctx.strokeStyle = "rgba(52, 211, 153, 0.3)";
            ctx.lineWidth = 1;
        }

        if (isSelected) {
            ctx.strokeStyle = "#a7f3d0";
            ctx.lineWidth = 3;
        }

        if (isHovered) {
            ctx.shadowColor = "#a7f3d0";
            ctx.shadowBlur = 12;
        }

        ctx.beginPath();
        ctx.roundRect(reg.x, reg.y, reg.w, reg.h, 6);
        ctx.fill();
        ctx.stroke();
        ctx.setLineDash([]);

        if (reg.type !== "BED") {
            ctx.fillStyle = isLocked ? "#fca5a5" : (isDescLocked ? "#fde68a" : "#d1fae5");
            ctx.font = reg.type === "HOSPITAL" ? "bold 11px sans-serif" : (reg.type === "WARD" ? "bold 12px sans-serif" : "bold 10px sans-serif");

            const labelY = reg.y + (reg.type === "HOSPITAL" ? 14 : (reg.type === "WARD" ? 18 : 16));
            ctx.fillText(reg.name, reg.x + 8, labelY);
        } else {
            ctx.fillStyle = isLocked ? "#fca5a5" : "#a7f3d0";
            ctx.font = "bold 9px sans-serif";
            ctx.fillText(reg.name, reg.x + 6, reg.y + 14);
        }

        if (isLocked && nodeData && nodeData.locked_by) {
            ctx.fillStyle = "#ef4444";
            ctx.beginPath();
            ctx.roundRect(reg.x + reg.w - 105, reg.y + 4, 100, 18, 4);
            ctx.fill();

            ctx.fillStyle = "#ffffff";
            ctx.font = "bold 9px monospace";
            const ttlText = nodeData.ttl_remaining > 0 ? `${nodeData.ttl_remaining}s` : "BUSY";
            ctx.fillText(`${nodeData.locked_by} (${ttlText})`, reg.x + reg.w - 101, reg.y + 16);
        }

        ctx.restore();
    }

    drawStaffIcon(ctx, st) {
        ctx.save();

        ctx.fillStyle = st.color;
        ctx.shadowColor = st.color;
        ctx.shadowBlur = st.isLocked ? 16 : 8;

        ctx.beginPath();
        ctx.arc(st.x, st.y, 11, 0, Math.PI * 2);
        ctx.fill();

        ctx.fillStyle = st.isLocked ? "#ef4444" : "#ffffff";
        ctx.beginPath();
        ctx.arc(st.x, st.y, 4, 0, Math.PI * 2);
        ctx.fill();

        ctx.fillStyle = "rgba(6, 78, 59, 0.9)";
        ctx.beginPath();
        ctx.roundRect(st.x - 28, st.y - 25, 56, 14, 3);
        ctx.fill();

        ctx.fillStyle = st.color;
        ctx.font = "bold 8px sans-serif";
        ctx.textAlign = "center";
        ctx.fillText(st.label, st.x, st.y - 15);

        ctx.restore();
    }

    setupEvents() {
        this.canvas.addEventListener("mousemove", (e) => {
            const rect = this.canvas.getBoundingClientRect();
            const scaleX = this.canvas.width / rect.width;
            const scaleY = this.canvas.height / rect.height;

            const mouseX = (e.clientX - rect.left) * scaleX;
            const mouseY = (e.clientY - rect.top) * scaleY;

            let found = null;
            const typePriority = { "BED": 5, "ROOM": 4, "DEPARTMENT": 3, "WARD": 2, "STATION": 2, "HOSPITAL": 1 };

            for (const reg of this.regions) {
                if (mouseX >= reg.x && mouseX <= reg.x + reg.w && mouseY >= reg.y && mouseY <= reg.y + reg.h) {
                    if (!found || typePriority[reg.type] > typePriority[found.type]) {
                        found = reg;
                    }
                }
            }

            if (found) {
                this.hoveredId = found.id;
                this.showTooltip(e, found);
            } else {
                this.hoveredId = null;
                canvasTooltip.classList.add("hidden");
            }
        });

        this.canvas.addEventListener("mouseleave", () => {
            this.hoveredId = null;
            canvasTooltip.classList.add("hidden");
        });

        this.canvas.addEventListener("click", () => {
            if (this.hoveredId) {
                selectedNode = this.hoveredId;
                nodeSelect.value = this.hoveredId;
                renderTree(currentTree);
                this.selectedId = this.hoveredId;
            }
        });
    }

    showTooltip(e, reg) {
        const containerRect = canvasContainer.getBoundingClientRect();
        const mouseX = e.clientX - containerRect.left;
        const mouseY = e.clientY - containerRect.top;

        const nodeData = this.treeMap.get(reg.id);
        const statusText = nodeData ? (nodeData.is_locked ? `Occupied by ${nodeData.locked_by} (${nodeData.ttl_remaining}s)` : (nodeData.locked_descendant_count > 0 ? `Occupied descendants (${nodeData.locked_descendant_count})` : "Available")) : "Available";

        ttTitle.textContent = reg.name;
        ttBody.textContent  = `Type: ${reg.type} | Status: ${statusText}`;

        canvasTooltip.style.left = `${mouseX + 12}px`;
        canvasTooltip.style.top  = `${mouseY + 12}px`;
        canvasTooltip.classList.remove("hidden");
    }
}

// MacWinControl Frontend - Auto-Discovery Edition

const { invoke } = window.__TAURI__.core;

// State
let isServer = false;
let isConnected = false;
let computers = [];
let localScreens = [];
let remoteScreens = [];
let savedLayout = null;  // Saved screen positions {screenId: {x, y}}
let connectionStatus = { is_connected: false, connected_to: null, discovered_peers: [] };

// Load saved layout from localStorage
function loadSavedLayout() {
    try {
        const saved = localStorage.getItem('macwincontrol_layout');
        if (saved) {
            savedLayout = JSON.parse(saved);
            console.log('Loaded saved layout:', savedLayout);
        }
    } catch (e) {
        console.error('Failed to load layout:', e);
    }
}

// Save layout to localStorage
function saveLayout() {
    try {
        localStorage.setItem('macwincontrol_layout', JSON.stringify(savedLayout));
        console.log('Saved layout:', savedLayout);
    } catch (e) {
        console.error('Failed to save layout:', e);
    }
}

// Initialize
document.addEventListener('DOMContentLoaded', async () => {
    loadSavedLayout();
    await loadSystemInfo();
    await loadLocalScreens();
    await loadRemoteScreens();
    await loadConnectionStatus();
    await loadComputers();
    setupNavigation();
    setupEventListeners();
    
    // Poll for updates
    setInterval(loadRemoteScreens, 2000);
    setInterval(loadConnectionStatus, 1000);
    setInterval(loadDebugInfo, 500);  // Debug info polling
});

async function loadConnectionStatus() {
    try {
        connectionStatus = await invoke('get_connection_status');
        updateConnectionUI();
    } catch (err) {
        console.error('Failed to load connection status:', err);
    }
}

function updateConnectionUI() {
    const indicator = document.getElementById('statusIndicator');
    const statusText = document.getElementById('statusText');
    
    if (connectionStatus.is_connected) {
        indicator.className = 'status-indicator connected';
        const peer = connectionStatus.discovered_peers.find(p => p.ip === connectionStatus.connected_to);
        statusText.textContent = peer 
            ? `Connected to ${peer.name}` 
            : `Connected to ${connectionStatus.connected_to}`;
    } else if (connectionStatus.discovered_peers.length > 0) {
        indicator.className = 'status-indicator server';
        statusText.textContent = `Found ${connectionStatus.discovered_peers.length} peer(s), connecting...`;
    } else {
        indicator.className = 'status-indicator';
        statusText.textContent = 'Searching for peers...';
    }
    
    // Update peer list in UI
    renderDiscoveredPeers();
}

async function loadSystemInfo() {
    try {
        const [ip, name, screen] = await Promise.all([
            invoke('get_local_ip'),
            invoke('get_computer_name'),
            invoke('get_screen_info')
        ]);
        
        document.getElementById('localIp').textContent = ip;
        document.getElementById('ipAddress').textContent = ip;
        document.getElementById('computerName').textContent = name;
        document.getElementById('screenSize').textContent = `${screen[0]} x ${screen[1]}`;
    } catch (err) {
        console.error('Failed to load system info:', err);
    }
}

async function loadLocalScreens() {
    try {
        localScreens = await invoke('get_all_screens');
        console.log('Local screens detected:', localScreens);
        renderScreenLayout();
    } catch (err) {
        console.error('Failed to load screens:', err);
        localScreens = [{ name: 'This Mac', x: 0, y: 0, width: 1920, height: 1080, is_primary: true }];
        renderScreenLayout();
    }
}

async function loadRemoteScreens() {
    try {
        remoteScreens = await invoke('get_remote_screens');
        console.log('Remote screens:', remoteScreens);
        if (remoteScreens.length > 0) {
            renderScreenLayout();
        }
    } catch (err) {
        console.error('Failed to load remote screens:', err);
    }
}

async function loadDebugInfo() {
    try {
        const debug = await invoke('get_debug_info');
        document.getElementById('debugMousePos').textContent = `(${debug.mouse_x}, ${debug.mouse_y})`;
        document.getElementById('debugScreenBounds').textContent = debug.screen_bounds || '-';
        document.getElementById('debugEdgeStatus').textContent = debug.edge_status || '-';
        // Use backend count which is more accurate
        document.getElementById('debugRemoteScreens').textContent = `${debug.remote_screen_count} (backend) / ${remoteScreens.length} (frontend)`;
    } catch (err) {
        // Silently ignore
    }
}

function setupNavigation() {
    document.querySelectorAll('.nav-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            document.querySelectorAll('.nav-btn').forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            const page = btn.dataset.page;
            document.querySelectorAll('.page').forEach(p => p.classList.remove('active'));
            document.getElementById(`page-${page}`).classList.add('active');
        });
    });
}

function setupEventListeners() {
    // Auto-discovery handles connection, but keep buttons for manual override
    document.getElementById('btnStartServer').addEventListener('click', async () => {
        updateStatus('server', 'Auto-Discovery Active');
        document.getElementById('btnStartServer').textContent = 'Discovery Active';
        document.getElementById('btnStartServer').disabled = true;
    });
    
    document.getElementById('btnConnect').addEventListener('click', async () => {
        const ip = document.getElementById('serverIp').value.trim();
        if (!ip) { 
            alert('Auto-discovery is active. Just open the app on both computers!'); 
            return; 
        }
        // Manual override if needed
        try {
            await invoke('connect_to_server', { ip });
        } catch (err) {
            console.log('Manual connect (auto-discovery will handle it)');
        }
    });
    
    document.getElementById('btnAddComputer').addEventListener('click', async () => {
        alert('Computers are now discovered automatically! Just open the app on both computers.');
    });
    
    document.getElementById('clipboardSync').addEventListener('change', async (e) => {
        try {
            await invoke('set_clipboard_sync', { enabled: e.target.checked });
        } catch (err) {
            console.error('Failed to update clipboard sync:', err);
        }
    });
    
    // Auto-enable server mode at startup
    setTimeout(() => {
        document.getElementById('btnStartServer').textContent = '✓ Auto-Discovery Active';
        document.getElementById('btnStartServer').disabled = true;
        document.getElementById('btnStartServer').style.backgroundColor = 'var(--success)';
    }, 500);
}

function renderDiscoveredPeers() {
    const container = document.getElementById('computers');
    
    if (connectionStatus.discovered_peers.length === 0) {
        container.innerHTML = `
            <div style="text-align: center; padding: 20px; color: var(--text-light)">
                <p>🔍 Searching for other computers...</p>
                <p style="font-size: 12px; margin-top: 10px;">Open MacWinControl on your other computer</p>
            </div>
        `;
        return;
    }
    
    container.innerHTML = connectionStatus.discovered_peers.map(peer => {
        const isConnectedToPeer = connectionStatus.connected_to === peer.ip;
        const icon = peer.computer_type === 'mac' ? '🍎' : '🪟';
        return `
            <div class="computer-item" style="border-left: 3px solid ${isConnectedToPeer ? 'var(--success)' : 'var(--primary)'}">
                <div class="info">
                    <span class="name">${icon} ${peer.name}</span>
                    <span class="ip">${peer.ip} • ${peer.computer_type}</span>
                </div>
                <span style="color: ${isConnectedToPeer ? 'var(--success)' : 'var(--text-light)'}">
                    ${isConnectedToPeer ? '✓ Connected' : 'Discovered'}
                </span>
            </div>
        `;
    }).join('');
}

function updateStatus(status, text) {
    const indicator = document.getElementById('statusIndicator');
    const statusText = document.getElementById('statusText');
    indicator.className = 'status-indicator';
    if (status === 'connected') indicator.classList.add('connected');
    else if (status === 'server') indicator.classList.add('server');
    statusText.textContent = text;
}

async function loadComputers() {
    try {
        computers = await invoke('get_computers');
        renderComputers();
        renderScreenLayout();
    } catch (err) {
        console.error('Failed to load computers:', err);
    }
}

function renderComputers() {
    const container = document.getElementById('computers');
    if (computers.length === 0) {
        container.innerHTML = '<p style="color: var(--text-light)">No computers added yet</p>';
        return;
    }
    container.innerHTML = computers.map(c => `
        <div class="computer-item">
            <div class="info">
                <span class="name">${c.name}</span>
                <span class="ip">${c.ip} • ${c.position}</span>
            </div>
            <button class="btn danger" onclick="removeComputer('${c.ip}')">Remove</button>
        </div>
    `).join('');
}

function renderScreenLayout() {
    const layout = document.getElementById('screenLayout');
    const containerWidth = 580;
    const containerHeight = 280;
    
    // Initialize saved layout if needed
    if (!savedLayout) {
        savedLayout = {};
    }
    
    let allScreens = [];
    
    // Add local screens - normalize so primary starts at x=0
    const localMinX = localScreens.length > 0 ? Math.min(...localScreens.map(s => s.x)) : 0;
    const localMinY = localScreens.length > 0 ? Math.min(...localScreens.map(s => s.y)) : 0;
    
    localScreens.forEach((s, i) => {
        const id = `local-${i}`;
        allScreens.push({
            id,
            name: s.name,
            x: s.x - localMinX,  // Normalize to start at 0
            y: s.y - localMinY,
            width: s.width,
            height: s.height,
            is_primary: s.is_primary,
            type: 'local',
            label: s.is_primary ? 'This Mac' : `Display ${i + 1}`,
            computerType: 'local',
            draggable: false
        });
    });
    
    // Calculate local bounds after normalization
    const localMaxX = allScreens.length > 0 ? Math.max(...allScreens.map(s => s.x + s.width)) : 0;
    const localMaxY = allScreens.length > 0 ? Math.max(...allScreens.map(s => s.y + s.height)) : 1080;
    
    // Add remote screens - place to the RIGHT of local screens by default
    // Group by computer name
    const remoteByComputer = {};
    remoteScreens.forEach((s, i) => {
        if (!remoteByComputer[s.computer_name]) {
            remoteByComputer[s.computer_name] = [];
        }
        remoteByComputer[s.computer_name].push({ ...s, index: i });
    });
    
    let remoteStartX = localMaxX + 100; // Gap between local and remote
    
    Object.entries(remoteByComputer).forEach(([computerName, screens]) => {
        // Normalize this computer's screens
        const minX = Math.min(...screens.map(s => s.x));
        const minY = Math.min(...screens.map(s => s.y));
        
        screens.forEach((s, idx) => {
            const id = `remote-${computerName}-${s.index}`;
            
            // Check for saved position, otherwise use calculated default
            let screenX, screenY;
            if (savedLayout[id]) {
                screenX = savedLayout[id].x;
                screenY = savedLayout[id].y;
            } else {
                // Place right of local, normalized
                screenX = remoteStartX + (s.x - minX);
                screenY = s.y - minY;
                // Save default
                savedLayout[id] = { x: screenX, y: screenY };
            }
            
            allScreens.push({
                id,
                name: s.name,
                x: screenX,
                y: screenY,
                width: s.width,
                height: s.height,
                is_primary: s.is_primary,
                type: 'remote',
                label: s.is_primary ? computerName : `${computerName} ${idx + 1}`,
                computerType: s.computer_type,
                computerName: computerName,
                draggable: true
            });
        });
        
        // Move start position for next computer
        const maxRemoteX = Math.max(...screens.map(s => s.x - minX + s.width));
        remoteStartX += maxRemoteX + 100;
    });
    
    if (allScreens.length === 0) {
        layout.innerHTML = '<p style="color: var(--text-light); text-align: center; padding: 40px;">No screens detected</p>';
        return;
    }
    
    // Calculate total bounds for scaling
    const minX = Math.min(...allScreens.map(s => s.x));
    const maxX = Math.max(...allScreens.map(s => s.x + s.width));
    const minY = Math.min(...allScreens.map(s => s.y));
    const maxY = Math.max(...allScreens.map(s => s.y + s.height));
    const totalWidth = maxX - minX;
    const totalHeight = maxY - minY;
    
    // Scale to fit container with padding
    const scale = Math.min(
        (containerWidth - 40) / totalWidth,
        (containerHeight - 50) / totalHeight,
        0.15  // Max scale
    );
    
    const innerWidth = totalWidth * scale;
    const innerHeight = totalHeight * scale;
    
    let html = `
        <div class="screen-layout-container" style="
            position: relative;
            width: ${containerWidth}px;
            height: ${containerHeight}px;
            background: linear-gradient(135deg, #f1f5f9 0%, #e2e8f0 100%);
            border-radius: 12px;
            border: 2px solid #cbd5e1;
            overflow: hidden;
        ">
            <div class="screen-layout-inner" id="layoutInner" style="
                position: absolute;
                left: ${(containerWidth - innerWidth) / 2}px;
                top: ${(containerHeight - innerHeight - 20) / 2}px;
                width: ${innerWidth}px;
                height: ${innerHeight}px;
            ">
    `;
    
    allScreens.forEach(screen => {
        const left = (screen.x - minX) * scale;
        const top = (screen.y - minY) * scale;
        const width = Math.max(screen.width * scale, 50);
        const height = Math.max(screen.height * scale, 35);
        
        // Colors
        let bgColor;
        if (screen.type === 'local') {
            bgColor = screen.is_primary ? '#f59e0b' : '#fbbf24';
        } else if (screen.computerType === 'mac') {
            bgColor = screen.is_primary ? '#ec4899' : '#f472b6';
        } else if (screen.computerType === 'windows') {
            bgColor = screen.is_primary ? '#3b82f6' : '#60a5fa';
        } else {
            bgColor = '#10b981';
        }
        
        html += `
            <div class="screen-box ${screen.type}" 
                 data-id="${screen.id}"
                 data-original-x="${screen.x}"
                 data-original-y="${screen.y}"
                 data-scale="${scale}"
                 style="
                    position: absolute;
                    left: ${left}px;
                    top: ${top}px;
                    width: ${width}px;
                    height: ${height}px;
                    background: ${bgColor};
                    border-radius: 5px;
                    display: flex;
                    flex-direction: column;
                    align-items: center;
                    justify-content: center;
                    color: white;
                    cursor: ${screen.draggable ? 'grab' : 'default'};
                    box-shadow: 0 2px 6px rgba(0,0,0,0.2);
                    user-select: none;
                    font-size: 9px;
                    ${screen.draggable ? 'border: 2px dashed rgba(255,255,255,0.5);' : 'border: 1px solid rgba(255,255,255,0.3);'}
                 "
                 ${screen.draggable ? `onmousedown="startDrag(event, '${screen.id}')"` : ''}
            >
                <span style="font-weight: 600; text-shadow: 0 1px 2px rgba(0,0,0,0.3); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; max-width: 90%;">${screen.label}</span>
                <span style="opacity: 0.8; font-size: 8px;">${screen.width}×${screen.height}</span>
            </div>
        `;
    });
    
    html += `
            </div>
            <div style="position: absolute; bottom: 5px; left: 10px; font-size: 9px; color: #64748b;">
                🟡 Local &nbsp; 🩷 Mac &nbsp; 🔵 Windows &nbsp; (drag to reposition)
            </div>
        </div>
    `;
    
    layout.innerHTML = html;
}

function getLocalBounds() {
    if (localScreens.length === 0) return { minX: 0, maxX: 1920, minY: 0, maxY: 1080 };
    return {
        minX: Math.min(...localScreens.map(s => s.x)),
        maxX: Math.max(...localScreens.map(s => s.x + s.width)),
        minY: Math.min(...localScreens.map(s => s.y)),
        maxY: Math.max(...localScreens.map(s => s.y + s.height))
    };
}

function calculateBounds(screens) {
    if (screens.length === 0) return { minX: 0, maxX: 1920, minY: 0, maxY: 1080, width: 1920, height: 1080 };
    const minX = Math.min(...screens.map(s => s.x));
    const maxX = Math.max(...screens.map(s => s.x + s.width));
    const minY = Math.min(...screens.map(s => s.y));
    const maxY = Math.max(...screens.map(s => s.y + s.height));
    return { minX, maxX, minY, maxY, width: maxX - minX, height: maxY - minY };
}

let draggedElement = null;
let dragStartX = 0, dragStartY = 0;
let elemStartX = 0, elemStartY = 0;
let dragScale = 1;

window.startDrag = function(event, screenId) {
    const element = event.target.closest('.screen-box');
    if (!element) return;
    
    // Only allow dragging remote screens
    if (screenId.startsWith('local-')) return;
    
    draggedElement = element;
    dragStartX = event.clientX;
    dragStartY = event.clientY;
    elemStartX = parseInt(element.style.left) || 0;
    elemStartY = parseInt(element.style.top) || 0;
    dragScale = parseFloat(element.dataset.scale) || 0.1;
    
    element.style.cursor = 'grabbing';
    element.style.zIndex = '100';
    element.style.transform = 'scale(1.05)';
    element.style.boxShadow = '0 4px 16px rgba(0,0,0,0.3)';
    
    document.addEventListener('mousemove', onDrag);
    document.addEventListener('mouseup', endDrag);
    event.preventDefault();
};

function onDrag(event) {
    if (!draggedElement) return;
    const dx = event.clientX - dragStartX;
    const dy = event.clientY - dragStartY;
    draggedElement.style.left = `${elemStartX + dx}px`;
    draggedElement.style.top = `${elemStartY + dy}px`;
}

function endDrag(event) {
    if (!draggedElement) return;
    
    const screenId = draggedElement.dataset.id;
    const dx = event.clientX - dragStartX;
    const dy = event.clientY - dragStartY;
    
    // Convert pixel movement back to screen coordinates
    const origX = parseInt(draggedElement.dataset.originalX) || 0;
    const origY = parseInt(draggedElement.dataset.originalY) || 0;
    const newX = origX + Math.round(dx / dragScale);
    const newY = origY + Math.round(dy / dragScale);
    
    // Save the new position
    if (!savedLayout) savedLayout = {};
    savedLayout[screenId] = { x: newX, y: newY };
    saveLayout();
    
    console.log(`Moved ${screenId} to (${newX}, ${newY})`);
    
    // Reset styles
    draggedElement.style.cursor = 'grab';
    draggedElement.style.zIndex = '';
    draggedElement.style.transform = '';
    draggedElement.style.boxShadow = '0 2px 6px rgba(0,0,0,0.2)';
    draggedElement = null;
    
    document.removeEventListener('mousemove', onDrag);
    document.removeEventListener('mouseup', endDrag);
    
    // Re-render with new positions
    renderScreenLayout();
}

window.removeComputer = async function(ip) {
    try {
        await invoke('remove_computer', { ip });
        await loadComputers();
    } catch (err) {
        alert('Failed to remove computer: ' + err);
    }
};

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
    const containerWidth = 600;
    const containerHeight = 300;
    
    // Initialize saved layout if needed
    if (!savedLayout) {
        savedLayout = {};
    }
    
    // Build unified screen layout
    // Local screens get their actual positions
    // Remote screens are placed relative to local screens (right side by default)
    
    let allScreens = [];
    
    // Add local screens with their real coordinates
    localScreens.forEach((s, i) => {
        const id = `local-${i}`;
        allScreens.push({
            id,
            name: s.name,
            x: s.x,
            y: s.y,
            width: s.width,
            height: s.height,
            is_primary: s.is_primary,
            type: 'local',
            label: s.is_primary ? 'This Mac' : `Display ${i + 1}`,
            computerType: 'local'
        });
    });
    
    // Calculate where to place remote screens (right of local by default)
    const localBounds = getLocalBounds();
    const defaultRemoteX = localBounds.maxX + 50;
    
    // Add remote screens with saved or default positions
    remoteScreens.forEach((s, i) => {
        const id = `remote-${s.computer_name}-${i}`;
        
        // Use saved position or calculate default
        let screenX, screenY;
        if (savedLayout[id]) {
            screenX = savedLayout[id].x;
            screenY = savedLayout[id].y;
        } else {
            // Default: place to the right of local screens
            screenX = defaultRemoteX + s.x;
            screenY = s.y;
            // Auto-save default position
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
            label: s.is_primary ? s.computer_name : `${s.computer_name} ${i + 1}`,
            computerType: s.computer_type,
            computerName: s.computer_name
        });
    });
    
    if (allScreens.length === 0) {
        layout.innerHTML = '<p style="color: var(--text-light); text-align: center; padding: 40px;">No screens detected</p>';
        return;
    }
    
    // Calculate bounds & scale
    const bounds = calculateBounds(allScreens);
    const scale = Math.min(
        (containerWidth - 60) / bounds.width,
        (containerHeight - 60) / bounds.height,
        0.15
    );
    
    let html = `
        <div class="screen-layout-container" id="layoutContainer" style="
            position: relative;
            width: ${containerWidth}px;
            height: ${containerHeight}px;
            background: linear-gradient(135deg, #f1f5f9 0%, #e2e8f0 100%);
            border-radius: 12px;
            border: 2px dashed #cbd5e1;
            overflow: visible;
        ">
            <div class="screen-layout-inner" id="layoutInner" style="
                position: absolute;
                left: 50%;
                top: 50%;
                transform: translate(-50%, -50%);
            ">
    `;
    
    allScreens.forEach(screen => {
        const left = (screen.x - bounds.minX) * scale;
        const top = (screen.y - bounds.minY) * scale;
        const width = Math.max(screen.width * scale, 60);
        const height = Math.max(screen.height * scale, 40);
        
        const isLocal = screen.type === 'local';
        
        // Colors
        let bgColor;
        if (isLocal) {
            bgColor = screen.is_primary ? '#f59e0b' : '#fbbf24';
        } else if (screen.computerType === 'mac') {
            bgColor = screen.is_primary ? '#ec4899' : '#f472b6';
        } else if (screen.computerType === 'windows') {
            bgColor = screen.is_primary ? '#3b82f6' : '#60a5fa';
        } else {
            bgColor = '#10b981';
        }
        
        const canDrag = !isLocal;
        
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
                    border-radius: 6px;
                    display: flex;
                    flex-direction: column;
                    align-items: center;
                    justify-content: center;
                    color: white;
                    cursor: ${canDrag ? 'grab' : 'default'};
                    box-shadow: 0 2px 8px rgba(0,0,0,0.2);
                    user-select: none;
                    font-size: 10px;
                    ${canDrag ? 'border: 2px dashed rgba(255,255,255,0.5);' : 'border: 2px solid rgba(255,255,255,0.3);'}
                    transition: box-shadow 0.2s, transform 0.1s;
                 "
                 ${canDrag ? `onmousedown="startDrag(event, '${screen.id}')"` : ''}
            >
                <span style="font-weight: 600; text-shadow: 0 1px 2px rgba(0,0,0,0.3);">${screen.label}</span>
                <span style="opacity: 0.8; font-size: 9px;">${screen.width}×${screen.height}</span>
            </div>
        `;
    });
    
    html += `
            </div>
            <div style="position: absolute; bottom: 6px; left: 10px; font-size: 9px; color: #64748b;">
                🟡 Local &nbsp; 🩷 Mac &nbsp; 🔵 Windows &nbsp; (drag remote screens to position)
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
    draggedElement.style.boxShadow = '0 2px 8px rgba(0,0,0,0.2)';
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

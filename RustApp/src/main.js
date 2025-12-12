// MacWinControl Frontend - Auto-Discovery Edition

const { invoke } = window.__TAURI__.core;

// State
let isServer = false;
let isConnected = false;
let computers = [];
let localScreens = [];
let remoteScreens = [];
let screenPositions = {}; // Store custom positions
let connectionStatus = { is_connected: false, connected_to: null, discovered_peers: [] };

// Initialize
document.addEventListener('DOMContentLoaded', async () => {
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
    
    // Build all screens - local first
    let allScreens = localScreens.map((s, i) => ({
        ...s,
        id: `local-${i}`,
        type: 'local',
        label: s.is_primary ? 'This Mac' : `Display ${i + 1}`,
        computerType: 'local'
    }));
    
    // Add remote screens from connected computers
    const localBounds = getLocalBounds();
    let remoteOffsetX = localBounds.maxX + 200;
    
    remoteScreens.forEach((s, i) => {
        allScreens.push({
            id: `remote-${i}`,
            name: s.name,
            x: remoteOffsetX + s.x,
            y: s.y,
            width: s.width,
            height: s.height,
            is_primary: s.is_primary,
            type: 'remote',
            label: s.is_primary ? s.computer_name : `${s.computer_name} - ${s.name}`,
            computerType: s.computer_type,
            computerName: s.computer_name
        });
    });
    
    // Also add manually added computers (for backward compatibility)
    computers.forEach((c, i) => {
        // Skip if we already have remote screens from this computer
        if (remoteScreens.some(s => s.computer_name === c.name)) return;
        
        let x, y;
        if (c.position === 'left') {
            x = localBounds.minX - 2100 - (i * 100);
            y = 0;
        } else if (c.position === 'right') {
            x = localBounds.maxX + 100 + (i * 100);
            y = 0;
        } else if (c.position === 'top') {
            x = 0;
            y = localBounds.minY - 1200;
        } else {
            x = 0;
            y = localBounds.maxY + 100;
        }
        
        allScreens.push({
            id: `manual-${i}`,
            name: c.name,
            ip: c.ip,
            x: screenPositions[`manual-${i}`]?.x ?? x,
            y: screenPositions[`manual-${i}`]?.y ?? y,
            width: c.screen_width || 1920,
            height: c.screen_height || 1080,
            type: 'manual',
            label: c.name,
            position: c.position,
            computerType: 'unknown'
        });
    });
    
    // Calculate bounds & scale
    const bounds = calculateBounds(allScreens);
    const scale = Math.min(
        (containerWidth - 80) / bounds.width,
        (containerHeight - 80) / bounds.height,
        0.12
    );
    
    let html = `
        <div class="screen-layout-container" id="layoutContainer" style="
            position: relative;
            width: ${containerWidth}px;
            height: ${containerHeight}px;
            background: linear-gradient(135deg, #f1f5f9 0%, #e2e8f0 100%);
            border-radius: 12px;
            border: 2px dashed #cbd5e1;
            overflow: hidden;
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
        const width = Math.max(screen.width * scale, 80);
        const height = Math.max(screen.height * scale, 50);
        
        const isLocal = screen.type === 'local';
        const isRemote = screen.type === 'remote';
        
        // Colors: local=gold/purple, remote mac=pink, remote windows=blue
        let bgColor;
        if (isLocal) {
            bgColor = screen.is_primary ? '#f59e0b' : '#fbbf24';  // Gold for local
        } else if (screen.computerType === 'mac') {
            bgColor = screen.is_primary ? '#ec4899' : '#f472b6';  // Pink for remote Mac
        } else if (screen.computerType === 'windows') {
            bgColor = screen.is_primary ? '#3b82f6' : '#60a5fa';  // Blue for remote Windows
        } else {
            bgColor = '#10b981';  // Green for unknown/manual
        }
        
        const canDrag = !isLocal;
        
        html += `
            <div class="screen-box ${screen.type}" 
                 data-id="${screen.id}"
                 style="
                    position: absolute;
                    left: ${left}px;
                    top: ${top}px;
                    width: ${width}px;
                    height: ${height}px;
                    background: ${bgColor};
                    border-radius: 8px;
                    display: flex;
                    flex-direction: column;
                    align-items: center;
                    justify-content: center;
                    color: white;
                    cursor: ${canDrag ? 'grab' : 'default'};
                    box-shadow: 0 2px 8px rgba(0,0,0,0.15);
                    user-select: none;
                    ${canDrag ? 'border: 2px dashed rgba(255,255,255,0.5);' : 'border: 2px solid rgba(255,255,255,0.3);'}
                 "
                 ${canDrag ? `onmousedown="startDrag(event, '${screen.id}')"` : ''}
            >
                <span style="font-size: 11px; font-weight: 600; text-shadow: 0 1px 2px rgba(0,0,0,0.2);">${screen.label}</span>
                <span style="font-size: 9px; opacity: 0.8;">${screen.width}×${screen.height}</span>
                ${screen.computerType && screen.computerType !== 'local' ? `<span style="font-size: 8px; opacity: 0.7; margin-top: 2px;">${screen.computerType === 'mac' ? '🍎' : '🪟'}</span>` : ''}
            </div>
        `;
    });
    
    html += `
            </div>
            <div style="position: absolute; bottom: 8px; left: 12px; font-size: 10px; color: #64748b;">
                🟡 Lokaal &nbsp;&nbsp; 🩷 Mac &nbsp;&nbsp; 🔵 Windows &nbsp;&nbsp; (versleep om positie aan te passen)
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

window.startDrag = function(event, screenId) {
    if (!screenId.startsWith('remote-')) return;
    
    const element = event.target.closest('.screen-box');
    if (!element) return;
    
    draggedElement = element;
    dragStartX = event.clientX;
    dragStartY = event.clientY;
    elemStartX = parseInt(element.style.left) || 0;
    elemStartY = parseInt(element.style.top) || 0;
    
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
    const remoteIndex = parseInt(screenId.replace('remote-', ''));
    
    // Calculate relative position to determine left/right
    const container = document.getElementById('layoutInner');
    const elemRect = draggedElement.getBoundingClientRect();
    const containerRect = container.getBoundingClientRect();
    const centerX = containerRect.left + containerRect.width / 2;
    
    if (computers[remoteIndex]) {
        computers[remoteIndex].position = elemRect.left < centerX ? 'left' : 'right';
        // Update dropdown if visible
        const posSelect = document.getElementById('newComputerPosition');
        if (posSelect) posSelect.value = computers[remoteIndex].position;
    }
    
    // Save position offset
    screenPositions[screenId] = {
        offsetX: parseInt(draggedElement.style.left) - elemStartX,
        offsetY: parseInt(draggedElement.style.top) - elemStartY
    };
    
    draggedElement.style.cursor = 'grab';
    draggedElement.style.zIndex = '';
    draggedElement.style.transform = '';
    draggedElement.style.boxShadow = '0 2px 8px rgba(0,0,0,0.15)';
    draggedElement = null;
    
    document.removeEventListener('mousemove', onDrag);
    document.removeEventListener('mouseup', endDrag);
    
    // Re-render to update position label
    setTimeout(renderScreenLayout, 100);
}

window.removeComputer = async function(ip) {
    try {
        await invoke('remove_computer', { ip });
        await loadComputers();
    } catch (err) {
        alert('Failed to remove computer: ' + err);
    }
};

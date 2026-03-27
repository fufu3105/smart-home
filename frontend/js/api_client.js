(function () {
  const DEFAULT_ORIGIN = 'http://127.0.0.1:5000';
  const TOKEN_KEY = 'sh_token';
  const USER_KEY = 'sh_user';

  const origin =
    window.location.protocol === 'file:' ? DEFAULT_ORIGIN : window.location.origin || DEFAULT_ORIGIN;
  const API_BASE = `${origin}/api`;

  const state = {
    devices: [],
    scenes: [],
    logs: [],
    sensors: [],
    users: [],
    lightLevels: {},
  };
  const DEVICE_POLL_MS = 3000;
  let devicePollHandle = null;
  let logStreamHandle = null;

  function escapeHtml(value) {
    return String(value || '').replace(/[&<>"']/g, (char) => {
      return {
        '&': '&amp;',
        '<': '&lt;',
        '>': '&gt;',
        '"': '&quot;',
        "'": '&#39;',
      }[char];
    });
  }

  function isLoginPage() {
    return window.location.pathname.toLowerCase().endsWith('/pages/login.html');
  }

  function pageHref(pageName) {
    if (window.location.protocol === 'file:') {
      const inPages = window.location.pathname.toLowerCase().includes('/pages/');
      if (pageName === 'index.html') return inPages ? '../index.html' : 'index.html';
      return inPages ? pageName : `pages/${pageName}`;
    }

    if (pageName === 'index.html') return '/';
    return `/pages/${pageName}`;
  }

  function getToken() {
    return localStorage.getItem(TOKEN_KEY) || '';
  }

  function getStoredUser() {
    try {
      return JSON.parse(localStorage.getItem(USER_KEY) || 'null');
    } catch (_error) {
      return null;
    }
  }

  function setSession(token, user) {
    if (token) localStorage.setItem(TOKEN_KEY, token);
    if (user) localStorage.setItem(USER_KEY, JSON.stringify(user));
  }

  function clearSession() {
    localStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem(USER_KEY);
  }

  async function request(path, options = {}) {
    const headers = new Headers(options.headers || {});
    if (!headers.has('Content-Type') && options.body && !(options.body instanceof FormData)) {
      headers.set('Content-Type', 'application/json');
    }

    const token = getToken();
    if (token && !headers.has('Authorization')) {
      headers.set('Authorization', `Bearer ${token}`);
    }

    const response = await fetch(`${API_BASE}${path}`, {
      ...options,
      headers,
    });

    const rawText = await response.text();
    let payload = {};
    if (rawText) {
      try {
        payload = JSON.parse(rawText);
      } catch (_error) {
        payload = { raw: rawText };
      }
    }

    if (!response.ok) {
      const error = new Error(payload.error || payload.raw || `HTTP ${response.status}`);
      error.status = response.status;
      error.payload = payload;
      throw error;
    }

    return payload;
  }

  function bindLogout() {
    const logoutBtn = document.getElementById('logout-btn');
    if (!logoutBtn || logoutBtn.dataset.bound === 'true') return;
    logoutBtn.dataset.bound = 'true';
    logoutBtn.addEventListener('click', () => {
      clearSession();
      window.location.href = pageHref('login.html');
    });
  }

  function ensureAuthenticated() {
    if (isLoginPage()) return;
    if (getToken()) return;
    window.location.href = pageHref('login.html');
  }

  function updateUserUi() {
    const user = getStoredUser();
    if (!user) return;

    const displayName = user.full_name || user.username || 'User';
    const avatarText = displayName
      .split(/\s+/)
      .map((part) => part[0])
      .join('')
      .slice(0, 2)
      .toUpperCase();

    const nameElement = document.getElementById('user-name');
    if (nameElement) nameElement.textContent = displayName;

    const avatarElement = document.getElementById('avatar');
    if (avatarElement) avatarElement.textContent = avatarText;

    document.querySelectorAll('.user-profile').forEach((profile) => {
      const avatar = profile.querySelector('.avatar');
      if (avatar && avatar.id !== 'avatar') avatar.textContent = avatarText;

      const textNode = Array.from(profile.querySelectorAll('span')).find((element) => element.id !== 'user-name');
      if (textNode) textNode.textContent = displayName;
    });

    const heroTitle = document.querySelector('.hero-text h2');
    if (heroTitle) heroTitle.textContent = `Hello, ${displayName}!`;
  }

  function getDeviceKind(deviceKey) {
    if (deviceKey === 'door_main') return 'door';
    if (deviceKey.includes('fan')) return 'fan';
    if (deviceKey.includes('lcd')) return 'lcd';
    if (deviceKey.includes('alarm')) return 'alarm';
    return 'light';
  }

  function getRoomLabel(roomKey) {
    return {
      living: 'Living Room',
      kitchen: 'Kitchen',
      bedroom: 'Bedroom',
      entrance: 'Entrance',
    }[roomKey] || roomKey;
  }

  function normalizeLogStatus(status) {
    const normalized = String(status || '').toLowerCase();
    if (normalized === 'success' || normalized === 'ok') return { label: 'OK', color: '#34c759' };
    if (normalized === 'failed' || normalized === 'error') return { label: 'FAILED', color: '#ff3b30' };
    return { label: 'PENDING', color: '#f0ad4e' };
  }

  function hasDeviceUi() {
    return Boolean(document.getElementById('full-devices-list') || document.getElementById('house-map'));
  }

  function getDeviceByKey(deviceKey) {
    return state.devices.find((device) => device.key === deviceKey) || null;
  }

  function clampPercent(value, fallback = 0) {
    const parsed = parseInt(value, 10);
    if (Number.isNaN(parsed)) return fallback;
    return Math.max(0, Math.min(100, parsed));
  }

  function getLightLevel(deviceKey) {
    const device = getDeviceByKey(deviceKey);
    const persistedLevel = clampPercent(device?.state?.level, NaN);
    if (!Number.isNaN(persistedLevel)) return persistedLevel;

    const rememberedLevel = clampPercent(state.lightLevels[deviceKey], NaN);
    if (!Number.isNaN(rememberedLevel)) return rememberedLevel;

    return device?.is_on ? 100 : 0;
  }

  function setDeviceStateLocal(deviceState) {
    if (!deviceState || !deviceState.device_key) return;
    const target = getDeviceByKey(deviceState.device_key);
    if (!target) return;
    target.is_on = Boolean(deviceState.is_on);
    target.state = { ...(target.state || {}), ...(deviceState.state || {}) };

    if (getDeviceKind(deviceState.device_key) === 'light') {
      const explicitLevel = clampPercent(deviceState.state?.level, NaN);
      if (!Number.isNaN(explicitLevel)) {
        state.lightLevels[deviceState.device_key] = explicitLevel;
      } else if (!target.is_on && state.lightLevels[deviceState.device_key] == null) {
        state.lightLevels[deviceState.device_key] = 0;
      }
    }
  }

  function updateActiveCount() {
    const container = document.getElementById('full-devices-list');
    const meta = document.getElementById('devices-active-meta');
    if (!container || !meta) return;

    const total = container.querySelectorAll('input[type="checkbox"]').length;
    const active = container.querySelectorAll('input[type="checkbox"]:checked').length;
    meta.textContent = `${active} / ${total} active`;
  }

  function renderRoomSummary(devices) {
    const container = document.getElementById('room-summary');
    if (!container) return;

    const grouped = {};
    devices.forEach((device) => {
      grouped[device.room] = grouped[device.room] || [];
      grouped[device.room].push(device);
    });

    container.innerHTML = Object.keys(grouped)
      .map((roomKey) => {
        const roomDevices = grouped[roomKey];
        const active = roomDevices.filter((device) => device.is_on).length;
        return `
          <div style="flex:1;background:#fff;border-radius:10px;padding:12px;box-shadow:0 6px 18px rgba(0,0,0,0.04);">
            <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px">
              <strong>${escapeHtml(getRoomLabel(roomKey))}</strong>
              <span style="font-size:12px;color:#666">${active}/${roomDevices.length}</span>
            </div>
            <div style="font-size:12px;color:#777">${roomDevices
              .map((device) => `<span style="margin-right:6px">${escapeHtml(device.name)}</span>`)
              .join('')}</div>
          </div>
        `;
      })
      .join('\n');
  }

  function renderDevices(devices) {
    const container = document.getElementById('full-devices-list');
    if (!container) return;

    const iconByKind = {
      light: 'far fa-lightbulb',
      fan: 'fas fa-fan',
      lcd: 'fas fa-desktop',
      door: 'fas fa-door-closed',
      alarm: 'fas fa-bell',
    };

    container.innerHTML = devices
      .map((device) => {
        const kind = getDeviceKind(device.key);
        return `
          <div class="device-item" data-device="${escapeHtml(device.key)}" data-device-type="${escapeHtml(
            kind
          )}" data-room="${escapeHtml(device.room)}" style="opacity:${device.is_on ? '1' : '0.6'};">
            <div class="device-icon ${kind === 'lcd' ? 'screen' : kind}">
              <i class="${iconByKind[kind]}"></i>
            </div>
            <div class="device-info">
              <span class="device-name">${escapeHtml(device.name)}</span>
              <label class="switch" onclick="event.stopPropagation()">
                <input type="checkbox" ${device.is_on ? 'checked' : ''}>
                <span class="slider"></span>
              </label>
            </div>
          </div>
        `;
      })
      .join('\n');

    renderRoomSummary(devices);
    updateActiveCount();
    updateAllRoomHighlights();

    const selectedDeviceKey = window.__selectedDeviceKey;
    if (selectedDeviceKey) {
      const item = container.querySelector(`.device-item[data-device="${selectedDeviceKey}"]`);
      if (item) item.classList.add('selected');
      if (typeof window.__refreshSelectedDevicePanel === 'function') {
        window.__refreshSelectedDevicePanel(selectedDeviceKey);
      }
    }
  }

  function renderMembers(users) {
    const fullList = document.getElementById('full-members-list');
    if (fullList) {
      fullList.innerHTML = users
        .map((user) => {
          const initials = (user.full_name || user.username || 'U')
            .split(/\s+/)
            .map((part) => part[0])
            .join('')
            .slice(0, 2)
            .toUpperCase();

          return `
            <div class="device-item member-card-item" data-user="${escapeHtml(
              user.username
            )}" data-full-name="${escapeHtml(user.full_name || user.username)}" data-role="${escapeHtml(user.role)}">
              <div class="avatar-circle bg-purple-light" style="width: 50px; height: 50px; font-size: 20px; flex-shrink: 0; margin: 0;">${escapeHtml(
                initials
              )}</div>
              <div class="device-info">
                <span class="device-name" style="font-size: 15px;">${escapeHtml(user.full_name || user.username)}</span>
                <span style="font-size: 11px; font-weight: bold; color: #6a4cff;">${escapeHtml(
                  String(user.role || 'resident').toUpperCase()
                )}</span>
              </div>
            </div>
          `;
        })
        .join('\n');
    }

    const compactList = document.getElementById('members-compact-list');
    if (compactList) {
      compactList.innerHTML = users
        .slice(0, 4)
        .map((user) => {
          const initials = (user.full_name || user.username || 'U')
            .split(/\s+/)
            .map((part) => part[0])
            .join('')
            .slice(0, 2)
            .toUpperCase();
          return `
            <div class="list-item" style="background: #f8f9fc; margin-bottom: 8px;">
              <div style="display: flex; align-items: center; gap: 12px;">
                <div class="avatar-circle bg-purple-light" style="width: 36px; height: 36px; font-size: 14px;">${escapeHtml(
                  initials
                )}</div>
                <div>
                  <h4 style="margin: 0; font-size: 13px; color: #333;">${escapeHtml(
                    user.full_name || user.username
                  )}</h4>
                  <span style="font-size: 10px; color: #6a4cff; font-weight: bold;">${escapeHtml(
                    String(user.role || 'resident').toUpperCase()
                  )}</span>
                </div>
              </div>
              <div style="width: 8px; height: 8px; border-radius: 50%; background: #34c759;"></div>
            </div>
          `;
        })
        .join('\n');
    }
  }

  function renderLogs(logs) {
    ['access-log-list', 'device-log-list'].forEach((id) => {
      const container = document.getElementById(id);
      if (!container) return;

      container.innerHTML = logs
        .map((log) => {
          const status = normalizeLogStatus(log.status);
          return `
            <div class="list-item" style="border-bottom: 1px solid #f0f0f5; padding-bottom: 10px; margin-bottom: 10px;">
              <div style="display: flex; align-items: center; gap: 12px;">
                <i class="fas fa-check-circle" style="color: ${status.color}; font-size: 18px;"></i>
                <div>
                  <h4 style="margin: 0; font-size: 13px; color: #333;">${escapeHtml(log.device_name || 'Unknown')}</h4>
                  <span style="font-size: 11px; color: #999;">${escapeHtml(log.action || '')}</span>
                </div>
              </div>
              <span style="font-size: 11px; color: #999; font-weight: 500;">${escapeHtml(log.timestamp || '')}</span>
            </div>
          `;
        })
        .join('\n');
    });
  }

  function prependLog(log) {
    ['access-log-list', 'device-log-list'].forEach((id) => {
      const container = document.getElementById(id);
      if (!container) return;

      const status = normalizeLogStatus(log.status);
      const wrapper = document.createElement('div');
      wrapper.className = 'list-item';
      wrapper.style = 'border-bottom: 1px solid #f0f0f5; padding-bottom: 10px; margin-bottom: 10px;';
      wrapper.innerHTML = `
        <div style="display: flex; align-items: center; gap: 12px;">
          <i class="fas fa-check-circle" style="color: ${status.color}; font-size: 18px;"></i>
          <div>
            <h4 style="margin: 0; font-size: 13px; color: #333;">${escapeHtml(log.device_name || 'Unknown')}</h4>
            <span style="font-size: 11px; color: #999;">${escapeHtml(log.action || '')}</span>
          </div>
        </div>
        <span style="font-size: 11px; color: #999; font-weight: 500;">${escapeHtml(log.timestamp || '')}</span>
      `;
      container.insertBefore(wrapper, container.firstChild);
    });
  }

  function renderSensors(sensors) {
    if (!Array.isArray(sensors) || sensors.length === 0) return;
    const latest = sensors[0];
    const cards = document.querySelectorAll('.sensors-grid .sensor-card h3');
    if (cards.length >= 3) {
      cards[0].textContent = `${latest.temperature}°C`;
      cards[1].textContent = `${latest.humidity}%`;
      cards[2].textContent = `${latest.gas_level} ppm`;
    }
  }

  function bindSceneMetadata() {
    const sceneKeyByMode = {
      home: 'home_mode',
      sleep: 'sleep_mode',
      away: 'away_mode',
      party: 'party_mode',
    };

    document.querySelectorAll('.card-modes .mode-btn').forEach((button) => {
      const text = button.textContent.toLowerCase();
      Object.keys(sceneKeyByMode).forEach((mode) => {
        if (text.includes(mode)) button.dataset.sceneKey = sceneKeyByMode[mode];
      });
    });

    document.querySelectorAll('#full-modes-list .mode-card-item').forEach((card) => {
      const mode = (card.dataset.mode || '').toLowerCase();
      if (sceneKeyByMode[mode]) card.dataset.sceneKey = sceneKeyByMode[mode];
    });
  }

  async function fetchLogs() {
    state.logs = await request('/logs');
    renderLogs(state.logs);
    return state.logs;
  }

  async function fetchSensors() {
    state.sensors = await request('/sensor/latest');
    renderSensors(state.sensors);
    return state.sensors;
  }

  async function fetchDevices() {
    state.devices = await request('/devices');
    renderDevices(state.devices);
    bindSceneMetadata();
    return state.devices;
  }

  function deviceSnapshotSignature(devices) {
    return JSON.stringify(
      (devices || []).map((device) => ({
        key: device.key,
        is_on: Boolean(device.is_on),
        state: device.state || {},
      }))
    );
  }

  async function refreshDevicesInBackground() {
    const nextDevices = await request('/devices');
    if (deviceSnapshotSignature(nextDevices) === deviceSnapshotSignature(state.devices)) {
      return state.devices;
    }

    state.devices = nextDevices;
    renderDevices(state.devices);
    bindSceneMetadata();
    return state.devices;
  }

  async function fetchMembers() {
    state.users = await request('/users');
    renderMembers(state.users);
    return state.users;
  }

  async function fetchScenes() {
    state.scenes = await request('/scenes?active_only=true');
    bindSceneMetadata();
    return state.scenes;
  }

  async function fetchSceneDetail(sceneKey) {
    return request(`/scenes/${encodeURIComponent(sceneKey)}`);
  }

  async function controlDevice(deviceKey, command) {
    const payload = await request('/devices/control', {
      method: 'POST',
      body: JSON.stringify({ device_key: deviceKey, command }),
    });

    if (getDeviceKind(deviceKey) === 'light') {
      const numericCommand = clampPercent(command, NaN);
      if (!Number.isNaN(numericCommand)) {
        state.lightLevels[deviceKey] = numericCommand;
      } else if (String(command || '').trim().toLowerCase() === 'on' && state.lightLevels[deviceKey] == null) {
        state.lightLevels[deviceKey] = 100;
      }
    }

    if (payload.device_state) {
      setDeviceStateLocal(payload.device_state);
      syncDeviceStateInDom(payload.device_state);
    }

    window.setTimeout(() => {
      refreshDevicesInBackground().catch(() => {});
    }, 150);

    return payload;
  }

  async function activateScene(sceneKey) {
    const payload = await request('/scenes/activate', {
      method: 'POST',
      body: JSON.stringify({ scene_key: sceneKey }),
    });

    (payload.results || []).forEach((result) => {
      if (result.device_state) {
        setDeviceStateLocal(result.device_state);
        syncDeviceStateInDom(result.device_state);
      }
    });

    window.setTimeout(() => {
      refreshDevicesInBackground().catch(() => {});
    }, 150);

    return payload;
  }

  function checkboxCommand(deviceKey, checked) {
    if (deviceKey === 'door_main') return checked ? 'unlock' : 'lock';
    return checked ? 'on' : 'off';
  }

  function syncDeviceStateInDom(deviceState) {
    if (!deviceState || !deviceState.device_key) return;

    const item = document.querySelector(`.device-item[data-device="${deviceState.device_key}"]`);
    if (item) {
      const checkbox = item.querySelector('input[type="checkbox"]');
      if (checkbox) checkbox.checked = Boolean(deviceState.is_on);
      item.style.opacity = deviceState.is_on ? '1' : '0.6';
    }

    updateActiveCount();
    renderRoomSummary(state.devices);
    updateAllRoomHighlights();

    if (typeof window.__refreshSelectedDevicePanel === 'function') {
      window.__refreshSelectedDevicePanel(deviceState.device_key);
    }
  }

  function initLogStream() {
    if (logStreamHandle) return;

    try {
      const stream = new EventSource(`${API_BASE}/stream/logs`);
      logStreamHandle = stream;
      stream.onmessage = (event) => {
        try {
          const payload = JSON.parse(event.data);
          prependLog(payload);
          if (['mqtt_sync', 'control_device', 'scene_activated'].includes(String(payload.action || '').toLowerCase())) {
            refreshDevicesInBackground().catch(() => {});
          }
        } catch (_error) {
          console.warn('Could not parse log stream payload');
        }
      };
      stream.onerror = () => {
        if (hasDeviceUi()) {
          refreshDevicesInBackground().catch(() => {});
        }
      };
    } catch (_error) {
      console.warn('Log stream unavailable');
    }
  }

  function initDevicePolling() {
    if (!hasDeviceUi() || devicePollHandle) return;

    devicePollHandle = window.setInterval(() => {
      refreshDevicesInBackground().catch(() => {});
    }, DEVICE_POLL_MS);
  }

  function initDeviceSyncTriggers() {
    if (!hasDeviceUi()) return;

    window.addEventListener('focus', () => {
      refreshDevicesInBackground().catch(() => {});
    });

    document.addEventListener('visibilitychange', () => {
      if (document.visibilityState === 'visible') {
        refreshDevicesInBackground().catch(() => {});
      }
    });
  }

  function updateAllRoomHighlights() {
    const map = {};
    state.devices.forEach((device) => {
      map[device.room] = map[device.room] || [];
      map[device.room].push(device);
    });

    Object.keys(map).forEach((roomKey) => {
      const rectId = roomKey === 'entrance' ? 'room-door' : `room-${roomKey}`;
      const rect = document.getElementById(rectId);
      if (!rect) return;
      const anyOn = map[roomKey].some((device) => device.is_on);
      rect.setAttribute('fill', anyOn ? '#fff9e6' : '#f8f8fb');
      rect.setAttribute('stroke', anyOn ? '#ffde7a' : '#e8e8ef');
    });

    const legend = document.getElementById('house-map-legend');
    if (legend) {
      legend.innerHTML = Object.keys(map)
        .map((roomKey) => {
          return `<div style="display:flex;justify-content:space-between;align-items:center"><div>${escapeHtml(
            getRoomLabel(roomKey)
          )}</div><div style="font-size:12px;color:#777">${map[roomKey]
            .map((device) => escapeHtml(device.name))
            .join(', ')}</div></div>`;
        })
        .join('\n');
    }
  }

  async function houseMapToggle(roomKey) {
    const targetRoom = roomKey === 'door' ? 'entrance' : roomKey;
    const roomDevices = state.devices.filter((device) => device.room === targetRoom);
    if (roomDevices.length === 0) return;

    const shouldTurnOn = roomDevices.some((device) => !device.is_on);
    for (const device of roomDevices) {
      const command = checkboxCommand(device.key, shouldTurnOn);
      await controlDevice(device.key, command);
    }
  }

  async function bootstrap() {
    if (!isLoginPage()) ensureAuthenticated();
    updateUserUi();
    bindLogout();
    bindSceneMetadata();

    const tasks = [];
    if (document.querySelector('.sensors-grid')) tasks.push(fetchSensors().catch(console.error));
    if (document.getElementById('full-devices-list') || document.getElementById('house-map')) {
      tasks.push(fetchDevices().catch(console.error));
    }
    if (document.getElementById('full-members-list') || document.getElementById('members-compact-list')) {
      tasks.push(fetchMembers().catch(console.error));
    }
    if (document.querySelector('.card-modes .mode-btn') || document.getElementById('full-modes-list')) {
      tasks.push(fetchScenes().catch(console.error));
    }
    if (document.getElementById('device-log-list') || document.getElementById('access-log-list')) {
      tasks.push(fetchLogs().catch(console.error));
    }

    await Promise.all(tasks);
    initLogStream();
    initDeviceSyncTriggers();
    initDevicePolling();
  }

  window.smartHomeApp = {
    API_BASE,
    state,
    pageHref,
    getToken,
    getStoredUser,
    setSession,
    clearSession,
    request,
    getDeviceKind,
    getDeviceByKey,
    getLightLevel,
    getRoomLabel,
    checkboxCommand,
    fetchSceneDetail,
    fetchScenes,
    fetchDevices,
    refreshDevicesInBackground,
    fetchMembers,
    fetchSensors,
    fetchLogs,
    controlDevice,
    activateScene,
    syncDeviceStateInDom,
    updateActiveCount,
    updateAllRoomHighlights,
    houseMapToggle,
    normalizeLogStatus,
    escapeHtml,
  };

  window.apiClient = window.smartHomeApp;
  window.houseMapToggle = houseMapToggle;
  window.updateAllRoomHighlights = updateAllRoomHighlights;

  document.addEventListener('DOMContentLoaded', bootstrap);
})();

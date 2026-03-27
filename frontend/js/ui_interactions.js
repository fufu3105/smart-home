document.addEventListener('DOMContentLoaded', () => {
  const app = window.smartHomeApp;
  let selectedDeviceKey = null;

  function toggleAlertsDropdown() {
    const bellIcon = document.getElementById('bell-icon');
    const alertsDropdown = document.getElementById('alerts-dropdown');
    if (!bellIcon || !alertsDropdown) return;

    bellIcon.addEventListener('click', (event) => {
      event.stopPropagation();
      alertsDropdown.classList.toggle('hidden');
    });

    document.addEventListener('click', (event) => {
      if (!bellIcon.contains(event.target) && !alertsDropdown.contains(event.target)) {
        alertsDropdown.classList.add('hidden');
      }
    });
  }

  function setSelectedDevice(deviceKey) {
    selectedDeviceKey = deviceKey;
    window.__selectedDeviceKey = deviceKey;
    document.querySelectorAll('#full-devices-list .device-item').forEach((item) => {
      item.classList.toggle('selected', item.dataset.device === deviceKey);
    });
  }

  function findDevice(deviceKey) {
    return app.getDeviceByKey(deviceKey) || {
      key: deviceKey,
      name: deviceKey,
      state: {},
      is_on: false,
    };
  }

  function renderDevicePanel(deviceKey) {
    const controlPanel = document.getElementById('main-control-panel');
    if (!controlPanel) return;

    const device = findDevice(deviceKey);
    const kind = app.getDeviceKind(deviceKey);
    const isOn = Boolean(device.is_on);
    const deviceName = device.name || deviceKey;
    const lightLevel = kind === 'light' ? app.getLightLevel(deviceKey) : 0;
    const fanSpeed = parseInt(device.state?.speed || (isOn ? '100' : '0'), 10) || 0;
    const lcdMessage = device.state?.message || '';
    const doorUnlocked = device.state?.lock === 'unlocked';

    const headers = {
      light: { icon: 'far fa-lightbulb', color: '#fce14b', title: 'Light Brightness' },
      fan: { icon: 'fas fa-fan', color: '#a05ef8', title: 'Fan Speed' },
      lcd: { icon: 'fas fa-desktop', color: '#499dff', title: 'LCD Display' },
      door: { icon: 'fas fa-door-closed', color: '#a46016', title: 'Smart Door' },
      alarm: { icon: 'fas fa-bell', color: '#ff4f53', title: 'Security Alarm' },
    };

    const header = headers[kind];
    const switchState = kind === 'door' ? doorUnlocked : isOn;
    const stateText = switchState ? 'ON' : 'OFF';

    const renderHeader = () => `
      <div style="display: flex; justify-content: space-between; align-items: center; width: 100%;">
        <div style="display: flex; align-items: center; gap: 12px;">
          <div style="width: 35px; height: 35px; border-radius: 50%; background-color: ${header.color}20; display: flex; justify-content: center; align-items: center; color: ${header.color}; font-size: 16px;">
            <i class="${header.icon}"></i>
          </div>
          <div>
            <h2 style="margin: 0; color: #6a4cff; font-size: 18px; font-weight: 600;">${deviceName}</h2>
            <div style="font-size: 12px; color: #888;">${header.title}</div>
          </div>
        </div>
        <div style="display: flex; align-items: center; gap: 10px;">
          <span id="panel-state-text" style="font-weight: bold; font-size: 14px; color: #333;">${stateText}</span>
          <label class="switch" onclick="event.stopPropagation()">
            <input type="checkbox" id="panel-toggle-switch" ${switchState ? 'checked' : ''}>
            <span class="slider"></span>
          </label>
        </div>
      </div>
    `;

    let html = '';
    if (kind === 'light') {
      html = `
        <div style="display:flex;flex-direction:column;width:100%;height:100%;">
          ${renderHeader()}
          <div style="flex:1;display:flex;flex-direction:column;justify-content:center;align-items:center;width:100%;margin-top:20px;">
            <div class="thermostat-wrapper" style="gap: 30px;">
              <button class="btn-round decrease" id="btn-decrease"><i class="fas fa-minus"></i></button>
              <div class="thermostat-circle" id="dynamic-circle" style="--ring-color: #fce14b; --progress:${lightLevel}%; width: 220px; height: 220px;">
                <div class="thermostat-circle-inner" style="width: 200px; height: 200px;">
                  <input type="number" class="value-input" id="panel-val" min="0" max="100" value="${lightLevel}">
                  <span class="unit">Brightness %</span>
                </div>
              </div>
              <button class="btn-round increase" id="btn-increase" style="background-color: #8c52ff; color: white;"><i class="fas fa-plus"></i></button>
            </div>
          </div>
        </div>
      `;
    } else if (kind === 'fan') {
      html = `
        <div style="display:flex;flex-direction:column;width:100%;height:100%;">
          ${renderHeader()}
          <div style="flex:1;display:flex;flex-direction:column;justify-content:center;align-items:center;width:100%;margin-top:20px;">
            <div class="thermostat-wrapper" style="flex-direction: column; gap: 30px;">
              <div class="thermostat-circle" id="dynamic-circle" style="--ring-color: #a05ef8; --progress:${fanSpeed}%; width: 180px; height: 180px;">
                <div class="thermostat-circle-inner" style="width: 160px; height: 160px;">
                  <input type="number" class="value-input" id="panel-val" min="0" max="100" value="${fanSpeed}" style="font-size: 46px; width: 100px;">
                  <span class="unit">Speed Lvl</span>
                </div>
              </div>
              <input type="range" min="0" max="100" value="${fanSpeed}" class="custom-slider-bar" id="panel-slider" style="width: 250px;">
            </div>
          </div>
        </div>
      `;
    } else if (kind === 'lcd') {
      html = `
        <div style="display:flex;flex-direction:column;width:100%;height:100%;">
          ${renderHeader()}
          <div style="flex:1;display:flex;flex-direction:column;justify-content:center;align-items:center;width:100%;margin-top:20px;">
            <div style="width: 100%; max-width: 350px;">
              <input type="text" placeholder="Type your message..." class="modern-input" id="lcd-text" value="${app.escapeHtml(
                lcdMessage
              )}">
              <button class="btn-modern purple" id="btn-send-lcd" style="background-color: #499dff; margin-top: 15px;">SEND TO LCD</button>
            </div>
          </div>
        </div>
      `;
    } else if (kind === 'door') {
      html = `
        <div style="display:flex;flex-direction:column;width:100%;height:100%;">
          ${renderHeader()}
          <div style="flex:1;display:flex;flex-direction:column;justify-content:center;align-items:center;width:100%;margin-top:20px;">
            <div style="font-size: 70px; color: #a46016; margin-bottom: 30px;">
              <i class="fas ${doorUnlocked ? 'fa-door-open' : 'fa-door-closed'}" id="door-icon"></i>
            </div>
            <button class="btn-modern green" id="btn-door" style="width: 100%; max-width: 300px;">${
              doorUnlocked ? 'LOCK DOOR' : 'UNLOCK DOOR'
            }</button>
          </div>
        </div>
      `;
    } else if (kind === 'alarm') {
      html = `
        <div style="display:flex;flex-direction:column;width:100%;height:100%;">
          ${renderHeader()}
          <div style="flex:1;display:flex;flex-direction:column;justify-content:center;align-items:center;width:100%;margin-top:20px;">
            <div style="font-size: 70px; color: #ff4f53; margin-bottom: 30px;"><i class="fas fa-bell"></i></div>
            <button class="btn-modern green" id="btn-alarm" style="width: 100%; max-width: 300px;">${
              isOn ? 'TURN ALARM OFF' : 'TURN ALARM ON'
            }</button>
          </div>
        </div>
      `;
    }

    controlPanel.classList.add('active-panel');
    controlPanel.innerHTML = html;

    const panelToggle = document.getElementById('panel-toggle-switch');
    if (panelToggle) {
      panelToggle.addEventListener('change', async () => {
        panelToggle.disabled = true;
        try {
          await app.controlDevice(deviceKey, app.checkboxCommand(deviceKey, panelToggle.checked));
        } catch (error) {
          panelToggle.checked = !panelToggle.checked;
          window.alert(error.message || 'Could not control device');
        } finally {
          panelToggle.disabled = false;
        }
      });
    }

    if (kind === 'light') {
      const input = document.getElementById('panel-val');
      const circle = document.getElementById('dynamic-circle');
      const decreaseBtn = document.getElementById('btn-decrease');
      const increaseBtn = document.getElementById('btn-increase');
      let submitting = false;

      const updateUi = (value) => {
        const next = Math.max(0, Math.min(100, parseInt(value || 0, 10) || 0));
        input.value = next;
        circle.style.setProperty('--progress', `${next}%`);
        circle.style.setProperty('--glow-color', `rgba(252, 225, 75, ${(next / 100) * 0.7})`);
        return next;
      };

      const submit = async (value) => {
        if (submitting) return;
        const next = updateUi(value);
        submitting = true;
        input.disabled = true;
        decreaseBtn.disabled = true;
        increaseBtn.disabled = true;
        try {
          await app.controlDevice(deviceKey, String(next));
        } finally {
          submitting = false;
          input.disabled = false;
          decreaseBtn.disabled = false;
          increaseBtn.disabled = false;
        }
      };

      decreaseBtn.addEventListener('click', () => submit((parseInt(input.value, 10) || 0) - 10));
      increaseBtn.addEventListener('click', () => submit((parseInt(input.value, 10) || 0) + 10));
      input.addEventListener('input', () => updateUi(input.value));
      input.addEventListener('change', () => submit(input.value));
      input.addEventListener('keydown', (event) => {
        if (event.key !== 'Enter') return;
        event.preventDefault();
        submit(input.value);
      });
      updateUi(lightLevel);
    }

    if (kind === 'fan') {
      const slider = document.getElementById('panel-slider');
      const input = document.getElementById('panel-val');
      const circle = document.getElementById('dynamic-circle');

      const updateUi = (value) => {
        const next = Math.max(0, Math.min(100, parseInt(value || 0, 10) || 0));
        slider.value = next;
        input.value = next;
        circle.style.setProperty('--progress', `${next}%`);
        circle.style.setProperty('--glow-color', `rgba(160, 94, 248, ${(next / 100) * 0.6})`);
        return next;
      };

      const submit = async (value) => {
        const next = updateUi(value);
        await app.controlDevice(deviceKey, String(next));
      };

      slider.addEventListener('input', () => updateUi(slider.value));
      slider.addEventListener('change', () => submit(slider.value));
      input.addEventListener('change', () => submit(input.value));
      updateUi(fanSpeed);
    }

    if (kind === 'lcd') {
      const sendBtn = document.getElementById('btn-send-lcd');
      sendBtn.addEventListener('click', async () => {
        const input = document.getElementById('lcd-text');
        const message = input.value.trim();
        if (!message) {
          window.alert('Please enter a message');
          return;
        }
        sendBtn.disabled = true;
        try {
          await app.controlDevice(deviceKey, message);
        } catch (error) {
          window.alert(error.message || 'Could not send LCD message');
        } finally {
          sendBtn.disabled = false;
        }
      });
    }

    if (kind === 'door') {
      const doorBtn = document.getElementById('btn-door');
      doorBtn.addEventListener('click', async () => {
        doorBtn.disabled = true;
        try {
          await app.controlDevice(deviceKey, doorUnlocked ? 'lock' : 'unlock');
        } catch (error) {
          window.alert(error.message || 'Could not toggle door');
        } finally {
          doorBtn.disabled = false;
        }
      });
    }

    if (kind === 'alarm') {
      const alarmBtn = document.getElementById('btn-alarm');
      alarmBtn.addEventListener('click', async () => {
        alarmBtn.disabled = true;
        try {
          await app.controlDevice(deviceKey, isOn ? 'off' : 'on');
        } catch (error) {
          window.alert(error.message || 'Could not toggle alarm');
        } finally {
          alarmBtn.disabled = false;
        }
      });
    }
  }

  function initDeviceInteractions() {
    const list = document.getElementById('full-devices-list');
    if (!list) return;

    list.addEventListener('click', (event) => {
      const item = event.target.closest('.device-item');
      if (!item || !list.contains(item)) return;
      if (event.target.closest('.switch')) return;

      if (document.getElementById('main-control-panel')) {
        setSelectedDevice(item.dataset.device);
        renderDevicePanel(item.dataset.device);
      }
    });

    list.addEventListener('change', async (event) => {
      const checkbox = event.target.closest('.switch input[type="checkbox"]');
      if (!checkbox) return;

      const item = checkbox.closest('.device-item');
      const deviceKey = item?.dataset.device;
      if (!deviceKey) return;

      const previous = !checkbox.checked;
      checkbox.disabled = true;
      item.style.opacity = checkbox.checked ? '1' : '0.6';

      try {
        await app.controlDevice(deviceKey, app.checkboxCommand(deviceKey, checkbox.checked));
      } catch (error) {
        checkbox.checked = previous;
        item.style.opacity = previous ? '1' : '0.6';
        window.alert(error.message || 'Could not control device');
      } finally {
        checkbox.disabled = false;
      }
    });

    window.__refreshSelectedDevicePanel = (deviceKey) => {
      if (selectedDeviceKey && selectedDeviceKey === deviceKey && document.getElementById('main-control-panel')) {
        renderDevicePanel(deviceKey);
      }
    };
  }

  function sceneKeyFromElement(element) {
    if (element?.dataset.sceneKey) return element.dataset.sceneKey;
    const mode = (element?.dataset.mode || '').toLowerCase();
    if (mode) return `${mode}_mode`;
    const text = String(element?.textContent || '').toLowerCase();
    if (text.includes('sleep')) return 'sleep_mode';
    if (text.includes('away')) return 'away_mode';
    if (text.includes('party')) return 'party_mode';
    return 'home_mode';
  }

  function formatSceneAction(deviceKey, command) {
    const raw = String(command || '').trim();
    const lowered = raw.toLowerCase();

    if (deviceKey === 'door_main') {
      return lowered === 'unlock'
        ? { label: 'UNLOCK', className: 'on' }
        : { label: 'LOCK DOOR', className: 'off' };
    }

    if (lowered === 'on') return { label: 'TURN ON', className: 'on' };
    if (lowered === 'off') return { label: 'TURN OFF', className: 'off' };
    if (/^\d+$/.test(lowered)) return { label: `SET ${lowered}`, className: 'value' };
    return { label: raw.toUpperCase(), className: 'value' };
  }

  async function renderModePanel(sceneKey) {
    const panel = document.getElementById('main-mode-panel');
    if (!panel) return;

    const scene = await app.fetchSceneDetail(sceneKey);
    const iconByScene = {
      home_mode: { icon: 'fas fa-home', color: '#4ba3e3' },
      away_mode: { icon: 'fas fa-sign-out-alt', color: '#a35c15' },
      sleep_mode: { icon: 'fas fa-moon', color: '#6a4cff' },
      party_mode: { icon: 'fas fa-glass-cheers', color: '#ff4f53' },
    };
    const appearance = iconByScene[sceneKey] || iconByScene.home_mode;

    panel.classList.add('active-panel');
    panel.innerHTML = `
      <div style="display: flex; flex-direction: column; width: 100%; height: 100%; align-items: center;">
        <div style="width: 80px; height: 80px; border-radius: 50%; background-color: ${appearance.color}20; display: flex; justify-content: center; align-items: center; color: ${appearance.color}; font-size: 35px; margin-bottom: 15px;">
          <i class="${appearance.icon}"></i>
        </div>
        <h2 style="color: #333; margin-bottom: 5px;">${scene.scene_name}</h2>
        <p style="color: #666; font-size: 14px;">${scene.description || 'The following actions will be executed:'}</p>
        <div class="mode-action-list">
          ${scene.actions
            .map((action) => {
              const formatted = formatSceneAction(action.device_key, action.command);
              const icon = app.getDeviceKind(action.device_key);
              const iconClass = {
                light: 'far fa-lightbulb',
                fan: 'fas fa-fan',
                lcd: 'fas fa-desktop',
                door: 'fas fa-door-closed',
                alarm: 'fas fa-bell',
              }[icon];
              const iconColor = {
                light: '#fce14b',
                fan: '#a05ef8',
                lcd: '#499dff',
                door: '#a46016',
                alarm: '#ff4f53',
              }[icon];
              return `
                <div class="action-item">
                  <div class="action-item-left">
                    <i class="${iconClass}" style="color: ${iconColor};"></i>
                    <span style="font-weight: 500; color: #333;">${action.device_name}</span>
                  </div>
                  <span class="action-status ${formatted.className}">${formatted.label}</span>
                </div>
              `;
            })
            .join('')}
        </div>
        <button class="btn-modern purple" id="btn-activate-mode" style="background-color: ${appearance.color}; width: 100%; max-width: 300px; padding: 15px; border-radius: 12px; margin-top: auto;">
          <i class="fas fa-play" style="margin-right: 8px;"></i> ACTIVATE MODE
        </button>
      </div>
    `;

    const activateBtn = document.getElementById('btn-activate-mode');
    activateBtn.addEventListener('click', async () => {
      const original = activateBtn.innerHTML;
      activateBtn.disabled = true;
      activateBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> ACTIVATING...';
      try {
        await app.activateScene(sceneKey);
        activateBtn.innerHTML = '<i class="fas fa-check"></i> MODE ACTIVATED';
        activateBtn.style.backgroundColor = '#34c759';
        setTimeout(() => {
          activateBtn.innerHTML = original;
          activateBtn.style.backgroundColor = appearance.color;
          activateBtn.disabled = false;
        }, 2000);
      } catch (error) {
        activateBtn.innerHTML = original;
        activateBtn.disabled = false;
        window.alert(error.message || 'Could not activate mode');
      }
    });
  }

  function initModesPage() {
    const list = document.getElementById('full-modes-list');
    if (list) {
      list.addEventListener('click', async (event) => {
        const card = event.target.closest('.mode-card-item');
        if (!card || !list.contains(card)) return;

        list.querySelectorAll('.mode-card-item').forEach((item) => item.classList.remove('selected'));
        card.classList.add('selected');

        try {
          await renderModePanel(sceneKeyFromElement(card));
        } catch (error) {
          window.alert(error.message || 'Could not load mode');
        }
      });
    }

    const dashboardButtons = document.querySelectorAll('.card-modes .mode-btn');
    dashboardButtons.forEach((button) => {
      button.addEventListener('click', async () => {
        const sceneKey = sceneKeyFromElement(button);
        const original = button.innerHTML;
        button.style.pointerEvents = 'none';
        button.innerHTML = '<i class="fas fa-spinner fa-spin"></i> <span>Activating...</span>';

        try {
          await app.activateScene(sceneKey);
          dashboardButtons.forEach((item) => {
            item.classList.remove('active');
            const badge = item.querySelector('.badge-active');
            if (badge) badge.remove();
          });
          button.classList.add('active');
          const badge = document.createElement('span');
          badge.className = 'badge-active';
          badge.textContent = 'Active';
          button.appendChild(badge);
        } catch (error) {
          window.alert(error.message || 'Could not activate scene');
        } finally {
          button.style.pointerEvents = '';
          button.innerHTML = original;
          if (button.classList.contains('active') && !button.querySelector('.badge-active')) {
            const badge = document.createElement('span');
            badge.className = 'badge-active';
            badge.textContent = 'Active';
            button.appendChild(badge);
          }
        }
      });
    });
  }

  function initMembersPage() {
    const list = document.getElementById('full-members-list');
    const panel = document.getElementById('main-member-panel');
    if (!list || !panel) return;

    list.addEventListener('click', (event) => {
      const card = event.target.closest('.member-card-item');
      if (!card || !list.contains(card)) return;

      list.querySelectorAll('.member-card-item').forEach((item) => item.classList.remove('selected'));
      card.classList.add('selected');

      const fullName = card.dataset.fullName || card.querySelector('.device-name')?.textContent || 'User';
      const role = (card.dataset.role || 'resident').toLowerCase();
      const initials = fullName
        .split(/\s+/)
        .map((part) => part[0])
        .join('')
        .slice(0, 2)
        .toUpperCase();

      const colorByRole = {
        admin: '#6a4cff',
        owner: '#6a4cff',
        resident: '#1a73e8',
        guest: '#d93025',
        maintenance: '#f57c00',
      };
      const roleColor = colorByRole[role] || '#6a4cff';
      const methods =
        role === 'guest'
          ? ['Temporary PIN', 'Expiry control']
          : role === 'admin' || role === 'owner'
          ? ['Password / PIN', 'Face ID', 'Remote control']
          : ['Password / PIN', 'Remote control'];

      panel.classList.add('active-panel');
      panel.innerHTML = `
        <div style="display: flex; flex-direction: column; width: 100%; height: 100%; align-items: center;">
          <div style="display: flex; align-items: center; width: 100%; gap: 15px; margin-bottom: 20px; border-bottom: 1px solid #eee; padding-bottom: 15px;">
            <div class="avatar-circle" style="width: 60px; height: 60px; font-size: 24px; background-color: ${roleColor}20; color: ${roleColor}; margin: 0;">
              ${initials}
            </div>
            <div style="text-align: left;">
              <h2 style="color: #333; margin-bottom: 5px; font-size: 20px;">${fullName}</h2>
              <span style="font-size: 11px; font-weight: bold; color: ${roleColor}; padding: 3px 10px; background: ${roleColor}15; border-radius: 20px;">${role.toUpperCase()}</span>
            </div>
          </div>
          <div style="flex: 1; width: 100%; overflow-y: auto; padding-right: 5px; margin-bottom: 20px;">
            <div style="text-align: left; margin-bottom: 25px;">
              <p style="color: #666; font-size: 13px; font-weight: bold; text-transform: uppercase; letter-spacing: 1px; margin-bottom: 10px;">Security Methods</p>
              <div class="auth-method-list" style="margin:0;">
                ${methods
                  .map(
                    (method) => `
                    <div class="auth-item">
                      <div class="auth-item-left"><i class="fas fa-shield-alt" style="color: ${roleColor};"></i> ${method}</div>
                      <span class="status-badge active">ACTIVE</span>
                    </div>
                  `
                  )
                  .join('')}
              </div>
            </div>
            <div style="text-align: left;">
              <p style="color: #666; font-size: 13px; font-weight: bold; text-transform: uppercase; letter-spacing: 1px; margin-bottom: 10px;">Access Summary</p>
              <div style="border: 1px solid #eee; border-radius: 12px; overflow: hidden;">
                <div style="display:flex;justify-content:space-between;align-items:center;padding:12px 15px;background:#fff;">
                  <span style="color:#333;font-weight:500;font-size:13px;">Role permissions</span>
                  <span style="color:${roleColor};font-weight:bold;font-size:12px;">${role.toUpperCase()}</span>
                </div>
                <div style="display:flex;justify-content:space-between;align-items:center;padding:12px 15px;background:#fff;border-top:1px solid #f0f0f5;">
                  <span style="color:#333;font-weight:500;font-size:13px;">Backend source</span>
                  <span style="color:#666;font-size:12px;">MySQL users table</span>
                </div>
              </div>
            </div>
          </div>
          <div style="width: 100%; margin-top: auto;">
            <button class="btn-modern ${role === 'guest' ? 'red' : 'purple'}" style="width: 100%;">${
              role === 'guest' ? 'REVOKE ACCESS' : 'EDIT PERMISSIONS'
            }</button>
          </div>
        </div>
      `;
    });
  }

  function initAiRecommendations() {
    const acceptButtons = document.querySelectorAll('.btn-rec-accept');
    const rejectButtons = document.querySelectorAll('.btn-rec-reject');
    const list = document.getElementById('ai-rec-list');
    const emptyState = document.getElementById('ai-empty-state');

    function updateEmptyState() {
      const remaining = document.querySelectorAll('.ai-rec-item:not(.fade-out)');
      if (remaining.length !== 0) return;
      setTimeout(() => {
        if (list) list.style.display = 'none';
        if (emptyState) emptyState.style.display = 'block';
      }, 300);
    }

    acceptButtons.forEach((button) => {
      button.addEventListener('click', () => {
        const card = button.closest('.ai-rec-item');
        button.innerHTML = '<i class="fas fa-spinner fa-spin"></i>';
        setTimeout(() => {
          card.classList.add('fade-out');
          setTimeout(() => card.remove(), 300);
          updateEmptyState();
        }, 500);
      });
    });

    rejectButtons.forEach((button) => {
      button.addEventListener('click', () => {
        const card = button.closest('.ai-rec-item');
        card.classList.add('fade-out');
        setTimeout(() => card.remove(), 300);
        updateEmptyState();
      });
    });
  }

  function initPowerView() {
    const powerViewContainer = document.getElementById('chart-container');
    if (!powerViewContainer) return;

    const mockPowerData = {
      day: {
        label: 'Today',
        currentLoad: 1425,
        totalConsumed: 5.2,
        cost: 1.85,
        tier: 'Tier 1',
        tierClass: 'color: #1e8e3e; background: #e6f4ea;',
        labels: ['00:00', '06:00', '12:00', '18:00', '23:59'],
        values: [300, 600, 1425, 1100, 400],
        nilm: [
          { name: 'Air Conditioner', icon: 'fas fa-snowflake', color: '#4ba3e3', value: '1,200 W', isPhantom: false },
          { name: 'Phantom Load', icon: 'fas fa-ghost', color: '#ff4f53', value: '30 W', isPhantom: true },
        ],
      },
      week: {
        label: 'This Week',
        currentLoad: 1425,
        totalConsumed: 42.5,
        cost: 15.2,
        tier: 'Tier 1',
        tierClass: 'color: #1e8e3e; background: #e6f4ea;',
        labels: ['Mon', 'Tue', 'Thu', 'Sat', 'Sun'],
        values: [400, 1000, 500, 1425, 1100],
        nilm: [
          { name: 'Air Conditioner', icon: 'fas fa-snowflake', color: '#4ba3e3', value: '1,200 W', isPhantom: false },
          { name: 'Refrigerator', icon: 'fas fa-cube', color: '#999', value: '150 W', isPhantom: false },
          { name: 'Lighting System', icon: 'far fa-lightbulb', color: '#fce14b', value: '60 W', isPhantom: false },
          { name: 'Phantom Load', icon: 'fas fa-ghost', color: '#ff4f53', value: '15 W', isPhantom: true },
        ],
      },
      month: {
        label: 'This Month',
        currentLoad: 1425,
        totalConsumed: 185.5,
        cost: 45.2,
        tier: 'Tier 2',
        tierClass: 'color: #f57c00; background: #fff3e0;',
        labels: ['1st', '8th', '15th', '22nd', '30th'],
        values: [800, 1500, 1100, 1800, 1425],
        nilm: [
          { name: 'Air Conditioner', icon: 'fas fa-snowflake', color: '#4ba3e3', value: '1,200 W', isPhantom: false },
          { name: 'Water Heater', icon: 'fas fa-hot-tub', color: '#ff7b00', value: '1,500 W', isPhantom: false },
          { name: 'Phantom Load', icon: 'fas fa-ghost', color: '#ff4f53', value: '25 W', isPhantom: true },
        ],
      },
    };

    let currentChartPoints = [];

    function renderPowerData(period) {
      const data = mockPowerData[period];
      if (!data) return;

      document.getElementById('val-current-load').textContent = data.currentLoad.toLocaleString();
      document.getElementById('val-total-consumed').textContent = data.totalConsumed;
      document.getElementById('lbl-total-consumed').textContent = data.label;
      document.getElementById('val-cost').textContent = `$${data.cost.toFixed(2)}`;
      document.getElementById('lbl-cost-period').textContent = `Total ${data.label.toLowerCase()}`;

      const tierElement = document.getElementById('val-tier');
      tierElement.textContent = `Currently in ${data.tier}`;
      tierElement.style.cssText = data.tierClass;

      const maxY = 2000;
      const chartTop = 20;
      const chartBottom = 200;
      const xPositions = [50, 175, 300, 425, 550];

      currentChartPoints = data.values.map((value, index) => {
        const yPosition = chartBottom - (value / maxY) * (chartBottom - chartTop) * 1.2;
        return { x: xPositions[index], y: yPosition, value, label: data.labels[index] };
      });

      let pathD = `M ${currentChartPoints[0].x},${currentChartPoints[0].y} `;
      for (let index = 1; index < currentChartPoints.length; index += 1) {
        const previous = currentChartPoints[index - 1];
        const current = currentChartPoints[index];
        const controlX = (previous.x + current.x) / 2;
        pathD += `C ${controlX},${previous.y} ${controlX},${current.y} ${current.x},${current.y} `;
      }

      document.getElementById('chart-path-stroke').setAttribute('d', pathD);
      document.getElementById('chart-path-fill').setAttribute('d', `${pathD} L 550,220 L 50,220 Z`);

      const labelsContainer = document.getElementById('chart-labels-container');
      labelsContainer.innerHTML = currentChartPoints
        .map((point) => `<text x="${point.x - 5}" y="220" fill="#999" font-size="12" text-anchor="middle">${point.label}</text>`)
        .join('');

      const nilmContainer = document.getElementById('nilm-list-container');
      nilmContainer.innerHTML = data.nilm
        .map((item) => {
          if (item.isPhantom) {
            return `<div class="nilm-item alert" style="background: #ffecec; border: 1px dashed #ff4f53;"><div class="nilm-info"><i class="${item.icon}" style="color: ${item.color};"></i><span style="color: #ff4f53; font-weight: bold;">${item.name}</span></div><span class="nilm-value" style="color: #ff4f53;">${item.value}</span></div>`;
          }
          return `<div class="nilm-item"><div class="nilm-info"><i class="${item.icon}" style="color: ${item.color};"></i><span>${item.name}</span></div><span class="nilm-value">${item.value}</span></div>`;
        })
        .join('');
    }

    const tooltip = document.getElementById('chart-tooltip');
    const hoverLine = document.getElementById('hover-line');
    const hoverDot = document.getElementById('hover-dot');

    powerViewContainer.addEventListener('mousemove', (event) => {
      const rect = powerViewContainer.getBoundingClientRect();
      const mouseX = ((event.clientX - rect.left) / rect.width) * 550;

      let closestPoint = currentChartPoints[0];
      let minDiff = Math.abs(mouseX - closestPoint.x);
      currentChartPoints.forEach((point) => {
        const diff = Math.abs(mouseX - point.x);
        if (diff < minDiff) {
          minDiff = diff;
          closestPoint = point;
        }
      });

      const pixelX = (closestPoint.x / 550) * rect.width;
      const pixelY = (closestPoint.y / 220) * rect.height;

      tooltip.style.display = 'block';
      hoverLine.style.display = 'block';
      hoverDot.style.display = 'block';

      tooltip.textContent = `${closestPoint.value} W`;
      tooltip.style.left = `${pixelX}px`;
      tooltip.style.top = `${pixelY}px`;
      hoverDot.style.left = `${pixelX}px`;
      hoverDot.style.top = `${pixelY}px`;
      hoverLine.style.left = `${pixelX}px`;
    });

    powerViewContainer.addEventListener('mouseleave', () => {
      tooltip.style.display = 'none';
      hoverLine.style.display = 'none';
      hoverDot.style.display = 'none';
    });

    document.querySelectorAll('.time-tab').forEach((tab) => {
      tab.addEventListener('click', () => {
        document.querySelectorAll('.time-tab').forEach((item) => item.classList.remove('active'));
        tab.classList.add('active');
        renderPowerData(tab.dataset.period);
      });
    });

    renderPowerData('week');
  }

  toggleAlertsDropdown();
  initDeviceInteractions();
  initModesPage();
  initMembersPage();
  initPowerView();
  initAiRecommendations();
});

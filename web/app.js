// ========== 全局状态 ==========
let currentData = null;
let focusMatchId = null;

// ========== 视图切换 ==========
function switchView(viewName) {
  const slider = document.getElementById('views-slider');
  slider.className = `slider-${viewName}`;
  document.querySelectorAll('.nav-item').forEach(i => i.classList.remove('active'));
  const nav = document.getElementById(`nav-${viewName}`);
  if (nav) nav.classList.add('active');
}

// ========== 数据绑定 ==========
function bindData(data) {
  currentData = data;

  // 更新连接状态指示
  const indicator = document.getElementById('live-indicator');
  const statusText = document.getElementById('data-status-text');

  if (data.fetch_error) {
    indicator.className = 'live-dot';
    statusText.textContent = '连接失败';
    statusText.style.color = '#ff3838';
  } else {
    statusText.style.color = '';
    if (data.has_live) {
      indicator.className = 'live-dot active';
      statusText.textContent = 'LIVE';
    } else {
      indicator.className = 'live-dot';
      statusText.textContent = '实时同步中';
    }
  }

  renderFocusMatch();
  renderSchedule();
  
}

// ========== 实时比分卡 / 无比赛提示 ==========
function renderFocusMatch() {
  if (!currentData || !currentData.matches) return;

  const noMatchEl = document.getElementById('no-match-notice');
  const liveCardEl = document.getElementById('live-match-card');

  // 找到进行中的比赛
  let liveMatch = currentData.matches.find(m => m.is_live);

  // 如果没有进行中的比赛
  if (!liveMatch) {
    // 如果用户手动点击选中了某场比赛，就展示那场
    if (focusMatchId) {
      liveMatch = currentData.matches.find(m => m.id === focusMatchId);
    }
  }

  if (!liveMatch) {
    // 显示"当前并无比赛进行中"
    noMatchEl.style.display = 'flex';
    liveCardEl.style.display = 'none';

    // 显示最近的下一场比赛提示
    const nextMatch = currentData.matches.find(m => !m.is_finished && !m.is_live);
    const hintEl = document.getElementById('next-match-hint');
    if (nextMatch) {
      hintEl.textContent = `下一场: ${nextMatch.home_team} vs ${nextMatch.away_team} · ${nextMatch.date} ${nextMatch.time}`;
    } else {
      hintEl.textContent = '请切换到"赛程"查看后续比赛安排';
    }
    return;
  }

  // 有比赛可展示
  noMatchEl.style.display = 'none';
  liveCardEl.style.display = 'flex';

  const m = liveMatch;

  document.getElementById('home-name').innerText = m.home_team;
  document.getElementById('away-name').innerText = m.away_team;
  document.getElementById('home-flag').src = m.home_badge || 'https://flagcdn.com/w160/un.png';
  document.getElementById('away-flag').src = m.away_badge || 'https://flagcdn.com/w160/un.png';

  // 比分
  const homeScoreEl = document.getElementById('home-score-num');
  const awayScoreEl = document.getElementById('away-score-num');
  const oldHome = parseInt(homeScoreEl.innerText);
  const oldAway = parseInt(awayScoreEl.innerText);

  const hScore = m.home_score !== null ? m.home_score : '-';
  const aScore = m.away_score !== null ? m.away_score : '-';
  homeScoreEl.innerText = hScore;
  awayScoreEl.innerText = aScore;

  if (!isNaN(oldHome) && oldHome !== m.home_score && m.home_score !== null) popElement(homeScoreEl);
  if (!isNaN(oldAway) && oldAway !== m.away_score && m.away_score !== null) popElement(awayScoreEl);

  // 状态
  const statusBadge = document.getElementById('match-status-badge');
  const timeText = document.getElementById('match-time-text');
  const pulseEl = statusBadge.querySelector('.live-pulse-indicator');

  if (m.is_live) {
    statusBadge.style.color = '#00f076';
    statusBadge.style.borderColor = 'rgba(0,240,118,0.15)';
    statusBadge.style.background = 'rgba(0,240,118,0.06)';
    timeText.innerText = m.status;
    pulseEl.style.display = 'block';
  } else if (m.is_finished) {
    statusBadge.style.color = 'rgba(255,255,255,0.5)';
    statusBadge.style.borderColor = 'rgba(255,255,255,0.05)';
    statusBadge.style.background = 'rgba(255,255,255,0.05)';
    timeText.innerText = m.status;
    pulseEl.style.display = 'none';
  } else {
    statusBadge.style.color = '#ffd700';
    statusBadge.style.borderColor = 'rgba(255,215,0,0.15)';
    statusBadge.style.background = 'rgba(255,215,0,0.06)';
    timeText.innerText = `${m.date} ${m.time}`;
    pulseEl.style.display = 'none';
  }

  // 小组
  const groupLabel = document.getElementById('match-group-label');
  if (m.group) {
    groupLabel.textContent = `${m.group}组 · ${m.venue || ''}`;
    groupLabel.style.display = 'block';
  } else {
    groupLabel.textContent = m.venue || '';
    groupLabel.style.display = m.venue ? 'block' : 'none';
  }
}

// ========== 赛程列表 ==========
function renderSchedule() {
  const listEl = document.getElementById('schedule-list');
  if (!currentData || !currentData.matches || !listEl) return;
  listEl.innerHTML = '';

  let lastDate = '';

  currentData.matches.forEach(m => {
    // 日期分隔
    if (m.date !== lastDate) {
      lastDate = m.date;
      const divider = document.createElement('div');
      divider.className = 'date-divider';
      divider.textContent = m.date;
      listEl.appendChild(divider);
    }

    const item = document.createElement('div');
    let cls = 'match-item no-drag';
    if (m.is_live) cls += ' live-item';
    else if (m.is_finished) cls += ' finished-item';
    item.className = cls;

    item.onclick = () => {
      focusMatchId = m.id;
      renderFocusMatch();
      switchView('live');
    };

    const scoreContent = m.home_score !== null && m.away_score !== null
      ? `${m.home_score} - ${m.away_score}`
      : 'vs';

    item.innerHTML = `
      <div class="item-team">
        <img class="item-flag" src="${m.home_badge || 'https://flagcdn.com/w80/un.png'}" onerror="this.src='https://flagcdn.com/w80/un.png'">
        <span class="item-name">${m.home_team}</span>
      </div>
      <div class="item-mid">
        <span class="item-score-box ${m.is_live ? 'live' : ''}">${scoreContent}</span>
        <span class="item-status ${m.is_live ? 'live' : ''}">${m.is_live ? m.status : (m.is_finished ? m.status : m.time)}</span>
      </div>
      <div class="item-team away">
        <span class="item-name">${m.away_team}</span>
        <img class="item-flag" src="${m.away_badge || 'https://flagcdn.com/w80/un.png'}" onerror="this.src='https://flagcdn.com/w80/un.png'">
      </div>
    `;
    listEl.appendChild(item);
  });
}

// ========== 动画 ==========
function popElement(el) {
  el.classList.add('pop');
  setTimeout(() => el.classList.remove('pop'), 1200);
}

function showGoalOverlay(event) {
  const overlay = document.getElementById('goal-overlay');
  if (!overlay) return;
  document.getElementById('goal-team-name').innerText = event.home_team + ' vs ' + event.away_team;
  document.getElementById('goal-current-score').innerText = event.new_score;
  overlay.classList.remove('hidden');
  setTimeout(() => overlay.classList.add('hidden'), 4500);
}

// ========== 窗口控制 ==========
function startDrag(e) {
  if (e.target.closest('.no-drag') || e.target.closest('button')) return;
  if (window.pywebview && window.pywebview.api) {
    window.pywebview.api.start_drag();
  }
}

function closeWidget() {
  if (window.pywebview && window.pywebview.api) {
    window.pywebview.api.close_widget();
  }
}

// ========== 后端推送接口 ==========
window.pushData = function(data) { bindData(data); };
window.pushGoalEvent = function(event) { showGoalOverlay(event); };

// ========== 初始化 ==========
function startPolling() {
  const requestData = () => {
    if (window.pywebview && window.pywebview.api) {
      window.pywebview.api.request_full_data().then(data => {
        if (data) bindData(data);
      });
    }
  };

  requestData();
  setInterval(requestData, 5000);
}

window.addEventListener('DOMContentLoaded', () => {
  startPolling();
});

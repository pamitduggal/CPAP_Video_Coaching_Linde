/**
 * ==============================================================================
 * CPAP Video VM Server - Interactive Dashboard JavaScript Engine
 * With Real-Time Scenario Activity Radar & Multi-Node Inbound Tracking
 * ==============================================================================
 */

// State Management
const state = {
  health: {},
  library: { existing_assets: [], new_videos: [], generated_subtitles: [] },
  triggers: [],
  history: [],
  activities: [],
  activeVideo: null,
  activeLang: 'en',
  activeCues: [],
  currentStem: null,
  playlistFilter: 'all',
  logAutoScroll: true,
  logSearchTerm: '',
  eventSource: null,
  radarTimeout: null,
};

// Helper: Get Auth Headers for API Requests
function getAuthHeaders(extraHeaders = {}) {
  const key = window.localStorage.getItem('VIDEO_SERVER_API_KEY') || '';
  const headers = { ...extraHeaders };
  if (key) {
    headers['X-API-KEY'] = key;
  }
  return headers;
}

// DOM Elements
const elements = {
  // Tabs
  tabBtns: document.querySelectorAll('.tab-btn'),
  tabContents: document.querySelectorAll('.tab-content'),
  
  // Scenario Radar
  scenarioRadarCard: document.getElementById('scenario-radar-card'),
  radarBeacon: document.getElementById('radar-beacon'),
  radarTitle: document.getElementById('radar-title'),
  radarSourceTag: document.getElementById('radar-source-tag'),
  radarMeta: document.getElementById('radar-meta'),
  radarScenarioBadge: document.getElementById('radar-scenario-badge'),
  radarPrimaryText: document.getElementById('radar-primary-text'),
  radarSubText: document.getElementById('radar-sub-text'),
  
  // KPIs
  kpiTotalVideos: document.getElementById('kpi-total-videos'),
  kpiTotalSubs: document.getElementById('kpi-total-subs'),
  kpiWatcherStatus: document.getElementById('kpi-watcher-status'),
  kpiLedgerStatus: document.getElementById('kpi-ledger-status'),
  kpiDedupCount: document.getElementById('kpi-dedup-count'),
  
  // Video Player
  videoPlayer: document.getElementById('main-video-player'),
  videoTrackEn: document.getElementById('track-en'),
  videoTrackFr: document.getElementById('track-fr'),
  videoSubtitleOverlay: document.getElementById('video-subtitle-overlay'),
  videoTitle: document.getElementById('player-video-title'),
  videoMetaDetails: document.getElementById('player-video-meta'),
  videoList: document.getElementById('video-playlist-items'),
  videoSearchInput: document.getElementById('video-search-input'),
  libraryBrowserTitle: document.getElementById('library-browser-title'),
  pillCountAll: document.getElementById('pill-count-all'),
  pillCountNew: document.getElementById('pill-count-new'),
  pillCountExisting: document.getElementById('pill-count-existing'),
  subtitleStatusIndicator: document.getElementById('subtitle-status-indicator'),
  subBtnEn: document.getElementById('sub-btn-en'),
  subBtnFr: document.getElementById('sub-btn-fr'),
  subBtnOff: document.getElementById('sub-btn-off'),
  
  // Triggers Table
  triggersTableBody: document.getElementById('triggers-table-body'),
  triggerSearchInput: document.getElementById('trigger-search-input'),
  triggerCountBadge: document.getElementById('trigger-count-badge'),
  
  // Ledger Table
  ledgerTableBody: document.getElementById('ledger-table-body'),
  ledgerSearchInput: document.getElementById('ledger-search-input'),
  ledgerCountBadge: document.getElementById('ledger-count-badge'),
  
  // Terminal Logs & Activity Feed
  terminalLogs: document.getElementById('terminal-logs-body'),
  activityFeedBody: document.getElementById('activity-feed-body'),
  btnLogScrollToggle: document.getElementById('btn-log-scroll'),
  btnClearLogs: document.getElementById('btn-clear-logs'),
  logFilterInput: document.getElementById('log-filter-input'),
  
  // Action Buttons
  btnRefreshKpis: document.getElementById('btn-refresh-kpis'),
  btnRebenchmark: document.getElementById('btn-rebenchmark'),
  btnSyncTriggers: document.getElementById('btn-sync-triggers'),
  btnRebuildCatalog: document.getElementById('btn-rebuild-catalog'),
  btnClearLedger: document.getElementById('btn-clear-ledger'),
  btnTestScenario1: document.getElementById('btn-test-scenario-1'),
  btnTestScenario2: document.getElementById('btn-test-scenario-2'),
  btnTestScenario3: document.getElementById('btn-test-scenario-3'),
  
  // KPI Gauges & Graphs Elements
  kpiTimestampDisplay: document.getElementById('kpi-timestamp-display'),
  topicDistributionBars: document.getElementById('topic-distribution-bars'),
  latencyColumnsContainer: document.getElementById('latency-columns-container'),
  safetyStratificationBody: document.getElementById('safety-stratification-body'),
  kpiStorageTotal: document.getElementById('kpi-storage-total'),
  storageSegVideos: document.getElementById('storage-seg-videos'),
  storageSegMeta: document.getElementById('storage-seg-meta'),
  storageSegSubs: document.getElementById('storage-seg-subs'),
  storageValVideos: document.getElementById('storage-val-videos'),
  storageValMeta: document.getElementById('storage-val-meta'),
  storageValSubs: document.getElementById('storage-val-subs'),

  // Toast
  toastContainer: document.getElementById('toast-container'),
};

// Initialize Application
document.addEventListener('DOMContentLoaded', () => {
  setupNavigation();
  setupPlayerControls();
  setupTerminalControls();
  setupActionButtons();
  
  // Initial Data Fetch
  fetchHealth();
  fetchLibrary();
  fetchTriggers();
  fetchHistory();
  fetchActivity();
  fetchKPIs();
  initLogStream();
  
  // Background Polling (Every 4 seconds for health, history, activity & KPIs)
  setInterval(() => {
    fetchHealth();
    fetchHistory();
    fetchActivity();
    fetchKPIs();
  }, 4000);

  // Background Library & Triggers Synchronization (Every 12 seconds)
  setInterval(() => {
    fetchLibrary();
    fetchTriggers();
  }, 12000);
});

// Toast System
function showToast(message, type = 'info') {
  const toast = document.createElement('div');
  toast.className = `toast toast-${type}`;
  toast.innerHTML = `<span>${type === 'success' ? '✅' : type === 'warn' ? '⚠️' : 'ℹ️'}</span> <span>${message}</span>`;
  elements.toastContainer.appendChild(toast);
  setTimeout(() => {
    toast.style.opacity = '0';
    setTimeout(() => toast.remove(), 300);
  }, 3500);
}

// Navigation Tabs
function setupNavigation() {
  elements.tabBtns.forEach(btn => {
    btn.addEventListener('click', () => {
      const targetTab = btn.getAttribute('data-tab');
      
      elements.tabBtns.forEach(b => b.classList.remove('active'));
      elements.tabContents.forEach(c => c.classList.remove('active'));
      
      btn.classList.add('active');
      const targetContent = document.getElementById(`tab-${targetTab}`);
      if (targetContent) targetContent.classList.add('active');
    });
  });
}

// ==============================================================================
// LIVE SCENARIO RADAR & INBOUND ACTIVITY ENGINE
// ==============================================================================
function updateScenarioRadar(activity) {
  if (!elements.scenarioRadarCard || !activity) return;
  
  const scId = activity.scenario_id || 1;
  const isDup = activity.status === 'shielded_duplicate';
  
  // Reset classes
  elements.scenarioRadarCard.classList.remove('active-scenario-1', 'active-scenario-2', 'active-scenario-3');
  elements.scenarioRadarCard.classList.add(`active-scenario-${scId}`);
  
  let scBadgeText = `Scenario ${scId}`;
  let scTitleText = `LIVE: SCENARIO ${scId} EXECUTION`;
  
  if (scId === 1) {
    scBadgeText = 'Scenario 1 • Single Clip';
    scTitleText = 'LIVE: SCENARIO 1 ACTIVE (Single-Clip Selection)';
  } else if (scId === 2) {
    scBadgeText = 'Scenario 2 • Virtual Sequence';
    scTitleText = 'LIVE: SCENARIO 2 ACTIVE (Multi-Clip Playlist & 1.5s Crossfade)';
  } else if (scId === 3) {
    scBadgeText = 'Scenario 3 • Google Veo AI';
    scTitleText = 'LIVE: SCENARIO 3 ACTIVE (Generative AI Video Synthesis)';
  }
  
  if (isDup) {
    scBadgeText += ' [SHIELDED DUPLICATE]';
  }
  
  if (elements.radarTitle) elements.radarTitle.textContent = scTitleText;
  if (elements.radarSourceTag) elements.radarSourceTag.textContent = `Inbound From: ${activity.source_node || 'External Node'}`;
  if (elements.radarMeta) elements.radarMeta.textContent = `Timestamp: ${activity.timestamp} • Status: ${activity.status}`;
  if (elements.radarScenarioBadge) elements.radarScenarioBadge.textContent = scBadgeText;
  if (elements.radarPrimaryText) {
    elements.radarPrimaryText.textContent = `Patient P-${activity.patient_id}: "${activity.title}"`;
  }
  if (elements.radarSubText) {
    const details = activity.details || {};
    elements.radarSubText.textContent = isDup
      ? `Duplicate recommendation recognized (<1ms). Network push suppressed to protect Central Dashboard.`
      : `Video assignment dispatched to Central Dashboard (${details.dashboard_push || 'OK'}). Duration: ${details.duration_s || 10}s.`;
  }
  
  // Reset timer to return to standby after 10s of inactivity
  if (state.radarTimeout) clearTimeout(state.radarTimeout);
  state.radarTimeout = setTimeout(() => {
    elements.scenarioRadarCard.classList.remove('active-scenario-1', 'active-scenario-2', 'active-scenario-3');
    if (elements.radarTitle) elements.radarTitle.textContent = 'LIVE SCENARIO RADAR: STANDBY';
    if (elements.radarSourceTag) elements.radarSourceTag.textContent = 'Listening for AI Server & Pi Edge Triggers';
    if (elements.radarScenarioBadge) elements.radarScenarioBadge.textContent = 'Standby';
    if (elements.radarPrimaryText) elements.radarPrimaryText.textContent = 'Standby: Listening on Port 8080.';
    if (elements.radarSubText) elements.radarSubText.textContent = `Last processed: Patient P-${activity.patient_id} (${scBadgeText}) at ${activity.timestamp}.`;
  }, 10000);
}

// Fetch Activity History
async function fetchActivity() {
  try {
    const res = await fetch('/api/activity/latest');
    if (!res.ok) return;
    const data = await res.json();
    state.activities = data.recent_activities || [];
    renderActivityFeed();
    if (data.active_scenario && !state.radarTimeout) {
      updateScenarioRadar(data.active_scenario);
    }
  } catch (err) {
    console.warn('Could not fetch activity:', err);
  }
}

// Render Inbound Activity Feed
function renderActivityFeed() {
  if (!elements.activityFeedBody) return;
  
  if (state.activities.length === 0) {
    elements.activityFeedBody.innerHTML = `<div class="activity-placeholder">No inbound requests recorded yet. Click a test button above to simulate.</div>`;
    return;
  }
  
  elements.activityFeedBody.innerHTML = '';
  state.activities.forEach(act => {
    const scId = act.scenario_id || 1;
    const badgeClass = scId === 1 ? 'badge-success' : scId === 2 ? 'badge-info' : 'badge-purple';
    const isDup = act.status === 'shielded_duplicate';
    
    const card = document.createElement('div');
    card.className = 'activity-item';
    card.innerHTML = `
      <div class="activity-item-header">
        <span class="badge ${badgeClass}">Scenario ${scId}</span>
        <span class="badge ${isDup ? 'badge-warning' : 'badge-success'}">${isDup ? '🛡️ Shielded Duplicate' : '🚀 Dispatched'}</span>
      </div>
      <div class="activity-item-title">Patient P-${act.patient_id}: ${act.title}</div>
      <div class="activity-item-meta">
        <span><strong>Source:</strong> ${act.source_node || 'AI Server'}</span>
        <span>${act.timestamp}</span>
      </div>
    `;
    elements.activityFeedBody.appendChild(card);
  });
}

// Fetch Health & KPIs
async function fetchHealth() {
  try {
    const res = await fetch('/health');
    if (!res.ok) return;
    const data = await res.json();
    state.health = data;
    
    if (elements.kpiLedgerStatus) {
      elements.kpiLedgerStatus.textContent = `${data.stored_patients || 0} Patients Tracked`;
    }
    if (elements.kpiDedupCount) {
      elements.kpiDedupCount.textContent = `${data.total_recorded_assignments || 0} Total Assignments`;
    }
  } catch (err) {
    console.warn('Could not fetch health:', err);
  }
}

// Fetch Video Library
async function fetchLibrary() {
  try {
    const res = await fetch('/api/library');
    if (!res.ok) return;
    const data = await res.json();
    state.library = data;
    
    const totalExisting = data.existing_assets?.length || 0;
    const totalNew = data.new_videos?.length || 0;
    const totalVids = totalExisting + totalNew;
    const totalSubs = data.generated_subtitles?.length || 0;
    
    if (elements.kpiTotalVideos) elements.kpiTotalVideos.textContent = `${totalVids} MP4s`;
    if (elements.kpiTotalSubs) elements.kpiTotalSubs.textContent = `${totalSubs} WebVTT Tracks`;
    if (elements.libraryBrowserTitle) elements.libraryBrowserTitle.textContent = `Library Browser (${totalVids} Clips)`;
    if (elements.pillCountAll) elements.pillCountAll.textContent = `${totalVids}`;
    if (elements.pillCountNew) elements.pillCountNew.textContent = `${totalNew}`;
    if (elements.pillCountExisting) elements.pillCountExisting.textContent = `${totalExisting}`;
    
    renderPlaylist();
    if (!state.activeVideo && totalVids > 0) {
      const defaultVid = (data.existing_assets && data.existing_assets.length > 0) ? data.existing_assets[0] : (data.new_videos ? data.new_videos[0] : null);
      if (defaultVid) selectVideo(defaultVid, 'auto');
    }
  } catch (err) {
    console.warn('Could not fetch library:', err);
  }
}

// Render Playlist
function renderPlaylist() {
  if (!elements.videoList) return;
  elements.videoList.innerHTML = '';
  
  const query = (elements.videoSearchInput?.value || '').toLowerCase().trim();
  const allVideos = [
    ...(state.library.existing_assets || []).map(f => ({ filename: f, bucket: 'existing' })),
    ...(state.library.new_videos || []).map(f => ({ filename: f, bucket: 'new' }))
  ];
  
  // Sort numerically by ID
  allVideos.sort((a, b) => {
    const idA = parseInt(a.filename.match(/^(\d+)_/)?.[1] || '9999', 10);
    const idB = parseInt(b.filename.match(/^(\d+)_/)?.[1] || '9999', 10);
    return idA - idB;
  });
  
  const filtered = allVideos.filter(v => {
    if (state.playlistFilter && state.playlistFilter !== 'all') {
      if (v.bucket !== state.playlistFilter) return false;
    }
    return v.filename.toLowerCase().includes(query);
  });
  
  if (filtered.length === 0) {
    elements.videoList.innerHTML = `<div style="padding: 1.5rem; text-align: center; color: var(--text-muted);">No matching video clips found</div>`;
    return;
  }
  
  filtered.forEach(vid => {
    const match = vid.filename.match(/^(\d+)_/);
    const id = match ? match[1] : '#';
    const cleanTitle = vid.filename.replace(/^\d+_/, '').replace(/\.mp4$/, '').replace(/_/g, ' ');
    const isNew = vid.bucket === 'new';
    
    const item = document.createElement('div');
    item.className = `video-item ${state.activeVideo === vid.filename ? 'active' : ''} ${isNew ? 'is-new' : ''}`;
    item.innerHTML = `
      <div class="vid-id-badge" style="${isNew ? 'color: #7c3aed; background: rgba(139, 92, 246, 0.1); font-weight: 800;' : ''}">#${id}</div>
      <div class="vid-info">
        <div class="vid-title" title="${cleanTitle}">${cleanTitle}</div>
        <div class="vid-sub">
          ${isNew ? '<span class="badge-ai-new">✨ AI Generated (Veo)</span>' : '<span>1080p Curated</span>'}
          <span class="badge-sub-ready" title="Bilingual WebVTT tracks ready">CC EN | FR</span>
          <span>• ${isNew ? 'new_videos/' : 'existing_videos/'}</span>
        </div>
      </div>
    `;
    item.addEventListener('click', () => selectVideo(vid.filename, vid.bucket));
    elements.videoList.appendChild(item);
  });
}

// Select Video in Player
function selectVideo(filename, bucket = 'auto') {
  if (!filename) return;
  state.activeVideo = filename;
  
  // Intelligent bucket auto-detection
  if (!bucket || bucket === 'auto' || bucket === 'existing') {
    if ((state.library?.new_videos || []).includes(filename)) {
      bucket = 'new';
    } else {
      bucket = 'existing';
    }
  }

  renderPlaylist();
  
  const cleanTitle = filename.replace(/^\d+_/, '').replace(/\.mp4$/, '').replace(/_/g, ' ');
  const stem = filename.replace(/\.mp4$/, '');
  state.currentStem = stem;
  const isNew = bucket === 'new';
  
  if (elements.videoTitle) elements.videoTitle.textContent = cleanTitle;
  if (elements.videoMetaDetails) {
    elements.videoMetaDetails.innerHTML = `
      <span><strong>File:</strong> ${filename}</span>
      <span><strong>Resolution:</strong> 1920x1080 (30fps)</span>
      <span><strong>Category:</strong> ${isNew ? '✨ AI Generative Coaching (Scenario 3)' : 'Standard Curated Clinical Clip'}</span>
      <span><strong>Storage:</strong> ${bucket}_videos/</span>
      <span><strong>Subtitles:</strong> 🇬🇧 English & 🇫🇷 French Synchronized</span>
    `;
  }
  
  // Cleanly replace video element to completely eliminate zombie TextTracks cached in memory
  const oldVideo = elements.videoPlayer;
  const parent = oldVideo ? oldVideo.parentNode : null;
  const newVideo = document.createElement('video');
  newVideo.id = 'main-video-player';
  newVideo.controls = true;
  newVideo.preload = 'metadata';
  newVideo.playsInline = true;
  newVideo.crossOrigin = 'anonymous';
  if (oldVideo && oldVideo.className) newVideo.className = oldVideo.className;

  // Cache buster ensures browser network layer never reuses stale VTT files
  const cacheBuster = `?t=${Date.now()}`;
  const trackEn = document.createElement('track');
  trackEn.id = 'track-en';
  trackEn.kind = 'subtitles';
  trackEn.label = 'English';
  trackEn.srclang = 'en';
  trackEn.src = `/subtitles/${encodeURIComponent(stem)}.en.vtt${cacheBuster}`;

  const trackFr = document.createElement('track');
  trackFr.id = 'track-fr';
  trackFr.kind = 'subtitles';
  trackFr.label = 'Français';
  trackFr.srclang = 'fr';
  trackFr.src = `/subtitles/${encodeURIComponent(stem)}.fr.vtt${cacheBuster}`;

  newVideo.appendChild(trackEn);
  newVideo.appendChild(trackFr);

  // Set video source with byte-range support
  const videoUrl = `/videos/${bucket}/${filename}`;
  newVideo.src = videoUrl;

  if (parent && oldVideo) {
    parent.replaceChild(newVideo, oldVideo);
  }
  elements.videoPlayer = newVideo;
  elements.videoTrackEn = trackEn;
  elements.videoTrackFr = trackFr;

  // Re-attach video listeners to the clean video element
  attachVideoEventListeners(newVideo);

  // Load exact VTT cues for real-time high-visibility clinical overlay
  loadActiveVttCues(stem, state.activeLang);

  newVideo.load();
}

// Subtitle Toggles and Player Controls
function setupPlayerControls() {
  if (elements.videoSearchInput) {
    elements.videoSearchInput.addEventListener('input', renderPlaylist);
  }

  // Playlist filter pills
  const filterPills = document.querySelectorAll('.playlist-filter-pills .filter-pill');
  filterPills.forEach(pill => {
    pill.addEventListener('click', () => {
      filterPills.forEach(p => p.classList.remove('active'));
      pill.classList.add('active');
      state.playlistFilter = pill.getAttribute('data-filter') || 'all';
      renderPlaylist();
    });
  });
  
  elements.subBtnEn?.addEventListener('click', () => applySubtitleLanguage('en'));
  elements.subBtnFr?.addEventListener('click', () => applySubtitleLanguage('fr'));
  elements.subBtnOff?.addEventListener('click', () => applySubtitleLanguage('off'));

  if (elements.videoPlayer) {
    attachVideoEventListeners(elements.videoPlayer);
  }
}

function attachVideoEventListeners(video) {
  if (!video) return;
  
  video.addEventListener('loadedmetadata', () => {
    applySubtitleLanguage(state.activeLang);
  });

  video.addEventListener('timeupdate', () => {
    updateSubtitleOverlay();
  });

  video.addEventListener('seeking', () => {
    updateSubtitleOverlay();
  });

  video.addEventListener('seeked', () => {
    updateSubtitleOverlay();
  });

  video.addEventListener('play', () => {
    updateSubtitleOverlay();
  });

  video.addEventListener('pause', () => {
    updateSubtitleOverlay();
  });

  video.addEventListener('ended', () => {
    if (elements.videoSubtitleOverlay) {
      elements.videoSubtitleOverlay.classList.remove('visible');
    }
  });
}

function updateSubtitleOverlay() {
  if (!elements.videoSubtitleOverlay || !elements.videoPlayer) return;
  if (state.activeLang === 'off' || !state.activeCues || state.activeCues.length === 0) {
    elements.videoSubtitleOverlay.classList.remove('visible');
    return;
  }
  const cur = elements.videoPlayer.currentTime;
  const activeCue = state.activeCues.find(c => cur >= c.start && cur <= c.end);
  if (activeCue && activeCue.text) {
    elements.videoSubtitleOverlay.textContent = activeCue.text;
    elements.videoSubtitleOverlay.classList.add('visible');
  } else {
    elements.videoSubtitleOverlay.classList.remove('visible');
  }
}

async function loadActiveVttCues(stem, lang) {
  if (!stem || lang === 'off') {
    state.activeCues = [];
    if (elements.videoSubtitleOverlay) elements.videoSubtitleOverlay.classList.remove('visible');
    return;
  }
  try {
    const res = await fetch(`/subtitles/${encodeURIComponent(stem)}.${lang}.vtt?t=${Date.now()}`);
    if (!res.ok) {
      state.activeCues = [];
      if (elements.videoSubtitleOverlay) elements.videoSubtitleOverlay.classList.remove('visible');
      return;
    }
    const text = await res.text();
    state.activeCues = parseVttToCues(text);
    updateSubtitleOverlay();
  } catch (err) {
    console.warn('Could not load VTT cues for overlay:', err);
    state.activeCues = [];
  }
}

function parseVttToCues(vttText) {
  const cues = [];
  const lines = vttText.split(/\r?\n/);
  let currentStart = null;
  let currentEnd = null;
  let currentText = [];

  for (let i = 0; i < lines.length; i++) {
    const line = lines[i].trim();
    if (line.includes('-->')) {
      const parts = line.split('-->');
      if (parts.length === 2) {
        currentStart = timeToSeconds(parts[0].trim());
        currentEnd = timeToSeconds(parts[1].trim());
        currentText = [];
      }
    } else if (line === '') {
      if (currentStart !== null && currentEnd !== null && currentText.length > 0) {
        cues.push({ start: currentStart, end: currentEnd, text: currentText.join(' ') });
        currentStart = null;
        currentEnd = null;
        currentText = [];
      }
    } else if (currentStart !== null && !line.startsWith('NOTE') && !line.startsWith('WEBVTT')) {
      currentText.push(line);
    }
  }
  if (currentStart !== null && currentEnd !== null && currentText.length > 0) {
    cues.push({ start: currentStart, end: currentEnd, text: currentText.join(' ') });
  }
  return cues;
}

function timeToSeconds(tStr) {
  const parts = tStr.split(':');
  if (parts.length === 3) {
    return parseFloat(parts[0]) * 3600 + parseFloat(parts[1]) * 60 + parseFloat(parts[2]);
  } else if (parts.length === 2) {
    return parseFloat(parts[0]) * 60 + parseFloat(parts[1]);
  }
  return parseFloat(tStr) || 0;
}

function applySubtitleLanguage(lang) {
  state.activeLang = lang;
  elements.subBtnEn?.classList.toggle('active', lang === 'en');
  elements.subBtnFr?.classList.toggle('active', lang === 'fr');
  elements.subBtnOff?.classList.toggle('active', lang === 'off');
  
  if (elements.subtitleStatusIndicator) {
    if (lang === 'en') {
      elements.subtitleStatusIndicator.textContent = '● Subtitles: English (.en.vtt)';
      elements.subtitleStatusIndicator.className = 'subtitle-status-pill active-en';
    } else if (lang === 'fr') {
      elements.subtitleStatusIndicator.textContent = '● Subtitles: Français (.fr.vtt)';
      elements.subtitleStatusIndicator.className = 'subtitle-status-pill active-fr';
    } else {
      elements.subtitleStatusIndicator.textContent = '○ Subtitles: Off';
      elements.subtitleStatusIndicator.className = 'subtitle-status-pill active-off';
    }
  }

  // Reload overlay cues for the selected language
  if (state.currentStem) {
    loadActiveVttCues(state.currentStem, lang);
  }

  // Update native HTML5 textTracks (mode='hidden' keeps track active in memory without native visual duplication)
  if (!elements.videoPlayer) return;
  const tracks = elements.videoPlayer.textTracks;
  for (let i = 0; i < tracks.length; i++) {
    const track = tracks[i];
    if (lang === 'off') {
      track.mode = 'disabled';
    } else if (track.language === lang) {
      track.mode = 'hidden'; // Kept loaded for accessibility/events, native visual display suppressed
    } else {
      track.mode = 'disabled';
    }
  }
}

// Fetch Trigger Catalog
async function fetchTriggers() {
  try {
    const res = await fetch('/api/triggers/catalog');
    if (!res.ok) return;
    const data = await res.json();
    state.triggers = data.triggers || data.video_triggers || [];
    if (elements.triggerCountBadge) {
      elements.triggerCountBadge.textContent = `${state.triggers.length}`;
    }
    renderTriggersTable();
  } catch (err) {
    console.warn('Could not fetch trigger catalog:', err);
  }
}

// Render Trigger Catalog
function renderTriggersTable() {
  if (!elements.triggersTableBody) return;
  elements.triggersTableBody.innerHTML = '';
  
  const query = (elements.triggerSearchInput?.value || '').toLowerCase().trim();
  const filtered = state.triggers.filter(t => {
    const text = `${t.video_id} ${t.title} ${t.category} ${t.subtopic} ${JSON.stringify(t.trigger_conditions)}`.toLowerCase();
    return text.includes(query);
  });
  
  if (filtered.length === 0) {
    elements.triggersTableBody.innerHTML = `<tr><td colspan="6" style="text-align:center; padding: 2rem; color: var(--text-muted);">No triggers match search criteria</td></tr>`;
    return;
  }
  
  filtered.forEach(t => {
    const condHtml = Object.entries(t.trigger_conditions || {})
      .map(([k, v]) => `<span class="badge badge-info" style="margin:2px 0;">${k} ${v}</span>`)
      .join('<br>') || '<span style="color:var(--text-muted);">-</span>';
    
    const isNew = t.bucket === 'new' || (state.library?.new_videos || []).includes(t.filename);
    const tr = document.createElement('tr');
    tr.innerHTML = `
      <td style="font-family: var(--font-mono); font-weight: 700; color: ${isNew ? '#7c3aed' : 'var(--accent-cyan)'};">#${t.video_id}</td>
      <td style="font-weight: 600;">
        ${t.title}
        ${isNew ? '<span class="badge-ai-new" style="margin-left: 6px;">AI Generated</span>' : ''}
      </td>
      <td>
        <span class="badge badge-success">${t.category || 'Clinical'}</span>
        <span class="badge-sub-ready" style="margin-left: 4px;">CC EN/FR</span>
      </td>
      <td>${condHtml}</td>
      <td>${t.duration_s || 10}s</td>
      <td>
        <button class="btn btn-secondary btn-sm" onclick="playCatalogVideo('${t.filename}', '${isNew ? 'new' : 'existing'}')" style="padding: 0.2rem 0.5rem; font-size:0.75rem;">
          ▶ Play
        </button>
      </td>
    `;
    elements.triggersTableBody.appendChild(tr);
  });
}

window.playCatalogVideo = function(filename, bucket = 'auto') {
  selectVideo(filename, bucket);
  elements.tabBtns[0].click();
  elements.videoPlayer.play().catch(() => {});
};

// Fetch Persistent Assignment Ledger
async function fetchHistory() {
  try {
    const res = await fetch('/api/assignments/history');
    if (!res.ok) return;
    const data = await res.json();
    
    // Flatten records
    const patientsMap = data.patients || {};
    const flatList = [];
    Object.entries(patientsMap).forEach(([pid, entries]) => {
      entries.forEach(entry => {
        flatList.push({ patient_id: pid, ...entry });
      });
    });
    
    // Sort descending by assigned_at
    flatList.sort((a, b) => new Date(b.assigned_at) - new Date(a.assigned_at));
    state.history = flatList;
    
    if (elements.ledgerCountBadge) {
      elements.ledgerCountBadge.textContent = `${flatList.length}`;
    }
    renderLedgerTable();
  } catch (err) {
    console.warn('Could not fetch assignment history:', err);
  }
}

// Render Ledger Table
function renderLedgerTable() {
  if (!elements.ledgerTableBody) return;
  elements.ledgerTableBody.innerHTML = '';
  
  const query = (elements.ledgerSearchInput?.value || '').toLowerCase().trim();
  const filtered = state.history.filter(h => {
    const text = `${h.patient_id} ${h.video_filename} ${h.title} ${h.event_id || ''}`.toLowerCase();
    return text.includes(query);
  });
  
  if (filtered.length === 0) {
    elements.ledgerTableBody.innerHTML = `<tr><td colspan="6" style="text-align:center; padding: 2rem; color: var(--text-muted);">No persistent assignments recorded yet.</td></tr>`;
    return;
  }
  
  filtered.forEach(h => {
    const timeStr = h.assigned_at ? new Date(h.assigned_at).toLocaleTimeString() : '-';
    const tr = document.createElement('tr');
    tr.innerHTML = `
      <td style="font-family: var(--font-mono); font-weight: 700; color: var(--accent-emerald);">P-${h.patient_id}</td>
      <td style="font-weight: 600;">${h.title || h.video_filename}</td>
      <td><span class="badge ${h.video_type === 'package' ? 'badge-warning' : 'badge-info'}">${h.video_type || 'single'}</span></td>
      <td style="font-family: var(--font-mono); font-size: 0.75rem;">${h.event_id || 'manual'}</td>
      <td><span class="badge badge-success">${h.dashboard_push_status || 'delivered'}</span></td>
      <td style="color: var(--text-secondary); font-size: 0.75rem;">${timeStr}</td>
    `;
    elements.ledgerTableBody.appendChild(tr);
  });
}

// Terminal Log Streaming (SSE)
function initLogStream() {
  if (state.eventSource) {
    state.eventSource.close();
  }
  
  try {
    state.eventSource = new EventSource('/api/logs/stream');
    state.eventSource.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        if (data.type === 'scenario_activity') {
          updateScenarioRadar(data.activity);
          fetchActivity();
        } else {
          appendLogLine(data);
        }
      } catch (e) {}
    };
    state.eventSource.onerror = () => {
      setTimeout(initLogStream, 3000);
    };
  } catch (err) {
    console.warn('SSE Log stream init error:', err);
  }
}

function appendLogLine(entry) {
  if (!elements.terminalLogs) return;
  
  const rawMsg = entry.raw || entry.message || '';
  const filter = (elements.logFilterInput?.value || '').toLowerCase().trim();
  if (filter && !rawMsg.toLowerCase().includes(filter)) {
    return;
  }
  
  let lineClass = 'log-info';
  if (rawMsg.includes('[ALERT]') || rawMsg.includes('[LIVE ASSET WATCHER]')) lineClass = 'log-alert';
  else if (rawMsg.includes('[DEDUPLICATION SHIELD]')) lineClass = 'log-shield';
  else if (rawMsg.includes('[SCENARIO 1 ACTIVE]')) lineClass = 'log-shield';
  else if (rawMsg.includes('[SCENARIO 2 ACTIVE]')) lineClass = 'log-info';
  else if (rawMsg.includes('[SCENARIO 3 ACTIVE]')) lineClass = 'log-warn';
  else if (rawMsg.includes('[WARN]') || rawMsg.includes('WARNING')) lineClass = 'log-warn';
  else if (rawMsg.includes('[ERROR]') || rawMsg.includes('ERROR')) lineClass = 'log-error';
  
  const lineDiv = document.createElement('div');
  lineDiv.className = `log-line ${lineClass}`;
  lineDiv.textContent = rawMsg;
  elements.terminalLogs.appendChild(lineDiv);
  
  // Limit DOM nodes in terminal to 600
  if (elements.terminalLogs.childNodes.length > 600) {
    elements.terminalLogs.removeChild(elements.terminalLogs.firstChild);
  }
  
  if (state.logAutoScroll) {
    elements.terminalLogs.scrollTop = elements.terminalLogs.scrollHeight;
  }
}

function setupTerminalControls() {
  elements.btnLogScrollToggle?.addEventListener('click', () => {
    state.logAutoScroll = !state.logAutoScroll;
    elements.btnLogScrollToggle.textContent = state.logAutoScroll ? 'Auto-Scroll: ON' : 'Auto-Scroll: OFF';
  });
  
  elements.btnClearLogs?.addEventListener('click', () => {
    if (elements.terminalLogs) elements.terminalLogs.innerHTML = '';
  });
  
  elements.logFilterInput?.addEventListener('input', () => {
    fetch('/api/logs/recent?limit=100')
      .then(res => res.json())
      .then(data => {
        if (elements.terminalLogs) elements.terminalLogs.innerHTML = '';
        (data.logs || []).forEach(appendLogLine);
      });
  });
}

// Action Buttons
function setupActionButtons() {
  // Refresh KPIs
  elements.btnRefreshKpis?.addEventListener('click', async () => {
    showToast('Recalculating live KPIs and metrics...', 'info');
    await fetchKPIs(false);
    showToast('Clinical KPIs & graphs refreshed!', 'success');
  });

  // Rebenchmark
  elements.btnRebenchmark?.addEventListener('click', async () => {
    if (elements.btnRebenchmark) elements.btnRebenchmark.disabled = true;
    showToast('Executing live endpoint benchmark suite...', 'info');
    try {
      await fetchKPIs(true);
      showToast('Live benchmark completed & graphs updated!', 'success');
    } catch (e) {
      showToast('Benchmark run failed: ' + e, 'warn');
    } finally {
      if (elements.btnRebenchmark) elements.btnRebenchmark.disabled = false;
    }
  });

  // Sync Triggers
  elements.btnSyncTriggers?.addEventListener('click', async () => {
    elements.btnSyncTriggers.disabled = true;
    showToast('Broadcasting triggers to AI Server, RPi 5, and Dashboard...', 'info');
    try {
      const res = await fetch('/api/triggers/broadcast', { method: 'POST', headers: getAuthHeaders() });
      showToast('Dynamic triggers broadcast complete!', 'success');
    } catch (err) {
      showToast('Broadcast failed: ' + err, 'warn');
    } finally {
      elements.btnSyncTriggers.disabled = false;
    }
  });
  
  // Rebuild Catalog
  elements.btnRebuildCatalog?.addEventListener('click', async () => {
    elements.btnRebuildCatalog.disabled = true;
    showToast('Scanning library and rebuilding metadata...', 'info');
    try {
      const res = await fetch('/api/catalog/rebuild', { method: 'POST', headers: getAuthHeaders() });
      const data = await res.json();
      showToast(`Rebuilt: ${data.total_videos} videos, ${data.total_subtitles} subtitle tracks`, 'success');
      fetchLibrary();
      fetchTriggers();
    } catch (err) {
      showToast('Rebuild failed: ' + err, 'warn');
    } finally {
      elements.btnRebuildCatalog.disabled = false;
    }
  });
  
  // Clear Ledger
  elements.btnClearLedger?.addEventListener('click', async () => {
    if (!confirm('Are you sure you want to clear the persistent video assignment ledger?')) return;
    try {
      const res = await fetch('/api/assignments/reset', { method: 'DELETE', headers: getAuthHeaders() });
      showToast('Assignment ledger reset successfully', 'success');
      fetchHistory();
      fetchHealth();
    } catch (err) {
      showToast('Clear failed: ' + err, 'warn');
    }
  });
  
  // Test Scenario 1
  elements.btnTestScenario1?.addEventListener('click', async () => {
    elements.btnTestScenario1.disabled = true;
    const testPid = '10' + Math.floor(100 + Math.random() * 900);
    showToast(`Testing Scenario 1 (Single Clip) for Patient ${testPid}...`, 'info');
    try {
      const reqPayload = {
        event_id: 'EVT_SC1_' + Date.now(),
        patient_id: testPid,
        title: 'Nasal Congestion Relief & Heated Humidification',
        video_filename: '9_Nasal_congestion_relief.mp4',
        category: 'Comfort & Hydration',
        trigger_reason: 'High nasal resistance reported in telemetry',
        relevance: 'high',
        duration_s: 10.0
      };
      const res = await fetch('/api/orchestrate', {
        method: 'POST',
        headers: getAuthHeaders({
          'Content-Type': 'application/json'
        }),
        body: JSON.stringify(reqPayload)
      });
      const data = await res.json();
      showToast(`Scenario 1 Active: Video 9 assigned to Patient ${testPid}`, 'success');
      fetchHistory();
      fetchHealth();
      fetchActivity();
    } catch (err) {
      showToast('Scenario 1 Test failed: ' + err, 'warn');
    } finally {
      elements.btnTestScenario1.disabled = false;
    }
  });
  
  // Test Scenario 2
  elements.btnTestScenario2?.addEventListener('click', async () => {
    elements.btnTestScenario2.disabled = true;
    const testPid = '20' + Math.floor(100 + Math.random() * 900);
    showToast(`Testing Scenario 2 (Multi-Clip Sequence) for Patient ${testPid}...`, 'info');
    try {
      const reqPayload = {
        event_id: 'EVT_SC2_' + Date.now(),
        patient_id: testPid,
        title: 'Dual-Factor Mask Leak & Dryness Coaching Sequence',
        video_type: 'package',
        scenario: 'scenario_2_stitched_sequence',
        category: 'Compound Anomaly Coaching',
        trigger_reason: 'Leak >= 24 L/min + Dry Mouth Alert',
        transition_type: 'fade_1_5s',
        clips: [
          { video_filename: '1_Mask_leak_adjust_straps.mp4', duration_s: 10.0, title: 'Mask Strap Adjustment' },
          { video_filename: '2_Mask_leak_refit_while_lying_down.mp4', duration_s: 10.0, title: 'Mask Refit in Recline Position' }
        ]
      };
      const res = await fetch('/api/orchestrate', {
        method: 'POST',
        headers: getAuthHeaders({
          'Content-Type': 'application/json'
        }),
        body: JSON.stringify(reqPayload)
      });
      const data = await res.json();
      showToast(`Scenario 2 Active: 2-Clip sequence assigned to Patient ${testPid}`, 'success');
      fetchHistory();
      fetchHealth();
      fetchActivity();
    } catch (err) {
      showToast('Scenario 2 Test failed: ' + err, 'warn');
    } finally {
      elements.btnTestScenario2.disabled = false;
    }
  });
  
  // Test Scenario 3
  elements.btnTestScenario3?.addEventListener('click', async () => {
    elements.btnTestScenario3.disabled = true;
    const testPid = '30' + Math.floor(100 + Math.random() * 900);
    showToast(`Testing Scenario 3 (Google Veo AI Video) for Patient ${testPid}...`, 'info');
    try {
      const reqPayload = {
        event_id: 'EVT_SC3_' + Date.now(),
        patient_id: testPid,
        prompt: 'Personalized 3D CPAP tubing repositioning during active tossing and turning in sleep',
        model: 'veo-3.1-generate-preview'
      };
      const res = await fetch('/api/vertex-generate', {
        method: 'POST',
        headers: getAuthHeaders({
          'Content-Type': 'application/json'
        }),
        body: JSON.stringify(reqPayload)
      });
      const data = await res.json();
      showToast(`Scenario 3 Active: ${data.generated_video_filename || 'Veo synthesis registered'}`, 'success');
      fetchLibrary();
      fetchActivity();
    } catch (err) {
      showToast('Scenario 3 Test failed: ' + err, 'warn');
    } finally {
      elements.btnTestScenario3.disabled = false;
    }
  });
}

// ==============================================================================
// CLINICAL KPIS, GAUGES & GRAPHS RENDERING ENGINE
// ==============================================================================
async function fetchKPIs(benchmark = false) {
  try {
    const url = benchmark ? '/api/kpis?benchmark=true' : '/api/kpis';
    const res = await fetch(url);
    if (!res.ok) return;
    const data = await res.json();
    state.kpis = data;
    renderGauges(data);
    renderTopicDistributionGraph(data.topic_distribution);
    renderLatencyBenchmarkGraph(data.latencies);
    renderSafetyStratification(data.safety_distribution);
    renderStorageMetrics(data.storage);
    if (elements.kpiTimestampDisplay) {
      elements.kpiTimestampDisplay.textContent = `Benchmark: ${data.timestamp || 'Active'}`;
    }
  } catch (err) {
    console.warn('Could not fetch KPIs:', err);
  }
}

function setRadialGauge(circleId, valId, percent, textDisplay) {
  const circle = document.getElementById(circleId);
  const textElem = document.getElementById(valId);
  if (circle) {
    const maxOffset = 216; // stroke-dasharray is "216 75"
    const clamped = Math.min(100, Math.max(0, percent));
    const offset = maxOffset * (1 - (clamped / 100));
    circle.style.strokeDashoffset = offset;
  }
  if (textElem && textDisplay !== undefined) {
    textElem.textContent = textDisplay;
  }
}

function renderGauges(kpis) {
  if (!kpis || !kpis.gauges) return;
  const g = kpis.gauges;

  // Top Card Mini-Gauges
  const topLatencyVal = document.getElementById('kpi-latency-val');
  if (topLatencyVal && g.latency_index) {
    topLatencyVal.textContent = `${g.latency_index.value} ms`;
  }

  // Showcase Radial Gauges (Circumference arc dasharray: 216)
  if (g.system_health) {
    setRadialGauge('gauge-health-circle', 'gauge-health-val', g.system_health.value, `${g.system_health.value}%`);
  }
  if (g.content_coverage) {
    setRadialGauge('gauge-content-circle', 'gauge-content-val', g.content_coverage.value, `${g.content_coverage.value}%`);
  }
  if (g.subtitle_coverage) {
    setRadialGauge('gauge-subs-circle', 'gauge-subs-val', g.subtitle_coverage.value, `${g.subtitle_coverage.value}%`);
  }
  if (g.latency_index) {
    const latMs = g.latency_index.value;
    const latScore = Math.max(10, Math.min(100, (1 - (latMs / 35)) * 100));
    setRadialGauge('gauge-latency-circle', 'gauge-latency-num', latScore, `${latMs}ms`);
  }
  if (g.security_shield) {
    setRadialGauge('gauge-sec-circle', 'gauge-sec-val', g.security_shield.value, `${g.security_shield.value}%`);
  }
  if (g.dedup_accuracy) {
    setRadialGauge('gauge-dedup-circle', 'gauge-dedup-val', g.dedup_accuracy.value, `<1ms`);
  }
}

function renderTopicDistributionGraph(topics) {
  const container = elements.topicDistributionBars;
  if (!container || !topics) return;

  const topicIcons = {
    'Wearable Biomarkers': '🩺',
    'Tips & Tricks': '💡',
    'Mask & Equipment': '🤿',
    'Clinical Alerts': '🚨',
    'Comfort': '🛏️',
    'Personalized Coaching': '🎯',
    'Maintenance': '🔧'
  };

  const topicGradients = {
    'Wearable Biomarkers': 'linear-gradient(90deg, #0284c7, #38bdf8)',
    'Tips & Tricks': 'linear-gradient(90deg, #059669, #34d399)',
    'Mask & Equipment': 'linear-gradient(90deg, #4f46e5, #818cf8)',
    'Clinical Alerts': 'linear-gradient(90deg, #e11d48, #f43f5e)',
    'Comfort': 'linear-gradient(90deg, #d97706, #fbbf24)',
    'Personalized Coaching': 'linear-gradient(90deg, #7c3aed, #a855f7)',
    'Maintenance': 'linear-gradient(90deg, #475569, #94a3b8)'
  };

  const total = Object.values(topics).reduce((a, b) => a + b, 0) || 1;
  const sorted = Object.entries(topics).sort((a, b) => b[1] - a[1]);

  container.innerHTML = '';
  sorted.forEach(([topic, count]) => {
    const pct = ((count / total) * 100).toFixed(1);
    const icon = topicIcons[topic] || '📋';
    const grad = topicGradients[topic] || 'linear-gradient(90deg, #0284c7, #0ea5e9)';

    const row = document.createElement('div');
    row.className = 'topic-bar-row';
    row.innerHTML = `
      <div class="topic-bar-meta">
        <span class="topic-name"><span>${icon}</span> ${topic}</span>
        <span class="topic-stat">${count} clips (${pct}%)</span>
      </div>
      <div class="topic-track">
        <div class="topic-fill" style="width: 0%; background: ${grad};" data-target-width="${pct}%"></div>
      </div>
    `;
    container.appendChild(row);
  });

  setTimeout(() => {
    container.querySelectorAll('.topic-fill').forEach(fill => {
      fill.style.width = fill.getAttribute('data-target-width');
    });
  }, 50);
}

function renderLatencyBenchmarkGraph(latencies) {
  const container = elements.latencyColumnsContainer;
  if (!container || !latencies) return;

  const endpointLabels = {
    'health_ping_ms': 'Health Ping',
    'library_query_ms': 'Catalog API',
    'stream_byte_ms': 'Stream TTFB',
    'subtitle_fetch_ms': 'Subtitles',
    'orchestrate_ms': 'Orchestrate'
  };

  container.innerHTML = '';
  const maxScale = 25.0;

  Object.entries(latencies).forEach(([k, val]) => {
    const num = typeof val === 'number' ? val : 10.0;
    const heightPct = Math.min(100, Math.max(12, (num / maxScale) * 100));
    const label = endpointLabels[k] || k;
    const isSub10 = num < 10.0;

    const col = document.createElement('div');
    col.className = 'latency-col';
    col.innerHTML = `
      <div class="latency-col-val">${num}ms</div>
      <div class="latency-col-bar ${isSub10 ? 'sub-10ms' : ''}" style="height: 0%;" data-target-height="${heightPct}%" title="${label}: ${num}ms"></div>
      <div class="latency-col-label">${label}</div>
    `;
    container.appendChild(col);
  });

  setTimeout(() => {
    container.querySelectorAll('.latency-col-bar').forEach(bar => {
      bar.style.height = bar.getAttribute('data-target-height');
    });
  }, 50);
}

function renderSafetyStratification(safety) {
  const container = elements.safetyStratificationBody;
  if (!container || !safety) return;

  const safetyLabels = {
    'standard': { name: 'Standard Coaching', icon: '🟢', badge: 'badge-success', grad: 'linear-gradient(90deg, #059669, #10b981)' },
    'biomarker_alert': { name: 'Biomarker Alert Level', icon: '🟡', badge: 'badge-warning', grad: 'linear-gradient(90deg, #d97706, #fbbf24)' },
    'clinical_alert': { name: 'Clinical Consultation Needed', icon: '🟠', badge: 'badge-warning', grad: 'linear-gradient(90deg, #ea580c, #f97316)' },
    'critical_alert': { name: 'Critical Escalation Alert', icon: '🔴', badge: 'badge-danger', grad: 'linear-gradient(90deg, #e11d48, #f43f5e)' }
  };

  const total = Object.values(safety).reduce((a, b) => a + b, 0) || 1;
  container.innerHTML = '';

  Object.entries(safety).forEach(([lvl, count]) => {
    const info = safetyLabels[lvl] || { name: lvl, icon: '⚪', badge: 'badge-info', grad: 'linear-gradient(90deg, #0284c7, #38bdf8)' };
    const pct = ((count / total) * 100).toFixed(1);

    const row = document.createElement('div');
    row.className = 'topic-bar-row';
    row.innerHTML = `
      <div class="topic-bar-meta">
        <span class="topic-name"><span>${info.icon}</span> ${info.name}</span>
        <span class="badge ${info.badge}">${count} videos (${pct}%)</span>
      </div>
      <div class="topic-track">
        <div class="topic-fill" style="width: 0%; background: ${info.grad};" data-target-width="${pct}%"></div>
      </div>
    `;
    container.appendChild(row);
  });

  setTimeout(() => {
    container.querySelectorAll('.topic-fill').forEach(fill => {
      fill.style.width = fill.getAttribute('data-target-width');
    });
  }, 50);
}

function renderStorageMetrics(storage) {
  if (!storage) return;
  if (elements.kpiStorageTotal) {
    elements.kpiStorageTotal.textContent = `${storage.total_mb} MB Total`;
  }
  if (elements.storageValVideos) elements.storageValVideos.textContent = `${storage.videos_mb} MB`;
  if (elements.storageValMeta) elements.storageValMeta.textContent = `${storage.metadata_mb} MB`;
  if (elements.storageValSubs) elements.storageValSubs.textContent = `${storage.subtitles_kb} KB`;

  const total = storage.total_mb || 1;
  const vidPct = ((storage.videos_mb / total) * 100).toFixed(1);
  const metaPct = ((storage.metadata_mb / total) * 100).toFixed(1);
  const subPct = Math.max(0.5, ((storage.subtitles_kb / 1024 / total) * 100)).toFixed(1);

  if (elements.storageSegVideos) elements.storageSegVideos.style.width = `${vidPct}%`;
  if (elements.storageSegMeta) elements.storageSegMeta.style.width = `${metaPct}%`;
  if (elements.storageSegSubs) elements.storageSegSubs.style.width = `${subPct}%`;
}


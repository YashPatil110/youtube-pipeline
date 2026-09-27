// State management
let pollInterval = null;

function setDuration(sec) {
  document.getElementById('duration-sec').value = sec;
}

function showToast(message, type = 'success') {
  const toast = document.getElementById('toast');
  toast.innerText = message;
  toast.className = `show toast-${type}`;
  setTimeout(() => {
    toast.className = '';
  }, 4000);
}

// Fetch network IP for mobile convenience badge
async function loadNetworkInfo() {
  try {
    const res = await fetch('/api/info');
    const data = await res.json();
    if (data.ip) {
      document.getElementById('network-ip-label').innerText = `Mobile Access: http://${data.ip}:${data.port}`;
    }
  } catch (e) {
    console.error('Could not fetch network info', e);
  }
}

// Load Shorts History
async function loadHistory() {
  try {
    const res = await fetch('/api/history');
    const history = await res.json();
    const listEl = document.getElementById('history-list');

    if (!history || history.length === 0) {
      listEl.innerHTML = '<p style="color:var(--text-dim); font-size:0.9rem;">No shorts generated yet.</p>';
      return;
    }

    listEl.innerHTML = history.slice().reverse().map(item => {
      const isApproved = item.decision === 'approved';
      const badgeClass = isApproved ? 'badge-approved' : 'badge-discarded';
      const badgeIcon = isApproved ? '✅' : '❌';
      const linkHtml = item.youtube_url 
        ? `<div class="history-action"><a href="${item.youtube_url}" target="_blank" rel="noopener"><span>▶</span> Watch Short</a></div>` 
        : '';

      return `
        <div class="history-item">
          <div class="history-info">
            <span class="history-title">${escapeHtml(item.title || 'Untitled Short')}</span>
            <span class="history-meta">${item.timestamp} • ${item.source_url}</span>
          </div>
          <div style="display:flex; align-items:center; gap:1rem;">
            <span class="badge ${badgeClass}">${badgeIcon} ${item.decision}</span>
            ${linkHtml}
          </div>
        </div>
      `;
    }).join('');
  } catch (err) {
    console.error('Failed to load history', err);
  }
}

function escapeHtml(str) {
  return str.replace(/[&<>'"]/g, tag => ({
    '&': '&amp;',
    '<': '&lt;',
    '>': '&gt;',
    "'": '&#39;',
    '"': '&quot;'
  }[tag] || tag));
}

// Handle Clip Generation Form
document.getElementById('clip-form').addEventListener('submit', async (e) => {
  e.preventDefault();

  const url = document.getElementById('video-url').value.trim();
  const startSec = parseInt(document.getElementById('start-sec').value, 10);
  const durationSec = parseInt(document.getElementById('duration-sec').value, 10);

  if (!url) {
    showToast('Please enter a valid YouTube URL', 'error');
    return;
  }

  const btnGenerate = document.getElementById('btn-generate');
  btnGenerate.disabled = true;
  btnGenerate.innerHTML = '<span>⏳</span> Processing Video...';

  // Reset preview & review elements
  document.getElementById('review-metadata-box').style.display = 'none';
  document.getElementById('action-buttons-grid').style.display = 'none';
  document.getElementById('preview-video').style.display = 'none';
  document.getElementById('empty-preview').style.display = 'flex';

  // Show progress container
  const progressContainer = document.getElementById('progress-container');
  progressContainer.style.display = 'block';
  document.getElementById('progress-bar-fill').style.width = '10%';
  document.getElementById('progress-step-text').innerText = 'Initializing downloader...';

  try {
    const response = await fetch('/api/process', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ url, start_sec: startSec, duration_sec: durationSec })
    });

    const result = await response.json();
    if (!response.ok) {
      throw new Error(result.detail || 'Failed to start processing');
    }

    startPolling();
  } catch (err) {
    showToast(err.message, 'error');
    btnGenerate.disabled = false;
    btnGenerate.innerHTML = '<span>✨</span> Generate Vertical Clip & AI Metadata';
    progressContainer.style.display = 'none';
  }
});

// Poll Backend Status
function startPolling() {
  if (pollInterval) clearInterval(pollInterval);

  pollInterval = setInterval(async () => {
    try {
      const res = await fetch('/api/status');
      const data = await res.json();

      const progressBar = document.getElementById('progress-bar-fill');
      const stepText = document.getElementById('progress-step-text');
      const btnGenerate = document.getElementById('btn-generate');

      if (data.status === 'processing') {
        stepText.innerText = data.step || 'Processing...';
        progressBar.style.width = `${data.progress || 35}%`;
      } else if (data.status === 'uploading') {
        progressContainer.style.display = 'block';
        stepText.innerText = data.step || 'Uploading to YouTube...';
        progressBar.style.width = `${data.progress || 10}%`;
        const btnApprove = document.getElementById('btn-approve');
        if (btnApprove) btnApprove.innerHTML = `<span>⏳</span> ${data.step}`;
      } else if (data.status === 'published') {
        clearInterval(pollInterval);
        progressBar.style.width = '100%';
        stepText.innerHTML = `🎉 <b>Published!</b> <a href="${data.youtube_url}" target="_blank" style="color:#818cf8; text-decoration:underline; font-weight:600; margin-left:6px;">Watch on YouTube ➔</a>`;
        showToast('🎉 Successfully published to YouTube Shorts!', 'success');
        
        const btnApprove = document.getElementById('btn-approve');
        if (btnApprove) {
          btnApprove.disabled = false;
          btnApprove.innerHTML = '<span>🚀</span> Published!';
        }
        document.getElementById('btn-discard').disabled = false;
        loadHistory();
      } else if (data.status === 'review_ready') {
        clearInterval(pollInterval);
        progressBar.style.width = '100%';
        stepText.innerText = '✨ Clip Ready For Review!';
        btnGenerate.disabled = false;
        btnGenerate.innerHTML = '<span>✨</span> Generate Another Clip';

        // Load preview video
        const video = document.getElementById('preview-video');
        video.src = `/api/video?t=${Date.now()}`;
        video.style.display = 'block';
        document.getElementById('empty-preview').style.display = 'none';
        video.load();

        // Populate editable metadata
        if (data.metadata) {
          document.getElementById('edit-title').value = data.metadata.title || '';
          document.getElementById('edit-description').value = data.metadata.description || '';
          document.getElementById('edit-tags').value = (data.metadata.tags || []).join(', ');
          document.getElementById('review-metadata-box').style.display = 'block';
        }

        // Show Approve & Discard buttons
        document.getElementById('action-buttons-grid').style.display = 'grid';
        showToast('Vertical Short is ready for your review!', 'success');
      } else if (data.status === 'error') {
        clearInterval(pollInterval);
        stepText.innerText = '❌ Failed';
        showToast(data.error_message || 'Processing error occurred', 'error');
        btnGenerate.disabled = false;
        btnGenerate.innerHTML = '<span>✨</span> Generate Vertical Clip & AI Metadata';
        const btnApprove = document.getElementById('btn-approve');
        if (btnApprove) {
          btnApprove.disabled = false;
          btnApprove.innerHTML = '<span>🚀</span> Publish to YouTube';
        }
        document.getElementById('btn-discard').disabled = false;
      }
    } catch (err) {
      console.error('Error polling status', err);
    }
  }, 1000);
}

// Publish to YouTube
async function publishShort() {
  const btnApprove = document.getElementById('btn-approve');
  const btnDiscard = document.getElementById('btn-discard');
  btnApprove.disabled = true;
  btnDiscard.disabled = true;
  btnApprove.innerHTML = '<span>⏳</span> Connecting to YouTube...';

  // Show progress bar for live upload tracking
  const progressContainer = document.getElementById('progress-container');
  progressContainer.style.display = 'block';
  document.getElementById('progress-bar-fill').style.width = '5%';
  document.getElementById('progress-step-text').innerText = 'Initializing YouTube upload...';

  const title = document.getElementById('edit-title').value;
  const description = document.getElementById('edit-description').value;
  const rawTags = document.getElementById('edit-tags').value;
  const tags = rawTags.split(',').map(t => t.trim()).filter(Boolean);

  try {
    const res = await fetch('/api/publish', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ title, description, tags })
    });

    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || 'Upload failed');

    // Start polling status to show live percentage
    startPolling();
  } catch (err) {
    showToast(err.message, 'error');
    btnApprove.disabled = false;
    btnDiscard.disabled = false;
    btnApprove.innerHTML = '<span>🚀</span> Publish to YouTube';
  }
}

// Discard Short
async function discardShort() {
  if (!confirm('Are you sure you want to discard this clip? The video file will be deleted to save disk space.')) {
    return;
  }

  const btnDiscard = document.getElementById('btn-discard');
  btnDiscard.disabled = true;
  btnDiscard.innerHTML = '<span>🗑</span> Discarding...';

  try {
    const res = await fetch('/api/discard', { method: 'POST' });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || 'Discard failed');

    showToast('Clip discarded and local storage cleaned.', 'success');

    // Reset UI
    document.getElementById('review-metadata-box').style.display = 'none';
    document.getElementById('action-buttons-grid').style.display = 'none';
    document.getElementById('preview-video').style.display = 'none';
    document.getElementById('empty-preview').style.display = 'flex';
    document.getElementById('progress-container').style.display = 'none';
    btnDiscard.disabled = false;
    btnDiscard.innerHTML = '<span>🗑</span> Discard';

    loadHistory();
  } catch (err) {
    showToast(err.message, 'error');
    btnDiscard.disabled = false;
    btnDiscard.innerHTML = '<span>🗑</span> Discard';
  }
}

// Initial Boot
loadNetworkInfo();
loadHistory();

// Register Service Worker for Mobile PWA
if ('serviceWorker' in navigator) {
  window.addEventListener('load', () => {
    navigator.serviceWorker.register('/sw.js').catch((err) => {
      console.log('ServiceWorker registration note:', err);
    });
  });
}

// Handle PWA Mobile Installation Prompt
let deferredPrompt;
const installBtn = document.getElementById('btn-install-app');

window.addEventListener('beforeinstallprompt', (e) => {
  e.preventDefault();
  deferredPrompt = e;
  if (installBtn) {
    installBtn.style.display = 'inline-flex';
  }
});

if (installBtn) {
  installBtn.addEventListener('click', async () => {
    if (!deferredPrompt) return;
    deferredPrompt.prompt();
    const { outcome } = await deferredPrompt.userChoice;
    if (outcome === 'accepted') {
      installBtn.style.display = 'none';
      showToast('🎉 Shorts Studio installed on your home screen!', 'success');
    }
    deferredPrompt = null;
  });
}

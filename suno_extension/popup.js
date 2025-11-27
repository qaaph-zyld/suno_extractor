// Popup script for Suno Extractor extension

let extractedSongs = [];
let isExtracting = false;

// Initialize popup
document.addEventListener('DOMContentLoaded', async () => {
  await checkCurrentTab();
  loadStoredSongs();
  
  document.getElementById('extract-btn').addEventListener('click', startExtraction);
  document.getElementById('download-btn').addEventListener('click', downloadJSON);
  document.getElementById('send-to-app').addEventListener('click', sendToApp);
});

// Check if we're on Suno
async function checkCurrentTab() {
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  
  if (tab.url && tab.url.includes('suno.com')) {
    document.getElementById('connection-status').textContent = 'Connected';
    document.getElementById('connection-status').className = 'status-value connected';
    document.getElementById('extract-btn').disabled = false;
    
    // Determine page type
    const url = tab.url.toLowerCase();
    let pageType = 'Home';
    if (url.includes('/me') && url.includes('liked')) pageType = 'Liked Songs';
    else if (url.includes('/me')) pageType = 'My Library';
    else if (url.includes('/song/')) pageType = 'Song Page';
    else if (url.includes('/playlist/')) pageType = 'Playlist';
    
    document.getElementById('page-type').textContent = pageType;
    
    // Get song count from page
    const results = await chrome.scripting.executeScript({
      target: { tabId: tab.id },
      func: countSongsOnPage
    });
    
    if (results && results[0]) {
      document.getElementById('song-count').textContent = results[0].result || 0;
    }
  } else {
    document.getElementById('connection-status').textContent = 'Not on Suno';
    document.getElementById('page-type').textContent = '-';
  }
}

// Count songs on current page
function countSongsOnPage() {
  const songLinks = document.querySelectorAll('a[href*="/song/"]');
  const uniqueUrls = new Set();
  songLinks.forEach(link => uniqueUrls.add(link.href));
  return uniqueUrls.size;
}

// Start extraction process
async function startExtraction() {
  if (isExtracting) return;
  
  isExtracting = true;
  const extractBtn = document.getElementById('extract-btn');
  const progress = document.getElementById('progress');
  
  extractBtn.disabled = true;
  extractBtn.textContent = 'Extracting...';
  progress.classList.add('active');
  
  try {
    const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
    
    // Execute extraction script
    const results = await chrome.scripting.executeScript({
      target: { tabId: tab.id },
      func: extractSongsFromPage
    });
    
    if (results && results[0] && results[0].result) {
      extractedSongs = results[0].result;
      
      // Store in extension storage
      await chrome.storage.local.set({ 
        extractedSongs,
        extractedAt: new Date().toISOString()
      });
      
      // Update UI
      document.getElementById('song-count').textContent = extractedSongs.length;
      document.getElementById('progress-fill').style.width = '100%';
      document.getElementById('progress-text').textContent = 
        `Extracted ${extractedSongs.length} songs`;
      
      // Enable buttons
      document.getElementById('download-btn').disabled = false;
      document.getElementById('send-to-app').disabled = false;
      
      // Show song list
      displaySongList();
    }
  } catch (error) {
    console.error('Extraction failed:', error);
    document.getElementById('progress-text').textContent = 'Extraction failed';
  }
  
  isExtracting = false;
  extractBtn.disabled = false;
  extractBtn.textContent = 'Extract Songs';
}

// Extraction function to run in page context
function extractSongsFromPage() {
  const songs = [];
  const songElements = document.querySelectorAll('a[href*="/song/"]');
  const processedUrls = new Set();
  
  songElements.forEach(element => {
    const href = element.href;
    if (processedUrls.has(href)) return;
    processedUrls.add(href);
    
    // Extract song ID
    const match = href.match(/\/song\/([a-f0-9-]{36})/);
    if (!match) return;
    
    const songId = match[1];
    
    // Find parent container
    let container = element.closest('[class*="song"], [class*="card"], [class*="item"]') || element.parentElement;
    
    // Extract data
    const song = {
      id: songId,
      url: href,
      title: '',
      artist: '',
      duration: '',
      image_url: '',
      extracted_at: new Date().toISOString()
    };
    
    // Title - look for heading or specific class
    const titleEl = container.querySelector('h1, h2, h3, h4, [class*="title"], [class*="name"]');
    if (titleEl) song.title = titleEl.textContent.trim();
    if (!song.title) song.title = element.textContent.trim().split('\n')[0];
    
    // Artist
    const artistEl = container.querySelector('[class*="artist"], [class*="creator"], a[href*="/@"]');
    if (artistEl) song.artist = artistEl.textContent.trim();
    
    // Duration
    const durationEl = container.querySelector('[class*="duration"], time');
    if (durationEl) song.duration = durationEl.textContent.trim();
    
    // Image
    const imgEl = container.querySelector('img');
    if (imgEl && imgEl.src) song.image_url = imgEl.src;
    
    // Only add if we have at least title or ID
    if (song.title || song.id) {
      songs.push(song);
    }
  });
  
  return songs;
}

// Load stored songs
async function loadStoredSongs() {
  const data = await chrome.storage.local.get(['extractedSongs', 'extractedAt']);
  if (data.extractedSongs && data.extractedSongs.length > 0) {
    extractedSongs = data.extractedSongs;
    document.getElementById('download-btn').disabled = false;
    document.getElementById('send-to-app').disabled = false;
    document.getElementById('song-count').textContent = extractedSongs.length;
    displaySongList();
  }
}

// Display extracted songs
function displaySongList() {
  const container = document.getElementById('songs-list');
  container.innerHTML = '';
  container.style.display = 'block';
  
  extractedSongs.slice(0, 20).forEach(song => {
    const item = document.createElement('div');
    item.className = 'song-item';
    item.innerHTML = `
      <img src="${song.image_url || ''}" class="song-cover" onerror="this.style.display='none'">
      <div class="song-info">
        <div class="song-title">${song.title || song.id}</div>
        <div class="song-duration">${song.duration || ''}</div>
      </div>
    `;
    container.appendChild(item);
  });
  
  if (extractedSongs.length > 20) {
    const more = document.createElement('div');
    more.className = 'song-item';
    more.innerHTML = `<div class="song-info"><div class="song-title">... and ${extractedSongs.length - 20} more</div></div>`;
    container.appendChild(more);
  }
}

// Download as JSON
function downloadJSON() {
  const data = {
    metadata: {
      extracted_at: new Date().toISOString(),
      total_songs: extractedSongs.length,
      source: 'Suno Extractor Extension'
    },
    songs: extractedSongs
  };
  
  const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
  const url = URL.createObjectURL(blob);
  
  const a = document.createElement('a');
  a.href = url;
  a.download = `suno_songs_${new Date().toISOString().slice(0,10)}.json`;
  a.click();
  
  URL.revokeObjectURL(url);
}

// Send to desktop app (via localhost API)
async function sendToApp() {
  try {
    const response = await fetch('http://localhost:5000/api/import-extension', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ songs: extractedSongs })
    });
    
    if (response.ok) {
      alert('Songs sent to Suno Extractor Pro!');
    } else {
      alert('Failed to connect. Make sure the desktop app is running.');
    }
  } catch (error) {
    alert('Could not connect to desktop app. Start it with: python suno_web.py');
  }
}

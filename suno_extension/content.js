// Content script for Suno Extractor
// Runs on suno.com pages

console.log('Suno Extractor: Content script loaded');

// Add extraction overlay button
function addExtractButton() {
  if (document.getElementById('suno-extractor-btn')) return;
  
  const btn = document.createElement('button');
  btn.id = 'suno-extractor-btn';
  btn.innerHTML = '🎵 Extract';
  btn.title = 'Extract songs with Suno Extractor';
  
  btn.style.cssText = `
    position: fixed;
    bottom: 20px;
    right: 20px;
    z-index: 99999;
    background: linear-gradient(135deg, #a855f7, #6366f1);
    color: white;
    border: none;
    padding: 12px 20px;
    border-radius: 25px;
    font-size: 14px;
    font-weight: 600;
    cursor: pointer;
    box-shadow: 0 4px 15px rgba(168, 85, 247, 0.4);
    transition: all 0.3s ease;
  `;
  
  btn.addEventListener('mouseenter', () => {
    btn.style.transform = 'scale(1.05)';
    btn.style.boxShadow = '0 6px 20px rgba(168, 85, 247, 0.5)';
  });
  
  btn.addEventListener('mouseleave', () => {
    btn.style.transform = 'scale(1)';
    btn.style.boxShadow = '0 4px 15px rgba(168, 85, 247, 0.4)';
  });
  
  btn.addEventListener('click', () => {
    // Trigger extraction via message to background
    chrome.runtime.sendMessage({ action: 'quickExtract' });
  });
  
  document.body.appendChild(btn);
}

// Monitor for navigation changes (SPA)
let lastUrl = location.href;
new MutationObserver(() => {
  if (location.href !== lastUrl) {
    lastUrl = location.href;
    console.log('Suno Extractor: Page changed to', lastUrl);
    setTimeout(addExtractButton, 1000);
  }
}).observe(document, { subtree: true, childList: true });

// Initialize
if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', () => setTimeout(addExtractButton, 1000));
} else {
  setTimeout(addExtractButton, 1000);
}

// Listen for messages from popup/background
chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
  if (request.action === 'getSongs') {
    const songs = extractAllSongs();
    sendResponse({ songs });
  }
  return true;
});

// Extract all songs from current page
function extractAllSongs() {
  const songs = [];
  const songLinks = document.querySelectorAll('a[href*="/song/"]');
  const processedIds = new Set();
  
  songLinks.forEach(link => {
    const match = link.href.match(/\/song\/([a-f0-9-]{36})/);
    if (!match || processedIds.has(match[1])) return;
    
    const songId = match[1];
    processedIds.add(songId);
    
    const container = link.closest('[class*="song"], [class*="card"], [class*="item"]') || link.parentElement;
    
    const song = {
      id: songId,
      url: link.href,
      title: '',
      artist: '',
      duration: '',
      image_url: ''
    };
    
    // Extract metadata from container
    const title = container.querySelector('h1, h2, h3, h4, [class*="title"]');
    if (title) song.title = title.textContent.trim();
    
    const artist = container.querySelector('[class*="artist"], [class*="creator"], a[href*="/@"]');
    if (artist) song.artist = artist.textContent.trim();
    
    const duration = container.querySelector('[class*="duration"], time');
    if (duration) song.duration = duration.textContent.trim();
    
    const img = container.querySelector('img');
    if (img) song.image_url = img.src;
    
    songs.push(song);
  });
  
  return songs;
}

// Expose for popup
window.sunoExtractor = {
  extractAllSongs,
  getSongCount: () => {
    const links = document.querySelectorAll('a[href*="/song/"]');
    const ids = new Set();
    links.forEach(l => {
      const m = l.href.match(/\/song\/([a-f0-9-]{36})/);
      if (m) ids.add(m[1]);
    });
    return ids.size;
  }
};

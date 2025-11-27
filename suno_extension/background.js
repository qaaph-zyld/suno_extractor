// Background service worker for Suno Extractor

console.log('Suno Extractor: Background script loaded');

// Handle messages from content script and popup
chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
  if (request.action === 'quickExtract') {
    handleQuickExtract(sender.tab);
  }
  return true;
});

// Quick extract from floating button
async function handleQuickExtract(tab) {
  try {
    const results = await chrome.scripting.executeScript({
      target: { tabId: tab.id },
      func: () => window.sunoExtractor ? window.sunoExtractor.extractAllSongs() : []
    });
    
    if (results && results[0] && results[0].result) {
      const songs = results[0].result;
      
      // Store songs
      await chrome.storage.local.set({
        extractedSongs: songs,
        extractedAt: new Date().toISOString()
      });
      
      // Show notification
      chrome.action.setBadgeText({ text: String(songs.length) });
      chrome.action.setBadgeBackgroundColor({ color: '#a855f7' });
      
      // Notify content script
      chrome.tabs.sendMessage(tab.id, {
        action: 'extractionComplete',
        count: songs.length
      });
    }
  } catch (error) {
    console.error('Quick extract failed:', error);
  }
}

// Clear badge when popup opens
chrome.action.onClicked.addListener(() => {
  chrome.action.setBadgeText({ text: '' });
});

// Monitor tab updates
chrome.tabs.onUpdated.addListener((tabId, changeInfo, tab) => {
  if (changeInfo.status === 'complete' && tab.url && tab.url.includes('suno.com')) {
    // Tab is on Suno - could trigger auto-extraction here
    console.log('Suno page detected:', tab.url);
  }
});

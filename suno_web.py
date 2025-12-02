#!/usr/bin/env python3
"""
Suno Web Dashboard - Flask-based local web UI
Beautiful web interface for managing your Suno music library
"""

import os
import json
import logging
from pathlib import Path
from datetime import datetime
from functools import wraps

# Flask and extensions
try:
    from flask import (Flask, render_template_string, jsonify, request, 
                       send_file, redirect, url_for, Response)
    FLASK_AVAILABLE = True
except ImportError:
    FLASK_AVAILABLE = False
    print("Flask not available. Install with: pip install flask")

# Local imports
try:
    from suno_core import get_config, get_database, SunoDatabase
    from suno_downloader import SunoDownloader, PlaylistManager
    from suno_audio import AudioAnalyzer, AudioProcessor
except ImportError as e:
    print(f"Import warning: {e}")

logger = logging.getLogger(__name__)

# Flask app
app = Flask(__name__)
app.secret_key = os.urandom(24)

# HTML Templates (embedded for simplicity)
BASE_TEMPLATE = '''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{{ title }} - Suno Library</title>
    <link href="https://cdn.jsdelivr.net/npm/tailwindcss@2.2.19/dist/tailwind.min.css" rel="stylesheet">
    <link href="https://cdn.jsdelivr.net/npm/@fortawesome/fontawesome-free@6.0.0/css/all.min.css" rel="stylesheet">
    <style>
        body { background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%); min-height: 100vh; }
        .glass { background: rgba(255,255,255,0.05); backdrop-filter: blur(10px); border: 1px solid rgba(255,255,255,0.1); }
        .song-card:hover { transform: translateY(-2px); box-shadow: 0 10px 40px rgba(0,0,0,0.3); }
        .playing { animation: pulse 2s infinite; }
        @keyframes pulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.7; } }
        .progress-bar { transition: width 0.1s linear; }
        audio { width: 100%; }
        .star { cursor: pointer; transition: all 0.2s; }
        .star:hover, .star.active { color: #fbbf24; transform: scale(1.2); }
    </style>
</head>
<body class="text-gray-100">
    <!-- Navigation -->
    <nav class="glass sticky top-0 z-50 px-6 py-4">
        <div class="max-w-7xl mx-auto flex items-center justify-between">
            <a href="/" class="text-2xl font-bold text-purple-400">
                <i class="fas fa-music mr-2"></i>Suno Library
            </a>
            <div class="flex items-center space-x-6">
                <a href="/" class="hover:text-purple-400 transition"><i class="fas fa-home mr-1"></i> Home</a>
                <a href="/songs" class="hover:text-purple-400 transition"><i class="fas fa-list mr-1"></i> Songs</a>
                <a href="/playlists" class="hover:text-purple-400 transition"><i class="fas fa-folder mr-1"></i> Playlists</a>
                <a href="/stats" class="hover:text-purple-400 transition"><i class="fas fa-chart-bar mr-1"></i> Stats</a>
                <a href="/settings" class="hover:text-purple-400 transition"><i class="fas fa-cog mr-1"></i> Settings</a>
            </div>
        </div>
    </nav>
    
    <!-- Main Content -->
    <main class="max-w-7xl mx-auto px-6 py-8">
        {% block content %}{% endblock %}
    </main>
    
    <!-- Audio Player Bar -->
    <div id="player-bar" class="glass fixed bottom-0 left-0 right-0 px-6 py-4 hidden">
        <div class="max-w-7xl mx-auto flex items-center justify-between">
            <div class="flex items-center space-x-4">
                <img id="player-cover" src="" class="w-12 h-12 rounded object-cover" alt="">
                <div>
                    <div id="player-title" class="font-semibold"></div>
                    <div id="player-artist" class="text-sm text-gray-400"></div>
                </div>
            </div>
            <div class="flex-1 max-w-xl mx-8">
                <div class="flex items-center justify-center space-x-4 mb-2">
                    <button onclick="prevTrack()" class="hover:text-purple-400"><i class="fas fa-step-backward"></i></button>
                    <button onclick="togglePlay()" id="play-btn" class="w-10 h-10 rounded-full bg-purple-500 hover:bg-purple-600">
                        <i class="fas fa-play"></i>
                    </button>
                    <button onclick="nextTrack()" class="hover:text-purple-400"><i class="fas fa-step-forward"></i></button>
                </div>
                <div class="flex items-center space-x-2">
                    <span id="current-time" class="text-xs">0:00</span>
                    <div class="flex-1 h-1 bg-gray-700 rounded cursor-pointer" onclick="seek(event)">
                        <div id="progress" class="progress-bar h-full bg-purple-500 rounded" style="width: 0%"></div>
                    </div>
                    <span id="duration" class="text-xs">0:00</span>
                </div>
            </div>
            <div class="flex items-center space-x-4">
                <button onclick="toggleShuffle()" id="shuffle-btn" class="hover:text-purple-400"><i class="fas fa-random"></i></button>
                <button onclick="toggleRepeat()" id="repeat-btn" class="hover:text-purple-400"><i class="fas fa-redo"></i></button>
                <input type="range" id="volume" min="0" max="100" value="70" class="w-20" onchange="setVolume(this.value)">
            </div>
        </div>
    </div>
    
    <audio id="audio-player" style="display:none"></audio>
    
    <script>
        let audioPlayer = document.getElementById('audio-player');
        let currentPlaylist = [];
        let currentIndex = 0;
        let isPlaying = false;
        let isShuffle = false;
        let repeatMode = 0; // 0: off, 1: all, 2: one
        
        function playSong(song) {
            if (!song.local_audio_path) return;
            
            document.getElementById('player-bar').classList.remove('hidden');
            document.getElementById('player-title').textContent = song.title || 'Unknown';
            document.getElementById('player-artist').textContent = song.artist || 'Suno AI';
            
            if (song.local_cover_path) {
                document.getElementById('player-cover').src = '/cover/' + song.id;
            }
            
            audioPlayer.src = '/audio/' + song.id;
            audioPlayer.play();
            isPlaying = true;
            updatePlayButton();
        }
        
        function togglePlay() {
            if (isPlaying) {
                audioPlayer.pause();
            } else {
                audioPlayer.play();
            }
            isPlaying = !isPlaying;
            updatePlayButton();
        }
        
        function updatePlayButton() {
            const btn = document.getElementById('play-btn');
            btn.innerHTML = isPlaying ? '<i class="fas fa-pause"></i>' : '<i class="fas fa-play"></i>';
        }
        
        function formatTime(seconds) {
            const mins = Math.floor(seconds / 60);
            const secs = Math.floor(seconds % 60);
            return mins + ':' + secs.toString().padStart(2, '0');
        }
        
        audioPlayer.addEventListener('timeupdate', () => {
            const progress = (audioPlayer.currentTime / audioPlayer.duration) * 100;
            document.getElementById('progress').style.width = progress + '%';
            document.getElementById('current-time').textContent = formatTime(audioPlayer.currentTime);
        });
        
        audioPlayer.addEventListener('loadedmetadata', () => {
            document.getElementById('duration').textContent = formatTime(audioPlayer.duration);
        });
        
        audioPlayer.addEventListener('ended', () => {
            if (repeatMode === 2) {
                audioPlayer.currentTime = 0;
                audioPlayer.play();
            } else {
                nextTrack();
            }
        });
        
        function seek(event) {
            const bar = event.target.closest('div');
            const percent = event.offsetX / bar.offsetWidth;
            audioPlayer.currentTime = percent * audioPlayer.duration;
        }
        
        function setVolume(value) {
            audioPlayer.volume = value / 100;
        }
        
        function prevTrack() {
            if (currentIndex > 0) {
                currentIndex--;
                playSong(currentPlaylist[currentIndex]);
            }
        }
        
        function nextTrack() {
            if (isShuffle) {
                currentIndex = Math.floor(Math.random() * currentPlaylist.length);
            } else if (currentIndex < currentPlaylist.length - 1) {
                currentIndex++;
            } else if (repeatMode === 1) {
                currentIndex = 0;
            } else {
                return;
            }
            playSong(currentPlaylist[currentIndex]);
        }
        
        function toggleShuffle() {
            isShuffle = !isShuffle;
            document.getElementById('shuffle-btn').classList.toggle('text-purple-400', isShuffle);
        }
        
        function toggleRepeat() {
            repeatMode = (repeatMode + 1) % 3;
            const btn = document.getElementById('repeat-btn');
            btn.classList.toggle('text-purple-400', repeatMode > 0);
            if (repeatMode === 2) btn.innerHTML = '<i class="fas fa-redo-alt"></i>';
            else btn.innerHTML = '<i class="fas fa-redo"></i>';
        }
        
        function rateSong(songId, rating) {
            fetch('/api/rate/' + songId, {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({rating: rating})
            }).then(r => r.json()).then(data => {
                if (data.success) {
                    updateStars(songId, rating);
                }
            });
        }
        
        function updateStars(songId, rating) {
            const container = document.getElementById('stars-' + songId);
            if (!container) return;
            const stars = container.querySelectorAll('.star');
            stars.forEach((star, i) => {
                star.classList.toggle('active', i < rating);
            });
        }
    </script>
</body>
</html>
'''

HOME_TEMPLATE = '''
{% extends "base" %}
{% block content %}
<div class="mb-8">
    <h1 class="text-4xl font-bold mb-2">Welcome to Your Suno Library</h1>
    <p class="text-gray-400">Manage, play, and discover your AI-generated music collection</p>
</div>

<!-- Stats Cards -->
<div class="grid grid-cols-1 md:grid-cols-4 gap-6 mb-8">
    <div class="glass rounded-xl p-6">
        <div class="text-3xl font-bold text-purple-400">{{ stats.total_songs }}</div>
        <div class="text-gray-400">Total Songs</div>
    </div>
    <div class="glass rounded-xl p-6">
        <div class="text-3xl font-bold text-blue-400">{{ stats.total_duration_formatted }}</div>
        <div class="text-gray-400">Total Duration</div>
    </div>
    <div class="glass rounded-xl p-6">
        <div class="text-3xl font-bold text-green-400">{{ stats.downloaded_songs }}</div>
        <div class="text-gray-400">Downloaded</div>
    </div>
    <div class="glass rounded-xl p-6">
        <div class="text-3xl font-bold text-yellow-400">{{ stats.total_plays }}</div>
        <div class="text-gray-400">Total Plays</div>
    </div>
</div>

<!-- Recent Songs -->
<div class="glass rounded-xl p-6 mb-8">
    <h2 class="text-2xl font-bold mb-4"><i class="fas fa-clock mr-2"></i>Recent Songs</h2>
    <div class="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-4">
        {% for song in recent_songs %}
        <div class="song-card glass rounded-lg p-3 cursor-pointer transition" onclick='playSong({{ song | tojson }})'>
            <div class="aspect-square bg-gray-700 rounded mb-2 overflow-hidden">
                {% if song.local_cover_path %}
                <img src="/cover/{{ song.id }}" class="w-full h-full object-cover" alt="">
                {% else %}
                <div class="w-full h-full flex items-center justify-center text-4xl text-gray-500">
                    <i class="fas fa-music"></i>
                </div>
                {% endif %}
            </div>
            <div class="font-semibold truncate">{{ song.title or 'Unknown' }}</div>
            <div class="text-sm text-gray-400 truncate">{{ song.duration or '--:--' }}</div>
        </div>
        {% endfor %}
    </div>
</div>

<!-- Quick Actions -->
<div class="grid grid-cols-1 md:grid-cols-3 gap-6">
    <a href="/songs" class="glass rounded-xl p-6 hover:bg-purple-500/20 transition">
        <i class="fas fa-list text-3xl text-purple-400 mb-3"></i>
        <h3 class="text-xl font-bold mb-1">Browse Library</h3>
        <p class="text-gray-400">View all your songs</p>
    </a>
    <a href="/search" class="glass rounded-xl p-6 hover:bg-blue-500/20 transition">
        <i class="fas fa-search text-3xl text-blue-400 mb-3"></i>
        <h3 class="text-xl font-bold mb-1">Search</h3>
        <p class="text-gray-400">Find specific songs</p>
    </a>
    <a href="/stats" class="glass rounded-xl p-6 hover:bg-green-500/20 transition">
        <i class="fas fa-chart-pie text-3xl text-green-400 mb-3"></i>
        <h3 class="text-xl font-bold mb-1">Analytics</h3>
        <p class="text-gray-400">View detailed statistics</p>
    </a>
</div>
{% endblock %}
'''

SONGS_TEMPLATE = '''
{% extends "base" %}
{% block content %}
<div class="flex items-center justify-between mb-6">
    <h1 class="text-3xl font-bold">
        <i class="fas fa-music mr-2"></i>All Songs
        <span class="text-lg font-normal text-gray-400 ml-2">({{ total_songs }} total)</span>
    </h1>
    <div class="flex items-center space-x-4">
        <input type="text" id="search" placeholder="Search..." 
               class="glass rounded-lg px-4 py-2 bg-transparent border-none focus:ring-2 focus:ring-purple-500"
               onkeyup="filterSongs(this.value)">
        <select id="sort" class="glass rounded-lg px-4 py-2 bg-transparent" onchange="sortSongs(this.value)">
            <option value="title">Sort by Title</option>
            <option value="duration">Sort by Duration</option>
            <option value="bpm">Sort by BPM</option>
            <option value="rating">Sort by Rating</option>
        </select>
    </div>
</div>

<div class="glass rounded-xl overflow-hidden">
    <table class="w-full">
        <thead class="bg-white/5">
            <tr>
                <th class="px-4 py-3 text-left">#</th>
                <th class="px-4 py-3 text-left">Title</th>
                <th class="px-4 py-3 text-left">Duration</th>
                <th class="px-4 py-3 text-left">BPM</th>
                <th class="px-4 py-3 text-left">Key</th>
                <th class="px-4 py-3 text-left">Rating</th>
                <th class="px-4 py-3 text-left">Actions</th>
            </tr>
        </thead>
        <tbody id="songs-table">
            {% for song in songs %}
            <tr class="border-t border-white/5 hover:bg-white/5 transition song-row" data-song='{{ song | tojson }}'>
                <td class="px-4 py-3">{{ loop.index }}</td>
                <td class="px-4 py-3">
                    <div class="flex items-center space-x-3">
                        <div class="w-10 h-10 rounded bg-gray-700 overflow-hidden">
                            {% if song.local_cover_path %}
                            <img src="/cover/{{ song.id }}" class="w-full h-full object-cover">
                            {% endif %}
                        </div>
                        <div>
                            <div class="font-semibold">{{ song.title or 'Unknown' }}</div>
                            <div class="text-sm text-gray-400">{{ song.artist or 'Suno AI' }}</div>
                        </div>
                    </div>
                </td>
                <td class="px-4 py-3">{{ song.duration or '--:--' }}</td>
                <td class="px-4 py-3">{{ song.bpm|round|int if song.bpm else '-' }}</td>
                <td class="px-4 py-3">{{ song.musical_key or '-' }}</td>
                <td class="px-4 py-3">
                    <div id="stars-{{ song.id }}" class="flex space-x-1">
                        {% for i in range(1, 6) %}
                        <i class="star fas fa-star {{ 'active text-yellow-400' if song.rating and i <= song.rating else 'text-gray-600' }}"
                           onclick="rateSong('{{ song.id }}', {{ i }})"></i>
                        {% endfor %}
                    </div>
                </td>
                <td class="px-4 py-3">
                    <button onclick='playSong({{ song | tojson }})' class="hover:text-purple-400" title="Play">
                        <i class="fas fa-play"></i>
                    </button>
                    {% if song.local_audio_path %}
                    <a href="/download/{{ song.id }}" class="ml-2 hover:text-green-400" title="Download">
                        <i class="fas fa-download"></i>
                    </a>
                    {% endif %}
                </td>
            </tr>
            {% endfor %}
        </tbody>
    </table>
</div>

<!-- Pagination Controls -->
{% if total_pages > 1 %}
<div class="flex items-center justify-between mt-6">
    <div class="text-gray-400">
        Showing {{ (page - 1) * per_page + 1 }} - {{ [page * per_page, total_songs] | min }} of {{ total_songs }} songs
    </div>
    <div class="flex items-center space-x-2">
        {% if page > 1 %}
        <a href="?page=1&per_page={{ per_page }}" 
           class="glass px-3 py-2 rounded-lg hover:bg-white/10 transition" title="First">
            <i class="fas fa-angle-double-left"></i>
        </a>
        <a href="?page={{ page - 1 }}&per_page={{ per_page }}" 
           class="glass px-3 py-2 rounded-lg hover:bg-white/10 transition" title="Previous">
            <i class="fas fa-angle-left"></i>
        </a>
        {% endif %}
        
        <span class="px-4 py-2 bg-purple-600/30 rounded-lg">
            Page {{ page }} of {{ total_pages }}
        </span>
        
        {% if page < total_pages %}
        <a href="?page={{ page + 1 }}&per_page={{ per_page }}" 
           class="glass px-3 py-2 rounded-lg hover:bg-white/10 transition" title="Next">
            <i class="fas fa-angle-right"></i>
        </a>
        <a href="?page={{ total_pages }}&per_page={{ per_page }}" 
           class="glass px-3 py-2 rounded-lg hover:bg-white/10 transition" title="Last">
            <i class="fas fa-angle-double-right"></i>
        </a>
        {% endif %}
        
        <select onchange="window.location.href='?page=1&per_page='+this.value" 
                class="glass rounded-lg px-3 py-2 bg-transparent ml-4">
            <option value="25" {{ 'selected' if per_page == 25 }}>25 per page</option>
            <option value="50" {{ 'selected' if per_page == 50 }}>50 per page</option>
            <option value="100" {{ 'selected' if per_page == 100 }}>100 per page</option>
        </select>
    </div>
</div>
{% endif %}

<script>
    let allSongs = {{ songs | tojson }};
    currentPlaylist = allSongs;
    
    function filterSongs(query) {
        query = query.toLowerCase();
        document.querySelectorAll('.song-row').forEach(row => {
            const song = JSON.parse(row.dataset.song);
            const match = (song.title || '').toLowerCase().includes(query) ||
                          (song.artist || '').toLowerCase().includes(query) ||
                          (song.tags || []).join(' ').toLowerCase().includes(query);
            row.style.display = match ? '' : 'none';
        });
    }
</script>
{% endblock %}
'''

STATS_TEMPLATE = '''
{% extends "base" %}
{% block content %}
<h1 class="text-3xl font-bold mb-6"><i class="fas fa-chart-bar mr-2"></i>Library Statistics</h1>

<div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-8">
    <div class="glass rounded-xl p-6 text-center">
        <div class="text-5xl font-bold text-purple-400 mb-2">{{ stats.total_songs }}</div>
        <div class="text-gray-400">Total Songs</div>
    </div>
    <div class="glass rounded-xl p-6 text-center">
        <div class="text-5xl font-bold text-blue-400 mb-2">{{ stats.total_duration_formatted }}</div>
        <div class="text-gray-400">Total Duration</div>
    </div>
    <div class="glass rounded-xl p-6 text-center">
        <div class="text-5xl font-bold text-green-400 mb-2">{{ stats.downloaded_songs }}</div>
        <div class="text-gray-400">Downloaded</div>
    </div>
    <div class="glass rounded-xl p-6 text-center">
        <div class="text-5xl font-bold text-yellow-400 mb-2">{{ stats.average_rating }}</div>
        <div class="text-gray-400">Avg Rating</div>
    </div>
</div>

<div class="grid grid-cols-1 md:grid-cols-2 gap-6">
    <!-- Top Tags -->
    <div class="glass rounded-xl p-6">
        <h2 class="text-xl font-bold mb-4"><i class="fas fa-tags mr-2"></i>Top Tags</h2>
        {% for tag, count in stats.top_tags.items() %}
        <div class="flex items-center justify-between py-2 border-b border-white/10">
            <span class="px-3 py-1 bg-purple-500/20 rounded-full text-sm">{{ tag }}</span>
            <span class="text-gray-400">{{ count }} songs</span>
        </div>
        {% endfor %}
    </div>
    
    <!-- By Version -->
    <div class="glass rounded-xl p-6">
        <h2 class="text-xl font-bold mb-4"><i class="fas fa-code-branch mr-2"></i>By Suno Version</h2>
        {% for version, count in stats.by_version.items() %}
        <div class="flex items-center justify-between py-2 border-b border-white/10">
            <span>{{ version }}</span>
            <div class="flex items-center">
                <div class="w-32 h-2 bg-gray-700 rounded mr-3">
                    <div class="h-full bg-blue-500 rounded" style="width: {{ (count / stats.total_songs * 100)|round }}%"></div>
                </div>
                <span class="text-gray-400">{{ count }}</span>
            </div>
        </div>
        {% endfor %}
    </div>
</div>
{% endblock %}
'''

SETTINGS_TEMPLATE = '''
{% extends "base" %}
{% block content %}
<h1 class="text-3xl font-bold mb-6"><i class="fas fa-cog mr-2"></i>Settings</h1>

<div class="glass rounded-xl p-6 mb-6">
    <h2 class="text-xl font-bold mb-4">Library Management</h2>
    <div class="space-y-4">
        <div class="flex items-center justify-between py-3 border-b border-white/10">
            <div>
                <div class="font-semibold">Import from JSON</div>
                <div class="text-sm text-gray-400">Import songs from extraction file</div>
            </div>
            <form action="/api/import" method="POST" enctype="multipart/form-data" class="flex items-center space-x-2">
                <input type="file" name="file" accept=".json" class="text-sm">
                <button type="submit" class="px-4 py-2 bg-purple-500 rounded-lg hover:bg-purple-600 transition">Import</button>
            </form>
        </div>
        <div class="flex items-center justify-between py-3 border-b border-white/10">
            <div>
                <div class="font-semibold">Export to JSON</div>
                <div class="text-sm text-gray-400">Export your library to JSON file</div>
            </div>
            <a href="/api/export" class="px-4 py-2 bg-blue-500 rounded-lg hover:bg-blue-600 transition">Export</a>
        </div>
        <div class="flex items-center justify-between py-3 border-b border-white/10">
            <div>
                <div class="font-semibold">Export to Spotify CSV</div>
                <div class="text-sm text-gray-400">Export for Spotify import</div>
            </div>
            <a href="/api/export-spotify" class="px-4 py-2 bg-green-500 rounded-lg hover:bg-green-600 transition">Export CSV</a>
        </div>
        <div class="flex items-center justify-between py-3">
            <div>
                <div class="font-semibold">Backup Database</div>
                <div class="text-sm text-gray-400">Create a backup of your library</div>
            </div>
            <a href="/api/backup" class="px-4 py-2 bg-yellow-500 rounded-lg hover:bg-yellow-600 transition text-black">Backup</a>
        </div>
    </div>
</div>

<div class="glass rounded-xl p-6">
    <h2 class="text-xl font-bold mb-4">Audio Analysis</h2>
    <div class="space-y-4">
        <div class="flex items-center justify-between py-3 border-b border-white/10">
            <div>
                <div class="font-semibold">Analyze All Songs</div>
                <div class="text-sm text-gray-400">Detect BPM, key, and energy for all downloaded songs</div>
            </div>
            <button onclick="analyzeAll()" class="px-4 py-2 bg-purple-500 rounded-lg hover:bg-purple-600 transition">
                <i class="fas fa-chart-line mr-1"></i> Analyze
            </button>
        </div>
        <div class="flex items-center justify-between py-3">
            <div>
                <div class="font-semibold">Find Duplicates</div>
                <div class="text-sm text-gray-400">Detect potential duplicate songs</div>
            </div>
            <a href="/duplicates" class="px-4 py-2 bg-red-500 rounded-lg hover:bg-red-600 transition">
                <i class="fas fa-copy mr-1"></i> Find
            </a>
        </div>
    </div>
</div>

<script>
function analyzeAll() {
    if (!confirm('This will analyze all downloaded songs. Continue?')) return;
    fetch('/api/analyze-all', {method: 'POST'})
        .then(r => r.json())
        .then(data => alert('Analyzed ' + data.count + ' songs'));
}
</script>
{% endblock %}
'''


# Template registry
TEMPLATES = {
    'base': BASE_TEMPLATE,
    'home': HOME_TEMPLATE,
    'songs': SONGS_TEMPLATE,
    'stats': STATS_TEMPLATE,
    'settings': SETTINGS_TEMPLATE,
}


def render(template_name, **kwargs):
    """Render template with base"""
    template = TEMPLATES.get(template_name, '')
    # Simple template inheritance
    if '{% extends "base" %}' in template:
        base = TEMPLATES['base']
        content = template.split('{% block content %}')[1].split('{% endblock %}')[0]
        template = base.replace('{% block content %}{% endblock %}', content)
    return render_template_string(template, **kwargs)


# Routes
@app.route('/')
def home():
    """Render home page with stats and recent songs."""
    db = get_database()
    stats = db.get_statistics()
    recent = db.get_recently_played(12) or db.get_all_songs(12)
    return render('home', title='Home', stats=stats, recent_songs=recent)


@app.route('/songs')
def songs():
    """Render paginated songs list with filtering and sorting."""
    db = get_database()
    
    # Get pagination parameters
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 50, type=int)
    per_page = min(per_page, 100)  # Cap at 100
    
    # Get all songs for now (can optimize with DB-level pagination later)
    all_songs = db.get_all_songs()
    total_songs = len(all_songs)
    total_pages = max(1, (total_songs + per_page - 1) // per_page)
    
    # Ensure page is in valid range
    page = max(1, min(page, total_pages))
    
    # Slice for current page
    start_idx = (page - 1) * per_page
    end_idx = start_idx + per_page
    page_songs = all_songs[start_idx:end_idx]
    
    # Add ratings
    for song in page_songs:
        song['rating'] = db.get_rating(song['id'])
    
    return render('songs', title='Songs', songs=page_songs,
                  page=page, total_pages=total_pages, per_page=per_page, total_songs=total_songs)


@app.route('/stats')
def stats():
    """Render library statistics page."""
    db = get_database()
    stats = db.get_statistics()
    return render('stats', title='Statistics', stats=stats)


@app.route('/settings')
def settings():
    """Render settings page."""
    return render('settings', title='Settings')


@app.route('/search')
def search():
    """Search songs by query and render results."""
    query = request.args.get('q', '')
    db = get_database()
    
    if query:
        results = db.search_songs(query)
    else:
        results = []
    
    return render('songs', title=f'Search: {query}', songs=results)


# API Routes
@app.route('/api/songs')
def api_songs():
    """API: Get all songs as JSON."""
    db = get_database()
    songs = db.get_all_songs()
    return jsonify(songs)


@app.route('/api/song/<song_id>')
def api_song(song_id):
    """API: Get single song by ID."""
    db = get_database()
    song = db.get_song(song_id)
    if song:
        return jsonify(song)
    return jsonify({'error': 'Not found'}), 404


@app.route('/api/rate/<song_id>', methods=['POST'])
def api_rate(song_id):
    """API: Rate a song (1-5 stars)."""
    data = request.get_json()
    rating = data.get('rating', 0)
    
    db = get_database()
    success = db.rate_song(song_id, rating)
    
    return jsonify({'success': success})


@app.route('/api/play/<song_id>', methods=['POST'])
def api_play(song_id):
    """API: Record a song play."""
    db = get_database()
    db.record_play(song_id)
    return jsonify({'success': True})


@app.route('/api/stats')
def api_stats():
    """API: Get library statistics."""
    db = get_database()
    return jsonify(db.get_statistics())


@app.route('/api/export')
def api_export():
    """API: Export library to JSON file."""
    db = get_database()
    output_path = "export_library.json"
    db.export_to_json(output_path)
    return send_file(output_path, as_attachment=True)


@app.route('/api/export-spotify')
def api_export_spotify():
    """Export to Spotify-compatible CSV"""
    db = get_database()
    songs = db.get_all_songs()
    
    import csv
    import io
    
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['Track Name', 'Artist Name', 'Album Name', 'Duration (ms)'])
    
    for song in songs:
        duration_ms = song.get('duration_seconds', 0) * 1000
        writer.writerow([
            song.get('title', 'Unknown'),
            song.get('artist', 'Suno AI'),
            'Suno AI Creations',
            duration_ms
        ])
    
    output.seek(0)
    return Response(
        output.getvalue(),
        mimetype='text/csv',
        headers={'Content-Disposition': 'attachment; filename=suno_spotify_export.csv'}
    )


@app.route('/api/backup')
def api_backup():
    """API: Create database backup."""
    db = get_database()
    backup_path = db.backup()
    return jsonify({'success': True, 'path': str(backup_path)})


@app.route('/api/import', methods=['POST'])
def api_import():
    """API: Import songs from uploaded JSON file."""
    if 'file' not in request.files:
        return jsonify({'error': 'No file provided'}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400
    
    # Save temporarily
    import tempfile
    with tempfile.NamedTemporaryFile(delete=False, suffix='.json') as f:
        file.save(f.name)
        temp_path = f.name
    
    db = get_database()
    count = db.import_from_json(temp_path)
    
    os.unlink(temp_path)
    
    return redirect(url_for('songs'))


@app.route('/api/analyze-all', methods=['POST'])
def api_analyze_all():
    try:
        analyzer = AudioAnalyzer()
        config = get_config()
        audio_dir = config.get('download', 'output_dir', default='suno_downloads')
        
        results = analyzer.batch_analyze(audio_dir)
        
        # Update database
        db = get_database()
        for result in results:
            if result.get('analyzed'):
                # Extract song ID from filename
                filename = Path(result['filepath']).stem
                songs = db.search_songs(filename, ['title'])
                if songs:
                    db.update_audio_info(
                        songs[0]['id'],
                        bpm=result.get('bpm'),
                        key=result.get('key')
                    )
        
        return jsonify({'success': True, 'count': len(results)})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/audio/<song_id>')
def serve_audio(song_id):
    db = get_database()
    song = db.get_song(song_id)
    
    if song and song.get('local_audio_path'):
        return send_file(song['local_audio_path'])
    
    return '', 404


@app.route('/cover/<song_id>')
def serve_cover(song_id):
    db = get_database()
    song = db.get_song(song_id)
    
    if song and song.get('local_cover_path'):
        return send_file(song['local_cover_path'])
    
    # Return placeholder
    return '', 404


@app.route('/download/<song_id>')
def download_song(song_id):
    db = get_database()
    song = db.get_song(song_id)
    
    if song and song.get('local_audio_path'):
        return send_file(
            song['local_audio_path'],
            as_attachment=True,
            download_name=f"{song.get('title', 'song')}.mp3"
        )
    
    return '', 404


def run_server(host='127.0.0.1', port=5000, debug=False):
    """Start the web server"""
    if not FLASK_AVAILABLE:
        print("Flask not available. Install with: pip install flask")
        return
    
    print(f"\n🎵 Suno Web Dashboard starting...")
    print(f"   Open http://{host}:{port} in your browser\n")
    
    app.run(host=host, port=port, debug=debug)


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="Suno Web Dashboard")
    parser.add_argument('--host', default='127.0.0.1', help='Host to bind')
    parser.add_argument('--port', type=int, default=5000, help='Port to bind')
    parser.add_argument('--debug', action='store_true', help='Debug mode')
    
    args = parser.parse_args()
    
    run_server(args.host, args.port, args.debug)


if __name__ == '__main__':
    main()

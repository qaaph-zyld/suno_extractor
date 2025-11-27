#!/usr/bin/env python3
"""
Suno Discord Bot - Play Suno songs in Discord voice channels
Integrates with Suno Extractor Pro library
"""

import os
import json
import asyncio
import logging
import random
from pathlib import Path
from typing import Optional, List, Dict

logger = logging.getLogger(__name__)

# Discord.py imports
try:
    import discord
    from discord import app_commands
    from discord.ext import commands
    DISCORD_AVAILABLE = True
except ImportError:
    DISCORD_AVAILABLE = False
    logger.warning("discord.py not installed. Run: pip install discord.py[voice]")

# Local imports
try:
    from suno_core import get_database, get_config
except ImportError:
    pass


class SunoBot(commands.Bot):
    """Discord bot for playing Suno songs"""
    
    def __init__(self, audio_dir: str = "suno_downloads"):
        intents = discord.Intents.default()
        intents.message_content = True
        intents.voice_states = True
        
        super().__init__(
            command_prefix="!suno ",
            intents=intents,
            description="Play your Suno AI music collection"
        )
        
        self.audio_dir = Path(audio_dir)
        self.current_song = None
        self.queue: List[Dict] = []
        self.is_playing = False
        self.voice_client: Optional[discord.VoiceClient] = None
        self.db = None
        
        try:
            self.db = get_database()
        except Exception:
            pass
    
    async def setup_hook(self):
        """Setup slash commands"""
        await self.tree.sync()
        logger.info("Slash commands synced")
    
    async def on_ready(self):
        """Called when bot is ready"""
        logger.info(f"Bot connected as {self.user}")
        await self.change_presence(
            activity=discord.Activity(
                type=discord.ActivityType.listening,
                name="Suno AI music"
            )
        )
    
    def get_songs(self) -> List[Dict]:
        """Get available songs"""
        if self.db:
            return self.db.get_all_songs()
        
        # Fallback to directory scan
        songs = []
        for ext in ['*.mp3', '*.m4a', '*.wav']:
            for f in self.audio_dir.glob(ext):
                songs.append({
                    'id': f.stem,
                    'title': f.stem,
                    'local_audio_path': str(f)
                })
        return songs
    
    def search_songs(self, query: str) -> List[Dict]:
        """Search songs by query"""
        if self.db:
            return self.db.search_songs(query)
        
        query = query.lower()
        return [s for s in self.get_songs() if query in s.get('title', '').lower()]
    
    async def join_voice(self, ctx) -> bool:
        """Join user's voice channel"""
        if not ctx.author.voice:
            await ctx.send("❌ You need to be in a voice channel!")
            return False
        
        channel = ctx.author.voice.channel
        
        if self.voice_client and self.voice_client.is_connected():
            await self.voice_client.move_to(channel)
        else:
            self.voice_client = await channel.connect()
        
        return True
    
    async def play_song(self, ctx, song: Dict):
        """Play a song"""
        audio_path = song.get('local_audio_path')
        if not audio_path or not Path(audio_path).exists():
            await ctx.send(f"❌ Audio file not found for: {song.get('title')}")
            return
        
        if self.voice_client and self.voice_client.is_playing():
            self.voice_client.stop()
        
        # Create audio source
        source = discord.FFmpegPCMAudio(audio_path)
        
        self.current_song = song
        self.is_playing = True
        
        def after_playing(error):
            if error:
                logger.error(f"Playback error: {error}")
            self.is_playing = False
            
            # Play next in queue
            if self.queue:
                next_song = self.queue.pop(0)
                asyncio.run_coroutine_threadsafe(
                    self.play_song(ctx, next_song),
                    self.loop
                )
        
        self.voice_client.play(source, after=after_playing)
        
        # Create embed
        embed = discord.Embed(
            title="🎵 Now Playing",
            description=song.get('title', 'Unknown'),
            color=discord.Color.purple()
        )
        embed.add_field(name="Duration", value=song.get('duration', '--:--'))
        
        if song.get('bpm'):
            embed.add_field(name="BPM", value=str(int(song['bpm'])))
        if song.get('musical_key'):
            embed.add_field(name="Key", value=song['musical_key'])
        
        await ctx.send(embed=embed)
        
        # Record play in database
        if self.db and song.get('id'):
            self.db.record_play(song['id'])


# Create bot instance
bot = SunoBot() if DISCORD_AVAILABLE else None


# Commands
if DISCORD_AVAILABLE:
    
    @bot.command(name='play', aliases=['p'])
    async def play_command(ctx, *, query: str):
        """Play a song by name or add to queue"""
        if not await bot.join_voice(ctx):
            return
        
        songs = bot.search_songs(query)
        if not songs:
            await ctx.send(f"❌ No songs found matching: {query}")
            return
        
        song = songs[0]
        
        if bot.is_playing:
            bot.queue.append(song)
            await ctx.send(f"📋 Added to queue: **{song.get('title')}**")
        else:
            await bot.play_song(ctx, song)
    
    @bot.command(name='pause')
    async def pause_command(ctx):
        """Pause playback"""
        if bot.voice_client and bot.voice_client.is_playing():
            bot.voice_client.pause()
            await ctx.send("⏸️ Paused")
    
    @bot.command(name='resume')
    async def resume_command(ctx):
        """Resume playback"""
        if bot.voice_client and bot.voice_client.is_paused():
            bot.voice_client.resume()
            await ctx.send("▶️ Resumed")
    
    @bot.command(name='skip', aliases=['next'])
    async def skip_command(ctx):
        """Skip current song"""
        if bot.voice_client and bot.voice_client.is_playing():
            bot.voice_client.stop()
            await ctx.send("⏭️ Skipped")
    
    @bot.command(name='stop')
    async def stop_command(ctx):
        """Stop playback and clear queue"""
        if bot.voice_client:
            bot.queue.clear()
            bot.voice_client.stop()
            await ctx.send("⏹️ Stopped")
    
    @bot.command(name='queue', aliases=['q'])
    async def queue_command(ctx):
        """Show current queue"""
        if not bot.queue:
            await ctx.send("📋 Queue is empty")
            return
        
        embed = discord.Embed(title="📋 Queue", color=discord.Color.blue())
        
        for i, song in enumerate(bot.queue[:10], 1):
            embed.add_field(
                name=f"{i}. {song.get('title', 'Unknown')}",
                value=song.get('duration', '--:--'),
                inline=False
            )
        
        if len(bot.queue) > 10:
            embed.set_footer(text=f"... and {len(bot.queue) - 10} more")
        
        await ctx.send(embed=embed)
    
    @bot.command(name='shuffle')
    async def shuffle_command(ctx):
        """Shuffle the queue"""
        if bot.queue:
            random.shuffle(bot.queue)
            await ctx.send("🔀 Queue shuffled")
        else:
            await ctx.send("📋 Queue is empty")
    
    @bot.command(name='nowplaying', aliases=['np'])
    async def nowplaying_command(ctx):
        """Show current song"""
        if bot.current_song:
            embed = discord.Embed(
                title="🎵 Now Playing",
                description=bot.current_song.get('title', 'Unknown'),
                color=discord.Color.purple()
            )
            await ctx.send(embed=embed)
        else:
            await ctx.send("Nothing playing")
    
    @bot.command(name='list')
    async def list_command(ctx, limit: int = 10):
        """List available songs"""
        songs = bot.get_songs()[:limit]
        
        embed = discord.Embed(
            title="🎵 Available Songs",
            description=f"Showing {len(songs)} songs",
            color=discord.Color.green()
        )
        
        for song in songs:
            embed.add_field(
                name=song.get('title', 'Unknown')[:50],
                value=song.get('duration', '--:--'),
                inline=True
            )
        
        await ctx.send(embed=embed)
    
    @bot.command(name='random', aliases=['r'])
    async def random_command(ctx):
        """Play a random song"""
        if not await bot.join_voice(ctx):
            return
        
        songs = bot.get_songs()
        if not songs:
            await ctx.send("❌ No songs available")
            return
        
        song = random.choice(songs)
        await bot.play_song(ctx, song)
    
    @bot.command(name='leave', aliases=['disconnect', 'dc'])
    async def leave_command(ctx):
        """Leave voice channel"""
        if bot.voice_client:
            await bot.voice_client.disconnect()
            bot.voice_client = None
            await ctx.send("👋 Disconnected")
    
    @bot.command(name='stats')
    async def stats_command(ctx):
        """Show library statistics"""
        if bot.db:
            stats = bot.db.get_statistics()
            
            embed = discord.Embed(
                title="📊 Library Statistics",
                color=discord.Color.gold()
            )
            embed.add_field(name="Total Songs", value=stats.get('total_songs', 0))
            embed.add_field(name="Total Duration", value=stats.get('total_duration_formatted', '--'))
            embed.add_field(name="Downloaded", value=stats.get('downloaded_songs', 0))
            embed.add_field(name="Total Plays", value=stats.get('total_plays', 0))
            
            await ctx.send(embed=embed)
        else:
            songs = bot.get_songs()
            await ctx.send(f"📊 {len(songs)} songs available")


def run_bot(token: str = None):
    """Run the Discord bot"""
    if not DISCORD_AVAILABLE:
        print("Discord.py not installed. Run: pip install discord.py[voice]")
        return
    
    if not token:
        token = os.environ.get('DISCORD_BOT_TOKEN')
    
    if not token:
        print("Discord bot token required.")
        print("Set DISCORD_BOT_TOKEN environment variable or pass token to run_bot()")
        return
    
    bot.run(token)


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="Suno Discord Bot")
    parser.add_argument('--token', help='Discord bot token')
    parser.add_argument('--audio-dir', default='suno_downloads', help='Audio directory')
    
    args = parser.parse_args()
    
    if args.audio_dir:
        bot.audio_dir = Path(args.audio_dir)
    
    run_bot(args.token)


if __name__ == "__main__":
    main()

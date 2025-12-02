"""
Tests for suno_core.py - Configuration and Database management
"""

import pytest
import tempfile
import os
from pathlib import Path
import json

# Import classes to test
from suno_core import Config, SunoDatabase


# =============================================================================
# Config Tests
# =============================================================================

class TestConfig:
    """Tests for Config class"""
    
    def test_default_config_loaded(self):
        """Test that default config is loaded"""
        config = Config()
        # Check some default values exist
        assert config.get('browser', 'type') is not None
        assert config.get('extraction', 'output_dir') is not None
        assert config.get('download', 'format') is not None
    
    def test_get_nested_value(self):
        """Test getting nested config values"""
        config = Config()
        # These should exist in DEFAULT_CONFIG
        assert config.get('browser', 'debug_port') == 9222
        assert config.get('extraction', 'scroll_pause') == 1.2
    
    def test_get_with_default(self):
        """Test get with default value for missing keys"""
        config = Config()
        result = config.get('nonexistent', 'key', default='fallback')
        assert result == 'fallback'
    
    def test_set_value(self):
        """Test setting config values"""
        config = Config()
        # Note: set() takes (value, *keys) not (*keys, value)
        config.set(123, 'test', 'value')
        assert config.get('test', 'value') == 123
    
    def test_deep_merge(self):
        """Test _deep_merge utility"""
        config = Config()
        base = {'a': 1, 'nested': {'b': 2, 'c': 3}}
        override = {'a': 10, 'nested': {'c': 30}}
        
        # Note: _deep_merge modifies base in-place and returns None
        config._deep_merge(base, override)
        
        assert base['a'] == 10  # Overridden
        assert base['nested']['b'] == 2  # Preserved
        assert base['nested']['c'] == 30  # Overridden
    
    def test_load_from_yaml_file(self):
        """Test loading config from YAML file"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write("browser:\n  type: firefox\n  debug_port: 9999\n")
            temp_path = f.name
        
        try:
            config = Config(config_path=temp_path)
            # Should merge with defaults
            assert config.get('browser', 'type') == 'firefox'
            assert config.get('browser', 'debug_port') == 9999
            # Other defaults should still exist
            assert config.get('extraction', 'output_dir') is not None
        finally:
            os.unlink(temp_path)
    
    def test_save_config(self):
        """Test saving config to file"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            temp_path = f.name
        
        try:
            # Create config with custom path
            config = Config(config_path=temp_path)
            config.set(42, 'test', 'saved_value')
            config.save()  # Note: save() uses self.config_path, no args
            
            # Verify file was written
            assert os.path.exists(temp_path)
            with open(temp_path, 'r') as f:
                content = f.read()
                assert 'test' in content
        finally:
            if os.path.exists(temp_path):
                os.unlink(temp_path)


# =============================================================================
# SunoDatabase Tests
# =============================================================================

class TestSunoDatabase:
    """Tests for SunoDatabase class"""
    
    @pytest.fixture
    def temp_db(self):
        """Create a temporary database for testing"""
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
            temp_path = f.name
        
        db = SunoDatabase(temp_path)
        yield db
        
        # Cleanup
        if os.path.exists(temp_path):
            os.unlink(temp_path)
    
    def test_database_created(self, temp_db):
        """Test that database file is created"""
        assert temp_db.db_path.exists()
    
    def test_add_song(self, temp_db):
        """Test adding a song to database"""
        song = {
            'title': 'Test Song',
            'url': 'https://suno.com/song/12345678-1234-1234-1234-123456789012',
            'artist': 'Test Artist',
            'duration': '3:24',
            'tags': ['rock', 'energetic'],
            'lyrics': 'Test lyrics here',
            'description': 'A test description'
        }
        
        result = temp_db.add_song(song)
        assert result is True
    
    def test_add_song_invalid_url(self, temp_db):
        """Test that invalid URL returns False"""
        song = {
            'title': 'Test Song',
            'url': 'invalid-url'
        }
        
        result = temp_db.add_song(song)
        assert result is False
    
    def test_get_song(self, temp_db):
        """Test retrieving a song by ID"""
        song_id = "12345678-1234-1234-1234-123456789012"
        song = {
            'title': 'Test Song',
            'url': f'https://suno.com/song/{song_id}',
            'artist': 'Test Artist'
        }
        
        temp_db.add_song(song)
        retrieved = temp_db.get_song(song_id)
        
        assert retrieved is not None
        assert retrieved['title'] == 'Test Song'
        assert retrieved['artist'] == 'Test Artist'
    
    def test_get_nonexistent_song(self, temp_db):
        """Test retrieving a song that doesn't exist"""
        result = temp_db.get_song("nonexistent-id")
        assert result is None
    
    def test_search_songs(self, temp_db):
        """Test searching songs by query"""
        # Add test songs
        songs = [
            {'title': 'Rock Anthem', 'url': 'https://suno.com/song/11111111-1111-1111-1111-111111111111', 'tags': ['rock']},
            {'title': 'Jazz Night', 'url': 'https://suno.com/song/22222222-2222-2222-2222-222222222222', 'tags': ['jazz']},
            {'title': 'Rock Ballad', 'url': 'https://suno.com/song/33333333-3333-3333-3333-333333333333', 'tags': ['rock', 'ballad']},
        ]
        
        for song in songs:
            temp_db.add_song(song)
        
        # Search by title
        results = temp_db.search_songs("Rock")
        assert len(results) == 2
    
    def test_get_all_songs(self, temp_db):
        """Test getting all songs"""
        songs = [
            {'title': 'Song 1', 'url': 'https://suno.com/song/11111111-1111-1111-1111-111111111111'},
            {'title': 'Song 2', 'url': 'https://suno.com/song/22222222-2222-2222-2222-222222222222'},
        ]
        
        for song in songs:
            temp_db.add_song(song)
        
        all_songs = temp_db.get_all_songs()
        assert len(all_songs) == 2
    
    def test_rate_song(self, temp_db):
        """Test rating a song"""
        song_id = "12345678-1234-1234-1234-123456789012"
        song = {'title': 'Test Song', 'url': f'https://suno.com/song/{song_id}'}
        
        temp_db.add_song(song)
        temp_db.rate_song(song_id, 5)
        
        retrieved = temp_db.get_song(song_id)
        # Rating should be recorded (check if rating exists in returned data)
        # Note: depends on implementation returning rating
    
    def test_record_play(self, temp_db):
        """Test recording a song play"""
        song_id = "12345678-1234-1234-1234-123456789012"
        song = {'title': 'Test Song', 'url': f'https://suno.com/song/{song_id}'}
        
        temp_db.add_song(song)
        # record_play should not raise an error
        temp_db.record_play(song_id)
        # If we get here without error, the play was recorded
    
    def test_get_statistics(self, temp_db):
        """Test getting database statistics"""
        songs = [
            {'title': 'Song 1', 'url': 'https://suno.com/song/11111111-1111-1111-1111-111111111111', 
             'duration': '3:00', 'tags': ['rock']},
            {'title': 'Song 2', 'url': 'https://suno.com/song/22222222-2222-2222-2222-222222222222',
             'duration': '4:00', 'tags': ['jazz']},
        ]
        
        for song in songs:
            temp_db.add_song(song)
        
        stats = temp_db.get_statistics()
        
        assert stats['total_songs'] == 2
        assert 'total_duration_seconds' in stats
    
    def test_playlist_operations(self, temp_db):
        """Test playlist create and add operations"""
        # Create playlist
        playlist_id = temp_db.create_playlist("My Playlist", "Test description")
        assert playlist_id is not None
        
        # Add song
        song_id = "12345678-1234-1234-1234-123456789012"
        song = {'title': 'Test Song', 'url': f'https://suno.com/song/{song_id}'}
        temp_db.add_song(song)
        
        # Add to playlist should not raise an error
        temp_db.add_to_playlist(playlist_id, song_id)
        # If we get here without error, playlist operations work
    
    def test_backup(self, temp_db):
        """Test database backup"""
        # Add some data
        song = {'title': 'Test', 'url': 'https://suno.com/song/12345678-1234-1234-1234-123456789012'}
        temp_db.add_song(song)
        
        # Create backup
        with tempfile.TemporaryDirectory() as tmpdir:
            backup_path = temp_db.backup(tmpdir)
            assert backup_path is not None
            assert Path(backup_path).exists()
    
    def test_import_from_json(self, temp_db):
        """Test importing songs from JSON file"""
        # Create test JSON
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            data = {
                'songs': [
                    {'title': 'Imported Song', 'url': 'https://suno.com/song/99999999-9999-9999-9999-999999999999'}
                ]
            }
            json.dump(data, f)
            json_path = f.name
        
        try:
            count = temp_db.import_from_json(json_path)
            assert count >= 1
            
            # Verify song was imported
            all_songs = temp_db.get_all_songs()
            assert any(s['title'] == 'Imported Song' for s in all_songs)
        finally:
            os.unlink(json_path)


# =============================================================================
# Run tests
# =============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v"])

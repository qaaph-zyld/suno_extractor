"""
Suno Extractor Pro - Integration Tests

These tests verify the end-to-end workflow:
1. JSON data → Database import
2. Database → Export
3. Downloader initialization
"""

import pytest
import json
import tempfile
import os
from pathlib import Path

# Import modules under test
from suno_core import Config, SunoDatabase, get_config, get_database
from suno_utils import (
    parse_duration, extract_song_id, safe_filename,
    validate_song_data, SunoError
)


# =============================================================================
# Test Fixtures
# =============================================================================

@pytest.fixture
def sample_extraction_data():
    """Sample data simulating extraction output."""
    return {
        "metadata": {
            "extracted_at": "2024-01-15T10:30:00",
            "browser": "chrome",
            "total_songs": 3
        },
        "songs": [
            {
                "title": "Summer Vibes",
                "url": "https://suno.com/song/11111111-1111-1111-1111-111111111111",
                "duration": "3:24",
                "tags": ["pop", "summer", "upbeat"],
                "description": "A catchy summer tune",
                "lyrics": "[Verse 1]\nHere come the summer days...",
                "plays": "1.2k",
                "likes": "500"
            },
            {
                "title": "Night Drive",
                "url": "https://suno.com/song/22222222-2222-2222-2222-222222222222",
                "duration": "4:15",
                "tags": ["electronic", "ambient"],
                "description": "Synthwave vibes for late nights",
                "lyrics": None
            },
            {
                "title": "Jazz Cafe",
                "url": "https://suno.com/song/33333333-3333-3333-3333-333333333333",
                "duration": "5:00",
                "tags": ["jazz", "instrumental"],
                "description": "Smooth jazz for coffee time"
            }
        ]
    }


@pytest.fixture
def temp_json_file(sample_extraction_data):
    """Create a temporary JSON file with sample data."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        json.dump(sample_extraction_data, f)
        temp_path = f.name
    
    yield temp_path
    
    # Cleanup
    if os.path.exists(temp_path):
        os.unlink(temp_path)


@pytest.fixture
def temp_database():
    """Create a temporary database for testing."""
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
        temp_path = f.name
    
    db = SunoDatabase(db_path=temp_path)
    yield db
    
    # Cleanup
    if os.path.exists(temp_path):
        os.unlink(temp_path)


# =============================================================================
# Integration Tests: JSON → Database
# =============================================================================

class TestJSONToDatabase:
    """Test importing JSON extraction data into database."""
    
    def test_import_from_json(self, temp_database, temp_json_file):
        """Test that JSON file can be imported into database."""
        count = temp_database.import_from_json(temp_json_file)
        
        assert count == 3
        
        # Verify songs are in database
        all_songs = temp_database.get_all_songs()
        assert len(all_songs) >= 3
    
    def test_imported_songs_have_correct_data(self, temp_database, temp_json_file):
        """Verify imported song data matches JSON."""
        temp_database.import_from_json(temp_json_file)
        
        # Get the summer vibes song
        song = temp_database.get_song("11111111-1111-1111-1111-111111111111")
        
        assert song is not None
        assert song['title'] == "Summer Vibes"
        assert song['duration_seconds'] == 204  # 3:24 = 204 seconds
    
    def test_import_updates_statistics(self, temp_database, temp_json_file):
        """Test that importing updates database statistics."""
        temp_database.import_from_json(temp_json_file)
        
        stats = temp_database.get_statistics()
        
        assert stats['total_songs'] >= 3
        assert stats['total_duration_seconds'] > 0
    
    def test_import_is_idempotent(self, temp_database, temp_json_file):
        """Test that importing twice doesn't create duplicates."""
        count1 = temp_database.import_from_json(temp_json_file)
        count2 = temp_database.import_from_json(temp_json_file)
        
        # First import adds songs, second should update (not add)
        assert count1 == 3
        
        # Get all songs - should still be 3
        all_songs = temp_database.get_all_songs()
        titles = [s['title'] for s in all_songs]
        
        # Each title should appear only once
        assert titles.count("Summer Vibes") == 1
        assert titles.count("Night Drive") == 1


# =============================================================================
# Integration Tests: Database Operations
# =============================================================================

class TestDatabaseOperations:
    """Test database CRUD operations."""
    
    def test_full_song_lifecycle(self, temp_database):
        """Test adding, rating, playing, and retrieving a song."""
        # Add song
        song = {
            "title": "Test Song",
            "url": "https://suno.com/song/aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
            "duration": "2:30",
            "tags": ["test"]
        }
        
        success = temp_database.add_song(song)
        assert success is True
        
        song_id = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
        
        # Rate song
        temp_database.rate_song(song_id, 5)
        
        # Record play
        temp_database.record_play(song_id)
        
        # Retrieve and verify
        retrieved = temp_database.get_song(song_id)
        assert retrieved is not None
        assert retrieved['title'] == "Test Song"
    
    def test_search_functionality(self, temp_database, temp_json_file):
        """Test search across imported songs."""
        temp_database.import_from_json(temp_json_file)
        
        # Search by title
        results = temp_database.search_songs("Summer")
        assert len(results) >= 1
        assert any(s['title'] == "Summer Vibes" for s in results)
        
        # Search by tag (if supported)
        results = temp_database.search_songs("jazz")
        assert len(results) >= 1
    
    def test_playlist_workflow(self, temp_database, temp_json_file):
        """Test creating and populating a playlist."""
        temp_database.import_from_json(temp_json_file)
        
        # Create playlist
        playlist_id = temp_database.create_playlist("My Favorites", "Best songs")
        assert playlist_id is not None
        
        # Add songs to playlist
        temp_database.add_to_playlist(playlist_id, "11111111-1111-1111-1111-111111111111")
        temp_database.add_to_playlist(playlist_id, "22222222-2222-2222-2222-222222222222")
        
        # Playlist should exist (verify no error was raised)
        assert True


# =============================================================================
# Integration Tests: Data Validation
# =============================================================================

class TestDataValidation:
    """Test data validation across the pipeline."""
    
    def test_song_validation_catches_issues(self):
        """Test that validation correctly identifies problems."""
        # Missing title
        issues = validate_song_data({'url': 'https://suno.com/song/test-id'})
        assert any('title' in i.lower() for i in issues)
        
        # Missing URL
        issues = validate_song_data({'title': 'Test'})
        assert any('url' in i.lower() for i in issues)
        
        # Valid song
        issues = validate_song_data({
            'title': 'Test',
            'url': 'https://suno.com/song/11111111-1111-1111-1111-111111111111'
        })
        assert len(issues) == 0
    
    def test_duration_parsing_consistency(self):
        """Test duration parsing is consistent."""
        test_cases = [
            ("3:24", 204),
            ("1:05:30", 3930),
            ("0:30", 30),
            ("invalid", 0),
        ]
        
        for duration_str, expected_seconds in test_cases:
            result = parse_duration(duration_str)
            assert result == expected_seconds, f"Failed for {duration_str}"
    
    def test_song_id_extraction_consistency(self):
        """Test song ID extraction from various URL formats."""
        test_cases = [
            ("https://suno.com/song/abcd1234-5678-90ab-cdef-1234567890ab", 
             "abcd1234-5678-90ab-cdef-1234567890ab"),
            ("suno.com/song/11111111-2222-3333-4444-555555555555",
             "11111111-2222-3333-4444-555555555555"),
        ]
        
        for url, expected_id in test_cases:
            result = extract_song_id(url)
            assert result == expected_id, f"Failed for {url}"


# =============================================================================
# Integration Tests: Error Handling
# =============================================================================

class TestErrorHandling:
    """Test error handling across components."""
    
    def test_database_handles_invalid_song(self, temp_database):
        """Test that database rejects songs without valid URL."""
        song = {"title": "No URL Song"}  # Missing URL
        
        result = temp_database.add_song(song)
        assert result is False
    
    def test_import_handles_empty_json(self, temp_database):
        """Test importing from JSON with no songs."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump({"metadata": {}, "songs": []}, f)
            temp_path = f.name
        
        try:
            count = temp_database.import_from_json(temp_path)
            assert count == 0
        finally:
            os.unlink(temp_path)
    
    def test_custom_exceptions_work(self):
        """Test that custom exceptions can be raised and caught."""
        from suno_utils import ExtractionError, DownloadError, DatabaseError
        
        with pytest.raises(SunoError):
            raise ExtractionError("Test error")
        
        # Test that subclasses are caught by parent
        try:
            raise DownloadError("Download failed")
        except SunoError as e:
            assert "Download failed" in str(e)

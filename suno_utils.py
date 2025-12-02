"""
Suno Extractor Pro - Shared Utilities

This module contains common utility functions and custom exceptions
used across the Suno Extractor project. Centralizing these reduces
code duplication and ensures consistent behavior.

Usage:
    from suno_utils import parse_duration, extract_song_id, safe_filename
    from suno_utils import SunoError, ExtractionError, DownloadError
"""

import re
import logging
from typing import Optional, Dict, Any, List
from pathlib import Path

# =============================================================================
# Custom Exceptions
# =============================================================================

class SunoError(Exception):
    """Base exception for all Suno-related errors"""
    pass


class ExtractionError(SunoError):
    """Raised when song extraction from browser fails"""
    pass


class DownloadError(SunoError):
    """Raised when audio download fails"""
    pass


class DatabaseError(SunoError):
    """Raised when database operations fail"""
    pass


class ConfigError(SunoError):
    """Raised when configuration is invalid"""
    pass


class AudioError(SunoError):
    """Raised when audio processing fails"""
    pass


# =============================================================================
# Duration Parsing
# =============================================================================

def parse_duration(duration_str: str) -> int:
    """
    Parse duration string to seconds.
    
    Supports formats:
        - "MM:SS" (e.g., "3:24" -> 204)
        - "HH:MM:SS" (e.g., "1:05:30" -> 3930)
        - "M:SS" (e.g., "1:05" -> 65)
    
    Args:
        duration_str: Duration in string format
        
    Returns:
        Duration in seconds, or 0 if parsing fails
        
    Examples:
        >>> parse_duration("3:24")
        204
        >>> parse_duration("1:05:30")
        3930
        >>> parse_duration("invalid")
        0
    """
    if not duration_str or not isinstance(duration_str, str):
        return 0
    
    try:
        # Remove any whitespace
        duration_str = duration_str.strip()
        
        parts = duration_str.split(':')
        if len(parts) == 2:
            # MM:SS format
            minutes, seconds = int(parts[0]), int(parts[1])
            return minutes * 60 + seconds
        elif len(parts) == 3:
            # HH:MM:SS format
            hours, minutes, seconds = int(parts[0]), int(parts[1]), int(parts[2])
            return hours * 3600 + minutes * 60 + seconds
        else:
            return 0
    except (ValueError, AttributeError):
        return 0


def format_duration(seconds: int) -> str:
    """
    Format seconds as duration string.
    
    Args:
        seconds: Duration in seconds
        
    Returns:
        Formatted string (MM:SS or HH:MM:SS)
        
    Examples:
        >>> format_duration(204)
        "3:24"
        >>> format_duration(3930)
        "1:05:30"
    """
    if seconds < 0:
        seconds = 0
    
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    secs = seconds % 60
    
    if hours > 0:
        return f"{hours}:{minutes:02d}:{secs:02d}"
    else:
        return f"{minutes}:{secs:02d}"


# =============================================================================
# Song ID Extraction
# =============================================================================

# Compiled regex patterns for song ID extraction (optimization)
_SONG_ID_PATTERNS = [
    re.compile(r'/song/([a-f0-9-]{36})'),  # Standard URL format
    re.compile(r'([a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12})'),  # Raw UUID
]


def extract_song_id(url: str) -> Optional[str]:
    """
    Extract song ID (UUID) from a Suno URL or string containing a UUID.
    
    Args:
        url: Suno song URL or string containing UUID
        
    Returns:
        36-character UUID string, or None if not found
        
    Examples:
        >>> extract_song_id("https://suno.com/song/abc12345-1234-1234-1234-123456789abc")
        "abc12345-1234-1234-1234-123456789abc"
        >>> extract_song_id("invalid")
        None
    """
    if not url or not isinstance(url, str):
        return None
    
    for pattern in _SONG_ID_PATTERNS:
        match = pattern.search(url)
        if match:
            return match.group(1)
    
    return None


def is_valid_song_id(song_id: str) -> bool:
    """
    Check if a string is a valid Suno song ID (UUID format).
    
    Args:
        song_id: String to validate
        
    Returns:
        True if valid UUID format
    """
    if not song_id or not isinstance(song_id, str):
        return False
    
    uuid_pattern = re.compile(
        r'^[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}$',
        re.IGNORECASE
    )
    return bool(uuid_pattern.match(song_id))


# =============================================================================
# Filename Utilities
# =============================================================================

# Characters invalid in filenames on Windows and Unix
_INVALID_FILENAME_CHARS = re.compile(r'[<>:"/\\|?*\x00-\x1f]')


def safe_filename(name: str, max_length: int = 100, replacement: str = '_') -> str:
    """
    Convert a string to a safe filename by removing/replacing invalid characters.
    
    Args:
        name: Original filename or title
        max_length: Maximum length of result (default 100)
        replacement: Character to replace invalid chars with (default '_')
        
    Returns:
        Sanitized filename safe for all operating systems
        
    Examples:
        >>> safe_filename('My Song: "The Best"')
        "My Song_ _The Best_"
        >>> safe_filename("A" * 200)
        "AAAA..." (truncated to 100)
    """
    if not name or not isinstance(name, str):
        return "untitled"
    
    # Replace invalid characters
    safe = _INVALID_FILENAME_CHARS.sub(replacement, name)
    
    # Remove leading/trailing whitespace and dots (problematic on Windows)
    safe = safe.strip(' .')
    
    # Collapse multiple replacement chars
    if replacement:
        safe = re.sub(f'{re.escape(replacement)}+', replacement, safe)
    
    # Truncate to max length
    if len(safe) > max_length:
        safe = safe[:max_length].rstrip(' .')
    
    # Ensure we have something
    return safe if safe else "untitled"


def generate_unique_path(directory: Path, base_name: str, extension: str) -> Path:
    """
    Generate a unique file path, adding numbers if file exists.
    
    Args:
        directory: Target directory
        base_name: Base filename (without extension)
        extension: File extension (without dot)
        
    Returns:
        Path that doesn't exist yet
        
    Examples:
        >>> generate_unique_path(Path("./"), "song", "mp3")
        Path("./song.mp3")  # or song_1.mp3 if song.mp3 exists
    """
    directory = Path(directory)
    safe_base = safe_filename(base_name)
    
    # Try original name first
    target = directory / f"{safe_base}.{extension}"
    if not target.exists():
        return target
    
    # Add incrementing number
    counter = 1
    while True:
        target = directory / f"{safe_base}_{counter}.{extension}"
        if not target.exists():
            return target
        counter += 1
        if counter > 9999:  # Safety limit
            raise SunoError(f"Could not generate unique filename for {base_name}")


# =============================================================================
# Data Validation
# =============================================================================

def validate_song_data(song: Dict[str, Any]) -> List[str]:
    """
    Validate song data dictionary and return list of issues.
    
    Args:
        song: Song data dictionary
        
    Returns:
        List of validation error messages (empty if valid)
    """
    issues = []
    
    if not isinstance(song, dict):
        return ["Song data must be a dictionary"]
    
    # Required fields
    if not song.get('title'):
        issues.append("Missing or empty 'title'")
    
    if not song.get('url'):
        issues.append("Missing or empty 'url'")
    elif not extract_song_id(song['url']):
        issues.append(f"Invalid song URL format: {song['url']}")
    
    # Type checks for optional fields
    if 'tags' in song and not isinstance(song['tags'], (list, tuple)):
        issues.append("'tags' must be a list")
    
    if 'duration' in song and song['duration']:
        if isinstance(song['duration'], str) and parse_duration(song['duration']) == 0:
            if ':' in song['duration']:  # Only warn if it looks like a duration
                issues.append(f"Could not parse duration: {song['duration']}")
    
    return issues


# =============================================================================
# Logging Setup
# =============================================================================

def setup_logging(
    level: str = "INFO",
    log_file: Optional[str] = None,
    use_rich: bool = True
) -> logging.Logger:
    """
    Configure logging for the application.
    
    Args:
        level: Log level (DEBUG, INFO, WARNING, ERROR)
        log_file: Optional file path for log output
        use_rich: Use Rich handler for colorful console output
        
    Returns:
        Configured root logger
    """
    log_level = getattr(logging, level.upper(), logging.INFO)
    
    # Create formatters
    detailed_format = "%(asctime)s | %(name)s | %(levelname)s | %(message)s"
    simple_format = "%(message)s"
    
    handlers: List[logging.Handler] = []
    
    # Console handler
    if use_rich:
        try:
            from rich.logging import RichHandler
            console_handler = RichHandler(
                rich_tracebacks=True,
                markup=True,
                show_time=False
            )
            console_handler.setFormatter(logging.Formatter(simple_format))
        except ImportError:
            console_handler = logging.StreamHandler()
            console_handler.setFormatter(logging.Formatter(detailed_format))
    else:
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(logging.Formatter(detailed_format))
    
    handlers.append(console_handler)
    
    # File handler
    if log_file:
        file_handler = logging.FileHandler(log_file, encoding='utf-8')
        file_handler.setFormatter(logging.Formatter(detailed_format))
        handlers.append(file_handler)
    
    # Configure root logger
    logging.basicConfig(
        level=log_level,
        handlers=handlers,
        force=True  # Override any existing configuration
    )
    
    return logging.getLogger()


# =============================================================================
# Module Info
# =============================================================================

__version__ = "1.0.0"
__all__ = [
    # Exceptions
    'SunoError',
    'ExtractionError', 
    'DownloadError',
    'DatabaseError',
    'ConfigError',
    'AudioError',
    # Duration utilities
    'parse_duration',
    'format_duration',
    # Song ID utilities
    'extract_song_id',
    'is_valid_song_id',
    # Filename utilities
    'safe_filename',
    'generate_unique_path',
    # Validation
    'validate_song_data',
    # Logging
    'setup_logging',
]

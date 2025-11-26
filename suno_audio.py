#!/usr/bin/env python3
"""
Suno Audio Analysis & Processing
Advanced audio features: BPM detection, key detection, waveform, normalization
"""

import os
import json
import logging
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from concurrent.futures import ThreadPoolExecutor, as_completed
import hashlib

logger = logging.getLogger(__name__)

# Audio analysis with librosa
try:
    import librosa
    import librosa.display
    LIBROSA_AVAILABLE = True
except ImportError:
    LIBROSA_AVAILABLE = False
    logger.warning("librosa not available - audio analysis disabled")

# Audio processing with pydub
try:
    from pydub import AudioSegment
    from pydub.effects import normalize, compress_dynamic_range
    PYDUB_AVAILABLE = True
except ImportError:
    PYDUB_AVAILABLE = False
    logger.warning("pydub not available - audio processing disabled")

# Image generation
try:
    import numpy as np
    from PIL import Image
    NUMPY_AVAILABLE = True
except ImportError:
    NUMPY_AVAILABLE = False

# Matplotlib for waveform images
try:
    import matplotlib
    matplotlib.use('Agg')  # Non-interactive backend
    import matplotlib.pyplot as plt
    MATPLOTLIB_AVAILABLE = True
except ImportError:
    MATPLOTLIB_AVAILABLE = False


class AudioAnalyzer:
    """Analyze audio files for BPM, key, and other features"""
    
    # Key mappings (Camelot wheel)
    KEY_NAMES = {
        0: 'C', 1: 'C#/Db', 2: 'D', 3: 'D#/Eb', 4: 'E', 5: 'F',
        6: 'F#/Gb', 7: 'G', 8: 'G#/Ab', 9: 'A', 10: 'A#/Bb', 11: 'B'
    }
    
    CAMELOT_WHEEL = {
        ('C', 'major'): '8B', ('A', 'minor'): '8A',
        ('G', 'major'): '9B', ('E', 'minor'): '9A',
        ('D', 'major'): '10B', ('B', 'minor'): '10A',
        ('A', 'major'): '11B', ('F#', 'minor'): '11A',
        ('E', 'major'): '12B', ('C#', 'minor'): '12A',
        ('B', 'major'): '1B', ('G#', 'minor'): '1A',
        ('F#', 'major'): '2B', ('D#', 'minor'): '2A',
        ('Db', 'major'): '3B', ('Bb', 'minor'): '3A',
        ('Ab', 'major'): '4B', ('F', 'minor'): '4A',
        ('Eb', 'major'): '5B', ('C', 'minor'): '5A',
        ('Bb', 'major'): '6B', ('G', 'minor'): '6A',
        ('F', 'major'): '7B', ('D', 'minor'): '7A',
    }
    
    def __init__(self, cache_dir: str = ".audio_cache"):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(exist_ok=True)
    
    def analyze_file(self, filepath: str, 
                     detect_bpm: bool = True,
                     detect_key: bool = True,
                     calculate_energy: bool = True) -> Dict:
        """
        Analyze an audio file for various features
        
        Args:
            filepath: Path to audio file
            detect_bpm: Whether to detect tempo/BPM
            detect_key: Whether to detect musical key
            calculate_energy: Whether to calculate energy levels
            
        Returns:
            Dict with analysis results
        """
        if not LIBROSA_AVAILABLE:
            logger.warning("librosa not available")
            return {}
        
        filepath = Path(filepath)
        if not filepath.exists():
            logger.error(f"File not found: {filepath}")
            return {}
        
        results = {
            'filepath': str(filepath),
            'filename': filepath.name,
            'analyzed': False
        }
        
        try:
            # Load audio file
            logger.info(f"Analyzing: {filepath.name}")
            y, sr = librosa.load(str(filepath), sr=None, mono=True)
            
            results['duration'] = librosa.get_duration(y=y, sr=sr)
            results['sample_rate'] = sr
            results['analyzed'] = True
            
            # BPM Detection
            if detect_bpm:
                tempo, beats = librosa.beat.beat_track(y=y, sr=sr)
                # Handle both scalar and array returns
                if hasattr(tempo, '__len__'):
                    tempo = float(tempo[0]) if len(tempo) > 0 else 0.0
                results['bpm'] = round(float(tempo), 1)
                results['beat_frames'] = beats.tolist() if hasattr(beats, 'tolist') else []
                logger.debug(f"BPM: {results['bpm']}")
            
            # Key Detection
            if detect_key:
                key_info = self._detect_key(y, sr)
                results.update(key_info)
                logger.debug(f"Key: {results.get('key', 'Unknown')}")
            
            # Energy Analysis
            if calculate_energy:
                energy_info = self._calculate_energy(y, sr)
                results.update(energy_info)
            
            logger.info(f"✓ Analyzed: {filepath.name} - BPM: {results.get('bpm')}, Key: {results.get('key')}")
            
        except Exception as e:
            logger.error(f"Analysis failed for {filepath}: {e}")
            results['error'] = str(e)
        
        return results
    
    def _detect_key(self, y, sr) -> Dict:
        """Detect musical key using chroma features"""
        try:
            # Compute chromagram
            chroma = librosa.feature.chroma_cqt(y=y, sr=sr)
            
            # Average chroma across time
            chroma_avg = chroma.mean(axis=1)
            
            # Find the most prominent pitch class
            key_idx = int(chroma_avg.argmax())
            key_name = self.KEY_NAMES.get(key_idx, 'Unknown')
            
            # Determine major/minor using correlation with templates
            major_template = [1, 0, 1, 0, 1, 1, 0, 1, 0, 1, 0, 1]  # Major scale
            minor_template = [1, 0, 1, 1, 0, 1, 0, 1, 1, 0, 1, 0]  # Minor scale
            
            # Rotate templates to detected key
            major_rotated = major_template[key_idx:] + major_template[:key_idx]
            minor_rotated = minor_template[key_idx:] + minor_template[:key_idx]
            
            major_corr = sum(c * t for c, t in zip(chroma_avg, major_rotated))
            minor_corr = sum(c * t for c, t in zip(chroma_avg, minor_rotated))
            
            mode = 'major' if major_corr >= minor_corr else 'minor'
            
            # Get Camelot notation
            key_simple = key_name.split('/')[0]
            camelot = self.CAMELOT_WHEEL.get((key_simple, mode), '')
            
            return {
                'key': f"{key_name} {mode}",
                'key_confidence': float(max(major_corr, minor_corr) / sum(chroma_avg)),
                'camelot': camelot,
                'mode': mode
            }
            
        except Exception as e:
            logger.error(f"Key detection failed: {e}")
            return {'key': 'Unknown', 'mode': 'unknown'}
    
    def _calculate_energy(self, y, sr) -> Dict:
        """Calculate energy and loudness metrics"""
        try:
            # RMS energy
            rms = librosa.feature.rms(y=y)[0]
            
            # Spectral centroid (brightness)
            centroid = librosa.feature.spectral_centroid(y=y, sr=sr)[0]
            
            # Zero crossing rate (noisiness/percussiveness)
            zcr = librosa.feature.zero_crossing_rate(y)[0]
            
            return {
                'energy_mean': float(rms.mean()),
                'energy_std': float(rms.std()),
                'brightness': float(centroid.mean()),
                'percussiveness': float(zcr.mean()),
                'dynamic_range': float(rms.max() - rms.min())
            }
            
        except Exception as e:
            logger.error(f"Energy calculation failed: {e}")
            return {}
    
    def generate_waveform(self, filepath: str, output_path: str = None,
                          width: int = 800, height: int = 200,
                          color: str = '#3498db',
                          bg_color: str = '#1a1a2e') -> Optional[Path]:
        """
        Generate waveform image for an audio file
        
        Args:
            filepath: Path to audio file
            output_path: Output path for image (auto-generated if None)
            width: Image width in pixels
            height: Image height in pixels
            color: Waveform color (hex)
            bg_color: Background color (hex)
            
        Returns:
            Path to generated image or None
        """
        if not LIBROSA_AVAILABLE or not MATPLOTLIB_AVAILABLE:
            logger.warning("Required libraries not available for waveform generation")
            return None
        
        filepath = Path(filepath)
        if not filepath.exists():
            logger.error(f"File not found: {filepath}")
            return None
        
        if output_path is None:
            output_path = filepath.with_suffix('.png')
        
        output_path = Path(output_path)
        
        try:
            # Load audio
            y, sr = librosa.load(str(filepath), sr=22050, mono=True)
            
            # Create figure
            fig, ax = plt.subplots(figsize=(width/100, height/100), dpi=100)
            fig.patch.set_facecolor(bg_color)
            ax.set_facecolor(bg_color)
            
            # Plot waveform
            librosa.display.waveshow(y, sr=sr, ax=ax, color=color, alpha=0.8)
            
            # Remove axes
            ax.set_xlim(0, len(y)/sr)
            ax.axis('off')
            
            # Save
            plt.tight_layout(pad=0)
            plt.savefig(str(output_path), 
                       facecolor=bg_color, 
                       edgecolor='none',
                       bbox_inches='tight',
                       pad_inches=0)
            plt.close(fig)
            
            logger.info(f"✓ Waveform saved: {output_path}")
            return output_path
            
        except Exception as e:
            logger.error(f"Waveform generation failed: {e}")
            return None
    
    def generate_spectrogram(self, filepath: str, output_path: str = None,
                             width: int = 800, height: int = 300) -> Optional[Path]:
        """Generate spectrogram image"""
        if not LIBROSA_AVAILABLE or not MATPLOTLIB_AVAILABLE:
            return None
        
        filepath = Path(filepath)
        if output_path is None:
            output_path = filepath.with_name(f"{filepath.stem}_spectrogram.png")
        
        output_path = Path(output_path)
        
        try:
            y, sr = librosa.load(str(filepath), sr=22050, mono=True)
            
            # Compute mel spectrogram
            S = librosa.feature.melspectrogram(y=y, sr=sr, n_mels=128)
            S_dB = librosa.power_to_db(S, ref=np.max)
            
            fig, ax = plt.subplots(figsize=(width/100, height/100), dpi=100)
            
            librosa.display.specshow(S_dB, sr=sr, x_axis='time', 
                                     y_axis='mel', ax=ax, cmap='magma')
            
            ax.axis('off')
            plt.tight_layout(pad=0)
            plt.savefig(str(output_path), bbox_inches='tight', pad_inches=0)
            plt.close(fig)
            
            logger.info(f"✓ Spectrogram saved: {output_path}")
            return output_path
            
        except Exception as e:
            logger.error(f"Spectrogram generation failed: {e}")
            return None
    
    def batch_analyze(self, audio_dir: str, 
                      output_json: str = None,
                      max_workers: int = 4) -> List[Dict]:
        """
        Analyze all audio files in a directory
        
        Args:
            audio_dir: Directory containing audio files
            output_json: Optional path to save results
            max_workers: Parallel analysis threads
            
        Returns:
            List of analysis results
        """
        audio_dir = Path(audio_dir)
        
        # Find all audio files
        audio_files = []
        for ext in ['*.mp3', '*.m4a', '*.wav', '*.flac', '*.ogg']:
            audio_files.extend(audio_dir.glob(ext))
        
        if not audio_files:
            logger.warning(f"No audio files found in {audio_dir}")
            return []
        
        logger.info(f"Analyzing {len(audio_files)} audio files...")
        
        results = []
        
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {
                executor.submit(self.analyze_file, str(f)): f
                for f in audio_files
            }
            
            for future in as_completed(futures):
                filepath = futures[future]
                try:
                    result = future.result()
                    if result.get('analyzed'):
                        results.append(result)
                except Exception as e:
                    logger.error(f"Analysis failed for {filepath}: {e}")
        
        # Save results if requested
        if output_json:
            with open(output_json, 'w', encoding='utf-8') as f:
                json.dump(results, f, indent=2)
            logger.info(f"Results saved to {output_json}")
        
        return results


class AudioProcessor:
    """Audio processing: normalization, format conversion, effects"""
    
    def __init__(self, output_dir: str = "processed_audio"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)
    
    def normalize_audio(self, filepath: str, 
                        target_dbfs: float = -14.0,
                        output_path: str = None) -> Optional[Path]:
        """
        Normalize audio loudness
        
        Args:
            filepath: Input audio file
            target_dbfs: Target loudness in dBFS
            output_path: Output path (in-place if None)
            
        Returns:
            Path to normalized file
        """
        if not PYDUB_AVAILABLE:
            logger.warning("pydub not available")
            return None
        
        filepath = Path(filepath)
        if not filepath.exists():
            logger.error(f"File not found: {filepath}")
            return None
        
        try:
            # Load audio
            audio = AudioSegment.from_file(str(filepath))
            
            # Calculate change needed
            change_in_dbfs = target_dbfs - audio.dBFS
            
            # Apply gain
            normalized = audio.apply_gain(change_in_dbfs)
            
            # Determine output path
            if output_path is None:
                output_path = filepath
            else:
                output_path = Path(output_path)
            
            # Export
            format = output_path.suffix[1:].lower()
            if format == 'm4a':
                format = 'mp4'
            
            normalized.export(str(output_path), format=format)
            
            logger.info(f"✓ Normalized: {filepath.name} ({change_in_dbfs:+.1f} dB)")
            return output_path
            
        except Exception as e:
            logger.error(f"Normalization failed for {filepath}: {e}")
            return None
    
    def convert_format(self, filepath: str, 
                       target_format: str,
                       output_dir: str = None,
                       bitrate: str = "320k") -> Optional[Path]:
        """
        Convert audio to different format
        
        Args:
            filepath: Input audio file
            target_format: Target format (mp3, flac, wav, m4a)
            output_dir: Output directory
            bitrate: Target bitrate for lossy formats
            
        Returns:
            Path to converted file
        """
        if not PYDUB_AVAILABLE:
            logger.warning("pydub not available")
            return None
        
        filepath = Path(filepath)
        if not filepath.exists():
            logger.error(f"File not found: {filepath}")
            return None
        
        try:
            # Load audio
            audio = AudioSegment.from_file(str(filepath))
            
            # Determine output path
            if output_dir:
                out_dir = Path(output_dir)
                out_dir.mkdir(exist_ok=True)
            else:
                out_dir = self.output_dir
            
            output_path = out_dir / f"{filepath.stem}.{target_format}"
            
            # Export with appropriate settings
            export_format = target_format
            if target_format == 'm4a':
                export_format = 'mp4'
            
            export_kwargs = {}
            if target_format in ['mp3', 'm4a', 'ogg']:
                export_kwargs['bitrate'] = bitrate
            
            audio.export(str(output_path), format=export_format, **export_kwargs)
            
            logger.info(f"✓ Converted: {filepath.name} -> {output_path.name}")
            return output_path
            
        except Exception as e:
            logger.error(f"Conversion failed for {filepath}: {e}")
            return None
    
    def batch_normalize(self, audio_dir: str,
                        target_dbfs: float = -14.0,
                        in_place: bool = False) -> int:
        """Normalize all audio files in a directory"""
        audio_dir = Path(audio_dir)
        
        audio_files = []
        for ext in ['*.mp3', '*.m4a', '*.wav', '*.flac']:
            audio_files.extend(audio_dir.glob(ext))
        
        count = 0
        for filepath in audio_files:
            output = str(filepath) if in_place else str(self.output_dir / filepath.name)
            if self.normalize_audio(str(filepath), target_dbfs, output):
                count += 1
        
        logger.info(f"Normalized {count}/{len(audio_files)} files")
        return count
    
    def batch_convert(self, audio_dir: str,
                      target_format: str,
                      bitrate: str = "320k") -> int:
        """Convert all audio files in a directory"""
        audio_dir = Path(audio_dir)
        
        audio_files = []
        for ext in ['*.mp3', '*.m4a', '*.wav', '*.flac']:
            audio_files.extend(audio_dir.glob(ext))
        
        count = 0
        for filepath in audio_files:
            if filepath.suffix[1:].lower() != target_format:
                if self.convert_format(str(filepath), target_format, bitrate=bitrate):
                    count += 1
        
        logger.info(f"Converted {count} files to {target_format}")
        return count


class CoverArtManager:
    """Manage cover art downloads and organization"""
    
    def __init__(self, cover_dir: str = "suno_covers"):
        self.cover_dir = Path(cover_dir)
        self.cover_dir.mkdir(exist_ok=True)
    
    def download_cover(self, image_url: str, song_id: str,
                       filename: str = None) -> Optional[Path]:
        """
        Download cover art image
        
        Args:
            image_url: URL of the cover image
            song_id: Song ID for naming
            filename: Optional custom filename
            
        Returns:
            Path to downloaded image
        """
        import requests
        
        if not image_url:
            return None
        
        try:
            response = requests.get(image_url, timeout=30)
            response.raise_for_status()
            
            # Determine file extension
            content_type = response.headers.get('content-type', 'image/jpeg')
            ext = 'jpg' if 'jpeg' in content_type else 'png'
            
            # Generate filename
            if filename is None:
                filename = f"{song_id}.{ext}"
            
            filepath = self.cover_dir / filename
            
            with open(filepath, 'wb') as f:
                f.write(response.content)
            
            logger.debug(f"Downloaded cover: {filepath}")
            return filepath
            
        except Exception as e:
            logger.error(f"Cover download failed: {e}")
            return None
    
    def download_all_covers(self, songs: List[Dict], 
                           max_workers: int = 5) -> Dict[str, Path]:
        """Download cover art for all songs"""
        results = {}
        
        def download_one(song):
            song_id = song.get('id') or self._extract_id(song.get('url', ''))
            image_url = song.get('image_url')
            if song_id and image_url:
                path = self.download_cover(image_url, song_id)
                if path:
                    return song_id, path
            return None, None
        
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = [executor.submit(download_one, song) for song in songs]
            
            for future in as_completed(futures):
                song_id, path = future.result()
                if song_id and path:
                    results[song_id] = path
        
        logger.info(f"Downloaded {len(results)} cover images")
        return results
    
    def _extract_id(self, url: str) -> Optional[str]:
        """Extract song ID from URL"""
        import re
        match = re.search(r'/song/([a-f0-9-]{36})', url)
        return match.group(1) if match else None
    
    def create_thumbnail(self, cover_path: str, 
                         size: Tuple[int, int] = (150, 150)) -> Optional[Path]:
        """Create thumbnail from cover art"""
        if not NUMPY_AVAILABLE:
            return None
        
        cover_path = Path(cover_path)
        if not cover_path.exists():
            return None
        
        try:
            img = Image.open(cover_path)
            img.thumbnail(size, Image.Resampling.LANCZOS)
            
            thumb_path = cover_path.with_name(f"{cover_path.stem}_thumb{cover_path.suffix}")
            img.save(thumb_path, quality=85)
            
            return thumb_path
            
        except Exception as e:
            logger.error(f"Thumbnail creation failed: {e}")
            return None


class DuplicateDetector:
    """Detect duplicate songs using various methods"""
    
    def __init__(self):
        pass
    
    def find_duplicates_by_hash(self, audio_dir: str) -> List[Tuple[Path, Path]]:
        """Find exact duplicates by file hash"""
        audio_dir = Path(audio_dir)
        
        hashes = {}
        duplicates = []
        
        for ext in ['*.mp3', '*.m4a', '*.wav']:
            for filepath in audio_dir.glob(ext):
                file_hash = self._calculate_hash(filepath)
                if file_hash in hashes:
                    duplicates.append((hashes[file_hash], filepath))
                else:
                    hashes[file_hash] = filepath
        
        return duplicates
    
    def find_duplicates_by_fingerprint(self, audio_dir: str,
                                       threshold: float = 0.9) -> List[Tuple[Path, Path, float]]:
        """Find similar songs by audio fingerprint"""
        if not LIBROSA_AVAILABLE:
            logger.warning("librosa required for fingerprint detection")
            return []
        
        audio_dir = Path(audio_dir)
        
        # Compute fingerprints
        fingerprints = {}
        
        for ext in ['*.mp3', '*.m4a', '*.wav']:
            for filepath in audio_dir.glob(ext):
                try:
                    y, sr = librosa.load(str(filepath), sr=22050, mono=True, duration=30)
                    mfcc = librosa.feature.mfcc(y=y, sr=sr, n_mfcc=13)
                    fingerprints[filepath] = mfcc.mean(axis=1)
                except Exception:
                    continue
        
        # Compare fingerprints
        duplicates = []
        filepaths = list(fingerprints.keys())
        
        for i, fp1 in enumerate(filepaths):
            for fp2 in filepaths[i+1:]:
                similarity = self._cosine_similarity(
                    fingerprints[fp1],
                    fingerprints[fp2]
                )
                if similarity >= threshold:
                    duplicates.append((fp1, fp2, similarity))
        
        return duplicates
    
    def find_duplicates_by_title(self, songs: List[Dict],
                                 threshold: float = 0.85) -> List[Tuple[Dict, Dict, float]]:
        """Find duplicates by similar titles"""
        duplicates = []
        
        for i, song1 in enumerate(songs):
            for song2 in songs[i+1:]:
                similarity = self._string_similarity(
                    song1.get('title', ''),
                    song2.get('title', '')
                )
                if similarity >= threshold:
                    duplicates.append((song1, song2, similarity))
        
        return duplicates
    
    def _calculate_hash(self, filepath: Path) -> str:
        """Calculate MD5 hash of file"""
        hasher = hashlib.md5()
        with open(filepath, 'rb') as f:
            for chunk in iter(lambda: f.read(8192), b''):
                hasher.update(chunk)
        return hasher.hexdigest()
    
    def _cosine_similarity(self, a, b) -> float:
        """Calculate cosine similarity between vectors"""
        if not NUMPY_AVAILABLE:
            return 0.0
        dot = np.dot(a, b)
        norm_a = np.linalg.norm(a)
        norm_b = np.linalg.norm(b)
        return float(dot / (norm_a * norm_b)) if norm_a and norm_b else 0.0
    
    def _string_similarity(self, s1: str, s2: str) -> float:
        """Calculate string similarity (Jaccard)"""
        if not s1 or not s2:
            return 0.0
        
        words1 = set(s1.lower().split())
        words2 = set(s2.lower().split())
        
        intersection = len(words1 & words2)
        union = len(words1 | words2)
        
        return intersection / union if union > 0 else 0.0


def main():
    """Demo and testing"""
    import sys
    
    logging.basicConfig(level=logging.INFO)
    
    if len(sys.argv) < 2:
        print("Usage: python suno_audio.py <audio_file_or_dir>")
        print("\nCommands:")
        print("  python suno_audio.py analyze <file>")
        print("  python suno_audio.py waveform <file>")
        print("  python suno_audio.py normalize <file>")
        print("  python suno_audio.py convert <file> <format>")
        print("  python suno_audio.py batch-analyze <dir>")
        sys.exit(1)
    
    command = sys.argv[1]
    
    if command == "analyze" and len(sys.argv) > 2:
        analyzer = AudioAnalyzer()
        result = analyzer.analyze_file(sys.argv[2])
        print(json.dumps(result, indent=2))
    
    elif command == "waveform" and len(sys.argv) > 2:
        analyzer = AudioAnalyzer()
        output = analyzer.generate_waveform(sys.argv[2])
        print(f"Waveform saved to: {output}")
    
    elif command == "normalize" and len(sys.argv) > 2:
        processor = AudioProcessor()
        output = processor.normalize_audio(sys.argv[2])
        print(f"Normalized: {output}")
    
    elif command == "convert" and len(sys.argv) > 3:
        processor = AudioProcessor()
        output = processor.convert_format(sys.argv[2], sys.argv[3])
        print(f"Converted to: {output}")
    
    elif command == "batch-analyze" and len(sys.argv) > 2:
        analyzer = AudioAnalyzer()
        results = analyzer.batch_analyze(sys.argv[2], "analysis_results.json")
        print(f"Analyzed {len(results)} files")
    
    else:
        # Single file analysis
        analyzer = AudioAnalyzer()
        result = analyzer.analyze_file(sys.argv[1])
        print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()

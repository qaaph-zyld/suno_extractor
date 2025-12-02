#!/usr/bin/env python3
"""
Suno Extractor Pro - Unified Entry Point

Single command-line interface for all Suno Extractor functionality.

Usage:
    python suno.py extract   - Extract songs from browser
    python suno.py download  - Download audio files
    python suno.py play      - Launch music player
    python suno.py web       - Start web dashboard
    python suno.py stats     - Show library statistics
    python suno.py search    - Search your library
"""

import sys
import argparse


def main():
    """Main entry point for Suno Extractor Pro"""
    parser = argparse.ArgumentParser(
        prog='suno',
        description='🎵 Suno Extractor Pro - Complete Music Library Manager',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  suno extract --tabs creations,likes    Extract from multiple tabs
  suno download --json-file songs.json   Download from JSON
  suno web --port 5001                   Start web dashboard on port 5001
  suno play                              Launch music player
  suno stats                             Show library statistics
        """
    )
    
    subparsers = parser.add_subparsers(dest='command', help='Available commands')
    
    # =========================================================================
    # Extract command
    # =========================================================================
    extract_parser = subparsers.add_parser(
        'extract', 
        help='Extract songs from Suno browser session'
    )
    extract_parser.add_argument('--browser', default='chrome', 
                               choices=['chrome', 'firefox'],
                               help='Browser type (default: chrome)')
    extract_parser.add_argument('--port', type=int, default=9222,
                               help='Browser debug port (default: 9222)')
    extract_parser.add_argument('--output', default='suno_songs',
                               help='Output directory (default: suno_songs)')
    extract_parser.add_argument('--tabs', default='creations',
                               help='Tabs to extract: creations,likes (default: creations)')
    extract_parser.add_argument('--formats', default='md,json,csv',
                               help='Output formats (default: md,json,csv)')
    extract_parser.add_argument('--fast', action='store_true',
                               help='Skip detailed extraction')
    extract_parser.add_argument('--full', action='store_true',
                               help='Full extraction (ignore existing songs)')
    extract_parser.add_argument('--skip-db', action='store_true',
                               help='Skip database import after extraction')
    
    # =========================================================================
    # Download command
    # =========================================================================
    download_parser = subparsers.add_parser(
        'download',
        help='Download audio files from extraction JSON'
    )
    download_parser.add_argument('--json-file', required=True,
                                help='Path to extraction JSON file')
    download_parser.add_argument('--format', default='mp3',
                                choices=['mp3', 'm4a', 'wav'],
                                help='Audio format (default: mp3)')
    download_parser.add_argument('--output', default='suno_downloads',
                                help='Output directory (default: suno_downloads)')
    download_parser.add_argument('--workers', type=int, default=3,
                                help='Parallel download workers (default: 3)')
    
    # =========================================================================
    # Web command
    # =========================================================================
    web_parser = subparsers.add_parser(
        'web',
        help='Start the web dashboard'
    )
    web_parser.add_argument('--port', type=int, default=5000,
                           help='Server port (default: 5000)')
    web_parser.add_argument('--host', default='127.0.0.1',
                           help='Server host (default: 127.0.0.1)')
    web_parser.add_argument('--debug', action='store_true',
                           help='Enable debug mode')
    
    # =========================================================================
    # Play command
    # =========================================================================
    play_parser = subparsers.add_parser(
        'play',
        help='Launch the music player'
    )
    play_parser.add_argument('--json-file',
                            help='Load playlist from JSON file')
    play_parser.add_argument('--dir', default='suno_downloads',
                            help='Audio directory (default: suno_downloads)')
    play_parser.add_argument('--shuffle', action='store_true',
                            help='Start with shuffle enabled')
    
    # =========================================================================
    # Stats command
    # =========================================================================
    stats_parser = subparsers.add_parser(
        'stats',
        help='Show library statistics'
    )
    stats_parser.add_argument('--json-file',
                             help='Stats from JSON file instead of database')
    
    # =========================================================================
    # Search command
    # =========================================================================
    search_parser = subparsers.add_parser(
        'search',
        help='Search your music library'
    )
    search_parser.add_argument('query', nargs='?', default='',
                              help='Search query')
    search_parser.add_argument('--tag', help='Filter by tag')
    search_parser.add_argument('--limit', type=int, default=20,
                              help='Max results (default: 20)')
    
    # =========================================================================
    # Parse and dispatch
    # =========================================================================
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        sys.exit(0)
    
    # Dispatch to appropriate handler
    if args.command == 'extract':
        run_extract(args)
    elif args.command == 'download':
        run_download(args)
    elif args.command == 'web':
        run_web(args)
    elif args.command == 'play':
        run_play(args)
    elif args.command == 'stats':
        run_stats(args)
    elif args.command == 'search':
        run_search(args)
    else:
        parser.print_help()


def run_extract(args):
    """Run extraction command"""
    try:
        from suno_cli import cmd_extract
        cmd_extract(args)
    except ImportError:
        # Fall back to direct implementation
        from suno_extractor import SunoExtractor
        from suno_core import get_database
        
        print(f"🎵 Extracting from {args.browser} on port {args.port}...")
        
        extractor = SunoExtractor(output_dir=args.output, browser=args.browser)
        extractor.connect_to_existing_browser(debug_port=args.port)
        
        tabs = args.tabs.split(',') if args.tabs else ['creations']
        formats = args.formats.split(',') if args.formats else ['md', 'json', 'csv']
        
        output_files = extractor.run_extraction(
            extract_details=not args.fast,
            save_formats=formats,
            tabs=tabs,
            incremental=not args.full
        )
        
        print(f"✓ Extraction complete!")
        for fmt, path in output_files.items():
            print(f"  {fmt}: {path}")


def run_download(args):
    """Run download command"""
    from suno_downloader import SunoDownloader
    
    print(f"📥 Downloading from {args.json_file}...")
    
    downloader = SunoDownloader(args.output)
    results = downloader.download_from_json(
        args.json_file, 
        format=args.format,
        max_workers=args.workers
    )
    
    print(f"✓ Download complete: {results.get('success', 0)} files")


def run_web(args):
    """Run web dashboard"""
    from suno_web import run_server
    
    print(f"🌐 Starting web dashboard at http://{args.host}:{args.port}")
    run_server(host=args.host, port=args.port, debug=args.debug)


def run_play(args):
    """Run music player"""
    from suno_player import SunoPlayer, PlayerUI
    
    player = SunoPlayer(audio_dir=args.dir)
    
    if args.json_file:
        player.load_playlist_from_json(args.json_file)
    else:
        player.load_playlist_from_directory()
    
    if args.shuffle:
        player.shuffle = True
    
    print(f"🎵 Starting player with {len(player.playlist)} songs...")
    
    ui = PlayerUI(player)
    ui.run()


def run_stats(args):
    """Show library statistics"""
    try:
        from rich.console import Console
        from rich.table import Table
        console = Console()
        use_rich = True
    except ImportError:
        use_rich = False
    
    if args.json_file:
        from suno_downloader import CollectionAnalyzer
        analyzer = CollectionAnalyzer(args.json_file)
        stats = analyzer.get_statistics()
    else:
        from suno_core import get_database
        db = get_database()
        stats = db.get_statistics()
    
    if use_rich:
        table = Table(title="📊 Library Statistics")
        table.add_column("Metric", style="cyan")
        table.add_column("Value", style="green")
        
        table.add_row("Total Songs", str(stats.get('total_songs', 0)))
        table.add_row("Total Duration", stats.get('total_duration_formatted', 'N/A'))
        table.add_row("With Lyrics", str(stats.get('with_lyrics', 0)))
        table.add_row("With Description", str(stats.get('with_description', 0)))
        
        console.print(table)
    else:
        print("\n📊 Library Statistics")
        print(f"  Total Songs: {stats.get('total_songs', 0)}")
        print(f"  Total Duration: {stats.get('total_duration_formatted', 'N/A')}")
        print(f"  With Lyrics: {stats.get('with_lyrics', 0)}")


def run_search(args):
    """Search the library"""
    from suno_core import get_database
    
    db = get_database()
    query = args.query or ''
    
    if query:
        results = db.search_songs(query, limit=args.limit)
    else:
        results = db.get_all_songs()[:args.limit]
    
    if not results:
        print("No songs found.")
        return
    
    print(f"\n🔍 Found {len(results)} songs:\n")
    for i, song in enumerate(results, 1):
        title = song.get('title', 'Unknown')
        artist = song.get('artist', 'Suno AI')
        duration = song.get('duration', '--:--')
        print(f"  {i}. {title} - {artist} [{duration}]")


if __name__ == '__main__':
    main()

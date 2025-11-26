#!/usr/bin/env python3
"""
Suno CLI - Rich Command Line Interface for Suno Extractor
Full-featured CLI with beautiful formatting
"""

import argparse
import json
import os
import sys
from pathlib import Path
from datetime import datetime

# Rich library for beautiful terminal output
try:
    from rich.console import Console
    from rich.table import Table
    from rich.panel import Panel
    from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn
    from rich.tree import Tree
    from rich.markdown import Markdown
    from rich.prompt import Prompt, Confirm
    from rich import print as rprint
    from rich.live import Live
    from rich.layout import Layout
    RICH_AVAILABLE = True
except ImportError:
    RICH_AVAILABLE = False
    print("Warning: 'rich' library not installed. Install with: pip install rich")

# Local imports
try:
    from suno_extractor import SunoExtractor
    from suno_downloader import SunoDownloader, PlaylistManager, CollectionAnalyzer
except ImportError as e:
    print(f"Import error: {e}")


console = Console() if RICH_AVAILABLE else None


def print_banner():
    """Print application banner"""
    banner = """
╔══════════════════════════════════════════════════════════════╗
║  🎵 SUNO EXTRACTOR PRO - Music Library Manager               ║
║  Extract • Download • Organize • Play                        ║
╚══════════════════════════════════════════════════════════════╝
    """
    if RICH_AVAILABLE:
        console.print(Panel(banner, style="bold cyan"))
    else:
        print(banner)


def cmd_extract(args):
    """Extract songs from Suno library"""
    print_banner()
    
    if RICH_AVAILABLE:
        console.print("\n[bold blue]📥 EXTRACTION MODE[/bold blue]")
        console.print(f"Browser: {args.browser}")
        console.print(f"Port: {args.port}")
        console.print(f"Output: {args.output}")
    else:
        print(f"\nExtraction Mode - Browser: {args.browser}, Port: {args.port}")
    
    extractor = SunoExtractor(
        output_dir=args.output,
        browser=args.browser
    )
    
    try:
        extractor.connect_to_existing_browser(debug_port=args.port)
        
        tabs = args.tabs.split(',') if args.tabs else ['creations']
        formats = args.formats.split(',') if args.formats else ['md', 'json', 'csv']
        
        output_files = extractor.run_extraction(
            extract_details=not args.fast,
            save_formats=formats,
            tabs=tabs,
            exclude_disliked=True
        )
        
        if RICH_AVAILABLE:
            console.print("\n[bold green]✓ Extraction Complete![/bold green]")
            for fmt, path in output_files.items():
                console.print(f"  {fmt}: {path}")
        else:
            print("\nExtraction Complete!")
            for fmt, path in output_files.items():
                print(f"  {fmt}: {path}")
                
    except Exception as e:
        if RICH_AVAILABLE:
            console.print(f"[bold red]✗ Error: {e}[/bold red]")
        else:
            print(f"Error: {e}")
        sys.exit(1)


def cmd_download(args):
    """Download audio files from collection"""
    print_banner()
    
    if not args.json_file:
        if RICH_AVAILABLE:
            console.print("[red]Error: Please specify a JSON file with --json-file[/red]")
        else:
            print("Error: Please specify a JSON file with --json-file")
        sys.exit(1)
    
    if RICH_AVAILABLE:
        console.print(f"\n[bold blue]📥 DOWNLOAD MODE[/bold blue]")
        console.print(f"Source: {args.json_file}")
        console.print(f"Format: {args.format}")
        console.print(f"Output: {args.output}")
    
    downloader = SunoDownloader(args.output)
    
    if RICH_AVAILABLE:
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
            console=console
        ) as progress:
            task = progress.add_task("Downloading...", total=100)
            results = downloader.download_from_json(args.json_file, args.format)
            progress.update(task, completed=100)
    else:
        results = downloader.download_from_json(args.json_file, args.format)
    
    # Summary
    if RICH_AVAILABLE:
        table = Table(title="Download Results")
        table.add_column("Status", style="cyan")
        table.add_column("Count", justify="right")
        table.add_row("✓ Success", str(len(results['success'])))
        table.add_row("✗ Failed", str(len(results['failed'])))
        console.print(table)
    else:
        print(f"\nSuccess: {len(results['success'])}")
        print(f"Failed: {len(results['failed'])}")


def cmd_stats(args):
    """Show collection statistics"""
    print_banner()
    
    if not args.json_file:
        # Try to find most recent JSON
        json_files = list(Path(args.input_dir).glob("*.json"))
        if not json_files:
            print("No JSON files found. Please specify with --json-file")
            sys.exit(1)
        args.json_file = str(max(json_files, key=os.path.getmtime))
    
    analyzer = CollectionAnalyzer(args.json_file)
    stats = analyzer.get_statistics()
    
    if RICH_AVAILABLE:
        console.print(f"\n[bold blue]📊 COLLECTION STATISTICS[/bold blue]")
        console.print(f"Source: {args.json_file}\n")
        
        # Main stats table
        table = Table(title="Overview")
        table.add_column("Metric", style="cyan")
        table.add_column("Value", justify="right", style="green")
        
        table.add_row("Total Songs", str(stats['total_songs']))
        table.add_row("Total Duration", stats['total_duration_formatted'])
        table.add_row("Avg Duration", f"{int(stats['avg_duration_seconds'])}s")
        table.add_row("With Lyrics", str(stats['with_lyrics']))
        table.add_row("With Description", str(stats['with_description']))
        
        console.print(table)
        
        # Tags distribution
        if stats['tags_distribution']:
            console.print("\n[bold]Tags Distribution:[/bold]")
            tag_table = Table()
            tag_table.add_column("Tag")
            tag_table.add_column("Count", justify="right")
            
            sorted_tags = sorted(stats['tags_distribution'].items(), 
                                key=lambda x: x[1], reverse=True)[:10]
            for tag, count in sorted_tags:
                tag_table.add_row(tag, str(count))
            console.print(tag_table)
        
        # Source tabs
        if stats['source_tab_distribution']:
            console.print("\n[bold]Source Tabs:[/bold]")
            for tab, count in stats['source_tab_distribution'].items():
                console.print(f"  {tab}: {count}")
    else:
        print(f"\nCollection Statistics: {args.json_file}")
        print(f"Total Songs: {stats['total_songs']}")
        print(f"Total Duration: {stats['total_duration_formatted']}")


def cmd_search(args):
    """Search collection"""
    print_banner()
    
    if not args.json_file:
        json_files = list(Path(args.input_dir).glob("*.json"))
        if not json_files:
            print("No JSON files found")
            sys.exit(1)
        args.json_file = str(max(json_files, key=os.path.getmtime))
    
    analyzer = CollectionAnalyzer(args.json_file)
    results = analyzer.search(args.query)
    
    if RICH_AVAILABLE:
        console.print(f"\n[bold blue]🔍 SEARCH RESULTS[/bold blue]")
        console.print(f"Query: '{args.query}'")
        console.print(f"Found: {len(results)} songs\n")
        
        if results:
            table = Table()
            table.add_column("#", style="dim")
            table.add_column("Title", style="cyan")
            table.add_column("Duration")
            table.add_column("Tags")
            
            for i, song in enumerate(results[:20], 1):
                tags = ', '.join(song.get('tags', [])[:3])
                table.add_row(
                    str(i),
                    song.get('title', 'Unknown')[:40],
                    song.get('duration', ''),
                    tags
                )
            console.print(table)
            
            if len(results) > 20:
                console.print(f"\n...and {len(results) - 20} more")
    else:
        print(f"\nSearch: '{args.query}' - Found {len(results)}")
        for song in results[:10]:
            print(f"  - {song.get('title', 'Unknown')}")


def cmd_playlist(args):
    """Create playlist from collection"""
    print_banner()
    
    if not args.json_file:
        json_files = list(Path(args.input_dir).glob("*.json"))
        if not json_files:
            print("No JSON files found")
            sys.exit(1)
        args.json_file = str(max(json_files, key=os.path.getmtime))
    
    playlist_mgr = PlaylistManager(args.output)
    
    name = args.name or f"suno_playlist_{datetime.now().strftime('%Y%m%d')}"
    
    playlist_path = playlist_mgr.create_m3u_from_json(
        args.json_file,
        args.audio_dir,
        name
    )
    
    if RICH_AVAILABLE:
        console.print(f"\n[bold green]✓ Playlist Created![/bold green]")
        console.print(f"Path: {playlist_path}")
    else:
        print(f"\nPlaylist created: {playlist_path}")


def cmd_list(args):
    """List songs in collection"""
    print_banner()
    
    if not args.json_file:
        json_files = list(Path(args.input_dir).glob("*.json"))
        if not json_files:
            print("No JSON files found")
            sys.exit(1)
        args.json_file = str(max(json_files, key=os.path.getmtime))
    
    with open(args.json_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    songs = data.get('songs', [])
    
    if RICH_AVAILABLE:
        console.print(f"\n[bold blue]📋 SONG LIST[/bold blue]")
        console.print(f"Total: {len(songs)} songs\n")
        
        table = Table(show_header=True, header_style="bold")
        table.add_column("#", style="dim", width=4)
        table.add_column("Title", min_width=30)
        table.add_column("Duration", width=8)
        table.add_column("Tags", max_width=20)
        table.add_column("Tab", width=10)
        
        start = (args.page - 1) * args.per_page
        end = start + args.per_page
        
        for song in songs[start:end]:
            tags = ', '.join(song.get('tags', [])[:2])
            table.add_row(
                str(song.get('index', '-')),
                song.get('title', 'Unknown')[:40],
                song.get('duration', '-'),
                tags,
                song.get('source_tab', '-')
            )
        
        console.print(table)
        console.print(f"\nPage {args.page} of {(len(songs) + args.per_page - 1) // args.per_page}")
    else:
        for song in songs[:20]:
            print(f"{song.get('index')}: {song.get('title')}")


def cmd_interactive(args):
    """Interactive mode with menu"""
    print_banner()
    
    if not RICH_AVAILABLE:
        print("Interactive mode requires 'rich' library")
        sys.exit(1)
    
    while True:
        console.print("\n[bold cyan]MAIN MENU[/bold cyan]")
        console.print("1. Extract from Suno")
        console.print("2. Download audio files")
        console.print("3. View statistics")
        console.print("4. Search collection")
        console.print("5. Create playlist")
        console.print("6. List songs")
        console.print("0. Exit")
        
        choice = Prompt.ask("\nSelect option", choices=["0", "1", "2", "3", "4", "5", "6"])
        
        if choice == "0":
            console.print("[yellow]Goodbye![/yellow]")
            break
        elif choice == "1":
            # Extraction submenu
            browser = Prompt.ask("Browser", default="chrome")
            port = Prompt.ask("Debug port", default="9222")
            args.browser = browser
            args.port = int(port)
            args.output = "suno_songs"
            args.tabs = "creations"
            args.formats = "md,json,csv"
            args.fast = False
            cmd_extract(args)
        elif choice == "2":
            json_file = Prompt.ask("JSON file path", 
                                   default="suno_songs/suno_liked_songs_latest.json")
            args.json_file = json_file
            args.format = "mp3"
            args.output = "suno_downloads"
            cmd_download(args)
        elif choice == "3":
            args.input_dir = "suno_songs"
            args.json_file = None
            cmd_stats(args)
        elif choice == "4":
            query = Prompt.ask("Search query")
            args.query = query
            args.input_dir = "suno_songs"
            args.json_file = None
            cmd_search(args)
        elif choice == "5":
            args.input_dir = "suno_songs"
            args.json_file = None
            args.output = "suno_playlists"
            args.audio_dir = "suno_downloads"
            args.name = None
            cmd_playlist(args)
        elif choice == "6":
            args.input_dir = "suno_songs"
            args.json_file = None
            args.page = 1
            args.per_page = 20
            cmd_list(args)


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description="Suno Extractor Pro - CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  suno_cli.py extract --browser chrome --port 9222
  suno_cli.py download --json-file suno_songs/collection.json
  suno_cli.py stats --json-file suno_songs/collection.json
  suno_cli.py search "electronic" --json-file suno_songs/collection.json
  suno_cli.py playlist --name "my_favorites"
  suno_cli.py interactive
        """
    )
    
    subparsers = parser.add_subparsers(dest='command', help='Commands')
    
    # Extract command
    extract_parser = subparsers.add_parser('extract', help='Extract songs from Suno')
    extract_parser.add_argument('--browser', default='chrome', choices=['chrome', 'firefox'])
    extract_parser.add_argument('--port', type=int, default=9222)
    extract_parser.add_argument('--output', default='suno_songs')
    extract_parser.add_argument('--tabs', default='creations', 
                               help='Comma-separated tabs: creations,likes')
    extract_parser.add_argument('--formats', default='md,json,csv',
                               help='Comma-separated formats: md,json,csv')
    extract_parser.add_argument('--fast', action='store_true',
                               help='Skip detailed extraction')
    
    # Download command
    download_parser = subparsers.add_parser('download', help='Download audio files')
    download_parser.add_argument('--json-file', required=True)
    download_parser.add_argument('--format', default='mp3', choices=['mp3', 'm4a', 'wav'])
    download_parser.add_argument('--output', default='suno_downloads')
    
    # Stats command
    stats_parser = subparsers.add_parser('stats', help='Show statistics')
    stats_parser.add_argument('--json-file')
    stats_parser.add_argument('--input-dir', default='suno_songs')
    
    # Search command
    search_parser = subparsers.add_parser('search', help='Search collection')
    search_parser.add_argument('query', help='Search query')
    search_parser.add_argument('--json-file')
    search_parser.add_argument('--input-dir', default='suno_songs')
    
    # Playlist command
    playlist_parser = subparsers.add_parser('playlist', help='Create playlist')
    playlist_parser.add_argument('--json-file')
    playlist_parser.add_argument('--input-dir', default='suno_songs')
    playlist_parser.add_argument('--output', default='suno_playlists')
    playlist_parser.add_argument('--audio-dir', default='suno_downloads')
    playlist_parser.add_argument('--name')
    
    # List command
    list_parser = subparsers.add_parser('list', help='List songs')
    list_parser.add_argument('--json-file')
    list_parser.add_argument('--input-dir', default='suno_songs')
    list_parser.add_argument('--page', type=int, default=1)
    list_parser.add_argument('--per-page', type=int, default=20)
    
    # Interactive command
    subparsers.add_parser('interactive', help='Interactive mode')
    
    args = parser.parse_args()
    
    if args.command is None:
        parser.print_help()
        sys.exit(0)
    
    commands = {
        'extract': cmd_extract,
        'download': cmd_download,
        'stats': cmd_stats,
        'search': cmd_search,
        'playlist': cmd_playlist,
        'list': cmd_list,
        'interactive': cmd_interactive
    }
    
    if args.command in commands:
        commands[args.command](args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()

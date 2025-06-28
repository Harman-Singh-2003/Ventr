#!/usr/bin/env python3
"""
Command-line interface for managing the grid-based cache system.
"""

import argparse
import sys
from pathlib import Path

# Add project root to path for imports
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from crime_aware_routing.core.cached_network_builder import CachedNetworkBuilder


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Manage grid-based cache for crime-aware routing system",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Predownload cache for Toronto
  python cache_manager.py predownload
  
  # Force refresh existing cache
  python cache_manager.py predownload --force
  
  # Check cache statistics
  python cache_manager.py stats
  
  # Clear old cache entries (older than 60 days)
  python cache_manager.py clear --older-than 60
  
  # Clear all cache
  python cache_manager.py clear --all
  
  # Test cache with sample route
  python cache_manager.py test
        """
    )
    
    parser.add_argument(
        '--cache-dir', 
        default="crime_aware_routing/cache",
        help="Cache directory (default: crime_aware_routing/cache)"
    )
    
    parser.add_argument(
        '--precision', 
        type=int, 
        default=6,
        help="Geohash precision level (default: 6, ~1.2km cells)"
    )
    
    subparsers = parser.add_subparsers(dest='command', help='Available commands')
    
    # Predownload command
    predownload_parser = subparsers.add_parser(
        'predownload', 
        help='Predownload map data for Toronto area'
    )
    predownload_parser.add_argument(
        '--force', 
        action='store_true',
        help='Force re-download existing cache entries'
    )
    
    # Stats command
    subparsers.add_parser('stats', help='Show cache statistics')
    
    # Clear command
    clear_parser = subparsers.add_parser('clear', help='Clear cache entries')
    clear_group = clear_parser.add_mutually_exclusive_group(required=True)
    clear_group.add_argument(
        '--older-than', 
        type=int,
        help='Clear entries older than N days'
    )
    clear_group.add_argument(
        '--all', 
        action='store_true',
        help='Clear all cache entries'
    )
    
    # Test command
    test_parser = subparsers.add_parser('test', help='Test cache with sample routes')
    test_parser.add_argument(
        '--no-cache', 
        action='store_true',
        help='Test without cache for comparison'
    )
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return
    
    # Initialize cache builder
    builder = CachedNetworkBuilder(args.cache_dir, args.precision)
    
    try:
        if args.command == 'predownload':
            print(f"Starting predownload (precision: {args.precision}, force: {args.force})")
            builder.predownload_cache(force_refresh=args.force)
            
        elif args.command == 'stats':
            print("Cache Statistics:")
            print("=" * 50)
            builder.get_cache_stats()
            
        elif args.command == 'clear':
            if args.all:
                print("Clearing all cache entries...")
                builder.clear_cache()
            else:
                print(f"Clearing cache entries older than {args.older_than} days...")
                builder.clear_cache(older_than_days=args.older_than)
                
        elif args.command == 'test':
            test_routes(builder, use_cache=not args.no_cache)
            
    except KeyboardInterrupt:
        print("\n⚠ Operation cancelled by user")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Error: {e}")
        sys.exit(1)


def test_routes(builder: CachedNetworkBuilder, use_cache: bool = True):
    """Test the cache system with sample Toronto routes."""
    print(f"Testing cache system (cache {'enabled' if use_cache else 'disabled'})...")
    print("=" * 60)
    
    # Sample Toronto routes for testing
    test_routes = [
        {
            'name': 'Downtown Core',
            'start': (43.6426, -79.3871),  # Financial District
            'end': (43.6544, -79.3807)     # Eaton Centre area
        },
        {
            'name': 'University Avenue',
            'start': (43.6629, -79.3957),  # Queen's Park
            'end': (43.6426, -79.3871)     # Union Station area
        },
        {
            'name': 'Harbourfront',
            'start': (43.6415, -79.3871),  # Union Station
            'end': (43.6385, -79.3755)     # Harbourfront Centre
        },
        {
            'name': 'Cross-town Route',
            'start': (43.6696, -79.3926),  # Spadina/Bloor
            'end': (43.6629, -79.4136)     # High Park area
        }
    ]
    
    import time
    
    for i, route in enumerate(test_routes, 1):
        print(f"\nTest {i}/{len(test_routes)}: {route['name']}")
        print(f"Route: {route['start']} → {route['end']}")
        
        start_time = time.time()
        
        try:
            network = builder.build_network(
                route['start'], 
                route['end'], 
                prefer_cache=use_cache
            )
            
            end_time = time.time()
            duration = end_time - start_time
            
            print(f"✓ Success: {len(network.nodes)} nodes, {len(network.edges)} edges")
            print(f"  Time: {duration:.2f}s")
            
        except Exception as e:
            end_time = time.time()
            duration = end_time - start_time
            print(f"❌ Failed: {e}")
            print(f"  Time: {duration:.2f}s")
    
    print(f"\nTest complete!")


if __name__ == '__main__':
    main() 
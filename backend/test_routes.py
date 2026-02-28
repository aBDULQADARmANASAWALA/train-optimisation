#!/usr/bin/env python
"""Test script to verify routes are loading correctly."""

import sys
sys.path.insert(0, '.')

try:
    from app.apis.routes import router
    
    print(f"✓ Routes module loaded successfully")
    print(f"✓ Total routes: {len(router.routes)}")
    
    # List all routes
    print("\nRegistered routes:")
    for route in router.routes:
        if hasattr(route, 'path') and hasattr(route, 'methods'):
            methods = ', '.join(route.methods) if route.methods else 'N/A'
            print(f"  {methods:6} {route.path}")
    
    # Check for conflicts endpoint
    conflict_routes = [r for r in router.routes if hasattr(r, 'path') and 'conflict' in r.path.lower()]
    
    if conflict_routes:
        print(f"\n✓ Conflicts endpoint found: {conflict_routes[0].path}")
    else:
        print("\n✗ Conflicts endpoint NOT found!")
        
except Exception as e:
    print(f"✗ Error loading routes: {e}")
    import traceback
    traceback.print_exc()

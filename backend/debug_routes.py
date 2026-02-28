#!/usr/bin/env python
"""Debug script to check route registration."""

import sys
import traceback

sys.path.insert(0, '.')

try:
    print("=" * 60)
    print("IMPORTING MAIN APP")
    print("=" * 60)
    
    from app.main import app
    
    print(f"\n✓ App imported successfully")
    print(f"✓ Total routes in app: {len(app.routes)}")
    
    # Check all routes
    print("\n" + "=" * 60)
    print("ALL REGISTERED ROUTES")
    print("=" * 60)
    
    for route in app.routes:
        if hasattr(route, 'path') and hasattr(route, 'methods'):
            methods = ', '.join(route.methods) if route.methods else 'N/A'
            print(f"{methods:10} {route.path}")
    
    # Check specifically for conflicts endpoint
    print("\n" + "=" * 60)
    print("CHECKING FOR CONFLICTS ENDPOINT")
    print("=" * 60)
    
    conflict_routes = [r for r in app.routes if hasattr(r, 'path') and 'conflict' in r.path.lower()]
    
    if conflict_routes:
        print(f"✓ FOUND: {len(conflict_routes)} conflict route(s)")
        for r in conflict_routes:
            print(f"  - {r.path}")
    else:
        print("✗ NOT FOUND: No conflict routes registered")
        
        # Check if it's in the router module
        print("\nChecking router module directly...")
        from app.apis.routes import router
        router_conflict_routes = [r for r in router.routes if hasattr(r, 'path') and 'conflict' in r.path.lower()]
        
        if router_conflict_routes:
            print(f"✓ Found in router module: {router_conflict_routes[0].path}")
            print("✗ ERROR: Route exists in router but not in app!")
            print("  This indicates a router registration issue.")
        else:
            print("✗ Not found in router module either")
            
except Exception as e:
    print(f"\n✗ ERROR: {e}")
    print("\nFull traceback:")
    traceback.print_exc()

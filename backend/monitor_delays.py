import requests
import time

print("Monitoring delays for 20 seconds...")
print("=" * 60)

for i in range(4):
    try:
        r = requests.get('http://localhost:8010/api/v1/state/live')
        data = r.json()
        
        print(f"\nTime: {i*5}s")
        print(f"  Conflicts: {data['current_conflicts']}")
        print(f"  Active trains: {data['active_trains']}")
        
        # Check individual train delays
        delayed_trains = [t for t in data['trains'] if t.get('accumulated_delay_minutes', 0) > 5]
        print(f"  Trains with >5min delay: {len(delayed_trains)}")
        
        if delayed_trains:
            for t in delayed_trains[:3]:
                print(f"    - {t['train_number']}: {t['accumulated_delay_minutes']:.1f}min")
        
        if i < 3:
            time.sleep(5)
            
    except Exception as e:
        print(f"Error: {e}")
        break

print("\n" + "=" * 60)
print("Monitoring complete")

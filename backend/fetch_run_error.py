import urllib.request
import json
try:
    data = json.dumps({"include_predictions": True}).encode('utf-8')
    req = urllib.request.Request('http://localhost:8010/api/v1/optimization/run', data=data,
                                 headers={'Content-Type': 'application/json'})
    with urllib.request.urlopen(req) as response:
        with open('error_out.txt', 'w') as f:
            f.write(response.read().decode())
except urllib.error.HTTPError as e:
    with open('error_out.txt', 'w') as f:
        f.write(e.read().decode())
except Exception as e:
    with open('error_out.txt', 'w') as f:
        f.write(str(e))

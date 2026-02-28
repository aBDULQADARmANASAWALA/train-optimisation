import urllib.request
try:
    urllib.request.urlopen('http://localhost:8010/api/v1/optimization/history')
except Exception as e:
    print(e.read().decode())

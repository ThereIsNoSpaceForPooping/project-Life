import httpx
for name, url in [
    ('MCP', 'http://localhost:8001/'),
    ('A2A', 'http://localhost:8002/health'),
    ('Backend', 'http://localhost:8005/health'),
    ('Frontend', 'http://localhost:3002/'),
]:
    try:
        r = httpx.get(url, timeout=5.0)
        print(f'  [OK]   {name:10s} {url} -> {r.status_code}')
    except Exception as e:
        print(f'  [FAIL] {name:10s} {url} -> {type(e).__name__}: {e}')

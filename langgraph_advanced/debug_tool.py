import httpx
url = 'http://localhost:8005/chat?mode=master&stream=true'
body = {'message': 'translate: apple', 'conversation_id': 'debug-001'}
print('Sending request...')
with httpx.stream('POST', url, json=body, timeout=60.0) as r:
    ct = r.headers.get('content-type', 'N/A')
    print(f'Status: {r.status_code}, Content-Type: {ct}')
    cnt = 0
    tool_cnt = 0
    step_cnt = 0
    all_events = []
    for line in r.iter_lines():
        if line.startswith('data: '):
            data = line[6:]
            all_events.append(data)
            if 'ToolCall' in data:
                tool_cnt += 1
                print(f'TOOL EVENT #{tool_cnt}: {data[:200]}')
            elif 'StepStarted' in data:
                step_cnt += 1
            elif cnt < 5:
                print(f'EVENT: {data[:150]}')
                cnt += 1
    print(f'Total: {len(all_events)} events, {tool_cnt} tool events, {step_cnt} step events')

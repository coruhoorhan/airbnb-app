import json
from datetime import datetime, timezone

with open('agent_tasks.json', 'r') as f:
    data = json.load(f)

for task in data['tasks']:
    if task['id'] == 'feat-06-push-notification-engine':
        task['status'] = 'done'
        break

data['updated_at'] = datetime.now(timezone.utc).timestamp()

with open('agent_tasks.json', 'w') as f:
    json.dump(data, f, indent=2)

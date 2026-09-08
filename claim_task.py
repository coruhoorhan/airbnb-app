import json
import datetime

with open('agent_tasks.json', 'r') as f:
    data = json.load(f)

for task in data['tasks']:
    if task.get('status') == 'todo' and task.get('claimed_by') not in ['human', 'veyyon']:
        task['status'] = 'in_progress'
        task['claimed_by'] = 'jules'
        task['claimed_at'] = datetime.datetime.now(datetime.timezone.utc).isoformat()
        break

with open('agent_tasks.json', 'w') as f:
    json.dump(data, f, indent=2)

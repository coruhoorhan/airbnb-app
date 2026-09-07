import json

with open('agent_tasks.json', 'r') as f:
    data = json.load(f)

for task in data['tasks']:
    if task.get('id') == 'feat-06-push-notification-engine':
        print(json.dumps(task, indent=2))
        break

import json

with open('agent_tasks.json', 'r') as f:
    data = json.load(f)

for task in data['tasks']:
    if task.get('status') == 'todo' and task.get('claimed_by') not in ['human', 'veyyon']:
        print(json.dumps(task, indent=2))
        break

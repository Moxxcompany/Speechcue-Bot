def validate_edges(data):
    nodes = data['nodes']
    edges = data['edges']

    source_ids = {edge['source'] for edge in edges}
    target_ids = {edge['target'] for edge in edges}
    missing_sources = []
    missing_targets = []

    for node in nodes:
        node_id = node['id']
        node_name = node['data']['name']
        node_type = node['type']
        node_data = node['data']

        if node_type == 'End Call':
            if node_id not in target_ids:
                missing_targets.append(node_name)

        elif node_data.get('isStart', False):
            if node_id not in source_ids:
                missing_sources.append(node_name)

        else:
            if node_id not in source_ids:
                missing_sources.append(node_name)

            if node_id not in target_ids:
                missing_targets.append(node_name)

    # Handle missing sources and targets
    if missing_sources or missing_targets:
        if missing_sources:
            print(
                f"The following nodes do not have any outgoing connections to other nodes: {', '.join(missing_sources)}")
        else:
            print("No nodes are missing incoming connections.")

        if missing_targets:
            print(f"The following nodes do not connect to any other nodes: {', '.join(missing_targets)}")
        else:
            print("No nodes are missing incoming connections.")

        return {
            'missing_sources': missing_sources,
            'missing_targets': missing_targets,
            'valid': False
        }

    print("All nodes are properly connected.")
    return {'valid': True}
pathway_id = '2b6bfe4b-4ca4-4f5d-8400-9427e249694e'

import requests

url = f"https://api.bland.ai/v1/convo_pathway/{pathway_id}"

headers = {"authorization": "sk-wvo26msfcc3qt0i7046jccgyo54tk7ow96fai01yrw0bmcjn8rbk8ld47bug8rww69"}

response = requests.request("GET", url, headers=headers)

print(response.json())

print(response.text)
data = response.json()


print(data)
# Run validation
result = validate_edges(data)
print(result)

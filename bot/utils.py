import json
from typing import Tuple, List, Dict, Any


def add_node(data: str, new_node: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Adds a new node to the existing pathway data.

    Args:
        data: A JSON string representing the existing pathway data.
        new_node: A dictionary representing the new node to be added.

    Returns:
        A list of nodes including the new node.
    """
    data = json.loads(data)
    nodes = data['pathway_data'].get('nodes', [])
    nodes.append(new_node)
    return nodes


def get_pathway_data(data: str) -> Tuple[str, str]:
    """
    Extracts the pathway name and description from the pathway data.

    Args:
        data: A JSON string representing the pathway data.

    Returns:
        A tuple containing the pathway name and description.
    """
    data = json.loads(data)
    name = data["pathway_data"].get("name")
    description = data["pathway_data"].get("description")
    return name, description


def get_pathway_payload(data: str) -> Dict[str, Any]:
    """
    Extracts the pathway payload from the pathway data.

    Args:
        data: A JSON string representing the pathway data.

    Returns:
        A dictionary representing the pathway payload.
    """
    data = json.loads(data)
    payload = data.get("pathway_data")
    return payload

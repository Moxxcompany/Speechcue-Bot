import json
import requests
from django.conf import settings
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt

from TelegramBot.constants import base_url, invalid_data, error
from bot.models import Pathways
from bot.utils import add_node, get_pathway_data


def handle_delete_flow(pathway_id: int) -> tuple[dict, int]:
    """
        Handles the deletion of a pathway via Bland.ai API.

        Args:
            pathway_id (int): The ID of the pathway to delete.

        Returns:
            tuple: A tuple containing:
                - A dictionary with either a success message or error message.
                - The HTTP status code.
        """
    if not pathway_id:
        return {'error': invalid_data}, 400

    endpoint = f"{base_url}/v1/convo_pathway/{pathway_id}"

    headers = {
        'Authorization': f'{settings.BLAND_API_KEY}',
        'Content-Type': 'application/json'
    }

    response = requests.delete(endpoint, headers=headers)
    if response.status_code != 200:
        return {'error': response.text}, response.status_code
    Pathways.objects.get(pathway_id=str(pathway_id)).delete()
    return {'Deleted': True}, response.status_code


def handle_create_flow(pathway_name: str, pathway_description: str, pathway_user_id: int) -> tuple:
    """
    Handles the creation of a pathway via Bland.ai API.

    Args:
        pathway_name (str): The name of the pathway.
        pathway_description (str): The description of the pathway.
        pathway_user_id (int): The user ID associated with the pathway.

    Returns:
        tuple: A tuple containing a dictionary with either a success message or error message,
               and an HTTP status code.
    """
    if not pathway_name or not pathway_description:
        return {'error': {invalid_data}}, 400

    endpoint = f"{base_url}/v1/convo_pathway/create"
    headers = {
        'Authorization': f'{settings.BLAND_API_KEY}',
        'Content-Type': 'application/json'
    }
    payload = {
        'name': pathway_name,
        'description': pathway_description,
    }

    response = requests.post(endpoint, json=payload, headers=headers)

    if response.status_code == 200:
        data = response.json()
        pathway_id = data.get('pathway_id')

        pathway_entry = Pathways.objects.create(
            pathway_id=pathway_id,
            pathway_name=pathway_name,
            pathway_user_id=pathway_user_id,
            pathway_description=pathway_description
        )

        return {'message': 'Pathway created successfully'}, 200
    else:
        return {{error}: response.json()}, 400


@csrf_exempt
def create_flow(request) -> JsonResponse:
    """
    Creates a new pathway based on POST request data.

    Args:
        request (HttpRequest): The HTTP request object.

    Returns:
        JsonResponse: A JSON response containing success or error message with corresponding HTTP status.
    """
    if request.method == 'POST':
        data = json.loads(request.body.decode('utf-8'))
        pathway_name = data.get('name')
        pathway_description = data.get('description')
        response_data, status = handle_create_flow(pathway_name, pathway_description)
        return JsonResponse(response_data, status=status)

    return JsonResponse({{error}: 'Invalid method'}, status=405)


def handle_end_call(pathway_id: int, node_id: int, prompt, node_name) -> requests.Response:
    pathway = Pathways.objects.get(pathway_id=pathway_id)
    node = {
        "id": node_id,
        "type": "End Call",
        "data": {
            "name": node_name,
            "prompt": prompt,
        }
    }
    pathway_name, pathway_description = get_pathway_data(pathway.pathway_payload)
    nodes = add_node(pathway.pathway_payload, new_node=node)
    data = {
        "name": pathway_name,
        "description": pathway_description,
        "nodes": nodes,
        "edges": []
    }
    response = handle_add_node(pathway_id, data)

    if response.status_code == 200:
        pathway_name, pathway_description = get_pathway_data(response.text)
        pathway = Pathways.objects.get(pathway_id=pathway_id)
        pathway.pathway_name = pathway_name
        pathway.pathway_description = pathway_description
        pathway.pathway_payload = response.text
        pathway.save()
    return response


def handle_dtmf_input_node(pathway_id: int, node_id: int, prompt, node_name) -> requests.Response:
    pathway = Pathways.objects.get(pathway_id=pathway_id)
    node = {
        "id": node_id,
        "type": "Default",
        "data": {
            "name": node_name,
            "prompt": prompt,
        }
    }
    pathway_name, pathway_description = get_pathway_data(pathway.pathway_payload)
    nodes = add_node(pathway.pathway_payload, new_node=node)
    data = {
        "name": pathway_name,
        "description": pathway_description,
        "nodes": nodes,
        "edges": []
    }
    response = handle_add_node(pathway_id, data)

    if response.status_code == 200:
        pathway_name, pathway_description = get_pathway_data(response.text)
        pathway = Pathways.objects.get(pathway_id=pathway_id)
        pathway.pathway_name = pathway_name
        pathway.pathway_description = pathway_description
        pathway.pathway_payload = response.text
        pathway.save()
    return response


def play_message(pathway_id: int, node_name: str, node_text: str, node_id: int, voice_type: str, voice_gender: str,
                 language: str) -> requests.Response:
    """
    Handles the addition of 'playing message' node via Bland.ai API.
    Args:
        pathway_id: ID of the pathway to be updated with the node
        node_name: Name of the node to be added to the pathway
        node_text: Text of the node to be added to the pathway
        node_id: ID of the node to be added to the pathway
        voice_type: Type of the voice to be added to the pathway
        voice_gender: Gender of the voice to be added to the pathway
        language: Language of the voice to be added to the pathway

    Returns:
        response: A JSON response containing success or error message with corresponding HTTP status.
    """
    pathway = Pathways.objects.get(pathway_id=pathway_id)

    nodes = {
        "id": node_id,
        "type": "Default",
        "data": {
            "name": node_name,
            "text": node_text,
            "voice_type": voice_type,
            "voice_gender": voice_gender,
            "language": language
        }
    }
    pathway_name, pathway_description = get_pathway_data(pathway.pathway_payload)
    if pathway.pathway_payload:
        nodes = add_node(pathway.pathway_payload, new_node=nodes)

    else:
        nodes["data"]["isStart"] = True
        nodes = [nodes]
        pathway_name = pathway.pathway_name
        pathway_description = pathway.pathway_description

    data = {
        "name": pathway_name,
        "description": pathway_description,
        "nodes": nodes,
        "edges": []
    }
    response = handle_add_node(pathway_id, data)

    if response.status_code == 200:
        pathway_name, pathway_description = get_pathway_data(response.text)
        pathway = Pathways.objects.get(pathway_id=pathway_id)
        pathway.pathway_name = pathway_name
        pathway.pathway_description = pathway_description
        pathway.pathway_payload = response.text
        pathway.save()
    return response


# def handle_add_transfer_call_node(pathway_id:int ,transfer_number:str):
#     pathway = Pathways.objects.get(pathway_id=pathway_id)
#

def handle_add_node(pathway_id: int, data) -> requests.Response:
    """
       Handles the addition of a node to a pathway via Bland.ai API.

       Args:
          pathway_id: The ID of the pathway to update.
          data: The data to be passed as payload.

       Returns:
           JsonResponse: A JSON response containing success or error message with corresponding HTTP status.
       """
    endpoint = f"{base_url}/v1/convo_pathway/{pathway_id}"

    # Todo: complete this endpoint
    headers = {
        'Authorization': f'{settings.BLAND_API_KEY}',
        'Content-Type': 'application/json'
    }

    response = requests.post(endpoint, json=data, headers=headers)
    return response


def handle_view_flows() -> tuple:
    """
    Handles the retrieval of all pathways via Bland.ai API.

    Returns:
        tuple: A tuple containing either a list of pathways (as JSON data) and HTTP status code 200,
               or an error message dictionary and HTTP status code 400.
    """
    endpoint = f"{base_url}/v1/convo_pathway"
    headers = {
        'Authorization': f'{settings.BLAND_API_KEY}',
        'Content-Type': 'application/json'
    }

    response = requests.get(endpoint, headers=headers)
    if response.status_code == 200:
        pathways = response.json()
        return pathways, 200
    else:
        return {{error}: 'Failed to retrieve pathways'}, 400


@csrf_exempt
def view_flows(request) -> JsonResponse:
    """
    Retrieves all pathways via GET request.

    Args:
        request (HttpRequest): The HTTP request object.

    Returns:
        JsonResponse: A JSON response containing pathways data or error message with corresponding HTTP status.
    """
    if request.method == 'GET':
        response_data, status = handle_view_flows()

        return JsonResponse(response_data, status=status)

    return JsonResponse({{error}: 'Invalid method'}, status=405)


def handle_view_single_flow(pathway_id):
    """
       Handles the retrieval of a single flow via Bland.ai API.

       Returns:
           tuple: A tuple containing either a list of pathways (as JSON data) and HTTP status code 200,
                  or an error message dictionary and HTTP status code 400.
       """
    endpoint = f"{base_url}/v1/convo_pathway/{pathway_id}"
    headers = {
        'Authorization': f'{settings.BLAND_API_KEY}',
        'Content-Type': 'application/json'
    }

    response = requests.get(endpoint, headers=headers)
    if response.status_code == 200:
        pathway = response.json()
        return pathway, 200
    else:
        return {{error}: 'Failed to retrieve pathways'}, 400

import json
import requests
from django.conf import settings
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt

from TelegramBot.constants import base_url, invalid_data, error
from bot.models import Pathways


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
            pathway_user_id=pathway_user_id
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


def handle_add_node(pathway_id: int, node_name: str, pathway_name:str, pathway_description:str, pathway_type):
    """
       Handles the addition of a node to a pathway via Bland.ai API.

       Args:
           pathway_id (int): The ID of the pathway.
           node_name (str): The name of the node.
           pathway_name (str): The name of the pathway.
           pathway_description (str): The description of the pathway.
           pathway_type (str): The type of the pathway.

       Returns:
           JsonResponse: A JSON response containing success or error message with corresponding HTTP status.
       """
    endpoint = f"{base_url}/v1/convo_pathway/{pathway_id}"

    # Todo: complete this endpoint
    headers = {
        'Authorization': f'{settings.BLAND_API_KEY}',
        'Content-Type': 'application/json'
    }

    # data = {
    #     "name": f"{pathway_name}",
    #     "description": f"{pathway_description}",
    #     "nodes": [
    #         {
    #             "id": "1",
    #             "data": {
    #                 "name": "Start",
    #                 "text": "Hey there, how are you doing today?",
    #                 "isStart": True,
    #                 "globalPrompt": ""
    #             },
    #             "type": "Default"
    #         },
    #         {
    #             "id": "1b5a5e78-ed3f-4826-ba62-3967009ce2df",
    #             "data": {
    #                 "name": "New Node 1",
    #                 "text": "Placeholder instructions for agent to say",
    #                 "globalPrompt": ""
    #             },
    #             "type": "Default"
    #         }
    #     ],
    #     "edges": []
    # }
    # response = requests.post(endpoint, json=data, headers=headers)

    #
    # if response.status_code == 200:
    #     return JsonResponse({'message': 'Node added successfully'}, status=201)
    # else:
    #
    #     return JsonResponse({'error': f'Failed to add node. Status code: {response.status_code}'},
    #                         status=response.status_code)


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

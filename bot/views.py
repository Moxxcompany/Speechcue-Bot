import json

import requests
from django.conf import settings
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt


def handle_create_pathway(pathway_name: str, pathway_description: str) -> tuple:
    """
    Handles the creation of a pathway via Bland.ai API.

    Args:
        pathway_name (str): The name of the pathway.
        pathway_description (str): The description of the pathway.

    Returns:
        tuple: A tuple containing a dictionary with either a success message or error message,
               and an HTTP status code.
    """
    if not pathway_name or not pathway_description:
        return {'error': 'Invalid data'}, 400

    endpoint = 'https://api.bland.ai/v1/convo_pathway/create'
    headers = {
        'Authorization': f'{settings.BLAND_API_KEY}',
        'Content-Type': 'application/json'
    }
    payload = {
        'name': pathway_name,
        'description': pathway_description,
        # Add more fields as required by Bland.ai API
    }

    response = requests.post(endpoint, json=payload, headers=headers)

    if response.status_code == 200:
        return {'message': 'Pathway created successfully'}, 200
    else:
        return {'error': 'Failed to create pathway'}, 400


@csrf_exempt
def create_pathway(request) -> JsonResponse:
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

        response_data, status = handle_create_pathway(pathway_name, pathway_description)
        return JsonResponse(response_data, status=status)

    return JsonResponse({'error': 'Invalid method'}, status=405)


def handle_get_all_pathways() -> tuple:
    """
    Handles the retrieval of all pathways via Bland.ai API.

    Returns:
        tuple: A tuple containing either a list of pathways (as JSON data) and HTTP status code 200,
               or an error message dictionary and HTTP status code 400.
    """
    endpoint = 'https://api.bland.ai/v1/convo_pathway'
    headers = {
        'Authorization': f'{settings.BLAND_API_KEY}',
        'Content-Type': 'application/json'
    }

    response = requests.get(endpoint, headers=headers)

    if response.status_code == 200:
        pathways = response.json()
        return pathways, 200
    else:
        return {'error': 'Failed to retrieve pathways'}, 400


@csrf_exempt
def get_all_pathways(request) -> JsonResponse:
    """
    Retrieves all pathways via GET request.

    Args:
        request (HttpRequest): The HTTP request object.

    Returns:
        JsonResponse: A JSON response containing pathways data or error message with corresponding HTTP status.
    """
    if request.method == 'GET':
        response_data, status = handle_get_all_pathways()
        return JsonResponse(response_data, status=status)

    return JsonResponse({'error': 'Invalid method'}, status=405)

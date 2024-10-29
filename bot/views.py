import json
import logging

import requests
from django.conf import settings
from django.core.exceptions import ObjectDoesNotExist
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from TelegramBot.constants import base_url, invalid_data, error
from bot.models import Pathways, CallLogsTable, FeedbackDetails, FeedbackLogs, BatchCallLogs
from bot.utils import add_node, get_pathway_data, get_batch_id
from payment.models import UserSubscription, SubscriptionPlans, ManageFreePlanSingleIVRCall
from user.models import TelegramUser

logging.basicConfig(level= logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')


def empty_nodes(pathway_name, pathway_description, pathway_id):
    data = {
        "name": f"{pathway_name}",
        "description": f"{pathway_description}",
        "nodes": [],
        "edges": []
    }
    response = handle_add_node(pathway_id, data)
    return response


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

        return {'message': 'Pathway created successfully'}, 200, pathway_id
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

    # Load existing pathway data, nodes, and edges
    if pathway.pathway_payload:
        pathway_data = json.loads(pathway.pathway_payload).get('pathway_data', {})
        existing_nodes = pathway_data.get('nodes', [])
        existing_edges = pathway_data.get('edges', [])
    else:
        existing_nodes = []
        existing_edges = []

    # Define the new node
    node = {
        "id": f"{node_id}",
        "type": "End Call",
        "data": {
            "name": node_name,
            "prompt": prompt,
        }
    }

    nodes = add_node(pathway.pathway_payload, new_node=node)

    # Prepare the data with both nodes and existing edges
    data = {
        "name": pathway.pathway_name,
        "description": pathway.pathway_description,
        "nodes": nodes,
        "edges": existing_edges  # Keep the previous edges
    }

    response = handle_add_node(pathway_id, data)

    if response.status_code == 200:
        pathway.pathway_payload = response.text
        pathway.save()

    return response


def handle_menu_node(pathway_id: int, node_id: int, prompt, node_name, menu) -> requests.Response:
    pathway = Pathways.objects.get(pathway_id=pathway_id)

    # Load existing pathway data, nodes, and edges
    if pathway.pathway_payload:
        pathway_data = json.loads(pathway.pathway_payload).get('pathway_data', {})
        existing_nodes = pathway_data.get('nodes', [])
        existing_edges = pathway_data.get('edges', [])
    else:
        existing_nodes = []
        existing_edges = []

    # Define the new node
    node = {
        "id": f"{node_id}",
        "type": "Default",
        "data": {
            "name": node_name,
            "prompt": prompt,
        }
    }

    if existing_nodes:
        nodes = add_node(pathway.pathway_payload, new_node=node)
    else:
        node["data"]["isStart"] = True
        nodes = [node]

    # Prepare the data with both nodes and existing edges
    data = {
        "name": pathway.pathway_name,
        "description": pathway.pathway_description,
        "nodes": nodes,
        "edges": existing_edges  # Keep the previous edges
    }

    response = handle_add_node(pathway_id, data)

    if response.status_code == 200:
        pathway.pathway_payload = response.text
        pathway.save()

    return response



def handle_dtmf_input_node(pathway_id: int, node_id: int, prompt, node_name, message_type: str) -> requests.Response:
    pathway = Pathways.objects.get(pathway_id=pathway_id)

    # Load existing pathway data, nodes, and edges
    if pathway.pathway_payload:
        pathway_data = json.loads(pathway.pathway_payload).get('pathway_data', {})
        existing_nodes = pathway_data.get('nodes', [])
        existing_edges = pathway_data.get('edges', [])
    else:
        existing_nodes = []
        existing_edges = []

    # Determine node type and text based on message_type
    if message_type == "DTMF Input":
        node_type = 'Default'
        text = 'text'
    else:
        node_type = 'Transfer Call'
        text = "transferNumber"

    # Define the new node
    node = {
        "id": f"{node_id}",
        "type": node_type,
        "data": {
            "name": node_name,
            f"{text}": prompt,
        }
    }

    # Add global properties for Transfer Call node
    if node_type == 'Transfer Call' and not any(n['type'] == 'Transfer Call' for n in existing_nodes):
        node["data"]["isGlobal"] = True
        node["data"]["globalPrompt"] = "User says transfer call"

    if existing_nodes:
        nodes = add_node(pathway.pathway_payload, new_node=node)
    else:
        node["data"]["isStart"] = True
        nodes = [node]

    # Prepare the data with both nodes and existing edges
    pathway_name, pathway_description = get_pathway_data(pathway.pathway_payload)
    data = {
        "name": pathway_name,
        "description": pathway_description,
        "nodes": nodes,
        "edges": existing_edges  # Keep the previous edges
    }

    response = handle_add_node(pathway_id, data)

    if response.status_code == 200:
        pathway.pathway_payload = response.text
        pathway.save()

    return response


def play_message(pathway_id: int, node_name: str, node_text: str, node_id: int, voice: str,
                 language: str, message_type: str) -> requests.Response:
    """
    Handles the addition of 'playing message' node via Bland.ai API.
    Args:
        message_type: Type of node to be added
        pathway_id: ID of the pathway to be updated with the node
        node_name: Name of the node to be added to the pathway
        node_text: Text of the node to be added to the pathway
        node_id: ID of the node to be added to the pathway
        voice: Type of the voice to be added to the pathway
        language: Language of the voice to be added to the pathway
    Returns:
        response: A JSON response containing success or error message with corresponding HTTP status.
    """
    try:
        pathway = Pathways.objects.get(pathway_id=pathway_id)
    except ObjectDoesNotExist:
        return requests.Response(status=404, json={"error": "Pathway not found"})

    pathway_name = pathway.pathway_name
    pathway_description = pathway.pathway_description

    if message_type == 'End Call':
        node_type = 'End Call'
    else:
        node_type = 'Default'

    new_node = {
        "id": f"{node_id}",
        "type": f"{node_type}",
        "data": {
            "name": node_name,
            "text": node_text,
            "voice": voice,
            "language": language
        }
    }


    # Load existing nodes and edges from the pathway payload
    if pathway.pathway_payload:
        pathway_data = json.loads(pathway.pathway_payload).get('pathway_data', {})
        existing_nodes = pathway_data.get('nodes', [])
        existing_edges = pathway_data.get('edges', [])
    else:
        existing_nodes = []
        existing_edges = []

    is_start_found = any(node['data'].get('isStart') for node in existing_nodes)
    is_global_found = any(node['data'].get('isGlobal') for node in existing_nodes)

    if node_type == 'Default':
        if not is_start_found:
            new_node["data"]["isStart"] = True
        existing_nodes.append(new_node)
    elif node_type == 'End Call':
        if not is_global_found:
            new_node["data"]["isGlobal"] = True
            new_node["data"]["globalLabel"] = "User says end call"
        existing_nodes.append(new_node)

    # Prepare the data structure to be sent to the handle_add_node endpoint
    data = {
        "name": pathway_name,
        "description": pathway_description,
        "nodes": existing_nodes,
        "edges": existing_edges  # Maintain existing edges
    }
    print("Data: ",data)

    # Call the API to handle the addition of the node
    response = handle_add_node(pathway_id, data)
    if response.status_code == 200:
        pathway.pathway_payload = response.text
        pathway.save()

    return response


def question_type(pathway_id: int, node_name: str, node_text: str, node_id: int, voice: str,
                 language: str) -> requests.Response:

    try:
        pathway = Pathways.objects.get(pathway_id=pathway_id)
    except ObjectDoesNotExist:
        return requests.Response(status=404, json={"error": "Pathway not found"})

    pathway_name = pathway.pathway_name
    pathway_description = pathway.pathway_description

    new_node = {
        "id": f"{node_id}",
        "type": "Default",
        "data": {
            "name": node_name,
            "text": node_text,
            "voice": voice,
            "language": language,
            "extractVars": [
                [
                    f"{node_name}_user_input",
                    "string",
                    "This is the user answer to the asked question"
                ]
            ]
        },

    }
    if pathway.pathway_payload:
        pathway_data = json.loads(pathway.pathway_payload).get('pathway_data', {})
        existing_nodes = pathway_data.get('nodes', [])
        existing_edges = pathway_data.get('edges', [])
    else:
        existing_nodes = []
        existing_edges = []

    is_start_found = any(node['data'].get('isStart') for node in existing_nodes)
    if not is_start_found:
        new_node["data"]["isStart"] = True
    existing_nodes.append(new_node)

    data = {
        "name": pathway_name,
        "description": pathway_description,
        "nodes": existing_nodes,
        "edges": existing_edges
    }
    print("Data: ", data)

    response = handle_add_node(pathway_id, data)
    if response.status_code == 200:
        pathway.pathway_payload = response.text
        pathway.save()

    return response


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

    headers = {
        'Authorization': f'{settings.BLAND_API_KEY}',
        'Content-Type': 'application/json'
    }
    data = json.dumps(data)
    payload = json.loads(data)
    print("Add node Payload ",payload)

    response = requests.request("POST", endpoint, json=payload, headers=headers)
    print(response)
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


def send_call_through_pathway(pathway_id, phone_number, user_id):

    endpoint = "https://api.bland.ai/v1/calls"
    payload = {
        "phone_number": f"{phone_number}",
        "pathway_id": f"{pathway_id}",
    }

    headers = {
        'Authorization': f'{settings.BLAND_API_KEY}',
        "Content-Type": "application/json"
    }

    response = requests.request("POST", endpoint, json=payload, headers=headers)
    if response.status_code == 200:
        pathway = response.json()
        call_id = pathway.get("call_id")
        plan_id = UserSubscription.objects.get(user_id=user_id).plan_id_id
        plan_price = SubscriptionPlans.objects.get(plan_id=plan_id).plan_price
        print("plan_price: ", plan_price)
        if plan_price == 0:

            print("creating an entry in the Manage free single IVR tables")
            max_duration = UserSubscription.objects.get(user_id=user_id).single_ivr_left
            payload.update({"max_duration": f"{max_duration}"})
            print(f"Updated payload for the free plan is {payload}")
            user = TelegramUser.objects.get(user_id=user_id)
            ManageFreePlanSingleIVRCall.objects.create(
                call_id=call_id,
                pathway_id=pathway_id,
                call_number=phone_number,
                user_id=user,
                call_status = 'new'
            )

        CallLogsTable.objects.create(
            call_id=call_id,
            call_number=phone_number,
            pathway_id=pathway_id,
            user_id = user_id,
            call_status= 'new'
        )


        return pathway, 200
    else:
        return {f"{response.text}": 'Failed to retrieve pathways'}, response.status_code

def get_voices():

    url = f"{base_url}/v1/voices"

    headers = {'Authorization': f'{settings.BLAND_API_KEY}'}
    response = requests.request("GET", url, headers=headers)
    return response.json()


def bulk_ivr_flow(call_data, pathway_id, user_id):

    endpoint = f"{base_url}/v1/batches"
    headers = {
        'Authorization': f'{settings.BLAND_API_KEY}',
        "Content-Type": "application/json"
    }
    data = {
        "call_data": call_data,
        "test_mode": False,
        "pathway_id": str(pathway_id)
    }
    response = requests.request("POST", endpoint, json=data, headers=headers)
    batch_id = get_batch_id(response.text)
    print("batch id: {}".format(batch_id))
    list_response = get_call_list_from_batch(batch_id, user_id)
    print(f"list status : {list_response.status_code}")
    if list_response.status_code != 200:
        print(list_response.content)

    return response


def get_call_details(call_id):

    endpoint = f"{base_url}/v1/calls/{call_id}"
    headers = {
        'Authorization': f'{settings.BLAND_API_KEY}'
    }
    response = requests.get(endpoint, headers=headers)
    return response.json()


def get_transcript(call_id, pathway_id):

    feedback_log = FeedbackLogs.objects.get(pathway_id=pathway_id)
    feedback_questions = feedback_log.feedback_questions
    print("Feedback questions: ", feedback_questions)
    response = get_call_details(call_id)
    data = response

    feedback_answers = []

    for feedback_question in feedback_questions:
        index = None
        for i, transcript in enumerate(data.get("transcripts", [])):
            if transcript.get("user") == "assistant" and transcript.get("text").lower() == feedback_question.lower():
                index = i
                break

        if index is not None and index + 1 < len(data["transcripts"]):
            next_text = data["transcripts"][index + 1].get("text", "No response found.")
            feedback_answers.append(next_text)
        else:
            feedback_answers.append("No response found.")

    feedback_detail, created = FeedbackDetails.objects.update_or_create(
        call_id=call_id,
        defaults={
            'feedback_questions': feedback_questions,
            'feedback_answers': feedback_answers,
        }
    )
    return feedback_detail

def get_variables(call_id):

    try:
        call_details = get_call_details(call_id)
        variables = call_details.get('variables', {})
        user_input_variables = {}

        for key, value in variables.items():
            if key.endswith('user_input'):
                user_input_variables[key] = value

        return user_input_variables

    except Exception as e:
        print(f"Error extracting user input variables: {e}")
        return {"error": str(e)}

def stop_single_active_call(call_id):

    url = f"https://api.bland.ai/v1/calls/{call_id}/stop"

    headers = {'authorization': f'{settings.BLAND_API_KEY}'}

    response = requests.request("POST", url, headers=headers)


    return response

def stop_all_active_calls(call_id):

    url = "https://us.api.bland.ai/v1/calls/active/stop"

    headers = {'authorization': f'{settings.BLAND_API_KEY}'}

    response = requests.request("POST", url, headers=headers)


    return response

def stop_active_batch_calls(batch_id):

    url = f"https://api.bland.ai/v1/batches/{batch_id}/stop"

    headers = {'authorization': f'{settings.BLAND_API_KEY}'}

    response = requests.request("POST", url, headers=headers)

    print(response.text)

    return response

def batch_details(batch_id):

    url = f"https://api.bland.ai/v1/batches/{batch_id}"
    print(f"batch details url: {url}")


    headers = {'authorization': f'{settings.BLAND_API_KEY}'}

    response = requests.request("GET", url, headers=headers)

    print(response.text)
    print(f"batch details response text : {response.text}")
    return response

def get_call_list_from_batch(batch_id, user_id):
    try:
        data = batch_details(batch_id)
        if data.status_code != 200:
            logging.error("Error occurred while fetching the batch details")
            return JsonResponse({'error': 'Error occurred while fetching batch details'},
                                status=data.status_code)

    except Exception as e:
        logging.exception("An exception occurred while fetching batch details")
        return JsonResponse({'error': f'An error occurred: {str(e)}'}, status=400)

    try:
        # Process JSON response
        response = data.json()
        print(f"Response data: {response}")

        # Extract batch_params information
        batch_params = response.get('batch_params', {})
        batch_id = batch_params.get('id')
        pathway_id = batch_params.get('call_params', {}).get('pathway_id')
        call_data = response.get('call_data', [])

        print(f"Pathway ID: {pathway_id}")
        print(f"Batch ID: {batch_id}")
        print(f"Call data: {call_data}")

        # Check if call_data is empty
        if not call_data:
            logging.error("Call data is empty, cannot iterate over an empty list.")
            return JsonResponse({'error': 'No call data available in the response'}, status=400)

        # Loop through each call data
        for call in call_data:
            call_id = call.get('call_id')
            to_number = call.get('to')
            from_number = call.get('from')
            queue_status = call.get('queue_status')

            print(f"Queue Status: {queue_status}")
            print(f"To Number: {to_number}")
            print(f"From Number: {from_number}")
            print(f"Call ID: {call_id}")

            # Save each call log
            batch_call_log = BatchCallLogs(
                call_id=call_id,
                batch_id=batch_id,
                pathway_id=pathway_id,
                user_id=user_id,
                to_number=to_number,
                from_number=from_number,
                call_status=queue_status,
            )
            batch_call_log.save()
            print(f"Batch call log saved for Call ID: {call_id}")

            # Save to CallLogsTable with unique call_id
            CallLogsTable.objects.create(
                call_id=call_id,
                call_number=to_number,
                pathway_id=pathway_id,
                user_id=user_id,
                call_status='new'
            )
            print(f"Call log entry created for Call ID: {call_id}")

        return JsonResponse({'message': 'Batch call logs saved successfully.'}, status=200)

    except KeyError as e:
        logging.error(f"Missing key in response: {str(e)}")
        return JsonResponse({'error': f'Missing key in response: {str(e)}'}, status=400)

    except json.JSONDecodeError as e:
        logging.error("Invalid JSON format in response")
        return JsonResponse({'error': 'Invalid JSON format'}, status=400)

    except Exception as e:
        logging.exception("An error occurred during processing")
        return JsonResponse({'error': f'An error occurred: {str(e)}'}, status=500)

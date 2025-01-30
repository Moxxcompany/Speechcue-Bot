import hmac
import hashlib
import json

from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt

from bot.tasks import update_dtmf_inbox
from bot.utils import extract_call_details


@csrf_exempt
def call_details_webhook(request):

    if request.method == "POST":
        call_data = json.loads(request.body)
        extracted_details = extract_call_details(call_data)
        update_dtmf_inbox(extracted_details)
        return JsonResponse({"status": "success"})
    return JsonResponse({"status": "failed"})

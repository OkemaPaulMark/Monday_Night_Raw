"""Structured API exception responses."""

from rest_framework.views import exception_handler


def custom_exception_handler(exc, context):
    response = exception_handler(exc, context)
    if response is None:
        return response

    # Normalize DRF error payloads to include a top-level "detail" when helpful.
    data = response.data
    if isinstance(data, dict) and 'detail' not in data:
        # Collect first non-field or field error into detail for mobile UX.
        messages = []
        for key, value in data.items():
            if isinstance(value, (list, tuple)):
                messages.append(f'{key}: {value[0]}')
            else:
                messages.append(f'{key}: {value}')
        if messages:
            response.data = {
                'detail': messages[0],
                'errors': data,
            }
    return response

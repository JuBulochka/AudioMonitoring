"""Custom exception handler."""
import logging

from rest_framework.views import exception_handler
from rest_framework.response import Response
from rest_framework import status

logger = logging.getLogger("apps.common")


def custom_exception_handler(exc, context):
    response = exception_handler(exc, context)

    if response is not None:
        response.data = {
            "success": False,
            "error": {
                "status_code": response.status_code,
                "detail": response.data,
            },
        }
        return response

    # Unhandled exception
    logger.exception("Unhandled exception in view: %s", exc)
    return Response(
        {"success": False, "error": {"status_code": 500, "detail": "Internal server error"}},
        status=status.HTTP_500_INTERNAL_SERVER_ERROR,
    )

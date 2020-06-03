"""
Various callback paths that support callbacks from SoftwareSecure
"""

import logging
from django.template import loader
from django.conf import settings
from django.http import HttpResponse

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.negotiation import BaseContentNegotiation

from edx_proctoring.api import (
    get_exam_attempt_by_code,
    mark_exam_attempt_as_ready,
)
from edx_proctoring.statuses import ProctoredExamStudentAttemptStatus
from edx_proctoring.backends import get_backend_provider, get_proctoring_settings
from edx_proctoring.utils import locate_attempt_by_attempt_code

log = logging.getLogger(__name__)


def start_exam_callback(request, attempt_code):  # pylint: disable=unused-argument
    """
    A callback endpoint which is called when SoftwareSecure completes
    the proctoring setup and the exam should be started.

    NOTE: This returns HTML as it will be displayed in an embedded browser

    This is an authenticated endpoint and the attempt_code is passed in
    as part of the URL path

    IMPORTANT: This is an unauthenticated endpoint, so be VERY CAREFUL about extending
    this endpoint
    """

    attempt = get_exam_attempt_by_code(attempt_code)
    if not attempt:
        log.warning("Attempt code %r cannot be found.", attempt_code)
        return HttpResponse(
            content='You have entered an exam code that is not valid.',
            status=404
        )

    if attempt['status'] in [ProctoredExamStudentAttemptStatus.created,
                             ProctoredExamStudentAttemptStatus.download_software_clicked]:
        mark_exam_attempt_as_ready(attempt['proctored_exam']['id'], attempt['user']['id'])

    log.info("Exam %r has been marked as ready", attempt['proctored_exam']['id'])
    template = loader.get_template('proctored_exam/proctoring_launch_callback.html')

    return HttpResponse(
        template.render({
            'platform_name': settings.PLATFORM_NAME,
            'link_urls': get_proctoring_settings(attempt['provider_name']).get('LINK_URLS', {})
        })
    )


class AttemptStatus(APIView):
    """
    This endpoint is called by a 3rd party proctoring review service to determine
    status of an exam attempt.
    IMPORTANT: This is an unauthenticated endpoint, so be VERY CAREFUL about extending
    this endpoint
    """

    def get(self, request, attempt_code):  # pylint: disable=unused-argument
        """
        Returns the status of an exam attempt. Given that this is an unauthenticated
        caller, we will only return the status string, no additional information
        about the exam
        """

        attempt = get_exam_attempt_by_code(attempt_code)
        if not attempt:
            return HttpResponse(
                content='You have entered an exam code that is not valid.',
                status=404
            )

        log.info("attempt status {} {}".format(attempt_code, attempt['status']))
        return Response(
            data={
                # IMPORTANT: Don't add more information to this as it is an
                # unauthenticated endpoint
                'status': attempt['status'],
            },
            status=200
        )

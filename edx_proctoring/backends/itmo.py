"""
Integration with ITMOproctoring system
"""

from Crypto.Cipher import DES3
import base64
from hashlib import sha256
import requests
import hmac
import binascii
import datetime
import json
import logging
import unicodedata
import six

from django.conf import settings

from edx_proctoring.backends.backend import ProctoringBackendProvider
from edx_proctoring import constants
from edx_proctoring.exceptions import (
    BackendProviderCannotRegisterAttempt,
    ProctoredExamSuspiciousLookup,
)
from edx_proctoring.utils import locate_attempt_by_attempt_code
from edx_proctoring.models import (
    ProctoredExamSoftwareSecureComment,
    ProctoredExamStudentAttemptStatus,
)
from edx_proctoring.statuses import SoftwareSecureReviewStatus

log = logging.getLogger(__name__)

SOFTWARE_SECURE_INVALID_CHARS = u'[]<>#:|!?/\'"*\\'

class ItmoBackendProvider(ProctoringBackendProvider):
    """
    Implementation of the ProctoringBackendProvider
    """
    verbose_name = u'RPNow'
    passing_statuses = SoftwareSecureReviewStatus.passing_statuses

    def __init__(self, organization, exam_sponsor, exam_register_endpoint,
                 secret_key_id, secret_key, crypto_key, software_download_url):
        """
        Class initializer
        """

        # pylint: disable=no-member
        super(ItmoBackendProvider, self).__init__()
        self.organization = organization
        self.exam_sponsor = exam_sponsor
        self.exam_register_endpoint = exam_register_endpoint
        self.secret_key_id = secret_key_id
        self.secret_key = secret_key
        self.crypto_key = crypto_key
        self.timeout = 10
        self.software_download_url = software_download_url
        self.passing_review_status = ['Clean', 'Rules Violation']
        self.failing_review_status = ['Not Reviewed', 'Suspicious']

    def register_exam_attempt(self, exam, context):
        """
        Method that is responsible for communicating with the backend provider
        to establish a new proctored exam
        """

        attempt_code = context['attempt_code']

        data = self._get_payload(
            exam,
            context
        )
        headers = {
            "Content-Type": 'application/json'
        }
        http_date = datetime.datetime.utcnow().strftime("%a, %d %b %Y %H:%M:%S GMT")
        signature = self._sign_doc(data, 'POST', headers, http_date)

        status, response = self._send_request_to_ssi(data, signature, http_date)

        if status not in [200, 201]:
            err_msg = (
                u'Could not register attempt_code = {attempt_code}. '
                'HTTP Status code was {status_code} and response was {response}.'.format(
                    attempt_code=attempt_code,
                    status_code=status,
                    response=response
                )
            )
            log.error(err_msg)
            raise BackendProviderCannotRegisterAttempt(err_msg)

        # get the external ID that Proctor webassistant has defined
        # for this attempt
        ssi_record_locator = json.loads(response)['sessionId']
        log.info(ssi_record_locator)

        return ssi_record_locator

    def start_exam_attempt(self, exam, attempt):  # pylint: disable=unused-argument
        """
        Called when the exam attempt has been created but not started
        """
        return None

    def stop_exam_attempt(self, exam, attempt):
        """
        Method that is responsible for communicating with the backend provider
        to establish a new proctored exam
        """
        return None

    def mark_erroneous_exam_attempt(self, exam, attempt):
        """
        Method that would be responsible for communicating with the
        backend provider to mark a proctored session as having
        encountered a technical error
        """
        return None

    def get_software_download_url(self):
        """
        Returns the URL that the user needs to go to in order to download
        the corresponding desktop software
        """
        return self.software_download_url

    def on_review_callback(self, attempt, payload):
        """
        Called when the reviewing 3rd party service posts back the results
        Documentation on the data format can be found from ProctorWebassistant's
        documentation named "Reviewer Data Transfer"
        """
        received_id = payload['examMetaData']['ssiRecordLocator'].lower()
        match = (
            attempt['external_id'].lower() == received_id.lower() or
            settings.PROCTORING_SETTINGS.get('ALLOW_CALLBACK_SIMULATION', False)
        )
        if not match:
            err_msg = (
                'Found attempt_code {attempt_code}, but the recorded external_id did not '
                'match the ssiRecordLocator that had been recorded previously. Has {existing} '
                'but received {received}!'.format(
                    attempt_code=attempt['attempt_code'],
                    existing=attempt['external_id'],
                    received=received_id
                )
            )
            raise ProctoredExamSuspiciousLookup(err_msg)

        # redact the videoReviewLink from the payload
        if 'videoReviewLink' in payload:
            del payload['videoReviewLink']

        log_msg = (
            'Received callback from SoftwareSecure with review data: {payload}'.format(
                payload=payload
            )
        )
        log.info(log_msg)
        SoftwareSecureReviewStatus.validate(payload['reviewStatus'])
        review_status = SoftwareSecureReviewStatus.to_standard_status.get(payload['reviewStatus'], None)

        comments = []
        for comment in payload.get('webCamComments', []) + payload.get('desktopComments', []):
            comments.append({
                'start': comment['eventStart'],
                'stop': comment['eventFinish'],
                'duration': comment['duration'],
                'comment': comment['comments'],
                'status': comment['eventStatus']
                })

        converted = {
            'status': review_status,
            'comments': comments,
            'payload': payload,
            'reviewed_by': None,
        }
        return converted


    def on_review_saved(self, review, allow_status_update_on_fail=False):  # pylint: disable=arguments-differ
        """
        called when a review has been save - either through API (on_review_callback) or via Django Admin panel
        in order to trigger any workflow associated with proctoring review results
        """

        (attempt_obj, is_archived_attempt) = locate_attempt_by_attempt_code(review.attempt_code)

        if not attempt_obj:
            # This should not happen, but it is logged in the help
            # method
            return

        if is_archived_attempt:
            # we don't trigger workflow on reviews on archived attempts
            err_msg = (
                'Got on_review_save() callback for an archived attempt with '
                'attempt_code {attempt_code}. Will not trigger workflow...'.format(
                    attempt_code=review.attempt_code
                )
            )
            log.warn(err_msg)
            return

        # only 'Clean' and 'Rules Violation' count as passing
        status = (
            ProctoredExamStudentAttemptStatus.verified
            if review.review_status in self.passing_review_status
            else ProctoredExamStudentAttemptStatus.rejected
        )

        # are we allowed to update the status if we have a failure status
        # i.e. do we need a review to come in from Django Admin panel?
        if status == ProctoredExamStudentAttemptStatus.verified or allow_status_update_on_fail:
            # updating attempt status will trigger workflow
            # (i.e. updating credit eligibility table)
            from edx_proctoring.api import update_attempt_status

            update_attempt_status(
                attempt_obj.proctored_exam_id,
                attempt_obj.user_id,
                status
            )

    def on_exam_saved(self, exam):
        """
        Called after an exam is saved.
        """

    def _save_review_comment(self, review, comment):
        """
        Helper method to save a review comment
        """
        comment = ProctoredExamSoftwareSecureComment(
            review=review,
            start_time=comment['eventStart'],
            stop_time=comment['eventFinish'],
            duration=comment['duration'],
            comment=comment['comments'],
            status=comment['eventStatus']
        )
        comment.save()

    def _encrypt_password(self, key, pwd):
        """
        Encrypt the exam passwork with the given key
        """
        block_size = DES3.block_size

        def pad(text):
            """
            Apply padding
            """
            return (text + (block_size - len(text) % block_size) *
                    chr(block_size - len(text) % block_size)).encode('utf-8')
        cipher = DES3.new(key, DES3.MODE_ECB)
        encrypted_text = cipher.encrypt(pad(pwd))
        return base64.b64encode(encrypted_text).decode('ascii')

    def _split_fullname(self, full_name):
        """
        Utility to break Full Name to first and last name
        """
        first_name = ''
        last_name = ''
        name_elements = full_name.split(' ')
        first_name = name_elements[0]
        if len(name_elements) > 1:
            last_name = ' '.join(name_elements[1:])

        return (first_name, last_name)

    def _get_payload(self, exam, context):
        """
        Constructs the data payload that Proctor webassistant expects
        """

        attempt_code = context['attempt_code']
        time_limit_mins = context['time_limit_mins']
        is_sample_attempt = context['is_sample_attempt']
        full_name = context['full_name']
        review_policy = context.get('review_policy', "")
        review_policy_exception = context.get('review_policy_exception')
        scheme = 'https' if getattr(settings, 'HTTPS', 'on') == 'on' else 'http'
        callback_url = '{scheme}://{hostname}{path}'.format(
            scheme=scheme,
            hostname=settings.SITE_NAME,
            path=reverse(
                'jump_to', kwargs={'course_id': exam['course_id'], 'location': exam['content_id']}
            )
        )

        # compile the notes to the reviewer
        # this is a combination of the Exam Policy which is for all students
        # combined with any exceptions granted to the particular student
        reviewer_notes = review_policy
        if review_policy_exception:
            reviewer_notes = '{notes}; {exception}'.format(
                notes=reviewer_notes,
                exception=review_policy_exception
            )

        (first_name, last_name) = self._split_fullname(full_name)

        now = datetime.datetime.utcnow()
        start_time_str = now.strftime("%a, %d %b %Y %H:%M:%S GMT")
        end_time_str = (now + datetime.timedelta(minutes=time_limit_mins)).strftime("%a, %d %b %Y %H:%M:%S GMT")
        # remove all illegal characters from the exam name
        exam_name = exam['exam_name']
        exam_name = unicodedata.normalize('NFKD', exam_name).encode('ascii', 'ignore').decode('utf8')

        for character in SOFTWARE_SECURE_INVALID_CHARS:
            exam_name = exam_name.replace(character, '_')

        # if exam_name is blank because we can't normalize a potential unicode (like Chinese) exam name
        # into something ascii-like, then we have use a default otherwise
        # SoftwareSecure will fail on the exam registration API call
        if not exam_name:
            exam_name = u'Proctored Exam'

        org_extra = {
            "examStartDate": start_time_str,
            "examEndDate": end_time_str,
            "noOfStudents": 1,
            "examID": exam['id'],
            "courseID": exam['course_id'],
            "firstName": first_name,
            "lastName": last_name,
            "userID": context.get('user_id'),
            "username": context.get('username'),
        }
        if self.send_email:
            org_extra["email"] = context['email']

        return {
            "examCode": attempt_code,
            "organization": self.organization,
            "duration": time_limit_mins,
            "reviewedExam": not is_sample_attempt,
            # NOTE: we will have to allow these notes to be authorable in Studio
            # and then we will pull this from the exam database model
            "reviewerNotes": reviewer_notes,
            "examPassword": self._encrypt_password(self.crypto_key, attempt_code),
            "examSponsor": self.exam_sponsor,
            "examName": exam_name,
            "ssiProduct": 'rp-now',
            # need to pass in a URL to the LMS?
            "examUrl": callback_url,
            "orgExtra": org_extra
        }

    def _header_string(self, headers, date):
        """
        Composes the HTTP header string that ProctorWebassistant expects
        """
        # Headers
        string = ""
        if 'Content-Type' in headers:
            string += headers.get('Content-Type')
            string += '\n'

        if date:
            string += date
            string += '\n'

        return string

    def _body_string(self, body_json, prefix=""):
        """
        Serializes out the HTTP body that ProctorWebassistant expects
        """
        keys = body_json.keys()
        keys.sort()
        string = b""
        for key in keys:
            value = body_json[key]
            if isinstance(value, bool):
                if value:
                    value = b'true'
                else:
                    value = b'false'
            key = key.encode('utf8')
            if isinstance(value, (list, tuple)):
                for idx, arr in enumerate(value):
                    pfx = b'%s.%d' % (key, idx)
                    if isinstance(arr, dict):
                        string += self._body_string(arr, pfx + b'.')
                    else:
                        string += b'%s:%s\n' % (pfx, six.text_type(arr).encode('utf8'))
            elif isinstance(value, dict):
                string += self._body_string(value, key + b'.')
            else:
                if value != "" and not value:
                    value = "null"
                string += b'%s%s:%s\n' % (prefix, key, six.text_type(value).encode('utf8'))

        return string

    def _sign_doc(self, body_json, method, headers, date):
        """
        Digitaly signs the datapayload that ProctorWebassistant expects
        """
        body_str = self._body_string(body_json)

        method_string = method + b'\n\n'

        headers_str = self._header_string(headers, date)
        message = method_string + headers_str + body_str

        # HMAC requires a string not a unicode
        message = str(message)

        log_msg = (
            'About to send payload to ITMOProctoring:\n{message}'.format(message=message)
        )
        log.info(log_msg)

        hashed = hmac.new(str(self.secret_key), str(message), sha256)
        computed = binascii.b2a_base64(hashed.digest()).rstrip('\n')

        return b'SSI %s:%s' % (self.secret_key_id.encode('ascii'), computed)

    def _send_request_to_ssi(self, data, sig, date):
        """
        Performs the webservice call to ITMOProctoring
        """
        response = requests.post(
            self.exam_register_endpoint,
            headers={
                'Content-Type': 'application/json',
                "Authorization": sig,
                "Date": date
            },
            data=json.dumps(data),
            timeout=self.timeout
        )

        return response.status_code, response.text

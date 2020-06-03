"""Defines serializers used by the Proctoring API."""

from __future__ import absolute_import

from django.contrib.auth.models import User

from rest_framework import serializers
from rest_framework.fields import DateTimeField

from edx_proctoring.models import (
    ProctoredExam,
    ProctoredExamParams,
    ProctoredExamStudentAttempt,
    ProctoredExamStudentAllowance,
    ProctoredExamReviewPolicy
)


class JSONSerializerField(serializers.Field):
    """
    Serializer for JSONField -- required to make field writable
    """

    def to_internal_value(self, data):
        return data

    def to_representation(self, value):
        return value


class ProctoredExamParamsSerializer(serializers.ModelSerializer):
    """
    Serializer for the ProctoredExamParam Model.
    """
    exam_review_checkbox = JSONSerializerField()

    class Meta:
        """
        Meta Class
        """
        model = ProctoredExamParams

        fields = (
            "service", "deadline", "start", "visible_to_staff_only", "exam_review_checkbox", "updated"
        )


class ProctoredExamSerializer(serializers.ModelSerializer):
    """
    Serializer for the ProctoredExam Model.
    """
    id = serializers.IntegerField(required=False)  # pylint: disable=invalid-name
    course_id = serializers.CharField(required=True)
    content_id = serializers.CharField(required=True)
    external_id = serializers.CharField(required=True)
    exam_name = serializers.CharField(required=True)
    time_limit_mins = serializers.IntegerField(required=True)

    is_active = serializers.BooleanField(required=True)
    is_practice_exam = serializers.BooleanField(required=True)
    is_proctored = serializers.BooleanField(required=True)
    due_date = serializers.DateTimeField(required=False, format=None)
    hide_after_due = serializers.BooleanField(required=True)
    backend = serializers.CharField(required=False)
    proctoring_service = serializers.CharField(source='proctored_exam_params.service', required=False)
    extended_params = ProctoredExamParamsSerializer(source='proctored_exam_params', required=False)

    def __init__(self, *args, **kwargs):
        include_extended_params = kwargs.pop('detailed', None)
        super(ProctoredExamSerializer, self).__init__(*args, **kwargs)
        if not include_extended_params:
            self.fields.pop('extended_params')

    class Meta:
        """
        Meta Class
        """
        model = ProctoredExam

        fields = (
            "id", "course_id", "content_id", "external_id", "exam_name",
            "time_limit_mins", "is_proctored", "is_practice_exam", "is_active",
            "due_date", "hide_after_due", "backend", "proctoring_service", "extended_params"
        )


class UserSerializer(serializers.ModelSerializer):
    """
    Serializer for the User Model.
    """
    id = serializers.IntegerField(required=False)  # pylint: disable=invalid-name
    username = serializers.CharField(required=True)
    email = serializers.CharField(required=True)
    first_name = serializers.CharField(required=False)
    last_name = serializers.CharField(required=False)

    class Meta:
        """
        Meta Class
        """
        model = User

        fields = (
            "id", "username", "email", "first_name", "last_name"
        )


class ProctoredExamStudentAttemptSerializer(serializers.ModelSerializer):
    """
    Serializer for the ProctoredExamStudentAttempt Model.
    """
    proctored_exam = ProctoredExamSerializer()
    user = UserSerializer()

    # Django Rest Framework v3 defaults to `settings.DATE_FORMAT` when serializing
    # datetime fields.  We need to specify `format=None` to maintain the old behavior
    # of returning raw `datetime` objects instead of unicode.
    started_at = DateTimeField(format=None)
    completed_at = DateTimeField(format=None)
    last_poll_timestamp = DateTimeField(format=None)
    provider_name = serializers.CharField(source='proctoring_service.service', required=False)

    class Meta:
        """
        Meta Class
        """
        model = ProctoredExamStudentAttempt

        fields = (
            "id", "created", "modified", "user", "started_at", "completed_at",
            "external_id", "status", "proctored_exam", "allowed_time_limit_mins",
            "attempt_code", "is_sample_attempt", "taking_as_proctored", "last_poll_timestamp",
            "provider_name",
            "last_poll_ipaddr", "review_policy_id", "student_name", "is_status_acknowledged"
        )


class ProctoredExamStudentAllowanceSerializer(serializers.ModelSerializer):
    """
    Serializer for the ProctoredExamStudentAllowance Model.
    """
    proctored_exam = ProctoredExamSerializer()
    user = UserSerializer()

    class Meta:
        """
        Meta Class
        """
        model = ProctoredExamStudentAllowance
        fields = (
            "id", "created", "modified", "user", "key", "value", "proctored_exam"
        )


class ProctoredExamReviewPolicySerializer(serializers.ModelSerializer):
    """
    Serializer for the ProctoredExamReviewPolicy Model.
    """
    proctored_exam = ProctoredExamSerializer()
    set_by_user = UserSerializer()

    class Meta:
        """
        Meta Class
        """
        model = ProctoredExamReviewPolicy
        fields = (
            "id", "created", "modified", "set_by_user", "proctored_exam", "review_policy",
        )

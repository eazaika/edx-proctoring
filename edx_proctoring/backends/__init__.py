"""
All supporting Proctoring backends
"""
from __future__ import absolute_import

from django.apps import apps
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from importlib import import_module

# Cached instance of backend provider
_BACKEND_PROVIDER = None

import logging
log = logging.getLogger(__name__)

def _get_proctoring_config(provider_name):
    """
    Returns an dictionary of the configured backend provider that is configured
    via the settings file
    """

    proctors_config = getattr(settings, 'PROCTORING_BACKEND_PROVIDERS')
    if not provider_name:
        provider_name = 'null'
    if not proctors_config:
        raise ImproperlyConfigured(
            "Settings not configured with PROCTORING_BACKEND_PROVIDERS!"
        )
    if provider_name not in proctors_config.keys():
        msg = (
            "Misconfigured PROCTORING_BACKEND_PROVIDERS settings, "
            "there is not '%s' provider specified" % provider_name
        )
        raise ImproperlyConfigured(msg)

    return proctors_config.get(provider_name)


def get_backend_provider(exam=None, name='null'):
    """
    Returns an instance of the configured backend provider
    Passing in an exam will return the backend for that exam
    name -- Name of the proctoring provider system, e.g. "WEB_ASSISTANT" or "EXAMUS"
    """
    if exam:
        if 'is_proctored' in exam and not exam['is_proctored']:
            # timed exams don't have a backend
            return None
        elif exam['backend']:
            name = exam['backend']
        elif exam['proctoring_service']:
            name = exam['proctoring_service']

    config = _get_proctoring_config(name)
    if not config:
        raise ImproperlyConfigured("Settings not configured with PROCTORING_BACKEND_PROVIDER!")

    if 'class' not in config or 'options' not in config:
        msg = (
            "Misconfigured PROCTORING_BACKEND_PROVIDERS settings, "
            "must have both 'class' and 'options' keys."
        )
        raise ImproperlyConfigured(msg)

    module_path, _, name = config['class'].rpartition('.')
    class_ = getattr(import_module(module_path), name)
    provider = class_(**config['options'])

    return provider

def get_proctoring_settings(provider_name):
    """
    Returns an settings from the configured backend provider.
    Keyword arguments:
    provider_name -- Name of the proctoring provider system, e.g. "WEB_ASSISTANT" or "EXAMUS"
    """
    config = _get_proctoring_config(provider_name)

    if 'settings' not in config:
        msg = (
            "Miscongfigured PROCTORING_BACKEND_PROVIDES settings,"
            "%s must contain 'settings' option" % provider_name
        )
        raise ImproperlyConfigured(msg)
    return config['settings']


def get_proctoring_settings_param(proctor_settings, param, default=False):
    """
    Returns an param from the proctor_settings.
    Keyword arguments:
    proctor_settings -- dict with settings for particular proctoring system
    param -- parameter name, e.g 'SITE_NAME' or 'BCC_EMAIL'
    default -- boolean, use platform default value for param if proctor_settings param is missing
    """
    platform_default = {
        'SITE_NAME': settings.SITE_NAME,
        'PLATFORM_NAME': settings.PLATFORM_NAME,
        'STATUS_EMAIL_FROM_ADDRESS': settings.DEFAULT_FROM_EMAIL,
        'CONTACT_EMAIL': getattr(settings, 'CONTACT_EMAIL'),
        'ALLOW_REVIEW_UPDATES': getattr(
            settings, 'ALLOW_REVIEW_UPDATES', True
        ),
        'BCC_EMAIL': None,
        'REPLY_TO_EMAIL': None,
    }
    if param in platform_default and not default:
        default = platform_default[param]
    return proctor_settings.get(param, default)

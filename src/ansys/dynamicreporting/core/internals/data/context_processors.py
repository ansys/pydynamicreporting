from django.conf import settings


def global_settings(request):
    # return any necessary values
    return {
        'BETA_FLAG': settings.BETA_FLAG,
        'ENABLE_ACLS': settings.ENABLE_ACLS,
        'MAX_UPLOAD_SIZE': settings.MAX_UPLOAD_SIZE,
        'COLOR_MODE': settings.COLOR_MODE
    }


def debug(request):
    """
    Return context variables helpful for debugging.
    """
    return {"debug": settings.DEBUG}

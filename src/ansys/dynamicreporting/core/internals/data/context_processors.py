from django.conf import settings


def global_settings(request):
    # return any necessary values
    return {
        'BETA_FLAG': settings.BETA_FLAG,
        'ENABLE_ACLS': settings.ENABLE_ACLS,
    }

#!/usr/bin/env python
import os

if __name__ == "__main__":
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "ceireports.settings")

    import django
    django.setup()

    from data.geofile_rendering import do_geometry_update_check

    do_geometry_update_check()


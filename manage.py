import os
import sys

if __name__ == "__main__":
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "myapp.settings")
    try:
        from django.core.management import execute_from_command_line
    except ImportError:
        # The above import may fail for some other reason. Make sure django is installed#
        try:
            import django
        except ImportError:
            raise ImportError(
                "Couldn't import Django. Is it installed and "
                "available on your PYTHONPATH environment variable? "
                " Have you activated the virtual environment?"
            )
        raise
    execute_from_command_line(sys.argv)

import os
import sys

sys.path.insert(0, '/home/estelatechnologi/FisioActif')

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'FisioActif.settings')

from django.core.wsgi import get_wsgi_application
application = get_wsgi_application()
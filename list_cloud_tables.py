import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'eatpan_core.settings')
django.setup()

from django.db import connections
with connections['cloud'].cursor() as c:
    c.execute("SELECT table_name FROM information_schema.tables WHERE table_schema='public'")
    for row in c.fetchall():
        print(row[0])

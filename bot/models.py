from django.db import models


# Create your models here.
class Pathways(models.Model):
    pathway_id = models.TextField(primary_key=True)
    pathway_name = models.TextField()
    pathway_user_id = models.BigIntegerField()
    pathway_description = models.TextField(null=True)
    pathway_payload = models.TextField(null=True)
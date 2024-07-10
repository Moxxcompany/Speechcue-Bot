from django.db import models


# Create your models here.
class Pathways(models.Model):
    pathway_id = models.IntegerField(primary_key=True)
    pathway_name = models.TextField()
    pathway_user_id = models.BigIntegerField()

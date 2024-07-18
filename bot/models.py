import uuid

from django.db import models


# Create your models here.
class Pathways(models.Model):
    pathway_id = models.TextField(primary_key=True)
    pathway_name = models.TextField()
    pathway_user_id = models.BigIntegerField()
    pathway_description = models.TextField(null=True)
    pathway_payload = models.TextField(null=True)


class AudioFile(models.Model):
    user_id = models.BigIntegerField()
    pathway_id = models.TextField()
    node_name = models.CharField(max_length=255)
    node_id = models.IntegerField()
    audio_file = models.FileField(upload_to='audio_files/')
    uploaded_at = models.DateTimeField(auto_now_add=True)



class TransferCallNumbers(models.Model):
    user_id = models.BigIntegerField()
    phone_number = models.TextField()
    num_id = models.CharField(max_length=40, primary_key=True, default=uuid.uuid4)

    def __str__(self):
        return self.phone_number


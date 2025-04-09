from django.db import models
from django.db.models import JSONField 

class ProjectHistory(models.Model):
    user_id = models.CharField(max_length=100, default='anonymous')
    language = models.CharField(max_length=50)
    user_request = models.TextField()
    project_name = models.CharField(max_length=100)
    project_path = models.TextField(null=True, blank=True)
    response_files = JSONField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.language} - {self.user_request[:30]}..."



from django.db import models
from django.conf import settings
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.core.exceptions import ValidationError
from django.db.models import Q

class Course(models.Model):
    title = models.CharField(max_length=200, unique=True)
    start_at = models.DateTimeField()
    end_at = models.DateTimeField()
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    registrations_count = models.PositiveIntegerField(default=0)

    class Meta:
        db_table = 'courses'
        indexes = [
            models.Index(fields=['registrations_count']),
            models.Index(fields=['is_active', 'start_at', 'end_at']),
            models.Index(fields=['created_at'])
        ]

    def clean(self):
        if self.start_at >= self.end_at:
            raise ValidationError("Start at must be before end at")

    def __str__(self):
        return self.title


class CourseRegistration(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='course_registrations')
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name='registrations')
    created_at = models.DateTimeField(auto_now_add=True)

    STATUS_CHOICES = [
        ('registered', 'registered'),
        ('in_progress', 'in_progress'),
        ('completed', 'completed'),
        ('cancelled', 'cancelled'),
    ]
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='registered', db_index=True)
    attempted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'course_registrations'
        indexes = [
            models.Index(fields=['course']),
            models.Index(fields=['user']),
            models.Index(fields=['status']),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=['user', 'course'],
                condition=~Q(status='cancelled'),
                name='uniq_active_course_registration',
            ),
        ]

@receiver(post_save, sender=CourseRegistration)
def inc_course_registration_count(sender, instance, created, **kwargs):
    if created:
        Course.objects.filter(pk=instance.course_id).update(registrations_count=models.F('registrations_count') + 1)

@receiver(post_delete, sender=CourseRegistration)
def dec_course_registration_count(sender, instance, **kwargs):
    Course.objects.filter(pk=instance.course_id).update(registrations_count=models.F('registrations_count') - 1)
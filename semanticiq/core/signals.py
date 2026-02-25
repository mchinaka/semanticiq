from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import Actor

@receiver(post_save, sender=User)
def create_actor_for_user(sender, instance, created, **kwargs):
    if created:
        Actor.objects.create(
            user=instance,
            actor_type=Actor.ActorType.USER,
            identifier=instance.username,  # canonical ID
            display_name=instance.get_full_name() or instance.username,
            roles=[],
        )
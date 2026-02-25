from django.contrib.auth.models import User
from ..models import Actor

def create_actor_for_user(user):
    if not user or not user.is_authenticated:
        return None

    actor, created = Actor.objects.get_or_create(
        user=user,
        defaults={
            "identifier": user.username,
            "display_name": user.get_full_name() or user.username,
            "actor_type": Actor.ActorType.USER,
            "roles": [],
        }
    )
    return actor


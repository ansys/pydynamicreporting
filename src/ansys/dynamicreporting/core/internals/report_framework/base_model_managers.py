from django.db import models

from .acls import ObjectPermsFilter


class NexusQuerySet(models.QuerySet):
    # custom querysets to chain custom method calls
    # eg: Session.objects.with_perms(request).orphaned()
    def with_perms(self, request, perm=None):
        return ObjectPermsFilter.get_result_set(request, self, perm=perm)


class NexusModelManager(models.Manager):
    # WARNING: Never do any filtering in get_queryset
    def get_queryset(self):
        return NexusQuerySet(model=self.model, using=self._db, hints=self._hints)

    def with_perms(self, request, perm=None):
        return self.get_queryset().with_perms(request, perm=perm)

from ceireports.base_model_managers import NexusModelManager, NexusQuerySet
from django.db.models import Count


class ItemManager(NexusModelManager):
    pass


class ItemCategoryManager(NexusModelManager):
    pass


class SessionQuerySet(NexusQuerySet):
    def orphaned(self):
        return self.annotate(Count('item')).filter(item__count=0)


class SessionManager(NexusModelManager):
    def get_queryset(self):
        return SessionQuerySet(model=self.model, using=self._db, hints=self._hints)

    def orphaned(self):
        return self.get_queryset().orphaned()


class DatasetQuerySet(NexusQuerySet):
    def orphaned(self):
        return self.annotate(Count('item')).filter(item__count=0)


class DatasetManager(NexusModelManager):
    def get_queryset(self):
        return DatasetQuerySet(model=self.model, using=self._db, hints=self._hints)

    def orphaned(self):
        return self.get_queryset().orphaned()

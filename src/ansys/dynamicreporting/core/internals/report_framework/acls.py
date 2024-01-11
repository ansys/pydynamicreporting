import time

from .utils import decrypt_hash
from django.conf import settings
from django.core import signing
from django.core.exceptions import PermissionDenied
from django.db.models import Q, Exists, OuterRef
from django.db.models import QuerySet
from guardian.shortcuts import assign_perm


def get_permission_codename(action, opts, codename_only=False):
    """
    Get the permission codename string

    Args:
        codename_only:
        action:
        opts: model meta API

    Returns:

    """
    model_name = opts.model_name
    app_label = opts.app_label
    if codename_only:
        return f"{action}_{model_name}"
    else:
        return f"{app_label}.{action}_{model_name}"


def get_perms_to_check(action, opts, codename_only=False):
    """
    Get a list of perms to check from a given action.
    Args:
        codename_only: should we only return codenames w/o app label
        action:
        opts: model meta API

    Returns:

    """
    codename_view = get_permission_codename('view', opts, codename_only=codename_only)
    codename_change = get_permission_codename('change', opts, codename_only=codename_only)
    codename_own = get_permission_codename('own', opts, codename_only=codename_only)
    codename_add = get_permission_codename('add', opts, codename_only=codename_only)
    codename_delete = get_permission_codename('delete', opts, codename_only=codename_only)

    lookup = {
        'add': [codename_add, ],
        'view': [codename_own, codename_view, codename_change],
        'change': [codename_own, codename_change, ],
        'delete': [codename_own, codename_delete, ],
        'own': [codename_own, ],
    }

    return lookup[action]


def assign_perms(perm, user_or_group, obj_or_queryset):
    """
    Assign owner permissions to object.

    Args:
        perm:
        user_or_group:
        obj_or_queryset: the target object or a set of them

    Returns:

    """
    if getattr(settings, 'ENABLE_ACLS', False):
        # meta options can be obtained from different places.
        if isinstance(obj_or_queryset, QuerySet):
            opts = obj_or_queryset.model._meta
        else:
            opts = obj_or_queryset._meta

        codename = get_permission_codename(perm, opts)
        assign_perm(codename, user_or_group, obj_or_queryset)


def has_add_permission(user, opts):
    """
    Return True if the given user has permission to add an object.
    """
    codename_add = get_permission_codename('add', opts)
    return user.has_perm(codename_add)


def has_change_permission(user, opts, obj=None):
    """
    Return True if the given user has permission to change the given
    Django model instance, should return True if the given request has
    permission to change the `obj` model instance.
    If `obj` is None, this should return True if the given
    request has permission to change *any* object of the given type.
    """
    codename_change = get_permission_codename('change', opts)
    codename_own = get_permission_codename('own', opts)
    return (
            user.has_perm(codename_own, obj) or
            user.has_perm(codename_change, obj)
    )


def has_delete_permission(user, opts, obj=None):
    """
    Return True if the given user has permission to change the given
    Django model instance.
    should return True if the given request has permission to delete the `obj`
    model instance. If `obj` is None, this should return True if the given
    request has permission to delete *any* object of the given type.
    """
    codename_delete = get_permission_codename('delete', opts)
    codename_own = get_permission_codename('own', opts)
    return (
            user.has_perm(codename_own, obj) or
            user.has_perm(codename_delete, obj)
    )


def has_view_permission(user, opts, obj=None):
    """
    Return True if the given user has permission to view the given
    Django model instance. should return True if the
    given request has permission to view the `obj` model instance. If `obj`
    is None, it should return True if the request has permission to view
    any object of the given type.
    """
    codename_view = get_permission_codename('view', opts)
    codename_change = get_permission_codename('change', opts)
    codename_own = get_permission_codename('own', opts)
    return (
            user.has_perm(codename_own, obj) or
            user.has_perm(codename_view, obj) or
            user.has_perm(codename_change, obj)
    )


def has_own_permission(user, opts, obj=None):
    """
    Return True if the given user owns the
    Django model instance. should return True if the
    given request has own permission on the `obj` model instance. If `obj`
    is None, it should return True if the request has own permission on
    any object of the given type.
    """
    codename_own = get_permission_codename('own', opts)
    return user.has_perm(codename_own, obj)


def has_perms(obj):
    """
    Check if the object has any assigned permissions at all.

    Args:
        obj:

    Returns:

    """
    model_name = obj._meta.model_name
    # get corresponding related managers
    group_obj_perm_rel_mgr = getattr(obj, f"{model_name}groupobjectpermission_set", None)

    # this can NEVER be none UNLESS the database has not been migrated properly
    # (if DB and the code are out of sync).
    if group_obj_perm_rel_mgr is None:
        raise Exception('Unusual exception: Object does not have related managers to check for permissions.'
                        'Make sure the database is migrated properly.')

    # check if the object has any perms at all
    return group_obj_perm_rel_mgr.exists()


def item_has_perms(item):
    """
    Check if the item has any perms at all.
    Separated from the general object perm check because items inherit perms
    through their categories.

    Args:
        item:

    Returns:

    """
    # unnecessary but what the hell
    if not hasattr(item, 'categories'):
        raise Exception('Unusual exception: Object does not have related categories to check for permissions.'
                        'Make sure the database is migrated properly.')

    return not item.categories.filter(Q(itemcategorygroupobjectpermission=None)).exists()


def has_any_perms(obj):
    """
    Check if the object has any assigned perms at all

    Args:
        obj: the target object

    Returns:

    """
    # add a cache to the item to be used for frequent checking.
    # compute only if no value in cache
    if not hasattr(obj, '_has_perms'):
        obj._has_perms = item_has_perms(obj) if obj._meta.model_name == 'item' else has_perms(obj)

    return obj._has_perms


def has_owner(obj):
    """
    Check if the object has a user or group owner

    Args:
        obj: the target object

    Returns:

    """
    # add a cache to the item to be used for frequent checking.
    # compute only if no value in cache
    if not hasattr(obj, '_has_owner'):
        model_name = obj._meta.model_name
        # get corresponding related managers
        group_obj_perm_rel_mgr = getattr(obj, f"{model_name}groupobjectpermission_set", None)

        # this can NEVER be none UNLESS the database has not been migrated properly
        # (if DB and the code are out of sync).
        if group_obj_perm_rel_mgr is None:
            raise Exception('Unusual exception: Object does not have related managers to check for permissions.'
                            'Make sure the database is migrated properly.')

        # check if the object has an owner.
        # check group owner first, because that's the most common.
        obj._has_owner = group_obj_perm_rel_mgr.filter(permission__codename=f"own_{model_name}").exists()

    return obj._has_owner


def check_perm(perm, user, obj, raise_exception=False, accept_global_perms=True, allow_no_perm_access=True):
    """
    Permission checks for all objects with ACLs enabled.

    Args:
        perm: the permission
        user: the user object
        obj: the object
        raise_exception: raise an exception if denied
        accept_global_perms: accept global perms
        allow_no_perm_access: allow access if the obj has no existing perms assigned

    Returns: bool

    """
    # 2. We check for objects without owners first and break out early.
    # This is for both authenticated and anon users.
    # if the user is not authenticated, i.e is anonymous, we
    # grant him access to the object only if it has no owner.
    # we don't return here because it could be
    # a logged-in inactive user, whom we dont want to give access to.
    # or an anonymous user (who are never considered active), ok to give access to.
    no_owner = allow_no_perm_access and not has_any_perms(obj)

    # an authenticated user has another shot at the object via his permissions,
    # but anon user is done after the no-owner check.
    # for some cases, we return early and avoid unnecessary db lookups, for the rest
    # we wait until the end.
    if user.is_authenticated:
        # check for inactive users first, because a superuser can also be inactive.
        # never allow inactive users.
        # we only check this if authenticated, otherwise is_active is always False
        if not user.is_active:
            return False

        # do the no owner check, then..
        # always allow active superusers
        if no_owner or user.is_superuser:
            return True

        function_lookup = {
            'view': has_view_permission,
            'change': has_change_permission,
            'delete': has_delete_permission,
            'own': has_own_permission,
        }
        has_perm = function_lookup[perm]
        opts = obj._meta

        if accept_global_perms:
            # allow global perm checks to override
            allow = has_perm(user, opts) or has_perm(user, opts, obj=obj)
        else:
            allow = has_perm(user, opts, obj=obj)

    else:
        allow = no_owner

    # raise if required.
    if not allow and raise_exception:
        raise PermissionDenied

    return allow


def get_categories(item):
    """
    Get all categories that the item belongs to.

    Args:
        item:

    Returns:

    """
    return item.categories.all()


def has_category(item):
    """
    Check if item has a category

    Args:
        item:

    Returns:

    """
    return item.categories.exists()


def check_item_perm(perm, user, item, raise_exception=False, accept_global_perms=True, allow_no_perm_access=False):
    """
    Item specific permission checks because of categories.
    Items do not have direct permissions. They inherit the permissions of their categories.

    Args:
        perm:
        user:
        item:
        raise_exception:
        accept_global_perms:
        allow_no_perm_access: This is False by default, because if a category has no perms assigned, then we
        deny access.

    Returns: bool

    """
    # unnecessary but what the hell
    if not hasattr(item, 'categories'):
        raise Exception('Unusual exception: Object does not have related categories to check for permissions.'
                        'Make sure the database is migrated properly.')

    # get categories of the obj
    categories = get_categories(item)

    # if the object does not have categories, its free for all.
    # also, force evaluate because we're looping through anyway.
    if not categories:
        return True

    # check if user has perm on any one category
    for category in categories:
        # - we dont raise by default, because we wait until at least one category has the required perms.
        # - allow_no_perm_access is False by default, because if a category has no perms assigned,
        # then we deny access.
        if check_perm(perm, user, category, raise_exception=False, accept_global_perms=accept_global_perms,
                      allow_no_perm_access=allow_no_perm_access):
            return True

    # do not raise until all categories are checked.
    if raise_exception:
        raise PermissionDenied

    return False


def check_obj_perm(perm, user, obj, raise_exception=False, accept_global_perms=True, allow_no_perm_access=True):
    """
    Check object specific perms and raise.

    Checks:
    User should have ANY of these:
    - global owner perms for the object's class
    - global *perm* perms for the object's class
    - owner perms for the object
    - *perm* perms for the object
    AND.. if the item does not have owner (if item has no owner, its free for all to play with.).
    if all of these are false, then deny access.

    NOTE: 'add' permissions are not per-object, so they are separated from this logic.

    Args:
        perm: the permission
        user: user obj
        obj: the target obj
        raise_exception: raise an exception?
        accept_global_perms: allow global perms to override other perms
        allow_no_perm_access: allow access if there's no owner

    Returns: bool

    """
    # 1. Allow if ACLs is disabled
    if not getattr(settings, 'ENABLE_ACLS', False):
        return True

    # this works around an issue with the checkin tests for Python 2 code where
    # 'xception{comma}' is not allowd.
    tmp = raise_exception

    if obj._meta.model_name == 'item':
        # special case for items because of categories.
        # we use the default value for allow_no_perm_access which is False,
        # because if a category has no perms assigned,
        # then we deny access. This is specific to the item case.
        return check_item_perm(perm, user, obj, raise_exception=tmp,
                               accept_global_perms=accept_global_perms)

    return check_perm(perm, user, obj, raise_exception=tmp,
                      accept_global_perms=accept_global_perms,
                      allow_no_perm_access=allow_no_perm_access)


def allow_categories(request):
    """
    Common check to decide if we should allow category assignment.

    NOTE: Make sure this is called lazily after other checks because
    user.groups.exists() is a SQL query which could be avoided.

    :param request:
    :return:
    """
    # cache this variable per request
    if not hasattr(request.user, "allow_categories"):
        setattr(request.user, "allow_categories",
                getattr(settings, 'ENABLE_ACLS', False) and request.user.groups.exists())
    return request.user.allow_categories


def generate_share_hash(request, obj_guid, perms=None, max_age=604800):
    """
    Generate a hash for the share feature using the given params.

    :param request: HttpRequest object
    :param obj_guid: guid of the object
    :param perms: temporary permissions allowed
    :param max_age: maximum age of hash in seconds. Default is one week: 604800s
    :return: Hash string
    """
    dict_to_hash = {
        'url': request.path_info,
        'sharer_user_id': request.user.id,
        'perms': perms,
        'max_age': max_age,
        'timestamp': signing.b62_encode(int(time.time())),
    }

    return signing.dumps(dict_to_hash, salt=str(obj_guid), compress=True)


def is_share_hash_valid(share_hash, request, obj_guid, perms=None):
    """
    Check if the provided sharing hash is valid.

    :param share_hash:
    :param request: HttpRequest object
    :param obj_guid: guid of the object
    :param perms: Permissions to verify.
    :return: bool
    """
    if not request.user.is_authenticated:
        return False

    decrypted_dict = decrypt_hash(share_hash, salt=str(obj_guid))
    # django's signing has its own max_age checking, but we use our own instead
    # because the max_age info is stored in the hashed dict and cant be accessed
    # until it is decrypted. To use django's own max_age checking, we have to pass
    # the max_age during decryption, but that won't be available then, so we do it
    # this way.
    max_age = decrypted_dict.get('max_age')
    if max_age:
        timestamp = decrypted_dict.get('timestamp')
        if timestamp:
            timestamp = signing.b62_decode(timestamp)
            age = time.time() - timestamp
            if age > max_age:
                return False

    if decrypted_dict.get('url') != request.path_info:
        return False

    current_perms = decrypted_dict.get('perms')
    if perms:
        if not current_perms or not set(current_perms).issubset(set(perms)):
            return False

    return True


class ObjectPermsFilter:
    """
    Filter backend to limit queryset based on user ACLs
    """

    @staticmethod
    def get_result_set(request, queryset, perm=None):
        """
        The result set is supposed to return a distinct result set from two sets combined:
        1. A set of all objects that the user has perms too
        2. A set of all objects that have no assigned permissions (meaning they are "free-for-all")

        Args:
            perm: specific perm to check
            request: Django HttpRequest
            queryset: Input queryset

        Returns:

        """
        # if ACLs is disabled
        if not getattr(settings, 'ENABLE_ACLS', False):
            return queryset

        opts = queryset.model._meta
        model_name = opts.model_name

        # check if the model has permissions directly or via its category
        # permission related field to query with
        perm_field = f'{model_name}groupobjectpermission'
        # if this does not exist(i.e no direct permissions),
        # the model's category is checked
        has_categ = perm_field not in opts.fields_map
        if has_categ:
            # this is for objects with permissions via a category. eg: Item
            no_perm_queryset = queryset.filter(Q(categories=None))
        else:
            # this is for objects with permissions directly on them. eg: ItemCategory
            # fetch objects that have no assigned permissions
            no_perm_queryset = queryset.filter(Q(**{perm_field: None}))

        # if the user is anonymous, only return objects without assigned permissions.
        if not request.user.is_authenticated:
            return no_perm_queryset

        # 1. check for inactive users first, because a superuser can also be inactive.
        # 2. also anon users are always considered inactive so handle them before this.
        # inactive users get nothing
        if not request.user.is_active:
            return queryset.none()

        # return everything if superuser.
        if request.user.is_superuser:
            return queryset

        # build the final qs
        if has_categ:
            # get the category through relation
            through_field = None
            for field in opts.get_fields():
                if field.one_to_many and field.auto_created and \
                        field.related_model._meta.model_name == f"{model_name}categoryrelation":
                    through_field = field
                    break

            if through_field:
                # get the "through" model
                model = through_field.related_model
                # category field on this model
                category_field = model._meta.get_field('category')
                # category model of this category field
                category_model = category_field.related_model
                # get category list and filter w/ it
                categories = category_model.filtered_objects.with_perms(request, perm=perm)
                # return items that belong to the allowed categories,
                # also return items that have no categories for backward compat
                final_qs = queryset.filter(Q(categories=None) | Q(categories__in=categories))
            else:
                final_qs = queryset.none()
        else:
            # There are two ways of deciding the perms to filter by, ordered
            # by priority:
            # 1. 'perm' param (overrides everything)
            # 2. request.method -- GET,DELETE,PUT/PATCH
            method_perm_lookup = {
                'get': 'view',
                'put': 'change',
                'patch': 'change',
                'delete': 'delete'
            }

            if perm:
                action = perm
            elif request.method.lower() in method_perm_lookup.keys():
                action = method_perm_lookup[request.method.lower()]
            else:
                # assume view action at the least.
                action = 'view'

            # get the perms list from utils
            perms_to_check = get_perms_to_check(action, opts)

            # WARNING: This won't handle anon users.
            from guardian.shortcuts import get_objects_for_user
            user_perm_queryset = get_objects_for_user(
                request.user,
                perms_to_check,
                queryset,
                use_groups=True,
                any_perm=True,
                accept_global_perms=True
            )

            # NOTE: in addition to the set of objects that user has perms on,
            # we also return objects that do not have assigned permissions.(backwards compatibility)
            final_qs = user_perm_queryset | no_perm_queryset

        # IMPORTANT: remove duplicates that are returned
        # Using .distinct() will prevent operations like delete()
        # on the filtered queryset so use this workaround:
        # Ref: https://github.com/django/django/pull/14313
        # subquery
        final_qs = final_qs.filter(pk=OuterRef('pk'))
        # actual query
        final_qs = queryset.filter(Exists(final_qs))

        # NOTE: returns empty qs if the model neither has permissions directly
        # on itself NOR has permissions via a category
        return final_qs

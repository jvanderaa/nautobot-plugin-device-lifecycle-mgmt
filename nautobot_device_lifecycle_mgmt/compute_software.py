"""> get-software

- Traverse the relationship from device to software.


> get-validated-software-list

- In m2m model we'll have to have a hierarchy
    - First get ValidatedSoftware with "device" equal to our device
    - Then look at "device_types" w/ "roles"
    - Then look at "device_types"

> get-validated-software-list-currently-valid

- Not all validated softwares will be currently valid.

> get-preferred-validated-software-list

- Logic is the same but when build preferred software we need to go from more specific to less specific
    - It is possible that Device will match the same ValidatedSoftware more than once
    e.g. if ValidatedSoftware is assigned to a device and to the device_type + role that the device has then we'll get the same object twice.

> is-software-valid
    - This requires check for "if device.soft in validated_softwares"
    - Can this be cached? Can this be saved in the database?
        - If so, which model?
"""

import itertools
import functools
import operator

from django.contrib.contenttypes.models import ContentType
from nautobot.extras.models import RelationshipAssociation

from .models import ValidatedSoftwareLCM, SoftwareLCM
from .tables import ValidatedSoftwareLCMTable


def get_software(soft_relation_name, obj_model, obj_id):
    """Get software assigned to the object."""
    try:
        obj_soft_relation = RelationshipAssociation.objects.get(
            relationship__slug=soft_relation_name,
            destination_type=ContentType.objects.get_for_model(obj_model),
            destination_id=obj_id,
        )
        obj_soft = SoftwareLCM.objects.get(id=obj_soft_relation.source_id)
    except (RelationshipAssociation.DoesNotExist, SoftwareLCM.DoesNotExist):
        obj_soft = None

    return obj_soft


def validate_software(software, validated_soft_list, preferred=False):
    """Validate software against the validated software objects."""
    if not (software or validated_soft_list):
        return False

    if preferred:
        validated_software_versions = {valsoft.software for valsoft in validated_soft_list if valsoft.preferred}
    else:
        validated_software_versions = {valsoft.software for valsoft in validated_soft_list}

    return software in validated_software_versions


class ItemValidatedSoftware:
    """Base class providing functions for validated software objects."""

    item_obj = None
    valid_only = False

    def get_validated_soft_query_sets(self):
        """Returns ValidateSoftware query sets for individual filters. Implemented by subclasses."""
        return NotImplemented

    def get_validated_soft_combined_query_set(self):
        """Combines individual query sets into final query set for ValidatedSoftware."""
        return functools.reduce(operator.or_, self.get_validated_soft_query_sets())

    def get_validated_soft_list(self):
        """Return query set combining individual query sets for ValidatedSoftwareLCM objects."""
        validsoft_combined_qs = self.get_validated_soft_combined_query_set()

        if not validsoft_combined_qs.exists():
            return None

        validsoft_list_qs = validsoft_combined_qs.distinct()

        if self.valid_only:
            validsoft_list = [validsoft for validsoft in validsoft_list_qs if validsoft.valid]
        else:
            validsoft_list = list(validsoft_list_qs)

        return validsoft_list

    def get_preferred_validated_soft_list(self):
        """Return preferred validated software list ordered by the order of preference."""
        preferred_validated_soft = []
        for valsoft_obj in itertools.chain(self.get_validated_soft_query_sets()):
            if not valsoft_obj.preferred:
                continue
            if self.valid_only and valsoft_obj.valid:
                preferred_validated_soft.append(valsoft_obj)

        return preferred_validated_soft

    def get_validated_soft_table(self):
        """Returns table of validated software linked to the object."""
        if not self.validated_soft_list:
            return None

        return ValidatedSoftwareLCMTable(
            list(self.validated_soft_list),
            orderable=False,
            exclude=(
                "name",
                "actions",
            ),
        )


class DeviceValidatedSoftware(ItemValidatedSoftware):
    """Computes validated software objects for Device objects."""

    def get_validated_soft_query_sets(self):
        """Returns ValidateSoftware query sets for individual filters."""

        valsoft_device_qs = ValidatedSoftwareLCM.objects.filter(devices=self.item_obj.pk)
        valsoft_devtype_role_qs = ValidatedSoftwareLCM.objects.filter(
            device_types=self.item_obj.device_type.pk, roles=self.item_obj.device_role.pk
        ).difference(valsoft_device_qs)
        valsoft_devtype_qs = ValidatedSoftwareLCM.objects.filter(
            device_types=self.item_obj.device_type.pk, roles=None
        ).difference(valsoft_device_qs, valsoft_devtype_role_qs)

        return (valsoft_device_qs, valsoft_devtype_role_qs, valsoft_devtype_qs)


class DeviceTypeValidatedSoftware(ItemValidatedSoftware):
    """Computes validated software objects for DeviceType objects."""

    def get_validated_soft_query_sets(self):
        """Returns ValidateSoftware query sets for individual filters."""

        valsoft_devtype_qs = ValidatedSoftwareLCM.objects.filter(device_types=self.item_obj.pk)

        return (valsoft_devtype_qs,)


class InventoryItemValidatedSoftware(ItemValidatedSoftware):
    """Computes validated software objects for InventoryItem objects."""

    def get_validated_soft_query_sets(self):
        """Returns ValidateSoftware query sets for individual filters."""

        valsoft_inventoryitem_qs = ValidatedSoftwareLCM.objects.filter(inventory_items=self.item_obj.pk)

        return (valsoft_inventoryitem_qs,)

import re
import logging
import copy
try:
    from configparser import RawConfigParser
except ImportError:
    from ConfigParser import RawConfigParser
from canopen import objectdictionary
from canopen.sdo import SdoClient
from . import objecttypes as otype


logger = logging.getLogger(__name__)


od_main_index_regex = re.compile(r"^[0-9A-Fa-f]{4}$")
od_main_index_with_name_regex = re.compile(r"^([0-9A-Fa-f]{4})Name")
od_sub_index_regex = re.compile(r"^([0-9A-Fa-f]{4})sub([0-9A-Fa-f]+)$")


def import_eds(source, node_id):
    eds = RawConfigParser()
    if hasattr(source, "read"):
        fp = source
    else:
        fp = open(source)
    try:
        # Python 3
        eds.read_file(fp)
    except AttributeError:
        # Python 2
        eds.readfp(fp)
    fp.close()
    od = objectdictionary.ObjectDictionary()
    if eds.has_section("DeviceComissioning"):
        od.bitrate = int(eds.get("DeviceComissioning", "Baudrate")) * 1000
        od.node_id = int(eds.get("DeviceComissioning", "NodeID"))

    for section in eds.sections():
        # Match main indexes
        match = od_main_index_regex.match(section)
        if match is not None:
            index = int(section, 16)
            name = eds.get(section, "ParameterName")
            object_type = int(eds.get(section, "ObjectType"), 0)

            if object_type == otype.VAR:
                var = build_variable(eds, section, node_id, index)
                od.add_object(var)
            elif object_type == otype.ARR and eds.has_option(section, "CompactSubObj"):
                arr = objectdictionary.Array(name, index)
                last_subindex = objectdictionary.Variable(
                    "Number of entries", index, 0)
                last_subindex.data_type = objectdictionary.UNSIGNED8
                arr.add_member(last_subindex)
                arr.add_member(build_variable(eds, section, node_id, index, 1))
                od.add_object(arr)
            elif object_type == otype.ARR:
                arr = objectdictionary.Array(name, index)
                od.add_object(arr)
            elif object_type == otype.RECORD:
                record = objectdictionary.Record(name, index)
                od.add_object(record)

            continue

        # Match subindexes
        match = od_sub_index_regex.match(section)
        if match is not None:
            index = int(match.group(1), 16)
            subindex = int(match.group(2), 16)
            entry = od[index]
            if isinstance(entry, (objectdictionary.Record,
                                  objectdictionary.Array)):
                var = build_variable(eds, section, node_id, index, subindex)
                entry.add_member(var)

        # Match [index]Name
        match = od_main_index_with_name_regex.match(section)
        if match is not None:
            index = int(match.group(1), 16)
            num_of_entries = int(eds.get(section, "NrOfEntries"))
            entry = od[index]
            # For CompactSubObj index 1 is were we find the variable
            src_var = od[index][1]
            for subindex in range(1, num_of_entries + 1):
                var = copy_variable(eds, section, subindex, src_var)
                if var is not None:
                    entry.add_member(var)

    return od


def import_from_node(node_id, network):
    # Create temporary SDO client
    sdo_client = SdoClient(0x600 + node_id, 0x580 + node_id, None)
    sdo_client.network = network
    # Subscribe to SDO responses
    network.subscribe(0x580 + node_id, sdo_client.on_response)
    # Create file like object for Store EDS variable
    try:
        eds_fp = sdo_client.open(0x1021, 0, "rt")
        od = import_eds(eds_fp, node_id)
    except Exception as e:
        logger.error("No object dictionary could be loaded for node %d: %s",
                     node_id, e)
        od = None
    finally:
        network.unsubscribe(0x580 + node_id)
    return od


def build_variable(eds, section, node_id, index, subindex=0):
    name = eds.get(section, "ParameterName")
    var = objectdictionary.Variable(name, index, subindex)
    var.data_type = int(eds.get(section, "DataType"), 0)
    var.access_type = eds.get(section, "AccessType").lower()
    if var.data_type > 0x1B:
        # The object dictionary editor from CANFestival creates an optional object if min max values are used
        # This optional object is then placed in the eds under the section [A0] (start point, iterates for more)
        # The eds.get function gives us 0x00A0 now convert to String without hex representation and upper case
        # The sub2 part is then the section where the type parameter stands
        var.data_type = int(eds.get("%Xsub1" % var.data_type, "DefaultValue"), 0)

    if eds.has_option(section, "LowLimit"):
        try:
            var.min = int(eds.get(section, "LowLimit"), 0)
        except ValueError:
            pass
    if eds.has_option(section, "HighLimit"):
        try:
            var.max = int(eds.get(section, "HighLimit"), 0)
        except ValueError:
            pass
    if eds.has_option(section, "DefaultValue"):
        try:
            default_value = eds.get(section, "DefaultValue")

            if var.data_type in objectdictionary.datatypes.DATA_TYPES:
                var.value = default_value
            elif var.data_type in objectdictionary.datatypes.FLOAT_TYPES:
                var.value = float(default_value)
            else:
                #COB-ID can have a suffix of '$NODEID+' so replace this with node_id before converting
                if '$NODEID+' in default_value and node_id is not None:
                    var.value = int(default_value.replace('$NODEID+',''), 0) + node_id
                else:
                    var.value = int(default_value, 0)
            var.default = var.current
        except ValueError:
            pass
    return var

def copy_variable(eds, section, subindex, src_var):
    name = eds.get(section, str(subindex))
    var = copy.copy(src_var)
    # It is only the name and subindex that varies
    var.name = name
    var.subindex = subindex
    return var

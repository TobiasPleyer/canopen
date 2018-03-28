import os.path
import unittest
import time
import canopen
from canopen import nmt
from canopen.objectdictionary import Variable, Record
import canopen.objectdictionary.datatypes as dtypes
from canopen.pdo import RemoteRPDO
import logging
from random import seed, randint
import threading
import struct


seed(333)


SENSOR_EDS_PATH = os.path.join(os.path.dirname(__file__), 'sensor.eds')
SENSOR_MASTER_EDS_PATH = os.path.join(os.path.dirname(__file__),
                                      'sensor_master.eds')


logging.basicConfig(level=logging.WARNING)


class Sensor(canopen.LocalNode):
    """A sensor device"""
    def __init__(self, node_id):
        canopen.LocalNode.__init__(self, node_id, SENSOR_EDS_PATH)

        correction_factor_var = self.get_object('Correction_Factor')
        self.correction_factor = correction_factor_var.raw
        correction_factor_var.add_callback(self.onNewFactor)

        self.do_measure = threading.Event()
        self.do_measure.set()
        self._measure = threading.Thread(target=self.measure)
        self._measure.daemon = True
        self._measure.start()

    def onNewFactor(self, index, subindex, data):
        """Variable change callback function
        When the object dictionary variable for the correction value changes,
        then this function is called and writes the new value into the class
        variable."""

        self.correction_factor = self.get_value('Correction_Factor')

    def measure(self):
        """This function simulates a sensor measurement.
        We fluctuate around some base value (measurement jitter). In addition
        we include the correction factor into the calculation."""
        base_value = 10000
        try:
            while self.do_measure.is_set():
                val = int(self.correction_factor *
                          (base_value + randint(-500, 500)))
                self.set_value('Sensor_Value', 0, val)
                time.sleep(0.25)
        except Exception as exc:
            self.exception = exc
            raise

    def remove_network(self):
        """Specialized child function to stop the daemonized measurement
        thread"""
        self.do_measure.clear()
        canopen.LocalNode.remove_network(self)


class NetworkMaster(canopen.RemoteNode):
    """The data collection instance of the network"""
    def __init__(self, node_id):
        canopen.Remote.__init__(self, node_id, SENSOR_MASTER_EDS_PATH)
        self.active_sensors = {}

    def associate_network(self, network):
        canopen.RemoteNode.associate_network(self, network)
        # Start listening for hearbeat signals of the first 50 nodes
        for node_id in range(1, 50):
            self.network.subscribe(node_id, self.on_sensor_heartbeat)

    def remove_network(self):
        for node_id in range(1, 50):
            self.network.unsubscribe(node_id)
        canopen.RemoteNode.remove_network(self)

    def on_sensor_heartbeat(self, can_id, data, timestamp):
        state = struct.unpack_from("<B", data)[0]
        state = nmt.NMT_STATES[nmt.COMMAND_TO_STATE[state]]
        if state == 'OPERATIONAL':
            # We have to dynamically create new object dictionary entries to
            # send/receive data to/from this node
            node_id = can_id - 0x700

            # First create the internal variable that the value is stored in
            internal_var_addr = node_id + 0x6060
            internal_var = Variable("Process_Data_Node#" + str(node_id),
                                    internal_var_addr, 0)
            internal_var.data_type = dtypes.INTEGER16

            # Now create the communication record
            com_index = 0x1400 + node_id
            com_record = Record("Com_Sensor#" + str(node_id), com_index)
            count_var = Variable("n_Entries", com_index, 0)
            count_var.data_type = dtypes.UNSIGNED8
            count_var.raw = 1
            cob_var = Variable("COB-ID", com_index, 1)
            cob_var.data_type = dtypes.UNSIGNED32
            cob_var.raw = node_id + 1024
            com_record.add_member(count_var)
            com_record.add_member(cob_var)

            # Now create the mapping record
            map_index = 0x1800 + node_id
            map_record = Record("Map_Sensor#" + str(node_id), map_index)
            count_var = Variable("n_Entries", com_index, 0)
            count_var.data_type = dtypes.UNSIGNED8
            count_var.raw = 1
            map_var = Variable("Map1", com_index, 1)
            map_var.data_type = dtypes.UNSIGNED32
            map_var.raw = (internal_var_addr << 16) | 0x20
            map_record.add_member(count_var)
            map_record.add_member(map_var)

            # Add the entries to the object dictionary
            self.object_dictionary.add_object(internal_var)
            self.object_dictionary.add_object(com_record)
            self.object_dictionary.add_object(map_record)

            # Now we can create the pdo for this sensor
            rpdo = RemoteRPDO(self.pdo, com_index, map_index)
            self.pdo.rx[com_index] = rpdo
        else:
            # Sensor not longer operational -> remove from active sensors
            if can_id in self.active_sensors:
                self.active_sensors.pop(can_id)


class TestDemo(unittest.TestCase):
    """
    A demo implementation of the canopen features.

    The scenario:
        We are the network master, a data collection device. The data we are
        collecting comes from a number of sensors. Each sensor can only measure
        one thing and sends its data as process data (PDO). In addition every
        sensor has a correction factor which it uses to compensate for errors
        due to ambient constraints. The sensors are not able to determine that
        correction factor themselves, instead the network master sends them the
        value of this factor via PDO.
    Network Settings:
        * The sensors send their data via COB-ID 0x400 + node ID
        * The sensors receive the correction factor on COB-ID 0x222
        * The network master does not know in advance which sensors are
          connected to the network
    """

    def setUp(self):
        self.master_network = canopen.Network()
        self.sensor_network = canopen.Network()
        # Connect to a virtual network to allow for OS independent tests
        self.master_network.connect(channel="demo", bustype="virtual",
                                    receive_own_messages=True)
        self.sensor_network.connect(channel="demo", bustype="virtual",
                                    receive_own_messages=True)
        self.master_node = NetworkMaster(1)
        self.master_node.associate_network(self.master_network)
        time.sleep(0.5)
        self.sensors = [
            Sensor(5),
            Sensor(8),
            Sensor(12),
        ]
        for sensor in self.sensors:
            sensor.associate_network(self.sensor_network)
            sensor.nmt.state = "PRE-OPERATIONAL"

    def tearDown(self):
        self.master_node.remove_network()
        for sensor in self.sensors:
            sensor.remove_network()
        self.network.disconnect()

    def test_demo(self):
        pass

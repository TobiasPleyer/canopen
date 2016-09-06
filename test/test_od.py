import unittest
from canopen import objectdictionary as od


class TestDataConversions(unittest.TestCase):

    def test_boolean(self):
        var = od.Variable("Test BOOLEAN", 0x1000)
        var.data_type = od.BOOLEAN
        self.assertEqual(var.decode_raw(b"\x01"), True)
        self.assertEqual(var.decode_raw(b"\x00"), False)
        self.assertEqual(var.encode_raw(True), b"\x01")
        self.assertEqual(var.encode_raw(False), b"\x00")

    def test_unsigned8(self):
        var = od.Variable("Test UNSIGNED8", 0x1000)
        var.data_type = od.UNSIGNED8
        self.assertEqual(var.decode_raw(b"\xff"), 255)
        self.assertEqual(var.encode_raw(254), b"\xfe")

    def test_unsigned16(self):
        var = od.Variable("Test UNSIGNED16", 0x1000)
        var.data_type = od.UNSIGNED16
        self.assertEqual(var.decode_raw(b"\xfe\xff"), 65534)
        self.assertEqual(var.encode_raw(65534), b"\xfe\xff")

    def test_unsigned32(self):
        var = od.Variable("Test UNSIGNED32", 0x1000)
        var.data_type = od.UNSIGNED32
        self.assertEqual(var.decode_raw(b"\xfc\xfd\xfe\xff"), 4294901244)
        self.assertEqual(var.encode_raw(4294901244), b"\xfc\xfd\xfe\xff")

    def test_integer8(self):
        var = od.Variable("Test INTEGER8", 0x1000)
        var.data_type = od.INTEGER8
        self.assertEqual(var.decode_raw(b"\xff"), -1)
        self.assertEqual(var.decode_raw(b"\x7f"), 127)
        self.assertEqual(var.encode_raw(-2), b"\xfe")
        self.assertEqual(var.encode_raw(127), b"\x7f")

    def test_integer16(self):
        var = od.Variable("Test INTEGER16", 0x1000)
        var.data_type = od.INTEGER16
        self.assertEqual(var.decode_raw(b"\xfe\xff"), -2)
        self.assertEqual(var.decode_raw(b"\x01\x00"), 1)
        self.assertEqual(var.encode_raw(-2), b"\xfe\xff")
        self.assertEqual(var.encode_raw(1), b"\x01\x00")

    def test_integer32(self):
        var = od.Variable("Test INTEGER32", 0x1000)
        var.data_type = od.INTEGER32
        self.assertEqual(var.decode_raw(b"\xfe\xff\xff\xff"), -2)
        self.assertEqual(var.encode_raw(-2), b"\xfe\xff\xff\xff")

    def test_visible_string(self):
        var = od.Variable("Test VIS_STR", 0x1000)
        var.data_type = od.VIS_STR
        self.assertEqual(var.decode_raw(b"abcdefg"), "abcdefg")
        self.assertEqual(var.encode_raw("testing"), b"testing")


class TestAlternativeRepresentations(unittest.TestCase):

    def test_phys(self):
        var = od.Variable("Test INTEGER16", 0x1000)
        var.data_type = od.INTEGER16
        var.factor = 0.1

        self.assertAlmostEqual(var.decode_phys(b"\x80\x00"), 12.8)
        self.assertEqual(var.encode_phys(-0.1), b"\xff\xff")

    def test_desc(self):
        var = od.Variable("Test UNSIGNED8", 0x1000)
        var.data_type = od.UNSIGNED8
        var.add_value_description(0, "Value 0")
        var.add_value_description(1, "Value 1")
        var.add_value_description(3, "Value 3")

        self.assertEqual(var.decode_desc(b"\x00"), "Value 0")
        self.assertEqual(var.decode_desc(b"\x03"), "Value 3")
        self.assertEqual(var.encode_desc("Value 1"), b"\x01")

    def test_bits(self):
        var = od.Variable("Test UNSIGNED8", 0x1000)
        var.data_type = od.UNSIGNED8
        var.add_bit_definition("BIT 0", [0])
        var.add_bit_definition("BIT 2 and 3", [2, 3])

        self.assertEqual(var.decode_bits(b"\x01", "BIT 0"), 1)
        self.assertEqual(var.decode_bits(b"\x01", [1]), 0)
        self.assertEqual(var.decode_bits(b"\x0f", [0, 1, 2, 3]), 15)
        self.assertEqual(var.decode_bits(b"\x08", "BIT 2 and 3"), 2)
        self.assertEqual(var.encode_bits(b"\x0f", [1], 0), b"\x0d")
        self.assertEqual(var.encode_bits(b"\x00", "BIT 0", 1), b"\x01")


class TestObjectDictionary(unittest.TestCase):

    def test_add_variable(self):
        test_od = od.ObjectDictionary()
        var = od.Variable("Test Variable", 0x1000)
        test_od.add_object(var)
        self.assertEqual(test_od["Test Variable"], var)
        self.assertEqual(test_od[0x1000], var)

    def test_add_record(self):
        test_od = od.ObjectDictionary()
        record = od.Record("Test Record", 0x1001)
        var = od.Variable("Test Subindex", 0x1001, 1)
        record.add_member(var)
        test_od.add_object(record)
        self.assertEqual(test_od["Test Record"], record)
        self.assertEqual(test_od[0x1001], record)
        self.assertEqual(test_od["Test Record"]["Test Subindex"], var)

    def test_add_array(self):
        test_od = od.ObjectDictionary()
        array = od.Array("Test Array", 0x1002)
        test_od.add_object(array)
        self.assertEqual(test_od["Test Array"], array)
        self.assertEqual(test_od[0x1002], array)


class TestArray(unittest.TestCase):

    def test_subindexes(self):
        array = od.Array("Test Array", 0x1000)
        array.variable = od.Variable("Test Variable", 0x1000, 1)
        subindexes = [var.subindex for var in array]
        self.assertSequenceEqual(subindexes, range(0, 256))

    def test_nof_entries(self):
        array = od.Array("Test Array", 0x1000)
        self.assertEqual(array[0].data_type, od.UNSIGNED8)
        self.assertEqual(array[0].subindex, 0)

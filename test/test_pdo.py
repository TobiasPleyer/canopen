import os.path
import unittest
import canopen


EDS_PATH = os.path.join(os.path.dirname(__file__), 'sample.eds')


class TestPDO(unittest.TestCase):

    def test_bit_mapping(self):
        pass


if __name__ == "__main__":
    unittest.main()

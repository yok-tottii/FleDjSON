
import unittest

class TestBasic(unittest.TestCase):
    def test_simple_assertion(self):
        """シンプルなアサーション"""
        self.assertEqual(1 + 1, 2)
        
    def test_string_operation(self):
        """文字列操作"""
        self.assertEqual("hello" + " " + "world", "hello world")
        
if __name__ == "__main__":
    unittest.main()

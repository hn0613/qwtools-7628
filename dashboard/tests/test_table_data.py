# -*- coding: utf-8 -*-
"""
Tests for the unified table data layer.

Covers:
  - SQL.run() NaN -> None replacement
  - Data shape contract (column-oriented dict)
  - JSON serialisation safety (no NaN / Infinity)

Run with:  python -m unittest dashboard.tests.test_table_data
"""

import json
import unittest


class TestNaNReplacement(unittest.TestCase):
    """Verify the astype(object).where(pd.notnull(...), None) pattern
    that SQL.run() uses to sanitise query results."""

    def test_nan_replaced_with_none(self):
        import pandas as pd
        frame = pd.DataFrame({
            'a': [1, None, 3],
            'b': ['x', 'y', None]
        })
        frame = frame.astype(object).where(pd.notnull(frame), None)
        result = frame.to_dict()

        self.assertIsNone(result['a'][1])
        self.assertIsNone(result['b'][2])
        self.assertEqual(result['a'][0], 1)
        self.assertEqual(result['b'][0], 'x')

    def test_empty_dataframe(self):
        import pandas as pd
        frame = pd.DataFrame()
        frame = frame.astype(object).where(pd.notnull(frame), None)
        result = frame.to_dict()
        self.assertEqual(result, {})

    def test_all_nan_column(self):
        import pandas as pd
        frame = pd.DataFrame({'x': [None, None, None]})
        frame = frame.astype(object).where(pd.notnull(frame), None)
        result = frame.to_dict()
        for val in result['x'].values():
            self.assertIsNone(val)


class TestDataShapeContract(unittest.TestCase):
    """Verify the column-oriented dict shape that the frontend expects."""

    def test_pandas_to_dict_shape(self):
        import pandas as pd
        frame = pd.DataFrame({
            'name': ['Alice', 'Bob'],
            'age': [30, 25]
        })
        frame = frame.astype(object).where(pd.notnull(frame), None)
        result = frame.to_dict()

        self.assertIn('name', result)
        self.assertIn('age', result)
        self.assertIsInstance(result['name'], dict)
        self.assertEqual(result['name'][0], 'Alice')
        self.assertEqual(result['name'][1], 'Bob')
        self.assertEqual(result['age'][0], 30)
        self.assertEqual(result['age'][1], 25)

    def test_json_round_trip(self):
        """After JSON serialise -> deserialise, NaN must be null, not NaN."""
        import pandas as pd
        frame = pd.DataFrame({
            'val': [1.0, None, 3.14],
            'text': ['hello', None, 'world']
        })
        frame = frame.astype(object).where(pd.notnull(frame), None)
        result = frame.to_dict()

        json_str = json.dumps(result)
        parsed = json.loads(json_str)
        # JSON keys become strings after round-trip
        self.assertIsNone(parsed['val']['1'])
        self.assertIsNone(parsed['text']['1'])

    def test_no_nan_in_json_output(self):
        """Ensure json.dumps does not produce 'NaN' (which is invalid JSON)."""
        import pandas as pd
        frame = pd.DataFrame({'x': [1.0, None, 3.0]})
        frame = frame.astype(object).where(pd.notnull(frame), None)
        result = frame.to_dict()

        json_str = json.dumps(result)
        self.assertNotIn('NaN', json_str)
        self.assertIn('null', json_str)


if __name__ == '__main__':
    unittest.main()

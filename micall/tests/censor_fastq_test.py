import StringIO
import unittest

from micall.core.censor_fastq import censor


class CensorTest(unittest.TestCase):
    def setUp(self):
        self.addTypeEqualityFunc(str, self.assertMultiLineEqual)
        self.original_text = """\
@M01841:45:000000000-A5FEG:1:1101:5296:13227 1:N:0:9
ACGT
+
AAAA
"""
        self.original_file = StringIO.StringIO(self.original_text)
        self.bad_cycles = []
        self.censored_file = StringIO.StringIO()
        self.summary_file = StringIO.StringIO()

    def testNoBadCycles(self):
        expected_text = self.original_text

        censor(self.original_file,
               self.bad_cycles,
               self.censored_file,
               use_gzip=False)

        self.assertEqual(expected_text, self.censored_file.getvalue())

    def testBadCycle(self):
        self.bad_cycles = [{'tile': '1101', 'cycle': '3'}]
        expected_text = """\
@M01841:45:000000000-A5FEG:1:1101:5296:13227 1:N:0:9
ACNT
+
AA#A
"""

        censor(self.original_file,
               self.bad_cycles,
               self.censored_file,
               use_gzip=False)

        self.assertEqual(expected_text, self.censored_file.getvalue())

    def testBadTail(self):
        self.bad_cycles = [{'tile': '1101', 'cycle': '3'},
                           {'tile': '1101', 'cycle': '4'}]
        expected_text = """\
@M01841:45:000000000-A5FEG:1:1101:5296:13227 1:N:0:9
AC
+
AA
"""

        censor(self.original_file,
               self.bad_cycles,
               self.censored_file,
               use_gzip=False)

        self.assertEqual(expected_text, self.censored_file.getvalue())

    def testDifferentTile(self):
        self.bad_cycles = [{'tile': '1102', 'cycle': '3'}]
        expected_text = self.original_text

        censor(self.original_file,
               self.bad_cycles,
               self.censored_file,
               use_gzip=False)

        self.assertEqual(expected_text, self.censored_file.getvalue())

    def testDifferentDirection(self):
        self.original_text = """\
@M01841:45:000000000-A5FEG:1:1101:5296:13227 2:N:0:9
ACGT
+
AAAA
"""
        self.original_file = StringIO.StringIO(self.original_text)
        self.bad_cycles = [{'tile': '1101', 'cycle': '3'}]
        expected_text = self.original_text

        censor(self.original_file,
               self.bad_cycles,
               self.censored_file,
               use_gzip=False)

        self.assertEqual(expected_text, self.censored_file.getvalue())

    def testReverseDirection(self):
        self.original_text = """\
@M01841:45:000000000-A5FEG:1:1101:5296:13227 2:N:0:9
ACGT
+
AAAA
"""
        self.original_file = StringIO.StringIO(self.original_text)
        self.bad_cycles = [{'tile': '1101', 'cycle': '-3'}]
        expected_text = """\
@M01841:45:000000000-A5FEG:1:1101:5296:13227 2:N:0:9
ACNT
+
AA#A
"""

        censor(self.original_file,
               self.bad_cycles,
               self.censored_file,
               use_gzip=False)

        self.assertEqual(expected_text, self.censored_file.getvalue())

    def testTwoReads(self):
        self.original_text = """\
@M01841:45:000000000-A5FEG:1:1101:5296:13227 1:N:0:9
ACGT
+
AAAA
@M01841:45:000000000-A5FEG:1:1102:1234:12345 1:N:0:9
TGCA
+
BBBB
"""
        self.original_file = StringIO.StringIO(self.original_text)
        self.bad_cycles = [{'tile': '1101', 'cycle': '2'},
                           {'tile': '1102', 'cycle': '3'}]
        expected_text = """\
@M01841:45:000000000-A5FEG:1:1101:5296:13227 1:N:0:9
ANGT
+
A#AA
@M01841:45:000000000-A5FEG:1:1102:1234:12345 1:N:0:9
TGNA
+
BB#B
"""

        censor(self.original_file,
               self.bad_cycles,
               self.censored_file,
               use_gzip=False)

        self.assertEqual(expected_text, self.censored_file.getvalue())

    def testSummary(self):
        self.bad_cycles = [{'tile': '1101', 'cycle': '3'}]
        expected_summary = """\
avg_quality,base_count
32.0,4
"""

        censor(self.original_file,
               self.bad_cycles,
               self.censored_file,
               use_gzip=False,
               summary_file=self.summary_file)

        self.assertEqual(expected_summary, self.summary_file.getvalue())

    def testSummaryAverage(self):
        self.original_text = """\
@M01841:45:000000000-A5FEG:1:1101:5296:13227 1:N:0:9
ACGT
+
AACC
"""
        self.original_file = StringIO.StringIO(self.original_text)
        self.bad_cycles = [{'tile': '1101', 'cycle': '3'}]
        expected_summary = """\
avg_quality,base_count
33.0,4
"""

        censor(self.original_file,
               self.bad_cycles,
               self.censored_file,
               use_gzip=False,
               summary_file=self.summary_file)

        self.assertEqual(expected_summary, self.summary_file.getvalue())

    def testSummaryEmpty(self):
        self.original_text = ""
        self.original_file = StringIO.StringIO(self.original_text)
        expected_summary = """\
avg_quality,base_count
,0
"""

        censor(self.original_file,
               self.bad_cycles,
               self.censored_file,
               use_gzip=False,
               summary_file=self.summary_file)

        self.assertEqual(expected_summary, self.summary_file.getvalue())

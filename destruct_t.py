from unittest import TestCase
import destruct as d
import struct as s

class strbufTests(TestCase):
    def setUp(self):
        self.teststr = 'In God we trust. The rest, we test!'
        self.buf = d.strbuf(self.teststr)

    def test_reads(self):
        self.assertEqual(str(self.buf.read(6)), 'In God')
        self.assertEqual(str(self.buf.read(11)), ' we trust. ')
        self.assertEqual(str(self.buf.read(30)), 'The rest, we test!')

    def test_moving(self):
        self.assertEqual(self.buf.pos, 0)
        self.assertRaises(ValueError, self.buf.read, -1)
        self.assertEqual(self.buf.pos, 0)

        self.buf.pos += 9
        self.assertEqual(self.buf.pos, 9)
        self.buf.pos -= 3
        self.assertEqual(self.buf.pos, 6)
        self.buf.pos = 4
        self.assertEqual(self.buf.pos, 4)
        
        self.buf.read(10)
        self.assertEqual(self.buf.pos, 14)
        self.buf.read(0)
        self.assertEqual(self.buf.pos, 14)
        self.buf.read(30)
        maxpos = len(self.teststr)
        self.assertEqual(self.buf.pos, maxpos)
        self.buf.pos = 100
        self.assertEqual(self.buf.pos, maxpos)

    def test_len(self):
        maxpos = len(self.teststr)
        self.assertEqual(maxpos, len(self.buf))
        self.buf.read(5)
        self.assertEqual(maxpos - 5, len(self.buf))
        self.buf.read(10)
        self.assertEqual(maxpos - 15, len(self.buf))
        self.buf.read(30)
        self.assertEqual(0, len(self.buf))

        self.buf.pos = 0
        self.assertEqual(maxpos, len(self.buf))
        self.buf.pos = 12
        self.assertEqual(maxpos - 12, len(self.buf))

class unpackTests(TestCase):
    def setUp(self):
        #struct scorecard{
        #   char name[40];
        #   uint32_t p_id;
        #   uint8_t points[42];
        #   uint32_t ranking;
        #}
        self.teststr = ('Jonny Normal' + ('\x00' * 28)
                        + '\x2e\x01\x00\x00'
                        + '\x00\x01\x05\x05\x10\x08\x18' + ('\x00' * 35)
                        + '\x04\x00\x00\x00')
        # That means Jonny Normal, id = 302, 7 games played with
        # with [0, 1, 5, 5, 16, 8, 24] points on them, ranked 4th
        self.buf = d.strbuf(self.teststr)

    def test_string(self):
        self.assertEqual(d.unpack('=40s', self.buf),
                         ['Jonny Normal' + (28 * '\x00')])
        self.assertEqual(self.buf.pos, 40)
        self.buf.pos = 0
        self.assertEqual(d.unpack('=5s', self.buf), ['Jonny'])

    def test_nested_string(self):
        self.assertEqual(d.unpack('=(((s)2s)2s)s(s(5s))', self.buf),
                         [[[['J'], 'on'], 'ny'], ' ', ['N', ['ormal']]])
        self.assertEqual(self.buf.pos, 12)

    def test_numbers(self):
        self.buf.pos = 40
        self.assertEqual(d.unpack('<I', self.buf), [0x12e])
        self.buf.pos = 40
        self.assertEqual(d.unpack('>I', self.buf), [0x2e010000])

    def test_endiannes(self):
        # make sure endianness distributes through the call stack
        self.buf.pos = 44
        self.assertEqual(d.unpack('<H((HH)H)', self.buf),
                         [0x100, [[0x0505, 0x0810], 0x18]])
        self.buf.pos = 44
        self.assertEqual(d.unpack('>H((HH)H)', self.buf),
                         [0x1, [[0x0505, 0x1008], 0x1800]])

    def test_combo(self):
        name, p_id, points, rank = d.unpack('<40s I (42B) I', self.buf)
        self.assertEqual(name, 'Jonny Normal' + (28 * '\x00'))
        self.assertEqual(p_id, 0x12e)
        self.assertEqual(points, [0, 1, 5, 5, 16, 8, 24] + ([0] * 35))
        self.assertEqual(rank, 4)

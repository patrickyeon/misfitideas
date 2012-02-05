import struct as s

def unpack(fmt, buff):
    ''' Extended unpacking, buff needs to be a destruct.buf subclass

        Format string is a strict superset of the struct format strings. Use
        parens '(' and ')' to delimit lists (arrays).'''
    order = '@'
    if fmt[0] in '@=<>!':
        # going to want to distribute the byte order to sub-strings
        order, fmt = fmt[0], fmt[1:]
    ret = []
    start = 0
    while start < len(fmt):
        # any special chars?
        op = fmt.find('(', start)
        cl = fmt.find(')', start)
        if op > -1 and op < cl:
            # unpack until opening paren, then recurse to handle content inside
            # the parens
            subfmt = order + fmt[start:op]
            start = op + 1 # nobody else needs to see the open paren
            if s.calcsize(subfmt) > 0:
                # ret.extend() to flatten the tuple returned by s.unpack()
                ret.extend(s.unpack(subfmt, buff.read(s.calcsize(subfmt))))
                # v-- if ever need to see which substrings are going where
                #ret.append(str(buff.read(s.calcsize(subfmt))))
            consumed, parsed = unpack(order + fmt[start:], buff)
            ret.append(parsed)
            # make sure to account for chars handled
            start += consumed
        elif cl > -1:
            # unpack until close paren, then bump it up the call stack
            subfmt = order + fmt[start:cl]
            start = cl + 1
            if s.calcsize(subfmt) > 0:
                ret.extend(s.unpack(subfmt, buff.read(s.calcsize(subfmt))))
                # v-- to see substrings
                #ret.append(str(buff.read(s.calcsize(subfmt))))
            return start, ret
        else:
            # unpack to the end of the format string
            subfmt = order + fmt[start:]
            if s.calcsize(subfmt) > 0:
                ret.extend(s.unpack(subfmt, buff.read(s.calcsize(subfmt))))
                #ret.append(str(buff.read(s.calcsize(subfmt))))
            start = len(fmt)
    return ret

class buf(object):
    ''' Buffers that work for me. No relation to the native buffer.

        buf.pos is the position in the byte stream.'''
    def _nie(self, foo=None):
        raise NotImplementedError
    pos = property(_nie, _nie)
    
    def read(self, size):
        ''' returns a [native] buffer of (at least?) size bytes.'''
        raise NotImplementedError
    def __len__(self):
        ''' returns number of bytes from current position to end of stream.'''
        raise NotImplementedError

class strbuf(buf):
    def __init__(self, string):
        self._buf = buffer(string)
        self._pos = 0

    def __len__(self):
        return len(self._buf) - self.pos

    def seek_to(self, to):
        self._pos = to
    def tell(self):
        return self._pos
    pos = property(tell, seek_to)

    def read(self, size):
        offset = self.pos
        self.pos = min(offset + size, len(self._buf))
        return buffer(self._buf, offset, size)

class filebuf(buf):
    def __init__(self, file_or_filename):
        """ Only actual files please. Need a static end, and seekable """
        if isinstance(file_or_filename, file):
            # TODO allow user to pass pre-seeked file, use position at
            # construction as base offset?
            self._f = file_or_filename
        else:
            # TODO open specifically as binary?
            self._f = open(file_or_filename)
        # I hope I'm not damaging anything by doing this
        self._f.seek(0, 2)
        self._end = self._f.tell()
        self._f.seek(0)
        self._pos = 0

    def __len__(self):
        return self._end - self._pos

    def seek_to(self, to):
        self._f.seek(to, 0)
    def tell(self):
        return self._f.tell()
    pos = property(tell, seek_to)

    def read(self, size):
        # TODO something to make sure size bytes are read?
        # TODO buffer map into the file, not create a new string?
        return buffer(self._f.read(size))

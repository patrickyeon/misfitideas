import struct as s

class Struct:
    ''' Extended Structs, with fancier format strings!

        Format string is a strict superset of the struct format strings. Use
        parens '(' and ')' to delimit lists (arrays).'''
    def __init__(self, fmt):
        self.fmt = self.build_fmt(fmt)

    def build_fmt(self, fmt):
        order = '@'
        if fmt[0] in '@=<>!':
            # going to want to distribute the byte order to sub-strings
            order, fmt = fmt[0], fmt[1:]
        tree, consumed = self._rec_build(order, fmt, 0)
        return tree

    def _rec_build(self, order, fmt, depth):
        ret = []
        start = 0
        while start < len(fmt):
            # any special chars?
            op = fmt.find('(', start)
            cl = fmt.find(')', start)
            if op > -1 and cl == -1:
                # don't like this here, but need to check for now
                raise Exception('not enough parens!')
            if op > -1 and op < cl:
                # unpack until opening paren, then recurse to handle content
                # inside the parens
                subfmt = fmt[start:op]
                start = op + 1 # nobody else needs to see the open paren
                if s.calcsize(subfmt) > 0:
                    ret.append(s.Struct(subfmt))
                    # v-- if ever need to see which substrings are going where
                    #ret.append(subfmt)
                parsed, consumed = self._rec_build(order, fmt[start:],
                                                   depth + 1)
                ret.append(parsed)
                # make sure to account for chars handled
                start += consumed
            elif cl > -1:
                if depth == 0:
                    raise Exception('too many parens!')
                # unpack until close paren, then bump it up the call stack
                subfmt = order + fmt[start:cl]
                start = cl + 1
                if s.calcsize(subfmt) > 0:
                    ret.append(s.Struct(subfmt))
                    # v-- to see substrings
                    #ret.append(subfmt)
                return ret, start
            else:
                # unpack to the end of the format string
                subfmt = order + fmt[start:]
                if s.calcsize(subfmt) > 0:
                    ret.append(s.Struct(subfmt))
                    #ret.append(str(buff.read(s.calcsize(subfmt))))
                start = len(fmt)
        if depth > 0:
            raise Exception('not enough parens!')
        return ret, start

    def unpack(self, buff):
        # buff needs to be a destruct.buf subclass
        if not issubclass(buff.__class__, buf):
            buff = strbuf(buff)
        return self._rec_unpack(buff, self.fmt)

    def _rec_unpack(self, buff, fmt_tree):
        # can pre-allocate ret, if it makes a difference
        ret = []
        for st in fmt_tree:
            if hasattr(st, 'unpack'):
                ret.extend(st.unpack(buff.read(st.size)))
            else:
                ret.append(self._rec_unpack(buff, st))
        return ret

def unpack(fmt, buff):
    return Struct(fmt).unpack(buff)

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
        if to < 0:
            raise ValueError('pos must be zero or positive')
        self._pos = min(to, len(self._buf))
    def tell(self):
        return self._pos
    pos = property(tell, seek_to)

    def read(self, size):
        if size < 0:
            raise ValueError('size must be zero or positive')
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

    def __len__(self):
        return self._end - self.pos

    def seek_to(self, to):
        if to < 0:
            raise ValueError('pos must be zero or positive')
        self._f.seek(to, 0)
    def tell(self):
        return self._f.tell()
    pos = property(tell, seek_to)

    def read(self, size):
        if size < 0:
            raise ValueError('size must be zero or positive')
        # TODO something to make sure size bytes are read?
        # TODO buffer map into the file, not create a new string?
        return buffer(self._f.read(size))

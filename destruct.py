import struct as s
from collections import OrderedDict

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
        tree, consumed = self._rec_build(order, lexer(fmt), 0)
        return tree

    def lex_build(self, lexed):
        cuts = iter(lexed.cuts)
        ctx = context()
        if lexed.txt[ctx.ind] in '@=<>!':
            # going to want to distribute the byte order to sub-strings
            ctx.end = lexed.txt[ctx.ind]
            ctx.ind += 1
        return self.rec_lex(lexed, ctx, cuts)
        
    def rec_lex(self, lexed, ctx, cuts):
        ret = odict()
        # TODO make lexer include a (len(txt), None) pair, then this is a for
        # loop
        # TODO ctx needs to fork() everywhere
        try:
            end, close = cuts.next()
        except(StopIteration):
            end, close = len(lexed.txt) + 1, None
        subfmt = lexed.txt[ctx.ind:end]

        if ctx.match == ']':
            if close != ']':
                raise Exception('unclosed bracket')
            ctx.ind = end + 1
            ctx.dep -= 1
            return subfmt

        elif close == '[':
            subctx = ctx.fork()
            subctx.ind = end + 1
            subctx.dep += 1
            subctx.match = lexed.delims[close]
            name = self.rec_lex(lexed, subctx, cuts)
            ctx.ind = subctx.ind
            ret[name] = ret[len(ret)]
            del ret[len(ret) - 1]

        elif close is None:
            if ctx.dep != 0:
                raise Exception('unclosed parens')
            if s.calcsize(ctx.end + subfmt) > 0:
                ret.append(s.struct(ctx.end + subfmt))
            return ret

        elif subfmt.isdigit():
            ctx.ind = end + 1
            ctx.dep += 1
            ctx.match = lexed.delims[close]
            ret.append(list(self.rec_lex(lexed, ctx, cuts)) * int(subfmt))

        elif close == ctx.match:
            if s.calcsize(subfmt) > 0:
                ret.append(ctx.end + subfmt)
            ctx.ind = end + 1
            ctx.dep -= 1
            return ret

        # NOTE I think the rest of this is garbage
        if lexed.txt[ctx.ind].isdigit():
            ret.append(self.lex_list(lexed, ctx, cuts))
            i = ctx.ind + 1
            while not lexed.txt[i].isdigit():
                i += 1
            reps = int(lexed.txt[ctx.ind:i])
        subfmt = ctx.end + lexed.txt[0:lexed.cuts[0][0]]
        if len(s.calcsize(subfmt) > 0):
            ret.append(subfmt)


    def _rec_build(self, order, fmt, depth):
        ret = odict()
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
        ret = odict()
        for k in fmt_tree:
            st = fmt_tree[k]
            if hasattr(st, 'unpack'):
                unpacked = st.unpack(buff.read(st.size))
            else:
                unpacked = self._rec_unpack(buff, st)
            if len(unpacked) > 0:
                ret.append(unpacked)
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

class odict(OrderedDict):
    def append(self, val):
        self.__setitem__(len(self), val)

    def __repr__(self):
        return '{' + ', '.join([self._fmt(k, self[k]) for k in self]) + '}'

    def _fmt(self, k, v):
        if isinstance(k, int):
            return str(v)
        return k + ': ' + str(v)

class context:
    def __init__(self, index=0, depth=0, endianness='@'):
        self.ind, self.dep, self.end = index, depth, endianness
        self.match = None
    # TODO implement .fork()

class lexer:
    def __init__(self, txt, comment='#', delims='()[]'):
        self.txt = self.strip_comments(txt, comment)
        self.txt = self.txt.replace(' ', '').replace('\n', '').replace('\t', '')
        self.cuts = [(n, char) for n, char in enumerate(self.txt)
                     if char in delims]
        self.delims = dict(zip(delims[::2], delims[1::2]))

    def strip_comments(self, txt, comment='#'):
        lines = txt.split('\n')
        for i, line in enumerate(lines):
            if comment in line:
                lines[i] = line[:line.index(comment)]
        return '\n'.join(lines)

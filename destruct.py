import struct as s
from collections import OrderedDict

class Struct:
    ''' Extended Structs, with fancier format strings!

        Format string is a strict superset of the struct format strings. Use
        parens '(' and ')' to delimit lists (arrays). Use brackets '[' and ']'
        to enclose a name for the immediately previous 'parse unit'. Names
        should (I would say must, but it's not properly enforced yet) be
        alphanumeric.'''
    def __init__(self, fmt, funcs={}):
        self.funcs = funcs
        self.fmt = self.lex_build(lexer(fmt))

    def lex_build(self, lexed):
        cuts = iter(lexed.cuts)
        ctx = context()
        if lexed.txt[ctx.ind] in '@=<>!':
            # going to want to distribute the byte order to sub-strings
            ctx.end = lexed.txt[ctx.ind]
            ctx.ind += 1
        return self._rec_lex(lexed, ctx, cuts)

    def _rec_lex(self, lexed, ctx, cuts):
        ret = odict()
        # I have a few compiler/language books in my reading queue. I assume
        # once I've read those, I'll want to tear this right up and do it
        # proper. Oh well, go with this for now.
        # TODO can this functionality be broken up, with _rec_lex just acting as
        # a dispatcher?
        for end, delim in cuts:
            subfmt = lexed.txt[ctx.ind:end]

            if ctx.match == ']':
                # subfmt is a name, we just return it
                if delim != ']':
                    raise Exception('unclosed bracket')
                ctx.ind = end + 1
                ctx.dep -= 1
                return subfmt

            elif delim == '[':
                if s.calcsize(subfmt) > 0:
                    ret.extend(self._struct(ctx.end, subfmt))
                # get the name, apply it to the last member of ret
                subctx = ctx.fork(end+1, lexed.delims[delim])
                name = self._rec_lex(lexed, subctx, cuts)
                ctx.ind = subctx.ind
                # this will fail if the member already has a name
                # FIXME that is correct, but it won't be friendly
                ret[name] = ret[len(ret) - 1]
                del ret[len(ret) - 2]

            elif delim == '(':
                if s.calcsize(subfmt) > 0:
                    ret.extend(self._struct(ctx.end, subfmt))
                subctx = ctx.fork(end+1, lexed.delims[delim])
                ret.append(self._rec_lex(lexed, subctx, cuts))
                ctx.ind = subctx.ind

            elif delim is None:
                # at the end of the format string, so should not be nested at
                # all
                if ctx.dep != 0:
                    raise Exception('unclosed parens')
                if s.calcsize(ctx.end + subfmt) > 0:
                    ret.extend(self._struct(ctx.end, subfmt))
                return ret

            elif delim == '$':
                if s.calcsize(ctx.end + subfmt) > 0:
                    ret.extend(self._struct(ctx.end, subfmt))
                i, c = cuts.next()
                ctx.ind = i + 1
                if c != '$':
                    raise Exception('brackets not allowed in $$')
                ret.append(self.funcs[lexed.txt[end + 1:i]])

            elif subfmt.isdigit():
                # subfmt is a repetition count for the next portion of the
                # format string
                ctx.ind = end + 1
                ctx.dep += 1
                ctx.match = lexed.delims[delim]
                repeated = self._rec_lex(lexed, ctx, cuts)
                for i in range(int(subfmt)):
                    ret.append(repeated)

            elif delim == ctx.match:
                # we are about to pop out of our current level
                if s.calcsize(subfmt) > 0:
                    ret.extend(self._struct(ctx.end, subfmt))
                ctx.ind = end + 1
                ctx.dep -= 1
                return ret

    def _struct(self, endian, fmt):
        # not pretty, but can be improved later
        # need to split up a classical format string into individual fields so
        # that (a) their indices work out as expected in the output odict, and
        # (b) naming only binds to the last unit of a string. Grouping can still
        # be done using parens, it's just not assumed.
        ret = []
        count = 0
        for c in fmt:
            if c.isdigit():
                count = 10 * count + int(c)
            else:
                if count == 0:
                    count = 1
                if c == 's':
                    # a number preceeding `s` is a length, not a repetition
                    ret.append(s.Struct(endian + str(count) + c))
                else:
                    ret.extend([s.Struct(endian + c)] * count)
                count = 0
        return ret

    def unpack(self, buff):
        # buff needs to be a destruct.buf subclass
        # TODO can this be more duck-typing and less strict-inheritance
        if not issubclass(buff.__class__, buf):
            buff = strbuf(buff)
        return self._rec_unpack(buff, self.fmt)

    def _rec_unpack(self, buff, fmt_tree):
        ret = odict()
        for k in fmt_tree:
            st = fmt_tree[k]
            if hasattr(st, 'unpack'):
                unpacked = st.unpack(buff.read(st.size))
            elif callable(st):
                unpacked = st(buff)
            else:
                unpacked = self._rec_unpack(buff, st)
            if len(unpacked) > 0:
                # TODO ugly shit here, also there may be legit cases for this
                if type(unpacked) is tuple and len(unpacked) == 1:
                    unpacked = unpacked[0]
                # don't keep the key for a positionally-keyed value. Don't-care
                # bytes (`x`) in a format string are dropped on the output, so
                # the counting can be put off.
                if type(k) is int:
                    ret.append(unpacked)
                # This does mean that internal fmt representative will not line
                # up with output structure (eg <odict>.fmt[3] may not be the
                # element that output <odict>.unpack(<str>)[3]). Consider
                # <odict>.fmt an implementation detail, unpacked output is
                # ordered according to the format string passed at construction.
                else:
                    ret[k] = unpacked
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
    # extension of an OrderedDict. Values can be added without keys, they will
    # be assigned a positional value as a key. ie if len(<odict>) = n,
    # <odict>.append(val) <=> <odict.[n] = val. Otherwise, as convention, use
    # alphanumeric strings as keys.
    # TODO may want to add positional lookup, even for keyed values. Wouldn't be
    # hard, <odict>.__getitem__(n) = <odict>.values()[n]
    @staticmethod
    def from_list(ls):
        return odict(enumerate(ls))

    # add in .append() and .extend() so that it can act kind of list-like.
    def append(self, val):
        self.__setitem__(len(self), val)

    def extend(self, ls):
        for i in ls:
            self.append(i)

    def __repr__(self):
        return '{' + ', '.join([self._fmt(k, self[k]) for k in self]) + '}'

    def _fmt(self, k, v):
        # values with positional keys don't need the keys printed in __repr__
        if isinstance(k, int):
            return repr(v)
        return k + ': ' + repr(v)

class context:
    def __init__(self, index=0, depth=0, endianness='@'):
        self.ind, self.dep, self.end = index, depth, endianness
        self.match = None

    def fork(self, index, newmatch):
        ret = context(index, self.dep + 1, self.end)
        ret.match = newmatch
        return ret

class lexer:
    def __init__(self, txt, comment='#', delims='()[]$$'):
        # TODO re-work this part so that we can deliver helpful error messages
        # (with line numbers, original context, etc)
        self.txt = self.strip_comments(txt, comment)
        self.txt = self.txt.replace(' ', '').replace('\n', '').replace('\t', '')
        self.cuts = [(n, char) for n, char in enumerate(self.txt)
                     if char in delims]
        # add in a None tag to signal EOF
        self.cuts.append((len(self.txt), None))
        # for now, delimiters need to be passed in matched pairs. Just easier
        # for the end user than a dict, I think.
        self.delims = dict(zip(delims[::2], delims[1::2]))

    def strip_comments(self, txt, comment='#'):
        lines = txt.split('\n')
        for i, line in enumerate(lines):
            if comment in line:
                lines[i] = line[:line.index(comment)]
        return '\n'.join(lines)

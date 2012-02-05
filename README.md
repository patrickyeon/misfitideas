File Format Reversing Tidbits
=============================
I'm interested in reversing file formats. While I get the hang of things, I'll be throwing little snippets of code that prove to be handy or have some promise into this repo. In the spirit of Fred Brooks' "Build one to throw away" advice, these are all for throwing away.

destruct.py
-----------
Extends Python's struct module, because its format strings seem to force some pretty tedious work. For example, imagine a score record (42 game season) stored in a file that can be handled in C with a data structure like this:

```#pragma pack(1)
struct scorecard{
    char player_name[40];
	uint32_t player_id;
	uint8_t game_points[42];
	uint32_t ranking;
}
```

```data = struct.unpack('=40sI42BI', raw_string)
player_name, player_id, games, ranking = data[0], data[1], data[2:-1], data[-1]
```

But really, what I want to do there is:

```player_name, player_id, games, ranking = destruct.unpack('=40sI(42B)I', raw_string)```

I expect it would get more useful as you see more complex data types. I also treat this as a step towards figuring out what would work for a more comprehensive format description grammar.

* Tests? Yeah, yeah, they're next on the to-do list. Just wanted the idea out there.
* I'm undecided about repetition counts applying to parens
* See TODOs in the file for even more design indecision
* A format string like `=40s[name]I[id](42B)[games]I[ranking]` with an `unpack()` that returned a dict is a further development I'd like to play with.

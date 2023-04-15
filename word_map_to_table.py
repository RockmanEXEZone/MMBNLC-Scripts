# Convert word_utf_*.map files in \exe*\data\msg to standard .tbl table file.
# The resulting output table file is encoded as UTF-8.
#
# Usage:
#     python word_map_to_table.py <map_file> <tbl_file>
#
# Example:
#     python word_map_to_table.py word_utf_eng.map word_utf_eng.tbl
#     Converts word_utf_eng.map to word_utf_eng.tbl.

from argparse import ArgumentParser
from pathlib import Path
import struct

parser = ArgumentParser()
parser.add_argument('map_file', type=Path)
parser.add_argument('tbl_file', type=Path)
args = parser.parse_args()

with open(args.map_file, 'rb') as map_f, open(args.tbl_file, 'w', encoding='utf-8') as tbl_f:
    # Read header
	count, = struct.unpack_from('<H', map_f.read(2))

	for i in range(count):
		char, utf16 = struct.unpack_from('<H2s', map_f.read(4))
		char += 0x6400
		utf16 = utf16.decode('utf-16-le', 'backslashreplace')
		tbl_f.write(f'{char:02X}={utf16}\n')

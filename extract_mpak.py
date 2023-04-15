# Extract a pair of .map and .mpak files in /exe/data/*/data/msg
#
# Note: 0x8000000 is subtracted from the resulting filenames.
#
# Usage:
#    python extract_mpak.py <map_file> <mpak_file> <out_folder>
#
# Example:
#    python extract_mpak.py message_eng.map message_eng.mpak message_eng
#    Extracts all files in message_eng.mpak using message_eng.map.
#    The extract files are placed in folder message_eng.

from argparse import ArgumentParser
from dataclasses import dataclass
from pathlib import Path
from typing import ClassVar, Type, TypeVar
import io
import struct

T = TypeVar('T')

parser = ArgumentParser()
parser.add_argument('map_file')
parser.add_argument('mpak_file')
parser.add_argument('out_folder', type=Path)
args = parser.parse_args()

@dataclass
class MapHeader:
	_struct: ClassVar[str] = '<III'
	count: int
	rom_addr_min: int
	rom_addr_max: int

@dataclass
class MapEntry:
	_struct: ClassVar[str] = '<III'
	rom_addr: int
	mpak_addr: int
	mpak_size: int

def read_from_stream(type : Type[T], stream : io.BufferedReader) -> T:
	size = struct.calcsize(type._struct)
	data = struct.unpack_from(type._struct, stream.read(size))
	return type(*data)

args.out_folder.mkdir(exist_ok=True)

with open(args.map_file, 'rb') as map_f, open(args.mpak_file, 'rb') as mpak_f:
	header = read_from_stream(MapHeader, map_f)

	for i in range(header.count):
		entry = read_from_stream(MapEntry, map_f)

		mpak_f.seek(entry.mpak_addr)
		data = mpak_f.read(entry.mpak_size)

		id = f'{entry.rom_addr & 0xFFFFFF:6X}';
		file = f'{id}.msg'
		path = Path(args.out_folder, file)
		print(f'Extracting {file}')
		with open(path, 'wb') as msg_f:
			msg_f.write(data)

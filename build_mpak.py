# Build a pair of .map and .mpak files in /exe/data/*/data/msg
# using an existing .map file as reference.
# The files are inserted in the same order that they were in the reference file.
#
# Note: 0x8000000 is added to the inserted filenames.
#
# Usage:
#    python build_mpak.py <map_file_ref> <map_file> <mpak_file> <in_folder>
#    Note: <map_file_ref> and <map_file> can be the same file.
#
# Example:
#    python build_mpak.py message_eng.map message_eng.map message_eng.mpak message_eng
#    Take the files in folder message_eng and build a pair of message_eng.map
#    and message_eng.mpak files, using an existing message_eng.map as reference.

from argparse import ArgumentParser
from dataclasses import dataclass
from pathlib import Path
from typing import ClassVar, Type, TypeVar
import io
import struct

T = TypeVar("T")

parser = ArgumentParser()
parser.add_argument('map_file_ref')
parser.add_argument('map_file')
parser.add_argument('mpak_file')
parser.add_argument('in_folder', type=Path)
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
	file: str = None

def read_from_stream(type : Type[T], stream : io.BufferedReader) -> T:
	size = struct.calcsize(type._struct)
	data = struct.unpack_from(type._struct, stream.read(size))
	return type(*data)

in_files : list[Path] = list(args.in_folder.glob('*.msg'))
entries : list[MapEntry] = []
ref_entries : list[MapEntry] = []

with open(args.map_file_ref, 'rb') as map_f:
	header = read_from_stream(MapHeader, map_f)

	for i in range(header.count):
		ref_entries.append(read_from_stream(MapEntry, map_f))

for in_file in in_files:
	id = in_file.stem
	rom_addr = 0x8000000 + int(id, 16)
	entries.append(MapEntry(rom_addr, 0, in_file.stat().st_size, in_file))

rom_addr_min = min(entries, key=lambda x: x.rom_addr).rom_addr
rom_addr_max = max(entries, key=lambda x: x.rom_addr).rom_addr
header = MapHeader(len(entries), rom_addr_min, rom_addr_max)

with open(args.map_file, 'wb') as map_f, open(args.mpak_file, 'wb') as mpak_f:
	map_f.write(struct.pack('<III', header.count, header.rom_addr_min, header.rom_addr_max))

	for ref_entry in ref_entries:
		entry = [x for x in entries if x.rom_addr == ref_entry.rom_addr][0]
		entry.mpak_addr = mpak_f.tell()
		#print(f'0x{ref_entry.rom_addr:8X}, 0x{ref_entry.mpak_addr:8X}, 0x{ref_entry.mpak_size:8X} -> 0x{entry.rom_addr:8X}, 0x{entry.mpak_addr:8X}, 0x{entry.mpak_size:8X}')

		with open(entry.file, 'rb') as f:
			data = f.read()
			mpak_f.write(data)

	for ref_entry in ref_entries:
		entry = [x for x in entries if x.rom_addr == ref_entry.rom_addr][0]
		print(f'0x{ref_entry.rom_addr:8X}, 0x{ref_entry.mpak_addr:8X}, 0x{ref_entry.mpak_size:8X} -> 0x{entry.rom_addr:8X}, 0x{entry.mpak_addr:8X}, 0x{entry.mpak_size:8X}')
		map_f.write(struct.pack('<III', entry.rom_addr, entry.mpak_addr, entry.mpak_size))

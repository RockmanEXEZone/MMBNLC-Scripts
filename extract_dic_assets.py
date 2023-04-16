# Extract files listed in .dic files from .srl files.
#
# Usage:
#    python extract_dic_assets.py <dic_file> <srl_file> <out_folder>
#
# Example:
#    python extract_dic_assets.py rom.dic rom.srl out
#    Extracts all files listed in rom.dic from rom.srl to out folder

from argparse import ArgumentParser
from dataclasses import dataclass
from pathlib import Path
from typing import ClassVar, Type, TypeVar
import os
import io
import struct
import zlib

T = TypeVar('T')

parser = ArgumentParser()
parser.add_argument('dic_file', type=Path)
parser.add_argument('srl_file', type=Path)
parser.add_argument('out_folder', type=Path)
parser.add_argument('--adjust_names', action='store_true', help='Removes _ADRS from the file name and assumes the file extention is after the final underscore.')
args = parser.parse_args()

@dataclass
class DicEntry:
	_struct: ClassVar[str] = '<IIIIII'
	filename_crc32: int
	rom_addr: int
	unk08: int
	total_size_sum: int
	unk10: int
	file_size: int

def read_from_stream(type : Type[T], stream : io.BufferedReader) -> T:
	size = struct.calcsize(type._struct)
	data = struct.unpack_from(type._struct, stream.read(size))
	return type(*data)

os.makedirs(args.out_folder, exist_ok=True)
adjust_names = args.adjust_names
with open(args.dic_file, 'rb') as dic_f, open(args.srl_file, 'rb') as srl_f:
	file_info_lookup = {}
	total_size = 0
	while struct.unpack('<I', dic_f.peek(4)[:4])[0] != 0:
		entry = read_from_stream(DicEntry, dic_f)
		file_info_lookup[entry.filename_crc32] = entry
		# if total_size != entry.total_size_sum:
		# 	print("Total size doesnt match file size sums")
		total_size = total_size + entry.file_size
		total_size = (total_size + 3) & ~3
	dic_f.read(4)
	entry_count = struct.unpack('<I', dic_f.read(4)[:4])[0]
	for i in range(entry_count):
		entry_name = bytearray()
		while True:
			b = dic_f.read(1)
			if b == b'\0':
				break
			entry_name += b
		entry_name_crc32 = zlib.crc32(entry_name)
		entry_name = entry_name.decode()
		if adjust_names:
			entry_name = ".".join(entry_name.replace("_ADRS", "").rsplit("_", 1))
		file_info = file_info_lookup[entry_name_crc32]
		srl_f.seek(file_info.rom_addr - 0x08000000)
		with open(f"{args.out_folder}/{entry_name}", "wb") as out_f:
			out_f.write(srl_f.read(file_info.file_size))
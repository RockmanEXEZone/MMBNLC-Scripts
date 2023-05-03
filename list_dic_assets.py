# Lists files listed in .dic files in a comma separated text format
#
# Usage:
#    python extract_dic_assets.py <dic_file> <out_file>
#
# Example:
#    python extract_dic_assets.py rom.dic rom_dic.csv
#    Lists: the label crc32, rom address, file size, and label for all files in in rom.dic to a comma separated format

from argparse import ArgumentParser
from dataclasses import dataclass
from pathlib import Path
from typing import ClassVar, Type, TypeVar
import io
import struct
import zlib

T = TypeVar('T')

parser = ArgumentParser()
parser.add_argument('dic_file', type=Path)
parser.add_argument('out_file', type=Path)
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

with open(args.dic_file, 'rb') as dic_f:
	file_info_lookup = {}
	total_size = 0
	containsNames = True
	while True:
		entry = read_from_stream(DicEntry, dic_f)
		file_info_lookup[entry.filename_crc32] = entry
		# if total_size != entry.total_size_sum:
		# 	print("Total size doesnt match file size sums")
		total_size = total_size + entry.file_size
		total_size = (total_size + 3) & ~3
		peekValue = dic_f.peek(4)[:4]
		# Check if the end of the stream was reached
		if peekValue == b'':
			containsNames = False
			break
		# Check if this section is over
		if struct.unpack('<I', peekValue)[0] == 0:
			break
	with open(args.out_file, "w") as out_f:
		if containsNames:
			out_f.write("label_crc32,rom_addr,file_size,label\n")
			#parse the name section and output using that
			dic_f.read(4)
			entry_count = struct.unpack('<I', dic_f.read(4)[:4])[0]
			namesFound = dic_f.peek(1)
			for i in range(entry_count):
				entry_name = bytearray()
				while True:
					b = dic_f.read(1)
					if b == b'\0':
						break
					entry_name += b
				entry_name_crc32 = zlib.crc32(entry_name)
				entry_name = entry_name.decode()
				file_info = file_info_lookup[entry_name_crc32]
				out_f.write(f"{file_info.filename_crc32:08X},{file_info.rom_addr:08X},{file_info.file_size:08X},{entry_name}\n")
		else:
			out_f.write("label_crc32,rom_addr,file_size\n")
			for fi in file_info_lookup.values():
				out_f.write(f"{fi.filename_crc32:08X},{fi.rom_addr:08X},{fi.file_size:08X}\n")
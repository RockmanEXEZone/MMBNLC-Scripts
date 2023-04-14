# Extract .dat files in /launcher/data
#
# Usage:
#    python extract_launcher_data.py <dat_file> <out_folder>
#
# Example:
#    python extract_launcher_data.py vol1.dat vol1
#    Extracts all files in vol1.dat to vol1 folder

from argparse import ArgumentParser
from dataclasses import dataclass
from pathlib import Path
from typing import ClassVar, Type, TypeVar
import io
import struct

T = TypeVar('T')

parser = ArgumentParser()
parser.add_argument('dat_file', type=Path)
parser.add_argument('out_folder', type=Path)
args = parser.parse_args()

@dataclass
class Header:
	_struct: ClassVar[str] = '<I'
	count: int

@dataclass
class Entry:
	_struct: ClassVar[str] = '<III'
	unknown: int
	offset: int
	length: int

def read_from_stream(type : Type[T], stream : io.BufferedReader) -> T:
	size = struct.calcsize(type._struct)
	data = struct.unpack_from(type._struct, stream.read(size))
	return type(*data)

args.out_folder.mkdir(exist_ok=True)

with open(args.dat_file, "rb") as dat_f:
	# Read header
	header = read_from_stream(Header, dat_f)

	# Read entries
	entries : list[Entry] = []
	for i in range(header.count):
		entries.append(read_from_stream(Entry, dat_f))

	for i in range(header.count):
		entry = entries[i]
		dat_f.seek(entry.offset)
		data = dat_f.read(entry.length)
		
		# Try to determine file type
		magic1, magic2, magic3, magic4 = struct.unpack_from("<IIII", data)
		ext = 'bin'
		if magic1 == 0x4F54544F:
			 # 'OTTO'
			ext = 'otf'
		elif magic4 == 0x47495344:
			# 'DSIG'
			ext = 'ttf'
		elif magic1 == 0x474E5089:
			# 'PNG'
			ext = 'png'
		elif magic1 == 0xE011CFD0 and magic2 == 0xE11AB1A1:
			# 'D0CF11E' (docfile), thumbs.db in this case
			ext = 'thumbs.db'
		elif magic2 == 0x70797466 and magic3 == 0x3234706D:
			# 'ftypmp42'
			ext = 'mp4'
		
		file = f'{i}.{ext}'
		path = Path(args.out_folder, file)
		print(f'Extracting 0x{entry.unknown:08X} : {file}')
		with open(path, "wb") as f:
			f.write(data)

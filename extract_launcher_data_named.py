# Extract .dat files in /launcher/data with the original file names where available
#
# Usage:
#    python extract_launcher_data_named.py <dat_file> <out_folder> <hash_list>
#
# Example:
#    python extract_launcher_data_named.py vol1.dat vol1 hash_lists/vol1
#    Extracts all files in vol1.dat to vol1 folder

from argparse import ArgumentParser
from dataclasses import dataclass
from pathlib import Path
from typing import ClassVar, Type, TypeVar
import os
import io
import struct

T = TypeVar('T')

parser = ArgumentParser()
parser.add_argument('dat_file', type=Path)
parser.add_argument('out_folder', type=Path)
parser.add_argument('hash_list', type=Path)
args = parser.parse_args()

@dataclass
class Header:
	_struct: ClassVar[str] = '<I'
	count: int

@dataclass
class Entry:
	_struct: ClassVar[str] = '<III'
	filename_hash: int
	offset: int
	length: int

def read_from_stream(type : Type[T], stream : io.BufferedReader) -> T:
	size = struct.calcsize(type._struct)
	data = struct.unpack_from(type._struct, stream.read(size))
	return type(*data)

args.out_folder.mkdir(exist_ok=True)

# Read known file name crc32
filename_hashes : dict[int,str] = {}
with open(args.hash_list, "r") as hash_list_f:
	for line in hash_list_f:
		line_split = line.strip().split("\t", maxsplit = 3)
		if(len(line_split) == 3):
			file_name_crc = int(line_split[1], 16)
			filename_hashes[file_name_crc] = line_split[2]

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
		# Use the original file name for known crc32
		if entry.filename_hash in filename_hashes:
			# Probably not needed but use the os path separator
			file_name = args.out_folder / filename_hashes[entry.filename_hash].replace("/", os.sep)
			os.makedirs(
				os.path.dirname(file_name),
				exist_ok = True
			)
		# use the index for file names with unknown crc32, all unknown files are png files
		else:
			file_name = args.out_folder / f"{i:03d}.png"

		print(f'Extracting {file_name}')
		with open(file_name, "wb") as f:
			f.write(data)

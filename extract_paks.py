# Extract textures from .pak files found in data/ui
#
# Usage:
#    python extract_paks.py <pak_folder> <out_folder>
#
# Example:
#    python extract_paks.py exe1/data/ui exe1_out
#    Extracts textures from .pak files in exe1/data/ui to exe1_out as PNGs

from argparse import ArgumentParser
import struct
from PIL import Image
import io
import os
import glob
from dataclasses import dataclass
from pathlib import Path
from typing import ClassVar, Type, TypeVar


T = TypeVar('T')

parser = ArgumentParser()
parser.add_argument('pak_folder', type=Path)
parser.add_argument('out_folder', type=Path)
args = parser.parse_args()

@dataclass
class PakHeader:
	_struct: ClassVar[str] = '<IBBHHI'
	texture_offset: int
	textureWidth: int
	textureHeight: int
	textureSizeMultiplier: int
	unk1: int
	unk2: int

def read_from_stream(type : Type[T], stream : io.BufferedReader) -> T:
	size = struct.calcsize(type._struct)
	data = struct.unpack_from(type._struct, stream.read(size))
	return type(*data)

os.makedirs(args.out_folder, exist_ok=True)
pak_files = glob.glob(f"{args.pak_folder}/*.pak")
for pak_file in pak_files:
	with open(pak_file, 'rb') as pak_f:
		print(pak_file)
		header = read_from_stream(PakHeader, pak_f)
		pak_f.seek(header.texture_offset)
		width = header.textureWidth * header.textureSizeMultiplier
		height = header.textureHeight * header.textureSizeMultiplier
		texture_length = width * height * 4
		texture_data = pak_f.read(texture_length)
		if(len(texture_data) != texture_length):
			print(f"\033[91mSkipping {pak_file}\033[0m")
			continue
		im2 = Image.frombytes('RGBA', (width, height), texture_data, "raw", "BGRA")
		out_file_name = os.path.basename(pak_file).replace(".pak", ".png")
		im2.save(f"{args.out_folder}/{out_file_name}")
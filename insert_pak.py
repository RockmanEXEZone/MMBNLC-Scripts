# Insert new .png image into existing .pak file found in data/ui
#
# Usage:
#    python insert_pak.py <pak_file_ref> <pak_file> <png_file>
#
# Example:
#    python insert_pak.py folder_name.pak folder_name_out.pak folder_name.png
#    Creates folder_name_out.pak by taking folder_name.pak and inserting
#    folder_name.png into it.

from argparse import ArgumentParser
from pathlib import Path
from PIL import Image
import struct

parser = ArgumentParser()
parser.add_argument('pak_file_ref', type=Path)
parser.add_argument('pak_file', type=Path)
parser.add_argument('png_file', type=Path)
args = parser.parse_args()

pak_file_ref: Path = args.pak_file_ref
pak_file: Path = args.pak_file
png_file: Path = args.png_file

bmp = Image.open(png_file).convert('RGBA')

# Read data from old .pak file
with open(pak_file_ref, 'rb') as pak_f:
	tex_addr, = struct.unpack_from('<I', pak_f.peek(4))
	data = pak_f.read(tex_addr)

# Build new .pak using old data and new image
with open(pak_file, 'wb') as pak_f:
    pak_f.write(data)
    pak_f.write(bmp.tobytes('raw', 'BGRA'))

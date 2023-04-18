# Builds a .fnt file from a folder with resources and information.
#
# The folder is expected to contain the following:
#  *  bmp - Folder containing raw bitmaps from which glyphs are drawn
#  *  info.json - Info about font file
#  *  glyphs.json - Glyph settings (converted from bounding box to x,y,w,h)
#  *  table.tbl - (For font with table) Table file
# Any other files and/or folders are not used.
#
# Usage:
#     python build_font <in_folder> <fnt_file>
#
# Example:
#     python build_font eng_mojiFont eng_mojiFont.fnt
#     Build eng_mojiFont.fnt from folder named eng_mojiFont

from argparse import ArgumentParser
from dataclasses import dataclass, field
from pathlib import Path
from PIL import Image
from typing import ClassVar, Optional
import json
import numpy
import struct

parser = ArgumentParser()
parser.add_argument('in_folder', type=Path)
parser.add_argument('font_file', type=Path)
args = parser.parse_args()

@dataclass
class FontHeader:
	_struct: ClassVar[str] = '<IHHHHHH'
	magic: int
	unk04: int
	glyph_map_count: int
	glyph_count: int
	unk0A: int
	unk0C: int
	unk0E: int

	placeholder_glyph: Optional[int | None] = None

@dataclass
class GlyphEntry:
	bmp_idx: int
	draw_x0: float
	draw_y0: float
	draw_x1: float
	draw_y1: float
	bmp_x0: float
	bmp_y0: float
	bmp_x1: float
	bmp_y1: float
	x_adv: float
	chars: list[str]

@dataclass
class Bucket:
	_struct: ClassVar[str] = '<HHHH'
	map_idx: int
	zero: int
	char_offset: int
	char_count: int

	chars: Optional[list[int]] = field(default_factory=list)
	glyphs: Optional[list[int]] = field(default_factory=list)

in_folder: Path = args.in_folder
font_file: Path = args.font_file

# Read info file
info_file = Path(in_folder, 'info.json')
with open(info_file, 'r', encoding='utf-8') as info_f:
	info_json = json.load(info_f)
header = FontHeader(magic=0x746E6F66, glyph_count=0, glyph_map_count=0, **info_json)

# Read bitmaps
bmp_files = list(Path.glob(Path(in_folder, 'bmp'), '*.png'))
bmps: list[Image.Image] = []
for bmp_file in bmp_files:
	bmp = Image.open(bmp_file)
	bmps.append(bmp)

# Read glyphs
glyph_file = Path(in_folder, 'glyphs.json')
glyphs: list[GlyphEntry] = []
with open(glyph_file, 'r', encoding='utf-8') as glyph_f:
	glyphs_json = json.load(glyph_f)
for glyph_json in glyphs_json:
	bmp_idx = glyph_json['bmp_idx']
	bmp_flags = glyph_json['bmp_flags']
	dx0 = glyph_json['draw_x']
	dy0 = glyph_json['draw_y']
	dx1 = dx0 + glyph_json['draw_w']
	dy1 = dy0 + glyph_json['draw_h']
	bx0 = glyph_json['bmp_x']
	by0 = glyph_json['bmp_y']
	bx1 = bx0 + glyph_json['bmp_w']
	by1 = by0 + glyph_json['bmp_h']
	x_adv = glyph_json['x_adv']
	chars = glyph_json['chars']

	bmp = bmps[bmp_idx]
	dx0 = numpy.float16(dx0)
	dy0 = numpy.float16(dy0)
	dx1 = numpy.float16(dx1)
	dy1 = numpy.float16(dy1)
	bx0 = numpy.float16(bx0 / bmp.width)
	by0 = numpy.float16(by0 / bmp.height)
	bx1 = numpy.float16(bx1 / bmp.width)
	by1 = numpy.float16(by1 / bmp.height)
	x_adv = numpy.float16(x_adv)

	glyph_entry = GlyphEntry(
		bmp_idx | bmp_flags, dx0, dy0, dx1, dy1, bx0, by0, bx1, by1, x_adv, chars)
	glyphs.append(glyph_entry)

# Read table file
tbl_file = Path(in_folder, 'table.tbl')
table: list[int] | None = None
if tbl_file.exists():
	table = []
	with open(tbl_file, 'r', encoding='utf-8') as tbl_f:
		lines = tbl_f.read().splitlines()
	for line in lines:
		if len(line) == 0:
			continue
		split = line.split('=')
		k = int(split[0], 16)
		while len(table) <= k:
			table.append(0)
		utf16, = struct.unpack_from('<H', split[1].encode('utf-16-le'))
		table[k] = utf16

# Build buckets and glyph map
buckets: list[Bucket] = []
glyph_map: list[int] = []
for bucket_idx in range(0x100):
	buckets.append(Bucket(0, 0, 0, 0))
for glyph_idx in range(len(glyphs)):
	glyph_entry = glyphs[glyph_idx]
	for char in glyph_entry.chars:
		utf16, = struct.unpack_from('<H', char.encode('utf-16-le'))
		buckets[utf16 >> 8].chars.append(utf16)
		buckets[utf16 >> 8].glyphs.append(glyph_idx)
for bucket_idx in range(0x100):
	bucket = buckets[bucket_idx]
	if len(bucket.chars) == 0:
		continue
	bucket.map_idx = len(glyph_map)
	bucket.zero = 0
	bucket.char_offset = min(bucket.chars) - (bucket_idx << 8)
	for i in range(min(bucket.chars), max(bucket.chars)+1):
		if i in bucket.chars:
			idx = bucket.chars.index(i)
			glyph_map.append(bucket.glyphs[idx])
		else:
			glyph_map.append(header.placeholder_glyph)
	bucket.char_count = len(glyph_map) - bucket.map_idx

header.glyph_map_count = len(glyph_map)
header.glyph_count = len(glyphs_json)
with open(font_file, 'wb') as font_f:
	font_f.write(struct.pack(FontHeader._struct,
			  header.magic,
			  header.unk04,
			  header.glyph_map_count,
			  header.glyph_count,
			  header.unk0A,
			  header.unk0C,
			  header.unk0E))
	
	for bucket in buckets:
		font_f.write(struct.pack(Bucket._struct,
	      bucket.map_idx,
		  bucket.zero,
		  bucket.char_offset,
		  bucket.char_count))
	
	for g in glyph_map:
		font_f.write(struct.pack('<H', g))
	
	for glyph_entry in glyphs:
		font_f.write(struct.pack('<H', glyph_entry.bmp_idx))
		font_f.write(numpy.float16(glyph_entry.draw_x0).tobytes())
		font_f.write(numpy.float16(glyph_entry.draw_y0).tobytes())
		font_f.write(numpy.float16(glyph_entry.draw_x1).tobytes())
		font_f.write(numpy.float16(glyph_entry.draw_y1).tobytes())
		font_f.write(numpy.float16(glyph_entry.bmp_x0).tobytes())
		font_f.write(numpy.float16(glyph_entry.bmp_y0).tobytes())
		font_f.write(numpy.float16(glyph_entry.bmp_x1).tobytes())
		font_f.write(numpy.float16(glyph_entry.bmp_y1).tobytes())
		font_f.write(numpy.float16(glyph_entry.x_adv).tobytes())
	
	while font_f.tell() % 4 != 0:
		font_f.write(b'\0')
	
	font_f.write(struct.pack('<I', len(bmps)))
	bmp_address = font_f.tell() + struct.calcsize('<III') * len(bmps)
	for bmp in bmps:
		font_f.write(struct.pack('<III', bmp.width, bmp.height, bmp_address))
		bmp_address += bmp.width * bmp.height * 4
	for bmp in bmps:
		font_f.write(bmp.tobytes('raw', 'BGRA'))
	
	if table is not None:
		font_f.write(struct.pack('<I', len(table)))
		for utf16 in table:
			font_f.write(struct.pack('<H', utf16))

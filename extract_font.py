# Extract resources and information from .fnt file
#
# This produces the following files/folders:
#  *  bmp - Folder containing raw bitmaps from which glyphs are drawn
#  *  glyph - Unscaled glyph images extracted from bitmaps
#  *  tbl - (For font with table) Scaled glyph images indexed by encoding table
#  *  utf16 - (For font without table) Scaled glyph images indexed by UTF-16 codepoint
#  *  info.json - Info about font file
#  *  glyphs.json - Glyph settings (converted from bounding box to x,y,w,h)
#  *  table.tbl - (For font with table) Table file
#
# Usage:
#     python extract_font <fnt_file> <out_folder>
#
# Example:
#     python extract_font eng_mojiFont.fnt eng_mojiFont
#     Extracts eng_mojiFont.fnt to folder named eng_mojiFont

from argparse import ArgumentParser
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from PIL import Image
from typing import ClassVar, Optional, Type, TypeVar
import dataclasses
import io
import json
import math
import numpy
import struct

T = TypeVar("T")

parser = ArgumentParser()
parser.add_argument('font_file', type=Path)
parser.add_argument('out_folder', type=Path)
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
class BitmapEntry:
	_struct: ClassVar[str] = '<III'
	width: int
	height: int
	address: int

@dataclass
class Bucket:
	_struct: ClassVar[str] = '<HHHH'
	map_idx: int
	zero: int
	char_offset: int
	char_count: int

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

	img: Optional[Image.Image] = None

def read_from_stream(type : Type[T], stream : io.BufferedReader) -> T:
	size = struct.calcsize(type._struct)
	data = struct.unpack_from(type._struct, stream.read(size))
	return type(*data)

font_file: Path = args.font_file
out_folder: Path = args.out_folder
Path(out_folder).mkdir(exist_ok=True)

with open(args.font_file, 'rb') as font_f:
	header = read_from_stream(FontHeader, font_f)

	# Read UTF-16 buckets
	buckets: list[Bucket] = []
	for i in range(0x100):
		buckets.append(read_from_stream(Bucket, font_f))

	# Read glyph map
	glyph_map: list[int] = []
	for i in range(header.glyph_map_count):
		m, = struct.unpack_from('<H', font_f.read(2))
		glyph_map.append(m)
	
	# Find most recurring glyph, treat it as placeholder glyph
	# This is a heuristic, but it's good enough
	counter = Counter(glyph_map)
	header.placeholder_glyph = max(glyph_map, key=counter.get)
	
	# Seek to glyphs
	glyphs: list[GlyphEntry] = []
	for i in range(header.glyph_count):
		bmp_idx, = struct.unpack_from('<H', font_f.read(2))
		floats = [float(x) for x in numpy.frombuffer(font_f.read(0x12), dtype=numpy.float16)]
		glyphs.append(GlyphEntry(bmp_idx, *floats))

	# Align to 4
	font_f.seek(math.ceil(font_f.tell() / 4)*4)

	# Read bitmap entries
	bmp_count, = struct.unpack_from('<I', font_f.read(4))
	bmp_entries: list[BitmapEntry] = []
	for i in range(bmp_count):
		bmp_entries.append(read_from_stream(BitmapEntry, font_f))
	
	# Dump bitmaps
	bmp_dir = Path(out_folder, 'bmp')
	bmp_dir.mkdir(exist_ok=True)
	bmp_imgs: list[Image.Image] = []
	for i in range(bmp_count):
		font_f.seek(bmp_entries[i].address)

		w = bmp_entries[i].width
		h = bmp_entries[i].height
		bmp_file = Path(bmp_dir, f'bmp_{i}.png')
		print(f'Extracting {bmp_file}')

		bmp_data = font_f.read(w * h * 4)
		bmp_img = Image.frombytes('RGBA', (w, h), bmp_data, 'raw', 'BGRA')
		bmp_imgs.append(bmp_img)
		bmp_img.save(bmp_file)

		#bmp_noalpha_file = Path(out_folder, f'bmp_{i}_noalpha.png')
		#bmp_noalpha_img = bmp_img.convert('RGB')
		#bmp_noalpha_img.save(bmp_noalpha_file)
	
	# Adjust glyphs
	for i in range(header.glyph_count):
		glyph_entry = glyphs[i]
		bmp_idx = glyph_entry.bmp_idx & 0xFFF
		bmp_entry = bmp_entries[bmp_idx]
		glyph_entry.bmp_x0 = round(glyph_entry.bmp_x0 * bmp_entry.width)
		glyph_entry.bmp_y0 = round(glyph_entry.bmp_y0 * bmp_entry.height)
		glyph_entry.bmp_x1 = round(glyph_entry.bmp_x1 * bmp_entry.width)
		glyph_entry.bmp_y1 = round(glyph_entry.bmp_y1 * bmp_entry.height)

	# Dump glyphs
	glyph_dir = Path(out_folder, 'glyphs')
	glyph_dir.mkdir(exist_ok=True)
	glyphs_json = []
	for i in range(header.glyph_count):
		glyph_entry = glyphs[i]
		bmp_idx = glyph_entry.bmp_idx & 0xFFF
		bmp_entry = bmp_entries[bmp_idx]
		dx0 = glyph_entry.draw_x0
		dy0 = glyph_entry.draw_y0
		dx1 = glyph_entry.draw_x1
		dy1 = glyph_entry.draw_y1
		dw = dx1 - dx0
		dh = dy1 - dy0
		bx0 = glyph_entry.bmp_x0
		by0 = glyph_entry.bmp_y0
		bx1 = glyph_entry.bmp_x1
		by1 = glyph_entry.bmp_y1
		bw = round(bx1 - bx0)
		bh = round(by1 - by0)
		x_adv = glyph_entry.x_adv

		print(f'0x{i:02X}    draw @ ({dx0:5.2f}, {dy0:5.2f}) : {dw:5.2f} x {dh:5.2f}    pixels @ ({bx0:4}, {by0:4}) : {bw:3} x {bh:2}    advance {x_adv:5.2f}')
		glyph_json = {}
		glyph_json['idx'] = i
		glyph_json['bmp_flags'] = glyph_entry.bmp_idx & ~0xFFF
		glyph_json['bmp_idx'] = bmp_idx
		glyph_json['draw_x'] = dx0
		glyph_json['draw_y'] = dy0
		glyph_json['draw_w'] = dw
		glyph_json['draw_h'] = dh
		glyph_json['bmp_x'] = bx0
		glyph_json['bmp_y'] = by0
		glyph_json['bmp_w'] = bw
		glyph_json['bmp_h'] = bh
		glyph_json['x_adv'] = x_adv
		glyph_json['chars'] = []
		glyphs_json.append(glyph_json)

		bmp_file = Path(glyph_dir, f'glyph{i:04}_{i:04X}.png')
		bmp_img = bmp_imgs[bmp_idx]
		glyph_img = Image.new('RGBA', (math.ceil(max(dx1, x_adv)), math.ceil(dy1)))
		if dw != 0 and dh != 0 and bw != 0 and bh != 0:
			bmp_img = bmp_img.crop((bx0, by0, bx1, by1))
			bmp_img.save(bmp_file)
			bmp_img = bmp_img.resize((int(round(dw)), int(round(dh))))
			glyph_img.alpha_composite(bmp_img, (round(dx0), round(dy0)))
			glyph_entry.img = glyph_img

	# Dump by table if it exists
	have_table = len(font_f.peek(1)) != 0
	if have_table:
		count_table, = struct.unpack_from('<I', font_f.read(4))
		table: list[int] = []
		tbl_file = Path(out_folder, 'table.tbl')
		with open(tbl_file, 'w', encoding='utf-8') as tbl_f:
			for i in range(count_table):
				utf16, = struct.unpack_from('<2s', font_f.read(2))
				table.append((utf16[0]) | (utf16[1] << 8))
				#char = 0x6400 + i
				utf16 = utf16.decode('utf-16-le', 'backslashreplace')
				tbl_f.write(f'{i:X}={utf16}\n')
		
		# Dump table chars
		tbl_dir = Path(out_folder, 'tbl')
		tbl_dir.mkdir(exist_ok=True)
		for i in range(len(table)):
			x = table[i]

			bucket_idx = x >> 8
			bucket = buckets[bucket_idx]
			map_idx = bucket.map_idx + (x & 0xFF) - bucket.char_offset
			glyph_idx = glyph_map[map_idx]
			if glyph_idx == header.placeholder_glyph:
				continue
			glyph_entry = glyphs[glyph_idx]

			#utf16 = struct.pack('<H', x).decode('utf-16-le', 'backslashreplace')
			#glyphs_json[glyph_idx]['chars'].append(utf16)
			print(f'Dumping char {i:04X} = UTF16 {x:04X} = map {map_idx:04X} = glyph {glyph_idx:04X}')

			bmp_file = Path(tbl_dir, f'tbl{i:04}_{i:04X}.png')
			if glyph_entry.img is not None:
				glyph_entry.img.save(bmp_file)
	
	# Also dump by UTF-16
	utf16_dir = Path(out_folder, 'utf16')
	utf16_dir.mkdir(exist_ok=True)
	got_placeholder = False
	for bucket_idx in range(0x100):
		bucket = buckets[bucket_idx]
		for i in range(bucket.char_count):
			char = (bucket_idx << 8) | (bucket.char_offset + i)
			
			map_idx = bucket.map_idx + i
			glyph_idx = glyph_map[map_idx]
			glyph_entry = glyphs[glyph_idx]

			utf16 = struct.pack('<H', char).decode('utf-16-le', 'backslashreplace')
			glyphs_json[glyph_idx]['chars'].append(utf16)
			if glyph_idx == header.placeholder_glyph and got_placeholder:
				continue
			got_placeholder = True
			print(f'Dumping UTF16 {char:04X} = map {map_idx:04X} = glyph {glyph_idx:04X}')

			bmp_file = Path(utf16_dir, f'char{char:04}_{char:04X}.png')
			if glyph_entry.img is not None:
				glyph_entry.img.save(bmp_file)

	glyph_file = Path(out_folder, 'glyphs.json')
	with open(glyph_file, 'w', encoding='utf-8') as glyph_f:
		json.dump(glyphs_json, glyph_f, indent=4)
	
	# Dump metadata
	info_file = Path(out_folder, 'info.json')
	with open(info_file, 'w', encoding='utf-8') as info_f:
		header_json = dataclasses.asdict(header)
		del header_json['magic']
		del header_json['glyph_map_count']
		del header_json['glyph_count']
		json.dump(header_json, info_f, indent=4)

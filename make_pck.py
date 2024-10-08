# Generates a .pck file for Mega Man Battle Network Legacy Collection Vol 1/2 from a list of .wem files
# The IDs for each wem file is automatically generated to match IDs generated by make_bnk.py
#
# Usage:
#    python make_pck.py wem_table pck_file
#
# Example:
#    python make_pck.py wem_table.txt output_pck.pck
#    Takes the list of wem files from wem_table.txt and generates a pck file named output_pck.pck
#    Each line in wem_table.txt is a tab separated entry in the format:
#    [language_id] [wem_path]
#    sound type could either be the numeric language_id or SFX, JPN, CHN, ENG.


from argparse import ArgumentParser
from dataclasses import dataclass
from pathlib import Path

@dataclass(slots=True)
class MediaEntry:
    hash : int
    language_id: int
    wem_filename : str
    offset : int
    size : int

def compute_hash(name: str) -> int:
    hash = 2166136261
    name = name.lower()
    for c in name:
        hash = ((hash * 16777619) ^ ord(c)) & 0xFFFFFFFF
    return hash

parser = ArgumentParser(
    prog = "make_pck",
    description = "generates a .pck file for Mega Man Battle Network Legacy Collection Vol 1/2 from a list of .wem files"
)
parser.add_argument(
    'wem_table', type=str,
    help = "a list of wem file entries to include. Each row in the file should be tab separated in the format: (language_id) (wem_filename). language_id can be eitehr the numeric id for the language or SFX, JPN, CHN, ENG"
)
parser.add_argument(
    'pck_file', type=Path,
    help = "the output pck file."
)
args = parser.parse_args()

media_file_lookup : dict[int, MediaEntry] = {}

with open(args.wem_table) as wem_table:
    for i, line in enumerate(wem_table):
        line_split = line.strip().split('\t')
        language_id_str = line_split[0]
        wem_path = line_split[1]
        hash = compute_hash(wem_path)
        if language_id_str.isnumeric():
            language_id = int(language_id_str)
        else:
            langauge_id_lookup = {
                "SFX": 0,
                "JPN": 1,
                "CHN": 2,
                "ENG": 3,
            }
            if language_id_str in langauge_id_lookup:
                language_id = langauge_id_lookup[language_id_str]
            else:
                print(f"Invalid language ID on line {i}\n")

        if hash in media_file_lookup:
            print(f"{media_file_lookup[hash].wem_filename} is already used.")
            exit(1)
        media_file_lookup[hash] = MediaEntry(
            hash = hash,
            wem_filename = wem_path,
            language_id = language_id,
            offset = -1,
            size = -1
        )

# IDs / Hashes need to be sorted in ascending order or the lookup fails
wem_hashes = list(media_file_lookup.keys())
wem_hashes.sort()

num_wem = len(media_file_lookup)
wem_offset = 0x8C + num_wem * 20

with open(args.pck_file, "wb") as pck:
    # Write AKPK
    pck.write(b"AKPK")
    # Write Pck header length
    pck.write(wem_offset.to_bytes(length = 4, byteorder="little"))
    # Write next part of header
    pck.write(bytes([
        0x01, 0x00, 0x00, 0x00, # PCK version
        0x68, 0x00, 0x00, 0x00, # Language Map Length
        0x04, 0x00, 0x00, 0x00, # Banks table Length
    ]))
    # Write length of entries
    pck.write((num_wem * 20).to_bytes(length = 4, byteorder="little")) # Stream Table length
    # Write next part of header
    pck.write(bytes([
        0x04, 0x00, 0x00, 0x00, # "externalLUT" Length
        # Language Map
        0x04, 0x00, 0x00, 0x00, #Number of languages
        0x24, 0x00, 0x00, 0x00, 0x02, 0x00, 0x00, 0x00, # Chinese offset + language ID
        0x34, 0x00, 0x00, 0x00, 0x03, 0x00, 0x00, 0x00, # English offset + language ID
        0x4C, 0x00, 0x00, 0x00, 0x01, 0x00, 0x00, 0x00, # Japanese offset + language ID
        0x5E, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, # SFX offset + language ID
        0x63, 0x00, 0x68, 0x00, 0x69, 0x00, 0x6E, 0x00, 0x65, 0x00, 0x73, 0x00, 0x65, 0x00, 0x00, 0x00, # "chinese" string
        0x65, 0x00, 0x6E, 0x00, 0x67, 0x00, 0x6C, 0x00, 0x69, 0x00, 0x73, 0x00, 0x68, 0x00, 0x28, 0x00, 0x75, 0x00, 0x73, 0x00, 0x29, 0x00, 0x00, 0x00, # "english(us)" string
        0x6A, 0x00, 0x61, 0x00, 0x70, 0x00, 0x61, 0x00, 0x6E, 0x00, 0x65, 0x00, 0x73, 0x00, 0x65, 0x00, 0x00, 0x00, # "japanese" string
        0x73, 0x00, 0x66, 0x00, 0x78, 0x00, 0x00, 0x00, # "sfx" string
        0x00, 0x00, # padding
        # Banks table
        0x00, 0x00, 0x00, 0x00, # Number of files
    ]))
    # Stream Table
    # Write number of entries
    pck.write(num_wem.to_bytes(length = 4, byteorder="little"))
    # Skip writing entries and write wem files first
    pck.seek(wem_offset, 0)
    for hash in wem_hashes:
        media_entry = media_file_lookup[hash]
        with open(media_entry.wem_filename, "rb") as wem_file:
            pck.write(wem_file.read())
            wem_len = wem_file.tell()
        media_entry.offset = wem_offset
        media_entry.size = wem_len
        wem_offset += wem_len
    # Go back to write the actual entries
    pck.seek(0x8C, 0)
    for hash in wem_hashes:
        media_entry = media_file_lookup[hash]
        pck.write(hash.to_bytes(length = 4, byteorder = "little"))
        pck.write((1).to_bytes(length = 4, byteorder = "little"))
        pck.write(media_entry.size.to_bytes(length = 4, byteorder = "little"))
        pck.write(media_entry.offset.to_bytes(length = 4, byteorder = "little"))
        pck.write((media_entry.language_id).to_bytes(length = 4, byteorder = "little"))
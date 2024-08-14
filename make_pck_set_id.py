# Generates a .pck file for Mega Man Battle Network Legacy Collection Vol 1/2 from a list of .wem files
# with user chosen IDs. These pck files are meant for asset replacement.
#
# Usage:
#    python make_pck_set_id.py wem_table pck_file
#
# Example:
#    python make_pck_set_id.py wem_table.txt output_pck.pck
#    Takes the list of wem files from wem_table.txt and generates a pck file named output_pck.pck
#    Each line in wem_table.txt is a tab separated entry in the format:
#    [language_id] [id] [wem_path]
#    sound type could either be the numeric language_id or SFX, JPN, CHN, ENG.
#    id is a known WEM_ID for the music being replaced


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


parser = ArgumentParser(
    prog = "make_pck",
    description = "generates a .pck file for Mega Man Battle Network Legacy Collection Vol 1/2 from a list of .wem files"
)
parser.add_argument(
    'wem_table', type=str,
    help = "a list of wem file entries to include. Each row in the file should be tab separated in the format: (language_id) (id) (wem_filename). language_id can be eitehr the numeric id for the language or SFX, JPN, CHN, ENG"
)
parser.add_argument(
    'pck_file', type=Path,
    help = "the output pck file."
)
args = parser.parse_args()

wem_replacements : dict[int, MediaEntry] = {}

with open(args.wem_table) as wem_table:
    for i, line in enumerate(wem_table):
        line_split = line.strip().split('\t')
        language_id_str = line_split[0]
        hash = int(line_split[1])
        wem_path = line_split[2]
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

        if hash in wem_replacements:
            print(f"{hash} is already replaced. Replacing again.")
        wem_replacements[hash] = MediaEntry(
            hash = hash,
            wem_filename = wem_path,
            language_id = language_id,
            offset = -1,
            size = -1
        )

# IDs / Hashes need to be sorted in ascending order or the lookup fails
wem_hashes = list(wem_replacements.keys())
wem_hashes.sort()

num_wem = len(wem_replacements)
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
        media_entry = wem_replacements[hash]
        with open(media_entry.wem_filename, "rb") as wem_file:
            pck.write(wem_file.read())
            wem_len = wem_file.tell()
        media_entry.offset = wem_offset
        media_entry.size = wem_len
        wem_offset += wem_len
    # Go back to write the actual entries
    pck.seek(0x8C, 0)
    for hash in wem_hashes:
        media_entry = wem_replacements[hash]
        pck.write(hash.to_bytes(length = 4, byteorder = "little"))
        pck.write((1).to_bytes(length = 4, byteorder = "little"))
        pck.write(media_entry.size.to_bytes(length = 4, byteorder = "little"))
        pck.write(media_entry.offset.to_bytes(length = 4, byteorder = "little"))
        pck.write((media_entry.language_id).to_bytes(length = 4, byteorder = "little"))
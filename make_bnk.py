# Generates a .bnk file for Mega Man Battle Network Legacy Collection Vol 1/2 from a list of .wem files
#
# Usage:
#    python make_bnk.py [--header_file HEADER_FILE] [--exclude_bgm] wem_table bnk_file
#
# Example:
#    python make_bnk.py wem_table.txt output_bnk.bnk
#    Takes the list of wem files from wem_table.txt and generates a bnk file named output_bnk.bnk
#    Each line in wem_table.txt is a tab separated entry in the format:
#    [sound_type] [wem_path]
#    sound type could either be SFX or BGM for which in game volume control this sound is controlled by.

from argparse import ArgumentParser
from dataclasses import dataclass
import re

@dataclass(slots=True)
class MediaEntry:
    hash : int
    wem_filename : str
    offset : int
    size : int

@dataclass(slots=True)
class SoundEntry:
    hash : int
    wem_hash : int
    wem_type : str

@dataclass(slots=True)
class EventEntry:
    hash : int
    wem_filename : str
    wem_type : str

def compute_hash(name: str) -> int:
    hash = 2166136261
    name = name.lower()
    for c in name:
        hash = ((hash * 16777619) ^ ord(c)) & 0xFFFFFFFF
    return hash

parser = ArgumentParser(
    prog = "make_bnk",
    description = "generates a .bnk file for Mega Man Battle Network Legacy Collection Vol 1/2 from a list of .wem files"
)
parser.add_argument(
    'wem_table', type=str,
    help = "a list of wem file entries to include. Each row in the file should be tab separated in the format: (type) (wem_filename). Type can be eitehr SFX for a sound effect or BGM for music."
)
parser.add_argument(
    'bnk_file', type=str,
    help = "the output bnk file."
)
parser.add_argument(
    '--header_file', type=str,
    help = "outputs a C header file with all the generated event IDs to play the sounds in game."
)
parser.add_argument(
    '--exclude_bgm', action='store_true',
    help = "does not include music in the bnk because they will stored in a pck."
)

args = parser.parse_args()

bnk_out = args.bnk_file
wem_table = args.wem_table
exclude_bgm = args.exclude_bgm

in_sfx_wems : list[str] = []
in_bgm_wems : list[str] = []

with open(wem_table, "r") as wem_table_file:
    for i, line in enumerate(wem_table_file):
        line_split = line.strip().split('\t')
        wem_type = line_split[0].upper()
        wem_path = line_split[1]
        match wem_type:
            case "SFX":
                in_sfx_wems.append(wem_path)
            case "BGM":
                in_bgm_wems.append(wem_path)
            case _:
                print(f"Line {i}: Invalid wem type ({wem_type}).\n")

bnk_bgm_audio_mixer = f"{bnk_out}_bgm_mix"
bnk_sfx_audio_mixer = f"{bnk_out}_sfx_mix"

# Setup as dictionary to lookup file size and offsets later
media_file_lookup : dict[int, MediaEntry] = {}
# If bgm are stored in a pck do not include in the bnk
if exclude_bgm:
    stored_wems = in_sfx_wems
else:
    stored_wems = in_sfx_wems + in_bgm_wems

for wem_filename in stored_wems:
    if wem_filename in media_file_lookup:
        print("{wem_filename} is already used.\n")
        exit(1)
    hash = compute_hash(wem_filename)
    media_file_lookup[hash] = MediaEntry(
        hash = hash,
        wem_filename = wem_filename,
        offset = -1,
        size = -1
    )

# The media file header appears to be sorted by filename hash
sorted_media_hashes = sorted(list(media_file_lookup.keys()))

with open(f"{bnk_out}", "wb") as bnk_file:
# Write header
    bnk_file.write(b"BKHD") #Tag
    bnk_file.write((0x18).to_bytes(length = 4, byteorder = "little")) #Section Length
    bnk_file.write((140).to_bytes(length = 4, byteorder = "little")) #BNK version
    bnk_file.write(compute_hash(bnk_out).to_bytes(length = 4, byteorder = "little")) #BNK name hash
    bnk_file.write(compute_hash("SFX").to_bytes(length = 4, byteorder = "little")) # language hash (always the same)
    bnk_file.write((16).to_bytes(length = 4, byteorder = "little")) # alignment
    bnk_file.write((11146).to_bytes(length = 4, byteorder = "little")) # project ID ( same for all LC bnks)
    bnk_file.write((0).to_bytes(length = 4, byteorder = "little")) # padding

# This section can be ommited if all wems are expected to be included by pck
    if len(media_file_lookup) > 0:
    # Write DIDX section
        bnk_file.write(b"DIDX") # DIDX
        didx_section_size = 12 * (len(media_file_lookup))
        bnk_file.write(didx_section_size.to_bytes(length = 4, byteorder = "little")) # dwChunkSize

    # Skip to Data section so all the wems dont need to be kept in memory
        didx_return_offset = bnk_file.tell()
        bnk_file.seek(didx_section_size,1)

    # Write Data
        bnk_file.write(b"DATA") # DATA
        data_size_offset = bnk_file.tell()
        bnk_file.write((0).to_bytes(length = 4, byteorder = "little")) # uSize
        wem_offset = 0
        for media_hash in sorted_media_hashes:
            media_entry = media_file_lookup[media_hash]
        # real bnk files appear to 8 byte align each wem but dont know if its required
            if (wem_offset % 8) != 0:
                bnk_file.write(bytes([0] * (wem_offset % 8)))
                wem_offset += wem_offset % 8
            with open(media_entry.wem_filename, "rb") as wem_file:
                bnk_file.write(wem_file.read()) # uSize
                wem_len = wem_file.tell()
            media_entry.offset = wem_offset
            media_entry.size = wem_len
            wem_offset += wem_len
    # go back and write section length
        bnk_file.seek(data_size_offset,0)
        bnk_file.write(wem_offset.to_bytes(length = 4, byteorder = "little"))

    # go back to writing the previous section to write media headers
        bnk_file.seek(didx_return_offset,0)

    # MediaHeader
        for media_hash in sorted_media_hashes:
            media_entry = media_file_lookup[media_hash]
            bnk_file.write(media_entry.hash.to_bytes(length = 4, byteorder = "little")) # id
            bnk_file.write(media_entry.offset.to_bytes(length = 4, byteorder = "little")) # uOffset
            bnk_file.write(media_entry.size.to_bytes(length = 4, byteorder = "little")) # uSize

    # to back to the end of the file and write the rest of it
        bnk_file.seek(0, 2)

# Write HIRC Hierarchy
    bnk_file.write(b"HIRC") # HIRC
    HIRC_len_location = bnk_file.tell()
    bnk_file.write((0).to_bytes(length = 4, byteorder = "little")) # Section Length
    hirc_entry_count = (
        (1 if len(in_sfx_wems) > 0 else 0) + # Mixer for SFX
        (1 if len(in_bgm_wems) > 0 else 0) + # Mixer for BGM
        (1 + 2) * len(in_sfx_wems)         + # Sound, Play, and Play Event per SFX
        (1 + 4) * len(in_bgm_wems)           # Sound, Stop1 Play Stop2, and Play Event per BGM
    )
    bnk_file.write(hirc_entry_count.to_bytes(length = 4, byteorder = "little")) # Num entries

# Sound entries appear to be sorted by hash
    sound_entry_list : list[SoundEntry] = []
    for wem_filename in in_sfx_wems:
        sound_entry_list.append(
            SoundEntry(
                hash = compute_hash(f"{wem_filename}_sound"),
                wem_hash = compute_hash(wem_filename),
                wem_type = "SFX"
            ))
    for wem_filename in in_bgm_wems:
        sound_entry_list.append(
            SoundEntry(
                hash = compute_hash(f"{wem_filename}_sound"),
                wem_hash = compute_hash(wem_filename),
                wem_type = "BGM"
            ))
    sound_entry_list.sort(key = lambda x: x.hash)

# Mixers also sorted by hash
    mixer_order = [
        (compute_hash(bnk_sfx_audio_mixer), "SFX"),
        (compute_hash(bnk_bgm_audio_mixer), "BGM"),
    ]
    mixer_order.sort(key = lambda x: x[0])
# Write the mixer's child sounds in hash order followed by the mixer
    for mixer_hash, mixer_type in mixer_order:
        mixer_sounds = list(filter(lambda x: x.wem_type == mixer_type, sound_entry_list))
        num_mixer_sounds = len(mixer_sounds)
        if num_mixer_sounds == 0:
            continue
        match mixer_type:
            case "SFX":
                for sound_entry in mixer_sounds:
                # Write CAkSound (sfx)
                    bnk_file.write(bytes([0x02, 0x32, 0x00, 0x00, 0x00])) # Type 02 for CAkSound, Size should always be 0x00000032
                    bnk_file.write(sound_entry.hash.to_bytes(length = 4, byteorder = "little")) # Sound name hash
                    bnk_file.write(bytes([
                        0x01, 0x00, 0x02, 0x00, # plugin ID ADPCM
                        0x00                    # Stream type Data/bnk
                    ]))
                    bnk_file.write(sound_entry.wem_hash.to_bytes(length = 4, byteorder = "little")) # wem name hash
                    # SFX should always be added to the lookup
                    bnk_file.write(media_file_lookup[sound_entry.wem_hash].size.to_bytes(length = 4, byteorder = "little")) # uSize
                    bnk_file.write(bytes([
                        0x00,                  # uSourceBits
                    # NodeBaseParams
                        0x00,                  # bIsOverrideParentFX
                        0x00,                  # uNumFx
                        0x00,                  # bIsOverrideParentMetadata
                        0x00,                  # uNumFx
                        0x00,                  # bOverrideAttachmentParams
                    ]))
                    bnk_file.write((0).to_bytes(length = 4, byteorder = "little")) # OverrideBusId
                    bnk_file.write(mixer_hash.to_bytes(length = 4, byteorder = "little")) # DirectParentID (should be the mixer)
                    bnk_file.write(bytes([
                        0x00,                  # byBitVector
                    # NodeInitialParams
                    # AkPropBundle<AkPropValue,unsigned char>
                        0x00,                  # cProps
                    # AkPropBundle<RANGED_MODIFIERS<AkPropValue>>
                        0x00,                  # cProps
                    # PositioningParams
                        0x00,                  # uBitsPositioning
                    # AuxParams
                        0x00,                  # byBitVector
                        0x00, 0x00, 0x00, 0x00,# reflectionsAuxBus
                    # AdvSettingsParams
                        0x00,                  # byBitVector
                        0x01,                  # eVirtualQueueBehavior [FromElapsedTime]
                        0x01, 0x00,            # u16MaxNumInstance
                        0x00,                  # eBelowThresholdBehavior [ContinueToPlay]
                        0x00,                  # byBitVector
                    # StateChunk
                        0x00,                  # ulNumStateProps
                        0x00,                  # ulNumStateGroups
                    # InitialRTPC
                        0x00, 0x00,            # ulNumRTPC
                    ]))
            # Write CAkActorMixer (sfx)
                bnk_file.write(bytes([0x07])) # Type 07 for CAkActorMixer
                bnk_file.write((0x33 + num_mixer_sounds * 4).to_bytes(length = 4, byteorder = "little")) # Section Size
                bnk_file.write(mixer_hash.to_bytes(length = 4, byteorder = "little")) # mixer ID
                # ActorMixerInitialValues
                bnk_file.write(bytes([
                # NodeBaseParams
                    0x00,                  # bIsOverrideParentFX
                    0x00,                  # uNumFx
                    0x00,                  # bIsOverrideParentMetadata
                    0x00,                  # uNumFx
                    0x00,                  # bOverrideAttachmentParams
                ]))
                # This is the audio bus defined in init.bnk
                # Setting this makes it so this sound is controlled by the sfx volume slider
                bnk_file.write((1584861537).to_bytes(length = 4, byteorder = "little")) # OverrideBusId
                bnk_file.write((0).to_bytes(length = 4, byteorder = "little")) # DirectParentID
                bnk_file.write(bytes([
                # NodeBaseParams (continued)
                    0x00,                  # byBitVector
                    # AkPropBundle<AkPropValue,unsigned char>
                    0x02,                  # cProps
                        0x00,                  # [Volume]
                        0x07,                  # [Priority]
                        0x00, 0x00, 0x20, 0x40,# 2.5 [Volume]
                        0x00, 0x00, 0x70, 0x42,# 60  [Priority]
                    # AkPropBundle<RANGED_MODIFIERS<AkPropValue>>
                    0x00,                  # cProps
                # PositioningParams
                    0x03,                  # uBitsPositioning
                    0x08,                  # uBits3d
                # AuxParams
                    0x00,                  # byBitVector
                    0x00, 0x00, 0x00, 0x00,# reflectionsAuxBus
                # AdvSettingsParams
                    0x00,                  # byBitVector
                    0x01,                  # eVirtualQueueBehavior [FromElapsedTime]
                    0x00, 0x00,            # u16MaxNumInstance
                    0x00,                  # eBelowThresholdBehavior
                    0x00,                  # byBitVector
                # StateChunk
                    0x00,                  # ulNumStateProps
                    0x00,                  # ulNumStateGroups
                # InitialRTPC
                    0x00, 0x00,            # ulNumRTPC
                ]))
                # Children
                bnk_file.write(num_mixer_sounds.to_bytes(length = 4, byteorder = "little")) # ulNumChilds
                for sound_entry in mixer_sounds:
                    bnk_file.write(sound_entry.hash.to_bytes(length = 4, byteorder = "little")) # sound entries
            case "BGM":
                for sound_entry in mixer_sounds:
                # Write CAkSound (bgm)
                    bnk_file.write(bytes([0x02, 0x37, 0x00, 0x00, 0x00])) # Type 02 for CAkSound, Size should always be 0x00000037
                    bnk_file.write(sound_entry.hash.to_bytes(length = 4, byteorder = "little")) # Sound name hash
                    bnk_file.write(bytes([
                        # 0x01, 0x00, 0x04, 0x00, # plugin ID VORBIS
                        # 0x02                    # Stream type Streaming
                        0x01, 0x00, 0x02, 0x00, # plugin ID ADPCM
                        0x02                    # Stream type Streaming
                    ]))
                    bnk_file.write(sound_entry.wem_hash.to_bytes(length = 4, byteorder = "little")) # wem name hash
                    # If this bgm is not in the lookup, exclude_bgm was probably used
                    if sound_entry.wem_hash in media_file_lookup:
                        bnk_file.write(media_file_lookup[sound_entry.wem_hash].size.to_bytes(length = 4, byteorder = "little")) # uSize
                    else:
                        bnk_file.write((1024).to_bytes(length = 4, byteorder = "little")) # uSize
                    bnk_file.write(bytes([
                        0x00,                  # uSourceBits
                    # NodeBaseParams
                        0x00,                  # bIsOverrideParentFX
                        0x00,                  # uNumFx
                        0x00,                  # bIsOverrideParentMetadata
                        0x00,                  # uNumFx
                        0x00,                  # bOverrideAttachmentParams
                    ]))
                    bnk_file.write((0).to_bytes(length = 4, byteorder = "little")) # OverrideBusId
                    bnk_file.write(mixer_hash.to_bytes(length = 4, byteorder = "little")) # DirectParentID (should be the mixer)
                    bnk_file.write(bytes([
                        0x00,                  # byBitVector
                    # NodeInitialParams
                    # AkPropBundle<AkPropValue,unsigned char>
                        0x01,                  # cProps
                    # listpProps
                            0x3A,                  # pID [Loop]
                            0x00, 0x00, 0x00, 0x00,# pValue
                    # AkPropBundle<RANGED_MODIFIERS<AkPropValue>>
                        0x00,                  # cProps
                    # PositioningParams
                        0x00,                  # uBitsPositioning
                    # AuxParams
                        0x00,                  # byBitVector
                        0x00, 0x00, 0x00, 0x00,# reflectionsAuxBus
                    # AdvSettingsParams
                        0x00,                  # byBitVector
                        0x01,                  # eVirtualQueueBehavior [FromElapsedTime]
                        0x00, 0x00,            # u16MaxNumInstance
                        0x00,                  # eBelowThresholdBehavior [ContinueToPlay]
                        0x00,                  # byBitVector
                    # StateChunk
                        0x00,                  # ulNumStateProps
                        0x00,                  # ulNumStateGroups
                    # InitialRTPC
                        0x00, 0x00,            # ulNumRTPC
                    ]))
            # Write CAkActorMixer (bgm)
                bnk_file.write(bytes([0x07])) # Type 07 for CAkActorMixer
                bnk_file.write((0x2E + num_mixer_sounds * 4).to_bytes(length = 4, byteorder = "little")) # Section Size
                bnk_file.write(mixer_hash.to_bytes(length = 4, byteorder = "little")) # mixer ID
                # ActorMixerInitialValues
                bnk_file.write(bytes([
                # NodeBaseParams
                    0x00,                  # bIsOverrideParentFX
                    0x00,                  # uNumFx
                    0x00,                  # bIsOverrideParentMetadata
                    0x00,                  # uNumFx
                    0x00,                  # bOverrideAttachmentParams
                ]))
                
                bnk_file.write((0).to_bytes(length = 4, byteorder = "little")) # OverrideBusId (This is defined in the parent mixer)
                # This sets the parent to the main mixer for bgm defined in Vol1/2Global.bnk
                # Setting this makes it so this bgm starts and stop with the rest of the bgm
                # and is controlled by the volume slider.

                # This works, but this mixer is not set as a child to it in Vol1/2Global.bnk
                # Not sure if this causes any issues?
                bnk_file.write((289663270).to_bytes(length = 4, byteorder = "little")) # DirectParentID
                bnk_file.write(bytes([
                # NodeBaseParams (continued)
                    0x00,                  # byBitVector
                    # AkPropBundle<AkPropValue,unsigned char>
                    0x01,                  # cProps
                        0x00,                  # [Volume]
                        0x00, 0x00, 0x20, 0xC0,# -2.5 [Volume]
                    # AkPropBundle<RANGED_MODIFIERS<AkPropValue>>
                    0x00,                  # cProps
                # PositioningParams
                    0x03,                  # uBitsPositioning
                    0x08,                  # uBits3d
                # AuxParams
                    0x00,                  # byBitVector
                    0x00, 0x00, 0x00, 0x00,# reflectionsAuxBus
                # AdvSettingsParams
                    0x00,                  # byBitVector
                    0x01,                  # eVirtualQueueBehavior [FromElapsedTime]
                    0x00, 0x00,            # u16MaxNumInstance
                    0x00,                  # eBelowThresholdBehavior
                    0x00,                  # byBitVector
                # StateChunk
                    0x00,                  # ulNumStateProps
                    0x00,                  # ulNumStateGroups
                # InitialRTPC
                    0x00, 0x00,            # ulNumRTPC
                ]))
                # Children
                bnk_file.write(num_mixer_sounds.to_bytes(length = 4, byteorder = "little")) # ulNumChilds
                for sound_entry in mixer_sounds:
                    bnk_file.write(sound_entry.hash.to_bytes(length = 4, byteorder = "little")) # sound entries

# Event entries appear to be sorted by hash
    event_entry_list : list[EventEntry] = []
    for wem_filename in in_sfx_wems:
        event_entry_list.append(
            EventEntry(
                hash = compute_hash(f"{wem_filename}_play_event"),
                wem_filename = wem_filename,
                wem_type = "SFX"
            ))
    for wem_filename in in_bgm_wems:
        event_entry_list.append(
            EventEntry(
                hash = compute_hash(f"{wem_filename}_play_event"),
                wem_filename = wem_filename,
                wem_type = "BGM"
            ))
    event_entry_list.sort(key = lambda x: x.hash)

    for event_entry in event_entry_list:
        match event_entry.wem_type:
            case "SFX":
            # SFX just need 1 play and 1 event
            # CAkActionPlay (sfx)
                bnk_file.write(bytes([0x03, 0x12, 0x00, 0x00, 0x00])) # Type 03 for CAkAction, Size should always be 0x00000012
                bnk_file.write(compute_hash(f"{event_entry.wem_filename}_play").to_bytes(length = 4, byteorder = "little")) # ulID
                bnk_file.write(bytes([0x03, 0x04])) # ulActionType [Play]
                # ActionInitialValues
                bnk_file.write(compute_hash(f"{event_entry.wem_filename}_sound").to_bytes(length = 4, byteorder = "little")) # idExt
                bnk_file.write(bytes([
                    0x00,                  # idExt_4
                    # AkPropBundle<AkPropValue,unsigned char>
                    0x00,                  # cProps
                    # AkPropBundle<RANGED_MODIFIERS<AkPropValue>>
                    0x00,                  # cProps
                    # PlayActionParams
                    0x04,                  # byBitVector
                ]))
                bnk_file.write(compute_hash(bnk_out).to_bytes(length = 4, byteorder = "little")) #bankID
            # CAkEvent (sfx)
                bnk_file.write(bytes([0x04, 0x09, 0x00, 0x00, 0x00])) # Type 04 for CAkEvent, Size should always be 0x00000009
                bnk_file.write(event_entry.hash.to_bytes(length = 4, byteorder = "little")) # ulID
                # EventInitialValues
                bnk_file.write(bytes([0x01])) #ulActionListSize (always 1)
                bnk_file.write(compute_hash(f"{event_entry.wem_filename}_play").to_bytes(length = 4, byteorder = "little")) # play
            case "BGM":
            # Music needs 2 stops, 1 play, and 1 event
            # CAkActionStop 1 (bgm)
                bnk_file.write(bytes([0x03, 0x15, 0x00, 0x00, 0x00])) # Type 03 for CAkAction, Size should always be 0x00000015
                bnk_file.write(compute_hash(f"{event_entry.wem_filename}_stop1").to_bytes(length = 4, byteorder = "little")) # ulID
                bnk_file.write(bytes([0x02, 0x01])) # ulActionType [Stop_E]
                # ActionInitialValues
                # bnk_file.write(compute_hash(bnk_bgm_audio_mixer).to_bytes(length = 4, byteorder = "little")) # idExt
                bnk_file.write((289663270).to_bytes(length = 4, byteorder = "little")) # idExt (stop games mixer)
                bnk_file.write(bytes([
                    0x00,                  # idExt_4
                    # AkPropBundle<AkPropValue,unsigned char>
                    0x01,                  # cProps
                    # AkPropBundle
                        0x10,                   # pID [TransitionTime]
                        0xF4, 0x01, 0x00, 0x00, # Transition Time [500]
                    # AkPropBundle<RANGED_MODIFIERS<AkPropValue>>
                    0x00,                  # cProps
                    # ActiveActionParams
                    0x04,                  # byBitVector
                    # StopActionSpecificParams
                    0x06,                  # byBitVector
                    # ExceptParams
                    0x00
                ]))
            # CAkActionPlay (bgm)
                bnk_file.write(bytes([0x03, 0x12, 0x00, 0x00, 0x00])) # Type 03 for CAkAction, Size should always be 0x00000012
                bnk_file.write(compute_hash(f"{event_entry.wem_filename}_play").to_bytes(length = 4, byteorder = "little")) # ulID
                bnk_file.write(bytes([0x03, 0x04])) # ulActionType [Play]
                # ActionInitialValues
                bnk_file.write(compute_hash(f"{event_entry.wem_filename}_sound").to_bytes(length = 4, byteorder = "little")) # idExt
                bnk_file.write(bytes([
                    0x00,                  # idExt_4
                    # AkPropBundle<AkPropValue,unsigned char>
                    0x00,                  # cProps
                    # AkPropBundle<RANGED_MODIFIERS<AkPropValue>>
                    0x00,                  # cProps
                    # PlayActionParams
                    0x04,                  # byBitVector
                ]))
                bnk_file.write(compute_hash(bnk_out).to_bytes(length = 4, byteorder = "little")) #bankID
            # CAkActionStop2 (bgm)
                bnk_file.write(bytes([0x03, 0x10, 0x00, 0x00, 0x00])) # Type 03 for CAkAction, Size should always be 0x00000010
                bnk_file.write(compute_hash(f"{event_entry.wem_filename}_stop2").to_bytes(length = 4, byteorder = "little")) # ulID
                bnk_file.write(bytes([0x02, 0x01])) # ulActionType [Stop_E]
                # ActionInitialValues
                bnk_file.write((920168426).to_bytes(length = 4, byteorder = "little")) # idExt (this is a hash of a mixer defined in Vol2Global.bnk)
                bnk_file.write(bytes([
                    0x00,                  # idExt_4
                    # AkPropBundle<AkPropValue,unsigned char>
                    0x00,                  # cProps
                    # AkPropBundle<RANGED_MODIFIERS<AkPropValue>>
                    0x00,                  # cProps
                    # ActiveActionParams
                    0x04,                  # byBitVector
                    # StopActionSpecificParams
                    0x06,                  # byBitVector
                    # ExceptParams
                    0x00
                ]))
            # CAkEvent (bgm)
                bnk_file.write(bytes([0x04, 0x11, 0x00, 0x00, 0x00])) # Type 04 for CAkEvent, Size should always be 0x00000011
                bnk_file.write(event_entry.hash.to_bytes(length = 4, byteorder = "little")) # ulID
                # EventInitialValues
                bnk_file.write(bytes([0x03])) #ulActionListSize (always 3)
                bnk_file.write(compute_hash(f"{event_entry.wem_filename}_stop1").to_bytes(length = 4, byteorder = "little")) # stop1
                bnk_file.write(compute_hash(f"{event_entry.wem_filename}_play").to_bytes(length = 4, byteorder = "little")) # play
                bnk_file.write(compute_hash(f"{event_entry.wem_filename}_stop2").to_bytes(length = 4, byteorder = "little")) # stop2
# Go back and add this sections length
    HIRC_end_location = bnk_file.tell()
    bnk_file.seek(HIRC_len_location, 0)
    bnk_file.write((HIRC_end_location - HIRC_len_location - 4).to_bytes(length = 4, byteorder = "little"))


# Write optional header file with the names
if args.header_file is not None:
    clean_string_regex = re.compile(r'[^a-zA-Z0-9_]')
    with open(f"{args.header_file}", "w") as header_file:
        header_file.write(f"#pragma once\n")
        header_file.write(f"#include <cstdint>\n\n")
        for event_entry in event_entry_list:
            play_event_variable_name = clean_string_regex.sub("_", f"PLAY_{event_entry.wem_filename.upper()}")
            header_file.write(f"static const uint32_t {play_event_variable_name} = {event_entry.hash}; //(0x{event_entry.hash:08X})\n")
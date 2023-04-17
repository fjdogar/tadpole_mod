import os
import sys
import re
import binascii
import shutil

systems = {
    "ARCADE": ["mswb7.tax", "msdtc.nec", "mfpmp.bvs"],
    "FC":     ["rdbui.tax", "fhcfg.nec", "nethn.bvs"],
    "GB":     ["vdsdc.tax", "umboa.nec", "qdvd6.bvs"],
    "GBA":    ["vfnet.tax", "htuiw.nec", "sppnp.bvs"],
    "GBC":    ["pnpui.tax", "wjere.nec", "mgdel.bvs"],
    "MD":     ["scksp.tax", "setxa.nec", "wmiui.bvs"],
    "SFC":    ["urefs.tax", "adsnt.nec", "xvb6c.bvs"]
}

supported_ext = [
    "bkp", "zip", "zfc", "zsf", "zmd", "zgb", "zfb", "smc", "fig", "sfc", "gd3", "gd7", "dx2", "bsx", "swc", "nes",
    "nfc", "fds", "unf", "gba", "agb", "gbz", "gbc", "gb", "sgb", "bin", "md", "smd", "gen", "sms"
]


class StopExecution(Exception):
    pass


def int_to_4_bytes_reverse(src_int):
    hex_string = format(src_int, "x").rjust(8, "0")[0:8]
    return binascii.unhexlify(hex_string)[::-1]  # reverse it


def file_entry_to_name(file_entry):
    return file_entry.name


def check_file(file_entry):
    file_regex = ".+\\.(" + "|".join(supported_ext) + ")$"
    return file_entry.is_file() and re.search(file_regex, file_entry.name.lower())


def build_sort_position_dict(sorted_list):
    # this MIGHT NOT WORK it relies on what i think is inherent behaviour of dicts being internally sorted
    # this is an array flip equiv
    return {value: key for key, value in dict(enumerate(sorted_list)).items()}


def strip_file_extension(name):
    parts = name.split(".")
    parts.pop()
    return ".".join(parts)


def sort_normal(unsorted_list):
    return sorted(unsorted_list)


def sort_without_file_ext(unsorted_list):
    stripped_names = list(map(strip_file_extension, unsorted_list))
    sort_map = dict(zip(unsorted_list, stripped_names))
    return sorted(sort_map, key=sort_map.get)


def process_sys(drive, system, test_mode):
    print(f"Processing {system}")

    roms_path = f"{drive}/{system}"
    if not os.path.isdir(roms_path):
        print(f"! Couldn't find folder {roms_path}")
        print("  Check the provided path points to an SF2000 SD card!")
        raise StopExecution

    index_path_files = f"{drive}/Resources/{systems[system][0]}"
    index_path_cn = f"{drive}/Resources/{systems[system][1]}"
    index_path_pinyin = f"{drive}/Resources/{systems[system][2]}"
    check_and_back_up_file(index_path_files)
    check_and_back_up_file(index_path_cn)
    check_and_back_up_file(index_path_pinyin)

    print(f"Looking for ROMs in {roms_path}")
    files = os.scandir(roms_path)
    files = list(filter(check_file, files))
    no_files = len(files)
    if no_files == 0:
        print("No ROMs found! Type Y to confirm you want to save an empty game list, or anything else to cancel")
        conf = input()
        if conf.upper() != "Y":
            print("Cancelling, game list not modified")
            return
    else:
        print(f"Found {no_files} ROMs")

    filenames = list(map(file_entry_to_name, files))
    stripped_names = list(map(strip_file_extension, filenames))

    # prepare maps of filenames to index name for the 3 index files
    # for "files" we just want the actual filenames as both key and value, the menu will strip the extensions
    name_map_files = dict(zip(filenames, filenames))
    # for the Chinese names and pinyin initials, i'm not supporting that at the moment, so use the English titles
    # but use the stripped versions because the menu will not strip them here
    name_map_cn = dict(zip(filenames, stripped_names))
    name_map_pinyin = dict(zip(filenames, stripped_names))

    write_index_file(name_map_files, sort_without_file_ext, index_path_files, test_mode)
    write_index_file(name_map_cn, sort_normal, index_path_cn, test_mode)
    write_index_file(name_map_pinyin, sort_normal, index_path_pinyin, test_mode)

    print("Done\n")


def check_and_back_up_file(file_path):
    if not os.path.exists(file_path):
        print(f"! Couldn't find game list file {file_path}")
        print("  Check the provided path points to an SF2000 SD card!")
        raise StopExecution

    if not os.path.exists(f"{file_path}_orig"):
        print(f"Backing up {file_path} as {file_path}_orig")
        try:
            shutil.copyfile(file_path, f"{file_path}_orig")
        except (OSError, IOError):
            print("! Failed to copy file.")
            print("  Check the SD card and Resources directory are writable.")
            raise StopExecution


def write_index_file(name_map, sort_func, index_path, test_mode):
    # entries must maintain a consistent order between all indexes, but what that order actually is doesn't matter
    # so use alphabetised filenames for this
    filenames = sorted(name_map.keys())

    pointers_by_name = {}
    names_bytes = b""
    for filename in filenames:
        display_name = name_map[filename]
        current_pointer = len(names_bytes)
        pointers_by_name[display_name] = current_pointer
        names_bytes += display_name.encode('utf-8') + chr(0).encode('utf-8')

    # sort the display names according to their desired display order, and build a list of pointers in that order
    sorted_pointers = []
    for sorted_name in sort_func(name_map.values()):
        sorted_pointers.append(pointers_by_name[sorted_name])

    # first metadata item is the total count of games in this list
    metadata_bytes = int_to_4_bytes_reverse(len(name_map))
    # and the rest are pointers to the display names in the desired display order
    for current_pointer in sorted_pointers:
        metadata_bytes += int_to_4_bytes_reverse(current_pointer)

    new_index_content = metadata_bytes + names_bytes

    if test_mode:
        print(f"Checking {index_path}")
        file_handle = open(index_path, 'rb')
        existing_index_content = file_handle.read(os.path.getsize(index_path))
        file_handle.close()
        if existing_index_content != new_index_content:
            print("! Doesn't match")
        return

    print(f"Overwriting {index_path}")
    try:
        file_handle = open(index_path, 'wb')
        file_handle.write(new_index_content)
        file_handle.close()
    except (IOError, OSError):
        print("! Failed overwriting file.")
        print("  Check the SD card and file are writable, and the file is not open in another program.")
        raise StopExecution


def check_sys_valid(system):
    return system and (system in systems.keys() or system == "ALL")


def run():

    drive = sys.argv[1] if len(sys.argv) >= 2 else ""
    system = sys.argv[2].upper() if len(sys.argv) >= 3 else ""
    skip_conf = len(sys.argv) >= 4 and sys.argv[3] == "-sc"
    test_mode = len(sys.argv) >= 4 and sys.argv[3] == "-t"

    while not drive or not os.path.isdir(drive):
        if drive and not os.path.isdir(drive):
            if len(drive) == 1 and os.path.isdir(f"{drive}:"):
                drive = f"{drive}:"
                continue
            else:
                print("! Specified drive or path is not accessible")
        print()
        print("Please enter the drive or path where your SF2000 SD card is located e.g. F:")
        drive = input()

    while not system or not check_sys_valid(system):
        if system and not check_sys_valid(system):
            print("! Specified system is not one of the accepted options")
        print()
        print("Please enter the system to rebuild game list for: ARCADE, FC, GB, GBA, GBC, MD, SFC or ALL")
        system = input().upper()

    print()
    print("=== DISCLAIMER ===")
    print()
    print("This program is experimental and you should proceed with caution!")
    print("Although it will back up the files it modifies, you should make your own backup of the ")
    print("Resources folder and ideally your whole SD card so you can restore the original state of")
    print("your device if anything goes wrong.")
    print()
    print("The following functionality from the stock system will be lost by using this program:")
    print("1. Chinese translations of game names (including searching by pinyin initials).")
    print("   Game names will be taken from the filename regardless of language setting.")
    print("2. Any custom sorting of games in the menu (e.g. popular games placed at the top).")
    print("   All games will be sorted alphabetically instead.")
    print()
    if not skip_conf:
        print("Type Y to continue, or anything else to cancel")
        conf = input()
        if conf.upper() != "Y":
            print("Cancelling, no files modified")
            return
        print()

    keys_to_process = systems.keys() if system == "ALL" else [system]
    for syskey in keys_to_process:
        process_sys(drive, syskey, test_mode)


try:
    run()
except KeyboardInterrupt:
    pass
except StopExecution:
    pass

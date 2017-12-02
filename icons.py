import os
import re
import json

from collections import OrderedDict
from PIL import ImageChops
import PIL.Image

import numpy as np

PARSE_REGEX = re.compile(r'\t(.*) = (.*)')

def parse_metadata(img):
    """
    Parses a DMI metadata, 
    returning an tuple array(icon_state, state dict). 
    img is a PIL.Image object
    """
    img_dict = img.info
    info = img_dict['Description'].split('\n')
    if not 'version = 4.0' in info:
        return None
    meta_info = []
    current_key = None
    for entry in info:
        if entry in ["# BEGIN DMI", "# END DMI", ""]:
            continue
        if '\t' not in entry:
            current_key = entry.replace('state = ', '').replace('\"', '')
            meta_info.append((current_key, {}))
        else:
            this_info = PARSE_REGEX.search(entry)
            if this_info:
                grp_1 = this_info.group(1)
                grp_2 = this_info.group(2)
                if grp_1 in ['delay', 'hotspot']:
                    entries = grp_2.split(',')
                    grp_2 = []
                    for thing in entries:
                        grp_2.append(int(thing))
                else:
                    grp_2 = int(grp_2)
                dict_to_add = {grp_1 : grp_2}
                meta_info[len(meta_info) - 1][1].update(dict_to_add)
    return meta_info

def generate_icon_states(filename, save_each = False):
    """Generates every icon state into an Image object. Returning a dict with {name : object}"""
    img = PIL.Image.open(filename)

    meta_data = parse_metadata(img)
    if meta_data is None:
        print("Failed to retreive metadata.")
        return
    
    image_width = img.width
    image_height = img.height

    icon_width = meta_data[0][1]['width']
    icon_height = meta_data[0][1]['height']
    meta_data = meta_data[1:] #We don't need the version info anymore

    icons_per_line = int(image_width / icon_width)
    total_lines = int(image_height / icon_height)

    if img.mode != "RGBA":
        img = img.convert("RGBA")
    data = np.asarray(img)
    
    img.close()

    icon_count = 0
    skip_naming = 0
    name_count = 1
    icons = {}
    for line in range(0, total_lines):
        icon = 0
        while icon < icons_per_line:
            this_icon = PIL.Image.new('RGBA', (icon_width, icon_height))
            try:
                state_tuple = meta_data[icon_count] # (name, {'dirs' : 1, 'frames' : 1})
                name = state_tuple[0]
                if skip_naming:
                    if name_count > 0:
                        name += str(name_count)
                    name_count += 1
                    skip_naming -= 1
                    if not skip_naming:
                        icon_count += 1
                else:
                    amt_dirs = state_tuple[1]['dirs']
                    amt_frames = state_tuple[1]['frames']
                    skip_naming = (amt_dirs * amt_frames) - 1
                    if not skip_naming:
                        icon_count += 1
                    else:
                        name_count = 1
            except IndexError:
                break #IndexError means blank icon
            icon_start_w = icon * icon_width
            icon_end_w = icon_start_w + icon_width
            icon_start_h = line * icon_height
            icon_end_h = icon_start_h + icon_height
            this_state_x = 0
            for i in range(icon_start_w, icon_end_w):
                this_state_y = 0
                for j in range(icon_start_h, icon_end_h):
                    this_icon.putpixel((this_state_x, this_state_y), tuple(data[j, i]))
                    this_state_y += 1
                this_state_x += 1

            icon += 1
            icons[name] = this_icon
            if save_each:
                this_icon.save("icon_dump/{}.png".format(name))
    return icons


def check_icon_state_diff(image_a, image_b):
    """Compares two icons(passed as an Image object), returning True if the icons are equal, False in case of a difference."""
    return ImageChops.difference(image_a, image_b).getbbox() is None


def compare_two_icon_files(file_a, file_b):
    """Compares every icon state of two icons, returning a dict with the icon state status: {state name : {status : no_check/modified/created, img_a : Image obj, img_b : Image obj}})"""
    if file_a:
        file_a_dict = generate_icon_states(file_a)
    else:
        file_a_dict = {}
    file_b_dict = generate_icon_states(file_b)
    final_dict = {}
    for key in file_a_dict:
        final_dict[key] = {}
        if not file_b_dict.get(key):
            final_dict[key]["status"] = "Removed"
            final_dict[key]["img_a"] = file_a_dict[key]
        elif check_icon_state_diff(file_a_dict[key], file_b_dict[key]):
            final_dict[key]["status"] = "Equal"
            file_a_dict[key].close()
            file_b_dict[key].close()
        else:
            final_dict[key]["status"] = "Modified"
            final_dict[key]["img_a"] = file_a_dict[key]
            final_dict[key]["img_b"] = file_b_dict[key]

    for key in file_b_dict:
        if not file_a_dict.get(key):
            final_dict[key] = {"status" : "Created", "img_b" : file_b_dict[key]}

    return final_dict

if __name__ == '__main__':
    with open("./icon_dump/new_unary_devices.dmi", 'rb') as f:
        generate_icon_states(f)

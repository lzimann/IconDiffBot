import os
import re

from collections import OrderedDict
from PIL import Image, ImageChops

import numpy as np

def parse_metadata(img):
    """Parses a DMI metadata, returning an OrderedDict. img is a PIL.Image object"""
    dict = img.info
    info = dict['Description']
    info = info.split('\n')
    if not 'version = 4.0' in info:
        return
    dict = OrderedDict()
    current_key = None
    for entry in info:
        if not '\t' in entry:
            current_key = entry
            dict.update({current_key : []})
            continue
        dict[current_key].append(entry.replace('\t', ''))
    return dict

def generate_icon_states(filename):
    """Generates every icon state into an Image object. Returning a dict with {name : object}"""
    frame_dir_re = re.compile('(dirs|frames) = (\d+)')
    img = Image.open(filename)

    meta_data = parse_metadata(img)
    try:
        sizes = meta_data['version = 4.0']
    except KeyError:
        print("DMI version not supported!")
        return

    image_width = img.width
    image_height = img.height

    icon_width = int(re.search('width = (\d+)', sizes[0]).group(1))
    icon_height = int(re.search('height = (\d+)', sizes[1]).group(1))
    img_data = img.getdata()

    total_size = image_width * image_height
    icons_per_line = int(image_width / icon_width)
    total_lines = int(image_height / icon_height)
    if img.mode != "RGBA":
        img = img.convert("RGBA")
    data = np.asarray(img)
    
    img.close()

    #Cut the first two and the last two elements of the list
    meta_data.popitem() # Pop last
    meta_data.popitem() # Pop last again
    meta_data.popitem(False) # Pop first
    meta_data.popitem(False) # Pop first again

    total_icons = len(meta_data)

    icon_names = []
    for key in meta_data.items():
        icon_names.append(key)
    icon_count = 0
    skip_naming = 0
    name_count = 1
    icons = {}
    for line in range(0, total_lines):
        icon = 0
        while icon < icons_per_line:
            this_icon = Image.new('RGBA', (icon_width, icon_height))
            try:
                this_icon_dict = icon_names[icon_count] # name : [dirs, frames, delay]
                name = this_icon_dict[0].replace('state = ', '').replace('\"', '')
                if skip_naming:
                    if name_count > 0:
                        name += str(name_count)
                    name_count += 1
                    skip_naming -= 1
                    if not skip_naming:
                        icon_count += 1
                else:
                    for item in this_icon_dict[1]:
                        match = frame_dir_re.search(item)
                        if match:
                            skip_naming += (int(match.group(2)) - 1)
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
            x = 0
            for i in range(icon_start_w, icon_end_w):
                y = 0
                for j in range(icon_start_h, icon_end_h):
                    this_icon.putpixel((x, y), tuple(data[j,i]))
                    y += 1
                x += 1

            icon += 1
            icons[name] = this_icon
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
    with open("cables.dmi", 'rb') as f:
        generate_icon_states(f)

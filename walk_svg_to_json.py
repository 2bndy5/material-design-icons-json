"""A python script to aggregate the Material Design Icons (v4.0.0+) from SVG sources
into several compiled JSON files. Each JSON file will have all the icons available for
a specific style (regular, round, sharp, outlined, twotone)."""
from posixpath import dirname
import time
import datetime
import os
import argparse
import re
import json
from xml.dom import minidom
from xml.dom.minidom import Document, Element

dicts = {"regular": {}, "outlined": {}, "round": {}, "sharp": {}, "twotone": {}}
skipped = []
duplicates = []

PATH_SEARCH = re.compile("<(\w{4,})(.*?)/>")

def parse_material_svg(file_path: str, src_path: str):
    """ "Import xml data from a named SVG asset.

    :param str file_path: path and name of SVG asset. For Example:
        src/social/whatshot/materialicons/24px.svg
    """
    data = minidom.parse(file_path)  # type: Document
    svg_tag = data.getElementsByTagName("svg")[0]  # type: Element
    svg_path = "".join([child.toxml() for child in svg_tag.childNodes])
    svg_path, count = re.subn(PATH_SEARCH, r"<\1\2></\1>", svg_path)
    while count:
        svg_path, count = re.subn(PATH_SEARCH, r"<\1\2></\1>", svg_path)
    svg_height = svg_tag.getAttribute("height")  # type: str
    svg_width = svg_tag.getAttribute("width")  # type: str
    if not svg_height.isnumeric() or not svg_width.isnumeric():
        skipped.append(file_path)
        return
    data.unlink()
    # src_info example: [social, whatshot, materialicons]
    path_name = file_path.replace(src_path, "")
    category, name, scheme = path_name.split(os.sep)[1:-1]
    scheme = scheme.replace("materialicons", "")
    if not scheme:
        scheme = "regular"
    if name in dicts[scheme].keys():
        if category not in dicts[scheme][name]["keywords"]:
            if dicts[scheme][name]["keywords"]:
                duplicates.append(file_path)
            dicts[scheme][name]["keywords"].append(category)
        if svg_height not in dicts[scheme][name]["heights"].keys():
            dicts[scheme][name]["heights"][svg_height] = {
                "width": int(svg_width),
                "path": svg_path,
            }
    else:
        dicts[scheme][name] = {
            "name": name,
            "keywords": [category],
            "heights": {svg_height: {"width": int(svg_width), "path": svg_path}},
        }


def walk_material_srcs(src_path: str = ".") -> int:
    """Walk the src tree of SVG assets and return the total count.
    
    :param str src_path: The root folder containing the icons' 'src' directory.
    """
    total = 0
    src_path += os.sep
    category = ""
    for path_name, dirnames, filenames in os.walk(src_path + "src"):
        if not dirnames:
            new_category = path_name.split(os.sep)[-3]
            if category != new_category:
                category = new_category
                print("parsing category", category)
        for filename in filenames:
            file_path = os.path.join(path_name, filename)
            # print("parsing", file_path)
            parse_material_svg(file_path, src_path)
            total += 1
    return total


def export_material_jsons():
    """Export seperate json files from assembled dicts."""
    for scheme, icon_info in dicts.items():
        json_name = f"material_{scheme}.json"
        with open("compiled/" + json_name, "w", encoding="utf-8") as json_file:
            print(f"dumping {json_name}")
            json.dump(icon_info, json_file, indent=2)

def crate_attribution():
    """Create an updated copyright notice for re-distribution."""
    license = []
    with open("LICENSE", "rb") as og_license:
        license = og_license.readlines()
    now = time.gmtime()
    year = str(now[0])
    print("Timestamping attribution notice")
    with open("compiled/material-icons_LICENSE", "wb") as dist_license:
        found_attribution = False
        for line in license:
            if (
                b"Copyright [yyyy] [name of copyright owner]" in line
                and not found_attribution
            ):
                found_attribution = True
                line = line.replace(b"[yyyy]", year.encode("utf-8"))
                line = line.replace(b"[name of copyright owner]", b"Google")
                dist_license.write(line)
            elif found_attribution:
                dist_license.write(line)


arg_parser = argparse.ArgumentParser(description=__doc__)
arg_parser.add_argument(
    "-p",
    "--path",
    default=".",
    help="The root folder containing the icons' 'src' directory."
)

if __name__ == "__main__":

    args = arg_parser.parse_args()
    start_timer = time.monotonic()
    total = walk_material_srcs(args.path)
    export_material_jsons()
    end_timer = time.monotonic()
    crate_attribution()
    print(f"json files created in {round(end_timer - start_timer, 3)} seconds.")
    print(
        f"Parsed {total - len(skipped)} svg files.",
        f"Skipped {len(skipped)}.",
        f"Found {len(duplicates)} duplicates."
    )
    # print("skipped the following files:\n  ", "\n    ".join(skipped))

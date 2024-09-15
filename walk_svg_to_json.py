"""A python script to aggregate the Material Design Icons (v4.0.0+) from SVG sources
into several compiled JSON files. Each JSON file will have all the icons available for
a specific style (regular, round, sharp, outlined, twotone)."""

import argparse
import json
import logging
import os
import re
from pathlib import Path
import time
from xml.dom import minidom
from xml.dom.minidom import Document, Element

dicts = {"regular": {}, "outlined": {}, "round": {}, "sharp": {}, "twotone": {}}
skipped = []
duplicates = []

PATH_SEARCH = re.compile(r"<(\w{4,})(.*?)/>")

logging.basicConfig(format="%(message)s")
LOGGER = logging.getLogger(__name__)


def parse_material_svg(file_path: str, src_path: str):
    """ "Import xml data from a named SVG asset.

    :param str file_path: The path and name of SVG asset. For Example:
        src/social/whatshot/materialicons/24px.svg
    :param src_path: The directory containing the svg.
    :returns: A 2-tuple containing the icon's category & name
    """
    data: Document = minidom.parse(file_path)
    svg_tag: Element = data.getElementsByTagName("svg")[0]
    svg_path = "".join([child.toxml() for child in svg_tag.childNodes])
    svg_path, count = re.subn(PATH_SEARCH, r"<\1\2></\1>", svg_path)
    while count:
        svg_path, count = re.subn(PATH_SEARCH, r"<\1\2></\1>", svg_path)
    svg_height: str = svg_tag.getAttribute("height")
    svg_width: str = svg_tag.getAttribute("width")
    data.unlink()
    if not svg_height.isnumeric() or not svg_width.isnumeric():
        skipped.append(file_path)
        return

    path_name = file_path.replace(src_path + os.sep, "")
    # category, name, scheme = [social, whatshot, materialicons]
    category, name, scheme = path_name.split(os.sep)[:-1]
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
            duplicates.append(file_path)
    else:
        dicts[scheme][name] = {
            "name": name,
            "keywords": [category],
            "heights": {svg_height: {"width": int(svg_width), "path": svg_path}},
        }
    return (category, name)


def walk_material_srcs(src_path: str = ".") -> int:
    """Walk the src tree of SVG assets and return the total count.

    :param str src_path: The root folder containing the icons' 'src' directory.
    :returns: The total number of icons parsed (includes duplicates from different sizes
        for same icons).
    """
    total = 0
    current_path = Path.cwd()
    os.chdir(src_path)
    category, name = ("", "")
    for file_path in Path("src").rglob("*.svg"):
        new_category, icon_name = parse_material_svg(str(file_path), "src")
        if category != new_category:
            category = new_category
            LOGGER.debug("parsing category: %s", category)
        if icon_name != name:
            name = icon_name
            LOGGER.debug("\ticon: %s", name)
        total += 1
    os.chdir(str(current_path))
    return total


def export_material_jsons():
    """Export separate json files from assembled dicts."""
    for scheme, icon_info in dicts.items():
        json_name = f"material_{scheme}.json"
        LOGGER.info("dumping %s", json_name)
        json_path = Path("compiled", json_name)
        json_path.parent.mkdir(parents=True, exist_ok=True)
        json_path.write_text(
            json.dumps(icon_info, indent=2) + "\n",
            encoding="utf-8",
        )


def crate_attribution():
    """Create an updated copyright notice for re-distribution."""
    icons_license = Path("LICENSE").read_bytes().splitlines()
    now = time.gmtime()
    year = str(now[0])
    LOGGER.info("Time-stamping attribution notice")
    start = -1
    for index, line in enumerate(icons_license):
        if b"Copyright [yyyy] [name of copyright owner]" in line:
            attribution = line.replace(b"[yyyy]", year.encode("utf-8"))
            icons_license[index] = attribution.replace(
                b"[name of copyright owner]", b"Google"
            )
            start = index
            break
    if start < 0:
        raise RuntimeError("Failed to find line in License that begins attribution")
    Path("compiled/material-icons_LICENSE").write_bytes(
        b"\n".join(icons_license[start:])
    )


def compare_json():
    """Used to compare old compiled JSONs (from sphinx-design repo) with
    newer compiled JSONs."""
    added, removed, new_sizes, rm_sizes = (0,) * 4
    added_names, removed_names = ([], [])
    sphinx_design_src = Path("sphinx-design/sphinx_design/compiled")
    if not sphinx_design_src.exists():
        sphinx_design_src = Path("../", sphinx_design_src)
        assert sphinx_design_src.exists(), "Failed to locate previously compiled json"
    for scheme, icon_info in dicts.items():
        json_name = f"material_{scheme}.json"
        old: dict = json.loads(
            Path(sphinx_design_src, json_name).read_text(encoding="utf-8")
        )
        for icon_name, info in icon_info.items():
            if icon_name not in old.keys():
                added += 1
                added_names.append(f"{scheme}/{icon_name}")
                continue
            new_icon_sizes = len(info["heights"])
            old_icon_sizes = len(old[icon_name]["heights"])
            new_sizes += new_icon_sizes > old_icon_sizes
            rm_sizes += new_icon_sizes < old_icon_sizes
        for icon_name in old.keys():
            # pylint: disable=consider-iterating-dictionary
            if icon_name not in icon_info.keys():
                removed += 1
                removed_names.append(f"{scheme}/{icon_name}")
            # pylint: enable=consider-iterating-dictionary
    LOGGER.info(
        "::notice title=Summary Comparison::"
        "%d new icons added. %d icons have new sizes. %d icons' sizes were removed."
        " %d icons were replaced or removed.",
        added,
        new_sizes,
        rm_sizes,
        removed,
    )
    if added_names:
        LOGGER.debug("::group::New Icon Names")
        for name in added_names:
            LOGGER.debug(name)
        LOGGER.debug("::endgroup::")
    if removed_names:
        LOGGER.debug("::group::Removed Icon Names")
        for name in removed_names:
            LOGGER.debug(name)
        LOGGER.debug("::endgroup::")


arg_parser = argparse.ArgumentParser(description=__doc__)
arg_parser.add_argument(
    "-p",
    "--path",
    default=".",
    help="The root folder containing the icons' 'src' directory.",
)
arg_parser.add_argument(
    "-q",
    "--quiet",
    action="store_true",
    help="disable the listing of icons as they're parsed. Use this as a speed-up",
)


def main():
    """The executable script entrypoint."""
    args = arg_parser.parse_args()
    if args.quiet:
        LOGGER.setLevel(logging.INFO)
    else:
        LOGGER.setLevel(logging.DEBUG)
    LOGGER.debug("::group::Processed Categories/Icons")
    start_timer = time.monotonic()
    total = walk_material_srcs(args.path)
    LOGGER.debug("::endgroup::")
    export_material_jsons()
    end_timer = time.monotonic()
    crate_attribution()
    LOGGER.debug("::group::Duplicate Icon Names")
    for name in duplicates:
        LOGGER.debug(name)
    LOGGER.debug("::endgroup::")
    LOGGER.info("json files created in %f seconds.", round(end_timer - start_timer, 3))
    LOGGER.info(
        "::notice title=Summary Compiled::"
        "Parsed %d svg files. Skipped %d. Found %d duplicates.",
        total - len(skipped),
        len(skipped),
        len(duplicates),
    )
    compare_json()
    if skipped:
        LOGGER.debug(
            "::notice title=skipped the following files::%s", ", ".join(skipped)
        )


if __name__ == "__main__":
    main()

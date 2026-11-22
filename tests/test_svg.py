"""pyrio.svg: stadium drawings as SVG strings."""

from __future__ import annotations

import pathlib
import xml.etree.ElementTree as ET

import pytest

import pyrio
import pyrio.svg
from pyrio import PrimaryContactResult, Stadium
from pyrio.geometry import boundary
from pyrio.svg import Flight, Mark

NS = "{http://www.w3.org/2000/svg}"
FIXTURES = pathlib.Path(__file__).parent / "fixtures"
GAME = pyrio.read_game(FIXTURES / "20260618T191655_SpiceOrange-Vs-MattGree_3896251267.json")


def parse(svg: str) -> ET.Element:
    root = ET.fromstring(svg)
    assert root.tag == f"{NS}svg"
    return root


def count(root: ET.Element, tag: str) -> int:
    return len(root.findall(f".//{NS}{tag}"))


@pytest.mark.parametrize("stadium", list(Stadium), ids=lambda s: s.name)
def test_every_stadium_draws_its_field_and_both_foul_lines(stadium: Stadium):
    root = parse(pyrio.svg.stadium(stadium))
    assert count(root, "polygon") == 1
    assert count(root, "line") == 2


def test_the_field_is_the_boundary_with_z_pointing_up():
    root = parse(pyrio.svg.stadium(Stadium.MARIO_STADIUM))
    polygon = root.find(f"{NS}polygon")
    assert polygon is not None
    first = polygon.get("points", "").split()[0]
    x, z = boundary(Stadium.MARIO_STADIUM)[0]
    assert first == f"{x:.2f},{-z:.2f}".replace(".00", "")


def test_foul_lines_run_at_45_degrees_to_the_wall():
    root = parse(pyrio.svg.stadium(Stadium.MARIO_STADIUM))
    for line in root.findall(f"{NS}line"):
        x2, y2 = float(line.get("x2", "")), float(line.get("y2", ""))
        assert abs(abs(x2) - abs(y2)) < 0.02
        assert abs(x2) > 30


def test_size_sets_the_width_and_keeps_the_fields_shape():
    root = parse(pyrio.svg.stadium(Stadium.MARIO_STADIUM, size=500))
    assert root.get("width") == "500"
    _, _, w, h = (float(v) for v in root.get("viewBox", "").split())
    assert int(root.get("height", "")) == round(500 * h / w)
    assert "width" not in parse(pyrio.svg.stadium(Stadium.MARIO_STADIUM, size=None)).attrib


def test_fielders_add_nine_labelled_spots():
    root = parse(pyrio.svg.stadium(Stadium.MARIO_STADIUM, fielders=True))
    assert count(root, "rect") == 9
    labels = {t.text for t in root.findall(f"{NS}text")}
    assert {"P", "C", "1B", "CF"} <= labels


@pytest.mark.parametrize(
    ("shape", "tag"),
    [
        ("circle", "circle"),
        ("square", "rect"),
        ("diamond", "polygon"),
        ("triangle", "polygon"),
        ("star", "polygon"),
        ("cross", "path"),
    ],
)
def test_each_mark_shape(shape: pyrio.svg.MarkShape, tag: str):
    plain = parse(pyrio.svg.stadium(Stadium.MARIO_STADIUM))
    marked = parse(pyrio.svg.stadium(Stadium.MARIO_STADIUM, marks=[Mark(x=1, z=50, shape=shape)]))
    assert count(marked, tag) == count(plain, tag) + 1


def test_text_is_escaped():
    svg = pyrio.svg.stadium(
        Stadium.MARIO_STADIUM,
        marks=[Mark(x=0, z=50, title="<Mario & Luigi>", label="a<b")],
        title="R&D",
    )
    root = parse(svg)
    assert root.findtext(f"{NS}title") == "R&D"
    assert root.findtext(f".//{NS}circle/{NS}title") == "<Mario & Luigi>"
    assert "a<b" in {t.text for t in root.findall(f"{NS}text")}


def test_flights_draw_from_above():
    flight = Flight(points=[(0.0, 1.0, 0.0), (10.0, 20.0, 30.0)])
    root = parse(pyrio.svg.stadium(Stadium.MARIO_STADIUM, flights=[flight]))
    polyline = root.find(f"{NS}polyline")
    assert polyline is not None
    assert polyline.get("points") == "0,0 10,-30"


def test_spray_chart_marks_each_fair_ball():
    fair = [
        e
        for e in GAME.events
        if e.contact is not None and e.contact.primary_result is not PrimaryContactResult.FOUL
    ]
    root = parse(pyrio.svg.spray_chart(GAME.events, stadium=GAME.stadium))
    tips = [t.text or "" for t in root.findall(f".//{NS}title")]
    assert len(tips) == len(fair)
    assert tips[0].startswith(fair[0].batter_spot.character.label)


def test_spray_chart_adds_fouls_on_request():
    without = parse(pyrio.svg.spray_chart(GAME.events, stadium=GAME.stadium))
    with_fouls = parse(pyrio.svg.spray_chart(GAME.events, stadium=GAME.stadium, fouls=True))
    fouls = sum(
        e.contact is not None and e.contact.primary_result is PrimaryContactResult.FOUL
        for e in GAME.events
    )
    assert fouls > 0
    assert len(with_fouls.findall(f".//{NS}title")) == len(without.findall(f".//{NS}title")) + fouls


def test_output_is_deterministic():
    one = pyrio.svg.spray_chart(GAME.events, stadium=GAME.stadium)
    assert one == pyrio.svg.spray_chart(GAME.events, stadium=GAME.stadium)

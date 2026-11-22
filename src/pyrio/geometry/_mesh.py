"""The stadium collision meshes: every surface the ball can touch."""

from __future__ import annotations

from dataclasses import dataclass
from functools import cache
from typing import TYPE_CHECKING, TypeAlias

from .._enum import CodeEnum
from . import _files
from ._point import Point

if TYPE_CHECKING:
    from .._codes import Stadium

__all__ = ["Surface", "Triangle", "triangles"]

MeshTriangle: TypeAlias = tuple[Point, Point, Point, int]
"""A triangle as the game stores it: mesh space (Y down) and its raw collision tag."""

FOUL_BIT = 0x80
"""Set on a collision tag when the surface is in foul territory."""


class Surface(CodeEnum):
    """What a collision triangle is made of (the decomp's ``BALL_COLLISION_TYPE``).

    The surface decides what a ball does on touching it: bounce and roll,
    rebound, or end the play. Labels are RioVisualizer's names.
    """

    GRASS = 1, "grass"
    WALL = 2, "wall"
    OUT_OF_PLAY = 3, "out of play"
    FOUL_POLE = 4, "foul pole"  # BALL_COLLISION_TYPE_FOUL_LINE: a ball off it is a home run
    UNCLIMBABLE_WALL = 5, "back wall"  # rebounds the ball exactly like WALL
    DIRT = 6, "dirt"
    PIT_WALL = 7, "pit wall"
    PIT = 8, "pit"
    ROUGH = 9, "rough"
    WATER = 10, "water"
    CHOMP_PEN = 11, "chomp pen"


@dataclass(frozen=True, slots=True)
class Triangle:
    """One collision triangle, in field coordinates (``y`` up).

    The vertices are in the game's winding order. The game's collision test is
    one-sided: a triangle stops only a ball coming at its front, the side
    ``(b - a) x (c - a)`` points to once ``y`` is flipped back to mesh space.
    """

    a: Point
    b: Point
    c: Point
    surface: Surface
    is_foul: bool


@cache
def mesh_triangles(stadium: Stadium) -> tuple[MeshTriangle, ...]:
    """The stadium's collision triangles in mesh space, in the game's order.

    Triangle strips are unrolled with the alternating winding the game gives
    them. The order matters to the live ball: of two hits at the same distance
    along a ray, the first triangle wins.
    """
    out: list[MeshTriangle] = []
    for box in _files.mesh(stadium)["Triangle Collections"]:
        for collection in box["Triangles"]:
            points = collection["Points"]
            strip = collection["CollectionType"] != 0
            for k, i in enumerate(range(0, len(points) - 2, 1 if strip else 3)):
                a, b, c = (_vertex(p["Point"]) for p in points[i : i + 3])
                tag: int = points[i + 2]["CollisionType"]
                out.append((c, b, a, tag) if strip and k % 2 else (a, b, c, tag))
    return tuple(out)


def _vertex(point: dict[str, float]) -> Point:
    return (point["X"], point["Y"], point["Z"])


def _to_field(p: Point) -> Point:
    return (p[0], -p[1], p[2])


@cache
def triangles(stadium: Stadium) -> tuple[Triangle, ...]:
    """Every collision triangle in the stadium, in field coordinates.

    This is the full-fidelity geometry the live ball casts against: walls of
    any shape, foul poles, the out-of-play structure, and the ground itself.
    """
    return tuple(
        Triangle(
            _to_field(a),
            _to_field(b),
            _to_field(c),
            Surface(tag & ~FOUL_BIT),
            bool(tag & FOUL_BIT),
        )
        for a, b, c, tag in mesh_triangles(stadium)
    )

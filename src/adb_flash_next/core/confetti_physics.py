"""Tiny particle physics for the finish animation (no Qt, so it can be tested)."""
from __future__ import annotations

import random
from dataclasses import dataclass


@dataclass
class Particle:
    x: float
    y: float
    vx: float
    vy: float
    size: float
    rotation: float
    spin: float  # degrees per second
    color_index: int


def make_particles(width: float, height: float, count: int, color_count: int, rng: random.Random) -> list[Particle]:
    """Confetti starting just above the top edge, spread across the width."""
    return [
        Particle(
            x=rng.uniform(0, max(width, 1.0)),
            y=rng.uniform(-max(height, 1.0) * 0.6, -10.0),
            vx=rng.uniform(-90.0, 90.0),
            vy=rng.uniform(60.0, 260.0),
            size=rng.uniform(6.0, 12.0),
            rotation=rng.uniform(0.0, 360.0),
            spin=rng.uniform(-360.0, 360.0),
            color_index=rng.randrange(max(color_count, 1)),
        )
        for _ in range(count)
    ]


def step_particles(particles: list[Particle], dt: float, gravity: float = 600.0, drag: float = 0.6) -> None:
    """Advance every particle by `dt` seconds, in place."""
    for p in particles:
        p.vy = min(p.vy + gravity * dt, 520.0)
        p.vx *= max(0.0, 1.0 - drag * dt)
        p.x += p.vx * dt
        p.y += p.vy * dt
        p.rotation = (p.rotation + p.spin * dt) % 360.0

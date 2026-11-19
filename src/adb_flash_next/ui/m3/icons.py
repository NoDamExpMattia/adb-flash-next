"""Vector icons drawn with QPainter on a 24x24 grid (no icon fonts or image files needed)."""
from __future__ import annotations

import math

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QPainter, QPainterPath, QPen, QPolygonF


def _dashboard(p: QPainter) -> None:
    for x, y, w, h in ((3, 3, 8, 10), (13, 3, 8, 6), (13, 11, 8, 10), (3, 15, 8, 6)):
        p.drawRoundedRect(QRectF(x, y, w, h), 2, 2)


def _images(p: QPainter) -> None:
    p.drawRoundedRect(QRectF(3, 4, 18, 16), 3, 3)
    p.drawEllipse(QPointF(8.5, 9.5), 1.6, 1.6)
    path = QPainterPath()
    path.moveTo(4, 18)
    path.lineTo(10, 12)
    path.lineTo(14, 16)
    path.lineTo(16.5, 13.5)
    path.lineTo(20, 17)
    p.drawPath(path)


def _flash(p: QPainter) -> None:
    p.drawPolygon(QPolygonF([
        QPointF(13, 2.5), QPointF(5.5, 13.5), QPointF(11, 13.5),
        QPointF(10, 21.5), QPointF(18.5, 10), QPointF(13, 10),
    ]))


def _power(p: QPainter) -> None:
    box = QRectF(5.5, 5.5, 13, 13)
    path = QPainterPath()
    path.arcMoveTo(box, 120)
    path.arcTo(box, 120, 300)
    p.drawPath(path)
    p.drawLine(QPointF(12, 3), QPointF(12, 11.5))


def _install(p: QPainter) -> None:
    p.drawLine(QPointF(12, 3.5), QPointF(12, 15))
    p.drawPolyline(QPolygonF([QPointF(7.5, 10.5), QPointF(12, 15), QPointF(16.5, 10.5)]))
    p.drawPolyline(QPolygonF([QPointF(4, 15), QPointF(4, 20), QPointF(20, 20), QPointF(20, 15)]))


def _tune(p: QPainter) -> None:
    for y, x in ((6, 9), (12, 15), (18, 8)):
        p.drawLine(QPointF(4, y), QPointF(x - 2.6, y))
        p.drawLine(QPointF(x + 2.6, y), QPointF(20, y))
        p.drawEllipse(QPointF(x, y), 2.2, 2.2)


def _menu(p: QPainter) -> None:
    for y in (6, 12, 18):
        p.drawLine(QPointF(4, y), QPointF(20, y))


def _refresh(p: QPainter) -> None:
    box = QRectF(5, 5, 14, 14)
    path = QPainterPath()
    path.arcMoveTo(box, 30)
    path.arcTo(box, 30, 300)
    p.drawPath(path)
    # Arrow head at the end of the arc (angle 330 degrees), pointing along the arc.
    end_angle = math.radians(330)
    ex = 12 + 7 * math.cos(end_angle)
    ey = 12 - 7 * math.sin(end_angle)
    dx, dy = -math.sin(end_angle), -math.cos(end_angle)
    px, py = -dy, dx
    p.drawPolyline(QPolygonF([
        QPointF(ex + px * 2.6 - dx * 0.5, ey + py * 2.6 - dy * 0.5),
        QPointF(ex + dx * 2.6, ey + dy * 2.6),
        QPointF(ex - px * 2.6 - dx * 0.5, ey - py * 2.6 - dy * 0.5),
    ]))


def _terminal(p: QPainter) -> None:
    p.drawPolyline(QPolygonF([QPointF(4.5, 6.5), QPointF(10.5, 12), QPointF(4.5, 17.5)]))
    p.drawLine(QPointF(12.5, 18), QPointF(19.5, 18))


def _recovery(p: QPainter) -> None:
    p.drawEllipse(QPointF(12, 12), 8.5, 8.5)
    p.drawLine(QPointF(12, 8), QPointF(12, 16))
    p.drawLine(QPointF(8, 12), QPointF(16, 12))


def _check(p: QPainter) -> None:
    p.drawPolyline(QPolygonF([QPointF(5, 12.5), QPointF(10, 17.5), QPointF(19, 7)]))



def _utilities(p: QPainter) -> None:
    p.drawRoundedRect(QRectF(3, 8, 18, 12), 2, 2)
    p.drawPolyline(QPolygonF([QPointF(9, 8), QPointF(9, 5), QPointF(15, 5), QPointF(15, 8)]))
    p.drawLine(QPointF(3, 13.5), QPointF(21, 13.5))


def _delete(p: QPainter) -> None:
    p.drawLine(QPointF(4, 7), QPointF(20, 7))
    p.drawPolyline(QPolygonF([QPointF(9, 7), QPointF(9, 4), QPointF(15, 4), QPointF(15, 7)]))
    p.drawPolyline(QPolygonF([QPointF(6, 7), QPointF(7, 20), QPointF(17, 20), QPointF(18, 7)]))
    p.drawLine(QPointF(10, 11), QPointF(10, 16))
    p.drawLine(QPointF(14, 11), QPointF(14, 16))


def _database(p: QPainter) -> None:
    p.drawEllipse(QRectF(5, 4, 14, 5))
    p.drawLine(QPointF(5, 6.5), QPointF(5, 17.5))
    p.drawLine(QPointF(19, 6.5), QPointF(19, 17.5))
    for top in (9.5, 15):
        path = QPainterPath()
        path.arcMoveTo(QRectF(5, top, 14, 5), 180)
        path.arcTo(QRectF(5, top, 14, 5), 180, 180)
        p.drawPath(path)


def _lock(p: QPainter) -> None:
    p.drawRoundedRect(QRectF(5, 11, 14, 10), 2, 2)
    path = QPainterPath()
    path.moveTo(8, 11)
    path.lineTo(8, 8)
    path.arcTo(QRectF(8, 4, 8, 8), 180, -180)
    path.lineTo(16, 11)
    p.drawPath(path)


def _shield(p: QPainter) -> None:
    p.drawPolygon(QPolygonF([
        QPointF(12, 3), QPointF(19, 6), QPointF(19, 12),
        QPointF(12, 21), QPointF(5, 12), QPointF(5, 6),
    ]))
    p.drawPolyline(QPolygonF([QPointF(9, 12), QPointF(11.2, 14.2), QPointF(15, 9.8)]))


_ICONS = {
    "dashboard": _dashboard,
    "images": _images,
    "flash": _flash,
    "reboot": _power,
    "install": _install,
    "settings": _tune,
    "menu": _menu,
    "refresh": _refresh,
    "terminal": _terminal,
    "recovery": _recovery,
    "check": _check,
    "utilities": _utilities,
    "delete": _delete,
    "database": _database,
    "lock": _lock,
    "shield": _shield,
}


def draw_icon(painter: QPainter, name: str, rect: QRectF, color: QColor, stroke: float = 2.0) -> None:
    """Draw icon `name` scaled into `rect`. Unknown names draw nothing."""
    draw = _ICONS.get(name)
    if draw is None:
        return
    painter.save()
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    painter.translate(rect.x(), rect.y())
    painter.scale(rect.width() / 24.0, rect.height() / 24.0)
    painter.setPen(QPen(color, stroke, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
    painter.setBrush(Qt.BrushStyle.NoBrush)
    draw(painter)
    painter.restore()

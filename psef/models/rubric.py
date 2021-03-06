"""This module defines a RubricRow.

SPDX-License-Identifier: AGPL-3.0-only
"""

import typing as t
import numbers
import datetime

from mypy_extensions import TypedDict

from . import Base, db, _MyQuery
from .. import helpers
from ..exceptions import APICodes, APIException


class RubricItem(Base):
    """This class holds the information about a single option/item in a
    :class:`.RubricRow`.
    """
    if t.TYPE_CHECKING:  # pragma: no cover
        query: t.ClassVar[_MyQuery['RubricItem']] = Base.query

    __tablename__ = 'RubricItem'

    id: int = db.Column('id', db.Integer, primary_key=True)
    rubricrow_id: int = db.Column(
        'Rubricrow_id', db.Integer,
        db.ForeignKey('RubricRow.id', ondelete='CASCADE')
    )
    header: str = db.Column('header', db.Unicode, default='')
    description: str = db.Column('description', db.Unicode, default='')
    points: float = db.Column('points', db.Float)

    # This variable is generated from the backref from RubricRow
    rubricrow: 'RubricRow'

    class JSONBaseSerialization(TypedDict, total=True):
        """The base serialization of a rubric item.
        """
        description: str
        header: str
        points: numbers.Real

    class JSONSerialization(JSONBaseSerialization, total=True):
        id: int

    def __to_json__(self) -> 'RubricItem.JSONSerialization':
        """Creates a JSON serializable representation of this object.
        """
        return {
            'id': self.id,
            'description': self.description,
            'header': self.header,
            # A float is a ``Real``, mypy issue:
            # https://github.com/python/mypy/issues/2636
            'points': t.cast(numbers.Real, self.points),
        }

    def copy(self) -> 'RubricItem':
        return RubricItem(
            header=self.header,
            description=self.description,
            points=self.points,
        )


class RubricRow(Base):
    """Describes a row of some rubric.

    This class forms the link between :class:`.Assignment` and
    :class:`.RubricItem` and holds information about the row.

    :ivar ~.RubricRow.assignment_id: The assignment id of the assignment that
        belows to this rubric row.
    """
    if t.TYPE_CHECKING:  # pragma: no cover
        query = Base.query  # type: t.ClassVar[_MyQuery['RubricRow']]
    __tablename__ = 'RubricRow'
    id: int = db.Column('id', db.Integer, primary_key=True)
    assignment_id: int = db.Column(
        'Assignment_id', db.Integer, db.ForeignKey('Assignment.id')
    )
    header: str = db.Column('header', db.Unicode)
    description: str = db.Column('description', db.Unicode, default='')
    created_at = db.Column(
        'created_at', db.DateTime, default=datetime.datetime.utcnow
    )
    items = db.relationship(
        "RubricItem",
        backref="rubricrow",
        cascade='delete-orphan, delete, save-update',
        order_by='asc(RubricItem.points)',
    )  # type: t.MutableSequence[RubricItem]

    def copy(self) -> 'RubricRow':
        return RubricRow(
            created_at=datetime.datetime.utcnow(),
            description=self.description,
            header=self.header,
            assignment_id=self.assignment_id,
            items=[item.copy() for item in self.items]
        )

    @property
    def is_valid(self) -> bool:
        """Check if the current row is valid.

        :returns: ``False`` if the row has no items or if the max points of the
            items is not > 0.
        """
        if not self.items:
            return False
        return max(it.points for it in self.items) >= 0

    def __to_json__(self) -> t.Mapping[str, t.Any]:
        """Creates a JSON serializable representation of this object.
        """
        return {
            'id': self.id,
            'header': self.header,
            'description': self.description,
            'items': self.items,
        }

    def _get_item(self, item_id: int) -> t.Optional['RubricItem']:
        """Get a rubric item from this row by id.

        :param item_id: The id of the item to get.
        :returns: The item found or ``None`` if the row didn't contain any item
            with the given id.
        """
        for item in self.items:
            if item.id == item_id:
                return item
        return None

    def update_items_from_json(
        self, items: t.List[RubricItem.JSONBaseSerialization]
    ) -> None:
        """Update the items of this row in place.

        .. warning::

            All items not present in the given ``items`` list will be deleted
            from the rubric row.

        :param items: The items (:class:`.RubricItem`) that should be added or
            updated. If ``id`` is in an item it should be an ``int`` and the
            rubric item with the corresponding ``id`` will be updated instead
            of added.
        :returns: Nothing.
        """
        # We store all new items in this list and not `self.items` as we need
        # to search for items in `self.items` if a rubric item needs to be
        # updated (instead of added).
        new_items: t.List[RubricItem] = []

        for item in items:
            item_description: str = item['description']
            item_header: str = item['header']
            points: numbers.Real = item['points']

            if 'id' in item:
                helpers.ensure_keys_in_dict(item, [('id', int)])
                item_id = t.cast(int, item['id'])  # type: ignore
                rubric_item = self._get_item(item_id)
                if rubric_item is None:
                    raise APIException(
                        "The requested rubric item is not present in this row",
                        f'The row "{self.id}" doesn\'t contain "{item_id}"',
                        APICodes.OBJECT_NOT_FOUND, 404
                    )

                rubric_item.header = item_header
                rubric_item.description = item_description
                rubric_item.points = float(points)
            else:
                rubric_item = RubricItem(
                    rubricrow=self,
                    description=item_description,
                    header=item_header,
                    points=points
                )

            new_items.append(rubric_item)

        self.items = new_items

    def update_from_json(
        self, header: str, description: str,
        items: t.List[RubricItem.JSONBaseSerialization]
    ) -> None:
        """Update this rubric in place.

        .. warning::

            All items not present in the given ``items`` list will be deleted
            from the rubric row.

        :param header: The new header of the row.
        :param description: The new description of the row.
        :param items: The items that should be in this row (see warning). The
            format is the same as the items passed to
            :meth:`.RubricRow.update_items_from_json`.
        :returns: Nothing.
        """
        self.header = header
        self.description = description
        self.update_items_from_json(items)

    @classmethod
    def create_from_json(
        cls: t.Type['RubricRow'], header: str, description: str,
        items: t.List[RubricItem.JSONBaseSerialization]
    ) -> 'RubricRow':
        """Create a new rubric row for an assignment.

        :param header: The name of the new rubric row.
        :param description: The description of the new rubric row.
        :param items: The items that should be added to this row. The format is
            the same as the items passed to
            :meth:`.RubricRow.update_items_from_json`.
        :returns: The newly created row.
        """
        self = cls(header=header, description=description)
        self.update_items_from_json(items)

        return self

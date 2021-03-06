# -*- coding:utf-8 -*-
#--
# Copyright (c) 2012-2014 Net-ng.
# All rights reserved.
#
# This software is licensed under the BSD License, as described in
# the file LICENSE.txt, which you should have received as part of
# this distribution.
#--

import datetime

from peak.rules import when

from nagare.i18n import _
from nagare.database import session
from nagare.security import common
from nagare import component, security

from kansha import validator
from kansha.card import Card
from kansha.board import Board
from kansha.column import Column
from kansha.user import usermanager
from kansha.services.search import schema
from kansha.cardextension import CardExtension
from kansha.board import COMMENTS_MEMBERS, COMMENTS_PUBLIC
from kansha.services.actionlog.messages import render_event

from .models import DataComment


@when(common.Rules.has_permission, "user and perm == 'comment' and isinstance(subject, Board)")
def has_permission_Board_comment(self, user, perm, board):
    return ((board.has_member(user) and board.comments_allowed == COMMENTS_MEMBERS)
            or ((board.comments_allowed == COMMENTS_PUBLIC) and user))


@when(common.Rules.has_permission, "user and perm == 'comment' and isinstance(subject, Column)")
def has_permission_Column_comment(self, user, perm, column):
    return security.has_permissions('comment', column.board)


@when(common.Rules.has_permission, "user and perm == 'comment' and isinstance(subject, Card)")
def has_permission_Card_comment(self, user, perm, card):
    return security.has_permissions('comment', card.column)


@when(common.Rules.has_permission, "user and (perm == 'delete_comment')")
def has_permission_delete_comment(self, user, perm, comment):
    return comment.is_author(user)


@when(common.Rules.has_permission, "user and (perm == 'edit_comment')")
def has_permission_edit_comment(self, user, perm, comment):
    return comment.is_author(user)


@when(render_event, "action=='card_add_comment'")
def render_event_card_add_comment(action, data):
    return _(u'User %(author)s has commented card "%(card)s"') % data


class Comment(object):

    """Comment component"""

    def __init__(self, data):
        """Initialization

        In:
            - ``data`` -- the comment object from the database
        """
        self.db_id = data.id
        self.text = data.comment
        self.creation_date = data.creation_date
        self.author = component.Component(usermanager.UserManager.get_app_user(data.author.username, data=data.author))
        self.comment_label = component.Component(Commentlabel(self))
        self.comment_label.on_answer(lambda v: self.comment_label.call(model='edit'))

    def edit_comment(self):
        self.comment_label.call(model='edit')

    def is_author(self, user):
        return self.author().username == user.username

    def set_comment(self, text):
        if text is None:
            return
        text = text.strip()

        if text:
            self.data.comment = validator.clean_text(text)

    @property
    def data(self):
        """Return the comment object from the database
        """
        return DataComment.get(self.db_id)


class Commentlabel(object):

    """comment label component.

    """

    def __init__(self, parent):
        """Initialization

        In:
          - ``parent`` -- parent of comment label
        """
        self.parent = parent
        self.text = parent.text or u''

    def change_text(self, text):
        """Change the comment of our wrapped object

        In:
            - ``text`` -- the new comment
        Return:
            - the new comment

        """
        if text is None:
            return
        text = text.strip()
        if text:
            text = validator.clean_text(text)
            self.text = text
            self.parent.set_comment(text)
            return text

    def is_author(self, user):
        return self.parent.is_author(user)


class Comments(CardExtension):

    LOAD_PRIORITY = 50

    """Comments component
    """

    def __init__(self, card, action_log, configurator):
        """Initialization

        In:
            - ``parent`` -- the parent card
            - ``comments`` -- the comments of the card
        """
        super(Comments, self).__init__(card, action_log, configurator)
        self.comments = [self._create_comment_component(data_comment) for data_comment in self.data]

    @staticmethod
    def get_schema_def():
        return schema.TEXT()

    def to_document(self):
        return u'\n'.join(comment().text for comment in self.comments)

    @property
    def data(self):
        return DataComment.get_by_card(self.card.data)

    def _create_comment_component(self, data_comment):
        return component.Component(Comment(data_comment)).on_answer(self.delete_comment)

    def add(self, v):
        """Add a new comment to the card

        In:
            - ``v`` -- the comment content
        """
        security.check_permissions('comment', self.card)
        if v is None:
            return
        v = v.strip()
        if v:
            v = validator.clean_text(v)
            user = security.get_user()
            comment = DataComment(comment=v, card_id=self.card.db_id,
                                  author=user.data, creation_date=datetime.datetime.utcnow())
            session.add(comment)
            session.flush()
            data = {'comment': v.strip(), 'card': self.card.get_title()}
            self.action_log.add_history(security.get_user(), u'card_add_comment', data)
            self.comments.insert(0, self._create_comment_component(comment))

    def delete_comment(self, comp):
        """Delete a comment.

        In:
            - ``comment`` -- the comment to delete
        """
        self.comments.remove(comp)
        comment = comp()
        DataComment.get(comment.db_id).delete()
        session.flush()

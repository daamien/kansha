#--
# Copyright (c) 2008-2013 Net-ng.
# All rights reserved.
#
# This software is licensed under the BSD License, as described in
# the file LICENSE.txt, which you should have received as part of
# this distribution.
#--

#--
# Copyright (c) 2012-2015 Net-ng.
# All rights reserved.
#
# This software is licensed under the BSD License, as described in
# the file LICENSE.txt, which you should have received as part of
# this distribution.
#--


"""
Create and (re)build the search index for cards.
It is safe to run it anytime.
Registered as a nagare-admin command.
Usage :
nagare-admin create-index <app name | config file>
"""

import pkg_resources

from nagare import database
from nagare.admin import util, command

from kansha.card.comp import Card
from kansha.column.comp import Column
from kansha.card.models import DataCard
from kansha.card.fts_schema import Card as SCard
from kansha.services.actionlog import DummyActionLog


def rebuild_index(app):
    # init index
    action_log = DummyActionLog()
    app.search_engine.create_collection([SCard])
    for card in DataCard.query:
        col = app._services(Column, card.column.id, card.column.board, app.card_extensions, action_log, app.search_engine, data=card.column)
        card = app._services(Card, card.id, col, app.card_extensions, action_log, data=card)
        scard = SCard(**card.to_document())
        app.search_engine.add_document(scard)
    app.search_engine.commit()


class ReIndex(command.Command):

    desc = '(Re-)Create index for the application.'

    @staticmethod
    def set_options(optparser):
        optparser.usage += ' [application]'

    @staticmethod
    def run(parser, options, args):

        try:
            application = args[0]
        except IndexError:
            application = 'kansha'

        (cfgfile, app, dist, conf) = util.read_application(application,
                                                           parser.error)
        requirement = (
            None if not dist
            else pkg_resources.Requirement.parse(dist.project_name)
        )
        data_path = (
            None if not requirement
            else pkg_resources.resource_filename(requirement, '/data')
        )

        (active_app, databases) = util.activate_WSGIApp(
            app, cfgfile, conf, parser.error, data_path=data_path)
        for (database_settings, populate) in databases:
            database.set_metadata(*database_settings)
        if active_app:
            rebuild_index(active_app)

# -*- coding:utf-8 -*-
#--
# Copyright (c) 2012-2014 Net-ng.
# All rights reserved.
#
# This software is licensed under the BSD License, as described in
# the file LICENSE.txt, which you should have received as part of
# this distribution.
#--

from kansha.cardextension.tests import CardExtensionTestCase

from .comp import Votes


class VoteTest(CardExtensionTestCase):
    def create_instance(self, card, action_log, configurator):
        return Votes(card, action_log, configurator)

    def test_toggle(self):
        self.extension.toggle()
        self.assertEqual(self.extension.count_votes(), 1)
        self.assertTrue(self.extension.has_voted())
        self.extension.toggle()
        self.assertEqual(self.extension.count_votes(), 0)
        self.assertFalse(self.extension.has_voted())

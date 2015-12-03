#--
# Copyright (c) 2012-2014 Net-ng.
# All rights reserved.
#
# This software is licensed under the BSD License, as described in
# the file LICENSE.txt, which you should have received as part of
# this distribution.
#--

import random

from cgi import FieldStorage
from webob.exc import HTTPOk

from nagare import component, security, var
from nagare.i18n import _

from kansha import notifications
from kansha.toolbox import overlay
from kansha.user import usermanager
from kansha.authentication.database import validators
from kansha.services.components_repository import CardExtension

from .models import DataGallery, DataAsset

IMAGE_CONTENT_TYPES = ('image/png', 'image/jpeg', 'image/pjpeg', 'image/gif')


class Gallery(CardExtension):

    LOAD_PRIORITY = 40

    def __init__(self, card, assets_manager_service):
        """Init method

        In:
            - ``card`` -- card component
        """
        self.card = card
        self.assets_manager = assets_manager_service
        self.data = DataGallery(self.card)

        self.assets = []
        self.overlays = []
        for data_asset in self.data.get_assets():
            self._create_asset_c(data_asset)
        #self.crop_overlay = None
        self.comp_id = str(random.randint(10000, 100000))

    def copy(self, parent, additional_data):
        new_extension = self.__class__(parent, self.assets_manager)
        for data_asset in self.data.get_assets():
            new_asset_id = self.assets_manager.copy(data_asset.filename)
            new_asset_data = data_asset.add_asset(new_asset_id, parent, additional_data['author'])
            new_extension._create_asset_c(new_asset_data)
            if data_asset.cover:
                new_asset_data.cover = parent.data
        return new_extension

    def _create_asset_c(self, data_asset):
        asset = Asset(data_asset, self.assets_manager)
        asset_thumb = component.Component(asset, 'thumb').on_answer(self.action)
        asset_menu = component.Component(asset, 'menu').on_answer(self.action)
        self.assets.append(asset_thumb)
        self.overlays.append(self._create_overlay_c(asset_thumb, asset_menu))
        return asset

    def _create_overlay_c(self, asset_thumb, asset_menu):
        return component.Component(overlay.Overlay(lambda h, asset_thumb=asset_thumb: asset_thumb.render(h),
                                                   lambda h, asset_menu=asset_menu: asset_menu.render(h),
                                                   dynamic=False, cls='card-edit-form-overlay'))

    def add_asset(self, new_file):
        """Add one new file to card

        In:
            - ``new_file`` -- new file to add

        Return:
            - The newly created Asset
        """
        validators.validate_file(new_file, self.assets_manager.max_size, _(u'File must be less than %d KB'))
        fileid = self.assets_manager.save(new_file.file.read(),
                                          metadata={'filename': new_file.filename, 'content-type': new_file.type})
        data = {'file': new_file.filename, 'card': self.card.title().text}
        notifications.add_history(self.card.column.board.data, self.card.data, security.get_user().data, u'card_add_file', data)
        return self._create_asset_c(self.data.add_asset(fileid))

    def add_assets(self, new_files):
        """Add new assets to the card

        In:
            - ``new_files`` -- new files to add
        """
        if isinstance(new_files, FieldStorage):
            self.add_asset(new_files)
        else:
            for new_file in new_files:
                self.add_asset(new_file)

    def get_asset(self, filename):
        """Return Asset component which match with filename

        In:
            - ``filename`` -- file id
        Return:
            - an Asset component
        """
        return Asset(self.data.get_asset(filename), self.assets_manager)

    def action(self, response):
        action, asset = response[0], response[1]
        if action == "download":
            pass
        elif action == "delete":
            self.delete_asset(asset)
        elif action == "make cover":
            self.make_cover(asset, *list(response[2]))
            # for data_asset in self.data.get_assets():
            #    self._create_asset_c(data_asset)
            # return "YAHOO.kansha.app.hideOverlay();"
        elif action == 'remove_cover':
            self.remove_cover(asset)

    def make_cover(self, asset, left, top, width, height):
        """Make the given asset as cover for the card

        In :
          - ``asset`` -- The asset to make as cover
          - ``left`` -- Left coordinate of the crop origin
          - ``top`` -- Top coordinate of the crop origin
          - ``width`` -- Crop width
          - ``height`` -- Crop height
        """
        self.assets_manager.create_cover(asset.filename, left, top, width, height)
        self.card.make_cover(asset)
        for a in self.assets:
            a().is_cover = False
        asset.is_cover = True

    def get_cover(self):
        cover = None
        if self.card.has_cover():
            cover = Asset(self.card.get_cover(), self.assets_manager)
        return cover

    def remove_cover(self, asset):
        """Don't use the asset as cover anymore

        In :
          - ``asset`` -- The asset
        """
        self.card.remove_cover()
        asset.is_cover = False

    def delete_asset(self, asset):
        """Delete asset

        Delete asset from card (component and overlay), database
        and asset manager.

        In:
            - ``asset`` -- Asset to delete
        """
        i = 0
        for a in self.assets:
            if a() == asset:
                self.assets.remove(a)
                self.overlays.pop(i)
                self.assets_manager.delete(asset.filename)
                self.data.delete(asset.filename)
                break
            i = i + 1

    def delete(self):
        '''Delete all assets'''
        for asset in self.data.get_assets():
            self.assets_manager.delete(asset.filename)
        self.assets = []
        self.overlays = []


class Asset(object):

    def __init__(self, data_asset, assets_manager_service):
        self.filename = data_asset.filename
        self.creation_date = data_asset.creation_date
        self.author = component.Component(usermanager.UserManager.get_app_user(data_asset.author.username, data=data_asset.author))
        self.assets_manager = assets_manager_service
        self.is_cover = data_asset.cover is not None
        self.cropper = None
        self.overlay_cropper = None

    def is_image(self):
        return self.assets_manager.get_metadata(self.filename)['content-type'] in IMAGE_CONTENT_TYPES

    def download_asset(self, size=None):
        e = HTTPOk()
        data, meta_data = self.assets_manager.load(self.filename, size)
        e.body = data
        e.content_type = str(meta_data['content-type'])
        e.title = meta_data['filename']
        #e.headers['Cache-Control'] = 'max-age=0, must-revalidate, no-cache, no-store'
        raise e

    @property
    def data(self):
        return DataAsset.get_by_filename(self.filename)

    def create_cropper_component(self, comp, card_component, card_component_id, card_component_model):
        self.cropper = component.Component(AssetCropper(self, card_component, card_component_id, card_component_model))
        asset_cropper_menu = component.Component(self, 'cropper_menu')
        self.asset_cropper = asset_cropper = component.Component(self, 'crop').on_answer(comp.answer)
        self.overlay_cropper = component.Component(overlay.Overlay(lambda h, asset_cropper_menu=asset_cropper_menu: asset_cropper_menu.render(h),
                                                                   lambda h, asset_cropper=asset_cropper: asset_cropper.render(h),
                                                                   dynamic=False,
                                                                   cls='card-edit-form-overlay',
                                                                   centered=True))


    def end_crop(self, comp, answ):
        comp.answer(('make cover', self, answ))


class AssetCropper(object):

    def __init__(self, asset, card_component, card_component_id, card_component_model):
        self.asset = asset
        self.card_component = card_component
        self.card_component_id = card_component_id
        self.card_component_model = card_component_model
        self.crop_left, self.crop_top, self.crop_width, self.crop_height = var.Var(), var.Var(), var.Var(), var.Var()

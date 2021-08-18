import os
import random
from collections import defaultdict
from math import ceil

import cv2
import numpy as np
from PIL import Image
from cytomine import Cytomine
from cytomine.models import ImageInstanceCollection, AnnotationCollection, PropertyCollection
from rasterio.features import rasterize
from shapely import wkt
from sklearn.utils import check_random_state
from torch.utils.data.dataset import Dataset

from dataset import DatasetsGenerator, convert_poly, BaseCrop, MemoryCrop, CropTrainDataset

MONUSEG_PROJECT = 532820586


def get_monuseg_data(data_path, mask_folder="masks", image_folder="images", incomplete_folder="incomplete",
                     complete_folder="complete", remove_ratio=0.0, seed=42):
    random_state = check_random_state(seed)
    data_path = os.path.join(data_path, "{}_{:0.4f}".format(seed, remove_ratio))
    train_path = os.path.join(data_path, "train")
    test_path = os.path.join(data_path, "test")
    images = ImageInstanceCollection().fetch_with_filter("project", MONUSEG_PROJECT)
    annotations = AnnotationCollection(project=MONUSEG_PROJECT, showWKT=True, showMeta=True).fetch()

    annot_per_image = defaultdict(list)
    # sorting for reproducibility
    for annot in sorted(annotations, key=lambda a: a.id):
        annot_per_image[annot.image].append(annot)

    train, test = dict(), dict()
    # sorting for reproducibility
    simages = sorted(images, key=lambda i: i.id)
    for image in simages:
        properties = PropertyCollection(image).fetch().as_dict()
        if properties["set"].value == "train":
            train[image.id] = image
        else:
            test[image.id] = image

    if remove_ratio > 0:
        train_ids = list(train.keys())
        random_state.shuffle(train_ids)
        half_train = len(train_ids) // 2
        incomplete = set(train_ids[half_train:])
    else:
        incomplete = set()

    for image in simages:
        if image.id in incomplete:
            write_path = os.path.join(train_path, incomplete_folder)
            image_annots = annot_per_image[image.id]
            random_state.shuffle(image_annots)
            n_annots = len(image_annots)
            to_keep = ceil(n_annots * (1 - remove_ratio))
            image_annots = image_annots[:to_keep]
        else:
            if image.id in train:
                write_path = os.path.join(train_path, complete_folder)
            else:
                write_path = test_path
            image_annots = annot_per_image[image.id]

        image_path = os.path.join(write_path, image_folder)
        os.makedirs(image_path, exist_ok=True)
        image.download(os.path.join(image_path, "{originalFilename}"), override=False)

        fg = [convert_poly(wkt.loads(a.location), 0, image.height) for a in image_annots]
        mask = rasterize(fg, out_shape=(image.height, image.width), fill=0, dtype=np.uint8) * 255
        mask_path = os.path.join(write_path, mask_folder)
        os.makedirs(mask_path, exist_ok=True)
        cv2.imwrite(os.path.join(mask_path, image.originalFilename.replace(".tif", ".png")), mask)


class MonusegDatasetGenerator(DatasetsGenerator):
    def __init__(self, data_path, tile_size, mask_folder="masks", image_folder="images", incomplete_folder="incomplete",
                     complete_folder="complete", missing_seed=42, remove_ratio=0.0):
        self._missing_seed = missing_seed
        self._remove_ratio = remove_ratio
        self._data_path = os.path.join(data_path, "{}_{:0.4f}".format(missing_seed, remove_ratio))
        self._train_path = os.path.join(self._data_path, "train")
        self._test_path = os.path.join(self._data_path, "test")
        self._mask_folder = mask_folder
        self._image_folder = image_folder
        self._incomplete_folder = incomplete_folder
        self._complete_folder = complete_folder
        self._tile_size = tile_size

        images = ImageInstanceCollection().fetch_with_filter("project", MONUSEG_PROJECT)
        annotations = AnnotationCollection(project=MONUSEG_PROJECT, showWKT=True, showMeta=True).fetch()
        a2i = defaultdict(list)
        for annot in annotations:
            a2i[annot.image].append(annot)
        self._annots_per_image = dict()
        for image in images:
            self._annots_per_image[image.originalFilename] = a2i[image.id]

    def _crops(self, path):
        images, masks = list(), list()
        for image_filename in os.listdir(os.path.join(path, self._image_folder)):
            images.append(os.path.join(path, self._image_folder, image_filename))
            mask_filename = image_filename.rsplit(".", 1)[0] + ".png"
            masks.append(os.path.join(path, self._mask_folder, mask_filename))
        return [MemoryCrop(i, m, tile_size=self._tile_size) for i, m in zip(images, masks)]

    def sets(self):
        return self._crops(os.path.join(self._train_path, self._incomplete_folder)), \
                self._crops(os.path.join(self._train_path, self._complete_folder)), \
                self._crops(self._test_path)

    def iterable_to_dataset(self, iterable, **kwargs):
        return CropTrainDataset(iterable, **kwargs)

    def val_roi_foreground(self, val_roi):
        return self._annots_per_image[os.path.basename(val_roi.img_path)]


def main(argv):
    with Cytomine.connect_from_cli(argv) as conn:
        get_monuseg_data("/scratch/users/rmormont/monuseg", remove_ratio=0.0, seed=42)


if __name__ == "__main__":
    import sys
    main(sys.argv[1:])

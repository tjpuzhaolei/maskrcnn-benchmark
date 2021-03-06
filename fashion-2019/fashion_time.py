# Copyright (c) Facebook, Inc. and its affiliates. All Rights Reserved.
import cv2
import os
import torch
import pylab
import random
import time
import numpy as np

from torchvision import transforms as T

from maskrcnn_benchmark.modeling.detector import build_detection_model
from maskrcnn_benchmark.utils.checkpoint import DetectronCheckpointer
from maskrcnn_benchmark.structures.image_list import to_image_list
from maskrcnn_benchmark.modeling.roi_heads.mask_head.inference import Masker

from maskrcnn_benchmark.config import cfg


class FashionPredictor(object):

    def __init__(
            self,
            confidence_threshold=0.7,
            show_mask_heatmaps=False,
            masks_per_dim=3,
            min_image_size=224,

    ):
        self.res_label_mask_scorse = []
        self.res_dir = './res_person/'
        config_file = "../configs/e2e_fashion_mask_rcnn_R_50_FPN_1x.yaml"
        cfg.merge_from_file(config_file)  # 设置配置文件
        cfg.merge_from_list(["MODEL.MASK_ON", True])
        # cfg.merge_from_list(["MODEL.DEVICE", "cpu"])  # 指定为CPU
        cfg.merge_from_list(["MODEL.DEVICE", "cuda"])  # 指定为GPU

        self.cfg = cfg.clone()
        self.model = build_detection_model(cfg)
        self.model.eval()
        self.device = torch.device(cfg.MODEL.DEVICE)
        self.model.to(self.device)
        self.min_image_size = min_image_size

        save_dir = cfg.OUTPUT_DIR
        checkpointer = DetectronCheckpointer(cfg, self.model, save_dir=save_dir)
        _ = checkpointer.load(cfg.MODEL.WEIGHT)

        self.transforms = self.build_transform()

        mask_threshold = -1 if show_mask_heatmaps else 0.5
        self.masker = Masker(threshold=mask_threshold, padding=1)

        # used to make colors for each class
        self.palette = torch.tensor([2 ** 25 - 1, 2 ** 15 - 1, 2 ** 21 - 1])


        self.confidence_threshold = confidence_threshold
        self.show_mask_heatmaps = show_mask_heatmaps
        self.masks_per_dim = masks_per_dim

    def build_transform(self):
        """
        Creates a basic transformation that was used to train the models
        """
        cfg = self.cfg

        # we are loading images with OpenCV, so we don't need to convert them
        # to BGR, they are already! So all we need to do is to normalize
        # by 255 if we want to convert to BGR255 format, or flip the channels
        # if we want it to be in RGB in [0-1] range.
        if cfg.INPUT.TO_BGR255:
            to_bgr_transform = T.Lambda(lambda x: x * 255)
        else:
            to_bgr_transform = T.Lambda(lambda x: x[[2, 1, 0]])

        normalize_transform = T.Normalize(
            mean=cfg.INPUT.PIXEL_MEAN, std=cfg.INPUT.PIXEL_STD
        )

        transform = T.Compose(
            [
                T.ToPILImage(),
                T.Resize(self.min_image_size),
                T.ToTensor(),
                to_bgr_transform,
                normalize_transform,
            ]
        )
        return transform

    def compute_prediction(self, original_image):
        """
        Arguments:
            original_image (np.ndarray): an image as returned by OpenCV

        Returns:
            prediction (BoxList): the detected objects. Additional information
                of the detection properties can be found in the fields of
                the BoxList via `prediction.fields()`
        """
        st = time.time()
        # apply pre-processing to image
        image = self.transforms(original_image)
        print('pre-processing time:',time.time() - st)

        st = time.time()
        # convert to an ImageList, padded so that it is divisible by
        # cfg.DATALOADER.SIZE_DIVISIBILITY
        image_list = to_image_list(image, self.cfg.DATALOADER.SIZE_DIVISIBILITY)
        image_list = image_list.to(self.device)
        print('convert to an ImageList time:', time.time() - st)

        st = time.time()
        # compute predictions
        with torch.no_grad():
            predictions = self.model(image_list)
        predictions = [o.to(self.device) for o in predictions]
        print('compute predictions time:', time.time() - st)

        # always single image is passed at a time
        prediction = predictions[0]

        # reshape prediction (a BoxList) into the original image size
        height, width = original_image.shape[:-1]
        prediction = prediction.resize((width, height))

        if prediction.has_field("mask"):
            # if we have masks, paste the masks in the right position
            # in the image, as defined by the bounding boxes
            masks = prediction.get_field("mask")
            # always single image is passed at a time
            masks = self.masker([masks], [prediction])[0]
            prediction.add_field("mask", masks)
        return prediction

    def predict(self, image_path):
        image = cv2.imread(image_path)

        s_time = time.time()

        predictions = self.compute_prediction(image)

        img_time = time.time() - s_time

        return img_time


def main():
    fashion_demo = FashionPredictor(  # 创建模型文件
        # min_image_size=1200,
        min_image_size=800,
        confidence_threshold=0.5,
    )

    image_path = '/data_sharing/data41_data1/zl9/fashion-2019/train_person/val/'
    # image_path = '/data_sharing/data41_data1/zl9/fashion-2019/test/'
    # image_path = '/Users/zl/Documents/fashion-2019/maskscoring_rcnn/data/fashion_test/test/'
    from glob import glob
    image_list = glob(image_path + '*.*')

    all_time = 0.0
    all_num = 0
    for img_path in image_list:

        print(img_path)
        try:
            img_time = fashion_demo.predict(img_path)
            all_time += img_time
            print('\n')
            all_num += 1
            if all_num > 40:
                break
        except Exception as e:
            print(e)
            continue

    print('image avg time :', all_time / float(all_num))


if __name__ == '__main__':
    main()

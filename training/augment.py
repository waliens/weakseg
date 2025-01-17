from functools import partial

import numpy as np
import torch
from skimage.color import rgb2hed, hed2rgb
from skimage.filters import gaussian
from skimage.util import random_noise
from sklearn.utils import check_random_state
from torchvision import transforms
from torchvision.transforms.functional import vflip, hflip
from PIL import Image


def random_blur(img, sigma_extent=0.1, random_state=None):
    rstate = check_random_state(random_state)
    return gaussian(img, sigma=rstate.uniform(0, sigma_extent), multichannel=True)


def random_gaussian_noise(img, var_extent=0.1, random_state=None):
    rstate = check_random_state(random_state)
    return random_noise(
        img, mode='gaussian',
        var=rstate.uniform(0, var_extent) ** 2,
        seed=rstate.randint(999999))


def random_hed_ratio(img, bias_range=0.025, coef_range=0.025, random_state=None):
    rstate = check_random_state(random_state)
    hed = rgb2hed(img)
    bias = rstate.uniform(-bias_range, bias_range, 3)
    coefs = rstate.uniform(1 - coef_range, 1 + coef_range, 3)
    return np.clip(hed2rgb(hed * coefs + bias), 0, 1)


def segmentation_transform(*images):
    if np.random.rand() > 0.5:
        images = (vflip(i) for i in images)
    if np.random.rand() > 0.5:
        images = (hflip(i) for i in images)
    images = (transforms.ToTensor()(i) for i in images)
    return images


class ToNumpy(torch.nn.Module):
    def forward(self, img):
        return np.asarray(img)


class ToPillow(torch.nn.Module):
    def forward(self, img):
        return Image.fromarray((img * 255).astype(np.uint8))


def random_multi_fn(tensors, fn=None, random_state=None, p=0.5):
    rstate = check_random_state(random_state)
    if rstate.rand() > p:
        return (fn(t) for t in tensors)
    else:
        return tensors


def multi_fn(tensors, fn=None):
    return (fn(t) for t in tensors)


# DEBUGGING FUNCTIONS
# def print_np(nparray, key=""):
#     import skimage
#     import os
#     print(key, nparray.shape, np.max(nparray), np.min(nparray))
#     skimage.io.imsave(os.path.join("/home/rmormont/tmp_aug/", "image_{}_{}.png".format(key, np.random.randint(1000000))), nparray)
#     return nparray
#
# def print_tensor(t, key=""):
#     import skimage
#     import os
#     skimage.io.imsave(os.path.join("/home/rmormont/tmp_aug/", "image_{}_{}.png".format(key, np.random.randint(1000000))), (np.moveaxis(t.numpy(), 0, 2) * 255).astype(np.uint8))
#     return t
#
# def print_pil(p:Image.Image, key=""):
#     import os
#     print(key, (p.height, p.width), p.getbands(), p.getextrema()[0], p.getextrema()[0])
#     p.save(os.path.join("/home/rmormont/tmp_aug/", "image_{}_{}.png".format(key, np.random.randint(1000000))))
#     return p

def get_aug_transforms(aug_noise_var_extent=0.1, aug_blur_sigma_extent=0.1, aug_hed_bias_range=0.025, aug_hed_coef_range=0.025, seed=42):
    aug_rstate = check_random_state(seed)
    struct_transform = [
        partial(random_multi_fn, fn=vflip, random_state=aug_rstate),
        partial(random_multi_fn, fn=hflip, random_state=aug_rstate),
        # TODO elastic transform
        # partial(
        #     random_elastic_transform,
        #     alpha_low=args.aug_elastic_alpha_low,
        #     alpha_high=args.aug_elastic_alpha_high,
        #     sigma_low=args.aug_elastic_sigma_low,
        #     sigma_high=args.aug_elastic_sigma_high,
        #     random_state=aug_rstate)
    ]
    visual_transform = [
        ToNumpy(),
        partial(random_hed_ratio, bias_range=aug_hed_bias_range, coef_range=aug_hed_coef_range, random_state=aug_rstate),
        partial(random_gaussian_noise, var_extent=aug_noise_var_extent, random_state=aug_rstate),
        partial(random_blur, sigma_extent=aug_blur_sigma_extent, random_state=aug_rstate),
        transforms.Lambda(lambda img: img.astype(np.float32)),
        transforms.ToTensor()
    ]

    return transforms.Compose(struct_transform), transforms.Compose(visual_transform)


def get_norm_transform():
    return transforms.Compose([
        transforms.ToTensor()
    ])
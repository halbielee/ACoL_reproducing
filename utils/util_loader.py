import os
import torch
from torchvision import transforms
from torch.utils.data import DataLoader
from utils.dataset.cub import CUBDataset
from utils.util import IMAGE_MEAN_VALUE, IMAGE_STD_VALUE


def data_loader(args):

    transform_train = transforms.Compose([
        transforms.Resize((args.resize_size, args.resize_size)),
        transforms.RandomCrop(args.crop_size),
        transforms.RandomHorizontalFlip(),
        transforms.ToTensor(),
        transforms.Normalize(IMAGE_MEAN_VALUE, IMAGE_STD_VALUE)])
    if args.VAL_CROP:
        transform_val = transforms.Compose([
            transforms.Resize((args.resize_size, args.resize_size)),
            transforms.CenterCrop(args.crop_size),
            transforms.ToTensor(),
            transforms.Normalize(IMAGE_MEAN_VALUE, IMAGE_STD_VALUE),
        ])
    else:
        transform_val = transforms.Compose([
            transforms.Resize((args.crop_size, args.crop_size)),
            transforms.ToTensor(),
            transforms.Normalize(IMAGE_MEAN_VALUE, IMAGE_STD_VALUE),
        ])

    img_train = CUBDataset(
        root=args.data_root,
        datalist=os.path.join(args.data_list, 'train.txt'),
        transform=transform_train,
        is_train=True
    )
    img_val = CUBDataset(
        root=args.data_root,
        datalist=os.path.join(args.data_list, 'test.txt'),
        transform=transform_val,
        is_train=False
    )

    if args.distributed:
        train_sampler = torch.utils.data.distributed.DistributedSampler(img_train)
    else:
        train_sampler = None

    train_loader = DataLoader(img_train,
                              batch_size=args.batch_size,
                              shuffle=(train_sampler is None),
                              sampler=train_sampler,
                              num_workers=args.workers)

    val_loader = DataLoader(img_val,
                            batch_size=args.batch_size,
                            shuffle=False,
                            num_workers=args.workers)

    return train_loader, val_loader, train_sampler

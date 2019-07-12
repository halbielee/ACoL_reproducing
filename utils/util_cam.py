import os, sys
sys.path.append(os.path.dirname(os.path.abspath(os.path.dirname(__file__))))
import torch
import cv2
import numpy as np
from network import resnet_se
import matplotlib.pyplot as plt


features_blobs = []
fc_blobs = []


def hook_feature(model, input, output):
    features_blobs.append(output)


def hook_fc(model, input, output):
    fc_blobs.append(output)


def get_cam(model, input, net_type):
    '''
    Get cam tensor from the model and input, for the position of cam net_type is necessary.
    Output is cam tensor for the input and output
    shape: batch_size x 14 x 14
    '''
    global features_blobs, fc_blobs

    if 'se_resnet' in net_type:
        try:
            feature_hook = model.layer4.register_forward_hook(hook_feature)
            fc_hook = model.fc.register_forward_hook(hook_fc)
        except:
            feature_hook = model.module.layer4.register_forward_hook(hook_feature)
            fc_hook = model.module.fc.register_forward_hook(hook_fc)
    elif 'vgg' in net_type:
        try:
            feature_hook = model.relu.register_forward_hook(hook_feature)
            fc_hook = model.fc.register_forward_hook(hook_fc)
        except:
            feature_hook = model.module.relu.register_forward_hook(hook_feature)
            fc_hook = model.module.fc.register_forward_hook(hook_fc)

    _ = model(input)
    feature_hook.remove()
    fc_hook.remove()
    if 'resnet' in net_type:
        try:
            fc_weight = model.fc.weight.squeeze()
        except:
            fc_weight = model.module.fc.weight.squeeze()
    if 'se_resnet' in net_type:
        try:
            fc_weight = model.fc.weight.squeeze()
        except:
            fc_weight = model.module.fc.weight.squeeze()
    elif 'vgg' in net_type:
        try:
            fc_weight = model.fc.weight.squeeze()
        except:
            fc_weight = model.module.fc.weight.squeeze()
    else:
        raise Exception("I am sorry, We are preparing for this.")

    feature_blob = torch.cat(features_blobs, 0)
    fc_blob = torch.cat(fc_blobs, 0)
    features_blobs.clear()
    fc_blobs.clear()
    pred = fc_blob.topk(1, 1, True, True)[1]
    pred_weight = fc_weight[pred, :]
    pred_weight = pred_weight.view(pred_weight.size(0), -1).unsqueeze(2).unsqueeze(3)

    cam = (pred_weight * feature_blob).detach().cpu().numpy()
    cam = cam.mean(1).squeeze()
    return cam


def get_heatmap(image, mask):
    mask = mask - np.min(mask)
    mask = mask / np.max(mask)
    heatmap = cv2.applyColorMap(np.uint8(255 * mask), cv2.COLORMAP_JET)
    heatmap = np.float32(heatmap) / 255
    cam = heatmap + np.float32(image) / 255
    cam = cam / np.max(cam)
    return heatmap * 255., cam * 255.


def large_rect(rect):
    # find largest recteangles
    large_area = 0
    target = 0
    for i in range(len(rect)):
        area = rect[i][2] * rect[i][3]
        if large_area < area:
            large_area = area
            target = i

    x = rect[target][0]
    y = rect[target][1]
    w = rect[target][2]
    h = rect[target][3]

    return x, y, w, h


def get_bbox(image, cam, thresh, gt_box, image_name, save_dir='test', isSave=False):
    gxa = int(gt_box[0])
    gya = int(gt_box[1])
    gxb = int(gt_box[2])
    gyb = int(gt_box[3])

    image_size = 224
    adjusted_gt_bbox = []
    adjusted_gt_bbox.append(max(gxa, 0))
    adjusted_gt_bbox.append(max(gya, 0))
    adjusted_gt_bbox.append(min(gxb, image_size-1))
    adjusted_gt_bbox.append(min(gyb, image_size-1))
    '''
    image: single image, shape (224, 224, 3)
    cam: single image, shape(14, 14)
    thresh: the floating point value (0~1)
    '''
    # resize to original size
    # image = cv2.resize(image, (224, 224))
    cam = cv2.resize(cam, (image_size, image_size))

    # convert to color map
    heatmap = intensity_to_rgb(cam, normalize=True)

    heatmap = cv2.cvtColor(heatmap, cv2.COLOR_RGB2BGR)
    # blend the original image with estimated heatmap
    blend = image * 0.5 + heatmap * 0.5

    # initialization for boundary box
    bbox_img = image.astype('uint8').copy()
    heatmap = heatmap.astype('uint8')
    blend = blend.astype('uint8')
    blend_box = blend.copy()
    # thresholding heatmap
    gray_heatmap = cv2.cvtColor(heatmap.copy(), cv2.COLOR_RGB2GRAY)
    th_value = np.max(gray_heatmap) * thresh

    _, thred_gray_heatmap = \
        cv2.threshold(gray_heatmap, int(th_value),
                      255, cv2.THRESH_TOZERO)
    try:
        _, contours, _ = \
            cv2.findContours(thred_gray_heatmap, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)
    except:
        contours, _ = \
            cv2.findContours(thred_gray_heatmap, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)

    # calculate bbox coordinates

    rect = []
    for c in contours:
        x, y, w, h = cv2.boundingRect(c)
        rect.append([x, y, w, h])
    if len(rect) == 0:
        estimated_box = [0,0,1,1]
    else:
        x, y, w, h = large_rect(rect)
        estimated_box = [x, y, x + w, y + h]

        cv2.rectangle(bbox_img, (x, y), (x + w, y + h), (0, 255, 0), 2)
        cv2.rectangle(blend_box, (x, y), (x + w, y + h), (0, 255, 0), 2)

    cv2.rectangle(bbox_img, (adjusted_gt_bbox[0], adjusted_gt_bbox[1]),
                  (adjusted_gt_bbox[2], adjusted_gt_bbox[3]), (0, 0, 255), 2)
    cv2.rectangle(blend_box, (adjusted_gt_bbox[0], adjusted_gt_bbox[1]),
                  (adjusted_gt_bbox[2], adjusted_gt_bbox[3]), (0, 0, 255), 2)
    concat = np.concatenate((bbox_img, heatmap, blend), axis=1)

    if isSave:
        if not os.path.isdir(os.path.join('image_path/', save_dir)):
            os.makedirs(os.path.join('image_path', save_dir))
        cv2.imwrite(os.path.join(os.path.join('image_path/',
                                              save_dir,
                                              image_name.split('/')[-1])), concat)
    blend_box = cv2.cvtColor(blend_box, cv2.COLOR_BGR2RGB).copy()

    return estimated_box, adjusted_gt_bbox, blend_box


def intensity_to_rgb(intensity, cmap='cubehelix', normalize=False):
    """
    Convert a 1-channel matrix of intensities to an RGB image employing a colormap.
    This function requires matplotlib. See `matplotlib colormaps
    <http://matplotlib.org/examples/color/colormaps_reference.html>`_ for a
    list of available colormap.
    Args:
        intensity (np.ndarray): array of intensities such as saliency.
        cmap (str): name of the colormap to use.
        normalize (bool): if True, will normalize the intensity so that it has
            minimum 0 and maximum 1.
    Returns:
        np.ndarray: an RGB float32 image in range [0, 255], a colored heatmap.
    """
    assert intensity.ndim == 2, intensity.shape
    intensity = intensity.astype("float")

    if normalize:
        intensity -= intensity.min()
        intensity /= intensity.max()

    cmap = 'jet'
    cmap = plt.get_cmap(cmap)
    intensity = cmap(intensity)[..., :3]
    return intensity.astype('float32') * 255.0


def main():

    models = getattr(resnet_se, 'se_resnet50')
    model = models(False)

    input = torch.ones((5,3,224,224))

    cam = get_cam(model, input, 'se_resnet')

    input = input.numpy().transpose(0, 2, 3, 1)
    print(input.shape)
    for i in range(5):
        bbox = get_bbox(input[i], cam[i], 0.2)
        print(bbox)

    return

if __name__ == '__main__':
    main()

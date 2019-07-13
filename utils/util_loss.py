import torch.nn as nn


class Loss():

    def __init__(self, gpu=None):
        if gpu is None:
            self.criterion_A = nn.CrossEntropyLoss()
            self.criterion_B = nn.CrossEntropyLoss()
        else:
            self.criterion_A = nn.CrossEntropyLoss().cuda(gpu)
            self.criterion_B = nn.CrossEntropyLoss().cuda(gpu)

    def cuda(self, gpu):
        self.criterion_A = self.criterion_A.cuda(gpu)
        self.criterion_B = self.criterion_B.cuda(gpu)

    def get_loss(self, logits_A, logits_B, gt_label):
        loss_A = self.criterion_A(logits_A, gt_label)
        loss_B = self.criterion_B(logits_B, gt_label)
        return loss_A + loss_B